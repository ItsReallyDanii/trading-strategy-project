# Strategy Spec: Key Level Retest + 15m Structure Confirmation

## Objective
Trade directional moves after key-level interaction, requiring break + close confirmation, retest validation, and threshold checkpoint passage.

## Timeframes
- Signal context: 15m
- Optional precision: 1m

## Preconditions
- Market hours active
- Symbol tradable
- Key level defined

## Entry Conditions
1. Price interacts with key level.
2. Break direction identified (above/below).
3. Candle close confirms break direction.
4. Retest occurs and confirms hold/fail behavior in break direction.
5. Threshold checkpoint A passed.
6. Threshold checkpoint B passed.

## Risk Management
- Initial stop at structural invalidation level (candle/wick reference).
- Trail stop to new wick structure as trade progresses.
- Exit immediately on stop breach.

## No-Trade Conditions
- No close confirmation.
- Retest absent or failed.
- Threshold checkpoints not both passed.
- Price condition vs market start level invalid.

## Logging Requirements
- Timestamp
- Symbol
- Direction
- Level values
- Threshold values
- Entry/stop/exit
- Reason codes for every decision node
