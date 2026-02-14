from pathlib import Path
import numpy as np
import pandas as pd


def make_ohlcv_3m(
    symbol: str = "SPY",
    start: str = "2025-01-02 09:30:00",
    periods: int = 3000,
    tz: str = "America/New_York",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates synthetic 3-minute OHLCV data during RTH-like hours.
    Timestamps emitted in UTC ISO format with Z.
    """
    rng = np.random.default_rng(seed)

    # 3-min bars across calendar time; we'll filter to trading hours-ish pattern
    idx_local = pd.date_range(start=start, periods=periods, freq="3min", tz=tz)

    # Keep approximate weekdays and trading hours 9:30-16:00
    is_weekday = idx_local.weekday < 5
    hm = idx_local.hour * 60 + idx_local.minute
    is_rth = (hm >= 9 * 60 + 30) & (hm <= 16 * 60)
    idx_local = idx_local[is_weekday & is_rth]

    n = len(idx_local)
    if n < 100:
        raise ValueError("Not enough rows generated. Increase periods.")

    # Random walk + gentle regimes
    base = 500.0
    drift = np.sin(np.linspace(0, 10, n)) * 0.02
    noise = rng.normal(0, 0.25, n)
    ret = drift + noise
    close = base + np.cumsum(ret)

    # Build OHLC around close
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.01, 0.20, n)
    low = np.minimum(open_, close) - rng.uniform(0.01, 0.20, n)
    volume = rng.integers(100_000, 1_500_000, n)

    df = pd.DataFrame(
        {
            "timestamp": idx_local.tz_convert("UTC"),
            "open": open_.round(4),
            "high": high.round(4),
            "low": low.round(4),
            "close": close.round(4),
            "volume": volume.astype(int),
        }
    )
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df


def main():
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    symbols = ["SPY", "QQQ", "AAPL"]
    for i, s in enumerate(symbols):
        df = make_ohlcv_3m(symbol=s, seed=42 + i)
        out_path = out_dir / f"{s}_3m.csv"
        df.to_csv(out_path, index=False)
        print(f"Wrote {out_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
