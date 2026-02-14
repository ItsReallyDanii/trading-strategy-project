# Rule Definitions (Binary Conditions)

## Notation
- `C_t, O_t, H_t, L_t`: close/open/high/low of bar t
- `V_t`: volume of bar t
- `KL_t`: active key level at bar t
- `ATR_t`: ATR(n) at bar t
- `tick`: minimum price increment
- `dir ∈ {long, short}`

## Core Parameters (initial defaults)
- `confirm_buffer = max(0.05% * price, 2 * tick)`
- `max_retest_bars = 4`  # 4 x 15m = 60 min
- `retest_tolerance = max(0.03% * price, 1 * tick)`
- `min_rejection_wick_ratio = 0.25`
- `thresholdA_min_excursion = 0.10 * ATR_t`
- `thresholdB_close_strength = 0.55`  # close location in bar range
- `stop_buffer = 1 * tick`

## Discretionary → Binary Mapping

### 1) "Is it real?" (break confirmation)
Long:
`is_real_break_long = (C_t > KL_t + confirm_buffer) AND (H_t > KL_t + confirm_buffer)`
Short:
`is_real_break_short = (C_t < KL_t - confirm_buffer) AND (L_t < KL_t - confirm_buffer)`

### 2) "Retest failing?" (numerical retest pass/fail)
For long, in bars `t+1 ... t+max_retest_bars`, let `r` be first bar with `L_r <= KL_t + retest_tolerance`:
`retest_seen_long = exists r`
`retest_hold_long = (C_r >= KL_t - retest_tolerance)`
`retest_fail_long = (C_r < KL_t - retest_tolerance)`

Short mirrors with high/close inequalities.

### 3) "Pass both thresholds"
Threshold A (minimum directional excursion after retest):
Long:
`thresholdA_pass = (max(H_{r:r+k}) - KL_t) >= thresholdA_min_excursion`
Short:
`thresholdA_pass = (KL_t - min(L_{r:r+k})) >= thresholdA_min_excursion`
where `k = 2` bars by default.

Threshold B (close-strength on confirmation bar `c`):
`close_location_value = (C_c - L_c) / max(H_c - L_c, tiny)`
Long:
`thresholdB_pass = close_location_value >= thresholdB_close_strength`
Short:
`thresholdB_pass = close_location_value <= (1 - thresholdB_close_strength)`

Final:
`both_thresholds_pass = thresholdA_pass AND thresholdB_pass`

### 4) "Bounce back from thin line/wick"
Long wick rejection:
`wick_rejection_long = ((min(O_r, C_r) - L_r) / max(H_r - L_r, tiny)) >= min_rejection_wick_ratio`
Short wick rejection:
`wick_rejection_short = ((H_r - max(O_r, C_r)) / max(H_r - L_r, tiny)) >= min_rejection_wick_ratio`

### 5) "Did candle close above/below level?"
Long:
`close_confirms_long = C_t > KL_t + confi
