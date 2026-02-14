from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import yfinance as yf


def _utc_now():
    return datetime.now(timezone.utc)


def _clamp_to_last_30d(start_dt: datetime, end_dt: datetime) -> tuple[datetime, datetime]:
    # Yahoo 1m constraint: requested range must be inside last ~30 days
    now = _utc_now()
    min_start = now - timedelta(days=29, hours=23)  # conservative buffer
    end_clamped = min(end_dt, now)
    start_clamped = max(start_dt, min_start)
    if start_clamped >= end_clamped:
        # fallback to last 7 days if user passed stale dates
        end_clamped = now
        start_clamped = now - timedelta(days=7)
    return start_clamped, end_clamped


def _download_1m_chunked(symbol: str, start_dt: datetime, end_dt: datetime, chunk_days: int = 7) -> pd.DataFrame:
    frames = []
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + timedelta(days=chunk_days), end_dt)
        df = yf.download(
            tickers=symbol,
            start=cur.strftime("%Y-%m-%d"),
            end=nxt.strftime("%Y-%m-%d"),
            interval="1m",
            auto_adjust=False,
            progress=False,
            prepost=False,
            threads=False,
        )
        if not df.empty:
            # normalize columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0].lower() for c in df.columns]
            else:
                df.columns = [str(c).lower() for c in df.columns]
            df = df.rename_axis("timestamp").reset_index()
            frames.append(df[["timestamp", "open", "high", "low", "close", "volume"]])
        cur = nxt

    if not frames:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return out


def _resample_3m(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m.empty:
        return df_1m.copy()

    out = df_1m.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out = out.set_index("timestamp").sort_index()

    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    bars = out.resample("3min", label="right", closed="right").agg(agg).dropna().reset_index()
    return bars


def fetch_symbol_3m(symbol: str, start: str | None, end: str | None) -> pd.DataFrame:
    now = _utc_now()
    if end:
        end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    else:
        end_dt = now

    if start:
        start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    else:
        start_dt = end_dt - timedelta(days=14)

    start_dt, end_dt = _clamp_to_last_30d(start_dt, end_dt)
    df_1m = _download_1m_chunked(symbol, start_dt, end_dt, chunk_days=7)
    return _resample_3m(df_1m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "AAPL", "IWM"])
    ap.add_argument("--start", type=str, default=None, help="YYYY-MM-DD (clamped to last 30d for 1m)")
    ap.add_argument("--end", type=str, default=None, help="YYYY-MM-DD (default now)")
    ap.add_argument("--outdir", type=str, default="data/raw")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for s in args.symbols:
        df = fetch_symbol_3m(s, args.start, args.end)
        out = outdir / f"{s}_3m.csv"
        df.to_csv(out, index=False)
        print(f"Wrote {out} ({len(df)} rows)")

    print("Done. Source: yfinance 1m chunked -> resampled to 3m.")


if __name__ == "__main__":
    main()
