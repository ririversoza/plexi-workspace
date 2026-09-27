"""Tests for Nori's Tiny Town businesses system (no Taro engine required)."""

from __future__ import annotations

import random
import unittest

from nori.shops import (
    SHOP_IDS,
    SHOP_PARAMS,
    START_BALANCE_CENTS,
    WAGE_BASE_CENTS,
    WAGE_REVENUE_SHARE_PCT,
    System,
    wage_per_staff,
)


class FakeTown:
    """Minimal Town stand-in matching the Tiny Town interface."""

    def __init__(self, seed: int = 42) -> None:
        self.day = 0
        self.rng = random.Random(seed)
        self.state: dict = {}
        self.events: list = []
        self._subscribers: list = []
        self._current_system = "businesses"

    def emit(self, kind: str, **data) -> None:
        event = {"day": self.day, "system": self._current_system, "kind": kind, **data}
        self.events.append(event)
        for cb in list(self._subscribers):
            cb(event)

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)


def _seed_residents(town: FakeTown, purchases=None, spent=None, staff_pairs=None):
    """Install a tiny residents blob. Default: two staff for one-mug-tea."""
    people = []
    if staff_pairs is None:
        staff_pairs = [("one-mug-tea", 1), ("one-mug-tea", 2)]
    for shop_id, rid in staff_pairs:
        people.append(
            {
                "id": rid,
                "name": f"Staff {rid}",
                "street": "Test St",
                "job": shop_id,
                "wallet_cents": 5000,
            }
        )
    town.state["residents"] = {
        "people": people,
        "purchases": dict(purchases or {}),
        "spent_cents": dict(spent or {}),
        "count": len(people),
        "employed": len(people),
        "avg_wallet_cents": 5000,
    }


def run_businesses(
    seed: int = 42,
    days: int = 90,
    *,
    with_residents: bool = False,
    with_weather: bool = False,
    weather_sequence=None,
):
    town = FakeTown(seed=seed)
    system = System()
    system.setup(town)
    if with_residents:
        _seed_residents(town)
    snapshots = []
    for day in range(1, days + 1):
        town.day = day
        if with_weather:
            if weather_sequence is not None:
                condition = weather_sequence[(day - 1) % len(weather_sequence)]
            else:
                condition = town.rng.choice(["sun", "cloud", "rain", "snow", "storm"])
            town.state["weather"] = {
                "condition": condition,
                "temp_c": 15.0,
                "season": "spring",
            }
            prev = town._current_system
            town._current_system = "weather"
            town.emit("daily", condition=condition)
            town._current_system = prev
        system.tick(town)
        snap = {
            "open_count": town.state["businesses"]["open_count"],
            "balances": {
                sid: town.state["businesses"]["shops"][sid]["balance_cents"]
                for sid in SHOP_IDS
            },
            "available": {
                sid: town.state["businesses"]["shops"][sid]["available"]
                for sid in SHOP_IDS
            },
            "open": {
                sid: town.state["businesses"]["shops"][sid]["open"]
                for sid in SHOP_IDS
            },
            "wages_paid": dict(town.state["businesses"]["wages_paid"]),
            "pending": dict(town.state["businesses"]["pending_revenue_cents"]),
        }
        snapshots.append(snap)
        if with_residents and day < days:
            units = 1 + (day % 3)
            price = SHOP_PARAMS["one-mug-tea"]["price_cents"]
            town.state["residents"]["purchases"] = {"one-mug-tea": units}
            town.state["residents"]["spent_cents"] = {"one-mug-tea": units * price}
            prev = town._current_system
            town._current_system = "economy"
            town.emit("daily")
            town._current_system = prev
    return town.state["businesses"], snapshots, system, town


class SetupTests(unittest.TestCase):
    def test_setup_writes_six_shops_at_500(self):
        town = FakeTown()
        System().setup(town)
        state = town.state["businesses"]
        self.assertEqual(set(state["shops"]), set(SHOP_IDS))
        self.assertEqual(state["open_count"], 6)
        for shop_id, shop in state["shops"].items():
            self.assertEqual(shop["balance_cents"], START_BALANCE_CENTS)
            self.assertEqual(shop["price_cents"], SHOP_PARAMS[shop_id]["price_cents"])
            self.assertEqual(shop["available"], SHOP_PARAMS[shop_id]["capacity"])
            self.assertEqual(shop["sold_yesterday"], 0)
            self.assertEqual(shop["staff"], [])
            self.assertTrue(shop["open"])
            self.assertIsInstance(shop["name"], str)
        self.assertEqual(state["wages_paid"], {})
        self.assertEqual(state["pending_revenue_cents"], {s: 0 for s in SHOP_IDS})


