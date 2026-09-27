"""Mood contract and byte-for-byte comparison against the frozen Phase 2 system."""

import copy
import json
from pathlib import Path
import runpy
import unittest

from kiwi.townfolk import System, _update_mood
from kiwi.townfolk.test_residents import Town, businesses

Phase2System = runpy.run_path(str(Path(__file__).parent / "fixtures" / "phase2_residents.py"))["System"]


def economic_bytes(state):
    state = copy.deepcopy(state)
    state.pop("avg_mood", None)
    state.pop("mood_bands", None)
    for person in state["people"]:
        person.pop("mood", None)
    return json.dumps(state, separators=(",", ":")).encode("utf-8")


class MoodTests(unittest.TestCase):
    def test_economy_bytes_and_rng_identical_to_phase2(self):
        for seed in (1, 42, 99):
            for installed in (False, True):
                before, after = Town(seed), Town(seed)
                old, new = Phase2System(), System()
                old.setup(before)
                new.setup(after)
                for day in range(91):
                    with self.subTest(seed=seed, installed=installed, day=day):
                        self.assertEqual(economic_bytes(before.state["residents"]),
                                         economic_bytes(after.state["residents"]))
                        self.assertEqual(before.rng.getstate(), after.rng.getstate())
                    if day == 90:
                        break
                    inputs = {"weather": {"condition": ("sun", "cloud", "rain", "snow", "storm", None, ["bad"])[day % 7]}}
                    if installed:
                        inputs["businesses"] = businesses(capacity=day % 13, price=100 + day * 71)
                        inputs["businesses"]["wages_paid"] = {1: 725, 2: day * 5}
                    for town, system in ((before, old), (after, new)):
                        town.state.update(copy.deepcopy(inputs))
                        town.day = day + 1
                        system.tick(town)

    def test_bounds_bands_and_integer_average(self):
        people = [{"id": index, "wallet_cents": wallet, "job": job}
                  for index, (wallet, job) in enumerate(
                      (w, j) for w in (0, 999, 1000, 9999, 40000, 10**50)
                      for j in (None, "out-of-town", "one-mug-tea"))]
        for weather in ("sun", "cloud", "rain", "snow", "storm", "unknown", None, []):
            state = {"people": copy.deepcopy(people)}
            bought = set(range(0, len(people), 2))
            _update_mood(state, bought, weather)
            moods = [p["mood"] for p in state["people"]]
            self.assertTrue(all(type(m) is int and 0 <= m <= 100 for m in moods))
            self.assertEqual(state["avg_mood"], sum(moods) // len(moods))
            self.assertEqual(state["mood_bands"], {
                "happy": sum(m >= 70 for m in moods),
                "ok": sum(40 <= m < 70 for m in moods),
                "unhappy": sum(m < 40 for m in moods),
            })
            self.assertEqual(sum(state["mood_bands"].values()), len(people))
            repeat = copy.deepcopy(state)
            _update_mood(state, bought, weather)
            self.assertEqual(state, repeat)

    def test_factor_values_and_band_boundaries(self):
        cases = [
            (0, None, False, "sun", 30, "unhappy"),
            (0, None, True, "sun", 40, "ok"),
            (9000, None, False, "sun", 39, "unhappy"),
            (19000, "out-of-town", False, "sun", 69, "ok"),
            (20000, "out-of-town", False, "sun", 70, "happy"),
            (40000, "one-mug-tea", True, "sun", 100, "happy"),
            (40000, "one-mug-tea", True, "cloud", 95, "happy"),
            (40000, "one-mug-tea", True, "rain", 90, "happy"),
            (40000, "one-mug-tea", True, "snow", 85, "happy"),
            (0, None, False, "storm", 5, "unhappy"),
        ]
        for wallet, job, bought, weather, expected, band in cases:
            state = {"people": [{"id": 1, "wallet_cents": wallet, "job": job}]}
            _update_mood(state, {1} if bought else set(), weather)
            self.assertEqual(state["people"][0]["mood"], expected)
            self.assertEqual(state["mood_bands"][band], 1)

    def test_successful_purchase_bonus_resets_next_tick(self):
        class Visits:
            def shuffle(self, people):
                pass

            def random(self):
                return 0

            def choice(self, choices):
                return choices[0]
        town = Town()
        system = System()
        system.setup(town)
        town.rng = Visits()
        town.day = 6
        for person in town.state["residents"]["people"]:
            person.update(wallet_cents=0, job=None)
        people = town.state["residents"]["people"]
        people[0]["wallet_cents"] = 10501
        town.state["businesses"] = businesses(capacity=120, price=500)
        system.tick(town)
        self.assertEqual(people[0]["wallet_cents"], 9501)
        self.assertEqual(people[0]["mood"], 49)  # two purchases, one bonus
        self.assertEqual(people[1]["mood"], 30)  # attempted, but unaffordable
        town.state.pop("businesses")
        town.day = 7
        system.tick(town)
        self.assertEqual(people[0]["mood"], 39)
        self.assertEqual(people[1]["mood"], 30)


if __name__ == "__main__":
    unittest.main()
