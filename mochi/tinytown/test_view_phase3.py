"""Phase 3 keys in the day view: mood, price arrows, Town Hall projects, bus. All optional."""

import copy
import unittest

from mochi.tinytown import view
from mochi.tinytown.test_view import fake_state

# render(fake_state(), 42) as drawn by main before Phase 3 (generated from origin/main's view.py).
GOLDEN_DAY_42 = """\
============================== Tiny Town | Day 42 / 90 ===============================
WEATHER  rain  7.4C  spring

STOREFRONTS  1 open
+--------------------------+ +--------------------------+
| One Mug Tea              | | Fold Post                |
| CLOSED  $3.25 each       | | OPEN    $8.00 each       |
| sold 0                   | | sold 2                   |
| bal $0.00                | | bal $538.60              |
|   Ada Ash                | |   Cy Chen                |
|   Ben Bell               | |                          |
+--------------------------+ +--------------------------+

RESIDENTS  4 people | 3 employed | avg wallet $46.55
  top wallets: 1. Ben Bell $90.00  2. Cy Chen $90.00  3. Ada Ash $5.00

TICKER   traffic:   81 commuters, congestion 20%, 0 accidents
         emergency: 2 incidents, 2 responded, avg 10.5 min, 0 open
         treasury:  $1,036.50
======================================================================================"""


def with_keys(system, **keys):
    state = fake_state()
    state[system].update(keys)
    return state


def line_with(text, needle):
    return next((line for line in text.splitlines() if needle in line), None)


class ByteIdenticalTest(unittest.TestCase):
    def test_no_phase3_keys_matches_main_exactly(self):
        self.assertEqual(view.render(fake_state(), 42), GOLDEN_DAY_42)

    def test_all_phase3_keys_only_add_lines_or_suffixes(self):
        state = fake_state()
        state["residents"].update(avg_mood=58, mood_bands={"happy": 2, "ok": 1, "unhappy": 1})
        state["businesses"]["shops"]["fold-post"]["price_cents"] = 840
        state["economy"].update(project="Park", projects_completed=1)
        state["traffic"].update(bus_running=True, bus_riders=12)
        text = view.render(state, 42)
        self.assertEqual(len(text.splitlines()), len(GOLDEN_DAY_42.splitlines()) + 2)

    def test_render_does_not_mutate_phase3_state(self):
        state = with_keys("residents", avg_mood=50, mood_bands={"ok": 4})
        before = copy.deepcopy(state)
        view.render(state, 1)
        self.assertEqual(state, before)


class MoodTest(unittest.TestCase):
    def test_avg_and_bands_in_contract_order(self):
        state = with_keys("residents", avg_mood=58, mood_bands={"unhappy": 19, "happy": 56, "ok": 45})
        self.assertEqual(line_with(view.render(state, 1), "mood:"), "  mood: avg 58/100 | happy 56 | ok 45 | unhappy 19")

    def test_only_one_key_shows_na_for_the_other(self):
        only_avg = view.render(with_keys("residents", avg_mood=40), 1)
        self.assertEqual(line_with(only_avg, "mood:"), "  mood: avg 40/100 | bands n/a")
        only_bands = view.render(with_keys("residents", mood_bands={"ok": 4}), 1)
        self.assertEqual(line_with(only_bands, "mood:"), "  mood: avg n/a | ok 4")

    def test_odd_values_never_raise(self):
        state = with_keys("residents", avg_mood="grumpy", mood_bands=["happy"])
        self.assertEqual(line_with(view.render(state, 1), "mood:"), "  mood: avg n/a | bands n/a")

    def test_absent_means_no_mood_line(self):
        self.assertIsNone(line_with(view.render(fake_state(), 1), "mood:"))


class PriceArrowTest(unittest.TestCase):
    def status_line(self, state, shop_name="Fold Post"):
        rows = view.render(state, 1).splitlines()
        index = next(i for i, row in enumerate(rows) if shop_name in row)
        col = rows[index].index(shop_name)
        return rows[index + 1][col:col + view.BOX_INNER]

    def set_price(self, cents, **extra):
        state = fake_state()
        state["businesses"]["shops"]["fold-post"].update(price_cents=cents, **extra)
        return state

    def test_above_base_is_up_below_is_down_equal_is_blank(self):
        self.assertEqual(self.status_line(self.set_price(840)).rstrip(), "OPEN    $8.40 each ↑")
        self.assertEqual(self.status_line(self.set_price(760)).rstrip(), "OPEN    $7.60 each ↓")
        self.assertEqual(self.status_line(self.set_price(800)).rstrip(), "OPEN    $8.00 each")

    def test_state_base_price_wins_over_catalog(self):
        self.assertIn("↓", self.status_line(self.set_price(800, base_price_cents=900)))

    def test_unknown_shop_or_price_gets_no_arrow(self):
        self.assertEqual(view.price_arrow("mystery-shop", {"price_cents": 999}), "")
        self.assertEqual(view.price_arrow("fold-post", {"price_cents": None}), "")
        self.assertEqual(view.price_arrow("fold-post", {}), "")

    def test_widest_arrow_still_fits_the_box(self):
        state = fake_state()
        state["businesses"]["shops"]["bench-and-bell"] = {"name": "Bench & Bell", "open": False, "price_cents": 862500}
        box_lines = [line for line in view.render(state, 1).splitlines() if line.startswith(("|", "+"))]
        self.assertEqual(len({len(line) for line in box_lines}), 1)


class TownHallTest(unittest.TestCase):
    def test_string_or_dict_project_with_count(self):
        text = view.render(with_keys("economy", project="Library", projects_completed=2), 1)
        self.assertEqual(line_with(text, "town hall:"), "         town hall: building Library | 2 completed")
        text = view.render(with_keys("economy", project={"name": "Park", "cost_cents": 5}), 1)
        self.assertIn("building Park | completed n/a", text)

    def test_only_count_or_empty_project(self):
        text = view.render(with_keys("economy", projects_completed=3), 1)
        self.assertIn("building n/a | 3 completed", text)
        text = view.render(with_keys("economy", project=None, projects_completed="x"), 1)
        self.assertIn("building n/a | completed n/a", text)

    def test_absent_means_no_town_hall_line(self):
        self.assertIsNone(line_with(view.render(fake_state(), 1), "town hall:"))
        state = fake_state()
        del state["economy"]
        self.assertIsNone(line_with(view.render(state, 1), "town hall:"))


class BusTest(unittest.TestCase):
    def traffic_line(self, **keys):
        return line_with(view.render(with_keys("traffic", **keys), 1), "traffic:")

    def test_running_with_riders(self):
        self.assertTrue(self.traffic_line(bus_running=True, bus_riders=12).endswith(
            "0 accidents, bus running (12 riders)"))

    def test_not_running_and_partial_keys(self):
        self.assertTrue(self.traffic_line(bus_running=False, bus_riders=0).endswith(", no bus (0 riders)"))
        self.assertTrue(self.traffic_line(bus_riders=7).endswith(", bus n/a (7 riders)"))
        self.assertTrue(self.traffic_line(bus_running=True).endswith(", bus running"))
        self.assertTrue(self.traffic_line(bus_running="yes", bus_riders="many").endswith(", bus n/a"))

    def test_absent_means_unchanged_traffic_line(self):
        self.assertTrue(line_with(view.render(fake_state(), 1), "traffic:").endswith("0 accidents"))


if __name__ == "__main__":
    unittest.main()
