import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

from mochi.tinytown import map as town_map

try:
    HAS_ENGINE = importlib.util.find_spec("taro.tinytown") is not None
except ImportError:
    HAS_ENGINE = False


def shop(name, balance_cents, is_open=True):
    return {"name": name, "open": is_open, "balance_cents": balance_cents, "price_cents": 100}


def town_state():
    return {
        "businesses": {
            "shops": {
                "rich": shop("Rich Shop", 50_000),
                "broke": shop("Broke Shop", 0),
                "shut": shop("Shut Shop", 12_000, is_open=False),
            }
        },
        "residents": {
            "people": [
                {"id": 1, "street": "Maple Street"},
                {"id": 2, "street": "Maple Street"},
                {"id": 3, "street": "Willow Way"},
            ]
        },
        "emergency": {
            "incidents_by_street": {"Maple Street": 0, "Willow Way": 2, "Clover Lane": 1},
            "busiest_street": "Willow Way",
        },
        "traffic": {"congestion": 0.25, "accidents_today": 1},
        "weather": {"condition": "rain"},
    }


class SnapshotTest(unittest.TestCase):
    def test_streets_merge_homes_and_incidents_in_name_order(self):
        snap = town_map.snapshot(town_state())
        self.assertEqual(
            snap["streets"],
            [
                {"name": "Clover Lane", "homes": 0, "incidents": 1, "busiest": False},
                {"name": "Maple Street", "homes": 2, "incidents": 0, "busiest": False},
                {"name": "Willow Way", "homes": 1, "incidents": 2, "busiest": True},
            ],
        )

    def test_shops_keep_state_order_and_fields(self):
        shops = town_map.snapshot(town_state())["shops"]
        self.assertEqual([s["id"] for s in shops], ["rich", "broke", "shut"])
        self.assertEqual(shops[2], {"id": "shut", "name": "Shut Shop", "balance_cents": 12_000, "open": False})

    def test_empty_town_has_no_shops_or_streets(self):
        snap = town_map.snapshot({})
        self.assertEqual((snap["shops"], snap["streets"]), ([], []))

    def test_malformed_values_are_skipped_not_crashed(self):
        state = {
            "businesses": {"shops": {"x": "nope", "y": shop("Y", "lots")}},
            "residents": {"people": ["nobody", {"street": None}]},
            "emergency": {"incidents_by_street": {"Elm": True, "Oak": 3}},
        }
        snap = town_map.snapshot(state)
        self.assertEqual([(s["id"], s["balance_cents"]) for s in snap["shops"]], [("y", None)])
        self.assertEqual([(s["name"], s["incidents"]) for s in snap["streets"]], [("Elm", 0), ("Oak", 3)])


class BalanceColourTest(unittest.TestCase):
    def test_red_at_zero_or_below_green_at_top(self):
        self.assertEqual(town_map.balance_hue(0, 50_000), 0)
        self.assertEqual(town_map.balance_hue(-500, 50_000), 0)
        self.assertEqual(town_map.balance_hue(50_000, 50_000), 120)
        self.assertEqual(town_map.balance_hue(25_000, 50_000), 60)

    def test_unknown_balance_has_no_hue(self):
        self.assertIsNone(town_map.balance_hue(None, 50_000))

    def test_all_broke_town_stays_red(self):
        self.assertEqual(town_map.balance_hue(0, 0), 0)


class RenderTest(unittest.TestCase):
    def render(self, state=None):
        return town_map.render_html(town_map.snapshot(state if state is not None else town_state()), day=12, seed=7)

    def test_page_is_self_contained_and_themed(self):
        page = self.render()
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("prefers-color-scheme: dark", page)
        self.assertIn('name="viewport"', page)
        self.assertIn("<svg", page)
        for banned in ("<script", "http://", "https://", "<link", "<img", "@import"):
            self.assertNotIn(banned, page)

    def test_labels_every_shop_street_and_the_day(self):
        page = self.render()
        for text in ("Rich Shop", "Broke Shop", "Shut Shop", "Maple Street", "Willow Way", "Clover Lane", "Day 12", "seed 7"):
            self.assertIn(text, page)
        self.assertIn("$500.00", page)
        self.assertIn("closed", page)

    def test_broke_shop_is_red_and_richest_is_green(self):
        page = self.render()
        self.assertIn('data-shop="broke" style="fill:hsl(0 ', page)
        self.assertIn('data-shop="rich" style="fill:hsl(120 ', page)

    def test_incident_streets_highlighted_and_busiest_marked(self):
        page = self.render()
        self.assertIn('class="road hot" data-street="Willow Way"', page)
        self.assertIn('class="road hot" data-street="Clover Lane"', page)
        self.assertIn('class="road" data-street="Maple Street"', page)
        self.assertIn("busiest", page)

    def test_one_home_per_resident(self):
        self.assertEqual(self.render().count('class="home"'), 3)

    def test_names_are_escaped(self):
        state = town_state()
        state["businesses"]["shops"]["rich"]["name"] = "<b>&</b>"
        page = self.render(state)
        self.assertNotIn("<b>&</b>", page)
        self.assertIn("&lt;b&gt;&amp;&lt;/b&gt;", page)

    def test_empty_town_still_renders(self):
        page = self.render({})
        self.assertIn("no shops yet", page)
        self.assertIn("no streets yet", page)


class CliTest(unittest.TestCase):
    def run_cli(self, argv):
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            town_map.main(argv)
        return caught.exception.code

    def test_out_is_required(self):
        self.assertEqual(self.run_cli([]), 2)

    def test_rejects_out_of_range_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("0", "91", "soon"):
                self.assertEqual(self.run_cli(["--out", os.path.join(tmp, "m.html"), "--day", bad]), 2)

    def test_rejects_bad_out_before_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli(["--out", os.path.join(tmp, "missing", "m.html")]), 2)
            self.assertEqual(self.run_cli(["--out", tmp]), 2)
            self.assertEqual(self.run_cli(["--out", " "]), 2)
            self.assertEqual(os.listdir(tmp), [])


@unittest.skipUnless(HAS_ENGINE, "taro.tinytown engine not installed")
class RunWithEngineTest(unittest.TestCase):
    def test_writes_only_out_and_defaults_to_last_day(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(town_map.main(["--out", "town.html"]), 0)
            finally:
                os.chdir(cwd)
            self.assertEqual(os.listdir(tmp), ["town.html"])
            with open(os.path.join(tmp, "town.html"), encoding="utf-8") as f:
                page = f.read()
        self.assertIn(f"Day {town_map.DAYS}", page)
        self.assertEqual(page.count('class="home"'), 120)

    def test_same_seed_same_map(self):
        self.assertEqual(town_map.capture(30, seed=5), town_map.capture(30, seed=5))

    def test_mapping_draws_nothing_from_town_rng(self):
        from mochi.tinytown import view

        def run(with_map):
            def on_day(town):
                if with_map:
                    before = town.rng.getstate()
                    town_map.snapshot(town.state)
                    self.assertEqual(town.rng.getstate(), before)

            town = view.run_engine(on_day, days=20, seed=3)
            return town.rng.getstate(), town.events

        self.assertEqual(run(True), run(False))


if __name__ == "__main__":
    unittest.main()
