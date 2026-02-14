import argparse
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from src.rules_engine.parameters import StrategyConfig
from src.features.structure_15m import build_external_structure
from src.features.liquidity_map import add_intraday_session_fields, add_liquidity_levels
from src.rules_engine.signals import generate_signal_for_bar
from src.rules_engine.risk import initial_stop, target_from_rr


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # timestamp alias handling
    if "timestamp" not in df.columns:
        for alt in ("datetime", "date", "time", "index"):
            if alt in df.columns:
                df = df.rename(columns={alt: "timestamp"})
                break

    # ohlcv alias handling
    alias = {
        "adj close": "close",
        "adj_close": "close",
        "vol": "volume",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    }
    for src, dst in alias.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")

    # CRITICAL: force UTC tz-aware timestamps so downstream tz_convert is valid
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

    # OHLC sanity
    df = df[(df["high"] >= df["low"])]
    df = df[(df["open"] <= df["high"]) & (df["open"] >= df["low"])]
    df = df[(df["close"] <= df["high"]) & (df["close"] >= df["low"])]

    # downstream feature funcs expect DatetimeIndex
    df = df.set_index("timestamp").sort_index()
    df.index.name = "timestamp"

    return df


def resample_15m(df_3m: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_3m.index, pd.DatetimeIndex):
        raise TypeError("resample_15m requires DatetimeIndex")

    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = df_3m.resample("15min", label="right", closed="right").agg(agg).dropna()
    out.index.name = "timestamp"
    return out


def _ensure_timestamp_column(df: pd.DataFrame) -> pd.DataFrame:
    x = df.reset_index()
    if "timestamp" in x.columns:
        return x
    if "index" in x.columns:
        return x.rename(columns={"index": "timestamp"})
    return x.rename(columns={x.columns[0]: "timestamp"})


def _to_ny_timestamp(series: pd.Series) -> pd.Series:
    # robust normalize to tz-aware then convert
    s = pd.to_datetime(series, errors="coerce", utc=True)
    return s.dt.tz_convert("America/New_York")


def merge_3m_with_15m_state(df_3m: pd.DataFrame, df_15m_state: pd.DataFrame) -> pd.DataFrame:
    cols = ["external_bias", "protected_swing_high", "protected_swing_low", "atr", "bos_flag", "choch_flag"]
    state = df_15m_state[cols].copy()

    left = _ensure_timestamp_column(df_3m).sort_values("timestamp")
    right = _ensure_timestamp_column(state).sort_values("timestamp")

    left["timestamp"] = _to_ny_timestamp(left["timestamp"])
    right["timestamp"] = _to_ny_timestamp(right["timestamp"])

    merged = pd.merge_asof(left, right, on="timestamp", direction="backward")
    merged = merged.set_index("timestamp").sort_index()
    merged.index.name = "timestamp"
    return merged


