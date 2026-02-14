from dataclasses import dataclass
import pandas as pd


@dataclass
class BiasDecision:
    bias: str            # bull, bear, range, none
    tradable: bool
    reason: str


def external_bias_decision(row_15m: pd.Series) -> BiasDecision:
    b = row_15m.get("external_bias", "none")
    if b == "bull":
        return BiasDecision("bull", True, "BIAS_BULL")
    if b == "bear":
        return BiasDecision("bear", True, "BIAS_BEAR")
    if b == "range":
        return BiasDecision("range", False, "EXTERNAL_RANGE")
    return BiasDecision("none", False, "NO_EXTERNAL_BIAS")
