# Trading Strategy Project — Canonical Handoff State

## Objective
Stabilize automated intraday ingestion + evaluation + learning refresh so the pipeline is deterministic and CI-safe, while keeping deploy scope locked to QQQ unless gates explicitly approve additional symbols.

---

## Current Deployment Policy
- Expected deploy scope: `QQQ` only
- If no symbols pass gates, fallback should still preserve `QQQ` tradable scope (champion fallback), and deploy-scope validation must pass.

---

## Environment
- Repo path: `/workspaces/trading-strategy-project`
- Runtime: GitHub Codespaces + `.venv`
- Main orchestration command:
  - `python -m src.learning.auto_refresh --symbols QQQ,SPY,AAPL,IWM --champion outputs/learning/champion.json --leaderboard outputs/learning/challenger_leaderboard.csv`

---

## Failing Command (historical)
`python -m src.learning.auto_refresh --symbols QQQ,SPY,AAPL,IWM --champion outputs/learning/champion.json --leaderboard outputs/learning/challenger_leaderboard.csv`

---

## Exact Error (historical root failure)
From `src.evaluation.promote_symbols`:
- `KeyError: 'exp_post_005'`
- Stack path indicated merge output in `_build_tradable_scope` did not contain `exp_post_005`
- This cascaded to:
  - `RuntimeError: Command failed (1): ... python -m src.evaluation.promote_symbols`
  - Then auto_refresh terminated.

---

## Expected Behavior
1. `append_market_data` should not corrupt/empty raw/history files when provider returns no new 1m rows.
2. `run_universe`, `rolling_validation`, `stress_test_costs`, `promote_symbols`, `validate_deploy_scope`, and challenger search should complete without runtime exceptions.
3. If gates fail for all symbols, system should fallback to champion symbol (`QQQ`) and pass deploy-scope validation.
4. Outputs should be regenerated deterministically:
   - `outputs/reports/tradable_symbols_next.csv`
   - `outputs/reports/cost_stress_summary.csv`
   - `outputs/universe/universe_summary.csv`
   - `outputs/rolling/rolling_summary.csv`
   - `outputs/learning/challenger_leaderboard.csv`
   - `outputs/learning/refresh_audit.csv`

---

## What Already Tried
- Added/ran workflows at intraday cadence (3-minute schedule in market window).
- Multiple `auto_refresh` runs with symbols: `QQQ,SPY,AAPL,IWM`.
- Adjusted data append behavior to avoid overwriting with empty frames.
- Added fallback logic in promote/deploy flow so no-pass gates can revert to champion (`QQQ`).
- Re-ran end-to-end pipeline after fixes.

---

## Current Observed State (latest logs)
- `append_market_data` prints Yahoo “possibly delisted; no price data found” for requested 1m windows, but pipeline still proceeds with existing history/raw data.
- `run_universe`:
  - QQQ has trades and positive expectancy.
  - SPY/AAPL/IWM show zero trades.
- `rolling_validation`:
  - QQQ mixed fold performance (some positive, some negative).
  - SPY weak/mostly non-positive.
- `stress_test_costs`:
  - In latest successful pass, QQQ shown as active under tradable scope.
- `promote_symbols`:
  - “No symbols passed gates. Fallback to champion symbol: QQQ”
- `validate_deploy_scope`:
  - “Deploy scope OK: QQQ only.”
- `challenger_search`:
  - QQQ produces meaningful candidate metrics.
  - SPY/AAPL/IWM mostly all-zero candidate rows.
- `auto_refresh`:
  - Completes with “No champion refresh. Existing champion retained.”

---

## Open Concerns
1. Data provider availability for intraday 1m window in current runtime/timezone context.
2. Ensuring append job never rewrites usable datasets with empty fetch outputs.
3. Whether non-QQQ symbols should remain in learning loop if they are consistently all-zero.
4. Maintaining CI logs concise enough for fast triage.

---

## Immediate Verification Commands
```bash
python -m src.tools.append_market_data
python -m src.evaluation.run_universe
python -m src.evaluation.rolling_validation
python -m src.evaluation.stress_test_costs
python -m src.evaluation.promote_symbols
python -m src.tools.validate_deploy_scope
python -m src.learning.auto_refresh --symbols QQQ,SPY,AAPL,IWM --champion outputs/learning/champion.json --leaderboard outputs/learning/challenger_leaderboard.csv
