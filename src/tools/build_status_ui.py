from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULT_SYMBOLS = ["QQQ", "SPY", "AAPL", "IWM"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _read_ts_index(path: Path) -> tuple[int, str]:
    if not path.exists() or path.stat().st_size == 0:
        return 0, ""
    try:
        df = pd.read_csv(path, index_col=0)
        if df.empty:
            return 0, ""
        idx = pd.to_datetime(df.index, errors="coerce")
        idx = idx[~idx.isna()]
        if len(idx) == 0:
            return len(df), ""
        return len(df), str(idx.max())
    except Exception:
        return 0, ""


def _build_ingest_status(symbols: list[str], root: Path) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        h1 = root / "data" / "history" / f"{symbol}_1m_history.csv"
        h3 = root / "data" / "history" / f"{symbol}_3m_history.csv"
        r3 = root / "data" / "raw" / f"{symbol}_3m.csv"

        h1_rows, h1_last = _read_ts_index(h1)
        h3_rows, h3_last = _read_ts_index(h3)
        r3_rows, r3_last = _read_ts_index(r3)

        missing = [
            str(p.relative_to(root))
            for p in [h1, h3, r3]
            if (not p.exists() or p.stat().st_size == 0)
        ]
        if missing:
            status = "missing"
        elif min(h1_rows, h3_rows, r3_rows) == 0:
            status = "empty"
        else:
            status = "ok"

        rows.append(
            {
                "symbol": symbol,
                "status": status,
                "h1_rows": h1_rows,
                "h1_last_ts": h1_last,
                "h3_rows": h3_rows,
                "h3_last_ts": h3_last,
                "raw3_rows": r3_rows,
                "raw3_last_ts": r3_last,
                "missing_paths": "; ".join(missing),
            }
        )
    return pd.DataFrame(rows)


def _num_int(v: object, default: int = 0) -> int:
    n = pd.to_numeric(v, errors="coerce")
    if pd.isna(n):
        return default
    return int(n)


def _num_float(v: object, default: float = 0.0) -> float:
    n = pd.to_numeric(v, errors="coerce")
    if pd.isna(n):
        return default
    return float(n)


def _build_gate_status(symbols: list[str], root: Path) -> pd.DataFrame:
    pm = _read_csv(root / "outputs" / "reports" / "promotion_matrix.csv")
    cost = _read_csv(root / "outputs" / "reports" / "cost_stress_summary.csv")

    if "symbol" not in pm.columns:
        pm["symbol"] = []

    c05 = pd.DataFrame(columns=["symbol", "expectancy_post_cost"])
    if not cost.empty and {"symbol", "cost_abs"}.issubset(cost.columns):
        c05 = cost[cost["cost_abs"] == 0.05].copy()
        if "expectancy_post_cost" not in c05.columns:
            c05["expectancy_post_cost"] = 0.0
        c05 = c05[["symbol", "expectancy_post_cost"]]

    all_symbols = sorted(set(symbols) | set(pm.get("symbol", pd.Series([], dtype=str)).dropna().astype(str).tolist()))

    rows = []
    for symbol in all_symbols:
        pm_row = pm[pm.get("symbol", "") == symbol]
        if pm_row.empty:
            trades = 0
            positive_folds = 0
            expectancy = 0.0
            exp_post_005 = 0.0
        else:
            r = pm_row.iloc[0]
            trades = _num_int(r.get("trades", 0), 0)
            positive_folds = _num_int(r.get("positive_folds", 0), 0)
            expectancy = _num_float(r.get("expectancy", 0.0), 0.0)
            exp_post_005 = _num_float(r.get("exp_post_005", 0.0), 0.0)

        c05_row = c05[c05["symbol"] == symbol]
        c05_val = _num_float(c05_row["expectancy_post_cost"].iloc[0], 0.0) if not c05_row.empty else 0.0
        effective = exp_post_005 if exp_post_005 != 0 else c05_val

        checks = {
            "trades>=40": trades >= 40,
            "positive_folds>=3": positive_folds >= 3,
            "expectancy>0": expectancy > 0,
            "exp_post_005_effective>0": effective > 0,
        }
        fail_reasons = [k for k, v in checks.items() if not v]

        rows.append(
            {
                "symbol": symbol,
                "passed": len(fail_reasons) == 0,
                "trades": trades,
                "positive_folds": positive_folds,
                "expectancy": expectancy,
                "exp_post_005_effective": effective,
                "reasons": " | ".join(fail_reasons),
            }
        )

    return pd.DataFrame(rows)


def _build_deploy_scope_panel(root: Path) -> tuple[pd.DataFrame, bool, str]:
    p = root / "outputs" / "reports" / "tradable_symbols_next.csv"
    t = _read_csv(p)
    if "symbol" not in t.columns:
        t = pd.DataFrame(columns=["symbol"])
    symbols = sorted(set(t["symbol"].dropna().astype(str).str.upper().tolist()))
    scope_ok = symbols == ["QQQ"]
    scope_text = ",".join(symbols) if symbols else "<empty>"
    panel = pd.DataFrame([{"deploy_scope": scope_text, "scope_ok": scope_ok, "required": "QQQ-only"}])
    return panel, scope_ok, scope_text


def _build_champion_panel(root: Path) -> pd.DataFrame:
    champion_path = root / "outputs" / "learning" / "champion.json"
    decay_path = root / "outputs" / "learning" / "decay_status.json"

    champion = {}
    decay = {}
    if champion_path.exists():
        try:
            champion = json.loads(champion_path.read_text())
        except Exception:
            champion = {}
    if decay_path.exists():
        try:
            decay = json.loads(decay_path.read_text())
        except Exception:
            decay = {}

    return pd.DataFrame(
        [
            {
                "symbol": champion.get("symbol", ""),
                "candidate_id": champion.get("candidate_id", ""),
                "expectancy": champion.get("expectancy", ""),
                "decay_triggered": decay.get("decay_triggered", ""),
                "decay_action": decay.get("action", ""),
            }
        ]
    )


def _to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No data_\n"

    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"

    lines = [header, sep]
    for row in df.fillna("").astype(str).itertuples(index=False):
        escaped = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build read-only status UI markdown from pipeline outputs.")
    p.add_argument("--root", type=Path, default=Path("."), help="Project root")
    p.add_argument("--symbols", type=str, default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbols")
    p.add_argument("--out", type=Path, default=Path("outputs/reports/status_ui.md"), help="Markdown output path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    ingest_df = _build_ingest_status(symbols, root)
    gate_df = _build_gate_status(symbols, root)
    deploy_df, scope_ok, scope_text = _build_deploy_scope_panel(root)
    champion_df = _build_champion_panel(root)

    sections = [
        "# Pipeline Status UI (Read-Only)",
        "",
        "## Ingest Status (per symbol)",
        _to_markdown(ingest_df),
        "## Gate Status (per symbol + reasons)",
        _to_markdown(gate_df),
        "## Deploy Scope Panel",
        _to_markdown(deploy_df),
        "## Champion Panel",
        _to_markdown(champion_df),
        "## Notes",
        f"- Deploy scope check: {'PASS' if scope_ok else 'FAIL'} (current: {scope_text}; required: QQQ-only)",
        "- This file is generated from existing outputs and does not mutate policy/strategy logic.",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sections) + "\n")
    print(f"Saved status UI markdown -> {args.out}")


if __name__ == "__main__":
    main()