class DeterminismTests(unittest.TestCase):
    def test_same_seed_same_state_with_weather(self):
        _, snaps_a, _, _ = run_businesses(
            seed=42, days=90, with_weather=True, with_residents=True
        )
        _, snaps_b, _, _ = run_businesses(
            seed=42, days=90, with_weather=True, with_residents=True
        )
        self.assertEqual(snaps_a, snaps_b)

    def test_different_seed_diverges_when_weather_uses_rng(self):
        _, snaps_a, _, _ = run_businesses(seed=42, days=30, with_weather=True)
        _, snaps_b, _, _ = run_businesses(seed=99, days=30, with_weather=True)
        self.assertNotEqual(snaps_a, snaps_b)


class BoundsTests(unittest.TestCase):
    def test_balances_never_negative(self):
        _, snapshots, _, _ = run_businesses(
            seed=42, days=90, with_weather=True, with_residents=True
        )
        for day, snap in enumerate(snapshots, start=1):
            for shop_id, bal in snap["balances"].items():
                self.assertGreaterEqual(bal, 0, msg=f"day {day} {shop_id}")
            self.assertGreaterEqual(snap["open_count"], 0)
            self.assertLessEqual(snap["open_count"], 6)
            for shop_id, avail in snap["available"].items():
                self.assertGreaterEqual(avail, 0)
                self.assertLessEqual(avail, SHOP_PARAMS[shop_id]["capacity"])
            for cents in snap["wages_paid"].values():
                self.assertGreaterEqual(cents, 0)

    def test_storm_closes_every_shop(self):
        _, snapshots, _, town = run_businesses(
            seed=42,
            days=5,
            with_weather=True,
            weather_sequence=["storm"] * 5,
        )
        for snap in snapshots:
            self.assertEqual(snap["open_count"], 0)
            self.assertTrue(all(v == 0 for v in snap["available"].values()))
            self.assertTrue(all(v is False for v in snap["open"].values()))
        kinds = [e["kind"] for e in town.events]
        self.assertIn("shops_closed", kinds)

    def test_rain_reduces_available_but_stays_open(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        town.state["weather"] = {"condition": "rain", "temp_c": 10.0, "season": "spring"}
        town.day = 1
        system.tick(town)
        for shop_id, shop in town.state["businesses"]["shops"].items():
            expected = int(SHOP_PARAMS[shop_id]["capacity"] * 0.7)
            self.assertTrue(shop["open"])
            self.assertEqual(shop["available"], expected)

    def test_wages_paid_to_staff_same_day(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, staff_pairs=[("matcha-mile", 10), ("matcha-mile", 11)])
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "summer"}
        town.day = 1
        system.tick(town)
        wages = town.state["businesses"]["wages_paid"]
        # Day 1: no booked revenue yet → base only, split N/A (each gets base).
        expected_wage = wage_per_staff(2, 0)
        self.assertEqual(expected_wage, WAGE_BASE_CENTS)
        self.assertEqual(wages.get(10), expected_wage)
        self.assertEqual(wages.get(11), expected_wage)
        shop = town.state["businesses"]["shops"]["matcha-mile"]
        self.assertEqual(shop["staff"], [10, 11])
        expected = (
            START_BALANCE_CENTS
            - SHOP_PARAMS["matcha-mile"]["overhead_cents"]
            - 2 * expected_wage
        )
        self.assertEqual(shop["balance_cents"], expected)

    def test_no_wages_when_storm_closed(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, staff_pairs=[("one-mug-tea", 1), ("one-mug-tea", 2)])
        town.state["weather"] = {"condition": "storm", "temp_c": 5.0, "season": "spring"}
        town.day = 1
        system.tick(town)
        self.assertEqual(town.state["businesses"]["wages_paid"], {})
        self.assertEqual(town.state["businesses"]["open_count"], 0)

    def test_wage_includes_revenue_share(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        units = 10
        price = SHOP_PARAMS["one-mug-tea"]["price_cents"]
        revenue = units * price
        _seed_residents(
            town,
            purchases={"one-mug-tea": units},
            spent={"one-mug-tea": revenue},
            staff_pairs=[("one-mug-tea", 1)],
        )
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "spring"}
        town.day = 2
        system.tick(town)
        expected = wage_per_staff(1, revenue)
        share = (revenue * WAGE_REVENUE_SHARE_PCT) // 100
        self.assertEqual(expected, WAGE_BASE_CENTS + share)
        self.assertEqual(town.state["businesses"]["wages_paid"].get(1), expected)

    def test_yesterday_purchases_booked_as_revenue(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        units = 4
        price = SHOP_PARAMS["fold-post"]["price_cents"]
        unit_cost = SHOP_PARAMS["fold-post"]["unit_cost_cents"]
        overhead = SHOP_PARAMS["fold-post"]["overhead_cents"]
        _seed_residents(
            town,
            purchases={"fold-post": units},
            spent={"fold-post": units * price},
            staff_pairs=[],
        )
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "spring"}
        town.day = 2
        before = town.state["businesses"]["shops"]["fold-post"]["balance_cents"]
        system.tick(town)
        shop = town.state["businesses"]["shops"]["fold-post"]
        self.assertEqual(shop["sold_yesterday"], units)
        expected = before + units * price - units * unit_cost - overhead
        self.assertEqual(shop["balance_cents"], expected)

    def test_pending_captures_day90_sales_after_later_emit(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, staff_pairs=[])
        town.day = 90
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "autumn"}
        system.tick(town)
        units = 3
        price = SHOP_PARAMS["daifuku-cart"]["price_cents"]
        town.state["residents"]["purchases"] = {"daifuku-cart": units}
        town.state["residents"]["spent_cents"] = {"daifuku-cart": units * price}
        town._current_system = "economy"
        town.emit("daily")
        pending = town.state["businesses"]["pending_revenue_cents"]
        self.assertEqual(pending["daifuku-cart"], units * price)


