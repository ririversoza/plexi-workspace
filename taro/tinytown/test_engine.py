"""Tests for the Tiny Town engine and runner.

These exercise Taro's Town + tick loop with tiny fake systems so they pass
without any peer packages installed.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from typing import Any, List

from taro.tinytown.engine import DEFAULT_DAYS, DEFAULT_SEED, TICK_ORDER, Town, run_town
from taro.tinytown.run import daily_summary, final_report, load_systems, main


class FakeSystem:
    """Minimal System stand-in that records call order."""

    def __init__(self, name: str, *, tickable: bool = True) -> None:
        self.name = name
        self.tickable = tickable
        self.setup_calls = 0
        self.tick_calls = 0

    def setup(self, town: Town) -> None:
        self.setup_calls += 1
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
        town.state["log"] = {"subscribed": True}
        town.subscribe(self.seen.append)


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
        economy = FakeSystem("economy")
        traffic = FakeSystem("traffic")
        emergency = FakeSystem("emergency")
        log = LogFake()
        # Intentionally shuffled input order — engine must tick by TICK_ORDER.
        systems = [emergency, log, weather, traffic, economy]
        order: List[str] = []

        def on_day(town: Town) -> None:
            if town.day == 1:
                order.extend(
                    event["system"]
                    for event in town.events
                    if event["day"] == 1 and event["kind"] == "tick"
                )

        town = run_town(systems, days=3, seed=DEFAULT_SEED, on_day=on_day)
        self.assertEqual(order, list(TICK_ORDER))
        for system in (weather, economy, traffic, emergency):
            self.assertEqual(system.setup_calls, 1)
            self.assertEqual(system.tick_calls, 3)
        self.assertEqual(log.setup_calls, 1)
        self.assertEqual(log.tick_calls, 0)
        # Log saw setup emits + tick emits via subscribe.
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
        self.assertEqual(weather.tick_calls, 2)
        self.assertEqual(emergency.tick_calls, 2)

    def test_determinism_same_seed_same_state(self) -> None:
        def snapshot() -> dict[str, Any]:
            systems = [
                FakeSystem("weather"),
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
        # With no peer tinytown packages on this branch, loader returns [].
        systems = load_systems()
        self.assertIsInstance(systems, list)

    def test_daily_summary_zero_systems(self) -> None:
        town = Town()
        town.day = 1
        line = daily_summary(town)
        self.assertIn("Day 1", line)
        self.assertIn("(no systems)", line)

    def test_main_zero_systems_prints_days_and_report(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
