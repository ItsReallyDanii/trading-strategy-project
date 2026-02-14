# Assumptions

## Market/Session
- Trading is evaluated in exchange-local regular session (RTH) unless explicitly configured otherwise.
- Session calendar/holidays are reliable from selected calendar source.
- Corporate actions are adjusted in historical data if strategy requires adjusted bars.

## Data
- OHLCV bars are chronologically ordered and complete.
- No lookahead leakage in feature generation.
- Timezone normalization is handled before rule evaluation.

## Execution
- Default fill model: next-bar open after signal.
- Slippage and fees are applied in backtest.
- No partial fill simulation in v1.

## Risk
- One position per symbol at a time (v1).
- Hard stop honored exactly in simulator constraints.
- Overnight exposure disabled unless explicitly enabled.

## Scope
- Layer 1 goal is deterministic logic, not optimization.
- Parameters marked "initial defaults" are calibration candidates, not fixed truths.
