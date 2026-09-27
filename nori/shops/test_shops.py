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
    PRICE_CEIL_PCT_OF_BASE,
    PRICE_FLOOR_PCT_OF_BASE,
    PRICE_WEEK_DAYS,
    System,
    next_price_cents,
    price_bounds_cents,
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
        from nori.shops import COMMERCIAL_RENT_CENTS, LICENCE_UTILITIES_CENTS

        expected = (
            START_BALANCE_CENTS
            - SHOP_PARAMS["matcha-mile"]["overhead_cents"]
            - COMMERCIAL_RENT_CENTS
            - LICENCE_UTILITIES_CENTS
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
        from nori.shops import (
            COMMERCIAL_RENT_CENTS,
            LICENCE_UTILITIES_CENTS,
            sales_tax_cents,
        )

        revenue = units * price
        tax = sales_tax_cents(revenue)
        expected = (
            before
            + revenue
            - tax
            - overhead
            - COMMERCIAL_RENT_CENTS
            - LICENCE_UTILITIES_CENTS
            - units * unit_cost
        )
        self.assertEqual(shop["balance_cents"], expected)
        self.assertEqual(town.state["businesses"]["taxes_paid_cents"], tax)
        # All six shops open → each pays rent + licence.
        self.assertEqual(
            town.state["businesses"]["bills_paid_cents"],
            6 * (COMMERCIAL_RENT_CENTS + LICENCE_UTILITIES_CENTS),
        )

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
        self.assertEqual(system._pending_from_day, 90)


class SettlementDayTests(unittest.TestCase):
    """Settlement must key by purchase day, not by purchase content."""

    def test_identical_consecutive_batches_are_both_booked(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, purchases={}, spent={}, staff_pairs=[])
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "spring"}
        price = SHOP_PARAMS["one-mug-tea"]["price_cents"]
        units = 5
        batch_p = {"one-mug-tea": units}
        batch_s = {"one-mug-tea": units * price}
        revenue = units * price

        town.day = 1
        town._current_system = "businesses"
        system.tick(town)
        self.assertEqual(system.revenue_booked_total_cents, 0)
        town.state["residents"]["purchases"] = dict(batch_p)
        town.state["residents"]["spent_cents"] = dict(batch_s)
        town._current_system = "economy"
        town.emit("daily")
        self.assertEqual(system._pending_from_day, 1)

        town.day = 2
        town._current_system = "businesses"
        system.tick(town)
        self.assertEqual(system.revenue_booked_total_cents, revenue)
        self.assertEqual(system._last_settled_day, 1)
        # Identical content on day 2 — must still be captured as a new day.
        town.state["residents"]["purchases"] = dict(batch_p)
        town.state["residents"]["spent_cents"] = dict(batch_s)
        town._current_system = "economy"
        town.emit("daily")
        self.assertEqual(system._pending_from_day, 2)

        town.day = 3
        town._current_system = "businesses"
        system.tick(town)
        self.assertEqual(system.revenue_booked_total_cents, 2 * revenue)
        self.assertEqual(system._last_settled_day, 2)

    def test_money_conservation_spent_equals_booked_plus_pending(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, purchases={}, spent={}, staff_pairs=[])
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "spring"}
        price = SHOP_PARAMS["fold-post"]["price_cents"]
        total_spent = 0
        # Mix identical and varying non-empty days across a short run.
        daily_units = [3, 3, 3, 7, 0, 4, 4]
        for day, units in enumerate(daily_units, start=1):
            town.day = day
            town._current_system = "businesses"
            system.tick(town)
            purchases = {"fold-post": units} if units else {}
            spent = {"fold-post": units * price} if units else {}
            town.state["residents"]["purchases"] = purchases
            town.state["residents"]["spent_cents"] = spent
            total_spent += units * price
            town._current_system = "economy"
            town.emit("daily")
        pending_total = sum(
            town.state["businesses"]["pending_revenue_cents"].values()
        )
        self.assertEqual(
            total_spent,
            system.revenue_booked_total_cents + pending_total,
        )
        # Last day's spend should still be pending (one-day lag).
        self.assertEqual(pending_total, daily_units[-1] * price)

    def test_settlement_safe_with_residents_missing(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        for day in range(1, 11):
            town.day = day
            system.tick(town)
        self.assertEqual(system.revenue_booked_total_cents, 0)
        self.assertEqual(town.state["businesses"]["wages_paid"], {})
        for shop in town.state["businesses"]["shops"].values():
            self.assertGreaterEqual(shop["balance_cents"], 0)
            self.assertEqual(shop["sold_yesterday"], 0)
        # Empty yesterday batches may be marked settled; that must not credit cash.
        self.assertEqual(sum(town.state["businesses"]["pending_revenue_cents"].values()), 0)


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


class WeeklyPricingTests(unittest.TestCase):
    def test_price_bounds_helper(self):
        for shop_id in SHOP_IDS:
            lo, hi = price_bounds_cents(shop_id)
            base = SHOP_PARAMS[shop_id]["price_cents"]
            unit = SHOP_PARAMS[shop_id]["unit_cost_cents"]
            self.assertGreaterEqual(lo, (base * PRICE_FLOOR_PCT_OF_BASE) // 100)
            self.assertGreaterEqual(lo, (unit * 115) // 100)
            self.assertEqual(hi, (base * PRICE_CEIL_PCT_OF_BASE) // 100)
            self.assertLessEqual(lo, hi)

    def test_next_price_bump_cut_and_clamp(self):
        shop_id = "one-mug-tea"
        base = SHOP_PARAMS[shop_id]["price_cents"]
        # Sold out most days → bump
        bumped, reason = next_price_cents(
            shop_id, base, [(150, 150), (150, 150), (10, 150)]
        )
        self.assertEqual(reason, "bump")
        self.assertEqual(bumped, base + (base * 5) // 100)
        # Low fill → cut
        cut, reason = next_price_cents(
            shop_id, base, [(10, 150), (10, 150), (10, 150)]
        )
        self.assertEqual(reason, "cut")
        self.assertEqual(cut, base - (base * 5) // 100)
        # Clamp to ceiling
        lo, hi = price_bounds_cents(shop_id)
        at_hi, _ = next_price_cents(shop_id, hi, [(150, 150)] * 5)
        self.assertEqual(at_hi, hi)
        at_lo, _ = next_price_cents(shop_id, lo, [(0, 150)] * 5)
        self.assertEqual(at_lo, lo)

    def test_weekly_adjust_emits_price_change_and_stays_in_bounds(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, purchases={}, spent={}, staff_pairs=[])
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "spring"}
        # Force a sell-out week for one-mug-tea via synthetic week stats.
        cap = SHOP_PARAMS["one-mug-tea"]["capacity"]
        system._week_stats["one-mug-tea"] = [(cap, cap)] * 6
        system._prev_available = {s: SHOP_PARAMS[s]["capacity"] for s in SHOP_IDS}
        # Days 1–6 open normally; day 7 triggers pricing.
        for day in range(1, PRICE_WEEK_DAYS + 1):
            town.day = day
            # Keep prev_available high so open-day logs accumulate for other shops too.
            system._prev_available = {
                s: SHOP_PARAMS[s]["capacity"] for s in SHOP_IDS
            }
            if day < PRICE_WEEK_DAYS:
                system._week_stats["one-mug-tea"] = [(cap, cap)] * day
            system.tick(town)
        tea = town.state["businesses"]["shops"]["one-mug-tea"]
        lo, hi = price_bounds_cents("one-mug-tea")
        self.assertGreaterEqual(tea["price_cents"], lo)
        self.assertLessEqual(tea["price_cents"], hi)
        changes = [e for e in town.events if e["kind"] == "price_change"]
        tea_changes = [e for e in changes if e["shop_id"] == "one-mug-tea"]
        self.assertTrue(tea_changes)
        self.assertEqual(tea_changes[0]["reason"], "bump")

    def test_storm_on_pricing_day_keeps_week_stats(self):
        """Closed on day 7 must not drop days 1–6; next open pricing day uses them."""
        town = FakeTown()
        system = System()
        system.setup(town)
        _seed_residents(town, purchases={}, spent={}, staff_pairs=[])
        cap = SHOP_PARAMS["one-mug-tea"]["capacity"]
        base = SHOP_PARAMS["one-mug-tea"]["price_cents"]
        # Pretend days 1–6 were full sell-outs, then storm closes everyone on day 7.
        system._week_stats["one-mug-tea"] = [(cap, cap)] * 6
        system._prev_available = {s: cap for s in SHOP_IDS}
        town.day = 7
        town.state["weather"] = {"condition": "storm", "temp_c": 5.0, "season": "spring"}
        system.tick(town)
        self.assertEqual(town.state["businesses"]["open_count"], 0)
        # Week window must survive the closed pricing day (may gain yesterday's log row).
        carried = system._week_stats["one-mug-tea"]
        self.assertGreaterEqual(len(carried), 6)
        self.assertTrue(all(avail == cap for _, avail in carried[:6]))
        self.assertFalse(
            any(
                e["kind"] == "price_change" and e["shop_id"] == "one-mug-tea"
                for e in town.events
            )
        )
        self.assertEqual(
            town.state["businesses"]["shops"]["one-mug-tea"]["price_cents"], base
        )
        # Next pricing day with sun: carried stats still drive a bump.
        town.day = 14
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "spring"}
        system.tick(town)
        tea = town.state["businesses"]["shops"]["one-mug-tea"]
        self.assertEqual(tea["price_cents"], base + (base * 5) // 100)
        self.assertEqual(system._week_stats["one-mug-tea"], [])
        tea_changes = [
            e
            for e in town.events
            if e["kind"] == "price_change" and e["shop_id"] == "one-mug-tea"
        ]
        self.assertTrue(tea_changes)
        self.assertEqual(tea_changes[-1]["reason"], "bump")

    def test_prices_always_within_bounds_over_90_days(self):
        _, snapshots, _, town = run_businesses(
            seed=42, days=90, with_weather=True, with_residents=True
        )
        for day, snap in enumerate(snapshots, start=1):
            # snapshots don't store prices; re-check final + scan events
            pass
        for shop_id, shop in town.state["businesses"]["shops"].items():
            lo, hi = price_bounds_cents(shop_id)
            self.assertGreaterEqual(shop["price_cents"], lo, msg=shop_id)
            self.assertLessEqual(shop["price_cents"], hi, msg=shop_id)
        for event in town.events:
            if event["kind"] != "price_change":
                continue
            lo, hi = price_bounds_cents(event["shop_id"])
            self.assertGreaterEqual(event["new_price_cents"], lo)
            self.assertLessEqual(event["new_price_cents"], hi)

    def test_tick_makes_zero_rng_draws(self):
        town = FakeTown(seed=42)
        system = System()
        system.setup(town)
        _seed_residents(town, staff_pairs=[])
        town.state["weather"] = {"condition": "sun", "temp_c": 18.0, "season": "spring"}
        draws = {"n": 0}
        real_random = town.rng.random

        def counted_random():
            draws["n"] += 1
            return real_random()

        town.rng.random = counted_random
        # Also wrap common Random methods businesses might call.
        for name in ("randint", "randrange", "choice", "choices", "uniform", "gauss"):
            if not hasattr(town.rng, name):
                continue
            orig = getattr(town.rng, name)

            def wrapper(*args, _orig=orig, **kwargs):
                draws["n"] += 1
                return _orig(*args, **kwargs)

            setattr(town.rng, name, wrapper)

        for day in range(1, 15):
            town.day = day
            before = draws["n"]
            system.tick(town)
            self.assertEqual(
                draws["n"], before, msg=f"rng draws on day {day}"
            )

    def test_pricing_deterministic_same_seed(self):
        def prices(seed):
            town = FakeTown(seed=seed)
            system = System()
            system.setup(town)
            _seed_residents(town)
            for day in range(1, 91):
                town.day = day
                town.state["weather"] = {
                    "condition": "sun",
                    "temp_c": 20.0,
                    "season": "summer",
                }
                system.tick(town)
                # identical daily purchases so sell-through is deterministic
                units = 20
                price = town.state["businesses"]["shops"]["one-mug-tea"]["price_cents"]
                town.state["residents"]["purchases"] = {"one-mug-tea": units}
                town.state["residents"]["spent_cents"] = {"one-mug-tea": units * price}
                town._current_system = "economy"
                town.emit("daily")
                town._current_system = "businesses"
            return {
                sid: town.state["businesses"]["shops"][sid]["price_cents"]
                for sid in SHOP_IDS
            }

        self.assertEqual(prices(42), prices(42))


class Phase4TaxBillTests(unittest.TestCase):
    """Sales tax, rent, licence, arrears — no RNG, no overdraft."""

    def test_setup_exposes_tax_bill_keys(self):
        town = FakeTown()
        System().setup(town)
        state = town.state["businesses"]
        self.assertEqual(state["taxes_paid_cents"], 0)
        self.assertEqual(state["bills_paid_cents"], 0)
        self.assertEqual(state["arrears_cents"], 0)
        for shop in state["shops"].values():
            self.assertEqual(shop["tax_arrears_cents"], 0)
            self.assertEqual(shop["bill_arrears_cents"], 0)

    def test_sales_tax_helper(self):
        from nori.shops import sales_tax_cents

        self.assertEqual(sales_tax_cents(1000), 50)
        self.assertEqual(sales_tax_cents(0), 0)
        self.assertEqual(sales_tax_cents(-5), 0)

    def test_open_day_pays_rent_and_licence(self):
        from nori.shops import COMMERCIAL_RENT_CENTS, LICENCE_UTILITIES_CENTS

        town = FakeTown()
        system = System()
        system.setup(town)
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "summer"}
        town.day = 1
        system.tick(town)
        state = town.state["businesses"]
        # Six open shops × ($8 rent + $2 licence)
        self.assertEqual(
            state["bills_paid_cents"],
            6 * (COMMERCIAL_RENT_CENTS + LICENCE_UTILITIES_CENTS),
        )
        self.assertEqual(state["taxes_paid_cents"], 0)
        self.assertEqual(state["arrears_cents"], 0)

    def test_storm_skips_rent_and_licence(self):
        town = FakeTown()
        system = System()
        system.setup(town)
        town.state["weather"] = {"condition": "storm", "temp_c": 5.0, "season": "spring"}
        town.day = 1
        system.tick(town)
        state = town.state["businesses"]
        self.assertEqual(state["open_count"], 0)
        self.assertEqual(state["bills_paid_cents"], 0)
        self.assertEqual(state["arrears_cents"], 0)

    def test_missed_shop_bill_goes_to_arrears_then_clears(self):
        from nori.shops import COMMERCIAL_RENT_CENTS, LICENCE_UTILITIES_CENTS

        town = FakeTown()
        system = System()
        system.setup(town)
        shop = town.state["businesses"]["shops"]["fold-post"]
        # Exactly overhead: can open, but rent+licence unpaid → arrears.
        shop["balance_cents"] = SHOP_PARAMS["fold-post"]["overhead_cents"]
        town.state["weather"] = {"condition": "sun", "temp_c": 20.0, "season": "summer"}
        town.day = 1
        system.tick(town)
        shop = town.state["businesses"]["shops"]["fold-post"]
        self.assertTrue(shop["open"])
        missed = [e for e in town.events if e["kind"] == "missed_shop_bill"]
        self.assertTrue(missed)
        due = COMMERCIAL_RENT_CENTS + LICENCE_UTILITIES_CENTS
        self.assertEqual(shop["bill_arrears_cents"], due)
        self.assertEqual(town.state["businesses"]["arrears_cents"], due)
        self.assertEqual(shop["balance_cents"], 0)

        # Next day with cash: arrears paid first.
        shop["balance_cents"] = due + SHOP_PARAMS["fold-post"]["overhead_cents"] + due
        town.day = 2
        system.tick(town)
        shop = town.state["businesses"]["shops"]["fold-post"]
        self.assertEqual(shop["bill_arrears_cents"], 0)
        self.assertEqual(shop["tax_arrears_cents"], 0)
        self.assertEqual(town.state["businesses"]["arrears_cents"], 0)

    def test_balances_never_negative_with_taxes(self):
        _, snapshots, _, town = run_businesses(
            seed=42, days=90, with_weather=True, with_residents=True
        )
        for day, snap in enumerate(snapshots, start=1):
            for shop_id, bal in snap["balances"].items():
                self.assertGreaterEqual(bal, 0, msg=f"day {day} {shop_id}")
        self.assertGreaterEqual(town.state["businesses"]["arrears_cents"], 0)
        self.assertGreaterEqual(town.state["businesses"]["taxes_paid_cents"], 0)
        self.assertGreaterEqual(town.state["businesses"]["bills_paid_cents"], 0)


if __name__ == "__main__":
    unittest.main()
