import pandas as pd


def add_intraday_session_fields(df: pd.DataFrame, tz: str = "America/New_York") -> pd.DataFrame:
    out = df.copy()
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC").tz_convert(tz)
    else:
        out.index = out.index.tz_convert(tz)

    out["session_date"] = out.index.date
    out["hour"] = out.index.hour
    out["minute"] = out.index.minute
    out["is_rth"] = ((out["hour"] > 9) | ((out["hour"] == 9) & (out["minute"] >= 30))) & (
        (out["hour"] < 16) | ((out["hour"] == 16) & (out["minute"] == 0))
    )
    return out


def add_liquidity_levels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds:
      - premarket_high, premarket_low
      - prev_day_high, prev_day_low
      - day_high_so_far, day_low_so_far
    """
    out = df.copy()

    # day high/low so far
    out["day_high_so_far"] = out.groupby("session_date")["high"].cummax()
    out["day_low_so_far"] = out.groupby("session_date")["low"].cummin()

    # premarket = before 09:30
    pre = out[(out["hour"] < 9) | ((out["hour"] == 9) & (out["minute"] < 30))]
    pm_hi = pre.groupby("session_date")["high"].max().rename("premarket_high")
    pm_lo = pre.groupby("session_date")["low"].min().rename("premarket_low")

    out = out.merge(pm_hi, on="session_date", how="left")
    out = out.merge(pm_lo, on="session_date", how="left")

    # prev day high/low
    day_hi = out.groupby("session_date")["high"].max().rename("day_high")
    day_lo = out.groupby("session_date")["low"].min().rename("day_low")

    day_df = pd.concat([day_hi, day_lo], axis=1).reset_index()
    day_df["prev_day_high"] = day_df["day_high"].shift(1)
    day_df["prev_day_low"] = day_df["day_low"].shift(1)

    out = out.merge(day_df[["session_date", "prev_day_high", "prev_day_low"]], on="session_date", how="left")

    return out

