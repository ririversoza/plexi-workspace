"""Contract tests that run without the engine or any sibling system."""

import copy
import math
import random
import unittest

from kiwi.tinytown import System


class Town:
    def __init__(self, state=None):
        self.day = 0
        self.rng = random.Random(42)
        self.state = {} if state is None else state
        self.events = []

    def emit(self, kind, **data):
        self.events.append(dict(day=self.day, system="emergency", kind=kind, **data))


def run(state=None):
    town = Town(copy.deepcopy(state))
    system = System()
    system.setup(town)
    history = []
    for day in range(1, 91):
        town.day = day
        system.tick(town)
        history.append(town.state["emergency"].copy())
    return town, history


class EmergencyTests(unittest.TestCase):
    def test_determinism_and_running_alone(self):
        for state in (None, {"weather": {"condition": "storm"},
                             "traffic": {"accidents_today": 12}}):
            first, history = run(state)
            second, repeated = run(state)
            self.assertEqual(history, repeated)
            self.assertEqual(first.events, second.events)
            self.assertEqual(len(first.events), 90)

    def test_bounds_and_conservation(self):
        for condition in ("sun", "cloud", "rain", "snow", "storm"):
            for accidents in (0, 1, 8, 1000):
                town, history = run({"weather": {"condition": condition},
                                     "traffic": {"accidents_today": accidents}})
                previous = 0
                for state, event in zip(history, town.events):
                    self.assertEqual(set(state), {"incidents_today", "responded",
                                                  "avg_response_min", "open_incidents"})
                    for key in ("incidents_today", "responded", "open_incidents"):
                        self.assertIs(type(state[key]), int)
                        self.assertGreaterEqual(state[key], 0)
                    self.assertLessEqual(state["incidents_today"], 1007)
                    self.assertLessEqual(state["responded"], state["incidents_today"])
                    served = state["responded"] + event["backlog_responded"]
                    self.assertEqual(served, min(8, previous + state["incidents_today"]))
                    self.assertEqual(state["open_incidents"], previous + state["incidents_today"] - served)
                    self.assertEqual(state["incidents_today"], event["police_calls"] + event["fire_calls"] + accidents)
                    response = state["avg_response_min"]
                    self.assertIs(type(response), float)
                    self.assertTrue(math.isfinite(response))
                    self.assertGreaterEqual(response, 4.0 if served else 0.0)
                    self.assertLessEqual(response, 18.0)
                    self.assertLessEqual(state["open_incidents"], 89910)
                    previous = state["open_incidents"]

    def test_bad_inputs_use_defaults(self):
        baseline, history = run()
        bad = [None, True, False, -1, 1001, 10**100, 1.0,
               float("nan"), float("inf"), "1", [], {}, object()]
        class CustomInt(int):
            pass
        class CustomString(str):
            pass
        class CustomDict(dict):
            def get(self, *args):
                raise AssertionError("untrusted mapping called")
        for value in bad + [CustomInt(2)]:
            with self.subTest(accidents=repr(value)):
                town, actual = run({"traffic": {"accidents_today": value}})
                self.assertEqual(actual, history)
                self.assertEqual(town.events, baseline.events)
        for value in bad + ["SUN", "unknown", CustomString("storm")]:
            with self.subTest(condition=repr(value)):
                _, actual = run({"weather": {"condition": value}})
                self.assertEqual(actual, history)
        for value in bad + [CustomDict(condition="storm", accidents_today=1000)]:
            _, actual = run({"weather": value, "traffic": value})
            self.assertEqual(actual, history)

    def test_backlog_first_and_event_accounting(self):
        town = Town({"traffic": {"accidents_today": 20}})
        system = System()
        system.setup(town)
        system.tick(town)
        previous = town.state["emergency"]["open_incidents"]
        self.assertGreaterEqual(previous, 12)
        town.state["traffic"]["accidents_today"] = 0
        system.tick(town)
        self.assertEqual(town.state["emergency"]["responded"], 0)
        self.assertEqual(town.events[-1]["backlog_responded"], 8)
        for _ in range(10):
            system.tick(town)
        self.assertEqual(town.state["emergency"]["open_incidents"], 0)

    def test_inputs_unchanged_and_setup_resets(self):
        inputs = {"weather": {"condition": "storm", "temp_c": []},
                  "traffic": {"accidents_today": 1000}, "other": [1, 2]}
        town = Town(copy.deepcopy(inputs))
        system = System()
        system.setup(town)
        system.tick(town)
        self.assertEqual({k: v for k, v in town.state.items() if k != "emergency"}, inputs)
        system.setup(town)
        self.assertEqual(town.state["emergency"], dict(incidents_today=0, responded=0,
                                                     avg_response_min=0.0, open_incidents=0))
        town.state.pop("traffic")
        town.state.pop("weather")
        system.tick(town)
        self.assertEqual(town.state["emergency"]["open_incidents"], 0)

    def test_rng_draw_order_and_no_calls(self):
        town = Town()
        system = System()
        system.setup(town)
        expected = random.Random(42)
        police = expected.randint(0, 3)
        fires = expected.randint(0, 1)
        expected.uniform(4.0, 8.0)
        system.tick(town)
        self.assertEqual(town.rng.getstate(), expected.getstate())
        self.assertEqual(town.state["emergency"]["incidents_today"], police + fires)
        self.assertEqual(police + fires, 0)
        self.assertEqual(town.state["emergency"]["avg_response_min"], 0.0)


if __name__ == "__main__":
    unittest.main()
