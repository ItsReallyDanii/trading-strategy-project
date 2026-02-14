from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

PROMOTION_MATRIX = Path("outputs/reports/promotion_matrix.csv")
COST_STRESS = Path("outputs/reports/cost_stress_summary.csv")
TRADABLE_NEXT = Path("outputs/reports/tradable_symbols_next.csv")
CHAMPION = Path("outputs/learning/champion.json")


def _load_pm(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "trades", "expectancy", "positive_folds", "mean_expectancy"])
    return pd.read_csv(path)


def _load_cost(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "cost_abs", "expectancy_post_cost"])
    c = pd.read_csv(path)

    if "expectancy_post_cost" not in c.columns:
        if "expectancy_post" in c.columns:
            c = c.rename(columns={"expectancy_post": "expectancy_post_cost"})
        else:
            c["expectancy_post_cost"] = 0.0

    if "cost_abs" not in c.columns:
        c["cost_abs"] = 0.05

    return c


def _ensure_required_cols(df: pd.DataFrame) -> pd.DataFrame:
    required_defaults = {
        "symbol": "",
        "trades": 0,
        "expectancy": 0.0,
        "positive_folds": 0,
        "mean_expectancy": 0.0,
        "exp_post_005": 0.0,
        "exp_post_010": 0.0,
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


def _build_tradable_scope(pm: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    pm = _ensure_required_cols(pm.copy())

    # use cost@0.05 as fallback for exp_post_005
    if not cost.empty:
        c05 = cost[cost["cost_abs"] == 0.05][["symbol", "expectancy_post_cost"]].copy()
        c05 = c05.rename(columns={"expectancy_post_cost": "exp_post_005_cost"})
        merged = pm.merge(c05, on="symbol", how="left")
    else:
        merged = pm.copy()
        merged["exp_post_005_cost"] = pd.NA

    merged["exp_post_005_effective"] = merged["exp_post_005"]
    fill_mask = merged["exp_post_005_effective"].isna() | (merged["exp_post_005_effective"] == 0)
    merged.loc[fill_mask, "exp_post_005_effective"] = merged.loc[fill_mask, "exp_post_005_cost"]

    merged["exp_post_005_effective"] = merged["exp_post_005_effective"].fillna(0.0)
    merged["trades"] = merged["trades"].fillna(0).astype(int)
    merged["positive_folds"] = merged["positive_folds"].fillna(0).astype(int)
    merged["expectancy"] = merged["expectancy"].fillna(0.0)

    # Keep your existing strict gates
    tradable = merged[
        (merged["trades"] >= 40)
        & (merged["positive_folds"] >= 3)
        & (merged["expectancy"] > 0)
        & (merged["exp_post_005_effective"] > 0)
    ][["symbol"]].drop_duplicates()

    return tradable


def _load_champion_symbol() -> str | None:
    if not CHAMPION.exists():
        return None
    try:
        payload = json.loads(CHAMPION.read_text())
        s = payload.get("symbol")
        if isinstance(s, str) and s.strip():
            return s.strip().upper()
    except Exception:
        return None
    return None


def main() -> None:
    pm = _load_pm(PROMOTION_MATRIX)
    cost = _load_cost(COST_STRESS)

    tradable = _build_tradable_scope(pm, cost)

    # deterministic fallback: never output empty scope if champion exists
    if tradable.empty:
        champion_symbol = _load_champion_symbol()
        if champion_symbol:
            tradable = pd.DataFrame({"symbol": [champion_symbol]})
            print(f"No symbols passed gates. Fallback to champion symbol: {champion_symbol}")
        else:
            print("No tradable symbols passed gates and no champion fallback available.")

    TRADABLE_NEXT.parent.mkdir(parents=True, exist_ok=True)
    tradable.to_csv(TRADABLE_NEXT, index=False)

    print(f"\nSaved: {TRADABLE_NEXT}")
    if not tradable.empty:
        print("Tradable scope:")
        print(tradable.to_string(index=False))


if __name__ == "__main__":
    main()
