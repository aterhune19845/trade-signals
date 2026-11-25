# Daytrade Bot — Public Signal Track Record

<!-- strategy-evidence-v1:start -->

## Strategy evidence versus actual account results

**These are separate records, not a blended track record.** The `Strategy` column/row in the
legacy account export means the **actual broker account**, including broker-access failures.
It is not the broker-neutral strategy shadow. Original commits, signal rows, and account
returns have not been relabeled as hypothetical fills or overwritten by shadow results.

### Hypothetical canonical-strategy shadow — not live trading

Normalized shadow index: **100.556951**; return **+0.556951%** from 2026-11-18 through 2026-11-25. Current shadow drawdown: 0.000000%.

This separate index is anchored at 100 on November 18, 2026 using the pre-block portfolio
fractions. It follows the **first saved scheduled decision** each session, not later retry
decisions, under a frozen 5% drift band, 0.05% proportional cash reserve and 3-basis-point
modeled cost per dollar traded. It has no deposits or transfers. It uses archived adjusted
engine observations, with QQQ/GLD proxies for QQQM/GLDM and cross-vintage dividend/split
alignment. Fractional trading is assumed; broker minimums, regulatory fees, settlement,
and account-specific risk overrides are **not** simulated. Canonical model safety remains.

Rows labeled `retrospective-from-contemporaneously-archived-inputs` were calculated later
from inputs saved at the original decision time. They were **not** published or traded then.
`prospective` rows are subsequently calculated forward under the same policy. A passing
hash/replay check verifies consistency, **not** investment merit, actual fills, an independent
audit, or suitability of hypothetical performance for marketing.

- [Shadow returns](performance/strategy_shadow.csv) · [Hash-linked evidence](performance/strategy_shadow.jsonl)
- [Frozen policy and limitations](performance/strategy_shadow_policy.json) · [Current validation status](performance/strategy_shadow_latest.json)
- [Published calculation source](performance/methodology/strategy_forward_evidence_v1.py)
- [Activation provenance](performance/evidence_activation.json): original Git commit and file hashes before this separate track was added.
- [Append-only execution-label corrections](signals/execution_corrections.jsonl): blocked/rejected is not intentional holding.

Missing sessions or changed old inputs cause a visible failure. Previously published shadow
rows cannot be silently recalculated; a changed policy requires a separate version.

### Capture continues without the trading bot

An independent, data-only recorder captures the same canonical engine five minutes before
the exchange close, including early closes. It cannot place, replace, or cancel orders.
IBKR quote reads have a guarded Schwab quote fallback; data still require valid access and
freshness. Missing data produces an explicit failure, not an invented signal. A separate
archived-engine replay audit runs before the 16:20 ET GitHub publication. Actual-account
valuations remain dated observations; no simulated value is substituted for a missing NAV.

The already-published v1 shadow calculator and its existing rows remain unchanged. A
separately disclosed source adapter adds the independent captures. New signal records use
`not_executed_signal_only` when no broker execution took place.

[Capture-source provenance](performance/strategy_capture_sources.jsonl) ·
[Independent replay status](performance/strategy_capture_audit_latest.json) ·
[Recorder/source adapter activation](performance/strategy_recorder_activation.json)

<!-- strategy-evidence-v1:end -->

> For informational and educational purposes only. NOT investment advice, not a solicitation, and not a recommendation to buy or sell any security. Past and simulated performance does not guarantee future results. The author is not a registered investment adviser.

This repository publishes the systematic strategy's target weights, a separate
hypothetical strategy shadow, and a cash-flow-adjusted actual-account return series.
Signals are recorded by a near-close decision process even when broker execution
is stopped. They are published after the close, not as a
pre-trade signal service or a subscriber-fill performance record. Git records
publication times and revisions; historical signal records may be corrected
with an accompanying audit note.

## Latest signal — data date `2026-11-25`

| Ticker | Target weight |
|---|---|
| BIL | 83.8% |
| TLT | 16.2% |

- **Equity exposure:** 0
- **Gold exposure:** 0
- **Catastrophe stop:** no
- **Published (UTC):** 2026-11-25T21:20:12Z
- **Execution status:** `not_executed_signal_only`
- **Decision source:** `execution-independent-signal-capture`
- **Engine:** `validate_combined fortify=True cat_dd=-0.32 rebal_drift=0.05 pvol=0.19 risk_on_confirm=5 dip_confirm=9 halt_confirm=5 excess_mom_regime m3_intl_regime cash_tips_regime gold2x_available=False`

Machine-readable: [`signals/latest.json`](signals/latest.json) ·
full history: [`signals/history.jsonl`](signals/history.jsonl)

## Performance

Live account, cash-flow-adjusted index (inception = 100.00 on 2026-06-18, 109 trading days):

| Series | Index | Since inception |
|---|---|---|
| Actual account | **90.8** | -9.20% |
| SPY | 96.97 | -3.03% |

Returns use date-weighted Modified Dietz adjustments for recorded live deposits and withdrawals. Only explicitly tagged live observations are included; earlier untagged or paper rows are excluded. SPY uses adjusted closes over the same dates. This is the broker account's return, not a simulated return for a public follower's execution.

Reconciliation: **reconciled**. Detected cash credits require broker verification; unavailable commissions remain unknown, not zero. Account NAV already reflects broker-charged costs; fees are not deducted a second time. Latest observation: 2026-11-23T14:37:30.397413+00:00; this is not an official closing valuation.

_Index only — no account balances are published. Full daily series: [`performance/nav.csv`](performance/nav.csv)._

## What is published (and what is not)

- **Published:** daily target weights, exposures, and a normalized performance
  index (start = 100).
- **Never published:** account balances, dollar amounts, broker details, API
  keys, or any credential.

## How to read the signals

`signals/history.jsonl` is one JSON object per line. A same-day rerun can refresh
the latest row, and audited historical corrections are identified in the record.
Fields: `published_utc`, `status` (`ok` or `error`), `data_date`, `weights`
(tradeable ETF tickers → target fraction), `cash`, `eq_exposure`,
`gold_exposure`, `cat_halted`, `engine`. A `status: error` row means the
publisher detected a data-source mismatch and **withheld** that day's signal
(the last verified signal is shown in the README, stamped as possibly stale).

---
*Auto-generated by `publish.py`. Do not edit by hand.*
