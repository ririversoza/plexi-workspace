"""Timeline data for the pixel town view — reuses Taro's export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from taro.tinytown.engine import DEFAULT_DAYS, DEFAULT_SEED, run_town
from taro.tinytown.run import (  # do not copy — import the shared schema helpers
    _SHOP_EXPORT_FIELDS,
    _count_events_by_kind,
    _load_systems,
    _snapshot_day,
    validate_export_path,
)

__all__ = [
    "DEFAULT_DAYS",
    "DEFAULT_SEED",
    "collect_timeline",
    "load_timeline",
    "validate_export_path",
    "_SHOP_EXPORT_FIELDS",
    "_count_events_by_kind",
    "_load_systems",
    "_snapshot_day",
]


def collect_timeline(
    *,
    seed: int = DEFAULT_SEED,
    days: int = DEFAULT_DAYS,
) -> Dict[str, Any]:
    """Run the town with log CSV disabled and return Taro's compact timeline."""
    systems = _load_systems(disable_log_files=True)
    daily: List[Dict[str, Any]] = []

    def on_day(town: Any) -> None:
        daily.append(_snapshot_day(town))

    town = run_town(systems, days=days, seed=seed, on_day=on_day)
    return {
        "seed": town.seed,
        "days": town.day,
        "systems": [system.name for system in systems],
        "daily": daily,
        "events_by_kind": _count_events_by_kind(town),
    }


def load_timeline(path: str) -> Dict[str, Any]:
    """Load a timeline JSON produced by ``taro.tinytown`` ``--export``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "daily" not in data:
        raise ValueError(f"not a timeline JSON: {path}")
    return data
