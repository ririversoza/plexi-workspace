"""Self-contained Tiny Town HTML dashboard (inline CSS + SVG, no JS libs).

Run a seeded town (log CSV disabled) or load an ``--export`` JSON timeline, then
write one static HTML file to ``--out``. Read-only: no extra ``town.rng`` draws.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from taro.tinytown.engine import (  # noqa: E402
    DEFAULT_DAYS,
    DEFAULT_SEED,
    run_town,
)
from taro.tinytown.run import (  # noqa: E402
    _SHOP_EXPORT_FIELDS,
    _count_events_by_kind,
    _load_systems,
    _snapshot_day,
    validate_export_path,
)

# Re-export so tests/callers can assert we share the runner schema helpers.
__all__ = [
    "build_parser",
    "cli",
    "collect_timeline",
    "load_timeline",
    "main",
    "parse_args",
    "render_html",
    "write_dashboard",
    "_SHOP_EXPORT_FIELDS",
]

# Weather strip colours (condition -> fill). No external assets.
_WEATHER_FILL = {
    "sun": "#e8b84a",
    "cloud": "#9aa3ad",
    "rain": "#4a90c8",
    "snow": "#c5d5e4",
    "storm": "#6b4f9a",
    "n/a": "#d8dde3",
}

# Stable palette for shop lines (cycled if more shops appear).
_SHOP_STROKES = (
    "#c45c26",
    "#2a6f6f",
    "#3d5a80",
    "#8b5e34",
    "#5c6b3a",
    "#7a3e5c",
    "#b08d57",
    "#4f5d75",
)


def collect_timeline(
    *,
    seed: int = DEFAULT_SEED,
    days: int = DEFAULT_DAYS,
) -> Dict[str, Any]:
    """Run the town quietly and return a compact timeline dict."""
    systems = _load_systems(disable_log_files=True)
    daily: List[Dict[str, Any]] = []

    def on_day(town: Any) -> None:
        daily.append(_snapshot_day(town))

    town = run_town(systems, days=days, seed=seed, on_day=on_day)
    return {
        "seed": town.seed,
        "days": town.day,
        "systems": [system.name for system in systems],
        "daily": daily,
        "events_by_kind": _count_events_by_kind(town),
    }


def load_timeline(path: str) -> Dict[str, Any]:
    """Load a timeline JSON produced by ``--export`` (or this module)."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or "daily" not in data:
        raise ValueError(f"not a timeline JSON: {path}")
    return data


def _fmt_dollars(cents: Any) -> str:
    try:
        value = int(cents)
    except (TypeError, ValueError):
        return "$?"
    sign = "-" if value < 0 else ""
    value = abs(value)
    return f"{sign}${value // 100}.{value % 100:02d}"


def _esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _series_shop_balances(
    daily: Sequence[Dict[str, Any]],
) -> Dict[str, List[Optional[float]]]:
    """shop_id -> balance dollars per day; missing days are ``None`` gaps.

    A shop that first appears mid-run is gapped at the *front* so the line
    does not invent day-1 history (pad/gap at the front, not the end).
    """
    n = len(daily)
    order: List[str] = []
    seen: set = set()
    for entry in daily:
        shops = entry.get("businesses") or {}
        if not isinstance(shops, dict):
            continue
        for shop_id in shops:
            sid = str(shop_id)
            if sid not in seen:
                seen.add(sid)
                order.append(sid)

    series: Dict[str, List[Optional[float]]] = {sid: [None] * n for sid in order}
    for index, entry in enumerate(daily):
        shops = entry.get("businesses") or {}
        if not isinstance(shops, dict):
            continue
        for shop_id, shop in shops.items():
            if not isinstance(shop, dict):
                continue
            cents = shop.get("balance_cents")
            try:
                dollars: Optional[float] = int(cents) / 100.0
            except (TypeError, ValueError):
                dollars = None
            series[str(shop_id)][index] = dollars
    return series


def _series_avg_wallet(daily: Sequence[Dict[str, Any]]) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for entry in daily:
        residents = entry.get("residents") or {}
        cents = residents.get("avg_wallet_cents") if isinstance(residents, dict) else None
        try:
            out.append(int(cents) / 100.0)
        except (TypeError, ValueError):
            out.append(None)
    return out


