import contextlib
import io
import os
import random
import tempfile
import unittest

from mochi.tinytown import System, csvlog, inspect

DAYS = 90


class FakeTown:
    """Minimal Town following the TINYTOWN.md interface (no engine needed)."""

    def __init__(self, systems):
        self.day = 0
        self.rng = random.Random(42)
        self.state = {}
        self.events = []
        self.systems = systems
        self._subscribers = []
        self._current = None

    def emit(self, kind, **data):
        event = {"day": self.day, "system": self._current, "kind": kind, **data}
        self.events.append(event)
        for callback in list(self._subscribers):
            callback(event)

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def run(self, days=DAYS):
        for system in self.systems:
            self._current = system.name
            system.setup(self)
        for day in range(1, days + 1):
            self.day = day
            for system in self.systems:
                self._current = system.name
                system.tick(self)
        self._current = None


class NoisySystem:
    """Stand-in for another owner's system: emits rng-driven events."""

    name = "noisy"

    def setup(self, town):
        town.state[self.name] = {"total": 0}
        town.emit("opened", note="hello, town")

    def tick(self, town):
        roll = town.rng.randint(0, 5)
        town.state[self.name]["total"] += roll
        if roll >= 3:
            town.emit("roll", value=roll, tags=["a", "b"], ratio=roll / 5)


class LogTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name="events.csv"):
        return os.path.join(self.tmp.name, name)

    def run_town(self, systems, csv_name="events.csv"):
        log = System(csv_path=self.path(csv_name))
        town = FakeTown([*systems, log])
        town.run()
        return town, log


class DeterminismTest(LogTestCase):
    def test_same_seed_gives_identical_csv_and_state(self):
        town_a, _ = self.run_town([NoisySystem()], "a.csv")
        town_b, _ = self.run_town([NoisySystem()], "b.csv")

        with open(self.path("a.csv"), "rb") as a, open(self.path("b.csv"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        # csv_path legitimately differs (a.csv vs b.csv); everything else must match.
        strip_path = lambda state: {**state, "log": {**state["log"], "csv_path": None}}
        self.assertEqual(strip_path(town_a.state), strip_path(town_b.state))

    def test_log_does_not_touch_rng(self):
        with_log, _ = self.run_town([NoisySystem()])
        without_log = FakeTown([NoisySystem()])
        without_log.run()

        self.assertEqual(with_log.rng.getstate(), without_log.rng.getstate())
        self.assertEqual(with_log.events, without_log.events)


class RecordingTest(LogTestCase):
    def test_records_every_event_including_setup_before_log(self):
        town, _ = self.run_town([NoisySystem()])
        log_state = town.state["log"]

        self.assertEqual(log_state["events"], town.events)
        self.assertEqual(log_state["events"][0]["kind"], "opened")
        self.assertEqual(log_state["counts"]["noisy.opened"], 1)
        self.assertEqual(sum(log_state["counts"].values()), len(town.events))

    def test_log_set_up_first_still_sees_everything(self):
        log = System(csv_path=self.path())
        town = FakeTown([log, NoisySystem()])
        town.run()

        self.assertEqual(town.state["log"]["events"], town.events)
        self.assertEqual(csvlog.read_events(self.path()), town.events)

    def test_recorded_events_are_copies(self):
        town, _ = self.run_town([NoisySystem()])
        town.events[0]["kind"] = "tampered"

        self.assertEqual(town.state["log"]["events"][0]["kind"], "opened")

    def test_csv_disabled_writes_no_file(self):
        town = FakeTown([NoisySystem(), System(csv_path=None)])
        town.run()

        self.assertEqual(len(town.state["log"]["events"]), len(town.events))
        self.assertEqual(os.listdir(self.tmp.name), [])


class CsvRoundTripTest(LogTestCase):
    def test_run_csv_reads_back_equal_to_town_events(self):
        town, _ = self.run_town([NoisySystem()])

        self.assertEqual(csvlog.read_events(self.path()), town.events)

    def test_awkward_values_round_trip(self):
        events = [
            {"day": 0, "system": "weather", "kind": "setup"},
            {"day": 7, "system": "economy", "kind": "note", "text": 'comma, "quote"\nnewline', "n": -3},
            {"day": 90, "system": "traffic", "kind": "jam", "nested": {"x": [1, 2.5, None, True]}},
        ]
        csvlog.write_events(self.path(), events)

        self.assertEqual(csvlog.read_events(self.path()), events)

    def test_header_is_contract_columns(self):
        csvlog.write_events(self.path(), [])

        with open(self.path(), encoding="utf-8") as handle:
            self.assertEqual(handle.readline().strip(), "day,system,kind,data_json")

    def test_unserialisable_value_is_stringified_not_crash(self):
        csvlog.write_events(self.path(), [{"day": 1, "system": "s", "kind": "k", "obj": {1, 2}}])

        self.assertEqual(csvlog.read_events(self.path())[0]["obj"], "{1, 2}")

    def test_rejects_file_without_contract_columns(self):
        with open(self.path(), "w", encoding="utf-8") as handle:
            handle.write("a,b\n1,2\n")

        with self.assertRaises(ValueError):
            csvlog.read_events(self.path())


class NoOtherSystemsTest(LogTestCase):
    def test_runs_alone_for_90_days(self):
        town, _ = self.run_town([])

        self.assertEqual(town.day, DAYS)
        self.assertEqual(town.state["log"]["events"], [])
        self.assertEqual(csvlog.read_events(self.path()), [])

    def test_inspect_on_empty_log(self):
        self.run_town([])

        lines = inspect.format_day(csvlog.read_events(self.path()), 5)
        self.assertEqual(lines, ["Day 5: nothing happened (0 events)"])


class InspectTest(LogTestCase):
    EVENTS = [
        {"day": 3, "system": "weather", "kind": "rain_started", "mm": 4},
        {"day": 3, "system": "traffic", "kind": "accident", "street": "Elm St", "injured": 0},
        {"day": 4, "system": "weather", "kind": "sun"},
    ]

    def test_format_day_lists_only_that_day(self):
        lines = inspect.format_day(self.EVENTS, 3)

        self.assertEqual(lines, [
            "Day 3: 2 events",
            "  weather  rain_started  mm=4",
            "  traffic  accident      injured=0 street=Elm St",
            "By system: weather 1, traffic 1",
        ])

    def test_system_filter(self):
        lines = inspect.format_day(self.EVENTS, 3, system="traffic")

        self.assertEqual(lines[0], "Day 3 (traffic): 1 event")
        self.assertEqual(len(lines), 3)

    def test_main_prints_day_from_csv(self):
        csvlog.write_events(self.path(), self.EVENTS)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = inspect.main(["4", "--csv", self.path()])

        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "Day 4: 1 event\n  weather  sun\nBy system: weather 1\n")

    def test_main_reports_missing_file(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = inspect.main(["1", "--csv", self.path("nope.csv")])

        self.assertEqual(code, 2)
        self.assertIn("cannot read event log", err.getvalue())


if __name__ == "__main__":
    unittest.main()
