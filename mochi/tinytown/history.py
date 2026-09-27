"""Shop balance history: snapshot each shop's balance per day and draw it as an ASCII chart.

Read-only: works from ``town.state`` snapshots, never touches ``town.rng`` or emits.
Used by ``python3 -m mochi.tinytown.view --history <shop_id|all>``.
"""

from typing import NamedTuple, Optional

CHART_COLUMNS = 60
CHART_ROWS = 12
Y_LABEL_WIDTH = 12
POINT = "*"
STORM_MARK = "S"
ZERO_MARK = "0"
MID_DAY = 45


class DayPoint(NamedTuple):
    day: int
    balance_cents: Optional[int]
    storm_closed: bool
    at_zero: bool


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cents(value):
    return f"${value / 100:,.2f}" if is_number(value) else "?"


# --- collecting -------------------------------------------------------------


def snapshot(state, day):
    """``{shop_id: (name, DayPoint)}`` for one day, or None when businesses isn't built."""
    businesses = state.get("businesses") if isinstance(state, dict) else None
    if not isinstance(businesses, dict):
        return None
    weather = state.get("weather")
    storm = isinstance(weather, dict) and weather.get("condition") == "storm"
    shops = businesses.get("shops")
    result = {}
    for shop_id, shop in (shops.items() if isinstance(shops, dict) else ()):
        if not isinstance(shop, dict):
            continue
        balance = shop.get("balance_cents")
        balance = balance if is_number(balance) else None
        point = DayPoint(day, balance, storm and not shop.get("open", True), balance == 0)
        result[str(shop_id)] = (str(shop.get("name", shop_id)), point)
    return result


def series_for(frames, shop_id):
    """(name, [DayPoint, ...]) for one shop across ``[(day, snapshot), ...]``; skips gaps."""
    name, points = shop_id, []
    for _, shops in frames:
        if shops and shop_id in shops:
            name, point = shops[shop_id]
            points.append(point)
    return name, points


def known_shops(frames, preferred_order=()):
    """Every shop id seen in any frame: ``preferred_order`` first, then the rest sorted."""
    seen = {sid for _, shops in frames if shops for sid in shops}
    ordered = [sid for sid in preferred_order if sid in seen]
    return ordered + sorted(seen - set(ordered))


# --- drawing ----------------------------------------------------------------


def column_of(day, days, width=CHART_COLUMNS):
    """Map day 1..days onto chart columns 0..width-1 (clamped)."""
    if days <= 1:
        return 0
    return min(width - 1, max(0, (day - 1) * width // days))


def level_of(value, top, rows=CHART_ROWS):
    """Map 0..top onto rows 0 (bottom)..rows-1 (top), clamped."""
    if top <= 0:
        return 0
    return min(rows - 1, max(0, round(value * (rows - 1) / top)))


def column_buckets(points, days, width=CHART_COLUMNS):
    buckets = [[] for _ in range(width)]
    for point in points:
        buckets[column_of(point.day, days, width)].append(point)
    return buckets


def plot_grid(buckets, top, rows=CHART_ROWS):
    """rows x width characters, top row first. A column shows its last day's balance."""
    grid = [[" "] * len(buckets) for _ in range(rows)]
    for col, bucket in enumerate(buckets):
        balances = [p.balance_cents for p in bucket if p.balance_cents is not None]
        if balances:
            grid[rows - 1 - level_of(balances[-1], top, rows)][col] = POINT
    return ["".join(row) for row in grid]


def marker_row(buckets, flag, mark):
    return "".join(mark if any(getattr(p, flag) for p in bucket) else " " for bucket in buckets)


def y_label(row, top, rows=CHART_ROWS):
    if row == 0:
        return cents(top)
    if row == rows - 1:
        return cents(0)
    if row == rows // 2:
        return cents(round(top * (rows - 1 - row) / (rows - 1)))
    return ""


def x_labels(days, width=CHART_COLUMNS):
    line = [" "] * width
    for day in (1, MID_DAY, days):
        if 1 <= day <= days:
            text = str(day)
            start = min(column_of(day, days, width), width - len(text))
            line[start : start + len(text)] = text
    return "".join(line)


def extreme(points, pick):
    valid = [p for p in points if p.balance_cents is not None]
    return pick(valid, key=lambda p: p.balance_cents) if valid else None


def summary(points):
    low = extreme(points, min)
    high = extreme(points, max)
    final = next((p for p in reversed(points) if p.balance_cents is not None), None)

    def describe(label, point):
        return f"{label} {cents(point.balance_cents)} (day {point.day})" if point else f"{label} ?"

    storms = sum(p.storm_closed for p in points)
    zeros = sum(p.at_zero for p in points)
    return (
        f"{describe('min', low)}  {describe('max', high)}  {describe('final', final)}\n"
        f"storm-closed days: {storms}  $0 days: {zeros}"
    )


def chart(shop_id, name, points, days, seed):
    """The full chart for one shop as a string (header, grid, axis, markers, summary)."""
    header = f"{name} ({shop_id}) balance, days 1-{days}, seed {seed}"
    if not any(p.balance_cents is not None for p in points):
        return f"{header}\n  no balance data"
    top = max(p.balance_cents for p in points if p.balance_cents is not None)
    buckets = column_buckets(points, days)
    pad = " " * Y_LABEL_WIDTH
    lines = [header]
    for row, cells in enumerate(plot_grid(buckets, top)):
        lines.append(f"{y_label(row, top):>{Y_LABEL_WIDTH}} |{cells}")
    lines.append(f"{pad} +{'-' * CHART_COLUMNS}")
    lines.append(f"{pad}  {x_labels(days)}  day")
    lines.append(f"{'storm':>{Y_LABEL_WIDTH}}  {marker_row(buckets, 'storm_closed', STORM_MARK)}")
    lines.append(f"{'$0':>{Y_LABEL_WIDTH}}  {marker_row(buckets, 'at_zero', ZERO_MARK)}")
    lines.append(summary(points))
    return "\n".join(lines)
