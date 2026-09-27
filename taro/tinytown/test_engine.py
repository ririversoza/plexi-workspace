"""Tests for the Tiny Town engine and runner.

These exercise Taro's Town + tick loop with tiny fake systems so they pass
without any peer packages installed.
"""

from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from typing import Any, List, Optional

from taro.tinytown.engine import DEFAULT_DAYS, DEFAULT_SEED, TICK_ORDER, Town, run_town
from taro.tinytown.run import (
    cli,
    daily_summary,
    evaluate_targets,
    final_report,
    format_dollars,
    format_seeds_table,
    load_systems,
    log_counts,
    main,
    parse_args,
    parse_seed_range,
    shop_leaderboard,
)


class FakeSystem:
    """Minimal System stand-in that records call order."""

    def __init__(self, name: str, *, tickable: bool = True) -> None:
        self.name = name
        self.tickable = tickable
        self.setup_calls = 0
        self.tick_calls = 0
        self.setup_day: Optional[int] = None

    def setup(self, town: Town) -> None:
        self.setup_calls += 1
        self.setup_day = town.day
        town.state[self.name] = {"ready": True, "ticks": 0}
        town.emit("setup")

    def tick(self, town: Town) -> None:
        self.tick_calls += 1
        state = town.state[self.name]
        state["ticks"] = state.get("ticks", 0) + 1
        # Draw from the shared RNG so determinism covers rng use.
        state["roll"] = town.rng.random()
        town.emit("tick", ticks=state["ticks"])


class LogFake(FakeSystem):
    """Setup-only system that mirrors Mochi's subscribe pattern."""

    def __init__(self) -> None:
        super().__init__("log", tickable=False)
        self.seen: List[dict] = []

    def setup(self, town: Town) -> None:
        self.setup_calls += 1
        town.state["log"] = {
            "subscribed": True,
            "events": [{"kind": "noise"} for _ in range(3)],
        }
        town.subscribe(self.seen.append)
        town.emit("setup")


class BusinessesFake(FakeSystem):
    """Minimal businesses system with two shops for report tests."""

    def __init__(self) -> None:
        super().__init__("businesses")

    def setup(self, town: Town) -> None:
        self.setup_calls += 1
        town.state["businesses"] = {
            "open_count": 2,
            "wages_paid": {},
            "pending_revenue_cents": {},
            "shops": {
                "fold-post": {
                    "name": "Fold Post",
                    "open": True,
                    "price_cents": 500,
                    "available": 10,
                    "balance_cents": 55000,
                    "sold_yesterday": 0,
                    "staff": [],
                },
                "one-mug-tea": {
                    "name": "One Mug Tea",
                    "open": True,
                    "price_cents": 400,
                    "available": 8,
                    "balance_cents": 48000,
                    "sold_yesterday": 0,
                    "staff": [],
                },
            },
        }
        town.emit("setup")

    def tick(self, town: Town) -> None:
        self.tick_calls += 1
        shops = town.state["businesses"]["shops"]
        shops["fold-post"]["sold_yesterday"] = 2
        shops["one-mug-tea"]["sold_yesterday"] = 1
        town.state["businesses"]["open_count"] = 2
        town.emit("tick")


class ResidentsFake(FakeSystem):
    """Minimal residents system with purchases for summary/sales tests."""

    def __init__(self) -> None:
        super().__init__("residents")

    def setup(self, town: Town) -> None:
        self.setup_calls += 1
        town.state["residents"] = {
            "people": [],
            "purchases": {},
            "spent_cents": {},
            "count": 120,
            "employed": 90,
            "avg_wallet_cents": 2500,
        }
        town.emit("setup")

    def tick(self, town: Town) -> None:
        self.tick_calls += 1
        town.state["residents"]["purchases"] = {"fold-post": 3, "one-mug-tea": 2}
        town.state["residents"]["spent_cents"] = {"fold-post": 1500, "one-mug-tea": 800}
        town.emit("tick")


