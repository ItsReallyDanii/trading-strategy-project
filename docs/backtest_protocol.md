# Backtest Protocol

## Objective
Validate deterministic rules before any parameter optimization.

## Data Split
1. In-sample: 60%
2. Validation: 20%
3. Out-of-sample: 20%
Split by time (no random shuffle).

## Simulation Rules
- Signal generated at bar close.
- Entry at next bar open.
- Stop checked intrabar with conservative fill assumption.
- Fees/slippage applied per trade.

## Metrics
- Win rate
- Profit factor
- Expectancy per trade
- Max drawdown
- Sharpe/Sortino (optional in v1)
- Exposure time
- Trade frequency
- Regime breakdown (trend/sideways if tagged)

## Diagnostics
- Count each gate pass/fail:
  - real break
  - retest seen
  - retest hold
  - threshold A/B
- Report attrition funnel by condition.

## Acceptance Criteria (v1)
- Strategy executes with zero runtime errors.
- Deterministic rerun (identical trades given same inputs + seed).
- Non-random edge proxy:
  - Profit factor > 1.1 out-of-sample
  - Max drawdown within predefined risk budget
  - Condition funnel shows coherent filtering (not near-random pass rates)

## Prohibitions
- No threshold tuning on out-of-sample.
- No adding new discretionary conditions during evaluation pass.