def _series_congestion(daily: Sequence[Dict[str, Any]]) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    for entry in daily:
        traffic = entry.get("traffic") or {}
        value = traffic.get("congestion") if isinstance(traffic, dict) else None
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _weather_conditions(daily: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for entry in daily:
        weather = entry.get("weather") or {}
        cond = weather.get("condition") if isinstance(weather, dict) else None
        if cond is None or cond == "":
            out.append("n/a")
        else:
            out.append(str(cond))
    return out


def _polyline_segments(
    values: Sequence[Optional[float]],
    *,
    width: float,
    height: float,
    pad: float,
    y_min: float,
    y_max: float,
) -> List[str]:
    """Build SVG polyline point strings, one per contiguous non-None run."""
    n = len(values)
    if n == 0:
        return []
    inner_w = max(width - 2 * pad, 1.0)
    inner_h = max(height - 2 * pad, 1.0)
    span = y_max - y_min if y_max > y_min else 1.0
    segments: List[str] = []
    pts: List[str] = []

    def flush() -> None:
        nonlocal pts
        if len(pts) >= 2:
            segments.append(" ".join(pts))
        elif len(pts) == 1:
            # Degenerate segment so a lone day still paints a mark.
            segments.append(f"{pts[0]} {pts[0]}")
        pts = []

    for i, value in enumerate(values):
        if value is None:
            flush()
            continue
        x = pad + (inner_w * i / max(n - 1, 1))
        y = pad + inner_h * (1.0 - (value - y_min) / span)
        pts.append(f"{x:.2f},{y:.2f}")
    flush()
    return segments


def _line_chart_svg(
    series: Dict[str, Sequence[Optional[float]]],
    *,
    title: str,
    y_label: str,
    width: int = 720,
    height: int = 240,
    pad: float = 36.0,
    colours: Optional[Sequence[str]] = None,
) -> str:
    """Multi-series line chart as inline SVG (``None`` values become gaps)."""
    if not series:
        return (
            f'<div class="chart"><h3>{_esc(title)}</h3>'
            f'<p class="muted">No data</p></div>'
        )

    all_vals = [v for values in series.values() for v in values if v is not None]
    if not all_vals:
        return (
            f'<div class="chart"><h3>{_esc(title)}</h3>'
            f'<p class="muted">No data</p></div>'
        )
    y_min = min(all_vals)
    y_max = max(all_vals)
    if y_min == y_max:
        y_min -= 1.0
        y_max += 1.0
    # Small padding on y
    margin = (y_max - y_min) * 0.05
    y_min -= margin
    y_max += margin

    palette = list(colours or _SHOP_STROKES)
    lines_svg: List[str] = []
    legend: List[str] = []
    for idx, (name, values) in enumerate(series.items()):
        colour = palette[idx % len(palette)]
        for points in _polyline_segments(
            values,
            width=float(width),
            height=float(height),
            pad=pad,
            y_min=y_min,
            y_max=y_max,
        ):
            lines_svg.append(
                f'<polyline fill="none" stroke="{colour}" stroke-width="2" '
                f'points="{points}" />'
            )
        legend.append(
            f'<span class="swatch" style="background:{colour}"></span>'
            f'<span class="legend-label">{_esc(name)}</span>'
        )

    # Axis labels
    y_top = f"{y_max:.0f}" if abs(y_max) >= 10 else f"{y_max:.2f}"
    y_bot = f"{y_min:.0f}" if abs(y_min) >= 10 else f"{y_min:.2f}"
    n = max(len(next(iter(series.values()))), 1)

    svg = f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}">
  <rect class="plot-bg" x="{pad}" y="{pad}" width="{width - 2 * pad}" height="{height - 2 * pad}" />
  <text class="axis" x="{pad - 6}" y="{pad + 4}" text-anchor="end">{_esc(y_top)}</text>
  <text class="axis" x="{pad - 6}" y="{height - pad}" text-anchor="end">{_esc(y_bot)}</text>
  <text class="axis" x="{pad}" y="{height - 10}" text-anchor="start">day 1</text>
  <text class="axis" x="{width - pad}" y="{height - 10}" text-anchor="end">day {n}</text>
  <text class="axis-title" x="14" y="{height / 2}" transform="rotate(-90 14 {height / 2})">{_esc(y_label)}</text>
  {"".join(lines_svg)}
