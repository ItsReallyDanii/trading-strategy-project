from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import pandas as pd

from src.rules_engine.bias_engine import external_bias_decision
from src.rules_engine.entry_models import (
    model_a_sweep_reclaim,
    model_b_failed_choch,
    model_c_continuation_pullback,
)
from src.rules_engine.parameters import StrategyConfig


@dataclass
class Signal:
    timestamp: pd.Timestamp
    symbol: str
    signal: bool
    side: Optional[str]
    model: Optional[str]
    reason_codes: List[str]
    entry_price: Optional[float]


def generate_signal_for_bar(
    *,
    symbol: str,
    ts: pd.Timestamp,
    row_3m: pd.Series,
    row_15m: pd.Series,
    cfg: StrategyConfig,
) -> Signal:
    reasons: List[str] = []

    # 1) External bias gate
    bias_dec = external_bias_decision(row_15m)
    reasons.append(bias_dec.reason)
    if not bias_dec.tradable:
        return Signal(ts, symbol, False, None, None, reasons, None)

    # buffer using ATR from 15m
    atr = row_15m.get("atr", None)
    if atr is None or pd.isna(atr):
        return Signal(ts, symbol, False, None, None, reasons + ["ATR_NA"], None)
    buffer_val = float(atr) * cfg.reclaim_buffer_atr

    # Inputs expected from feature pipeline (placeholder friendly)
    swept_level = row_3m.get("swept_level", None)
    reclaim_bar = {
        "open": row_3m.get("open"),
        "high": row_3m.get("high"),
        "low": row_3m.get("low"),
        "close": row_3m.get("close"),
    }
    failed_choch_confirmed = bool(row_3m.get("failed_choch_confirmed", False))
    pullback_respected = bool(row_3m.get("pullback_respected", False))
    internal_sweep_reclaim = bool(row_3m.get("internal_sweep_reclaim", False))

    # 2) Model priority A -> B -> C (can change later)
    a = model_a_sweep_reclaim(
        bias=bias_dec.bias,
        swept_level=swept_level,
        reclaim_bar=reclaim_bar,
        buffer_val=buffer_val,
    )
    if a.passed:
        return Signal(ts, symbol, True, a.side, a.model, reasons + a.reason_codes, float(row_3m["close"]))

    b = model_b_failed_choch(
        bias=bias_dec.bias,
        failed_choch_confirmed=failed_choch_confirmed,
    )
    if b.passed:
        return Signal(ts, symbol, True, b.side, b.model, reasons + b.reason_codes, float(row_3m["close"]))

    c = model_c_continuation_pullback(
        bias=bias_dec.bias,
        pullback_respected=pullback_respected,
        internal_sweep_reclaim=internal_sweep_reclaim,
    )
    if c.passed:
        return Signal(ts, symbol, True, c.side, c.model, reasons + c.reason_codes, float(row_3m["close"]))

    return Signal(ts, symbol, False, None, None, reasons + a.reason_codes + b.reason_codes + c.reason_codes, None)
