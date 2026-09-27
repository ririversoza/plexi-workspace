"""Print what happened on one day of a Tiny Town run.

Usage: python3 -m mochi.tinytown.inspect <day> [--csv events.csv] [--system NAME]
"""

import argparse
import json
import sys

from mochi.tinytown import DEFAULT_CSV_PATH, csvlog


def format_data(event):
    fields = {key: value for key, value in event.items() if key not in csvlog.RESERVED_KEYS}
    parts = []
    for key in sorted(fields):
        value = fields[key]
        text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        parts.append(f"{key}={text}")
    return " ".join(parts)


def format_day(events, day, system=None):
    """Return the report for one day as a list of lines."""
    todays = [
        event for event in events
        if event["day"] == day and (system is None or event["system"] == system)
    ]
    scope = f" ({system})" if system else ""
    if not todays:
        return [f"Day {day}{scope}: nothing happened (0 events)"]

    noun = "event" if len(todays) == 1 else "events"
    lines = [f"Day {day}{scope}: {len(todays)} {noun}"]
    system_width = max(len(event["system"]) for event in todays)
    kind_width = max(len(event["kind"]) for event in todays)
    for event in todays:
        line = f"  {event['system']:<{system_width}}  {event['kind']:<{kind_width}}  {format_data(event)}"
        lines.append(line.rstrip())

    per_system = {}
    for event in todays:
        per_system[event["system"]] = per_system.get(event["system"], 0) + 1
    totals = ", ".join(f"{name} {count}" for name, count in per_system.items())
    lines.append(f"By system: {totals}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m mochi.tinytown.inspect",
        description="Print what happened on one day of a Tiny Town run.",
    )
    parser.add_argument("day", type=int, help="day number (0 = setup, 1..90)")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="event log to read (default: events.csv)")
    parser.add_argument("--system", help="only show events from this system")
    args = parser.parse_args(argv)

    try:
        events = csvlog.read_events(args.csv)
    except (OSError, ValueError) as error:
        print(f"inspect: cannot read event log: {error}", file=sys.stderr)
        return 2

    print("\n".join(format_day(events, args.day, args.system)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
