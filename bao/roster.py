#!/usr/bin/env python3
"""Print the Plexi Office roster."""

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


ROSTER_PATH = Path(__file__).with_name("roster.json")
COLUMNS = (
    ("emoji", "Emoji"),
    ("name", "Name"),
    ("pronouns", "Pronouns"),
    ("team", "Team"),
    ("role", "Role"),
    ("catchphrase", "Catchphrase"),
)


def load_roster(path: Path = ROSTER_PATH) -> List[Dict[str, str]]:
    """Load roster entries from JSON."""
    with path.open(encoding="utf-8") as roster_file:
        return json.load(roster_file)


def filter_by_team(
    agents: Iterable[Dict[str, str]], team: Optional[str]
) -> List[Dict[str, str]]:
    """Return agents on ``team`` using a case-insensitive match."""
    if team is None:
        return list(agents)

    requested_team = team.strip().casefold()
    return [agent for agent in agents if agent["team"].casefold() == requested_team]


def format_table(agents: Iterable[Dict[str, str]]) -> str:
    """Format roster entries as a simple ASCII table."""
    rows = [[agent[key] for key, _ in COLUMNS] for agent in agents]
    headers = [heading for _, heading in COLUMNS]
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        if rows
        else len(header)
        for index, header in enumerate(headers)
    ]

    separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"

    def render_row(values: Sequence[str]) -> str:
        return "| " + " | ".join(
            value.ljust(width) for value, width in zip(values, widths)
        ) + " |"

    rendered = [separator, render_row(headers), separator]
    rendered.extend(render_row(row) for row in rows)
    rendered.append(separator)
    return "\n".join(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the Plexi Office roster.")
    parser.add_argument("--team", help="show only agents on this team")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    agents = filter_by_team(load_roster(), args.team)
    print(format_table(agents))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
