from dataclasses import dataclass
from typing import Tuple


@dataclass
class StrategyConfig:
    displacement_atr_mult: float = 1.1
    min_break_close_buffer_atr: float = 0.05

    rr_target: float = 2.5
    stop_buffer_atr: float = 0.05
    reclaim_buffer_atr: float = 0.03

    rth_only: bool = True
    allowed_entry_hours: Tuple[int, ...] = (10,)

    enable_model_a: bool = False
    enable_model_b: bool = False
    enable_model_c: bool = True

    long_only: bool = False

    # DEPLOY LOCK: primary only
    allowed_symbols: Tuple[str, ...] = ("QQQ",)

    # optional filter remains off unless explicitly tested
    use_atr_regime_filter: bool = False
    atr_pct_min: float = 0.2
    atr_pct_max: float = 0.8
