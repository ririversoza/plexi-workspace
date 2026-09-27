"""Tiny Town engine: shared Town world and the daily tick loop.

Contract: juniper/TINYTOWN.md — all systems share one seeded RNG, emit through
Town, and tick in a fixed order. Missing systems are simply skipped.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterable, Optional, Protocol

DEFAULT_SEED = 42
DEFAULT_DAYS = 90

# Daily tick order from the contract. "log" sets up (and may subscribe) but does not tick.
TICK_ORDER = ("weather", "economy", "traffic", "emergency")

# Catalog of packages that may export System. Import failures mean "not installed".
SYSTEM_MODULES = {
    "weather": "nori.tinytown",
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


def run_town(
    systems: Iterable[SystemProtocol],
    *,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    on_day: Optional[Callable[[Town], None]] = None,
) -> Town:
    """Set up every system once, then run ``days`` ticks in ``TICK_ORDER``.

    Systems whose ``name`` is not in ``TICK_ORDER`` still receive ``setup``
    (e.g. Mochi's log) but are skipped during the daily loop. Unknown or
    missing names never crash the run.
    """
    installed = list(systems)
    by_name = {system.name: system for system in installed}
    town = Town(seed=seed)

    for system in installed:
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
