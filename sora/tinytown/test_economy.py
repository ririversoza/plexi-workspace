import random
import unittest

from sora.tinytown import SHOPS, System


class FakeTown:
    """Just enough of the Town interface from juniper/TINYTOWN.md."""

    def __init__(self, seed=42):
        self.day = 0
        self.rng = random.Random(seed)
        self.state = {}
        self.events = []

    def emit(self, kind, **data):
        self.events.append({"day": self.day, "system": "economy", "kind": kind, **data})


def run(days=90, weather=None, others=None):
    town = FakeTown()
    economy = System()
    economy.setup(town)
    for day in range(1, days + 1):
        town.day = day
        if weather is not None:
            town.state["weather"] = {"condition": weather(day)}
        if others is not None:
            town.state.update(others(day))
        economy.tick(town)
        yield town


def final(**kwargs):
    *_, town = run(**kwargs)
    return town


class EconomyTest(unittest.TestCase):
    def test_same_seed_same_state(self):
        a, b = final(), final()
        self.assertEqual(a.state, b.state)
        self.assertEqual(a.events, b.events)

    def test_runs_alone_without_weather(self):
        town = final()
        self.assertNotIn("weather", town.state)
        self.assertEqual(town.state["economy"]["shops_open"], SHOPS)

    def test_bounds_every_day(self):
        storm_every_third = lambda day: "storm" if day % 3 == 0 else "sun"
        for town in run(weather=storm_every_third):
            eco = town.state["economy"]
            self.assertGreaterEqual(eco["population"], 0)
            self.assertTrue(0 <= eco["employed"] <= eco["population"])
            self.assertTrue(0 <= eco["shops_open"] <= SHOPS)
            self.assertGreaterEqual(eco["treasury"], 0)

    def test_storm_closes_shops(self):
        town = final(days=1, weather=lambda day: "storm")
        self.assertEqual(town.state["economy"]["shops_open"], 0)
        self.assertEqual(town.events[0]["kind"], "shops_closed")

    def test_treasury_never_overdrafts(self):
        town = FakeTown()
        economy = System()
        economy.setup(town)
        town.state["economy"]["treasury"] = 0.0
        town.state["weather"] = {"condition": "storm"}
        for _ in range(30):
            economy.tick(town)
            self.assertGreaterEqual(town.state["economy"]["treasury"], 0)
        self.assertIn("budget_shortfall", [e["kind"] for e in town.events])


class EconomyV2Test(unittest.TestCase):
    RESIDENTS = {"residents": {"count": 120, "employed": 102}}
    BUSINESSES = {"businesses": {"open_count": 4}}

    def test_reads_residents_and_businesses(self):
        town = final(days=1, others=lambda day: {**self.RESIDENTS, **self.BUSINESSES})
        eco = town.state["economy"]
        self.assertEqual((eco["population"], eco["employed"], eco["shops_open"]), (120, 102, 4))

    def test_no_rng_draws_when_both_present(self):
        town = final(days=5, others=lambda day: {**self.RESIDENTS, **self.BUSINESSES})
        self.assertEqual(town.rng.random(), random.Random(42).random())

    def test_businesses_own_storm_closures(self):
        town = final(days=1, weather=lambda day: "storm", others=lambda day: self.BUSINESSES)
        self.assertEqual(town.state["economy"]["shops_open"], 4)
        self.assertNotIn("shops_closed", [e["kind"] for e in town.events])

    def test_residents_only_falls_back_for_shops(self):
        town = final(days=1, others=lambda day: self.RESIDENTS)
        eco = town.state["economy"]
        self.assertEqual((eco["population"], eco["employed"], eco["shops_open"]), (120, 102, SHOPS))

    def test_businesses_only_falls_back_for_people(self):
        with_shops = final(others=lambda day: self.BUSINESSES).state["economy"]
        phase1 = final().state["economy"]
        self.assertEqual(with_shops["population"], phase1["population"])
        self.assertEqual(with_shops["employed"], phase1["employed"])
        self.assertEqual(with_shops["shops_open"], 4)

    def test_missing_or_bad_keys_fall_back(self):
        town = final(days=1, others=lambda day: {"residents": {"count": "lots"}, "businesses": {}})
        eco = town.state["economy"]
        self.assertTrue(0 <= eco["employed"] <= eco["population"])
        self.assertEqual(eco["shops_open"], SHOPS)

    def test_employed_capped_at_population(self):
        town = final(days=1, others=lambda day: {"residents": {"count": 10, "employed": 50}})
        self.assertEqual(town.state["economy"]["employed"], 10)

    def test_treasury_never_overdrafts_with_residents(self):
        broke = lambda day: {"residents": {"count": 120, "employed": 0}, "businesses": {"open_count": 0}}
        for town in run(others=broke):
            self.assertGreaterEqual(town.state["economy"]["treasury"], 0)
        self.assertIn("budget_shortfall", [e["kind"] for e in town.events])


if __name__ == "__main__":
    unittest.main()
