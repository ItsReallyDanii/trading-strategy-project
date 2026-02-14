from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    # Timeframes
    external_tf: str = "15min"
    execution_tf: str = "3min"

    # Session
    rth_only: bool = True

    # Universe
    include_indices: bool = True
    include_large_caps: bool = True
    include_etfs: bool = True

    # Structure / displacement
    displacement_atr_mult: float = 0.7
    min_break_close_buffer_atr: float = 0.05

    # Retest / reclaim
    reclaim_buffer_atr: float = 0.03
    max_retest_bars_execution_tf: int = 8  # 8 x 3m = 24m

    # Liquidity / equal highs-lows tolerance
    equal_level_tolerance_atr: float = 0.08

    # Risk
    stop_buffer_atr: float = 0.05
    rr_target: float = 2.0  # structure target logic can replace later

    # Reporting
    risk_per_trade_pct: float = 0.005  # 0.5%
