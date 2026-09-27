import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from mochi.tinytown import history, view
from mochi.tinytown.history import CHART_COLUMNS, CHART_ROWS, DayPoint

try:
    HAS_ENGINE = importlib.util.find_spec("taro.tinytown") is not None
except ImportError:  # the parent "taro" package itself is missing
    HAS_ENGINE = False

DAYS = 90


def fake_state(day, balance, open_=True, condition="sun"):
    """One day of synthetic state with a single shop."""
    return {
        "weather": {"condition": condition},
        "businesses": {"shops": {"fold-post": {"name": "Fold Post", "open": open_, "balance_cents": balance}}},
    }


def fake_frames(days=DAYS):
    """A shop that dips to $0 on days 20-22 and is storm-closed every 10th day."""
    frames = []
    for day in range(1, days + 1):
        balance = 0 if 20 <= day <= 22 else 50000 + day * 1000
        storm = day % 10 == 0
        state = fake_state(day, balance, open_=not storm, condition="storm" if storm else "sun")
        frames.append((day, history.snapshot(state, day)))
    return frames


def grid_rows(text):
    """The plot rows: the lines holding a '|' y-axis."""
    return [line.split("|", 1)[1] for line in text.splitlines() if " |" in line]


class SnapshotTest(unittest.TestCase):
    def test_storm_closed_needs_storm_and_closed(self):
        cases = [("storm", False, True), ("storm", True, False), ("rain", False, False)]
        for condition, open_, expected in cases:
            shops = history.snapshot(fake_state(1, 100, open_, condition), 1)
            self.assertEqual(shops["fold-post"][1].storm_closed, expected, (condition, open_))

    def test_zero_balance_is_flagged(self):
        self.assertTrue(history.snapshot(fake_state(1, 0), 1)["fold-post"][1].at_zero)
        self.assertFalse(history.snapshot(fake_state(1, 1), 1)["fold-post"][1].at_zero)

    def test_missing_or_odd_businesses(self):
        self.assertIsNone(history.snapshot({}, 1))
        self.assertIsNone(history.snapshot(None, 1))
        self.assertEqual(history.snapshot({"businesses": {"shops": "x"}}, 1), {})
        odd = history.snapshot({"businesses": {"shops": {"a": {"balance_cents": "lots"}, "b": 7}}}, 1)
        self.assertEqual(list(odd), ["a"])
        self.assertIsNone(odd["a"][1].balance_cents)


class ChartBoundsTest(unittest.TestCase):
    def setUp(self):
        self.name, self.points = history.series_for(fake_frames(), "fold-post")
        self.text = history.chart("fold-post", self.name, self.points, DAYS, 42)

    def test_grid_is_exactly_rows_by_columns(self):
        rows = grid_rows(self.text)
        self.assertEqual(len(rows), CHART_ROWS)
        self.assertTrue(all(len(row) == CHART_COLUMNS for row in rows))

    def test_one_point_per_column_and_nothing_else(self):
        rows = grid_rows(self.text)
        for col in range(CHART_COLUMNS):
            column = [row[col] for row in rows]
            self.assertEqual(column.count(history.POINT), 1, col)
            self.assertEqual(set(column) - {history.POINT, " "}, set())

    def test_max_on_top_row_and_zero_on_bottom_row(self):
        rows = grid_rows(self.text)
        last_col = history.column_of(DAYS, DAYS)
        zero_col = history.column_of(21, DAYS)
        self.assertEqual(rows[0][last_col], history.POINT)
        self.assertEqual(rows[-1][zero_col], history.POINT)

    def test_labels_and_summary(self):
        lines = self.text.splitlines()
        self.assertEqual(lines[0], "Fold Post (fold-post) balance, days 1-90, seed 42")
        self.assertTrue(lines[1].strip().startswith("$1,400.00 |"))
        self.assertIn("min $0.00 (day 20)  max $1,400.00 (day 90)  final $1,400.00 (day 90)", self.text)
        self.assertIn("storm-closed days: 9  $0 days: 3", self.text)

    def test_marker_rows_line_up_with_days(self):
        lines = self.text.splitlines()
        offset = history.Y_LABEL_WIDTH + 2
        storm = next(line for line in lines if line.strip().startswith("storm "))[offset:]
        zero = next(line for line in lines if line.strip().startswith("$0 "))[offset:]
        self.assertEqual(len(storm), CHART_COLUMNS)
        storm_cols = {history.column_of(day, DAYS) for day in range(10, DAYS + 1, 10)}
        self.assertEqual({i for i, c in enumerate(storm) if c == history.STORM_MARK}, storm_cols)
        zero_cols = {history.column_of(day, DAYS) for day in (20, 21, 22)}
        self.assertEqual({i for i, c in enumerate(zero) if c == history.ZERO_MARK}, zero_cols)

    def test_every_chart_line_fits_the_width(self):
        width = history.Y_LABEL_WIDTH + 2 + CHART_COLUMNS
        for line in self.text.splitlines()[1:-2]:
            self.assertLessEqual(len(line.rstrip()), width + len("  day"), line)

    def test_day_to_column_mapping_spans_the_chart(self):
        columns = [history.column_of(day, DAYS) for day in range(1, DAYS + 1)]
        self.assertEqual((columns[0], columns[-1]), (0, CHART_COLUMNS - 1))
        self.assertEqual(columns, sorted(columns))
        self.assertEqual(set(columns), set(range(CHART_COLUMNS)))

    def test_level_is_clamped(self):
        self.assertEqual(history.level_of(-5, 100), 0)
        self.assertEqual(history.level_of(500, 100), CHART_ROWS - 1)
        self.assertEqual(history.level_of(10, 0), 0)


