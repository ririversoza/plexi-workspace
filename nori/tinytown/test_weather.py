"""Tests for Nori's Tiny Town weather system (no Taro engine required)."""

from __future__ import annotations

import random
import unittest

from nori.tinytown import (
    CONDITIONS,
    SEASONS,
    STORM_MAX_TOTAL,
    STORM_MIN_GAP_DAYS,
    System,
    TEMP_MAX_C,
    TEMP_MIN_C,
    season_for_day,
)


class FakeTown:
    """Minimal Town stand-in matching the Tiny Town interface."""

    def __init__(self, seed: int = 42) -> None:
        self.day = 0
        self.rng = random.Random(seed)
        self.state: dict = {}
        self.events: list = []
        self._subscribers: list = []
        self._current_system = "weather"

    def emit(self, kind: str, **data) -> None:
        event = {"day": self.day, "system": self._current_system, "kind": kind, **data}
        self.events.append(event)
        for cb in self._subscribers:
            cb(event)

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)


def run_weather(seed: int = 42, days: int = 90):
    """Setup + `days` ticks; returns (final_state, daily_snapshots, system, town)."""
    town = FakeTown(seed=seed)
    system = System()
    system.setup(town)
    snapshots = []
    for day in range(1, days + 1):
        town.day = day
        system.tick(town)
        snapshots.append(dict(town.state["weather"]))
    return town.state["weather"], snapshots, system, town


class SeasonTests(unittest.TestCase):
    def test_season_boundaries(self):
        self.assertEqual(season_for_day(0), "spring")
        self.assertEqual(season_for_day(1), "spring")
        self.assertEqual(season_for_day(23), "spring")
        self.assertEqual(season_for_day(24), "summer")
        self.assertEqual(season_for_day(45), "summer")
        self.assertEqual(season_for_day(46), "autumn")
        self.assertEqual(season_for_day(68), "autumn")
        self.assertEqual(season_for_day(69), "winter")
        self.assertEqual(season_for_day(90), "winter")


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_daily_state(self):
        _, snaps_a, _, _ = run_weather(seed=42)
        _, snaps_b, _, _ = run_weather(seed=42)
        self.assertEqual(snaps_a, snaps_b)

    def test_different_seed_diverges(self):
        _, snaps_a, _, _ = run_weather(seed=42)
        _, snaps_b, _, _ = run_weather(seed=99)
        self.assertNotEqual(snaps_a, snaps_b)


class BoundsTests(unittest.TestCase):
    def test_condition_season_and_temp_bounds(self):
        _, snapshots, _, _ = run_weather(seed=42)
        for day, snap in enumerate(snapshots, start=1):
            self.assertIn(snap["condition"], CONDITIONS, msg=f"day {day}")
            self.assertIn(snap["season"], SEASONS, msg=f"day {day}")
            self.assertEqual(snap["season"], season_for_day(day), msg=f"day {day}")
            self.assertIsInstance(snap["temp_c"], float)
            self.assertGreaterEqual(snap["temp_c"], TEMP_MIN_C)
            self.assertLessEqual(snap["temp_c"], TEMP_MAX_C)
            if snap["condition"] == "snow":
                self.assertLessEqual(snap["temp_c"], 1.5)

    def test_storm_frequency_bounded(self):
        _, snapshots, system, _ = run_weather(seed=42)
        storm_days = [
            i for i, s in enumerate(snapshots, start=1) if s["condition"] == "storm"
        ]
        self.assertLessEqual(len(storm_days), STORM_MAX_TOTAL)
        self.assertEqual(system._storm_count, len(storm_days))
        for prev, curr in zip(storm_days, storm_days[1:]):
            gap = curr - prev
            self.assertGreaterEqual(
                gap,
                STORM_MIN_GAP_DAYS,
                msg=f"storms on day {prev} and {curr} too close",
            )

    def test_storm_bounds_hold_across_seeds(self):
        for seed in (0, 1, 7, 42, 123, 999):
            _, snapshots, _, _ = run_weather(seed=seed)
            storm_days = [
                i for i, s in enumerate(snapshots, start=1) if s["condition"] == "storm"
            ]
            self.assertLessEqual(len(storm_days), STORM_MAX_TOTAL, msg=f"seed {seed}")
            for prev, curr in zip(storm_days, storm_days[1:]):
                self.assertGreaterEqual(
                    curr - prev, STORM_MIN_GAP_DAYS, msg=f"seed {seed}"
                )


class SoloTests(unittest.TestCase):
    def test_runs_with_other_systems_missing(self):
        town = FakeTown(seed=42)
        system = System()
        system.setup(town)
        self.assertEqual(set(town.state.keys()), {"weather"})
        for day in range(1, 91):
            town.day = day
            system.tick(town)
        weather = town.state["weather"]
        self.assertIn(weather["condition"], CONDITIONS)
        self.assertIn(weather["season"], SEASONS)
        # No peer keys required or created.
        self.assertNotIn("economy", town.state)
        self.assertNotIn("traffic", town.state)
        self.assertNotIn("emergency", town.state)

    def test_setup_initial_state(self):
        town = FakeTown(seed=42)
        System().setup(town)
        self.assertEqual(
            town.state["weather"],
            {"condition": "sun", "temp_c": 12.0, "season": "spring"},
        )
        self.assertEqual(town.events[0]["kind"], "weather_init")


if __name__ == "__main__":
    unittest.main()
