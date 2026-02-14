from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("\n$", " ".join(cmd))
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        raise SystemExit(f"Command failed ({res.returncode}): {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="QQQ")
    parser.add_argument("--input", default="data/raw/QQQ_3m.csv")
    parser.add_argument("--leaderboard", default="outputs/learning/challenger_leaderboard.csv")
    parser.add_argument("--champion", default="outputs/learning/champion.json")
    args = parser.parse_args()

    py = sys.executable

    run([py, "-m", "src.learning.challenger_search",
         "--symbol", args.symbol,
         "--input", args.input,
         "--out", args.leaderboard])

    run([py, "-m", "src.learning.promote_champion",
         "--symbol", args.symbol,
         "--leaderboard", args.leaderboard,
         "--champion", args.champion])

    print("\nDaily learning cycle completed.")


if __name__ == "__main__":
    main()
