"""Tests for the Tiny Town HTML dashboard generator."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import taro.tinytown.dashboard as dash
import taro.tinytown.run as run
from taro.tinytown.dashboard import (
    _series_arrears,
    _series_avg_wallet,
    _series_congestion,
    _series_shop_balances,
    _series_taxes_and_bills,
    _weather_conditions,
    cli,
    collect_timeline,
    load_timeline,
    main,
    parse_args,
    render_html,
    render_seeds_html,
    write_dashboard,
)


def _tiny_timeline() -> dict:
    return {
        "seed": 7,
        "days": 3,
        "systems": ["weather", "businesses", "residents", "traffic"],
        "daily": [
            {
                "day": 1,
                "weather": {"condition": "sun", "temp_c": 20.0, "season": "summer"},
                "traffic": {"commuters": 10, "congestion": 0.2, "accidents_today": 0},
                "businesses": {
                    "fold-post": {
                        "open": True,
                        "price_cents": 500,
                        "available": 4,
                        "balance_cents": 50000,
                        "sold_yesterday": 0,
                    },
                    "one-mug-tea": {
                        "open": True,
                        "price_cents": 400,
                        "available": 8,
                        "balance_cents": 48000,
                        "sold_yesterday": 0,
                    },
                },
                "residents": {"count": 120, "employed": 90, "avg_wallet_cents": 2500},
            },
            {
                "day": 2,
                "weather": {"condition": "rain", "temp_c": 14.0, "season": "summer"},
                "traffic": {"commuters": 12, "congestion": 0.5, "accidents_today": 1},
                "businesses": {
                    "fold-post": {
                        "open": True,
                        "price_cents": 500,
                        "available": 3,
                        "balance_cents": 52000,
                        "sold_yesterday": 2,
                    },
                    "one-mug-tea": {
                        "open": True,
                        "price_cents": 400,
                        "available": 7,
                        "balance_cents": 47000,
                        "sold_yesterday": 1,
                    },
                },
                "residents": {"count": 120, "employed": 90, "avg_wallet_cents": 2600},
            },
            {
                "day": 3,
                "weather": {"condition": "storm", "temp_c": 12.0, "season": "summer"},
                "traffic": {"commuters": 8, "congestion": 0.9, "accidents_today": 2},
                "businesses": {
                    "fold-post": {
                        "open": False,
                        "price_cents": 500,
                        "available": 0,
                        "balance_cents": 51000,
                        "sold_yesterday": 0,
                    },
                    "one-mug-tea": {
                        "open": False,
                        "price_cents": 400,
                        "available": 0,
                        "balance_cents": 46000,
                        "sold_yesterday": 0,
                    },
                },
                "residents": {"count": 120, "employed": 90, "avg_wallet_cents": 2550},
            },
        ],
        "events_by_kind": {"weather.tick": 3},
    }


class DashboardTests(unittest.TestCase):
    def test_parse_requires_out(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args([])
        args = parse_args(["--out", "/tmp/x.html", "--seed", "3"])
        self.assertEqual(args.out, "/tmp/x.html")
        self.assertEqual(args.seed, 3)
        self.assertIsNone(args.from_file)

    def test_imports_schema_helpers_from_run(self) -> None:
        self.assertIs(dash._load_systems, run._load_systems)
        self.assertIs(dash._snapshot_day, run._snapshot_day)
        self.assertIs(dash._count_events_by_kind, run._count_events_by_kind)
        self.assertIs(dash._SHOP_EXPORT_FIELDS, run._SHOP_EXPORT_FIELDS)

    def test_shop_balance_series_gaps_at_front(self) -> None:
        daily = [
            {"day": 1, "businesses": {}},
            {"day": 2, "businesses": {}},
            {
                "day": 3,
                "businesses": {
                    "late-shop": {
                        "open": True,
                        "price_cents": 100,
                        "available": 1,
                        "balance_cents": 500,
                        "sold_yesterday": 0,
                    }
                },
            },
            {
                "day": 4,
                "businesses": {
                    "late-shop": {
                        "open": True,
                        "price_cents": 100,
                        "available": 1,
                        "balance_cents": 600,
                        "sold_yesterday": 0,
                    }
                },
            },
        ]
        series = _series_shop_balances(daily)
        self.assertEqual(series["late-shop"], [None, None, 5.0, 6.0])

    def test_missing_wallet_congestion_weather_are_gaps(self) -> None:
        daily = [
            {"day": 1},
            {
                "day": 2,
                "weather": {"condition": "sun"},
                "traffic": {"congestion": 0.4},
                "residents": {"avg_wallet_cents": 2500},
            },
            {"day": 3, "weather": {}, "traffic": {}, "residents": {}},
        ]
        self.assertEqual(_series_avg_wallet(daily), [None, 25.0, None])
        self.assertEqual(_series_congestion(daily), [None, 0.4, None])
        self.assertEqual(_weather_conditions(daily), ["n/a", "sun", "n/a"])
        html = render_html(
            {"seed": 1, "days": 3, "systems": [], "daily": daily, "events_by_kind": {}}
        )
        self.assertIn("n/a", html)

    def test_cli_out_bad_path_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            cli(["--out", "   "])
        self.assertEqual(ctx.exception.code, 2)

        with self.assertRaises(SystemExit) as ctx2:
            cli(["--out", "/no/such/parent/dash.html"])
        self.assertEqual(ctx2.exception.code, 2)

        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            with self.assertRaises(SystemExit) as ctx3:
                cli(["--out", tmp])
            self.assertEqual(ctx3.exception.code, 2)

    def test_render_html_looks_valid_and_safe(self) -> None:
        html = render_html(_tiny_timeline())
        lower = html.lower()
        self.assertIn("<!doctype html>", lower)
        self.assertIn("<html", lower)
        self.assertIn("</html>", lower)
        self.assertIn("<style>", lower)
        self.assertIn("<svg", lower)
        self.assertIn("prefers-color-scheme", html)
        self.assertIn("Shop balances", html)
        self.assertIn("average wallet", html.lower())
        self.assertIn("Taxes and bills", html)
        self.assertIn("Arrears", html)
        self.assertIn("Weather strip", html)
        self.assertIn("Traffic congestion", html)
        self.assertIn("leaderboard", html.lower())
        self.assertIn("fold-post", html)
        self.assertNotIn("http", lower)
        self.assertNotIn("<script src", lower)
        self.assertNotIn("<script", lower)

    def test_render_deterministic(self) -> None:
        timeline = _tiny_timeline()
        self.assertEqual(render_html(timeline), render_html(timeline))

    def test_write_only_to_out_and_from_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            out = str(Path(tmp) / "dash.html")
            src = str(Path(tmp) / "town.json")
            Path(src).write_text(json.dumps(_tiny_timeline()))
            html = main(out=out, from_file=src)
            self.assertTrue(Path(out).is_file())
            self.assertEqual(Path(out).read_text(), html)
            self.assertEqual(load_timeline(src)["seed"], 7)
            # Only the --out file should be the HTML write target in tmp.
            names = {p.name for p in Path(tmp).iterdir()}
            self.assertEqual(names, {"dash.html", "town.json"})

    def test_collect_timeline_short_run_deterministic(self) -> None:
        a = collect_timeline(seed=42, days=3)
        b = collect_timeline(seed=42, days=3)
        self.assertEqual(a, b)
        self.assertEqual(len(a["daily"]), 3)
        html_a = render_html(a)
        html_b = render_html(b)
        self.assertEqual(html_a, html_b)
        self.assertNotIn("http", html_a.lower())
        self.assertNotIn("<script src", html_a.lower())

    def test_write_dashboard_helper(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            path = str(Path(tmp) / "out.html")
            write_dashboard(path, _tiny_timeline())
            text = Path(path).read_text()
            self.assertIn("<svg", text)

    def test_parse_seeds_flag(self) -> None:
        args = parse_args(["--out", "/tmp/x.html", "--seeds", "1-3"])
        self.assertEqual(list(args.seeds), [1, 2, 3])

    def test_cli_seeds_with_from_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            cli(["--out", "/tmp/x.html", "--seeds", "1-2", "--from", "/tmp/t.json"])
        self.assertEqual(ctx.exception.code, 2)

    def test_render_seeds_html_small_multiples_and_grid(self) -> None:
        rows = [
            {
                "seed": 1,
                "shops_open": 6,
                "max_zero_streak": 0,
                "avg_wallet_cents": 40000,
                "treasury": 1000.0,
                "pass": True,
                "avg_wallet_series_cents": [30000, 35000, 40000],
                "shops_open_series": [6, 6, 6],
            },
            {
                "seed": 2,
                "shops_open": 4,
                "max_zero_streak": 5,
                "avg_wallet_cents": 70000,
                "treasury": 900.0,
                "pass": False,
                "avg_wallet_series_cents": [50000, 60000, 70000],
                "shops_open_series": [6, 5, 4],
            },
        ]
        html = render_seeds_html(rows, days=3, seed_lo=1, seed_hi=2)
        lower = html.lower()
        self.assertIn("<!doctype html>", lower)
        self.assertIn("prefers-color-scheme", html)
        self.assertIn("Average wallet by seed", html)
        self.assertIn("Shops open by seed", html)
        self.assertIn("PASS / FAIL grid", html)
        self.assertIn("1 of 2 seeds pass", html)
        self.assertIn("seed 1", html)
        self.assertIn("seed 2", html)
        self.assertIn("PASS", html)
        self.assertIn("FAIL", html)
        self.assertIn("<svg", lower)
        self.assertIn("multiples", html)
        self.assertNotIn("<script", lower)
        self.assertNotIn("http", lower)
        self.assertEqual(render_seeds_html(rows, days=3, seed_lo=1, seed_hi=2), html)

    def test_seeds_page_reuses_run_seeds_report(self) -> None:
        called = {"n": 0}

        def fake_report(seeds, *, days=90):
            called["n"] += 1
            self.assertEqual(list(seeds), [1, 2])
            self.assertEqual(days, 2)
            return "table", [
                {
                    "seed": 1,
                    "shops_open": 6,
                    "max_zero_streak": 0,
                    "avg_wallet_cents": 1000,
                    "treasury": 1,
                    "pass": True,
                    "avg_wallet_series_cents": [1000, 1000],
                    "shops_open_series": [6, 6],
                },
                {
                    "seed": 2,
                    "shops_open": 6,
                    "max_zero_streak": 0,
                    "avg_wallet_cents": 1100,
                    "treasury": 1,
                    "pass": True,
                    "avg_wallet_series_cents": [1100, 1100],
                    "shops_open_series": [6, 6],
                },
            ]

        original = dash.run_seeds_report
        dash.run_seeds_report = fake_report
        try:
            with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
                out = str(Path(tmp) / "seeds.html")
                html = main(out=out, seeds=range(1, 3), days=2)
                self.assertEqual(called["n"], 1)
                self.assertTrue(Path(out).is_file())
                self.assertEqual(Path(out).read_text(), html)
                self.assertIn("Average wallet by seed", html)
                self.assertEqual({p.name for p in Path(tmp).iterdir()}, {"seeds.html"})
        finally:
            dash.run_seeds_report = original

    def test_run_seed_metrics_includes_series(self) -> None:
        row = run.run_seed_metrics(1, days=2)
        self.assertEqual(len(row["avg_wallet_series_cents"]), 2)
        self.assertEqual(len(row["shops_open_series"]), 2)
        self.assertEqual(row["shops_open_series"][-1], row["shops_open"])

    def test_phase4_series_and_charts(self) -> None:
        daily = [
            {
                "day": 1,
                "economy": {"tax_income": 10.0, "utility_income": 2.0, "treasury": 1000},
                "residents": {
                    "bills_paid_cents": 600,
                    "arrears_cents": 0,
                    "in_arrears": 0,
                },
                "businesses": {
                    "shops": {
                        "fold-post": {
                            "open": True,
                            "price_cents": 500,
                            "available": 1,
                            "balance_cents": 50000,
                            "sold_yesterday": 0,
                        }
                    },
                    "bills_paid_cents": 200,
                    "arrears_cents": 0,
                },
            },
            {
                "day": 2,
                "economy": {"treasury": 1010},
                "residents": {"count": 120},
                "businesses": {"shops": {}},
            },
        ]
        taxes = _series_taxes_and_bills(daily)
        self.assertEqual(taxes["tax income ($)"][0], 10.0)
        self.assertEqual(taxes["bills paid ($)"][0], 8.0)
        self.assertIsNone(taxes["tax income ($)"][1])
        self.assertIsNone(taxes["bills paid ($)"][1])
        arrears = _series_arrears(daily)
        self.assertEqual(arrears["residents in arrears"][0], 0.0)
        self.assertIsNone(arrears["residents in arrears"][1])
        html = render_html(
            {"seed": 1, "days": 2, "systems": [], "daily": daily, "events_by_kind": {}}
        )
        self.assertIn("Taxes and bills", html)
        self.assertIn("Arrears", html)
        # Nested shops still chart.
        self.assertIn("fold-post", html)



if __name__ == "__main__":
    unittest.main()
