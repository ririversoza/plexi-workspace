"""CLI for ``python3 -m nori.pixeltown``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .data import (
    DEFAULT_DAYS,
    DEFAULT_SEED,
    collect_timeline,
    load_timeline,
    validate_export_path,
)
from .render import render_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nori.pixeltown",
        description=(
            "Write a self-contained pixelated Tiny Town HTML sim view "
            "(one file; inline CSS/JS only)."
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help="HTML file to write (only path this tool writes)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        metavar="N",
        help=f"RNG seed when running the town (default {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--from",
        dest="from_file",
        default=None,
        metavar="TIMELINE.json",
        help="load Taro timeline JSON instead of running the town",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        metavar="N",
        help=f"days to simulate when running (default {DEFAULT_DAYS})",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(
    *,
    out: str,
    seed: int = DEFAULT_SEED,
    days: int = DEFAULT_DAYS,
    from_file: Optional[str] = None,
) -> str:
    """Build timeline and write HTML to ``out``. Returns the HTML string."""
    if from_file:
        timeline = load_timeline(from_file)
    else:
        timeline = collect_timeline(seed=seed, days=days)
    html_text = render_html(timeline)
    Path(out).write_text(html_text, encoding="utf-8")
    return html_text


def cli(argv: Optional[Sequence[str]] = None) -> str:
    args = parse_args(argv)
    try:
        validate_export_path(args.out, flag="--out")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    return main(out=args.out, seed=args.seed, days=args.days, from_file=args.from_file)
