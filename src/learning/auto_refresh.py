from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class RefreshConfig:
    symbols: List[str]
    champion_path: Path
    leaderboard_path: Path
    promotion_matrix_path: Path
    tradable_next_path: Path
    audit_log_path: Path
    min_delta: float = 0.01
    min_trades: int = 40
    min_pos_folds: int = 3
    min_exp_post_005: float = 0.0
    min_exp_post_010: float = 0.0
    min_expectancy_floor: float = -0.20
    dry_run: bool = False


def _run(cmd: List[str]) -> None:
    print(f"[RUN] {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}")


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _candidate_passes(row: pd.Series, current_exp: float, cfg: RefreshConfig) -> bool:
    # Defensive NaN handling
    required_fields = [
        "expectancy",
        "exp_post_005",
        "exp_post_010",
        "positive_folds",
        "trades",
        "min_expectancy",
    ]
    for col in required_fields:
        if col not in row or pd.isna(row[col]):
            return False

    return (
        float(row["trades"]) >= cfg.min_trades
        and int(row["positive_folds"]) >= cfg.min_pos_folds
        and float(row["expectancy"]) > float(current_exp) + cfg.min_delta
        and float(row["exp_post_005"]) > cfg.min_exp_post_005
        and float(row["exp_post_010"]) > cfg.min_exp_post_010
        and float(row["min_expectancy"]) > cfg.min_expectancy_floor
    )


def _choose_best_candidate_for_symbol(
    symbol: str,
    leaderboard: pd.DataFrame,
    current_exp: float,
    cfg: RefreshConfig,
) -> Optional[pd.Series]:
    lb = leaderboard[leaderboard["symbol"] == symbol].copy()
    if lb.empty:
        return None

    # Prefer strongest robust candidate
    sort_cols = ["expectancy", "exp_post_010", "exp_post_005", "mean_expectancy", "trades"]
    for c in sort_cols:
        if c not in lb.columns:
            lb[c] = 0.0
    lb = lb.sort_values(sort_cols, ascending=False)

    for _, row in lb.iterrows():
        if _candidate_passes(row, current_exp=current_exp, cfg=cfg):
            return row
    return None


