from dataclasses import dataclass
import math

TINY = 1e-12

@dataclass
class Params:
    confirm_buffer: float
    retest_tolerance: float
    min_rejection_wick_ratio: float
    thresholdA_min_excursion: float
    thresholdB_close_strength: float

def close_location_value(o: float, h: float, l: float, c: float) -> float:
    rng = max(h - l, TINY)
    return (c - l) / rng

def is_real_break_long(c: float, h: float, key_level: float, p: Params) -> bool:
    return (c > key_level + p.confirm_buffer) and (h > key_level + p.confirm_buffer)

def is_real_break_short(c: float, l: float, key_level: float, p: Params) -> bool:
    return (c < key_level - p.confirm_buffer) and (l < key_level - p.confirm_buffer)

def retest_hold_long(c_retest: float, key_level: float, p: Params) -> bool:
    return c_retest >= key_level - p.retest_tolerance

def retest_hold_short(c_retest: float, key_level: float, p: Params) -> bool:
    return c_retest <= key_level + p.retest_tolerance

def wick_rejection_long(o: float, h: float, l: float, c: float, p: Params) -> bool:
    rng = max(h - l, TINY)
    lower_wick = min(o, c) - l
    return (lower_wick / rng) >= p.min_rejection_wick_ratio

def wick_rejection_short(o: float, h: float, l: float, c: float, p: Params) -> bool:
    rng = max(h - l, TINY)
    upper_wick = h - max(o, c)
    return (upper_wick / rng) >= p.min_rejection_wick_ratio

def thresholdA_pass_long(max_high_after_retest: float, key_level: float, p: Params) -> bool:
    return (max_high_after_retest - key_level) >= p.thresholdA_min_excursion

def thresholdA_pass_short(min_low_after_retest: float, key_level: float, p: Params) -> bool:
    return (key_level - min_low_after_retest) >= p.thresholdA_min_excursion

def thresholdB_pass_long(o: float, h: float, l: float, c: float, p: Params) -> bool:
    return close_location_value(o, h, l, c) >= p.thresholdB_close_strength

def thresholdB_pass_short(o: float, h: float, l: float, c: float, p: Params) -> bool:
    return close_location_value(o, h, l, c) <= (1.0 - p.thresholdB_close_strength)