class TownInterfaceTests(unittest.TestCase):
    def test_starts_at_day_zero_with_seeded_rng(self) -> None:
        town = Town(seed=DEFAULT_SEED)
        self.assertEqual(town.day, 0)
        self.assertEqual(town.state, {})
        self.assertEqual(town.events, [])
        a = Town(seed=DEFAULT_SEED).rng.random()
        b = Town(seed=DEFAULT_SEED).rng.random()
        self.assertEqual(a, b)

    def test_emit_fills_day_and_system(self) -> None:
        town = Town()
        town.day = 3
        town._current_system = "weather"
        event = town.emit("storm", severity=2)
        self.assertEqual(event["day"], 3)
        self.assertEqual(event["system"], "weather")
        self.assertEqual(event["kind"], "storm")
        self.assertEqual(event["severity"], 2)
        self.assertEqual(town.events, [event])

    def test_subscribe_receives_future_emits(self) -> None:
        town = Town()
        seen: List[dict] = []
        town.subscribe(seen.append)
        town.emit("ping")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["kind"], "ping")


class TickLoopTests(unittest.TestCase):
    def test_zero_systems_runs_requested_days(self) -> None:
        days: List[int] = []
        town = run_town([], days=90, seed=DEFAULT_SEED, on_day=lambda t: days.append(t.day))
        self.assertEqual(town.day, 90)
        self.assertEqual(days, list(range(1, 91)))
        self.assertEqual(town.events, [])
        self.assertEqual(town.state, {})

    def test_tick_order_and_setup_only_log(self) -> None:
        weather = FakeSystem("weather")
        businesses = FakeSystem("businesses")
        residents = FakeSystem("residents")
        economy = FakeSystem("economy")
        traffic = FakeSystem("traffic")
        emergency = FakeSystem("emergency")
        log = LogFake()
        # Intentionally shuffled input order — engine must tick by TICK_ORDER.
        systems = [emergency, log, residents, weather, traffic, businesses, economy]
        order: List[str] = []

        def on_day(town: Town) -> None:
            if town.day == 1:
                order.extend(
                    event["system"]
                    for event in town.events
                    if event["day"] == 1 and event["kind"] == "tick"
                )

        town = run_town(systems, days=3, seed=DEFAULT_SEED, on_day=on_day)
        setup_order = [
            event["system"]
            for event in town.events
            if event["day"] == 0 and event["kind"] == "setup"
        ]
        self.assertEqual(order, list(TICK_ORDER))
        self.assertEqual(setup_order, list(TICK_ORDER) + ["log"])
        for system in (weather, businesses, residents, economy, traffic, emergency):
            self.assertEqual(system.setup_calls, 1)
            self.assertEqual(system.tick_calls, 3)
        self.assertEqual(log.setup_calls, 1)
        self.assertEqual(log.tick_calls, 0)
        self.assertGreater(len(log.seen), 0)
        self.assertTrue(all("kind" in event for event in log.seen))
        self.assertEqual(town.state["weather"]["ticks"], 3)

    def test_missing_systems_skipped(self) -> None:
        weather = FakeSystem("weather")
        emergency = FakeSystem("emergency")
        town = run_town([weather, emergency], days=2, seed=DEFAULT_SEED)
        self.assertIn("weather", town.state)
        self.assertIn("emergency", town.state)
        self.assertNotIn("economy", town.state)
        self.assertNotIn("traffic", town.state)
        self.assertNotIn("businesses", town.state)
        self.assertNotIn("residents", town.state)
        self.assertEqual(weather.tick_calls, 2)
        self.assertEqual(emergency.tick_calls, 2)

    def test_subset_businesses_and_residents_only(self) -> None:
        businesses = BusinessesFake()
        residents = ResidentsFake()
        town = run_town([residents, businesses], days=2, seed=DEFAULT_SEED)
        self.assertEqual(list(town.state), ["businesses", "residents"])
        self.assertEqual(businesses.tick_calls, 2)
        self.assertEqual(residents.tick_calls, 2)

    def test_determinism_same_seed_same_state(self) -> None:
        def snapshot() -> dict[str, Any]:
            systems = [
                FakeSystem("weather"),
                FakeSystem("businesses"),
                FakeSystem("residents"),
                FakeSystem("economy"),
                FakeSystem("traffic"),
                FakeSystem("emergency"),
            ]
            town = run_town(systems, days=10, seed=DEFAULT_SEED)
            return {
                "state": town.state,
                "events": town.events,
                "rolls": [town.state[name]["roll"] for name in TICK_ORDER],
            }

        self.assertEqual(snapshot(), snapshot())


