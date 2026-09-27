"""Reading and writing the Tiny Town event log as CSV (day,system,kind,data_json)."""

import csv
import json

HEADER = ["day", "system", "kind", "data_json"]
RESERVED_KEYS = ("day", "system", "kind")


def event_to_row(event):
    """Turn an event dict into a CSV row. Extra fields go into data_json."""
    data = {key: value for key, value in event.items() if key not in RESERVED_KEYS}
    data_json = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return [event.get("day", 0), event.get("system", ""), event.get("kind", ""), data_json]


def row_to_event(row):
    """Turn a CSV row (dict from DictReader) back into an event dict."""
    event = {"day": int(row["day"]), "system": row["system"], "kind": row["kind"]}
    data = json.loads(row["data_json"] or "{}")
    event.update({key: value for key, value in data.items() if key not in RESERVED_KEYS})
    return event


def write_header(path):
    """Create (or truncate) the log file with just the header row."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(HEADER)


def append_event(path, event):
    """Append one event row to an existing log file."""
    with open(path, "a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(event_to_row(event))


def write_events(path, events):
    """Write a whole list of events to a fresh log file."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(event_to_row(event) for event in events)


def read_events(path):
    """Read every event from a log file, in file order."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in HEADER if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: not an event log, missing columns {missing}")
        return [row_to_event(row) for row in reader]
