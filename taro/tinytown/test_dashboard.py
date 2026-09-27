"""Tests for the Tiny Town HTML dashboard generator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from taro.tinytown.dashboard import (
    collect_timeline,
    load_timeline,
    main,
    parse_args,
    render_html,
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
        "events_by_kind": {"tick": 3},
    }


class DashboardTests(unittest.TestCase):
    def test_parse_requires_out(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args([])
        args = parse_args(["--out", "/tmp/x.html", "--seed", "3"])
        self.assertEqual(args.out, "/tmp/x.html")
        self.assertEqual(args.seed, 3)
        self.assertIsNone(args.from_file)

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
        with tempfile.TemporaryDirectory() as tmp:
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
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.html")
            write_dashboard(path, _tiny_timeline())
            text = Path(path).read_text()
            self.assertIn("<svg", text)


if __name__ == "__main__":
    unittest.main()
