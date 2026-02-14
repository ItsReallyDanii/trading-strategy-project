import pandas as pd
from pathlib import Path


def main():
    p = Path("outputs/universe/universe_summary.csv")
    if not p.exists():
        raise FileNotFoundError("Missing outputs/universe/universe_summary.csv")

    df = pd.read_csv(p)

    # simple, explicit gate: positive expectancy and at least 50 trades
    tradable = df[(df["expectancy"] > 0) & (df["trades"] >= 50)].copy()
    tradable = tradable.sort_values("expectancy", ascending=False)

    out = Path("outputs/universe/tradable_symbols.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    tradable.to_csv(out, index=False)

    print("Tradable symbols:")
    if tradable.empty:
        print("(none)")
    else:
        print(tradable[["symbol", "trades", "win_rate", "expectancy", "avg_r"]].to_string(index=False))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
