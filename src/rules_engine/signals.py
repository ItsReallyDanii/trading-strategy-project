
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from .conditions import (
    Params,
    is_real_break_long, is_real_break_short,
    retest_touch_long, retest_touch_short,
    retest_hold_long, retest_hold_short,
    wick_rejection_long, wick_rejection_short,
    thresholdA_pass_long, thresholdA_pass_short,
    thresholdB_pass_long, thresholdB_pass_short
)

@dataclass
class SignalResult:
    entry_signal: bool
    side: Optional[str]               # "long", "short", or None
    reason_codes: List[str]
    key_level: float
    break_index: Optional[int]
    retest_index: Optional[int]

def evaluate_signal(
    bars: List[Dict[str, float]],
    key_level: float,
    p: Params,
    allow_long: bool = True,
    allow_short: bool = True
) -> SignalResult:
    """
    bars: sequential bars; each bar has keys: open, high, low, close
    assumes last bar is current context window end
    """
    reasons: List[str] = []
    n = len(bars)
    if n < 3:
        return SignalResult(False, None, ["ERR_NOT_ENOUGH_BARS"], key_level, None, None)

    # naive break detection on penultimate bar
    b = n - 2
    bar_b = bars[b]

    long_break = allow_long and is_real_break_long(bar_b["close"], bar_b["high"], key_level, p)
    short_break = allow_short and is_real_break_short(bar_b["close"], bar_b["low"], key_level, p)

    if not (long_break or short_break):
        return SignalResult(False, None, ["NO_REAL_BREAK"], key_level, None, None)

    side = "long" if long_break else "short"
    reasons.append(f"REAL_BREAK_{side.upper()}")

    # retest search window
    retest_idx = None
    end_idx = min(n - 1, b + p.max_retest_bars)
    for i in range(b + 1, end_idx + 1):
        bi = bars[i]
        if side == "long":
            if retest_touch_long(bi["low"], key_level, p):
                retest_idx = i
                break
        else:
            if retest_touch_short(bi["high"], key_level, p):
                retest_idx = i
                break

    if retest_idx is None:
        return SignalResult(False, side, reasons + ["NO_RETEST_IN_WINDOW"], key_level, b, None)

    r = bars[retest_idx]
    if side == "long":
        hold = retest_hold_long(r["close"], key_level, p)
        wick = wick_rejection_long(r["open"], r["high"], r["low"], r["close"], p)
    else:
        hold = retest_hold_short(r["close"], key_level, p)
        wick = wick_rejection_short(r["open"], r["high"], r["low"], r["close"], p)

    if not hold:
        return SignalResult(False, side, reasons + ["RETEST_FAIL_CLOSE"], key_level, b, retest_idx)
    if not wick:
        return SignalResult(False, side, reasons + ["REJECTION_WICK_FAIL"], key_level, b, retest_idx)

    reasons += ["RETEST_HOLD_PASS", "WICK_REJECTION_PASS"]

    # threshold checks using next up-to-2 bars after retest (or available)
    post = bars[retest_idx:min(retest_idx + 3, n)]
    max_high = max(x["high"] for x in post)
    min_low = min(x["low"] for x in post)
    cbar = post[-1]

    if side == "long":
        a_pass = thresholdA_pass_long(max_high, key_level, p)
        b_pass = thresholdB_pass_long(cbar["open"], cbar["high"], cbar["low"], cbar["close"], p)
    else:
        a_pass = thresholdA_pass_short(min_low, key_level, p)
        b_pass = thresholdB_pass_short(cbar["open"], cbar["high"], cbar["low"], cbar["close"], p)

    if not a_pass:
        return SignalResult(False, side, reasons + ["THRESHOLD_A_FAIL"], key_level, b, retest_idx)
    if not b_pass:
        return SignalResult(False, side, reasons + ["THRESHOLD_B_FAIL"], key_level, b, retest_idx)

    reasons += ["THRESHOLD_A_PASS", "THRESHOLD_B_PASS", "ENTRY_SIGNAL_TRUE"]
    return SignalResult(True, side, reasons, key_level, b, retest_idx)
