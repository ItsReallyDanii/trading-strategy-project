from typing import List, Dict

def initial_stop_long(retest_bar: Dict[str, float], prev_bar: Dict[str, float], stop_buffer: float) -> float:
    return min(retest_bar["low"], prev_bar["low"]) - stop_buffer

def initial_stop_short(retest_bar: Dict[str, float], prev_bar: Dict[str, float], stop_buffer: float) -> float:
    return max(retest_bar["high"], prev_bar["high"]) + stop_buffer

def trail_stop_long(current_stop: float, new_pivot_low: float, stop_buffer: float) -> float:
    candidate = new_pivot_low - stop_buffer
    return max(current_stop, candidate)

def trail_stop_short(current_stop: float, new_pivot_high: float, stop_buffer: float) -> float:
    candidate = new_pivot_high + stop_buffer
    return min(current_stop, candidate)

