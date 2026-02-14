# Validation Checklist

## Layer 1 — Rule Formalization
- [ ] Every discretionary phrase mapped to formula
- [ ] Each formula has explicit units and inequality direction
- [ ] Long/short symmetry verified
- [ ] Edge cases documented (zero-range candles, gaps, missing bars)

## Data Integrity
- [ ] Timezone normalized
- [ ] Session flags present and correct
- [ ] OHLC constraints validated (`low <= open/close <= high`)
- [ ] Duplicate/missing timestamps handled

## Backtest Integrity
- [ ] No lookahead bias
- [ ] Same inputs => identical outputs (determinism)
- [ ] Fees/slippage included
- [ ] Entry/exit reasons logged

## Strategy Sanity
- [ ] Pass/fail funnel generated
- [ ] Trade distribution by hour/session reviewed
- [ ] Stop behavior inspected on sample trades
- [ ] Out-of-sample run completed

## Collaboration Readiness
- [ ] Parameter list prepared for teammate review
- [ ] Disagreement points listed as explicit toggles
- [ ] Changelog updated with rule revisions
