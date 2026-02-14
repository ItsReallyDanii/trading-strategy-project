import pandas as pd


def add_intraday_session_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        raise TypeError("add_intraday_session_fields expects DatetimeIndex")

    # convert to NY session context
    ts_ny = out.index.tz_convert("America/New_York")
    out["session_date"] = ts_ny.date
    out["hour"] = ts_ny.hour
    out["minute"] = ts_ny.minute

    # RTH: 09:30 to 16:00 NY
    mins = out["hour"] * 60 + out["minute"]
    out["is_rth"] = (mins >= (9 * 60 + 30)) & (mins <= 16 * 60)

    return out


def add_liquidity_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # hard-cast OHLCV to numeric to avoid object cummax/cummin crashes
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(subset=["open", "high", "low", "close"])

    if "session_date" not in out.columns:
        raise ValueError("session_date missing. Run add_intraday_session_fields first.")

    # rolling intraday range
    out["day_high_so_far"] = out.groupby("session_date")["high"].cummax()
    out["day_low_so_far"] = out.groupby("session_date")["low"].cummin()

    # previous day high/low
    day_hilo = out.groupby("session_date").agg(day_high=("high", "max"), day_low=("low", "min")).sort_index()
    day_hilo["prev_day_high"] = day_hilo["day_high"].shift(1)
    day_hilo["prev_day_low"] = day_hilo["day_low"].shift(1)

    out = out.join(day_hilo[["prev_day_high", "prev_day_low"]], on="session_date")

    return out
