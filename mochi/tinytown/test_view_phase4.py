"""Phase 4 keys (taxes, bills, rent, arrears) in the day view and the map. All optional."""

import copy
import unittest

from mochi.tinytown import map as town_map
from mochi.tinytown import view
from mochi.tinytown.test_view import fake_state
from mochi.tinytown.test_view_phase3 import GOLDEN_DAY_42


def phase4_state():
    """fake_state() once residents and shops pay: Ben and Di are behind, and so is Fold Post."""
    state = fake_state()
    arrears = {1: 0, 2: 600, 3: 0, 4: 150}
    for person in state["residents"]["people"]:
        person["arrears_cents"] = arrears[person["id"]]
    state["residents"].update(
        taxes_paid_cents=1234, bills_paid_cents=180, rent_paid_cents=1800, arrears_cents=750, in_arrears=2
    )
    state["businesses"]["shops"]["fold-post"]["arrears_cents"] = 800
    state["businesses"]["shops"]["one-mug-tea"]["arrears_cents"] = 0
    state["businesses"].update(taxes_paid_cents=50, bills_paid_cents=200, rent_paid_cents=800, arrears_cents=800)
    return state


def lines_from(text, label):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(label))
    return lines[start : start + 3]


class ViewerBillsTest(unittest.TestCase):
    def test_no_phase4_keys_matches_main_exactly(self):
        self.assertEqual(view.render(fake_state(), 42), GOLDEN_DAY_42)

    def test_bills_panel_with_every_key(self):
        self.assertEqual(
            lines_from(view.render(phase4_state(), 42), "BILLS TODAY"),
            [
                "BILLS TODAY  residents: tax $12.34 | utilities $1.80 | rent $18.00",
                "             shops:     tax $0.50 | licence $2.00 | rent $8.00",
                "             behind:    residents 2 ($7.50 owed) | shops 1 ($8.00 owed)",
            ],
        )

    def test_panel_only_adds_lines(self):
        text = view.render(phase4_state(), 42)
        self.assertEqual(len(text.splitlines()), len(GOLDEN_DAY_42.splitlines()) + 4)

    def test_missing_keys_show_na(self):
        state = fake_state()
        state["residents"]["taxes_paid_cents"] = 99  # residents started paying, shops not yet
        self.assertEqual(
            lines_from(view.render(state, 42), "BILLS TODAY"),
            [
                "BILLS TODAY  residents: tax $0.99 | utilities n/a | rent n/a",
                "             shops:     tax n/a | licence n/a | rent n/a",
                "             behind:    residents n/a (n/a owed) | shops n/a (n/a owed)",
            ],
        )

    def test_odd_values_show_na_and_never_raise(self):
        state = fake_state()
        state["residents"].update(taxes_paid_cents="lots", in_arrears=True, arrears_cents=None)
        state["businesses"].update(rent_paid_cents={"fold-post": "?"})
        panel = lines_from(view.render(state, 42), "BILLS TODAY")
        self.assertIn("tax n/a", panel[0])
        self.assertIn("rent n/a", panel[1])
        self.assertIn("residents n/a (n/a owed)", panel[2])

    def test_render_does_not_mutate_phase4_state(self):
        state = phase4_state()
        before = copy.deepcopy(state)
        view.render(state, 1)
        self.assertEqual(state, before)


class MapArrearsTest(unittest.TestCase):
    def page(self, state):
        return town_map.render_html(town_map.snapshot(state), day=42, seed=7)

    def test_households_and_shops_behind_get_a_red_dot(self):
        page = self.page(phase4_state())
        self.assertEqual(page.count('class="behind"'), 3)  # Ben, Di and Fold Post
        self.assertIn('data-shop-behind="fold-post"', page)
        self.assertNotIn('data-shop-behind="one-mug-tea"', page)
        self.assertIn("owes $8.00", page)
        self.assertIn("2 households, 1 shop behind", page)

    def test_street_notes_count_households_behind(self):
        streets = {s["name"]: s for s in town_map.snapshot(phase4_state())["streets"]}
        self.assertEqual((streets["Elm"]["behind"], streets["Oak"]["behind"]), ([False, True], [False, True]))
        self.assertIn("1 behind", self.page(phase4_state()))

    def test_before_phase4_the_map_is_unchanged(self):
        page = self.page(fake_state())
        self.assertNotIn('class="behind"', page)
        self.assertNotIn("behind", page.split("<svg", 1)[0])
        self.assertNotIn("behind on payments", page)

    def test_phase4_without_per_entity_keys_says_na(self):
        state = fake_state()
        state["residents"]["taxes_paid_cents"] = 10
        page = self.page(state)
        self.assertNotIn('class="behind"', page)
        self.assertIn("behind n/a", page)


if __name__ == "__main__":
    unittest.main()
