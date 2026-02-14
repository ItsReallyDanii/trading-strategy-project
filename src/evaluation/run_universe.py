from pathlib import Path
import pandas as pd

from src.rules_engine.parameters import StrategyConfig
from src.backtest.run_backtest import run_for_symbol


def cfg_for_symbol(symbol: str) -> StrategyConfig:
    base = StrategyConfig(
        displacement_atr_mult=1.1,
        rr_target=2.5,
        reclaim_buffer_atr=0.03,
        allowed_entry_hours=(10,),
        enable_model_a=False,
        enable_model_b=True,
        enable_model_c=True,
    )
    if symbol == "QQQ":
        return StrategyConfig(
            displacement_atr_mult=1.3,
            rr_target=2.0,
            reclaim_buffer_atr=0.05,
            allowed_entry_hours=(10,),
            enable_model_a=False,
            enable_model_b=True,
            enable_model_c=True,
        )
    return base


def main():
    symbols = ["SPY", "QQQ", "AAPL", "IWM"]
    out_root = Path("outputs/universe")
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []

    for s in symbols:
        csv_path = Path(f"data/raw/{s}_3m.csv")
        if not csv_path.exists():
            print(f"{s}: missing input file, skipping")
            rows.append({"symbol": s, "trades": 0, "win_rate": 0.0, "expectancy": 0.0, "avg_r": 0.0, "rejections": 0})
            continue

        # Empty-file safety
        try:
            df_check = pd.read_csv(csv_path)
        except Exception as e:
            print(f"{s}: failed to read {csv_path}: {e}")
            rows.append({"symbol": s, "trades": 0, "win_rate": 0.0, "expectancy": 0.0, "avg_r": 0.0, "rejections": 0})
            continue

        if df_check.empty:
            print(f"{s}: empty input file, skipping")
            rows.append({"symbol": s, "trades": 0, "win_rate": 0.0, "expectancy": 0.0, "avg_r": 0.0, "rejections": 0})
            continue

        cfg = cfg_for_symbol(s)

        trades, rejections = run_for_symbol(
            symbol=s,
            csv_path=csv_path,
            out_dir=out_root / s,
            cfg=cfg,
        )

        if trades.empty:
            rows.append({
                "symbol": s,
                "trades": 0,
                "win_rate": 0.0,
                "expectancy": 0.0,
                "avg_r": 0.0,
                "rejections": len(rejections),
            })
            continue

        rows.append({
            "symbol": s,
            "trades": len(trades),
            "win_rate": float((trades["pnl_abs"] > 0).mean()),
            "expectancy": float(trades["pnl_abs"].mean()),
            "avg_r": float(trades["r_multiple"].mean()) if "r_multiple" in trades.columns else 0.0,
            "rejections": len(rejections),
        })

    summary = pd.DataFrame(rows).sort_values("expectancy", ascending=False)
    summary.to_csv(out_root / "universe_summary.csv", index=False)

    print(summary.to_string(index=False))
    print(f"\nSaved: {out_root / 'universe_summary.csv'}")


if __name__ == "__main__":
    main()
