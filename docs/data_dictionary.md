# Data Dictionary

## OHLCV Core Fields
- `timestamp` (datetime, tz-aware): bar end timestamp
- `symbol` (string)
- `open` (float)
- `high` (float)
- `low` (float)
- `close` (float)
- `volume` (float/int)
- `vwap` (float, optional)
- `trade_count` (int, optional)

## Session Metadata Fields
- `exchange` (string): e.g., XNAS, XNYS
- `timezone` (string): e.g., America/New_York
- `session_date` (date): exchange-local trading date
- `is_rth` (bool): regular trading hours flag
- `session_open_ts` (datetime)
- `session_close_ts` (datetime)
- `is_half_day` (bool)
- `is_holiday_session` (bool)
- `minutes_from_open` (int)
- `minutes_to_close` (int)

## Strategy-Derived Fields
- `key_level` (float)
- `break_direction` (enum: long/short/none)
- `confirm_buffer` (float)
- `is_real_break` (bool)
- `retest_seen` (bool)
- `retest_hold` (bool)
- `retest_fail` (bool)
- `wick_rejection_pass` (bool)
- `thresholdA_pass` (bool)
- `thresholdB_pass` (bool)
- `both_thresholds_pass` (bool)
- `entry_signal` (bool)
- `initial_stop` (float)
- `trailing_stop` (float)

## Trade Log Fields
- `trade_id` (string)
- `entry_ts`, `entry_px`
- `exit_ts`, `exit_px`
- `side` (long/short)
- `qty`
- `stop_path` (json/string)
- `pnl_gross`, `pnl_net`
- `reason_code_entry`, `reason_code_exit`
