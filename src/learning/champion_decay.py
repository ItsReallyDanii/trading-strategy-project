from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, obj: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _latest_symbol_rows(audit_csv: Path, symbol: str, lookback: int) -> pd.DataFrame:
    if not audit_csv.exists():
        return pd.DataFrame()
    df = pd.read_csv(audit_csv)
    if "new_symbol" not in df.columns:
        return pd.DataFrame()
    # Normalize symbol source: use new_symbol when refreshed, else old_symbol
    df["effective_symbol"] = df["new_symbol"].fillna(df.get("old_symbol"))
    out = df[df["effective_symbol"] == symbol].copy()
    if out.empty:
        return out
    return out.tail(lookback)


def _is_fail_row(
    row: pd.Series,
    min_exp_post_005: float,
    min_exp_post_010: float,
    min_pos_folds: int,
    min_expectancy: float,
) -> bool:
    # Conservative: any missing critical metric = fail
    checks = {
        "new_expectancy": row.get("new_expectancy"),
        "min_pos_folds": row.get("min_pos_folds"),
    }
    # We store thresholds in audit; live metrics may not all be there.
    # Fail on explicit "no_candidate_passed_guardrails" reason too.
    reason = str(row.get("reason", ""))
    if reason == "no_candidate_passed_guardrails":
        return True

    # If the run didn't refresh, we still treat as neutral unless no candidate passed.
    # You can tune this policy.
    new_exp = row.get("new_expectancy")
    if pd.isna(new_exp):
        return True

    return float(new_exp) < float(min_expectancy)


def main() -> None:
    parser = argparse.ArgumentParser(description="Champion decay detector")
    parser.add_argument("--champion", type=Path, default=Path("outputs/learning/champion.json"))
    parser.add_argument("--audit", type=Path, default=Path("outputs/learning/refresh_audit.csv"))
    parser.add_argument("--out", type=Path, default=Path("outputs/learning/decay_status.json"))
    parser.add_argument("--lookback", type=int, default=6, help="Recent refresh rows to inspect")
    parser.add_argument("--fail-streak", type=int, default=3, help="Consecutive fails to trigger demotion")
    parser.add_argument("--min-expectancy", type=float, default=0.0, help="Minimum acceptable expectancy")
    args = parser.parse_args()

    champion = _load_json(args.champion)
    symbol = champion.get("symbol", "QQQ")
    rows = _latest_symbol_rows(args.audit, symbol=symbol, lookback=args.lookback)

    fail_count = 0
    max_streak = 0

    if not rows.empty:
        for _, r in rows.iterrows():
            fail = _is_fail_row(
                r,
                min_exp_post_005=0.0,
                min_exp_post_010=0.0,
                min_pos_folds=3,
                min_expectancy=args.min_expectancy,
            )
            if fail:
                fail_count += 1
                max_streak = max(max_streak, fail_count)
            else:
                fail_count = 0

    decay_triggered = max_streak >= args.fail_streak

    result = {
        "symbol": symbol,
        "lookback_rows": int(len(rows)),
        "max_fail_streak": int(max_streak),
        "fail_streak_threshold": int(args.fail_streak),
        "decay_triggered": bool(decay_triggered),
        "current_champion_candidate_id": champion.get("candidate_id"),
        "current_expectancy": champion.get("expectancy"),
        "action": "demote_to_safe_mode" if decay_triggered else "keep_champion",
    }

    _save_json(args.out, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
