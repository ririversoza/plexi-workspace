"""Street allocation and frozen-main RNG compatibility tests."""

import copy
import importlib
from pathlib import Path
import runpy
import unittest

from kiwi.tinytown import System, _STREETS, _street_breakdown
from kiwi.tinytown.test_emergency import Town

Baseline = runpy.run_path(str(Path(__file__).parent / "fixtures" / "phase1_emergency.py"))["System"]


def residents(counts=(30, 30, 30, 30)):
    return {"people": [{"street": street} for street, count in zip(_STREETS, counts)
                       for _ in range(count)]}


class StreetTests(unittest.TestCase):
    def test_weighting_rounding_rotation_and_zero(self):
        town = Town({"residents": residents((60, 30, 20, 10))})
        town.day = 1
        self.assertEqual(_street_breakdown(town, 12)["incidents_by_street"],
                         dict(zip(_STREETS, (6, 3, 2, 1))))
        town.state["residents"] = residents()
        for day in range(1, 9):
            town.day = day
            result = _street_breakdown(town, 1)
            self.assertEqual(result["busiest_street"], _STREETS[(day - 1) % 4])
            self.assertEqual(sum(result["incidents_by_street"].values()), 1)
        result = _street_breakdown(town, 0)
        self.assertEqual(result["incidents_by_street"], dict.fromkeys(_STREETS, 0))
        self.assertIsNone(result["busiest_street"])

    def test_bounds_conservation_and_read_only_inputs(self):
        for population in ((1, 0, 0, 0), (0, 1, 1, 0), (1, 2, 3, 114)):
            town = Town({"residents": residents(population)})
            before = copy.deepcopy(town.state)
            rng = town.rng.getstate()
            for day in range(1, 5):
                town.day = day
                for incidents in range(1008):
                    result = _street_breakdown(town, incidents)
                    counts = result["incidents_by_street"]
                    self.assertEqual(set(counts), set(_STREETS))
                    self.assertEqual(sum(counts.values()), incidents)
                    for street, count in zip(_STREETS, population):
                        self.assertIs(type(counts[street]), int)
                        self.assertGreaterEqual(counts[street], 0)
                        if count == 0:
                            self.assertEqual(counts[street], 0)
                    if incidents:
                        self.assertEqual(counts[result["busiest_street"]], max(counts.values()))
            self.assertEqual(town.state, before)
            self.assertEqual(town.rng.getstate(), rng)

    def test_invalid_and_removed_residents_fall_back_to_phase1(self):
        bad = (None, [], {}, True, {"people": None}, {"people": []},
               {"people": [None, [], {"street": []}, {"street": "unknown"}]})
        for value in bad:
            town = Town({"residents": value})
            self.assertEqual(_street_breakdown(town, 3), {})
        town = Town({"residents": residents()})
        system = System()
        system.setup(town)
        system.tick(town)
        self.assertIn("incidents_by_street", town.state["emergency"])
        town.state.pop("residents")
        system.tick(town)
        self.assertEqual(set(town.state["emergency"]),
                         {"incidents_today", "responded", "avg_response_min", "open_incidents"})

    def test_90_day_rng_and_existing_state_events_match_main(self):
        before, after = Town(), Town()
        old, new = Baseline(), System()
        old.setup(before)
        new.setup(after)
        for day in range(1, 91):
            for town, system in ((before, old), (after, new)):
                town.day = day
                town.state["residents"] = residents((day, 30, 20, 10))
                town.state["traffic"] = {"accidents_today": day % 11}
                town.state["weather"] = {"condition": ("sun", "rain", "storm")[day % 3]}
                system.tick(town)
            actual = dict(after.state["emergency"])
            self.assertEqual(sum(actual.pop("incidents_by_street").values()), actual["incidents_today"])
            actual.pop("busiest_street")
            self.assertEqual(actual, before.state["emergency"])
            self.assertEqual(after.events, before.events)
            self.assertEqual(after.rng.getstate(), before.rng.getstate())

    def test_full_town_final_rng_unchanged_vs_main(self):
        try:
            engine = importlib.import_module("taro.tinytown.engine")
            runner = importlib.import_module("taro.tinytown.run")
        except ImportError as error:
            self.skipTest(f"Optional engine unavailable: {error}")

        def run(old):
            systems = runner.load_systems()
            for index, system in enumerate(systems):
                if system.name == "log":
                    system.csv_path = None
                if old and system.name == "emergency":
                    systems[index] = Baseline()
            history = []

            def snapshot(town):
                state = copy.deepcopy(town.state)
                emergency = state.get("emergency", {})
                emergency.pop("incidents_by_street", None)
                emergency.pop("busiest_street", None)
                history.append(state)

            town = engine.run_town(systems, seed=42, days=90, on_day=snapshot)
            return town, history

        before, old_history = run(True)
        after, new_history = run(False)
        self.assertEqual(new_history, old_history)
        self.assertEqual(after.events, before.events)
        self.assertEqual(after.rng.getstate(), before.rng.getstate())


if __name__ == "__main__":
    unittest.main()
