import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe-summary", default="outputs/universe/universe_summary.csv")
    parser.add_argument("--rolling-stability", default="outputs/rolling/rolling_stability.csv")
    parser.add_argument("--cost-stress", default="outputs/reports/cost_stress_summary.csv")
    parser.add_argument("--out-matrix", default="outputs/reports/promotion_matrix.csv")
    parser.add_argument("--out-tradable", default="outputs/reports/tradable_symbols_next.csv")
    args = parser.parse_args()

    u = _safe_read_csv(Path(args.universe_summary))
    r = _safe_read_csv(Path(args.rolling_stability))
    c = _safe_read_csv(Path(args.cost_stress))

    if u.empty or "symbol" not in u.columns:
        raise SystemExit("Missing universe summary.")
    if r.empty or "symbol" not in r.columns:
        raise SystemExit("Missing rolling stability.")
    if c.empty or "symbol" not in c.columns:
        raise SystemExit("Missing cost stress summary.")

    # active rows only for post-cost gates
    c_active = c[c["status"] == "active"].copy() if "status" in c.columns else c.copy()

    c005 = c_active[c_active["cost_abs"] == 0.05][["symbol", "expectancy_post_cost"]].rename(
        columns={"expectancy_post_cost": "exp_post_005"}
    )
    c010 = c_active[c_active["cost_abs"] == 0.10][["symbol", "expectancy_post_cost"]].rename(
        columns={"expectancy_post_cost": "exp_post_010"}
    )

    m = (
        u[["symbol", "trades", "expectancy"]]
        .merge(r[["symbol", "positive_folds", "mean_expectancy"]], on="symbol", how="left")
        .merge(c005, on="symbol", how="left")
        .merge(c010, on="symbol", how="left")
    )

    # Gates: only symbols with enough evidence can promote
    # Keep existing philosophy: durable_candidate if robust + post-cost positive
    def classify(row):
        trades = row.get("trades", np.nan)
        pos_folds = row.get("positive_folds", np.nan)
        exp005 = row.get("exp_post_005", np.nan)
        exp010 = row.get("exp_post_010", np.nan)

        if pd.isna(trades) or trades < 30:
            return "watch"
        if pd.isna(pos_folds) or pos_folds < 3:
            return "watch"
        if pd.isna(exp005) or exp005 <= 0:
            return "watch"
        if pd.isna(exp010) or exp010 <= 0:
            return "watch"
        return "durable_candidate"

    m["tier"] = m.apply(classify, axis=1)

    out_matrix = Path(args.out_matrix)
    out_matrix.parent.mkdir(parents=True, exist_ok=True)
    m.to_csv(out_matrix, index=False)

    tradable = m[m["tier"] == "durable_candidate"][["symbol"]].copy()
    out_tradable = Path(args.out_tradable)
    tradable.to_csv(out_tradable, index=False)

    with pd.option_context("display.max_rows", 200, "display.width", 200):
        print(m.to_string(index=False))
    print(f"\nSaved: {out_matrix}")
    print(f"Saved: {out_tradable}")


if __name__ == "__main__":
    main()