class MissingPeersTests(unittest.TestCase):
    def test_runs_with_no_other_systems(self):
        state, snapshots, _, town = run_businesses(
            seed=42, days=90, with_residents=False, with_weather=False
        )
        self.assertEqual(len(snapshots), 90)
        self.assertIn("shops", state)
        # Day 1 opens all six; later days may close shops that can't cover overhead
        # (no residents → no revenue), but never crash or go negative.
        self.assertEqual(snapshots[0]["open_count"], 6)
        for snap in snapshots:
            self.assertGreaterEqual(snap["open_count"], 0)
            self.assertLessEqual(snap["open_count"], 6)
            for bal in snap["balances"].values():
                self.assertGreaterEqual(bal, 0)
        self.assertEqual(snapshots[-1]["wages_paid"], {})

    def test_missing_weather_defaults_to_open(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        town.day = 1
        system.tick(town)
        self.assertEqual(town.state["businesses"]["open_count"], 6)

    def test_wages_short_when_open_but_broke(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        shop = town.state["businesses"]["shops"]["fold-post"]
        # Enough for overhead ($15) but not full wages after opening.
        shop["balance_cents"] = SHOP_PARAMS["fold-post"]["overhead_cents"] + 100
        _seed_residents(town, staff_pairs=[("fold-post", 1), ("fold-post", 2)])
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "summer"}
        town.day = 1
        system.tick(town)
        self.assertTrue(town.state["businesses"]["shops"]["fold-post"]["open"])
        short = [e for e in town.events if e["kind"] == "wages_short"]
        self.assertTrue(short)
        for bal in (
            town.state["businesses"]["shops"][s]["balance_cents"] for s in SHOP_IDS
        ):
            self.assertGreaterEqual(bal, 0)

    def test_closed_for_overhead_pays_no_wages(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        shop = town.state["businesses"]["shops"]["matcha-mile"]
        shop["balance_cents"] = 100  # less than overhead → closed, no wages
        _seed_residents(
            town, staff_pairs=[("matcha-mile", 1), ("matcha-mile", 2)]
        )
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "summer"}
        town.day = 1
        system.tick(town)
        self.assertFalse(town.state["businesses"]["shops"]["matcha-mile"]["open"])
        self.assertEqual(town.state["businesses"]["wages_paid"], {})
        self.assertFalse(any(e["kind"] == "wages_short" for e in town.events))


if __name__ == "__main__":
    unittest.main()
