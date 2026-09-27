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
        self.events = []

    def emit(self, kind, **data):
        self.events.append({"day": self.day, "kind": kind, **data})


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
            self.assertEqual(set(person), {"id", "name", "street", "job", "wallet_cents", "mood",
                                           "rent_arrears_cents", "utility_arrears_cents",
                                           "arrears_cents", "taxes_paid_cents", "rent_paid_cents",
                                           "utilities_paid_cents", "benefit_received_cents"})
            self.assertTrue(2000 <= person["wallet_cents"] <= 10000)

    def test_setup_does_not_read_other_systems(self):
        class WriteOnly(dict):
            def get(self, *args):
                raise AssertionError("setup read another system")

            def __getitem__(self, key):
                raise AssertionError("setup read another system")
        self.town.state = WriteOnly()
        self.system.setup(self.town)

    def test_empty_people_after_setup(self):
        state = self.town.state["residents"]
        state["people"] = []
        state["purchases"] = {SHOP_IDS[0]: 1}
        state["spent_cents"] = {SHOP_IDS[0]: 500}
        self.town.state["businesses"] = businesses()
        self.town.state["businesses"]["wages_paid"] = {1: 500}
        inputs = copy.deepcopy(self.town.state["businesses"])
        rng = self.town.rng.getstate()
        for day in (1, 2):
            self.town.day = day
            self.system.tick(self.town)
            self.assertEqual(state, {
                "people": [], "purchases": {}, "spent_cents": {},
                "count": 0, "employed": 0, "avg_wallet_cents": 0,
                "avg_mood": 0, "mood_bands": {"happy": 0, "ok": 0, "unhappy": 0},
                "taxes_paid_cents": 0, "rent_paid_cents": 0, "bills_paid_cents": 0,
                "arrears_cents": 0, "in_arrears": 0, "benefits_received_cents": 0,
            })
            self.assertEqual(self.town.rng.getstate(), rng)
            self.assertEqual(self.town.state["businesses"], inputs)

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
        for before, after in zip(initial, self.town.state["residents"]["people"]):
            self.assertGreaterEqual(after["wallet_cents"], 0)
            self.assertEqual(after["arrears_cents"],
                             after["rent_arrears_cents"] + after["utility_arrears_cents"])
            if before["job"] is None:
                self.assertGreater(after["arrears_cents"], 0)

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
                self.assertIs(type(new["wallet_cents"]), int)
                self.assertGreaterEqual(new["wallet_cents"], 0)
                self.assertEqual(new["taxes_paid_cents"], wage // 10)
            self.assertLessEqual(sum(state["purchases"].values()), 240)
            for shop, units in state["purchases"].items():
                self.assertTrue(0 < units <= 5)
                self.assertEqual(state["spent_cents"][shop], units * 500)
            total = sum(p["wallet_cents"] for p in state["people"])
            wage_total = 740 + (188000 if (day - 1) % 7 < 5 else 0)
            self.assertEqual(total, sum(p["wallet_cents"] for p in before) + wage_total
                             - state["taxes_paid_cents"] - state["rent_paid_cents"]
                             - state["bills_paid_cents"] - sum(state["spent_cents"].values()))
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
        self.town.state["businesses"]["wages_paid"] = {1: 1400, 2: 1387}
        self.system.tick(self.town)
        state = self.town.state["residents"]
        self.assertEqual(state["purchases"], {SHOP_IDS[0]: 1})
        self.assertEqual(state["people"][0]["wallet_cents"], 10)
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
                (10750, 100, 120, {SHOP_IDS[0]: 1}),
                (10751, 100, 120, {SHOP_IDS[0]: 1, SHOP_IDS[1]: 1}),
                (10751, 6000, 120, {SHOP_IDS[0]: 1}),
                (10751, 100, 0, {})):
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
                self.assertEqual(people[0]["wallet_cents"], wallet - 750 - price * sum(expected.values()))

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
                self.system.tick(self.town)
                self.assertEqual(self.town.state["residents"]["taxes_paid_cents"], 0)
                self.assertTrue(all(p["wallet_cents"] >= 0
                                    for p in self.town.state["residents"]["people"]))
                self.assertEqual(self.town.state["residents"]["purchases"], {})

    def test_tax_withholding_bills_and_arrears_recovery(self):
        state = self.town.state["residents"]
        person = state["people"][0]
        state["people"] = [person]
        person.update(wallet_cents=0, job=None)
        self.town.state["weather"] = {"condition": "sun"}

        self.town.day = 6  # No out-of-town wages.
        self.town.state["businesses"] = {"wages_paid": {person["id"]: 833}}
        self.system.tick(self.town)
        self.assertEqual((person["wallet_cents"], person["taxes_paid_cents"],
                          person["rent_paid_cents"], person["utilities_paid_cents"]),
                         (0, 83, 600, 150))
        self.assertEqual((state["taxes_paid_cents"], state["rent_paid_cents"],
                          state["bills_paid_cents"], state["arrears_cents"], state["in_arrears"]),
                         (83, 600, 150, 0, 0))

        self.town.day = 7
        self.town.state.pop("businesses")
        self.system.tick(self.town)
        self.assertEqual((person["wallet_cents"], person["rent_arrears_cents"],
                          person["utility_arrears_cents"]), (0, 600, 150))
        self.assertEqual([event["kind"] for event in self.town.events],
                         ["missed_rent", "missed_bill"])
        self.assertEqual(state["in_arrears"], 1)
        self.assertEqual(person["mood"], 15)  # Base 30, minus arrears penalty 15.

        self.town.day = 8
        self.town.state["businesses"] = {"wages_paid": {person["id"]: 2000}}
        self.system.tick(self.town)
        self.assertEqual((person["wallet_cents"], person["arrears_cents"]), (300, 0))
        self.assertEqual((state["taxes_paid_cents"], state["rent_paid_cents"],
                          state["bills_paid_cents"], state["in_arrears"]),
                         (200, 1200, 300, 0))
        self.assertEqual(len(self.town.events), 2)

    def test_partial_old_arrears_first_and_no_overdraft(self):
        state = self.town.state["residents"]
        person = state["people"][0]
        state["people"] = [person]
        person.update(wallet_cents=0, job=None, rent_arrears_cents=600,
                      utility_arrears_cents=150, arrears_cents=750)
        self.town.day = 6
        self.town.state["weather"] = {"condition": "storm"}
        self.town.state["businesses"] = {"wages_paid": {person["id"]: 500}}
        self.system.tick(self.town)
        self.assertEqual((person["wallet_cents"], person["rent_arrears_cents"],
                          person["utility_arrears_cents"]), (0, 750, 300))
        self.assertEqual((state["taxes_paid_cents"], state["rent_paid_cents"],
                          state["bills_paid_cents"], state["arrears_cents"]),
                         (50, 450, 0, 1050))
        self.assertEqual([event["kind"] for event in self.town.events],
                         ["missed_rent", "missed_bill"])

    def test_prior_day_unemployment_benefit_is_untaxed(self):
        state = self.town.state["residents"]
        unemployed = next(person for person in state["people"] if person["job"] is None)
        employed = next(person for person in state["people"] if person["job"] is not None)
        state["people"] = [unemployed, employed]
        unemployed["wallet_cents"] = employed["wallet_cents"] = 0
        self.town.day = 6
        self.town.state["economy"] = {"benefit_per_head_cents": 750}
        self.system.tick(self.town)
        self.assertEqual((unemployed["benefit_received_cents"], unemployed["wallet_cents"],
                          unemployed["arrears_cents"]), (750, 0, 0))
        self.assertEqual((employed["benefit_received_cents"], employed["wallet_cents"],
                          employed["arrears_cents"]), (0, 0, 750))
        self.assertEqual((state["benefits_received_cents"], state["taxes_paid_cents"],
                          state["bills_paid_cents"], state["in_arrears"]),
                         (750, 0, 150, 1))


if __name__ == "__main__":
    unittest.main()
