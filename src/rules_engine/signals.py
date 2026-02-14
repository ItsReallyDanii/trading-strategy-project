from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass
class SignalDecision:
    signal: bool
    side: str | None
    model: str | None
    reason_codes: List[str]


def _hour_ok(ts, cfg) -> bool:
    h = pd.Timestamp(ts).hour
    return h in set(cfg.allowed_entry_hours)


def _atr_regime_ok(row_15m, cfg) -> bool:
    # safe gate: if disabled, always pass
    if not getattr(cfg, "use_atr_regime_filter", False):
        return True

    p = row_15m.get("atr_pct_lookback", None)
    if p is None or pd.isna(p):
        return False

    lo = getattr(cfg, "atr_pct_min", 0.20)
    hi = getattr(cfg, "atr_pct_max", 0.80)
    return lo <= float(p) <= hi


def generate_signal_for_bar(symbol, ts, row_3m, row_15m, cfg) -> SignalDecision:
    reasons = []

    if getattr(cfg, "allowed_symbols", None):
        if symbol not in set(cfg.allowed_symbols):
            reasons.append("SYMBOL_BLOCKED")
            return SignalDecision(False, None, None, reasons)

    if not _hour_ok(ts, cfg):
        reasons.append("HOUR_BLOCKED")
        return SignalDecision(False, None, None, reasons)

    bias = str(row_15m.get("external_bias", "none"))
    if bias not in ("bull", "bear"):
        reasons.append("BIAS_NONE")
        return SignalDecision(False, None, None, reasons)

    if not _atr_regime_ok(row_15m, cfg):
        reasons.append("ATR_REGIME_BLOCKED")
        return SignalDecision(False, None, None, reasons)

    side = "long" if bias == "bull" else "short"
    if cfg.long_only and side != "long":
        reasons.append("SHORT_DISABLED")
        return SignalDecision(False, None, None, reasons)

    if cfg.enable_model_a:
        swept_level = row_3m.get("swept_level", None)
        if pd.notna(swept_level):
            close = float(row_3m["close"])
            reclaim_ok = (close > swept_level) if side == "long" else (close < swept_level)
            if reclaim_ok:
                return SignalDecision(True, side, "A", ["MODEL_A_SWEEP_RECLAIM"])

    if cfg.enable_model_b:
        if bool(row_3m.get("failed_choch_confirmed", False)):
            return SignalDecision(True, side, "B", ["MODEL_B_FAILED_CHOCH"])

    if cfg.enable_model_c:
        pullback_ok = bool(row_3m.get("pullback_respected", False))
        reclaim_ok = bool(row_3m.get("internal_sweep_reclaim", False))
        if pullback_ok and reclaim_ok:
            return SignalDecision(True, side, "C", ["MODEL_C_CONT_PULLBACK"])

    reasons.append("NO_MODEL_MATCH")
    return SignalDecision(False, None, None, reasons)
