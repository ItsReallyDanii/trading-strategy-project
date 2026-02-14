from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


CANONICAL_PRICE_COLS = ["open", "high", "low", "close", "volume"]
CANONICAL_ALL_COLS = ["timestamp"] + CANONICAL_PRICE_COLS


def _first_existing(cols: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    cols_set = {c for c in cols}
    for c in candidates:
        if c in cols_set:
            return c
    return None


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    # Work on lowercase names for robust mapping
    original_cols = list(df.columns)
    lower_map = {c: c.strip().lower() for c in original_cols}
    df = df.rename(columns=lower_map)

    # Map common timestamp variants
    ts_col = _first_existing(
        df.columns,
        ["timestamp", "datetime", "date", "time", "index"],
    )
    if ts_col is None:
        raise ValueError("No timestamp-like column found.")

    # Map common OHLCV variants
    col_map = {}

    open_col = _first_existing(df.columns, ["open", "o"])
    high_col = _first_existing(df.columns, ["high", "h"])
    low_col = _first_existing(df.columns, ["low", "l"])
    close_col = _first_existing(df.columns, ["close", "c", "adj close", "adj_close"])
    vol_col = _first_existing(df.columns, ["volume", "vol", "v"])

    missing = []
    if open_col is None:
        missing.append("open")
    if high_col is None:
        missing.append("high")
    if low_col is None:
        missing.append("low")
    if close_col is None:
        missing.append("close")
    if vol_col is None:
        # allow missing volume -> fill zeros
        pass

    if missing:
        raise ValueError(f"Missing required OHLC columns: {missing}")

    col_map[ts_col] = "timestamp"
    col_map[open_col] = "open"
    col_map[high_col] = "high"
    col_map[low_col] = "low"
    col_map[close_col] = "close"
    if vol_col is not None:
        col_map[vol_col] = "volume"

    out = df.rename(columns=col_map)

    if "volume" not in out.columns:
        out["volume"] = 0

    out = out[["timestamp", "open", "high", "low", "close", "volume"]].copy()

    # Parse timestamp
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=False)
    out = out.dropna(subset=["timestamp"])

    # Numeric cast
    for c in CANONICAL_PRICE_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])

    # Enforce OHLC sanity
    out = out[(out["high"] >= out["low"])]
    out = out[(out["open"] <= out["high"]) & (out["open"] >= out["low"])]
    out = out[(out["close"] <= out["high"]) & (out["close"] >= out["low"])]

    # Sort + dedupe
    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

    return out


def repair_symbol(symbol: str, history_dir: Path, raw_dir: Path) -> None:
    src = history_dir / f"{symbol}_3m_history.csv"
    dst = raw_dir / f"{symbol}_3m.csv"

    if not src.exists():
        raise FileNotFoundError(f"Missing history file: {src}")

    df = pd.read_csv(src)
    fixed = normalize_ohlcv(df)

    raw_dir.mkdir(parents=True, exist_ok=True)
    fixed.to_csv(dst, index=False)

    print(
        f"{symbol}: repaired rows={len(fixed)} -> {dst} "
        f"(first={fixed['timestamp'].iloc[0]}, last={fixed['timestamp'].iloc[-1]})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair/normalize raw 3m OHLCV files from history CSVs.")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols, e.g. QQQ,SPY,AAPL,IWM")
    parser.add_argument("--history-dir", default="data/history")
    parser.add_argument("--raw-dir", default="data/raw")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    history_dir = Path(args.history_dir)
    raw_dir = Path(args.raw_dir)

    for sym in symbols:
        repair_symbol(sym, history_dir, raw_dir)


if __name__ == "__main__":
    main()
