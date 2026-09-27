"""Standalone contract tests; no engine or business implementation required."""

import copy
import random
import unittest
from collections import Counter

from kiwi.townfolk import SHOP_IDS, STAFF_COUNTS, System


class Town:
    def __init__(self, seed=42):
        self.day = 0
        self.rng = random.Random(seed)
        self.state = {}


def businesses(capacity=5, price=500):
    return {"shops": {shop: {"open": True, "available": capacity,
                            "price_cents": price} for shop in SHOP_IDS},
            "wages_paid": {}}


class ResidentsTests(unittest.TestCase):
    def setUp(self):
        self.town = Town()
        self.system = System()
        self.system.setup(self.town)

    def test_setup_population_and_jobs(self):
        state = self.town.state["residents"]
        people = state["people"]
        self.assertEqual(state["count"], 120)
        self.assertEqual(state["employed"], 102)
        self.assertEqual(len({p["name"] for p in people}), 120)
        self.assertEqual([p["id"] for p in people], list(range(1, 121)))
        self.assertEqual(Counter(p["job"] for p in people),
                         Counter({**STAFF_COUNTS, "out-of-town": 94, None: 18}))
        for person in people:
            self.assertEqual(set(person), {"id", "name", "street", "job", "wallet_cents"})
            self.assertTrue(2000 <= person["wallet_cents"] <= 10000)

    def test_setup_does_not_read_other_systems(self):
        class WriteOnly(dict):
            def get(self, *args):
                raise AssertionError("setup read another system")

            def __getitem__(self, key):
                raise AssertionError("setup read another system")
        self.town.state = WriteOnly()
        self.system.setup(self.town)

    def test_determinism_over_90_days(self):
        def run(seed):
            town = Town(seed)
            System().setup(town)
            town.state["businesses"] = businesses()
            history = []
            for day in range(1, 91):
                town.day = day
                town.state["weather"] = {"condition": ("sun", "cloud", "rain", "snow", "storm")[day % 5]}
                System().tick(town)
                history.append(copy.deepcopy(town.state["residents"]))
            return history
        self.assertEqual(run(42), run(42))
        self.assertNotEqual(run(42), run(43))

    def test_missing_businesses_weekday_wages(self):
        initial = copy.deepcopy(self.town.state["residents"]["people"])
        for day in range(1, 91):
            self.town.day = day
            self.system.tick(self.town)
            self.assertEqual(self.town.state["residents"]["purchases"], {})
            self.assertEqual(self.town.state["residents"]["spent_cents"], {})
        weekdays = sum((day - 1) % 7 < 5 for day in range(1, 91))
        for before, after in zip(initial, self.town.state["residents"]["people"]):
            self.assertEqual(after["wallet_cents"], before["wallet_cents"] +
                             (weekdays * 2000 if before["job"] == "out-of-town" else 0))

    def test_bounds_and_money_conservation_and_read_only_inputs(self):
        town = self.town
        town.state["businesses"] = businesses()
        town.state["businesses"]["wages_paid"] = {1: 725, 2: 15}
        for day in range(1, 91):
            town.day = day
            town.state["weather"] = {"condition": ("sun", "rain", "snow", "storm")[day % 4]}
            inputs = copy.deepcopy({k: v for k, v in town.state.items() if k != "residents"})
            before = copy.deepcopy(town.state["residents"]["people"])
            self.system.tick(town)
            state = town.state["residents"]
            for old, new in zip(before, state["people"]):
                wage = inputs["businesses"]["wages_paid"].get(old["id"], 0)
                if (day - 1) % 7 < 5 and old["job"] == "out-of-town":
                    wage += 2000
                self.assertIn(old["wallet_cents"] + wage - new["wallet_cents"], (0, 500, 1000))
                self.assertIs(type(new["wallet_cents"]), int)
                self.assertGreaterEqual(new["wallet_cents"], 0)
            self.assertLessEqual(sum(state["purchases"].values()), 240)
            for shop, units in state["purchases"].items():
                self.assertTrue(0 < units <= 5)
                self.assertEqual(state["spent_cents"][shop], units * 500)
            total = sum(p["wallet_cents"] for p in state["people"])
            wage_total = 740 + (188000 if (day - 1) % 7 < 5 else 0)
            self.assertEqual(total, sum(p["wallet_cents"] for p in before) + wage_total - sum(state["spent_cents"].values()))
            self.assertEqual(state["avg_wallet_cents"], total // 120)
            self.assertEqual({k: v for k, v in town.state.items() if k != "residents"}, inputs)
            if inputs["weather"]["condition"] == "storm":
                self.assertEqual(state["purchases"], {})

    def test_wages_available_before_purchase_and_exact_wallet(self):
        class AlwaysVisits:
            def shuffle(self, people):
                pass

            def random(self):
                return 0.0

            def choice(self, shops):
                return shops[0]
        self.town.rng = AlwaysVisits()
        self.town.day = 6  # Saturday: no outside wages.
        for person in self.town.state["residents"]["people"]:
            person["wallet_cents"] = 0
        self.town.state["businesses"] = businesses(capacity=120)
        self.town.state["businesses"]["wages_paid"] = {1: 500, 2: 499}
        self.system.tick(self.town)
        state = self.town.state["residents"]
        self.assertEqual(state["purchases"], {SHOP_IDS[0]: 1})
        self.assertEqual(state["people"][0]["wallet_cents"], 0)
        self.assertEqual(state["people"][1]["wallet_cents"], 499)
        self.town.state.pop("businesses")
        self.system.tick(self.town)
        self.assertEqual(state["purchases"], {})
        self.assertEqual(state["spent_cents"], {})

    def test_bad_weather_reduces_visits(self):
        totals = []
        for condition in ("sun", "cloud", "rain", "snow", "storm"):
            town = Town()
            self.system.setup(town)
            town.day = 6
            town.state["businesses"] = businesses(capacity=120, price=1)
            town.state["weather"] = {"condition": condition}
            self.system.tick(town)
            totals.append(sum(town.state["residents"]["purchases"].values()))
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertGreater(totals[0], totals[-2])
        self.assertEqual(totals[-1], 0)

    def test_healthy_threshold_distinct_shops_and_affordability(self):
        class AlwaysVisits:
            def shuffle(self, people):
                pass

            def random(self):
                return 0.0

            def choice(self, shops):
                return shops[0]

        for wallet, price, capacity, expected in (
                (10000, 100, 120, {SHOP_IDS[0]: 1}),
                (10001, 100, 120, {SHOP_IDS[0]: 1, SHOP_IDS[1]: 1}),
                (10001, 6000, 120, {SHOP_IDS[0]: 1}),
                (10001, 100, 0, {})):
            with self.subTest(wallet=wallet, price=price, capacity=capacity):
                town = Town()
                self.system.setup(town)
                town.rng = AlwaysVisits()
                town.day = 6
                people = town.state["residents"]["people"]
                for person in people:
                    person["wallet_cents"] = 0
                people[0]["wallet_cents"] = wallet
                town.state["businesses"] = businesses(capacity=capacity, price=price)
                self.system.tick(town)
                self.assertEqual(town.state["residents"]["purchases"], expected)
                self.assertEqual(people[0]["wallet_cents"], wallet - price * sum(expected.values()))

    def test_missing_and_invalid_inputs_and_closed_shops(self):
        for value in (None, {}, [], -1, True, "bad"):
            self.town.state["businesses"] = value
            self.town.state["weather"] = value
            self.system.tick(self.town)
            self.assertEqual(self.town.state["residents"]["purchases"], {})
        for field, values in (("open", (False, None, 1)),
                              ("available", (0, -1, None, True, 1.5)),
                              ("price_cents", (0, -1, None, True, 1.5, 10**9))):
            for value in values:
                self.town.state["businesses"] = businesses()
                for shop in self.town.state["businesses"]["shops"].values():
                    shop[field] = value
                self.town.state["businesses"]["wages_paid"] = {1: -100, 2: True, 3: 1.5, 999: 100}
                before = copy.deepcopy(self.town.state["residents"]["people"])
                self.system.tick(self.town)
                self.assertEqual(self.town.state["residents"]["people"], before)
                self.assertEqual(self.town.state["residents"]["purchases"], {})


if __name__ == "__main__":
    unittest.main()
