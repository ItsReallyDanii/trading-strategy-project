from pathlib import Path
import pandas as pd


def append_csv(symbol: str):
    raw_path = Path(f"data/raw/{symbol}_3m.csv")
    hist_path = Path(f"data/history/{symbol}_3m_history.csv")
    hist_path.parent.mkdir(parents=True, exist_ok=True)

    if not raw_path.exists():
        print(f"skip {symbol}: no fresh raw file")
        return

    new_df = pd.read_csv(raw_path)
    if new_df.empty:
        print(f"skip {symbol}: fresh file empty")
        return

    if hist_path.exists() and hist_path.stat().st_size > 0:
        old_df = pd.read_csv(hist_path)
        all_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        all_df = new_df.copy()

    all_df["timestamp"] = pd.to_datetime(all_df["timestamp"], utc=True, errors="coerce")
    all_df = (
        all_df.dropna(subset=["timestamp"])
              .drop_duplicates(subset=["timestamp"])
              .sort_values("timestamp")
    )

    all_df.to_csv(hist_path, index=False)
    print(f"{symbol}: history rows={len(all_df)} saved -> {hist_path}")


def main():
    for s in ["QQQ", "SPY", "AAPL", "IWM"]:
        append_csv(s)


if __name__ == "__main__":
    main()
