"""File-only canonical-strategy shadow. Never connect to a broker or revise old rows.

This is a normalized hypothetical book, NOT simulated customer fills. Marks use
frozen near-close engine observations. Cross-vintage adjustment scales are aligned
on a shared completed session before the prior decision (dividends/splits).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from decision_replay import get_blob
from live_certification import EVIDENCE_PATH, effective_evidence, verify_evidence

ALIASES = {'QQQM': 'QQQ', 'GLDM': 'GLD'}
BASE_POLICY = {
    'schema': 'canonical-strategy-shadow-policy/v1',
    'anchor_session': '2026-11-18', 'initial_index': 100.0,
    'seed': 'actual pre-block portfolio fractions; account dollar balance is not used',
    'target': 'archived broker-neutral canonical target, before account/broker overrides',
    'decision_selection': 'first scheduled daily cycle with same-session replay inputs; ignore deposit cycles/retries',
    'rebalance_band_l1': 0.05, 'cash_reserve_fraction': 0.0005,
    'slippage_bps_per_dollar_traded': 3.0,
    'external_flows': 'none; normalized strategy unit, independent of deposits/transfers',
    'price_basis': 'frozen near-close engine observations; vintages aligned at last shared completed session before prior decision',
    'price_proxies': ALIASES,
    'limitations': [
        'Hypothetical canonical-target book; not proof of broker acceptance, fills, or realized performance.',
        'Assumes fractional execution; no broker minimums, fixed/regulatory fees, settlement, or market capacity.',
        'Cash earns zero; ETF expenses/leverage financing are embedded in observed/proxy price returns.',
        'Canonical model safety rules retained; customer-account catastrophe overrides are not applied.',
        'Proxy returns and cross-vintage adjustment alignment are modeling assumptions, not actual ETF fills or broker cash dividends.',
        'No strategy returns inferred for missing sessions; missing evidence is a hard failure.',
        'Does not replace or splice into the real-account performance history.',
    ],
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def clean_weights(weights):
    result = {str(k): float(v) for k, v in weights.items() if float(v) != 0}
    if any(not math.isfinite(v) or v < 0 for v in result.values()) or sum(result.values()) > 1.00001:
        raise ValueError('Invalid long-only weights')
    return result


def scheduled_events(path=EVIDENCE_PATH):
    chain = verify_evidence(path)
    if not chain['ok']:
        raise ValueError('Source evidence chain failed validation')
    rows = effective_evidence([json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()])
    selected = {}
    for envelope in sorted(rows, key=lambda x: x['record'].get('decision_time_et', '')):
        event = envelope['record']
        day = str(event.get('decision_time_et', ''))[:10]
        if (event.get('mode') != 'live' or day < BASE_POLICY['anchor_session']
                or event.get('execution_context', {}).get('gate_band') is None):
            continue
        reference = event.get('replay_evidence', {})
        if day in selected:
            continue
        if reference.get('session') != day:
            raise ValueError('Scheduled decision does not have same-session inputs: ' + day)
        capsule = json.loads(get_blob(reference['capsule_sha256']))
        if capsule['session'] != day:
            raise ValueError('Capsule session mismatch')
        target = capsule['target']
        context_target = event['execution_context'].get('model_target', {})
        if any(context_target.get(k) != value for k, value in target.items()):
            raise ValueError('Canonical target link mismatch')
        selected[day] = (envelope, capsule)
    return selected


def market_factors(previous_capsule, capsule, previous_day, day, symbols):
    import numpy as np
    with np.load(io.BytesIO(get_blob(capsule['arrays'])), allow_pickle=False) as arrays, \
            np.load(io.BytesIO(get_blob(previous_capsule['arrays'])), allow_pickle=False) as prior:
        dates = [str(x)[:10] for x in arrays['dates'].astype('datetime64[ns]')]
        prior_dates = [str(x)[:10] for x in prior['dates'].astype('datetime64[ns]')]
        if dates[-1] != day or prior_dates[-1] != previous_day or previous_day not in dates:
            raise ValueError('Price observation coverage mismatch')
        common = sorted(set(dates) & set(prior_dates))
        common = [d for d in common if d < previous_day]
        if not common:
            raise ValueError('Missing completed-session adjustment anchor')
        anchor = common[-1]
        result = {}
        for symbol in symbols:
            name = ALIASES.get(symbol, symbol)
            if name not in capsule['price_names'] or name not in previous_capsule['price_names']:
                raise ValueError('Missing held-symbol price: ' + symbol)
            prices = arrays['p' + str(capsule['price_names'].index(name))]
            prior_prices = prior['p' + str(previous_capsule['price_names'].index(name))]
            values = [float(prior_prices[-1]), float(prices[-1]),
                      float(prices[dates.index(anchor)]), float(prior_prices[prior_dates.index(anchor)])]
            if not all(math.isfinite(v) and v > 0 for v in values):
                raise ValueError('Invalid price observation')
            old, new, adjusted_anchor, prior_anchor = values
            result[symbol] = new / (old * adjusted_anchor / prior_anchor)
        return result


def advance(previous, target, factors, policy):
    """Mark old holdings BEFORE using today's decision; self-financing estimated costs."""
    target = clean_weights(target)
    positions = {s: value * factors[s] for s, value in previous['position_values'].items()}
    before = sum(positions.values()) + previous['cash_value']
    held = {s: value / before for s, value in positions.items()}
    drift = sum(abs(target.get(s, 0) - held.get(s, 0)) for s in set(target) | set(held))
    rebalance = drift >= policy['rebalance_band_l1'] or any(
        value > 1e-12 and target.get(s, 0) == 0 for s, value in positions.items())
    nav, cost, turnover = before, 0.0, 0.0
    cash = previous['cash_value']
    if rebalance:
        rate = policy['slippage_bps_per_dollar_traded'] / 10000
        reserve = policy['cash_reserve_fraction']
        for _ in range(60):
            desired = {s: nav * (1 - reserve) * w for s, w in target.items()}
            turnover = sum(abs(desired.get(s, 0) - positions.get(s, 0)) for s in set(desired) | set(positions))
            nav = before - turnover * rate
        positions = {s: nav * (1 - reserve) * w for s, w in target.items()}
        cash = nav - sum(positions.values())
        cost = before - nav
    if nav <= 0 or cash < -1e-8 or abs(sum(positions.values()) + cash - nav) > 1e-8:
        raise ValueError('Shadow accounting conservation failed')
    peak = max(previous['peak_index'], nav)
    return {
        'index': nav, 'peak_index': peak, 'drawdown_pct': (nav / peak - 1) * 100,
        'daily_return_pct': (nav / previous['index'] - 1) * 100,
        'position_values': positions, 'cash_value': max(0, cash),
        'drift_l1': drift, 'hypothetical_rebalance': rebalance,
        'modeled_cost_index_units': cost, 'modeled_turnover_index_units': turnover,
    }


