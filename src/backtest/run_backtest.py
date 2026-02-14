import argparse
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from src.rules_engine.parameters import StrategyConfig
from src.features.structure_15m import build_external_structure
from src.features.liquidity_map import add_intraday_session_fields, add_liquidity_levels
from src.rules_engine.signals import generate_signal_for_bar
from src.rules_engine.risk import initial_stop, target_from_rr


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"{path} missing 'timestamp' column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    needed = {"open", "high", "low", "close", "volume"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    return df


def resample_15m(df_3m: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    out = df_3m.resample("15min", label="right", closed="right").agg(agg).dropna()
    return out


def merge_3m_with_15m_state(df_3m: pd.DataFrame, df_15m_state: pd.DataFrame) -> pd.DataFrame:
    cols = ["external_bias", "protected_swing_high", "protected_swing_low", "atr", "bos_flag", "choch_flag"]
    state = df_15m_state[cols].copy()
    # forward fill 15m state onto 3m bars
    merged = pd.merge_asof(
        df_3m.reset_index().sort_values("timestamp"),
        state.reset_index().sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    ).set_index("timestamp")
    return merged


def simulate_trades(symbol: str, df_3m: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    trades: List[Dict[str, Any]] = []
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

        # exit logic first
        if in_pos:
            hit_stop = False
            hit_target = False

            if side == "long":
                if row["low"] <= stop_price:
                    hit_stop = True
                elif row["high"] >= target_price:
                    hit_target = True
            else:
                if row["high"] >= stop_price:
                    hit_stop = True
                elif row["low"] <= target_price:
                    hit_target = True

            if hit_stop or hit_target:
                exit_price = stop_price if hit_stop else target_price
                pnl = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
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
                        "model": entry_model,
                        "entry_reasons": "|".join(reason_open),
                        "exit_reason": "STOP_HIT" if hit_stop else "TARGET_HIT",
                    }
                )
                in_pos = False
                side = None

        if in_pos:
            continue

        # signal generation
        sig = generate_signal_for_bar(
            symbol=symbol,
            ts=ts,
            row_3m=row,
            row_15m=row,  # row already has 15m state columns merged in
            cfg=cfg,
        )

        if not sig.signal:
            continue

        side = sig.side
        entry_price = float(row["close"])
        entry_ts = ts
        entry_model = sig.model
        reason_open = sig.reason_codes

        stop_price = initial_stop(
            side=side,
            entry_bar={"low": float(row["low"]), "high": float(row["high"])},
            reference_bar={"low": float(prev["low"]), "high": float(prev["high"])},
            stop_buffer=float(row["atr"]) * cfg.stop_buffer_atr if pd.notna(row["atr"]) else 0.01,
        )
        target_price = target_from_rr(
            side=side,
            entry_price=entry_price,
            stop_price=stop_price,
            rr_target=cfg.rr_target,
        )
        in_pos = True

    return pd.DataFrame(trades)


def run_for_symbol(symbol: str, csv_path: Path, out_dir: Path, cfg: StrategyConfig) -> pd.DataFrame:
    df_3m = load_csv(csv_path)
    df_3m = add_intraday_session_fields(df_3m)
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

    # placeholder model features; replace with real feature pipeline
    merged["swept_level"] = merged["prev_day_low"]  # example placeholder
    merged["failed_choch_confirmed"] = False
    merged["pullback_respected"] = True
    merged["internal_sweep_reclaim"] = True

    trades = simulate_trades(symbol=symbol, df_3m=merged, cfg=cfg)

    out_dir.mkdir(parents=True, exist_ok=True)
    trades_path = out_dir / f"{symbol}_trades.csv"
    merged_path = out_dir / f"{symbol}_bars_with_state.csv"
    trades.to_csv(trades_path, index=False)
    merged.reset_index().to_csv(merged_path, index=False)

    return trades


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY")
    parser.add_argument("--input", required=True, help="Path to 3m OHLCV CSV")
    parser.add_argument("--out", default="outputs/trades", help="Output dir")
    args = parser.parse_args()

    cfg = StrategyConfig()
    symbol = args.symbol.upper()
    trades = run_for_symbol(
        symbol=symbol,
        csv_path=Path(args.input),
        out_dir=Path(args.out),
        cfg=cfg,
    )

    if trades.empty:
        print("No trades generated.")
    else:
        win_rate = (trades["pnl_abs"] > 0).mean()
        expectancy = trades["pnl_abs"].mean()
        print(f"Trades: {len(trades)}")
        print(f"Win rate: {win_rate:.2%}")
        print(f"Expectancy (abs): {expectancy:.4f}")


if __name__ == "__main__":
    main()