def _build_champion_from_row(row: pd.Series) -> Dict:
    # Keep keys consistent with existing champion format
    return {
        "symbol": str(row["symbol"]),
        "candidate_id": int(row["candidate_id"]),
        "disp": float(row["disp"]),
        "rr": float(row["rr"]),
        "reclaim": float(row["reclaim"]),
        "trades": int(row["trades"]),
        "win_rate": float(row["win_rate"]),
        "expectancy": float(row["expectancy"]),
        "exp_post_005": float(row["exp_post_005"]),
        "exp_post_010": float(row["exp_post_010"]),
        "positive_folds": int(row["positive_folds"]),
        "mean_expectancy": float(row["mean_expectancy"]),
        "min_expectancy": float(row["min_expectancy"]),
        "score": float(
            0.5 * float(row["expectancy"])
            + 0.3 * float(row["exp_post_010"])
            + 0.2 * float(row["mean_expectancy"])
        ),
        "refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _append_audit(audit_path: Path, payload: Dict) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([payload])
    if audit_path.exists():
        prev = pd.read_csv(audit_path)
        out = pd.concat([prev, row], ignore_index=True)
    else:
        out = row
    out.to_csv(audit_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-refresh champion with strict guardrails.")
    parser.add_argument("--symbols", type=str, default="QQQ,SPY,AAPL,IWM")
    parser.add_argument("--champion", type=Path, default=Path("outputs/learning/champion.json"))
    parser.add_argument("--leaderboard", type=Path, default=Path("outputs/learning/challenger_leaderboard.csv"))
    parser.add_argument("--promotion-matrix", type=Path, default=Path("outputs/reports/promotion_matrix.csv"))
    parser.add_argument("--tradable-next", type=Path, default=Path("outputs/reports/tradable_symbols_next.csv"))
    parser.add_argument("--audit-log", type=Path, default=Path("outputs/learning/refresh_audit.csv"))
    parser.add_argument("--min-delta", type=float, default=0.01)
    parser.add_argument("--min-trades", type=int, default=40)
    parser.add_argument("--min-pos-folds", type=int, default=3)
    parser.add_argument("--min-exp-post-005", type=float, default=0.0)
    parser.add_argument("--min-exp-post-010", type=float, default=0.0)
    parser.add_argument("--min-expectancy-floor", type=float, default=-0.20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = RefreshConfig(
        symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()],
        champion_path=args.champion,
        leaderboard_path=args.leaderboard,
        promotion_matrix_path=args.promotion_matrix,
        tradable_next_path=args.tradable_next,
        audit_log_path=args.audit_log,
        min_delta=args.min_delta,
        min_trades=args.min_trades,
        min_pos_folds=args.min_pos_folds,
        min_exp_post_005=args.min_exp_post_005,
        min_exp_post_010=args.min_exp_post_010,
        min_expectancy_floor=args.min_expectancy_floor,
        dry_run=args.dry_run,
    )

    # 1) Data + evaluations (multi-symbol learning scope)
    _run([sys.executable, "-m", "src.tools.append_market_data"])
    _run([sys.executable, "-m", "src.evaluation.run_universe"])
    _run([sys.executable, "-m", "src.evaluation.rolling_validation"])
    _run([sys.executable, "-m", "src.evaluation.stress_test_costs"])
    _run([sys.executable, "-m", "src.evaluation.promote_symbols"])
    _run([sys.executable, "-m", "src.tools.validate_deploy_scope"])

    # 2) Challenger search for each symbol in learning scope
    for sym in cfg.symbols:
        input_csv = Path(f"data/raw/{sym}_3m.csv")
        if input_csv.exists():
            _run(
                [
                    sys.executable,
                    "-m",
                    "src.learning.challenger_search",
                    "--symbol",
                    sym,
                    "--input",
                    str(input_csv),
                    "--out",
                    str(cfg.leaderboard_path),
                ]
            )

    # 3) Load latest artifacts
    if not cfg.leaderboard_path.exists():
        raise FileNotFoundError(f"Missing leaderboard: {cfg.leaderboard_path}")

    leaderboard = pd.read_csv(cfg.leaderboard_path)
    current = _load_json(cfg.champion_path)
    current_symbol = str(current.get("symbol", "QQQ"))
    current_expectancy = float(current.get("expectancy", 0.0))

    # If current symbol no longer valid, allow re-selection from symbols list
    candidate_symbol_order = [current_symbol] + [s for s in cfg.symbols if s != current_symbol]

    chosen = None
    chosen_reason = "no_candidate_passed_guardrails"

    for sym in candidate_symbol_order:
        row = _choose_best_candidate_for_symbol(sym, leaderboard, current_expectancy, cfg)
        if row is not None:
            chosen = row
            chosen_reason = "passed_guardrails"
            break

    refreshed = False
    if chosen is not None:
        new_champ = _build_champion_from_row(chosen)
        if not cfg.dry_run:
            _save_json(cfg.champion_path, new_champ)
        refreshed = True
        print(f"Champion refreshed -> {cfg.champion_path}")
        print(new_champ)
    else:
        print("No champion refresh. Existing champion retained.")

    _append_audit(
        cfg.audit_log_path,
        {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "symbols": ",".join(cfg.symbols),
            "old_symbol": current.get("symbol"),
            "old_candidate_id": current.get("candidate_id"),
            "old_expectancy": current.get("expectancy"),
            "refreshed": refreshed,
            "reason": chosen_reason,
            "new_symbol": (None if chosen is None else str(chosen["symbol"])),
            "new_candidate_id": (None if chosen is None else int(chosen["candidate_id"])),
            "new_expectancy": (None if chosen is None else float(chosen["expectancy"])),
            "min_delta": cfg.min_delta,
            "min_trades": cfg.min_trades,
            "min_pos_folds": cfg.min_pos_folds,
            "min_exp_post_005": cfg.min_exp_post_005,
            "min_exp_post_010": cfg.min_exp_post_010,
            "min_expectancy_floor": cfg.min_expectancy_floor,
            "dry_run": cfg.dry_run,
        },
    )
    print(f"Audit log updated -> {cfg.audit_log_path}")


if __name__ == "__main__":
    main()
