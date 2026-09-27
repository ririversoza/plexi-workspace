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


class TaxesTest(unittest.TestCase):
    """Phase 4: the treasury collects what residents and businesses actually paid today."""

    PEOPLE = {"count": 120, "employed": 102}

    def day_one(self, residents=None, businesses=None):
        others = {"residents": {**self.PEOPLE, **(residents or {})}, "businesses": {"open_count": 4, **(businesses or {})}}
        return final(days=1, others=lambda day: others).state["economy"]

    def test_fallback_is_the_old_conjured_formula(self):
        eco = self.day_one()
        self.assertEqual((eco["tax_income"], eco["utility_income"]), (102 * 1.0 + 4 * 5.0, 0.0))
        self.assertEqual(eco["treasury"], 1000.0 + 122.0 - 120.0 - 2.0)  # income, upkeep, park instalment

    def test_real_taxes_and_bills_replace_the_formula(self):
        eco = self.day_one(
            residents={"taxes_paid_cents": 1234, "bills_paid_cents": 18000},
            businesses={"taxes_paid_cents": {"fold-post": 105, "matcha-mile": 0}, "bills_paid_cents": 800},
        )
        self.assertEqual((eco["tax_income"], eco["utility_income"]), (13.39, 188.0))
        self.assertEqual(eco["treasury"], 946.39)  # 1000 + 201.39 - 120 upkeep - 18 x 7.50 benefits

    def test_each_source_falls_back_on_its_own(self):
        residents_only = self.day_one(residents={"taxes_paid_cents": 500, "bills_paid_cents": 0})
        self.assertEqual((residents_only["tax_income"], residents_only["utility_income"]), (5.0 + 4 * 5.0, 0.0))
        shops_only = self.day_one(businesses={"taxes_paid_cents": 0, "bills_paid_cents": 200})
        self.assertEqual((shops_only["tax_income"], shops_only["utility_income"]), (102.0, 2.0))

    def test_nothing_paid_means_no_income(self):
        zero = {"taxes_paid_cents": 0, "bills_paid_cents": 0}
        eco = self.day_one(residents=zero, businesses=zero)
        self.assertEqual((eco["tax_income"], eco["utility_income"]), (0.0, 0.0))
        self.assertEqual(eco["treasury"], 745.0)  # 1000 - 120 upkeep - 135 benefits; no project below the reserve

    def test_malformed_amounts_count_as_zero_never_conjured(self):
        for bad in (-500, True, "500", 5.5, None, [500], {"a": -1, "b": "x"}):
            eco = self.day_one(residents={"taxes_paid_cents": bad}, businesses={"bills_paid_cents": bad})
            self.assertEqual((eco["tax_income"], eco["utility_income"]), (0.0, 0.0), bad)

    def test_cents_are_summed_before_converting(self):
        eco = self.day_one(residents={"taxes_paid_cents": 10, "bills_paid_cents": 1}, businesses={"taxes_paid_cents": 20})
        self.assertEqual((eco["tax_income"], eco["utility_income"]), (0.3, 0.01))

    def test_treasury_gets_exactly_what_was_paid(self):
        """Conservation: over 90 days the treasury moves by what was paid in, minus upkeep and benefits, to the cent."""
        paid = lambda day: {
            "residents": {**self.PEOPLE, "taxes_paid_cents": 1000 + day, "bills_paid_cents": 28000 - day},
            "businesses": {"open_count": 6, "taxes_paid_cents": {"a": 37 * day}, "bills_paid_cents": 1200},
        }
        with mock.patch("sora.tinytown.PROJECTS", ()):
            towns = [town.state["economy"] for town in run(others=paid)]
        received = sum(1000 + d + 28000 - d + 37 * d + 1200 for d in range(1, 91))
        benefits = sum(eco["benefits_paid_cents"] for eco in towns)
        self.assertEqual(benefits, 90 * 18 * 750)  # never short here
        self.assertEqual(round(towns[-1]["treasury"] * 100), 100_000 + received - 90 * 120 * 100 - benefits)

    def test_no_rng_draws_and_no_overdraft_with_real_keys(self):
        zero = {"taxes_paid_cents": 0, "bills_paid_cents": 0}
        broke = lambda day: {"residents": {"count": 120, "employed": 0, **zero}, "businesses": {"open_count": 0, **zero}}
        for town in run(others=broke):
            self.assertGreaterEqual(town.state["economy"]["treasury"], 0)
        self.assertEqual(town.rng.random(), random.Random(42).random())
        self.assertIn("budget_shortfall", [e["kind"] for e in town.events])

    def test_benefits_paid_per_unemployed_resident(self):
        eco = self.day_one(residents={"taxes_paid_cents": 0})
        self.assertEqual((eco["benefits_paid_cents"], eco["benefit_per_head_cents"]), (18 * 750, 750))

    def test_no_benefits_without_phase4_residents(self):
        self.assertEqual(self.day_one()["benefits_paid_cents"], 0)  # nobody would credit them
        self.assertEqual(self.day_one(businesses={"taxes_paid_cents": 0})["benefits_paid_cents"], 0)

    def test_short_treasury_pays_everyone_the_same_whole_cents(self):
        town = FakeTown()
        economy = System()
        economy.setup(town)
        town.state["economy"]["treasury"] = 120.0 + 100.0  # upkeep, then $100 for 18 people
        town.state["residents"] = {**self.PEOPLE, "taxes_paid_cents": 0, "bills_paid_cents": 0}
        town.state["businesses"] = {"open_count": 6, "taxes_paid_cents": 0, "bills_paid_cents": 0}
        economy.tick(town)
        eco = town.state["economy"]
        self.assertEqual((eco["benefit_per_head_cents"], eco["benefits_paid_cents"]), (555, 18 * 555))
        self.assertEqual(eco["treasury"], 0.1)  # 10 cents can't be split 18 ways
        self.assertIn({"needed_cents": 13500, "paid_cents": 9990},
                      [{k: e[k] for k in ("needed_cents", "paid_cents")} for e in town.events if e["kind"] == "benefits_short"])

    def test_setup_exposes_the_new_keys(self):
        town = FakeTown()
        System().setup(town)
        self.assertEqual((town.state["economy"]["tax_income"], town.state["economy"]["utility_income"]), (0.0, 0.0))


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
