from __future__ import annotations
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf


def _normalize_yf_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])

    # yfinance can return MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.reset_index()
    cols = {c: c.lower() for c in df.columns}
    df = df.rename(columns=cols)

    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    elif "date" in df.columns:
        df = df.rename(columns={"date": "timestamp"})

    keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].copy()

    if "timestamp" not in df.columns:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()
    df["symbol"] = symbol
    return df


def fetch_1m(symbol: str, lookback_minutes: int = 180) -> pd.DataFrame:
    """
    Robust 1m fetch:
    - use period='7d' (stable for Yahoo intraday)
    - then trim locally to lookback window
    """
    raw = yf.download(
        tickers=symbol,
        interval="1m",
        period="7d",
        auto_adjust=False,
        progress=False,
        prepost=False,
        threads=False,
    )
    df = _normalize_yf_df(raw, symbol=symbol)
    if df.empty:
        return df

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    df = df[df["timestamp"] >= cutoff].copy()
    return df


def append_dedupe(history_csv: Path, new_df: pd.DataFrame) -> pd.DataFrame:
    history_csv.parent.mkdir(parents=True, exist_ok=True)

    if history_csv.exists():
        old = pd.read_csv(history_csv)
        if not old.empty:
            old["timestamp"] = pd.to_datetime(old["timestamp"], utc=True, errors="coerce")
            old = old.dropna(subset=["timestamp"])
        else:
            old = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])
    else:
        old = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol"])

    # IMPORTANT: if no new data (weekend/closed), keep old history (do not zero out)
    if new_df is None or new_df.empty:
        df = old.copy()
    else:
        df = pd.concat([old, new_df], ignore_index=True)

    if df.empty:
        return df

    df = df.drop_duplicates(subset=["symbol", "timestamp"], keep="last")
    df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    df.to_csv(history_csv, index=False)
    return df


def resample_3m(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m is None or df_1m.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "open", "high", "low", "close", "volume"])

    x = df_1m.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True, errors="coerce")
    x = x.dropna(subset=["timestamp"]).sort_values("timestamp")
    x = x.set_index("timestamp")

    out = (
        x.groupby("symbol")
         .resample("3min")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
         .dropna(subset=["open", "high", "low", "close"])
         .reset_index()
    )
    return out


def gap_check_1m(df_1m: pd.DataFrame) -> tuple[int, int, float]:
    if df_1m is None or df_1m.empty:
        return 0, 0, 0.0

    ts = pd.DatetimeIndex(pd.to_datetime(df_1m["timestamp"], utc=True, errors="coerce").dropna()).sort_values().unique()
    if len(ts) == 0:
        return 0, 0, 0.0

    start, end = ts.min(), ts.max()
    expected = pd.date_range(start=start.floor("min"), end=end.floor("min"), freq="1min", tz="UTC")
    got = pd.DatetimeIndex(ts)
    missing = expected.difference(got)

    total = len(expected)
    miss = len(missing)
    cov = 0.0 if total == 0 else (total - miss) / total
    return total, miss, cov


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default="QQQ,SPY,AAPL,IWM")
    p.add_argument("--lookback-minutes", type=int, default=180)
    args = p.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    health_rows = []

    for sym in symbols:
        new_1m = fetch_1m(sym, lookback_minutes=args.lookback_minutes)

        hist_path = Path(f"data/history/{sym}_1m_history.csv")
        all_1m = append_dedupe(hist_path, new_1m)

        out3 = resample_3m(all_1m)
        raw3_path = Path(f"data/raw/{sym}_3m.csv")
        raw3_path.parent.mkdir(parents=True, exist_ok=True)
        out3.to_csv(raw3_path, index=False)

        expected, missing, coverage = gap_check_1m(all_1m)
        last_ts = None if all_1m.empty else str(pd.to_datetime(all_1m["timestamp"], utc=True).max())

        health_rows.append(
            {
                "symbol": sym,
                "rows_1m": int(len(all_1m)),
                "rows_3m": int(len(out3)),
                "expected_minutes": int(expected),
                "missing_minutes": int(missing),
                "coverage": float(coverage),
                "last_ts_utc": last_ts,
                "new_rows_fetched": int(0 if new_1m is None else len(new_1m)),
            }
        )

    health = pd.DataFrame(health_rows)
    Path("outputs/health").mkdir(parents=True, exist_ok=True)
    health.to_csv("outputs/health/ingest_health.csv", index=False)
    print(health.to_string(index=False))


if __name__ == "__main__":
    main()