def verify_rows(rows):
    previous = None
    for row in rows:
        content = {k: v for k, v in row.items() if k != 'record_sha256'}
        if content.get('previous_record_sha256') != previous or digest(content) != row.get('record_sha256'):
            raise ValueError('Strategy shadow evidence hash chain failed')
        previous = row['record_sha256']


def publish_shadow(directory, *, events=None, now=None):
    """Append deterministic modeled evidence; refuse stale, missing, or revised inputs."""
    now = now or datetime.now(timezone.utc)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    events = scheduled_events() if events is None else events
    if BASE_POLICY['anchor_session'] not in events:
        raise ValueError('Pre-block anchor evidence is missing')
    days = sorted(events)
    import pandas_market_calendars as mcal
    expected = [str(day.date()) for day in mcal.get_calendar('XNYS').valid_days(days[0], days[-1])]
    if days != expected:
        raise ValueError('Missing scheduled session evidence: ' + ','.join(sorted(set(expected) - set(days))))
    # A missing new session must never be hidden by a stale last event.
    from backtest_inputs import completed_through
    if days[-1] < str(completed_through(now.isoformat())):
        raise ValueError('Strategy shadow has no evidence for latest completed session')
    policy_path = directory / 'strategy_shadow_policy.json'
    if policy_path.exists():
        policy = json.loads(policy_path.read_text())
        if (any(policy.get(k) != v for k, v in BASE_POLICY.items()) or
                policy.get('implementation_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
            raise ValueError('Frozen shadow policy changed; use a new version')
    else:
        policy = dict(BASE_POLICY, activated_utc=now.isoformat(), reconstructed_through=days[-1],
                      implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    policy_hash = digest(policy)
    path = directory / 'strategy_shadow.jsonl'
    old = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    verify_rows(old)
    if len(old) > len(days):
        raise ValueError('Archived sessions disappeared')
    rows = []
    for i, day in enumerate(days):
        envelope, capsule = events[day]
        event = envelope['record']
        target = clean_weights(capsule['target']['weights'])
        if any(ALIASES.get(s, s) not in capsule['price_names'] for s in target):
            raise ValueError('Missing target instrument price mapping')
        if i == 0:
            positions = {s: v * 100 for s, v in clean_weights(event['actual_after']).items()}
            state = {'index': 100.0, 'peak_index': 100.0, 'drawdown_pct': 0.0,
                     'daily_return_pct': 0.0, 'position_values': positions,
                     'cash_value': 100 - sum(positions.values()), 'drift_l1': None,
                     'hypothetical_rebalance': False, 'modeled_cost_index_units': 0.0,
                     'modeled_turnover_index_units': 0.0}
            factors = {}
        else:
            factors = market_factors(events[days[i - 1]][1], capsule, days[i - 1], day,
                                     rows[-1]['position_values'])
            state = advance(rows[-1], target, factors, policy)
        publication_time = old[i]['published_utc'] if i < len(old) else now.isoformat()
        publication_day = datetime.fromisoformat(publication_time).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        row = {
            'schema': 'canonical-strategy-shadow/v1', 'session_date': day,
            'basis': 'hypothetical-strategy-shadow-not-realized-account-return',
            'publication_basis': ('retrospective-from-contemporaneously-archived-inputs'
                                  if day <= policy['reconstructed_through'] or publication_day != day else 'prospective'),
            'published_utc': publication_time,
            'decision_time_et': event['decision_time_et'], 'decision_id': event['decision_id'],
            'source_event_sha256': envelope['event_sha256'],
            'capsule_sha256': event['replay_evidence']['capsule_sha256'],
            'input_arrays_sha256': capsule['arrays'], 'policy_sha256': policy_hash,
            'target_weights': target, 'held_price_factors': factors,
            'input_fail_safe': bool(capsule['target'].get('input_fail_safe')),
            'previous_record_sha256': rows[-1]['record_sha256'] if rows else None,
            **state,
        }
        row['record_sha256'] = digest(row)
        if i < len(old) and row != old[i]:
            raise ValueError('Previously published shadow evidence changed: ' + day)
        rows.append(row)
    # All source/data/accounting checks above succeed before any public files are changed.
    from live_signal_snapshot import atomic_write_json
    atomic_write_json(policy_path, policy)
    text = ''.join(canonical(row) + '\n' for row in rows)
    temporary = path.with_suffix('.jsonl.tmp')
    temporary.write_text(text)
    temporary.replace(path)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['date', 'strategy_shadow_index', 'daily_return_pct', 'drawdown_pct', 'publication_basis'])
    for row in rows:
        writer.writerow([row['session_date'], f"{row['index']:.8f}", f"{row['daily_return_pct']:.8f}",
                         f"{row['drawdown_pct']:.8f}", row['publication_basis']])
    csv_path = directory / 'strategy_shadow.csv'
    csv_tmp = csv_path.with_suffix('.csv.tmp'); csv_tmp.write_text(stream.getvalue()); csv_tmp.replace(csv_path)
    summary = {'status': 'ok', 'basis': rows[-1]['basis'], 'start_date': days[0], 'last_date': days[-1],
               'sessions': len(rows), 'index': rows[-1]['index'], 'return_pct': rows[-1]['index'] - 100,
               'drawdown_pct': rows[-1]['drawdown_pct'], 'head_sha256': rows[-1]['record_sha256'],
               'policy_sha256': policy_hash, 'limitations': policy['limitations']}
    atomic_write_json(directory / 'strategy_shadow_latest.json', summary)
    return summary
