from dataclasses import dataclass
from typing import Optional, List

import pandas as pd

from src.features.displacement import add_atr, displacement_pass


@dataclass
class ExternalState:
    bias: str  # "bull", "bear", "range", "none"
    protected_swing_high: Optional[float]
    protected_swing_low: Optional[float]
    last_bos: Optional[str]   # "bull_bos", "bear_bos", None
    last_choch: Optional[str] # "bull_choch", "bear_choch", None


def _pivot_high(df: pd.DataFrame, i: int) -> bool:
    if i < 1 or i >= len(df) - 1:
        return False
    return (
        df["high"].iloc[i] > df["high"].iloc[i - 1]
        and df["high"].iloc[i] > df["high"].iloc[i + 1]
    )


def _pivot_low(df: pd.DataFrame, i: int) -> bool:
    if i < 1 or i >= len(df) - 1:
        return False
    return (
        df["low"].iloc[i] < df["low"].iloc[i - 1]
        and df["low"].iloc[i] < df["low"].iloc[i + 1]
    )


def build_external_structure(
    df_15m: pd.DataFrame,
    displacement_atr_mult: float = 0.7,
    min_break_close_buffer_atr: float = 0.05,
) -> pd.DataFrame:
    """
    Returns df_15m enriched with:
      - protected_swing_high, protected_swing_low
      - bos_flag (1 bull bos, -1 bear bos, 0 none)
      - choch_flag (1 bull choch, -1 bear choch, 0 none)
      - external_bias (bull/bear/range/none)

    IMPORTANT: Preserves original DatetimeIndex for merge_asof alignment.
    """
    if not isinstance(df_15m.index, pd.DatetimeIndex):
        raise TypeError("build_external_structure requires DatetimeIndex input.")

    # Preserve index (do NOT reset/drop it)
    df = df_15m.copy()
    df = add_atr(df)

    df["protected_swing_high"] = pd.NA
    df["protected_swing_low"] = pd.NA
    df["bos_flag"] = 0
    df["choch_flag"] = 0
    df["external_bias"] = "none"

    pivot_highs: List[int] = []
    pivot_lows: List[int] = []

    last_protected_high = None
    last_protected_low = None
    current_bias = "none"

    # iterate by positional index, write back by label index
    for i in range(len(df)):
        if _pivot_high(df, i):
            pivot_highs.append(i)
        if _pivot_low(df, i):
            pivot_lows.append(i)

        idx = df.index[i]
        close_i = float(df.iloc[i]["close"])
        atr_i = df.iloc[i]["atr"]

        last_pivot_high_price = float(df.iloc[pivot_highs[-1]]["high"]) if pivot_highs else None
        last_pivot_low_price = float(df.iloc[pivot_lows[-1]]["low"]) if pivot_lows else None

        bos_flag = 0
        choch_flag = 0

        # Bull break of opposing high
        if last_pivot_high_price is not None and pd.notna(atr_i):
            buffer_val = float(atr_i) * min_break_close_buffer_atr
            move_size = close_i - last_pivot_high_price
            if close_i > last_pivot_high_price + buffer_val and displacement_pass(
                move_size=move_size,
                atr_value=float(atr_i),
                threshold_mult=displacement_atr_mult,
            ):
                if last_pivot_low_price is not None:
                    last_protected_low = last_pivot_low_price

                if current_bias in ("bull", "none", "range"):
                    bos_flag = 1
                elif current_bias == "bear":
                    choch_flag = 1

                current_bias = "bull"

        # Bear break of opposing low
        if last_pivot_low_price is not None and pd.notna(atr_i):
            buffer_val = float(atr_i) * min_break_close_buffer_atr
            move_size = last_pivot_low_price - close_i
            if close_i < last_pivot_low_price - buffer_val and displacement_pass(
                move_size=move_size,
                atr_value=float(atr_i),
                threshold_mult=displacement_atr_mult,
            ):
                if last_pivot_high_price is not None:
                    last_protected_high = last_pivot_high_price

                if current_bias in ("bear", "none", "range"):
                    bos_flag = -1
                elif current_bias == "bull":
                    choch_flag = -1

                current_bias = "bear"

        if last_protected_high is None and last_protected_low is None:
            bias_out = "none"
        else:
            bias_out = current_bias

        df.at[idx, "protected_swing_high"] = last_protected_high
        df.at[idx, "protected_swing_low"] = last_protected_low
        df.at[idx, "bos_flag"] = bos_flag
        df.at[idx, "choch_flag"] = choch_flag
        df.at[idx, "external_bias"] = bias_out

    # keep index name stable for downstream reset_index -> timestamp
    if df.index.name is None:
        df.index.name = "timestamp"

    return df
