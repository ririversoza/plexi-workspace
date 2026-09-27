"""Tests for nori.pixeltown data layer and CLI (read-only HTML writer)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import nori.pixeltown as pix
import nori.pixeltown.data as data
import taro.tinytown.run as run
from nori.pixeltown import collect_timeline, load_timeline, render_html
from nori.pixeltown.cli import cli, main, parse_args


def _tiny_timeline() -> dict:
    return {
        "seed": 7,
        "days": 2,
        "systems": ["weather", "businesses", "residents"],
        "daily": [
            {
                "day": 1,
                "weather": {"condition": "sun", "temp_c": 20.0},
                "economy": {"treasury": 1000.0},
                "businesses": {
                    "matcha-mile": {
                        "open": True,
                        "price_cents": 550,
                        "available": 10,
                        "balance_cents": 45800,
                        "sold_yesterday": 0,
                    },
                    "fold-post": {
                        "open": True,
                        "price_cents": 800,
                        "available": 4,
                        "balance_cents": 0,
                        "sold_yesterday": 0,
                    },
                },
                "residents": {"count": 40, "employed": 30, "avg_wallet_cents": 2500},
            },
            {
                "day": 2,
                "weather": {"condition": "rain", "temp_c": 12.0},
                "economy": {"treasury": 980.5},
                "businesses": {
                    "matcha-mile": {
                        "open": True,
                        "price_cents": 550,
                        "available": 8,
                        "balance_cents": 47000,
                        "sold_yesterday": 2,
                    },
                    "fold-post": {
                        "open": False,
                        "price_cents": 800,
                        "available": 0,
                        "balance_cents": 0,
                        "sold_yesterday": 0,
                    },
                },
                "residents": {"count": 40, "employed": 30, "avg_wallet_cents": 2600},
            },
        ],
        "events_by_kind": {"weather.tick": 2},
    }


class DataLayerTests(unittest.TestCase):
    def test_imports_schema_helpers_from_run(self) -> None:
        self.assertIs(data._load_systems, run._load_systems)
        self.assertIs(data._snapshot_day, run._snapshot_day)
        self.assertIs(data._count_events_by_kind, run._count_events_by_kind)
        self.assertIs(data._SHOP_EXPORT_FIELDS, run._SHOP_EXPORT_FIELDS)
        self.assertIs(data.validate_export_path, run.validate_export_path)

    def test_load_timeline_roundtrip(self) -> None:
        timeline = _tiny_timeline()
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            path = Path(tmp) / "town.json"
            path.write_text(json.dumps(timeline), encoding="utf-8")
            loaded = load_timeline(str(path))
        self.assertEqual(loaded["seed"], 7)
        self.assertEqual(len(loaded["daily"]), 2)
        self.assertEqual(loaded["daily"][0]["weather"]["condition"], "sun")

    def test_load_timeline_rejects_non_timeline(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            path = Path(tmp) / "nope.json"
            path.write_text(json.dumps({"hello": 1}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_timeline(str(path))

    def test_collect_timeline_uses_snapshot_helper(self) -> None:
        calls = {"snap": 0}

        def fake_snap(town):
            calls["snap"] += 1
            return {"day": town.day, "businesses": {}, "weather": {"condition": "cloud"}}

        class FakeTown:
            def __init__(self) -> None:
                self.seed = 99
                self.day = 0
                self.events: list = []

        def fake_run(systems, days=90, seed=42, on_day=None):
            town = FakeTown()
            for day in range(1, days + 1):
                town.day = day
                if on_day:
                    on_day(town)
            return town

        with mock.patch.object(data, "_load_systems", return_value=[]):
            with mock.patch.object(data, "_snapshot_day", side_effect=fake_snap):
                with mock.patch.object(data, "_count_events_by_kind", return_value={}):
                    with mock.patch.object(data, "run_town", side_effect=fake_run):
                        timeline = collect_timeline(seed=99, days=3)

        self.assertEqual(timeline["seed"], 99)
        self.assertEqual(timeline["days"], 3)
        self.assertEqual(len(timeline["daily"]), 3)
        self.assertEqual(calls["snap"], 3)

    def test_collect_timeline_disables_log_csv(self) -> None:
        seen = {}

        def fake_load(*, disable_log_files=False):
            seen["disable_log_files"] = disable_log_files
            return []

        class FakeTown:
            seed = 1
            day = 1
            events: list = []

        with mock.patch.object(data, "_load_systems", side_effect=fake_load):
            with mock.patch.object(data, "_snapshot_day", return_value={"day": 1}):
                with mock.patch.object(data, "_count_events_by_kind", return_value={}):
                    with mock.patch.object(data, "run_town", return_value=FakeTown()):
                        collect_timeline(seed=1, days=1)

        self.assertTrue(seen.get("disable_log_files"))


class RenderAndCliTests(unittest.TestCase):
    def test_render_html_is_self_contained(self) -> None:
        html = render_html(_tiny_timeline())
        self.assertIn("<canvas", html)
        self.assertIn("image-rendering: pixelated", html)
        self.assertIn("const TIMELINE =", html)
        self.assertIn("matcha-mile", html)
        self.assertNotIn("http://", html.split("<script>", 1)[-1].split("</script>", 1)[0])
        self.assertNotIn("<img", html)
        self.assertIn("btn-play", html)
        self.assertIn("day-slider", html)

    def test_parse_requires_out(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args([])
        args = parse_args(["--out", "/tmp/x.html", "--seed", "3", "--days", "5"])
        self.assertEqual(args.out, "/tmp/x.html")
        self.assertEqual(args.seed, 3)
        self.assertEqual(args.days, 5)
        self.assertIsNone(args.from_file)

    def test_cli_out_bad_path_exits_2(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            cli(["--out", "   "])
        self.assertEqual(ctx.exception.code, 2)

        with self.assertRaises(SystemExit) as ctx2:
            cli(["--out", "/no/such/parent/pix.html"])
        self.assertEqual(ctx2.exception.code, 2)

        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            with self.assertRaises(SystemExit) as ctx3:
                cli(["--out", tmp])
            self.assertEqual(ctx3.exception.code, 2)

    def test_main_from_file_writes_only_out(self) -> None:
        timeline = _tiny_timeline()
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src = Path(tmp) / "town.json"
            out = Path(tmp) / "town.html"
            src.write_text(json.dumps(timeline), encoding="utf-8")
            main(out=str(out), from_file=str(src))
            text = out.read_text(encoding="utf-8")
            extras = [p for p in Path(tmp).iterdir() if p.name not in ("town.json", "town.html")]
        self.assertTrue(text.startswith("<!DOCTYPE html>"))
        self.assertIn("Pixel Sim", text)
        self.assertEqual(extras, [])

    def test_package_exports(self) -> None:
        self.assertTrue(callable(pix.collect_timeline))
        self.assertTrue(callable(pix.render_html))
        self.assertTrue(callable(pix.cli))


if __name__ == "__main__":
    unittest.main()
