"""
Optional downloader for Alpaca historical bars.
Requires:
  export ALPACA_API_KEY=...
  export ALPACA_API_SECRET=...
"""

from pathlib import Path
import os
import requests
import pandas as pd


def fetch_3m_bars(symbol: str, start: str, end: str, feed: str = "sip") -> pd.DataFrame:
    url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {
        "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
        "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET"],
    }
    params = {
        "symbols": symbol,
        "timeframe": "3Min",
        "start": start,   # ISO8601, e.g. 2025-01-01T00:00:00Z
        "end": end,       # ISO8601
        "limit": 10000,
        "adjustment": "all",
        "feed": feed,
        "sort": "asc",
    }

    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    rows = data.get("bars", {}).get(symbol, [])
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def main():
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    symbol = "SPY"
    start = "2025-01-01T00:00:00Z"
    end = "2025-03-01T00:00:00Z"

    df = fetch_3m_bars(symbol=symbol, start=start, end=end)
    out_path = out_dir / f"{symbol}_3m.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
