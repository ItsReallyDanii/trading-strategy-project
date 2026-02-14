from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from src.rules_engine.parameters import StrategyConfig


DEFAULT_CHAMPION_PATH = Path("outputs/learning/champion.json")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def strategy_config_to_dict(cfg: StrategyConfig) -> Dict[str, Any]:
    return asdict(cfg)


def dict_to_strategy_config(d: Dict[str, Any]) -> StrategyConfig:
    return StrategyConfig(**d)


def load_champion(path: Path = DEFAULT_CHAMPION_PATH) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_champion(
    symbol: str,
    config: StrategyConfig,
    metrics: Dict[str, Any],
    path: Path = DEFAULT_CHAMPION_PATH,
) -> None:
    _ensure_parent(path)
    payload = {
        "symbol": symbol,
        "config": strategy_config_to_dict(config),
        "metrics": metrics,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def bootstrap_champion_if_missing(
    symbol: str = "QQQ",
    path: Path = DEFAULT_CHAMPION_PATH,
) -> Dict[str, Any]:
    existing = load_champion(path)
    if existing is not None:
        return existing

    cfg = StrategyConfig()
    # Keep current project assumptions explicit:
    cfg.allowed_symbols = (symbol,)
    payload = {
        "symbol": symbol,
        "config": strategy_config_to_dict(cfg),
        "metrics": {
            "trades": 0,
            "expectancy": 0.0,
            "exp_post_005": 0.0,
            "exp_post_010": 0.0,
            "positive_folds": 0,
            "mean_expectancy": 0.0,
            "min_expectancy": 0.0,
            "note": "bootstrapped",
        },
    }
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    return payload