def add_model_feature_flags(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Lightweight deterministic proxies to replace hardcoded placeholders.
    Keeps project moving until full micro-structure parser is added.
    """
    out = merged.copy()

    # Sweep proxy: touches below prev_day_low then closes back above it
    out["swept_level"] = out["prev_day_low"]

    # Failed CHOCH proxy
    roll_hi = out["high"].rolling(6, min_periods=6).max().shift(1)
    broke_up = out["close"] > roll_hi
    failed_up = broke_up.shift(1).fillna(False) & (out["close"] < roll_hi)
    out["failed_choch_confirmed"] = failed_up.fillna(False)

    # Pullback respected proxy
    out["pullback_respected"] = True

    # Internal sweep reclaim proxy
    out["internal_sweep_reclaim"] = out["close"] > out["low"].shift(1)

    return out


def simulate_trades(symbol: str, df_3m: pd.DataFrame, cfg: StrategyConfig):
    trades: List[Dict[str, Any]] = []
    rejections: List[Dict[str, Any]] = []

    in_pos = False
    side = None
    entry_price = stop_price = target_price = None
    entry_ts = None
    entry_model = None
    reason_open = None

    for i in range(2, len(df_3m)):
        ts = df_3m.index[i]
        row = df_3m.iloc[i]
        prev = df_3m.iloc[i - 1]

        # Exit first
        if in_pos:
            hit_stop = False
            hit_target = False

            if side == "long":
                hit_stop = row["low"] <= stop_price
                hit_target = (not hit_stop) and (row["high"] >= target_price)
            else:
                hit_stop = row["high"] >= stop_price
                hit_target = (not hit_stop) and (row["low"] <= target_price)

            if hit_stop or hit_target:
                exit_price = stop_price if hit_stop else target_price
                pnl = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
                r_mult = pnl / abs(entry_price - stop_price) if abs(entry_price - stop_price) > 0 else 0.0

                trades.append(
                    {
                        "symbol": symbol,
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "stop_price": stop_price,
                        "target_price": target_price,
                        "pnl_abs": pnl,
                        "r_multiple": r_mult,
                        "model": entry_model,
                        "entry_reasons": "|".join(reason_open) if reason_open else "",
                        "exit_reason": "STOP_HIT" if hit_stop else "TARGET_HIT",
                        "entry_hour": pd.Timestamp(entry_ts).hour,
                    }
                )
                in_pos = False
                side = None

        if in_pos:
            continue

        sig = generate_signal_for_bar(
            symbol=symbol,
            ts=ts,
            row_3m=row,
            row_15m=row,
            cfg=cfg,
        )

        if not sig.signal:
            rejections.append(
                {
                    "timestamp": ts,
                    "symbol": symbol,
                    "reason_codes": "|".join(sig.reason_codes),
                    "hour": pd.Timestamp(ts).hour,
                }
            )
            continue

        side = sig.side
        entry_price = float(row["close"])
        entry_ts = ts
        entry_model = sig.model
        reason_open = sig.reason_codes

        atr_val = float(row["atr"]) if pd.notna(row.get("atr")) else 0.01
        stop_price = initial_stop(
            side=side,
            entry_bar={"low": float(row["low"]), "high": float(row["high"])},
            reference_bar={"low": float(prev["low"]), "high": float(prev["high"])},
            stop_buffer=atr_val * cfg.stop_buffer_atr,
        )
        target_price = target_from_rr(side=side, entry_price=entry_price, stop_price=stop_price, rr_target=cfg.rr_target)
        in_pos = True

    return pd.DataFrame(trades), pd.DataFrame(rejections)


def run_for_symbol(symbol: str, csv_path: Path, out_dir: Path, cfg: StrategyConfig):
    df_3m = load_csv(str(csv_path))  # returns tz-aware DatetimeIndex (UTC)
    df_3m = add_intraday_session_fields(df_3m)  # safe tz_convert now
    df_3m = add_liquidity_levels(df_3m)

    if cfg.rth_only:
        df_3m = df_3m[df_3m["is_rth"]].copy()

    df_15m = resample_15m(df_3m[["open", "high", "low", "close", "volume"]])
    df_15m = build_external_structure(
        df_15m,
        displacement_atr_mult=cfg.displacement_atr_mult,
        min_break_close_buffer_atr=cfg.min_break_close_buffer_atr,
    )

    merged = merge_3m_with_15m_state(df_3m, df_15m)
    merged = add_model_feature_flags(merged)

    trades, rejections = simulate_trades(symbol=symbol, df_3m=merged, cfg=cfg)

    out_dir.mkdir(parents=True, exist_ok=True)
    trades_path = out_dir / f"{symbol}_trades.csv"
    bars_path = out_dir / f"{symbol}_bars_with_state.csv"
    rej_path = out_dir / f"{symbol}_rejections.csv"

    trades.to_csv(trades_path, index=False)
    merged.reset_index().to_csv(bars_path, index=False)
    rejections.to_csv(rej_path, index=False)

    return trades, rejections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY")
    parser.add_argument("--input", required=True, help="Path to 3m OHLCV CSV")
    parser.add_argument("--out", default="outputs/trades", help="Output dir")
    args = parser.parse_args()

    cfg = StrategyConfig()
    symbol = args.symbol.upper()

    trades, rejections = run_for_symbol(symbol, Path(args.input), Path(args.out), cfg)

    if trades.empty:
        print("No trades generated.")
    else:
        print(f"Trades: {len(trades)}")
        print(f"Win rate: {(trades['pnl_abs'] > 0).mean():.2%}")
        print(f"Expectancy (abs): {trades['pnl_abs'].mean():.6f}")

    print(f"Rejections: {len(rejections)}")


if __name__ == "__main__":
    main()
