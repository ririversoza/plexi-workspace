"""Tiny Town weather system (Nori).

Writes town.state["weather"] with condition, temp_c, and season.
Uses only town.rng; never creates its own Random.
"""

from __future__ import annotations

# --- contract constants -------------------------------------------------

CONDITIONS = ("sun", "cloud", "rain", "snow", "storm")
SEASONS = ("spring", "summer", "autumn", "winter")

# 90-day calendar: four nearly equal seasons (spring first).
# spring 1–23, summer 24–45, autumn 46–68, winter 69–90
_SEASON_ENDS = (23, 45, 68, 90)

# Temperate mid-latitude climate (°C). mean ± spread before condition delta.
SEASON_CLIMATE = {
    "spring": {"mean": 12.0, "spread": 5.0},
    "summer": {"mean": 24.0, "spread": 6.0},
    "autumn": {"mean": 14.0, "spread": 5.0},
    "winter": {"mean": 2.0, "spread": 6.0},
}

# Relative weights per season. Storm weight is capped at 0.10.
SEASON_WEIGHTS = {
    "spring": (0.32, 0.30, 0.26, 0.04, 0.08),  # sun cloud rain snow storm
    "summer": (0.42, 0.28, 0.20, 0.00, 0.10),
    "autumn": (0.28, 0.32, 0.26, 0.06, 0.08),
    "winter": (0.22, 0.28, 0.12, 0.30, 0.08),
}

# Condition offsets applied after the seasonal base draw.
CONDITION_DELTA = {
    "sun": 3.0,
    "cloud": 0.0,
    "rain": -2.0,
    "storm": -4.0,
    "snow": -6.0,
}

TEMP_MIN_C = -15.0
TEMP_MAX_C = 38.0
SNOW_MAX_C = 1.5  # wet snow allowed slightly above freezing

# Storm bounds: min calendar gap between storm days, and hard cap over 90 days.
STORM_MIN_GAP_DAYS = 3  # next storm allowed when day - last_storm_day >= 3
STORM_MAX_TOTAL = 12


def season_for_day(day: int) -> str:
    """Map town.day (1..90) to a season. Day 0 (setup) → spring."""
    if day <= 0:
        return "spring"
    for season, end in zip(SEASONS, _SEASON_ENDS):
        if day <= end:
            return season
    return "winter"


class System:
    """Daily weather for Tiny Town."""

    name = "weather"

    def __init__(self) -> None:
        # Instance counters (not part of the public state contract).
        self._last_storm_day: int | None = None
        self._storm_count = 0

    def setup(self, town) -> None:
        self._last_storm_day = None
        self._storm_count = 0
        town.state[self.name] = {
            "condition": "sun",
            "temp_c": 12.0,
            "season": "spring",
        }
        town.emit(
            "weather_init",
            condition="sun",
            temp_c=12.0,
            season="spring",
        )

    def tick(self, town) -> None:
        season = season_for_day(town.day)
        condition = self._pick_condition(town, season)
        temp_c = self._temp_for(town, season, condition)
        town.state[self.name] = {
            "condition": condition,
            "temp_c": temp_c,
            "season": season,
        }
        town.emit(
            "daily",
            condition=condition,
            temp_c=temp_c,
            season=season,
        )

    def _pick_condition(self, town, season: str) -> str:
        weights = list(SEASON_WEIGHTS[season])
        storm_blocked = self._storm_count >= STORM_MAX_TOTAL
        if self._last_storm_day is not None:
            if town.day - self._last_storm_day < STORM_MIN_GAP_DAYS:
                storm_blocked = True
        if storm_blocked:
            weights[CONDITIONS.index("storm")] = 0.0

        condition = town.rng.choices(CONDITIONS, weights=weights, k=1)[0]

        if condition == "storm":
            self._storm_count += 1
            self._last_storm_day = town.day
        return condition

    def _temp_for(self, town, season: str, condition: str) -> float:
        climate = SEASON_CLIMATE[season]
        base = climate["mean"] + town.rng.uniform(
            -climate["spread"], climate["spread"]
        )
        temp = base + CONDITION_DELTA[condition]
        if condition == "snow":
            temp = min(temp, SNOW_MAX_C)
        temp = max(TEMP_MIN_C, min(TEMP_MAX_C, temp))
        return round(temp, 1)


__all__ = [
    "System",
    "CONDITIONS",
    "SEASONS",
    "season_for_day",
    "STORM_MIN_GAP_DAYS",
    "STORM_MAX_TOTAL",
    "TEMP_MIN_C",
    "TEMP_MAX_C",
]
