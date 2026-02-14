import argparse
from pathlib import Path
import numpy as np
import pandas as pd


COSTS = (0.02, 0.05, 0.10)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def apply_cost_stress(trades_df: pd.DataFrame, per_trade_cost_abs: float) -> dict:
    if trades_df.empty:
        return {
            "trades": np.nan,
            "win_rate": np.nan,
            "expectancy_pre_cost": np.nan,
            "expectancy_post_cost": np.nan,
        }

    pnl_col = "pnl_abs" if "pnl_abs" in trades_df.columns else None
    if pnl_col is None:
        return {
            "trades": np.nan,
            "win_rate": np.nan,
            "expectancy_pre_cost": np.nan,
            "expectancy_post_cost": np.nan,
        }

    pnl = pd.to_numeric(trades_df[pnl_col], errors="coerce").dropna()
    if pnl.empty:
        return {
            "trades": np.nan,
            "win_rate": np.nan,
            "expectancy_pre_cost": np.nan,
            "expectancy_post_cost": np.nan,
        }

    expectancy_pre = float(pnl.mean())
    expectancy_post = float((pnl - per_trade_cost_abs).mean())
    win_rate = float((pnl > 0).mean())

    return {
        "trades": float(len(pnl)),
        "win_rate": win_rate,
        "expectancy_pre_cost": expectancy_pre,
        "expectancy_post_cost": expectancy_post,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe-summary", default="outputs/universe/universe_summary.csv")
    parser.add_argument("--tradable-next", default="outputs/reports/tradable_symbols_next.csv")
    parser.add_argument("--universe-dir", default="outputs/universe")
    parser.add_argument("--out", default="outputs/reports/cost_stress_summary.csv")
    args = parser.parse_args()

    universe_df = _safe_read_csv(Path(args.universe_summary))
    tradable_df = _safe_read_csv(Path(args.tradable_next))

    if universe_df.empty or "symbol" not in universe_df.columns:
        raise SystemExit("Missing/invalid universe summary. Run run_universe first.")

    tradable_set = set()
    if not tradable_df.empty and "symbol" in tradable_df.columns:
        tradable_set = set(tradable_df["symbol"].dropna().astype(str).tolist())

    rows = []
    for symbol in universe_df["symbol"].astype(str).tolist():
        trades_path = Path(args.universe_dir) / symbol / f"{symbol}_trades.csv"
        trades_df = _safe_read_csv(trades_path)

        active = symbol in tradable_set
        status = "active" if active else "inactive_scope"
        inactive_reason = "" if active else "not_in_tradable_symbols_next"

        for c in COSTS:
            metrics = apply_cost_stress(trades_df if active else pd.DataFrame(), c)

            rows.append(
                {
                    "symbol": symbol,
                    "status": status,
                    "inactive_reason": inactive_reason,
                    "cost_abs": c,
                    "trades": metrics["trades"],
                    "win_rate": metrics["win_rate"],
                    "expectancy_pre_cost": metrics["expectancy_pre_cost"],
                    "expectancy_post_cost": metrics["expectancy_post_cost"],
                }
            )

    out_df = pd.DataFrame(rows)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    with pd.option_context("display.max_rows", 200, "display.width", 200):
        print(out_df.to_string(index=False))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
