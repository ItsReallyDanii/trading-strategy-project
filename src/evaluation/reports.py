from pathlib import Path
import pandas as pd


def summarize_trades(trades_csv: str) -> pd.DataFrame:
    df = pd.read_csv(trades_csv)
    if df.empty:
        return pd.DataFrame([{"trades": 0, "win_rate": 0.0, "expectancy": 0.0}])

    out = {
        "trades": len(df),
        "win_rate": float((df["pnl_abs"] > 0).mean()),
        "expectancy_abs": float(df["pnl_abs"].mean()),
        "avg_win_abs": float(df.loc[df["pnl_abs"] > 0, "pnl_abs"].mean()) if (df["pnl_abs"] > 0).any() else 0.0,
        "avg_loss_abs": float(df.loc[df["pnl_abs"] <= 0, "pnl_abs"].mean()) if (df["pnl_abs"] <= 0).any() else 0.0,
    }

    by_model = df.groupby("model")["pnl_abs"].agg(["count", "mean"])
    print("By model:\n", by_model)

    return pd.DataFrame([out])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", required=True)
    parser.add_argument("--out", default="outputs/reports/summary.csv")
    args = parser.parse_args()

    summary = summarize_trades(args.trades)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False)
    print(summary)

