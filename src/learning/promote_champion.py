from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _pick_first_existing(row: pd.Series, cols: list[str], default=0.0) -> float:
    for c in cols:
        if c in row and pd.notna(row[c]):
            try:
                return float(row[c])
            except Exception:
                pass
    return float(default)


def _load_current_expectancy(champion_path: Path) -> float:
    if not champion_path.exists():
        return 0.0
    try:
        data = json.loads(champion_path.read_text())
    except Exception:
        return 0.0

    for k in ["expectancy", "expectancy_post_cost", "exp_post_005", "champion_expectancy", "score"]:
        v = data.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--leaderboard", required=True)
    parser.add_argument("--champion", required=True)
    parser.add_argument("--min-trades", type=int, default=40)

    # Support both spellings
    parser.add_argument("--min-pos-folds", type=int, default=None)
    parser.add_argument("--min-positive-folds", type=int, default=None)

    # Keep compatibility with older script variants
    parser.add_argument("--min-delta", type=float, default=0.0)
    parser.add_argument("--promotion-buffer", type=float, default=None)

    parser.add_argument("--require-positive-min-fold", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    lb_path = Path(args.leaderboard)
    champion_path = Path(args.champion)

    min_pos_folds = (
        args.min_positive_folds
        if args.min_positive_folds is not None
        else (args.min_pos_folds if args.min_pos_folds is not None else 3)
    )

    promotion_buffer = (
        args.promotion_buffer if args.promotion_buffer is not None else args.min_delta
    )

    if not lb_path.exists():
        print(f"No leaderboard found: {lb_path}")
        return

    df = pd.read_csv(lb_path)
    if df.empty:
        print("Leaderboard is empty. No promotion.")
        return

    if "symbol" in df.columns:
        df = df[df["symbol"].astype(str).str.upper() == symbol]

    if df.empty:
        print(f"No rows for symbol={symbol}. No promotion.")
        return

    def row_score(r: pd.Series) -> float:
        exp = _pick_first_existing(r, ["expectancy", "expectancy_pre_cost"], 0.0)
        exp_post_005 = _pick_first_existing(r, ["exp_post_005", "expectancy_post_cost_005"], 0.0)
        exp_post_010 = _pick_first_existing(r, ["exp_post_010", "expectancy_post_cost_010"], 0.0)
        mean_exp = _pick_first_existing(r, ["mean_expectancy"], 0.0)
        return exp + 0.7 * exp_post_005 + 0.5 * exp_post_010 + 0.2 * mean_exp

    elig = df.copy()

    if "trades" in elig.columns:
        elig = elig[elig["trades"].fillna(0) >= args.min_trades]
    if "positive_folds" in elig.columns:
        elig = elig[elig["positive_folds"].fillna(0) >= min_pos_folds]
    if args.require_positive_min_fold and "min_expectancy" in elig.columns:
        elig = elig[elig["min_expectancy"].fillna(0) > 0]

    if elig.empty:
        print("No promotion. No eligible candidates after gates.")
        return

    elig = elig.copy()
    elig["__score__"] = elig.apply(row_score, axis=1)
    winner = elig.sort_values("__score__", ascending=False).iloc[0]

    winner_expectancy = _pick_first_existing(winner, ["expectancy", "expectancy_pre_cost"], 0.0)
    current_expectancy = _load_current_expectancy(champion_path)

    if winner_expectancy <= current_expectancy + float(promotion_buffer):
        print("No promotion. Champion remains unchanged.")
        print(f"Champion expectancy: {current_expectancy:.6f}")
        return

    payload = {
        "symbol": symbol,
        "candidate_id": int(winner["candidate_id"]) if "candidate_id" in winner else None,
        "disp": _pick_first_existing(winner, ["disp"], None),
        "rr": _pick_first_existing(winner, ["rr"], None),
        "reclaim": _pick_first_existing(winner, ["reclaim"], None),
        "trades": int(_pick_first_existing(winner, ["trades"], 0)),
        "win_rate": _pick_first_existing(winner, ["win_rate"], 0.0),
        "expectancy": winner_expectancy,
        "exp_post_005": _pick_first_existing(winner, ["exp_post_005", "expectancy_post_cost_005"], 0.0),
        "exp_post_010": _pick_first_existing(winner, ["exp_post_010", "expectancy_post_cost_010"], 0.0),
        "positive_folds": int(_pick_first_existing(winner, ["positive_folds"], 0)),
        "mean_expectancy": _pick_first_existing(winner, ["mean_expectancy"], 0.0),
        "min_expectancy": _pick_first_existing(winner, ["min_expectancy"], 0.0),
        "score": float(winner["__score__"]),
    }

    champion_path.parent.mkdir(parents=True, exist_ok=True)
    champion_path.write_text(json.dumps(payload, indent=2))
    print(f"Promoted new champion -> {champion_path}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
