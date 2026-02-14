# src/learning/challenger_search.py
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.backtest.run_backtest import run_for_symbol
from src.rules_engine.parameters import StrategyConfig


def _safe_expectancy(trades_df: pd.DataFrame) -> float:
    if trades_df is None or trades_df.empty:
        return 0.0
    if "pnl_abs" not in trades_df.columns:
        return 0.0
    return float(trades_df["pnl_abs"].mean())


def _safe_win_rate(trades_df: pd.DataFrame) -> float:
    if trades_df is None or trades_df.empty or "pnl_abs" not in trades_df.columns:
        return 0.0
    return float((trades_df["pnl_abs"] > 0).mean())


def _safe_avg_r(trades_df: pd.DataFrame) -> float:
    if trades_df is None or trades_df.empty:
        return 0.0
    if "r_multiple" in trades_df.columns:
        return float(trades_df["r_multiple"].mean())
    # fallback if r_multiple not present
    return 0.0


def _positive_folds_stats(
    symbol: str,
    input_csv: Path,
    cfg: StrategyConfig,
    folds: int = 4,
) -> Tuple[int, float, float]:
    """
    Rolling fold evaluation using contiguous chunks.
    Returns:
      positive_folds, mean_expectancy, min_expectancy
    """
    df = pd.read_csv(input_csv)
    if df.empty:
        return 0, 0.0, 0.0

    n = len(df)
    fold_size = n // folds
    fold_exps: List[float] = []

    tmp_dir = Path("outputs/learning/_tmp_folds")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for i in range(folds):
        start = i * fold_size
        end = (i + 1) * fold_size if i < folds - 1 else n
        fold_df = df.iloc[start:end].copy()
        if fold_df.empty:
            fold_exps.append(0.0)
            continue

        fold_csv = tmp_dir / f"{symbol}_fold_{i+1}.csv"
        fold_df.to_csv(fold_csv, index=False)

        trades, _rejections = run_for_symbol(
            symbol=symbol,
            csv_path=fold_csv,
            out_dir=tmp_dir / f"{symbol}_fold_{i+1}",
            cfg=cfg,
        )
        exp_i = _safe_expectancy(trades)
        fold_exps.append(exp_i)

    if not fold_exps:
        return 0, 0.0, 0.0

    pos = int(sum(1 for x in fold_exps if x > 0))
    mean_exp = float(np.mean(fold_exps))
    min_exp = float(np.min(fold_exps))
    return pos, mean_exp, min_exp


def _evaluate_candidate(
    symbol: str,
    input_csv: Path,
    cfg: StrategyConfig,
    out_dir: Path,
) -> Dict:
    trades, rejections = run_for_symbol(
        symbol=symbol,
        csv_path=input_csv,
        out_dir=out_dir,
        cfg=cfg,
    )

    trades_count = int(len(trades)) if trades is not None else 0
    rej_count = int(len(rejections)) if rejections is not None else 0
    expectancy = _safe_expectancy(trades)
    win_rate = _safe_win_rate(trades)
    avg_r = _safe_avg_r(trades)

    # --- FIX: derive cost-stressed expectancy from raw expectancy ---
    # cost_abs is per-trade absolute cost deducted from pnl_abs
    exp_post_005 = float(expectancy - 0.05) if trades_count > 0 else 0.0
    exp_post_010 = float(expectancy - 0.10) if trades_count > 0 else 0.0

    positive_folds, mean_expectancy, min_expectancy = _positive_folds_stats(
        symbol=symbol,
        input_csv=input_csv,
        cfg=cfg,
        folds=4,
    )

    return {
        "symbol": symbol,
        "trades": trades_count,
        "win_rate": win_rate,
        "expectancy": expectancy,
        "avg_r": avg_r,
        "rejections": rej_count,
        "exp_post_005": exp_post_005,
        "exp_post_010": exp_post_010,
        "positive_folds": positive_folds,
        "mean_expectancy": mean_expectancy,
        "min_expectancy": min_expectancy,
    }


def _candidate_grid() -> List[Tuple[float, float, float]]:
    disp_vals = [1.0, 1.1, 1.2, 1.3]
    rr_vals = [2.0, 2.5, 3.0]
    reclaim_vals = [0.02, 0.03, 0.04]
    grid: List[Tuple[float, float, float]] = []
    for d in disp_vals:
        for r in rr_vals:
            for rc in reclaim_vals:
                grid.append((d, r, rc))
    return grid


def _score_row(row: pd.Series) -> float:
    """
    Composite score: prioritize robust post-cost expectancy and stability.
    """
    return float(
        0.40 * row["expectancy"]
        + 0.25 * row["exp_post_005"]
        + 0.20 * row["mean_expectancy"]
        + 0.10 * row["avg_r"]
        + 0.05 * (row["positive_folds"] / 4.0)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", type=str, default="QQQ")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/learning/challenger_leaderboard.csv"),
    )
    args = ap.parse_args()

    symbol = args.symbol.upper()
    input_csv = args.input
    out_csv = args.out

    base_cfg = StrategyConfig()

    rows: List[Dict] = []
    out_root = Path("outputs/learning/candidates")
    out_root.mkdir(parents=True, exist_ok=True)

    cid = 1
    for disp, rr, reclaim in _candidate_grid():
        cfg = replace(
            base_cfg,
            displacement_atr_mult=disp,
            rr_target=rr,
            reclaim_buffer_atr=reclaim,
        )

        cand_dir = out_root / f"{symbol}_cand_{cid}"
        cand_dir.mkdir(parents=True, exist_ok=True)

        metrics = _evaluate_candidate(
            symbol=symbol,
            input_csv=input_csv,
            cfg=cfg,
            out_dir=cand_dir,
        )

        row = {
            "candidate_id": cid,
            "symbol": symbol,
            "disp": disp,
            "rr": rr,
            "reclaim": reclaim,
            **metrics,
        }
        rows.append(row)
        cid += 1

    lb = pd.DataFrame(rows)
    if lb.empty:
        raise RuntimeError("No candidates evaluated.")

    lb["score"] = lb.apply(_score_row, axis=1)
    lb = lb.sort_values(
        by=["score", "expectancy", "exp_post_005", "trades"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    lb.to_csv(out_csv, index=False)

    show_cols = [
        "candidate_id",
        "symbol",
        "disp",
        "rr",
        "reclaim",
        "trades",
        "win_rate",
        "expectancy",
        "avg_r",
        "rejections",
        "exp_post_005",
        "exp_post_010",
        "positive_folds",
        "mean_expectancy",
        "min_expectancy",
    ]
    print(lb[show_cols].head(10).to_string(index=False))
    print(f"\nSaved: {out_csv}")


if __name__ == "__main__":
    main()
