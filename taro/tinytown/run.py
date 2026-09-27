"""Load installed Tiny Town systems and run a 90-day simulation.

Works with zero systems installed: still prints 90 daily lines and a final report.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, List

# Allow `python3 taro/tinytown/run.py` from the repo root.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from taro.tinytown.engine import (  # noqa: E402
    DEFAULT_DAYS,
    DEFAULT_SEED,
    SYSTEM_MODULES,
    TICK_ORDER,
    Town,
    run_town,
)

# Re-export for callers that import constants from the runner module.
__all__ = [
    "daily_summary",
    "final_report",
    "load_systems",
    "main",
]


def load_systems() -> List[Any]:
    """Import every catalogued system package; skip anything not installed."""
    loaded: List[Any] = []
    for module_path in SYSTEM_MODULES.values():
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        system_cls = getattr(module, "System", None)
        if system_cls is None:
            continue
        loaded.append(system_cls())
    return loaded


def daily_summary(town: Town) -> str:
    """One-line snapshot of whatever state is present today."""
    parts: List[str] = [f"Day {town.day}"]
    weather = town.state.get("weather")
    if weather is not None:
        parts.append(
            f"weather={weather.get('condition')} {weather.get('temp_c')}C/{weather.get('season')}"
        )
    economy = town.state.get("economy")
    if economy is not None:
        parts.append(
            f"pop={economy.get('population')} employed={economy.get('employed')} "
            f"treasury={economy.get('treasury')} shops={economy.get('shops_open')}"
        )
    traffic = town.state.get("traffic")
    if traffic is not None:
        parts.append(
            f"commuters={traffic.get('commuters')} congestion={traffic.get('congestion')} "
            f"accidents={traffic.get('accidents_today')}"
        )
    emergency = town.state.get("emergency")
    if emergency is not None:
        parts.append(
            f"incidents={emergency.get('incidents_today')} responded={emergency.get('responded')} "
            f"open={emergency.get('open_incidents')}"
        )
    if len(parts) == 1:
        parts.append("(no systems)")
    today_events = sum(1 for event in town.events if event.get("day") == town.day)
    parts.append(f"events={today_events}")
    return " | ".join(parts)


def final_report(town: Town, systems: List[Any]) -> str:
    """Short end-of-run report: who ran, how many events, final state."""
    names = [system.name for system in systems]
    lines = [
        "=== Tiny Town final report ===",
        f"days={town.day} seed={town.seed} systems={names or '(none)'}",
        f"total_events={len(town.events)}",
    ]
    for name in list(TICK_ORDER) + ["log"]:
        if name in town.state:
            lines.append(f"{name}: {town.state[name]}")
    return "\n".join(lines)


def main(days: int = DEFAULT_DAYS, seed: int = DEFAULT_SEED) -> Town:
    systems = load_systems()
    town = run_town(systems, days=days, seed=seed, on_day=lambda t: print(daily_summary(t)))
    print(final_report(town, systems))
    return town


if __name__ == "__main__":
    main()
