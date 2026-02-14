from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf


SYMBOLS_DEFAULT = ["QQQ", "SPY", "AAPL", "IWM"]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_csv_indexed(path: Path) -> pd.DataFrame:
    """
    Read OHLCV CSV with timestamp index in first column.
    Returns empty DataFrame with OHLCV columns if file missing/empty/invalid.
    """
    cols = ["Open", "High", "Low", "Close", "Volume"]
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=cols)

    try:
        df = pd.read_csv(path, index_col=0)
        if df.empty:
            return pd.DataFrame(columns=cols)

        df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
        df = df.loc[~df.index.isna()].copy()
        if df.empty:
            return pd.DataFrame(columns=cols)

        # Normalize index to UTC tz-naive for stable CSV roundtrips
        df.index = df.index.tz_convert("UTC").tz_localize(None)

        # Keep standard columns if present; add missing as NaN
        for c in cols:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[cols].sort_index()
        return df
    except Exception:
        return pd.DataFrame(columns=cols)


def _write_csv_indexed(df: pd.DataFrame, path: Path) -> None:
    _ensure_parent(path)
    out = df.copy()
    out.index.name = "timestamp"
    out.to_csv(path)


def _flatten_yf_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def fetch_1m_safe(
    symbol: str,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    Robust 1m fetch sequence:
      1) explicit [start, end] window (if provided)
      2) fallback to period='7d'
    Returns tz-naive UTC index and OHLCV columns.
    """
    cols = ["Open", "High", "Low", "Close", "Volume"]
    df = pd.DataFrame()

    # Attempt explicit window first
    if start is not None and end is not None:
        try:
            df = yf.download(
                symbol,
                start=start,
                end=end,
                interval="1m",
                auto_adjust=False,
                progress=False,
                prepost=False,
                threads=False,
                group_by="column",
            )
        except Exception:
            df = pd.DataFrame()

    # Fallback to rolling period
    if df is None or df.empty:
        try:
            df = yf.download(
                symbol,
                period="7d",
                interval="1m",
                auto_adjust=False,
                progress=False,
                prepost=False,
                threads=False,
                group_by="column",
            )
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame(columns=cols)

    df = _flatten_yf_columns(df)

    # Normalize index
    idx = pd.to_datetime(df.index, utc=True, errors="coerce")
    df = df.loc[~idx.isna()].copy()
    idx = idx[~idx.isna()]
    if df.empty:
        return pd.DataFrame(columns=cols)

    df.index = idx.tz_convert("UTC").tz_localize(None)

    # Keep only OHLCV that exist
    keep = [c for c in cols if c in df.columns]
    if not keep:
        return pd.DataFrame(columns=cols)

    df = df[keep].sort_index()

    # Ensure all target cols exist
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


def _resample_to_3m(hist_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Resample merged 1m history -> 3m OHLCV.
    """
    if hist_1m.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    hist_1m = hist_1m[~hist_1m.index.duplicated(keep="last")].sort_index()

    df_3m = (
        hist_1m.resample("3min", label="right", closed="right")
        .agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )
        .dropna(subset=["Open", "High", "Low", "Close"])
    )
    return df_3m


def append_for_symbol(symbol: str, base_dir: Path, lookback_hours: int = 48) -> int:
    """
    Appends fresh 1m data into history, rebuilds 3m history/raw snapshots.
    Returns number of *new* 1m rows added.
    """
    data_dir = base_dir / "data"
    history_dir = data_dir / "history"
    raw_dir = data_dir / "raw"

    h1m_path = history_dir / f"{symbol}_1m_history.csv"
    h3m_path = history_dir / f"{symbol}_3m_history.csv"
    raw3m_path = raw_dir / f"{symbol}_3m.csv"

    hist_1m = _read_csv_indexed(h1m_path)

    # Build explicit fetch window from last timestamp if available
    now_utc = pd.Timestamp.now("UTC").tz_localize(None)
    if not hist_1m.empty:
        last_ts = hist_1m.index.max()
        # small overlap to protect against boundary loss
        start_ts = last_ts - pd.Timedelta(minutes=10)
    else:
        start_ts = now_utc - pd.Timedelta(hours=lookback_hours)
    end_ts = now_utc + pd.Timedelta(minutes=1)

    new_1m = fetch_1m_safe(symbol=symbol, start=start_ts, end=end_ts)

    if new_1m.empty:
        print(f"{symbol}: no new rows fetched; keeping existing files unchanged")
        # IMPORTANT: do not overwrite files with empties
        return 0

    # Merge + dedupe
    merged = pd.concat([hist_1m, new_1m], axis=0)
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()

    before = len(hist_1m)
    after = len(merged)
    new_rows = max(after - before, 0)

    # Save 1m history
    _write_csv_indexed(merged, h1m_path)

    # Rebuild and save 3m from merged history
    hist_3m = _resample_to_3m(merged)
    _write_csv_indexed(hist_3m, h3m_path)
    _write_csv_indexed(hist_3m, raw3m_path)

    print(f"{symbol}: history rows={len(hist_3m)} saved -> {h3m_path}")
    return new_rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append market data and rebuild 3m files.")
    p.add_argument(
        "--symbols",
        type=str,
        default=",".join(SYMBOLS_DEFAULT),
        help="Comma-separated symbols, e.g. QQQ,SPY,AAPL,IWM",
    )
    p.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Project root (contains /data)",
    )
    p.add_argument(
        "--lookback-hours",
        type=int,
        default=48,
        help="Initial lookback window when no 1m history exists.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    for sym in symbols:
        try:
            append_for_symbol(sym, base_dir=base_dir, lookback_hours=args.lookback_hours)
        except Exception as e:
            print(f"{sym}: failed -> {e}")


if __name__ == "__main__":
    main()
