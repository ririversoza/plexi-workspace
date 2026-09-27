"""Tiny Town event log: records every event the town emits and writes events.csv."""

from mochi.tinytown import csvlog

DEFAULT_CSV_PATH = "events.csv"


class System:
    """Event log. Subscribes during setup; never ticks, draws from town.rng or emits.

    State written to town.state["log"]:
      events       list of every event seen, in emit order (copies)
      counts       {"<system>.<kind>": n}
      csv_path     where the CSV is written, or None if disabled
    """

    name = "log"

    def __init__(self, csv_path=DEFAULT_CSV_PATH):
        self.csv_path = csv_path
        self._state = None

    def setup(self, town):
        self._state = {"events": [], "counts": {}, "csv_path": self.csv_path}
        town.state[self.name] = self._state
        if self.csv_path is not None:
            csvlog.write_header(self.csv_path)
        # Events emitted by systems whose setup ran before ours.
        for event in list(getattr(town, "events", [])):
            self._record(event)
        town.subscribe(self._record)

    def tick(self, town):
        """The log does not tick; present so an engine that ticks everyone stays safe."""

    def _record(self, event):
        event = dict(event)
        self._state["events"].append(event)
        key = f"{event.get('system', '')}.{event.get('kind', '')}"
        self._state["counts"][key] = self._state["counts"].get(key, 0) + 1
        if self.csv_path is not None:
            csvlog.append_event(self.csv_path, event)


__all__ = ["System", "DEFAULT_CSV_PATH"]
