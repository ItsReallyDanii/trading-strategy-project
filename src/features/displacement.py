import pandas as pd


def compute_true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    out["tr"] = compute_true_range(out)
    out["atr"] = out["tr"].rolling(period, min_periods=period).mean()
    return out


def displacement_pass(
    move_size: float, atr_value: float, threshold_mult: float
) -> bool:
    if pd.isna(atr_value) or atr_value <= 0:
        return False
    return move_size >= threshold_mult * atr_value

