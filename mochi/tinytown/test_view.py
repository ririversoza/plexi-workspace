import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

from mochi.tinytown import view

try:
    HAS_ENGINE = importlib.util.find_spec("taro.tinytown") is not None
except ImportError:  # the parent "taro" package itself is missing
    HAS_ENGINE = False


def fake_state():
    """A day of Phase 2 state shaped like juniper/TINYTOWN.md (synthetic values)."""
    return {
        "weather": {"condition": "rain", "temp_c": 7.44, "season": "spring"},
        "businesses": {
            "shops": {
                "fold-post": {
                    "name": "Fold Post", "open": True, "price_cents": 800, "available": 5,
                    "balance_cents": 53860, "sold_yesterday": 2, "staff": [3],
                },
                "one-mug-tea": {
                    "name": "One Mug Tea", "open": False, "price_cents": 325, "available": 0,
                    "balance_cents": 0, "sold_yesterday": 0, "staff": [1, 2],
                },
            },
            "open_count": 1,
            "wages_paid": {3: 1500},
            "pending_revenue_cents": {"fold-post": 1600},
        },
        "residents": {
            "people": [
                {"id": 1, "name": "Ada Ash", "street": "Elm", "job": "one-mug-tea", "wallet_cents": 500},
                {"id": 2, "name": "Ben Bell", "street": "Elm", "job": "one-mug-tea", "wallet_cents": 9000},
                {"id": 3, "name": "Cy Chen", "street": "Oak", "job": "fold-post", "wallet_cents": 9000},
                {"id": 4, "name": "Di Dale", "street": "Oak", "job": None, "wallet_cents": 120},
            ],
            "purchases": {"fold-post": 2},
            "spent_cents": {"fold-post": 1600},
            "count": 4, "employed": 3, "avg_wallet_cents": 4655,
        },
        "economy": {"population": 4, "employed": 3, "treasury": 1036.5, "shops_open": 1},
        "traffic": {"commuters": 81, "congestion": 0.2025, "accidents_today": 0},
        "emergency": {"incidents_today": 2, "responded": 2, "avg_response_min": 10.49, "open_incidents": 0},
    }


class RenderMissingSystemsTest(unittest.TestCase):
    def test_empty_state_shows_every_panel_as_not_built(self):
        text = view.render({}, 1)
        for label in ("WEATHER", "STOREFRONTS", "RESIDENTS", "traffic:", "emergency:", "treasury:"):
            line = next(line for line in text.splitlines() if label in line)
            self.assertIn(view.NOT_BUILT, line, label)

    def test_phase_one_state_renders_without_businesses_or_residents(self):
        state = fake_state()
        del state["businesses"], state["residents"]
        text = view.render(state, 5)
        self.assertIn(f"STOREFRONTS  {view.NOT_BUILT}", text)
        self.assertIn(f"RESIDENTS  {view.NOT_BUILT}", text)
        self.assertIn("WEATHER  rain  7.4C  spring", text)
        self.assertIn("treasury:  $1,036.50", text)

    def test_businesses_without_residents_uses_ids_and_sold_yesterday(self):
        state = fake_state()
        del state["residents"]
        text = view.render(state, 5)
        self.assertIn("#3", text)
        self.assertIn("sold 2", text)
        self.assertIn(f"RESIDENTS  {view.NOT_BUILT}", text)

    def test_malformed_values_never_raise(self):
        state = {
            "weather": {"temp_c": "warm"},
            "businesses": {"shops": {"odd-shop": {"price_cents": None, "staff": None}, "x": "nope"}},
            "residents": {"people": [None, {"id": 9, "wallet_cents": True}, {"name": "No Wallet"}]},
            "economy": {"treasury": None},
            "traffic": {"congestion": "jammed"},
            "emergency": {},
        }
        text = view.render(state, 1)
        self.assertIn("odd-shop", text)
        self.assertIn("no staff", text)
        self.assertIn("treasury:  ?", text)

    def test_non_dict_state_renders_empty_town(self):
        self.assertIn(view.NOT_BUILT, view.render(None, 1))


