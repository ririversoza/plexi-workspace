"""Contract tests that run without the shared engine."""

import copy
import random
import unittest

from bao.tinytown import System


class FakeTown:
    def __init__(self, state=None, seed=42):
        self.day = 0
        self.rng = random.Random(seed)
        self.state = copy.deepcopy(state or {})
        self.events = []

    def emit(self, kind, **data):
        self.events.append(dict(day=self.day, system="traffic", kind=kind, **data))


def simulate(state=None):
    town = FakeTown(state)
    system = System()
    system.setup(town)
    history = []
    for town.day in range(1, 91):
        system.tick(town)
        history.append(copy.deepcopy(town.state["traffic"]))
    return town, history


class TrafficTests(unittest.TestCase):
    def test_determinism_for_full_run(self):
        state = {"economy": {"employed": 700}, "weather": {"condition": "rain"}}
        first, first_history = simulate(state)
        second, second_history = simulate(state)
        self.assertEqual(first_history, second_history)
        self.assertEqual(first.events, second.events)
        self.assertEqual(first.rng.getstate(), second.rng.getstate())
        self.assertGreater(len({row["commuters"] for row in first_history}), 1)

    def test_bounds_across_weather_and_employment(self):
        for condition in ("sun", "cloud", "rain", "snow", "storm"):
            for employed in (-10, 0, 1, 100, 1000, 10000):
                with self.subTest(condition=condition, employed=employed):
                    _, history = simulate({"economy": {"employed": employed},
                                           "weather": {"condition": condition}})
                    for row in history:
                        self.assertIsInstance(row["commuters"], int)
                        self.assertIsInstance(row["accidents_today"], int)
                        self.assertIsInstance(row["congestion"], float)
                        self.assertTrue(0 <= row["commuters"] <= max(0, employed))
                        self.assertTrue(0.0 <= row["congestion"] <= 1.0)
                        self.assertTrue(0 <= row["accidents_today"] <= row["commuters"])

    def test_runs_alone(self):
        town, history = simulate()
        self.assertEqual(set(town.state), {"traffic"})
        self.assertEqual(len(town.events), 90)
        self.assertTrue(all(row == dict(commuters=0, congestion=0.0,
                                       accidents_today=0) for row in history))

    def test_missing_keys_and_unknown_weather_defaults(self):
        for state in ({"economy": {}, "weather": {}}, {"weather": {"condition": "snow"}}):
            _, history = simulate(state)
            self.assertTrue(all(row["commuters"] == 0 for row in history))
        _, sunny = simulate({"economy": {"employed": 100}})
        for weather in ({}, {"condition": "unknown"}, {"condition": "sun"}):
            _, actual = simulate({"economy": {"employed": 100}, "weather": weather})
            self.assertEqual(actual, sunny)

    def test_setup_preserves_upstream_and_rng(self):
        town = FakeTown({"economy": {"employed": 100}, "weather": {"condition": "rain"}})
        before = copy.deepcopy(town.state)
        rng_before = town.rng.getstate()
        System().setup(town)
        self.assertEqual(town.rng.getstate(), rng_before)
        self.assertEqual(town.events, [])
        System().tick(town)
        for key, value in before.items():
            self.assertEqual(town.state[key], value)
        self.assertEqual(set(town.state), {"traffic", "economy", "weather"})

    def test_current_inputs_and_daily_reset(self):
        town = FakeTown({"economy": {"employed": 10000}})
        system = System()
        system.setup(town)
        town.day = 1
        system.tick(town)
        self.assertEqual(town.state["traffic"]["congestion"], 1.0)
        self.assertGreater(town.state["traffic"]["accidents_today"], 0)
        town.state["economy"]["employed"] = 0
        town.day = 2
        system.tick(town)
        self.assertEqual(town.state["traffic"], dict(commuters=0, congestion=0.0, accidents_today=0))
        self.assertEqual(town.events[-1], dict(day=2, system="traffic", kind="traffic_daily",
                                             commuters=0, congestion=0.0, accidents_today=0))

    def test_adverse_weather_reduces_capacity(self):
        results = []
        for condition in ("sun", "rain", "snow", "storm"):
            town = FakeTown({"economy": {"employed": 100}, "weather": {"condition": condition}})
            System().setup(town)
            System().tick(town)
            results.append(town.state["traffic"])
        self.assertEqual(len({row["commuters"] for row in results}), 1)
        self.assertEqual(sorted(row["congestion"] for row in results),
                         [row["congestion"] for row in results])
        self.assertLess(results[0]["congestion"], results[-1]["congestion"])


if __name__ == "__main__":
    unittest.main()
