"""Tiny Town engine: shared Town world and the daily tick loop.

Contract: juniper/TINYTOWN.md — all systems share one seeded RNG, emit through
Town, and tick in a fixed order. Missing systems are simply skipped.

Phase 2 adds businesses and residents to the catalog and tick order.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterable, Optional, Protocol

DEFAULT_SEED = 42
DEFAULT_DAYS = 90

# Daily tick order (Phase 2). "log" sets up (and may subscribe) but does not tick.
TICK_ORDER = (
    "weather",
    "businesses",
    "residents",
    "economy",
    "traffic",
    "emergency",
)

# Catalog of packages that may export System. Import failures mean "not installed".
SYSTEM_MODULES = {
    "weather": "nori.tinytown",
    "businesses": "nori.shops",
    "residents": "kiwi.townfolk",
    "economy": "sora.tinytown",
    "traffic": "bao.tinytown",
    "emergency": "kiwi.tinytown",
    "log": "mochi.tinytown",
}

EventDict = dict[str, Any]
EventCallback = Callable[[EventDict], None]


class SystemProtocol(Protocol):
    """Duck-typed system: name + setup + tick."""

    name: str

    def setup(self, town: "Town") -> None: ...

    def tick(self, town: "Town") -> None: ...


class Town:
    """Shared simulation world: day clock, RNG, per-system state, and event bus."""

    def __init__(self, seed: int = DEFAULT_SEED) -> None:
        self.day = 0
        self.seed = seed
        self.rng = random.Random(seed)
        self.state: dict[str, dict[str, Any]] = {}
        self.events: list[EventDict] = []
        self._subscribers: list[EventCallback] = []
        self._current_system: Optional[str] = None

    def emit(self, kind: str, **data: Any) -> EventDict:
        """Record an event. Fills ``day`` and ``system`` (the system currently ticking)."""
        event: EventDict = {
            "day": self.day,
            "system": self._current_system,
            "kind": kind,
            **data,
        }
        self.events.append(event)
        for callback in list(self._subscribers):
            callback(event)
        return event

    def subscribe(self, callback: EventCallback) -> None:
        """Register ``callback(event_dict)`` for every future ``emit``."""
        self._subscribers.append(callback)


def _setup_order(installed_names: Iterable[str]) -> list[str]:
    """Setup follows TICK_ORDER, then any leftover systems (e.g. log)."""
    names = list(installed_names)
    present = set(names)
    ordered: list[str] = [name for name in TICK_ORDER if name in present]
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return ordered


def run_town(
    systems: Iterable[SystemProtocol],
    *,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    on_day: Optional[Callable[[Town], None]] = None,
) -> Town:
    """Set up every system once, then run ``days`` ticks in ``TICK_ORDER``.

    Setup order matches ``TICK_ORDER``, then any remaining systems (e.g. Mochi's
    log). Systems whose ``name`` is not in ``TICK_ORDER`` still receive ``setup``
    but are skipped during the daily loop. Unknown or missing names never crash.
    """
    installed = list(systems)
    by_name = {system.name: system for system in installed}
    town = Town(seed=seed)

    for name in _setup_order(system.name for system in installed):
        system = by_name[name]
        town._current_system = system.name
        system.setup(town)
    town._current_system = None

    for day in range(1, days + 1):
        town.day = day
        for name in TICK_ORDER:
            system = by_name.get(name)
            if system is None:
                continue
            town._current_system = system.name
            system.tick(town)
        town._current_system = None
        if on_day is not None:
            on_day(town)

    return town