class RenderFullTownTest(unittest.TestCase):
    def setUp(self):
        self.text = view.render(fake_state(), 42)

    def test_title_and_weather(self):
        self.assertIn("Day 42 / 90", self.text.splitlines()[0])
        self.assertIn("WEATHER  rain  7.4C  spring", self.text)

    def test_storefronts_show_status_price_sold_balance_and_staff_names(self):
        self.assertIn("STOREFRONTS  1 open", self.text)
        self.assertIn("OPEN    $8.00 each", self.text)
        self.assertIn("CLOSED  $3.25 each", self.text)
        self.assertIn("sold 2", self.text)
        self.assertIn("bal $538.60", self.text)
        self.assertIn("bal $0.00", self.text)
        for name in ("Ada Ash", "Ben Bell", "Cy Chen"):
            self.assertIn(name, self.text)

    def test_shops_follow_contract_order(self):
        self.assertLess(self.text.index("One Mug Tea"), self.text.index("Fold Post"))

    def test_boxes_are_aligned(self):
        box_lines = [line for line in self.text.splitlines() if line.startswith(("|", "+"))]
        self.assertTrue(box_lines)
        self.assertEqual(len({len(line) for line in box_lines}), 1)

    def test_residents_panel_and_top_wallets_break_ties_by_id(self):
        self.assertIn("RESIDENTS  4 people | 3 employed | avg wallet $46.55", self.text)
        self.assertIn("1. Ben Bell $90.00  2. Cy Chen $90.00  3. Ada Ash $5.00", self.text)

    def test_ticker(self):
        self.assertIn("81 commuters, congestion 20%, 0 accidents", self.text)
        self.assertIn("2 incidents, 2 responded, avg 10.5 min, 0 open", self.text)
        self.assertIn("treasury:  $1,036.50", self.text)

    def test_render_does_not_mutate_state(self):
        state = fake_state()
        view.render(state, 1)
        self.assertEqual(state, fake_state())


class HelpersTest(unittest.TestCase):
    def test_fit_pads_and_truncates_to_width(self):
        self.assertEqual(view.fit("abc", 5), "abc  ")
        self.assertEqual(view.fit("abcdefgh", 6), "abc...")

    def test_staff_overflow_is_summarised(self):
        self.assertEqual(view.staff_lines([1, 2, 3], {1: "A"}), ["A", "+2 more"])
        self.assertEqual(view.staff_lines([], {}), ["no staff", ""])

    def test_load_systems_skips_missing_and_disables_log_csv(self):
        systems = view.load_systems({"log": "mochi.tinytown", "ghost": "no_such_pkg.tinytown"})
        self.assertEqual([s.name for s in systems], ["log"])
        self.assertIsNone(systems[0].csv_path)

    def test_cli_rejects_out_of_range_day(self):
        for bad in ("0", "91", "soon"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                view.main(["--day", bad])

    def test_cli_rejects_day_with_every(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            view.main(["--day", "3", "--every"])


@unittest.skipUnless(HAS_ENGINE, "taro.tinytown engine not installed")
class RunWithEngineTest(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(view.main(argv), 0)
        return out.getvalue()

    def test_default_draws_day_90_and_writes_no_csv(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                text = self.run_cli([])
            finally:
                os.chdir(cwd)
            self.assertEqual(os.listdir(tmp), [])
        self.assertIn("Day 90 / 90", text)
        self.assertNotIn("Day 89 /", text)

    def test_every_draws_all_days_in_order(self):
        text = self.run_cli(["--every"])
        titles = [line for line in text.splitlines() if "Tiny Town | Day" in line]
        self.assertEqual(len(titles), view.DAYS)
        self.assertIn("Day 1 / 90", titles[0])
        self.assertIn("Day 90 / 90", titles[-1])

    def test_same_seed_same_picture(self):
        self.assertEqual(view.run(17), view.run(17))

    def test_single_day_matches_every_frame(self):
        self.assertEqual(view.run(30)[0], view.run(None)[29])


if __name__ == "__main__":
    unittest.main()
