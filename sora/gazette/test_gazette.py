import contextlib
import io
import os
import tempfile
import unittest

from taro.tinytown import run_town
from sora.gazette.edition import path, price_series, render_html
from sora.gazette import (
    DAYS,
    NOT_REPORTED,
    WEEKS,
    collect,
    headline,
    shop_table,
    load_systems,
    main,
    render,
    render_week,
    snapshot,
    week_number,
    week_of,
    weather_line,
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


    def test_known_zero_sales_print_zero(self):
        shops = {"one-mug-tea": {"name": "One Mug Tea", "open": True, "balance_cents": 100}}
        days = [day(n, residents={"purchases": {}}, businesses={"shops": shops}) for n in range(1, 8)]
        self.assertRegex(shop_table(days)[1], r"^One Mug Tea\s+7d\s+0\s")

    def test_missing_sales_print_question_mark(self):
        shops = {"one-mug-tea": {"name": "One Mug Tea", "open": True, "balance_cents": 100}}
        self.assertRegex(shop_table([day(1, businesses={"shops": shops})])[1], r"\s\?\s")

    def test_malformed_weather_falls_back(self):
        for weather in ({"condition": []}, {"condition": {}}, {}, {"condition": 3}, []):
            self.assertEqual(weather_line([day(1, weather=weather)]), f"Weather: {NOT_REPORTED}")
        mixed = [day(1, weather={"condition": []}), day(2, weather={"condition": "sun"})]
        self.assertEqual(weather_line(mixed), "Weather: 1 sun")


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


def phase2_week(extra=lambda n: {}):
    """Seven days with only Phase 2 keys; ``extra(n)`` merges more state into day n."""
    shops = {"one-mug-tea": {"name": "One Mug Tea", "open": True, "balance_cents": 50000}}
    days = []
    for n in range(1, 8):
        state = {
            "weather": {"condition": "sun", "temp_c": 10 + n},
            "businesses": {"shops": shops, "open_count": 1},
            "residents": {"count": 3, "avg_wallet_cents": 1000 + n, "purchases": {"one-mug-tea": 2}},
            "economy": {"treasury": 1000.0},
            "traffic": {"accidents_today": 0, "congestion": 0.25},
            "emergency": {"incidents_today": 1, "responded": 1},
        }
        for system, keys in extra(n).items():
            state[system] = {**state[system], **keys}
        days.append(day(n, **state))
    return days


# Rendered by the gazette before Phase 3 sections existed (#36); must not change.
PHASE2_GOLDEN = (
    "============================================================\n"
    "       THE TINY TOWN GAZETTE  |  Week 1  |  Days 1-7        \n"
    "============================================================\n"
    "ONE MUG TEA TOPS SALES WITH 14 UNITS\n"
    "------------------------------------------------------------\n"
    "Weather: 7 sun | 11 to 17 C\n"
    "\n"
    "Shop                       Open  Sold      Balance\n"
    "One Mug Tea                  7d    14      $500.00\n"
    "\n"
    "Wallets: 3 residents, average $10.07 (+$0.06 this week)\n"
    "Traffic: 0 accidents, congestion 25% | Emergency: 7 incidents, 7 responded"
)


class Phase3SectionsTest(unittest.TestCase):
    def issue(self, extra=lambda n: {}, events=(), before=None):
        return render_week(phase2_week(extra), list(events), 1, before)

    def test_week_without_new_keys_is_byte_identical(self):
        self.assertEqual(self.issue(), PHASE2_GOLDEN)

    def test_town_hall(self):
        building = self.issue(lambda n: {"economy": {"project": {"name": "park", "progress": 0.9999}, "projects_completed": []}})
        self.assertIn("Town Hall: building park (99%)", building)
        for progress, shown in ((0.58, "58%"), (0.999999999, "99%")):  # 0.58 * 100 == 57.999...
            text = self.issue(lambda n: {"economy": {"project": {"name": "park", "progress": progress}}})
            self.assertIn(f"Town Hall: building park ({shown})", text)
        done = self.issue(lambda n: {"economy": {"project": None, "projects_completed": ["park"] if n >= 3 else []}})
        self.assertIn("Town Hall: park completed", done)
        idle = self.issue(lambda n: {"economy": {"project": None, "projects_completed": ["park"]}},
                          before=day(0, economy={"projects_completed": ["park"]}))
        self.assertIn("Town Hall: no project under way", idle)
        self.assertNotIn("Town Hall", self.issue())

    def test_mood(self):
        text = self.issue(lambda n: {"residents": {"avg_mood": 50 + n, "mood_bands": {"happy": n, "ok": 3 - n // 7}}})
        self.assertIn("Mood of the town: 57 average (+6 this week) | happy 7 (+6), ok 2 (-1)", text)
        self.assertNotIn("Mood of the town", self.issue())

    def test_prices(self):
        move = {"day": 7, "kind": "price_change", "shop_id": "one-mug-tea", "old_price_cents": 325, "new_price_cents": 309}
        self.assertIn("Prices: One Mug Tea $3.25 -> $3.09", self.issue(events=[move]))
        self.assertNotIn("Prices", self.issue(events=[{**move, "kind": "daily"}]))

    def test_busiest_street(self):
        streets = lambda n: {"emergency": {"incidents_by_street": {"Willow Way": 1, "Clover Lane": 1, "Maple Street": 0}}}
        self.assertIn("Streets: busiest for incidents was Clover Lane (7)", self.issue(streets))  # tie: alphabetical
        quiet = lambda n: {"emergency": {"incidents_by_street": {"Willow Way": 0}}}
        self.assertIn("Streets: no incidents on any street", self.issue(quiet))
        self.assertNotIn("Streets:", self.issue())

    def test_bus_days(self):
        bus = lambda n: {"traffic": {"bus_running": n <= 2, "bus_riders": 15 if n <= 2 else 0}}
        self.assertIn("congestion 25%, bus ran 2 days (30 riders) |", self.issue(bus))
        self.assertIn("congestion 25%, no bus |", self.issue(lambda n: {"traffic": {"bus_running": False}}))
        self.assertNotIn("bus", self.issue())

    def test_taxes_and_bills(self):
        self.assertNotIn("Taxes & bills", self.issue())
        paid = lambda n: {"economy": {"tax_income": 1.5, "utility_income": 180.25}}
        self.assertIn("Taxes & bills: treasury took $10.50 in taxes and $1,261.75 in utilities\n", self.issue(paid))
        dimes = self.issue(lambda n: {"economy": {"tax_income": 0.1 if n <= 3 else None, "utility_income": 0.0}})
        self.assertIn("treasury took $0.30 in taxes", dimes)  # not $0.30000000000000004 or $0.31

    def test_taxes_and_bills_arrears(self):
        shops = {"one-mug-tea": {"name": "One Mug Tea", "open": True, "balance_cents": 0, "arrears_cents": 800},
                 "fold-post": {"name": "Fold Post", "open": True, "balance_cents": 0, "arrears_cents": 0}}
        behind = lambda n: {"economy": {"tax_income": 1.0, "utility_income": 1.0},
                            "residents": {"in_arrears": 2, "arrears_cents": 1200}, "businesses": {"shops": shops}}
        self.assertIn("in utilities | 2 residents behind ($12.00 owed) | 1 shop behind ($8.00 owed)\n", self.issue(behind))
        paid_up = {sid: {**shop, "arrears_cents": 0} for sid, shop in shops.items()}
        clear = lambda n: {"economy": {"tax_income": 1.0, "utility_income": 1.0},
                           "residents": {"in_arrears": 1, "arrears_cents": 0}, "businesses": {"shops": paid_up}}
        self.assertIn("in utilities | 1 resident behind | 0 shops behind\n", self.issue(clear))

    def test_taxes_and_bills_in_html(self):
        days = phase2_week(lambda n: {"economy": {"tax_income": 1.0, "utility_income": 2.0}})
        self.assertIn("Taxes &amp; bills:</span> treasury took $7.00 in taxes and $14.00 in utilities", render_html(days, [], [1]))

    def test_project_completion_headline_comes_first(self):
        days = [day(n, traffic={"accidents_today": 2}, economy={"projects_completed": ["park"] if n == 4 else []})
                for n in range(1, 5)]
        self.assertEqual(headline(days, []), "TOWN OPENS NEW PARK")

    def test_mood_swing_headline(self):
        storm = [{"day": 2, "kind": "shops_closed", "reason": "storm"}]
        big = [day(1, residents={"avg_mood": 60}), day(2, residents={"avg_mood": 50})]
        self.assertEqual(headline(big, storm), "TOWN MOOD SINKS 10 POINTS")
        small = [day(1, residents={"avg_mood": 60}), day(2, residents={"avg_mood": 51})]
        self.assertEqual(headline(small, storm), "STORM SHUTS EVERY SHOP ON 1 DAY")


class HtmlEditionTest(unittest.TestCase):
    def page(self, days, events=()):
        return render_html(days, list(events), [1])

    def test_full_page_is_self_contained(self):
        page = paper(["--html"])
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertEqual(page.count("<article"), WEEKS)
        self.assertIn("The Tiny Town Gazette", page)
        self.assertIn("prefers-color-scheme:dark", page)
        self.assertIn('name="viewport"', page)
        for outside in ("<script", "http://", "https://", "<link", "url(", " src=", "<img"):
            self.assertNotIn(outside, page)

    def test_out_writes_only_that_file(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = os.path.join(scratch, "gazette.html")
            self.assertEqual(paper(["--html", "--week", "2", "--out", out]), f"Wrote {out}\n")
            self.assertEqual(os.listdir(scratch), ["gazette.html"])
            with open(out, encoding="utf-8") as page:
                self.assertEqual(page.read().count("<article"), 1)

    def test_out_needs_html(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["--out", "x.html"])

    def test_state_text_is_escaped(self):
        days = phase2_week(lambda n: {"businesses": {"shops": {"x": {"name": "<b>Tea & Co</b>", "open": True}}}})
        page = self.page(days)
        self.assertIn("&lt;b&gt;Tea &amp; Co&lt;/b&gt;", page)
        self.assertNotIn("<b>", page)

    def test_sparklines_follow_their_keys(self):
        self.assertNotIn('class="tile"', self.page(phase2_week()))
        shops = lambda n: {"one-mug-tea": {"name": "One Mug Tea", "price_cents": 300 if n < 7 else 330}}
        page = self.page(phase2_week(lambda n: {"residents": {"avg_mood": 50 + n}, "businesses": {"shops": shops(n)}}))
        self.assertEqual(page.count('class="tile"'), 2)
        self.assertIn('<div class="value">57<span class="delta">+6 this week', page)
        self.assertIn('<div class="value">110.0%<span class="delta">+10.0 pts this week', page)

    def test_price_series_is_relative_to_each_shops_first_price(self):
        days = [
            day(1, businesses={"shops": {"a": {"price_cents": 100}, "free": {"price_cents": 0}}}),
            day(2),
            day(3, businesses={"shops": {"a": {"price_cents": 120}, "b": {"price_cents": 50}}}),
        ]
        self.assertEqual(price_series(days), [(1, 100.0), (2, None), (3, 110.0)])

    def test_sparkline_breaks_at_gaps(self):
        self.assertEqual(path([(0, 1), None, (2, 3), (4, 5)]), "M0.0 1.0 M2.0 3.0 L4.0 5.0")


if __name__ == "__main__":
    unittest.main()
