from pathlib import Path
import pandas as pd


def summarize_trades(trades_csv: str, rejections_csv: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(trades_csv)
    if df.empty:
        return pd.DataFrame([{"trades": 0, "win_rate": 0.0, "expectancy_abs": 0.0, "max_drawdown_proxy": 0.0}])

    df["win"] = df["pnl_abs"] > 0
    equity = df["pnl_abs"].cumsum()
    dd = equity - equity.cummax()
    max_dd = dd.min()

    out = {
        "trades": len(df),
        "win_rate": float(df["win"].mean()),
        "expectancy_abs": float(df["pnl_abs"].mean()),
        "avg_win_abs": float(df.loc[df["win"], "pnl_abs"].mean()) if df["win"].any() else 0.0,
        "avg_loss_abs": float(df.loc[~df["win"], "pnl_abs"].mean()) if (~df["win"]).any() else 0.0,
        "avg_r_multiple": float(df["r_multiple"].mean()) if "r_multiple" in df.columns else 0.0,
        "max_drawdown_proxy": float(max_dd),
    }

    print("\nBy model:")
    print(df.groupby("model").agg(
        trades=("pnl_abs", "count"),
        win_rate=("win", "mean"),
        expectancy=("pnl_abs", "mean"),
        avg_r=("r_multiple", "mean"),
    ))

    if "entry_hour" in df.columns:
        print("\nBy hour:")
        print(df.groupby("entry_hour")["pnl_abs"].agg(["count", "mean"]))

    if rejections_csv and Path(rejections_csv).exists():
        rj = pd.read_csv(rejections_csv)
        if not rj.empty and "reason_codes" in rj.columns:
            x = rj.assign(reason_codes=rj["reason_codes"].fillna("").str.split("|")).explode("reason_codes")
            x = x[x["reason_codes"] != ""]
            counts = x["reason_codes"].value_counts()
            shares = (counts / counts.sum()).rename("share")
            funnel = pd.concat([counts.rename("count"), shares], axis=1)
            print("\nRejection funnel:")
            print(funnel.head(12))

    return pd.DataFrame([out])


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--trades", required=True)
    p.add_argument("--rejections", default=None)
    p.add_argument("--out", default="outputs/reports/summary.csv")
    args = p.parse_args()

    summary = summarize_trades(args.trades, args.rejections)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False)
    print("\nSummary:")
    print(summary)
