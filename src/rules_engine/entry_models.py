from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class ModelDecision:
    passed: bool
    model: Optional[str]  # A/B/C
    reason_codes: List[str]
    side: Optional[str]   # long/short


def _is_bullish_reclaim(bar: Dict[str, float], level: float, buffer_val: float) -> bool:
    return bar["close"] > (level + buffer_val)


def _is_bearish_reclaim(bar: Dict[str, float], level: float, buffer_val: float) -> bool:
    return bar["close"] < (level - buffer_val)


def model_a_sweep_reclaim(
    *,
    bias: str,
    swept_level: Optional[float],
    reclaim_bar: Optional[Dict[str, float]],
    buffer_val: float,
) -> ModelDecision:
    reasons = []
    if swept_level is None:
        return ModelDecision(False, None, ["MODEL_A_NO_SWEEP"], None)
    if reclaim_bar is None:
        return ModelDecision(False, None, ["MODEL_A_NO_RECLAIM"], None)

    if bias == "bull":
        ok = _is_bullish_reclaim(reclaim_bar, swept_level, buffer_val)
        return ModelDecision(ok, "A" if ok else None, ["MODEL_A_PASS" if ok else "MODEL_A_FAIL"], "long" if ok else None)
    if bias == "bear":
        ok = _is_bearish_reclaim(reclaim_bar, swept_level, buffer_val)
        return ModelDecision(ok, "A" if ok else None, ["MODEL_A_PASS" if ok else "MODEL_A_FAIL"], "short" if ok else None)

    return ModelDecision(False, None, ["MODEL_A_FAIL"], None)


def model_b_failed_choch(
    *,
    bias: str,
    failed_choch_confirmed: bool,
) -> ModelDecision:
    if not failed_choch_confirmed:
        return ModelDecision(False, None, ["MODEL_B_NO_FAILED_CHOCH"], None)

    if bias == "bull":
        return ModelDecision(True, "B", ["MODEL_B_PASS"], "long")
    if bias == "bear":
        return ModelDecision(True, "B", ["MODEL_B_PASS"], "short")

    return ModelDecision(False, None, ["MODEL_B_FAIL"], None)


def model_c_continuation_pullback(
    *,
    bias: str,
    pullback_respected: bool,
    internal_sweep_reclaim: bool,
) -> ModelDecision:
    if not pullback_respected:
        return ModelDecision(False, None, ["MODEL_C_NO_CONT_PULLBACK"], None)
    if not internal_sweep_reclaim:
        return ModelDecision(False, None, ["MODEL_C_NO_INTERNAL_SWEEP_RECLAIM"], None)

    if bias == "bull":
        return ModelDecision(True, "C", ["MODEL_C_PASS"], "long")
    if bias == "bear":
        return ModelDecision(True, "C", ["MODEL_C_PASS"], "short")

    return ModelDecision(False, None, ["MODEL_C_FAIL"], None)

