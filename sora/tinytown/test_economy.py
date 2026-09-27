import random
import unittest
from unittest import mock

from sora.tinytown import PROJECT_RESERVE, PROJECTS, SHOPS, System


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


class PublicWorksTest(unittest.TestCase):
    SUN = staticmethod(lambda day: "sun")

    def kinds(self, town):
        return [(e["kind"], e.get("name")) for e in town.events if e["kind"].startswith("project")]

    def test_setup_has_no_project(self):
        town = FakeTown()
        System().setup(town)
        self.assertIsNone(town.state["economy"]["project"])
        self.assertEqual(town.state["economy"]["projects_completed"], [])

    def test_builds_the_list_in_order(self):
        town = final(weather=self.SUN)
        names = [name for name, _ in PROJECTS]
        self.assertEqual(town.state["economy"]["projects_completed"], names)
        self.assertIsNone(town.state["economy"]["project"])
        expected = [(kind, name) for name in names for kind in ("project_started", "project_completed")]
        self.assertEqual(self.kinds(town), expected)

    def test_progress_and_reserve_every_day(self):
        for town in run(weather=self.SUN):
            eco = town.state["economy"]
            self.assertGreaterEqual(eco["treasury"], PROJECT_RESERVE)  # sunny days never dip
            if eco["project"] is not None:
                self.assertTrue(0 <= eco["project"]["progress"] < 1)

    def test_nothing_starts_at_or_below_reserve(self):
        town = FakeTown()
        economy = System()
        economy.setup(town)
        town.state["economy"]["treasury"] = 0.0
        town.state["weather"] = {"condition": "storm"}
        for _ in range(10):
            economy.tick(town)
            self.assertLessEqual(town.state["economy"]["treasury"], PROJECT_RESERVE)
        self.assertEqual(self.kinds(town), [])

    def test_only_treasury_changes(self):
        weather = lambda day: "storm" if day % 5 == 0 else "sun"
        with mock.patch("sora.tinytown.PROJECTS", ()):
            base = final(weather=weather)
        works = final(weather=weather)
        self.assertEqual(base.rng.getstate(), works.rng.getstate())
        before, after = base.state["economy"], works.state["economy"]
        for key in ("population", "employed", "shops_open"):
            self.assertEqual(before[key], after[key])
        spent = sum(cost for name, cost in PROJECTS if name in after["projects_completed"])
        spent += (after["project"] or {}).get("paid", 0.0)
        self.assertAlmostEqual(before["treasury"] - spent, after["treasury"], places=2)

    def test_progress_stays_below_one_until_paid(self):
        town = FakeTown()
        economy = System()
        economy.setup(town)
        town.state["weather"] = {"condition": "storm"}
        town.state["residents"] = {"count": 0, "employed": 0}
        town.state["businesses"] = {"open_count": 0}
        town.state["economy"].update(
            treasury=PROJECT_RESERVE + 19.99,
            project={"name": "market square", "cost": 400.0, "paid": 380.0, "progress": 0.95},
        )
        economy.tick(town)
        project = town.state["economy"]["project"]
        self.assertEqual(project["paid"], 399.99)
        self.assertLess(project["progress"], 1.0)
        self.assertNotIn("market square", town.state["economy"]["projects_completed"])

    def test_tolerates_state_without_project_keys(self):
        town = FakeTown()
        economy = System()
        economy.setup(town)
        for key in ("project", "projects_completed"):
            del town.state["economy"][key]
        economy.tick(town)
        self.assertIn("projects_completed", town.state["economy"])


if __name__ == "__main__":
    unittest.main()