</svg>'''
    return (
        f'<div class="chart"><h3>{_esc(title)}</h3>'
        f'<div class="legend">{"".join(legend)}</div>{svg}</div>'
    )


def _weather_strip_svg(conditions: Sequence[str], *, width: int = 720, height: int = 48) -> str:
    n = len(conditions)
    if n == 0:
        return '<div class="chart"><h3>Weather</h3><p class="muted">No data</p></div>'
    cell = width / n
    rects: List[str] = []
    for i, cond in enumerate(conditions):
        fill = _WEATHER_FILL.get(cond, "#9aa3ad")
        rects.append(
            f'<rect x="{i * cell:.2f}" y="0" width="{cell:.2f}" height="{height}" '
            f'fill="{fill}"><title>day {i + 1}: {_esc(cond)}</title></rect>'
        )
    legend = "".join(
        f'<span class="swatch" style="background:{fill}"></span>'
        f'<span class="legend-label">{_esc(name)}</span>'
        for name, fill in _WEATHER_FILL.items()
    )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Weather by day">'
        f'{"".join(rects)}</svg>'
    )
    return (
        f'<div class="chart"><h3>Weather strip</h3>'
        f'<div class="legend">{legend}</div>{svg}</div>'
    )


def _leaderboard_rows(daily: Sequence[Dict[str, Any]]) -> List[Tuple[str, int, int, bool]]:
    """Final-day shop rows: (id, balance_cents, sold_yesterday, open)."""
    if not daily:
        return []
    last = daily[-1]
    shops = last.get("businesses") or {}
    if not isinstance(shops, dict):
        return []
    rows: List[Tuple[str, int, int, bool]] = []
    for shop_id, shop in shops.items():
        if not isinstance(shop, dict):
            continue
        try:
            balance = int(shop.get("balance_cents") or 0)
        except (TypeError, ValueError):
            balance = 0
        try:
            sold = int(shop.get("sold_yesterday") or 0)
        except (TypeError, ValueError):
            sold = 0
        open_flag = bool(shop.get("open"))
        rows.append((str(shop_id), balance, sold, open_flag))
    rows.sort(key=lambda row: (-row[1], row[0]))
    return rows


def _leaderboard_html(daily: Sequence[Dict[str, Any]]) -> str:
    rows = _leaderboard_rows(daily)
    if not rows:
        return '<div class="chart"><h3>Final shop leaderboard</h3><p class="muted">No shops</p></div>'
    body = []
    for rank, (shop_id, balance, sold, open_flag) in enumerate(rows, start=1):
        status = "open" if open_flag else "closed"
        body.append(
            "<tr>"
            f"<td>{rank}</td>"
            f"<td>{_esc(shop_id)}</td>"
            f"<td class=\"num\">{_esc(_fmt_dollars(balance))}</td>"
            f"<td class=\"num\">{sold}</td>"
            f"<td>{status}</td>"
            "</tr>"
        )
    return f'''<div class="chart">
  <h3>Final shop leaderboard</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>#</th><th>Shop</th><th>Balance</th><th>Sold yesterday</th><th>Open</th></tr></thead>
      <tbody>
        {"".join(body)}
      </tbody>
    </table>
  </div>
