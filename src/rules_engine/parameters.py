from .conditions import Params

DEFAULT_PARAMS = Params(
    confirm_buffer=0.05,              # placeholder units: dollars unless normalized; finalize with key-level spec
    retest_tolerance=0.03,            # same note as above
    min_rejection_wick_ratio=0.25,    # 25% wick rejection
    thresholdA_min_excursion=0.20,    # placeholder; can map to ATR multiple later
    thresholdB_close_strength=0.55,   # close in top 55% of range for longs
    max_retest_bars=4,                # 4 x 15m = 60 min
    stop_buffer=0.01                  # placeholder tick buffer
)
