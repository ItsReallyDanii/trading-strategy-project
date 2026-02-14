import itertools
from pathlib import Path
import pandas as pd

from src.rules_engine.parameters import StrategyConfig
from src.backtest.run_backtest import run_for_symbol


def run_sweep():
    symbol = "SPY"
    input_csv = Path("data/raw/SPY_3m.csv")
    out_root = Path("outputs/sweeps")
    out_root.mkdir(parents=True, exist_ok=True)

    displacement_grid = [0.7, 0.9, 1.1, 1.3]
    rr_grid = [1.5, 2.0, 2.5]
    reclaim_grid = [0.02, 0.03, 0.05]

    rows = []

    for disp, rr, reclaim in itertools.product(displacement_grid, rr_grid, reclaim_grid):
        cfg = StrategyConfig(
            displacement_atr_mult=disp,
            rr_target=rr,
            reclaim_buffer_atr=reclaim,
        )

        run_dir = out_root / f"d{disp}_rr{rr}_rb{reclaim}"
        trades, rejections = run_for_symbol(
            symbol=symbol,
            csv_path=input_csv,
            out_dir=run_dir,
            cfg=cfg,
        )

        if trades.empty:
            rows.append({
                "disp": disp,
                "rr": rr,
                "reclaim": reclaim,
                "trades": 0,
                "win_rate": 0.0,
                "expectancy": 0.0,
                "rejections": len(rejections),
            })
            continue

        win_rate = float((trades["pnl_abs"] > 0).mean())
        expectancy = float(trades["pnl_abs"].mean())

        rows.append({
            "disp": disp,
            "rr": rr,
            "reclaim": reclaim,
            "trades": len(trades),
            "win_rate": win_rate,
            "expectancy": expectancy,
            "rejections": len(rejections),
        })

    out = pd.DataFrame(rows).sort_values("expectancy", ascending=False)
    out_path = out_root / "leaderboard.csv"
    out.to_csv(out_path, index=False)

    print("Top 10 configs by expectancy:")
    print(out.head(10).to_string(index=False))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    run_sweep()
