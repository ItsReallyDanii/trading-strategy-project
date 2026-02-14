Trading Strategy Project (QQQ-Scoped, Intraday Ingestion + Auto-Refresh)

A practical, automation-first trading research pipeline that:

ingests market data (1m),

resamples to 3m bars,

runs evaluation + rolling validation + cost stress,

promotes tradable symbols under strict gates,

enforces deploy scope = QQQ only as a safety constraint,

performs challenger search and champion refresh logging.

This README is focused on what the project does, how to run it, expected outputs, and failure handling.

1) Project Objective

Maintain a deterministic daily/intraday workflow for strategy evaluation and controlled learning with guardrails:

Primary deployment symbol: QQQ

Fallback behavior: if no symbols pass promotion gates, force QQQ

Safety check: deploy-scope validator must pass (QQQ only)

No silent data loss: ingestion should avoid empty overwrites

2) High-Level Pipeline

Ingest + append market data

Pull recent 1m data

Merge with history

Resample to 3m OHLCV

Run universe evaluation

Run rolling validation

Run cost stress test

Promote symbols

Gate candidates

If none pass, fallback to QQQ

Validate deploy scope

Must equal QQQ-only

Run challenger search

Generate leaderboard

Refresh champion

Update or retain champion based on rules

Append refresh audit

3) Expected Repository Structure (Core Paths)
/workspaces/trading-strategy-project
├── src/
│   ├── tools/
│   │   ├── append_market_data.py
│   │   └── validate_deploy_scope.py
│   ├── evaluation/
│   │   ├── run_universe.py
│   │   ├── rolling_validation.py
│   │   ├── stress_test_costs.py
│   │   └── promote_symbols.py
│   └── learning/
│       ├── auto_refresh.py
│       └── challenger_search.py
├── data/
│   ├── raw/
│   │   ├── QQQ_3m.csv
│   │   ├── SPY_3m.csv
│   │   ├── AAPL_3m.csv
│   │   └── IWM_3m.csv
│   └── history/
│       ├── QQQ_3m_history.csv
│       ├── SPY_3m_history.csv
│       ├── AAPL_3m_history.csv
│       └── IWM_3m_history.csv
├── outputs/
│   ├── universe/universe_summary.csv
│   ├── rolling/
│   │   ├── rolling_summary.csv
│   │   └── rolling_stability.csv
│   ├── reports/
│   │   ├── cost_stress_summary.csv
│   │   └── tradable_symbols_next.csv
│   └── learning/
│       ├── champion.json
│       ├── challenger_leaderboard.csv
│       └── refresh_audit.csv
└── .github/workflows/
    ├── intraday-ingest.yml
    ├── auto-refresh.yml
    └── daily-learning-refresh.yml

4) Environment Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

5) Primary Commands
A) One-shot end-to-end auto refresh
python -m src.learning.auto_refresh \
  --symbols QQQ,SPY,AAPL,IWM \
  --champion outputs/learning/champion.json \
  --leaderboard outputs/learning/challenger_leaderboard.csv

B) Manual step-by-step (debug mode)
python -m src.tools.append_market_data
python -m src.evaluation.run_universe
python -m src.evaluation.rolling_validation
python -m src.evaluation.stress_test_costs
python -m src.evaluation.promote_symbols
python -m src.tools.validate_deploy_scope
python -m src.learning.challenger_search --symbol QQQ --input data/raw/QQQ_3m.csv --out outputs/learning/challenger_leaderboard.csv

6) Success Criteria

A healthy run should produce:

outputs/reports/tradable_symbols_next.csv with at least:

QQQ (fallback or passed gates)

src.tools.validate_deploy_scope result:

Deploy scope OK: QQQ only.

Updated:

outputs/learning/challenger_leaderboard.csv

outputs/learning/refresh_audit.csv

7) Known Failure Modes and Meaning
1) KeyError: 'exp_post_005' in promote_symbols

Cause: merged frame missing expected metric column (schema mismatch / incomplete upstream output).

Required behavior: no crash. Missing columns should be defaulted (e.g., fill with 0) and fallback logic should still emit QQQ.

2) “No symbols passed gates” + deploy scope empty

Cause: gating rejected all symbols and fallback not applied correctly.

Required behavior: write tradable_symbols_next.csv with QQQ fallback.

3) yfinance “possibly delisted; no price data found” for valid tickers

Cause: request window timing/availability issue (commonly off-hours or data window mismatch), not true delisting.

Required behavior: ingestion should not wipe existing history/raw files when fetch returns empty.

8) Data Integrity Requirements (Non-Negotiable)

Never overwrite history/raw with empty fetch results.

Deduplicate by timestamp and keep last.

Keep sorted chronological index.

Resample deterministically to 3m OHLCV.

Preserve continuity checks where applicable.

9) GitHub Actions Intent

Intraday ingest: runs frequently (e.g., every 3 minutes in market window)

Daily refresh: post-close learning/evaluation sweep

Auto refresh: orchestrated end-to-end command

If schedules overlap, enforce idempotence and empty-fetch-safe writes.

10) Minimal Operational Policy

Deployment remains QQQ-only until explicit policy change.

SPY/AAPL/IWM may run in evaluation/learning lanes but are non-deploy unless gates + scope policy are updated.

Any scope violation should fail fast.

11) Quick Verification Checklist

After a run:

outputs/reports/tradable_symbols_next.csv exists and contains QQQ

validate_deploy_scope passes with QQQ-only

universe_summary.csv, rolling_summary.csv, cost_stress_summary.csv are fresh

challenger_leaderboard.csv updated

refresh_audit.csv appended

No empty-file overwrite in data/raw or data/history

12) Canonical Handoff File

Create and maintain:

handoff/state.md


Recommended sections:

objective

failing command

exact error

expected behavior

what already tried

This keeps sessions deterministic and prevents context loss across tools/chats.

13) Example handoff/state.md Template
# State Handoff

## Objective
Keep pipeline stable with deploy scope QQQ-only and safe intraday ingestion.

## Failing Command
python -m src.learning.auto_refresh --symbols QQQ,SPY,AAPL,IWM --champion outputs/learning/champion.json --leaderboard outputs/learning/challenger_leaderboard.csv

## Exact Error
KeyError: 'exp_post_005' in src/evaluation/promote_symbols.py

## Expected Behavior
No crash; missing metrics handled safely; if no symbols pass, fallback to QQQ; deploy scope validator passes.

## What Already Tried
- Re-ran auto_refresh
- Ran step-by-step modules
- Checked outputs/reports/tradable_symbols_next.csv
- Confirmed QQQ fallback behavior in some runs
