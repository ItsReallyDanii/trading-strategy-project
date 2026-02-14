from pathlib import Path
import pandas as pd


def main():
    p = Path("outputs/reports/tradable_symbols_next.csv")
    if not p.exists():
        raise SystemExit("Missing outputs/reports/tradable_symbols_next.csv. Run promote_symbols first.")

    df = pd.read_csv(p)
    symbols = df["symbol"].dropna().tolist()

    if symbols != ["QQQ"]:
        raise SystemExit(f"Deploy scope violation. Expected ['QQQ'], got {symbols}")

    print("Deploy scope OK: QQQ only.")


if __name__ == "__main__":
    main()