class ChartEdgeCasesTest(unittest.TestCase):
    def test_all_zero_balances_sit_on_the_bottom_row(self):
        points = [DayPoint(day, 0, False, True) for day in range(1, DAYS + 1)]
        rows = grid_rows(history.chart("x", "X", points, DAYS, 42))
        self.assertEqual(rows[-1], history.POINT * CHART_COLUMNS)
        self.assertTrue(all(set(row) == {" "} for row in rows[:-1]))

    def test_no_data_and_gaps_never_raise(self):
        self.assertIn("no balance data", history.chart("x", "X", [], DAYS, 42))
        points = [DayPoint(1, None, False, False), DayPoint(50, 1200, False, False)]
        text = history.chart("x", "X", points, DAYS, 42)
        self.assertEqual(len(grid_rows(text)), CHART_ROWS)
        self.assertIn("final $12.00 (day 50)", text)

    def test_known_shops_prefers_contract_order(self):
        frames = [(1, {"zed": None, "fold-post": None}), (2, None), (3, {"one-mug-tea": None})]
        self.assertEqual(history.known_shops(frames, view.SHOP_IDS), ["one-mug-tea", "fold-post", "zed"])


class HistoryCliWithoutEngineTest(unittest.TestCase):
    """Drive run_history with a stand-in engine so these run with no taro installed."""

    def fake_engine(self, states):
        def run_engine(on_day, days=DAYS, seed=42):
            for day, state in enumerate(states, start=1):
                on_day(SimpleNamespace(day=day, state=state))
        return mock.patch.object(view, "run_engine", run_engine)

    def test_businesses_not_built_is_graceful(self):
        with self.fake_engine([{"weather": {"condition": "sun"}}] * 3):
            text, code = view.run_history("all")
        self.assertEqual(code, 0)
        self.assertIn(view.NOT_BUILT, text)

    def test_unknown_shop_lists_known_ids(self):
        with self.fake_engine([fake_state(1, 100)]):
            text, code = view.run_history("nope")
        self.assertEqual(code, 2)
        self.assertIn("fold-post", text)

    def test_shop_missing_on_some_days_still_charts(self):
        states = [fake_state(1, 100), {}, fake_state(3, 300)]
        with self.fake_engine(states):
            text, code = view.run_history("fold-post", days=3)
        self.assertEqual(code, 0)
        self.assertIn("final $3.00 (day 3)", text)

    def test_cli_flags(self):
        for argv in (["--history", "all", "--day", "3"], ["--history", "all", "--every"], ["--seed", "x"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                view.main(argv)


@unittest.skipUnless(HAS_ENGINE, "taro.tinytown engine not installed")
class HistoryWithEngineTest(unittest.TestCase):
    def test_same_seed_same_chart(self):
        self.assertEqual(view.run_history("all"), view.run_history("all"))

    def test_seed_changes_the_chart(self):
        body = lambda seed: view.run_history("all", seed=seed)[0].split("\n", 1)[1]
        self.assertNotEqual(body(42), body(7))

    def test_all_draws_every_installed_shop(self):
        text, code = view.run_history("all")
        self.assertEqual(code, 0)
        headers = [line for line in text.splitlines() if "balance, days 1-90, seed 42" in line]
        self.assertGreaterEqual(len(headers), 1)

    def test_viewer_makes_no_rng_draws(self):
        from taro.tinytown import SYSTEM_MODULES, run_town

        plain = run_town(view.load_systems(SYSTEM_MODULES), seed=42)
        watched = view.run_engine(lambda town: history.snapshot(town.state, town.day), seed=42)
        self.assertEqual(plain.rng.getstate(), watched.rng.getstate())

    def test_history_writes_no_files_in_cwd(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(view.main(["--history", "all"]), 0)
            finally:
                os.chdir(cwd)
            self.assertEqual(os.listdir(tmp), [])


def flat_points(values):
    return [DayPoint(day, value, False, value == 0) for day, value in enumerate(values, start=1)]


class ReviewRegressionTest(unittest.TestCase):
    """Edge cases from Bao's review of the history chart."""

    def column_of_char(self, lines, char, predicate):
        return {line.index(char) for line in lines if predicate(line)}

    def test_huge_balances_keep_every_row_aligned(self):
        text = history.chart("x", "X", flat_points([10**15] * 45 + [3 * 10**14] * 45), DAYS, 42)
        lines = text.splitlines()
        bars = self.column_of_char(lines, "|", lambda line: " |" in line)
        axis = self.column_of_char(lines, "+", lambda line: line.strip().startswith("+"))
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars, axis)
        marker_start = bars.pop() + 1  # grid cells start right after the "|"
        for label in ("storm", "$0"):
            row = next(line for line in lines if line.split()[:1] == [label] and "|" not in line)
            self.assertEqual(len(row[marker_start:]), CHART_COLUMNS, label)
            self.assertEqual(row[:marker_start].strip(), label)
        self.assertIn("$10,000,000,000,000.00 |", text)

    def test_normal_balances_keep_the_default_width(self):
        text = history.chart("x", "X", flat_points([1000] * DAYS), DAYS, 42)
        self.assertTrue(all(line.index("|") == history.Y_LABEL_WIDTH + 1 for line in text.splitlines() if " |" in line))

    def test_negative_balances_get_their_own_range(self):
        values = [5000 - day * 100 for day in range(DAYS)]  # $50.00 down to -$39.00
        text = history.chart("x", "X", flat_points(values), DAYS, 42)
        rows = grid_rows(text)
        self.assertLess(rows[-1].count(history.POINT), CHART_COLUMNS // CHART_ROWS + 2)  # not a flat $0 line
        levels = [next(r for r, row in enumerate(rows) if row[col] == history.POINT) for col in range(CHART_COLUMNS)]
        self.assertEqual(levels, sorted(levels))  # a steady decline, top to bottom
        self.assertEqual(len(set(levels)), CHART_ROWS)  # uses the whole height
        self.assertEqual((levels[0], levels[-1]), (0, CHART_ROWS - 1))
        self.assertTrue(text.splitlines()[CHART_ROWS].strip().startswith("-$39.00 |"))
        self.assertIn("min -$39.00 (day 90)", text)
        self.assertEqual(history.value_range(flat_points(values)), (-3900, 5000))

    def test_value_range_always_includes_zero(self):
        self.assertEqual(history.value_range(flat_points([200, 300])), (0, 300))
        self.assertEqual(history.value_range(flat_points([-5, -2])), (-5, 0))

    def test_enormous_values_never_overflow(self):
        self.assertEqual(history.cents(10**400).replace(",", ""), "$1" + "0" * 398 + ".00")
        self.assertTrue(history.cents(10**400).endswith(".00"))
        text = history.chart("x", "X", flat_points([10**400, 10**399, 0]), DAYS, 42)
        self.assertEqual(len(grid_rows(text)), CHART_ROWS)
        self.assertEqual(history.level_of(10**400, 10**400), CHART_ROWS - 1)

    def test_cents_formatting(self):
        self.assertEqual(history.cents(-5), "-$0.05")
        self.assertEqual(history.cents(123456), "$1,234.56")
        self.assertEqual(history.cents(12.6), "$0.13")
        for bad in (float("inf"), float("nan"), True, None, "5"):
            self.assertEqual(history.cents(bad), "?", bad)

    def test_non_finite_balances_are_treated_as_missing(self):
        state = {"businesses": {"shops": {"a": {"balance_cents": float("nan")}, "b": {"balance_cents": float("inf")}}}}
        shops = history.snapshot(state, 1)
        self.assertIsNone(shops["a"][1].balance_cents)
        self.assertIsNone(shops["b"][1].balance_cents)


if __name__ == "__main__":
    unittest.main()
