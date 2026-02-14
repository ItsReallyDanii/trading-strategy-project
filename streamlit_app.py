from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_BIN = "python"
DEFAULT_SYMBOLS = ["QQQ", "SPY", "AAPL", "IWM"]
TOP_SP_LIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK.B", "LLY", "AVGO",
    "TSLA", "JPM", "XOM", "UNH", "V", "WMT", "MA", "PG", "JNJ", "ORCL",
    "HD", "COST", "MRK", "ABBV", "BAC", "KO", "PEP", "ADBE", "NFLX", "CVX",
]
LOG_PATH = PROJECT_ROOT / "outputs" / "reports" / "ui_latest_run.log"
SCHEDULE_PATH = PROJECT_ROOT / "outputs" / "reports" / "ui_schedule_config.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _parse_symbols(text: str | None) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for token in text.replace("\n", ",").split(","):
        s = token.strip().upper()
        if not s:
            continue
        if s not in out:
            out.append(s)
    return out


def _symbols_string(symbols: Iterable[str]) -> str:
    deduped = []
    for s in symbols:
        su = s.strip().upper()
        if su and su not in deduped:
            deduped.append(su)
    return ",".join(deduped)


def _append_log(line: str) -> None:
    _ensure_parent(LOG_PATH)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    started = datetime.now(timezone.utc).isoformat()
    _append_log(f"[{started}] START {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        _append_log(proc.stdout)
    if proc.stderr:
        _append_log(proc.stderr)
    ended = datetime.now(timezone.utc).isoformat()
    _append_log(f"[{ended}] END exit={proc.returncode} {' '.join(cmd)}")
    merged = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, merged.strip()


def _run_ingest_only(symbols_csv: str) -> tuple[bool, str]:
    cmd = [PYTHON_BIN, "-m", "src.tools.append_market_data", "--symbols", symbols_csv, "--base-dir", "."]
    rc, out = _run_cmd(cmd)
    return rc == 0, out


def _run_full_cycle(symbols_csv: str) -> tuple[bool, str]:
    steps = [
        [PYTHON_BIN, "-m", "src.tools.append_market_data", "--symbols", symbols_csv, "--base-dir", "."],
        [PYTHON_BIN, "-m", "src.evaluation.run_universe"],
        [PYTHON_BIN, "-m", "src.evaluation.rolling_validation"],
        [PYTHON_BIN, "-m", "src.evaluation.stress_test_costs"],
        [PYTHON_BIN, "-m", "src.evaluation.promote_symbols"],
        [PYTHON_BIN, "-m", "src.tools.validate_deploy_scope"],
        [
            PYTHON_BIN,
            "-m",
            "src.learning.auto_refresh",
            "--symbols",
            symbols_csv,
            "--champion",
            "outputs/learning/champion.json",
            "--leaderboard",
            "outputs/learning/challenger_leaderboard.csv",
        ],
    ]

    all_out: list[str] = []
    for cmd in steps:
        rc, out = _run_cmd(cmd)
        all_out.append(f"$ {' '.join(cmd)}\n{out}\n")
        if rc != 0:
            return False, "\n".join(all_out)
    return True, "\n".join(all_out)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _badge(label: str, state: str) -> str:
    colors = {
        "good": "#16a34a",
        "warn": "#f59e0b",
        "bad": "#dc2626",
        "info": "#2563eb",
        "muted": "#6b7280",
    }
    color = colors.get(state, colors["muted"])
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{color};color:white;font-size:12px'>{label}</span>"


def _compute_status_rows(symbols: list[str]) -> pd.DataFrame:
    pm = _load_csv(PROJECT_ROOT / "outputs" / "reports" / "promotion_matrix.csv")
    cost = _load_csv(PROJECT_ROOT / "outputs" / "reports" / "cost_stress_summary.csv")
    trad = _load_csv(PROJECT_ROOT / "outputs" / "reports" / "tradable_symbols_next.csv")

    tradable_set = set(trad.get("symbol", pd.Series(dtype=str)).dropna().astype(str).str.upper().tolist())
    cost05 = pd.DataFrame(columns=["symbol", "expectancy_post_cost"])
    if not cost.empty and {"symbol", "cost_abs", "expectancy_post_cost"}.issubset(cost.columns):
        cost05 = cost[cost["cost_abs"] == 0.05][["symbol", "expectancy_post_cost"]].copy()
        cost05["symbol"] = cost05["symbol"].astype(str).str.upper()

    rows = []
    for sym in symbols:
        s = sym.upper()
        row = pm[pm.get("symbol", "").astype(str).str.upper() == s]
        tier = "inactive"
        trades = 0
        expectancy = 0.0
        if not row.empty:
            r = row.iloc[0]
            tier = str(r.get("tier", "inactive") or "inactive").lower()
            trades = int(pd.to_numeric(r.get("trades", 0), errors="coerce") or 0)
            expectancy = float(pd.to_numeric(r.get("expectancy", 0), errors="coerce") or 0)

        c = cost05[cost05["symbol"] == s]
        post_cost = float(pd.to_numeric(c.iloc[0]["expectancy_post_cost"], errors="coerce") or 0.0) if not c.empty else 0.0

        if s in tradable_set:
            lane = "active"
        elif tier in {"probation", "watch"}:
            lane = tier
        elif trades > 0 or expectancy > 0:
            lane = "watch"
        else:
            lane = "inactive"

        rows.append(
            {
                "symbol": s,
                "tradable_today": "yes" if s in tradable_set else "no",
                "cost_adjusted_edge": "positive" if post_cost > 0 else "negative",
                "lane_status": lane,
            }
        )
    return pd.DataFrame(rows)


def _show_policy_guard() -> None:
    trad = _load_csv(PROJECT_ROOT / "outputs" / "reports" / "tradable_symbols_next.csv")
    symbols = sorted(set(trad.get("symbol", pd.Series(dtype=str)).dropna().astype(str).str.upper().tolist()))
    ok = symbols == ["QQQ"]
    if ok:
        st.success("Deploy policy check: QQQ-only ✅")
    else:
        st.error(f"Deploy policy violation: expected QQQ-only, found {symbols}")


def _load_schedule_config() -> dict:
    d = _load_json(SCHEDULE_PATH)
    if not d:
        d = {"enabled": False, "cron": "*/3 13-20 * * 1-5", "timezone": "America/New_York", "mode": "full_cycle"}
    return d


def _save_schedule_config(cfg: dict) -> None:
    _ensure_parent(SCHEDULE_PATH)
    SCHEDULE_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def main() -> None:
    st.set_page_config(page_title="Trading Strategy Control Panel", layout="wide")
    st.title("Trading Strategy Control Panel (Read-Only Policy: QQQ Deploy)")

    with st.sidebar:
        st.header("Symbol Source")
        source = st.selectbox("Source", ["Preset", "Top S&P list", "Custom input"], index=0)
        if source == "Preset":
            base = DEFAULT_SYMBOLS
        elif source == "Top S&P list":
            base = TOP_SP_LIST
        else:
            base = _parse_symbols(st.text_area("Custom symbols (comma/newline)", value="QQQ,SPY,AAPL,IWM"))

        selected = st.multiselect("Symbols", options=base, default=base[:4] if len(base) >= 4 else base)
        symbols_csv = _symbols_string(selected)
        st.text_input("Generated symbols string", value=symbols_csv, disabled=True)

        st.header("Optional Schedule (config only)")
        cfg = _load_schedule_config()
        enabled = st.toggle("Enable schedule", value=bool(cfg.get("enabled", False)))
        cron = st.text_input("Cron expression", value=str(cfg.get("cron", "*/3 13-20 * * 1-5")))
        timezone_name = st.text_input("Timezone", value=str(cfg.get("timezone", "America/New_York")))
        mode = st.selectbox("Mode", ["ingest_only", "full_cycle"], index=0 if cfg.get("mode") == "ingest_only" else 1)
        if st.button("Save schedule config"):
            payload = {"enabled": enabled, "cron": cron, "timezone": timezone_name, "mode": mode}
            _save_schedule_config(payload)
            st.success(f"Saved schedule config -> {SCHEDULE_PATH.relative_to(PROJECT_ROOT)}")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Run ingest only", type="primary", disabled=not bool(symbols_csv)):
            ok, out = _run_ingest_only(symbols_csv)
            if ok:
                st.success("Ingest completed")
            else:
                st.error("Ingest failed")
            st.code(out or "(no output)")

    with col2:
        if st.button("Run full cycle", disabled=not bool(symbols_csv)):
            ok, out = _run_full_cycle(symbols_csv)
            if ok:
                st.success("Full cycle completed")
            else:
                st.error("Full cycle failed")
            st.code(out or "(no output)")

    st.divider()
    _show_policy_guard()

    st.subheader("Plain-language status badges")
    status_df = _compute_status_rows(_parse_symbols(symbols_csv) or DEFAULT_SYMBOLS)
    for _, r in status_df.iterrows():
        trad_badge = _badge("Tradable today" if r["tradable_today"] == "yes" else "Not tradable today", "good" if r["tradable_today"] == "yes" else "bad")
        edge_badge = _badge(
            "Cost-adjusted edge positive" if r["cost_adjusted_edge"] == "positive" else "Cost-adjusted edge negative",
            "good" if r["cost_adjusted_edge"] == "positive" else "warn",
        )
        lane = str(r["lane_status"]).lower()
        lane_state = "good" if lane == "active" else ("warn" if lane in {"probation", "watch"} else "muted")
        lane_badge = _badge(lane, lane_state)
        st.markdown(f"**{r['symbol']}** &nbsp; {trad_badge} &nbsp; {edge_badge} &nbsp; {lane_badge}", unsafe_allow_html=True)

    st.divider()
    st.subheader("Outputs")

    trad_path = PROJECT_ROOT / "outputs" / "reports" / "tradable_symbols_next.csv"
    st.markdown("**tradable_symbols_next.csv**")
    st.dataframe(_load_csv(trad_path), use_container_width=True)

    champ_path = PROJECT_ROOT / "outputs" / "learning" / "champion.json"
    st.markdown("**champion.json**")
    st.json(_load_json(champ_path))

    decay_path = PROJECT_ROOT / "outputs" / "learning" / "decay_status.json"
    st.markdown("**decay_status.json**")
    st.json(_load_json(decay_path))

    board_path = PROJECT_ROOT / "outputs" / "learning" / "challenger_leaderboard.csv"
    st.markdown("**challenger_leaderboard.csv (top 10)**")
    board = _load_csv(board_path)
    st.dataframe(board.head(10), use_container_width=True)

    st.markdown("**Latest run logs**")
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        st.code("\n".join(lines[-200:]))
    else:
        st.info("No run log yet. Use a run button to execute pipeline commands.")


if __name__ == "__main__":
    main()