class RunnerTests(unittest.TestCase):
    def test_load_systems_skips_missing(self) -> None:
        systems = load_systems()
        self.assertIsInstance(systems, list)

    def test_daily_summary_zero_systems(self) -> None:
        town = Town()
        town.day = 1
        line = daily_summary(town)
        self.assertIn("Day 1", line)
        self.assertIn("(no systems)", line)

    def test_daily_summary_includes_residents_and_shops(self) -> None:
        town = Town()
        town.day = 5
        town.state["residents"] = {
            "count": 120,
            "employed": 90,
            "avg_wallet_cents": 2500,
            "purchases": {"fold-post": 4},
        }
        town.state["businesses"] = {"open_count": 5, "shops": {}}
        line = daily_summary(town)
        self.assertIn("residents=120 employed=90 avg_wallet=$25.00", line)
        self.assertIn("shops_open=5 sales=4", line)

    def test_format_dollars(self) -> None:
        self.assertEqual(format_dollars(0), "$0.00")
        self.assertEqual(format_dollars(2500), "$25.00")
        self.assertEqual(format_dollars(-105), "-$1.05")

    def test_log_counts_trims_event_lists(self) -> None:
        counts = log_counts({"subscribed": True, "events": [1, 2, 3, 4]})
        self.assertEqual(counts["events"], 4)
        self.assertEqual(counts["subscribed"], 1)

    def test_final_report_leaderboard_and_log_counts(self) -> None:
        businesses = BusinessesFake()
        residents = ResidentsFake()
        log = LogFake()
        town = run_town([businesses, residents, log], days=3, seed=DEFAULT_SEED)
        report = final_report(
            town,
            [businesses, residents, log],
            units_sold={"fold-post": 9, "one-mug-tea": 6},
        )
        self.assertIn("shop_leaderboard:", report)
        self.assertIn("fold-post", report)
        self.assertIn("balance=$550.00", report)
        self.assertIn("sold=9", report)
        self.assertIn("log:", report)
        self.assertIn("'events': 3", report)
        self.assertNotIn("{'kind': 'noise'}", report)
        self.assertNotIn("'shops':", report.split("shop_leaderboard:")[0])

    def test_shop_leaderboard_empty_without_businesses(self) -> None:
        self.assertEqual(shop_leaderboard(Town()), [])

    def test_main_zero_systems_prints_days_and_report(self) -> None:
        import taro.tinytown.run as run_mod

        original = run_mod.load_systems
        run_mod.load_systems = lambda **_kwargs: []
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                town = main(days=DEFAULT_DAYS, seed=DEFAULT_SEED)
            output = buf.getvalue()
            lines = [line for line in output.splitlines() if line.startswith("Day ")]
            self.assertEqual(len(lines), DEFAULT_DAYS)
            self.assertIn("=== Tiny Town final report ===", output)
            self.assertIn("systems=(none)", output)
            self.assertEqual(town.day, DEFAULT_DAYS)
            self.assertIn("systems=(none)", final_report(town, []))
        finally:
            run_mod.load_systems = original



class CliTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = parse_args([])
        self.assertEqual(args.seed, DEFAULT_SEED)
        self.assertEqual(args.days, DEFAULT_DAYS)
        self.assertFalse(args.quiet)
        self.assertIsNone(args.seeds)

    def test_parse_args_flags(self) -> None:
        args = parse_args(["--seed", "7", "--days", "3", "--quiet"])
        self.assertEqual(args.seed, 7)
        self.assertEqual(args.days, 3)
        self.assertTrue(args.quiet)
        self.assertIsNone(args.seeds)

    def test_parse_seed_range(self) -> None:
        self.assertEqual(list(parse_seed_range("1-3")), [1, 2, 3])
        self.assertEqual(list(parse_args(["--seeds", "2-4"]).seeds), [2, 3, 4])

    def test_parse_seed_range_rejects_bad(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--seeds", "nope"])

    def test_evaluate_targets(self) -> None:
        self.assertTrue(
            evaluate_targets(shops_open=5, max_zero_streak=3, avg_wallet_cents=59999)
        )
        self.assertFalse(
            evaluate_targets(shops_open=4, max_zero_streak=0, avg_wallet_cents=100)
        )
        self.assertFalse(
            evaluate_targets(shops_open=6, max_zero_streak=4, avg_wallet_cents=100)
        )
        self.assertFalse(
            evaluate_targets(shops_open=6, max_zero_streak=0, avg_wallet_cents=60000)
        )

    def test_cli_default_matches_main_bytes(self) -> None:
        """Plain CLI argv must match main() stdout (default-output invariance)."""
        import taro.tinytown.run as run_mod

        original = run_mod.load_systems

        def fake_load(**_kwargs):
            return [FakeSystem("weather")]

        run_mod.load_systems = fake_load
        try:
            with redirect_stdout(io.StringIO()) as buf_main:
                main(days=2, seed=1)
            main_out = buf_main.getvalue()
            with redirect_stdout(io.StringIO()) as buf_cli:
                cli([])
            # cli([]) uses defaults (90 days / seed 42) — compare same knobs via flags
            with redirect_stdout(io.StringIO()) as buf_cli_same:
                cli(["--seed", "1", "--days", "2"])
            self.assertEqual(buf_cli_same.getvalue(), main_out)
            # And no-arg CLI still invokes default seed/days path (smoke: starts Day 1)
            self.assertTrue(buf_cli.getvalue().startswith("Day 1"))
        finally:
            run_mod.load_systems = original

    def test_cli_no_args_uses_default_seed_and_days(self) -> None:
        args = parse_args([])
        self.assertEqual(args.seed, 42)
        self.assertEqual(args.days, 90)

    def test_seeds_table_formatting(self) -> None:
        rows = [
            {
                "seed": 1,
                "shops_open": 6,
                "max_zero_streak": 0,
                "avg_wallet_cents": 2500,
                "treasury": 100.0,
                "pass": True,
            },
            {
                "seed": 2,
                "shops_open": 4,
                "max_zero_streak": 5,
                "avg_wallet_cents": 90000,
                "treasury": 50.0,
                "pass": False,
            },
        ]
        table = format_seeds_table(rows)
        self.assertIn("1 of 2 seeds pass", table)
        self.assertIn("PASS", table)
        self.assertIn("FAIL", table)


    def test_seeds_do_not_write_log_files(self) -> None:
        import os
        import tempfile
        from taro.tinytown.run import run_seeds_report

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                table, rows = run_seeds_report(range(1, 2), days=2)
                self.assertIn("seed", table)
                self.assertEqual(len(rows), 1)
                self.assertFalse(any(name.endswith(".csv") for name in os.listdir(tmp)))
            finally:
                os.chdir(cwd)

    def test_default_cli_stdout_matches_main_subprocess(self) -> None:
        """``python3 -m taro.tinytown.run`` with no flags matches ``main()`` bytes."""
        import os
        import subprocess
        import tempfile

        import taro.tinytown.run as run_mod

        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with redirect_stdout(io.StringIO()) as buf:
                    run_mod.main()
                main_bytes = buf.getvalue().encode()
                env = os.environ.copy()
                env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
                proc = subprocess.run(
                    [sys.executable, "-m", "taro.tinytown.run"],
                    check=True,
                    capture_output=True,
                    env=env,
                    cwd=tmp,
                )
                self.assertEqual(proc.stdout, main_bytes)
            finally:
                os.chdir(cwd)

    def test_load_systems_can_disable_log_files(self) -> None:
        systems = load_systems(disable_log_files=True)
        for system in systems:
            if getattr(system, "name", None) == "log":
                self.assertIsNone(getattr(system, "csv_path", "missing"))



if __name__ == "__main__":
    unittest.main()
