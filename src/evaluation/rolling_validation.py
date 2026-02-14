from pathlib import Path
import pandas as pd

from src.rules_engine.parameters import StrategyConfig
from src.backtest.run_backtest import run_for_symbol


def split_time_folds(df: pd.DataFrame, n_folds: int = 4):
    # assumes timestamp column exists and is sortable
    d = df.sort_values("timestamp").reset_index(drop=True)
    n = len(d)
    fold_size = n // n_folds
    folds = []
    for i in range(n_folds):
        a = i * fold_size
        b = (i + 1) * fold_size if i < n_folds - 1 else n
        folds.append(d.iloc[a:b].copy())
    return folds


def evaluate_fold(symbol: str, fold_df: pd.DataFrame, fold_idx: int, out_root: Path, cfg: StrategyConfig):
    fold_dir = out_root / symbol / f"fold_{fold_idx+1}"
    fold_dir.mkdir(parents=True, exist_ok=True)
    fold_csv = fold_dir / f"{symbol}_3m_fold.csv"
    fold_df.to_csv(fold_csv, index=False)

    trades, rejections = run_for_symbol(
        symbol=symbol,
        csv_path=fold_csv,
        out_dir=fold_dir,
        cfg=cfg,
    )

    if trades.empty:
        return {
            "symbol": symbol,
            "fold": fold_idx + 1,
            "bars": len(fold_df),
            "trades": 0,
            "win_rate": 0.0,
            "expectancy": 0.0,
            "avg_r": 0.0,
            "rejections": len(rejections),
        }

    return {
        "symbol": symbol,
        "fold": fold_idx + 1,
        "bars": len(fold_df),
        "trades": len(trades),
        "win_rate": float((trades["pnl_abs"] > 0).mean()),
        "expectancy": float(trades["pnl_abs"].mean()),
        "avg_r": float(trades["r_multiple"].mean()) if "r_multiple" in trades.columns else 0.0,
        "rejections": len(rejections),
    }


def main():
    symbols = ["QQQ", "SPY"]  # tradable set
    cfg = StrategyConfig(
        enable_model_a=False,
        enable_model_b=False,
        enable_model_c=True,
        allowed_entry_hours=(10,),
        allowed_symbols=("SPY", "QQQ"),
)


    out_root = Path("outputs/rolling")
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in symbols:
        csv_path = Path(f"data/raw/{s}_3m.csv")
        if not csv_path.exists():
            print(f"{s}: missing input file")
            continue

        df = pd.read_csv(csv_path)
        if df.empty or "timestamp" not in df.columns:
            print(f"{s}: empty or invalid file")
            continue

        folds = split_time_folds(df, n_folds=4)
        for i, fold_df in enumerate(folds):
            row = evaluate_fold(s, fold_df, i, out_root, cfg)
            rows.append(row)

    out = pd.DataFrame(rows).sort_values(["symbol", "fold"])
    out_path = out_root / "rolling_summary.csv"
    out.to_csv(out_path, index=False)

    print(out.to_string(index=False))
    print(f"\nSaved: {out_path}")

    # stability verdict helper
    if not out.empty:
        stability = (
            out.groupby("symbol")
            .agg(
                folds=("fold", "count"),
                positive_folds=("expectancy", lambda x: int((x > 0).sum())),
                mean_expectancy=("expectancy", "mean"),
                min_expectancy=("expectancy", "min"),
            )
            .reset_index()
        )
        s_path = out_root / "rolling_stability.csv"
        stability.to_csv(s_path, index=False)
        print("\nStability:")
        print(stability.to_string(index=False))
        print(f"\nSaved: {s_path}")


if __name__ == "__main__":
    main()