</div>'''


def _css() -> str:
    """Inline stylesheet with light/dark via prefers-color-scheme."""
    return """
:root {
  --bg: #f4efe6;
  --fg: #1c1a17;
  --muted: #5c564c;
  --card: #fffaf2;
  --border: #d9cfc0;
  --plot: #efe8dc;
  --accent: #c45c26;
  --link: #2a6f6f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16181c;
    --fg: #e8e2d8;
    --muted: #a39a8c;
    --card: #1e2228;
    --border: #323842;
    --plot: #262b33;
    --accent: #e8b84a;
    --link: #7eb6b6;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}
header {
  padding: 1.25rem 1rem 0.5rem;
  border-bottom: 1px solid var(--border);
}
header h1 {
  margin: 0 0 0.25rem;
  font-size: clamp(1.4rem, 4vw, 2rem);
  letter-spacing: 0.02em;
}
header p {
  margin: 0;
  color: var(--muted);
  font-size: 0.95rem;
}
main {
  display: grid;
  gap: 1rem;
  padding: 1rem;
  max-width: 880px;
  margin: 0 auto;
}
.chart {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem 0.9rem 1rem;
}
.chart h3 {
  margin: 0 0 0.55rem;
  font-size: 1.05rem;
}
.muted { color: var(--muted); margin: 0; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.75rem;
  margin: 0 0 0.55rem;
  font-size: 0.82rem;
  color: var(--muted);
  align-items: center;
}
.swatch {
  display: inline-block;
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 2px;
  margin-right: 0.25rem;
  vertical-align: middle;
}
.legend-label { margin-right: 0.35rem; }
svg { width: 100%; height: auto; display: block; }
.plot-bg { fill: var(--plot); stroke: var(--border); stroke-width: 1; }
.axis { fill: var(--muted); font-size: 11px; font-family: ui-monospace, Menlo, monospace; }
.axis-title { fill: var(--muted); font-size: 11px; font-family: ui-monospace, Menlo, monospace; }
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
th, td {
  text-align: left;
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid var(--border);
}
th { color: var(--muted); font-weight: 600; }
td.num { font-variant-numeric: tabular-nums; font-family: ui-monospace, Menlo, monospace; }
footer {
  max-width: 880px;
  margin: 0 auto;
  padding: 0 1rem 1.5rem;
  color: var(--muted);
  font-size: 0.8rem;
}
@media (max-width: 520px) {
  main { padding: 0.75rem; gap: 0.75rem; }
  .chart { padding: 0.7rem; border-radius: 8px; }
  th, td { padding: 0.4rem 0.35rem; font-size: 0.85rem; }
}
"""


def render_html(timeline: Dict[str, Any]) -> str:
    """Render a full static HTML document from a timeline dict."""
    daily = timeline.get("daily") or []
    if not isinstance(daily, list):
        daily = []
    seed = timeline.get("seed", "?")
    days = timeline.get("days", len(daily))
    systems = timeline.get("systems") or []

    shop_series = _series_shop_balances(daily)
    wallet_series = {"avg wallet ($)": _series_avg_wallet(daily)}
    congestion_series = {"congestion": _series_congestion(daily)}
    weather = _weather_conditions(daily)

    shop_chart = _line_chart_svg(
        shop_series,
        title="Shop balances over time",
        y_label="balance ($)",
        colours=_SHOP_STROKES,
    )
    wallet_chart = _line_chart_svg(
        wallet_series,
        title="Residents average wallet",
        y_label="avg wallet ($)",
        colours=("#2a6f6f",),
    )
    weather_chart = _weather_strip_svg(weather)
    traffic_chart = _line_chart_svg(
        congestion_series,
        title="Traffic congestion",
        y_label="congestion (0-1)",
        colours=("#3d5a80",),
    )
    board = _leaderboard_html(daily)

    systems_s = ", ".join(_esc(name) for name in systems) if systems else "(none)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Tiny Town dashboard — seed {_esc(seed)}</title>
<style>
{_css()}
</style>
</head>
<body>
<header>
  <h1>Tiny Town</h1>
  <p>seed {_esc(seed)} · {_esc(days)} days · systems: {systems_s}</p>
</header>
<main>
  {shop_chart}
  {wallet_chart}
  {weather_chart}
  {traffic_chart}
  {board}
</main>
<footer>
  Static snapshot. Inline CSS and SVG only — no scripts, no external assets.
</footer>
</body>
</html>
"""


def write_dashboard(path: str, timeline: Dict[str, Any]) -> None:
    """Write the HTML dashboard to the exact ``path``."""
    Path(path).write_text(render_html(timeline), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taro.tinytown.dashboard",
        description="Write a self-contained Tiny Town HTML dashboard.",
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
        metavar="FILE",
        help="load timeline JSON instead of running the town",
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


if __name__ == "__main__":
    cli()
