from typing import Dict


def initial_stop(side: str, entry_bar: Dict[str, float], reference_bar: Dict[str, float], stop_buffer: float) -> float:
    if side == "long":
        return min(entry_bar["low"], reference_bar["low"]) - stop_buffer
    return max(entry_bar["high"], reference_bar["high"]) + stop_buffer


def target_from_rr(side: str, entry_price: float, stop_price: float, rr_target: float) -> float:
    risk = abs(entry_price - stop_price)
    if side == "long":
        return entry_price + rr_target * risk
    return entry_price - rr_target * risk
