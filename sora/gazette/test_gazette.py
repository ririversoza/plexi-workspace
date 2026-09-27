import contextlib
import io
import os
import tempfile
import unittest

from taro.tinytown import run_town
from sora.gazette import (
    DAYS,
    NOT_REPORTED,
    WEEKS,
    collect,
    headline,
    load_systems,
    main,
    render,
    snapshot,
    week_number,
    week_of,
)


def day(n, **state):
    return {"day": n, **state}


def paper(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(argv)
    return out.getvalue()


class FullTownTest(unittest.TestCase):
    def test_same_output_every_run(self):
        self.assertEqual(paper(["--all"]), paper(["--all"]))

    def test_all_prints_every_week(self):
        self.assertEqual(paper(["--all"]).count("THE TINY TOWN GAZETTE"), WEEKS)

    def test_read_only(self):
        plain = run_town(load_systems())
        watched = run_town(load_systems(), on_day=snapshot)
        self.assertEqual(plain.rng.getstate(), watched.rng.getstate())
        self.assertEqual(plain.events, watched.events)
        self.assertEqual({k: v for k, v in plain.state.items() if k != "log"},
                         {k: v for k, v in watched.state.items() if k != "log"})

    def test_writes_no_files(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as scratch:
            os.chdir(scratch)
            try:
                paper(["--week", "1"])
                self.assertEqual(os.listdir(scratch), [])
            finally:
                os.chdir(cwd)


class WeekBoundsTest(unittest.TestCase):
    def test_weeks_cover_every_day_once(self):
        days = [day(n) for n in range(1, DAYS + 1)]
        covered = [d["day"] for w in range(1, WEEKS + 1) for d in week_of(days, w)]
        self.assertEqual(covered, list(range(1, DAYS + 1)))

    def test_last_week_is_short(self):
        self.assertIn("Days 85-90", paper(["--week", str(WEEKS)]))

    def test_rejects_out_of_range_weeks(self):
        for bad in ("0", str(WEEKS + 1), "x"):
            with self.assertRaises(Exception):
                week_number(bad)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["--week", "0"])


class MissingSystemsTest(unittest.TestCase):
    def test_zero_systems(self):
        text = render(*collect([]), range(1, WEEKS + 1))
        self.assertEqual(text.count("QUIET WEEK IN TINY TOWN"), WEEKS)
        for section in ("Weather:", "Shops:", "Wallets:", "Traffic:", "Emergency:"):
            self.assertIn(f"{section} {NOT_REPORTED}", text)

    def test_weather_only(self):
        weather = [s for s in load_systems() if s.name == "weather"]
        text = render(*collect(weather), [1])
        self.assertNotIn(f"Weather: {NOT_REPORTED}", text)
        self.assertIn(f"Shops: {NOT_REPORTED}", text)

    def test_malformed_state(self):
        for days in (
            [day(1, businesses={"shops": {"one-mug-tea": None}}, residents={"purchases": "lots"})],
            [day(1, businesses={"shops": ["one-mug-tea"]}, weather="storm", traffic={"congestion": "high"})],
        ):
            self.assertIn("Week 1", render(days, [], [1]))


class HeadlineTest(unittest.TestCase):
    def test_accident_spike_comes_first(self):
        days = [day(n, traffic={"accidents_today": 2}, weather={"condition": "storm"}) for n in range(1, 5)]
        self.assertEqual(headline(days, []), "ACCIDENT SPIKE: 8 CRASHES ON TOWN ROADS")

    def test_storm_closures(self):
        events = [{"day": 2, "kind": "shops_closed", "reason": "storm"}]
        self.assertEqual(headline([day(1), day(2)], events), "STORM SHUTS EVERY SHOP ON 1 DAY")

    def test_treasury_drop_and_big_gain(self):
        before = day(0, economy={"treasury": 500.0})
        self.assertEqual(headline([day(1, economy={"treasury": 490.0})], [], before), "TREASURY DOWN $10.00")
        self.assertEqual(headline([day(1, economy={"treasury": 600.0})], [], before), "TREASURY UP $100.00")

    def test_best_seller(self):
        days = [day(1, economy={"treasury": 1.0}, residents={"purchases": {"fold-post": 3, "matcha-mile": 3}},
                    businesses={"shops": {"fold-post": {"name": "Fold Post"}}})]
        self.assertEqual(headline(days, []), "FOLD POST TOPS SALES WITH 3 UNITS")

    def test_quiet_week(self):
        self.assertEqual(headline([], []), "QUIET WEEK IN TINY TOWN")


if __name__ == "__main__":
    unittest.main()
