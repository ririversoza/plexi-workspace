"""Tiny Town Gazette: a weekly newspaper, read from a finished town run.

    python3 -m sora.gazette [--week N | --all]

Read-only: it never draws from ``town.rng`` and never writes town state or files.
See README.md for the headline rules.
"""

import argparse
import copy
import importlib
import math
from collections import Counter

DAYS = 90
SEED = 42
WEEK = 7
WEEKS = -(-DAYS // WEEK)  # 13; the last week is days 85-90

# Contract order from juniper/TINYTOWN.md (Phase 2, shared constants).
SHOP_IDS = (
    "one-mug-tea",
    "bench-and-bell",
    "spoke-and-spanner",
    "matcha-mile",
    "fold-post",
    "daifuku-cart",
)
READS = ("weather", "businesses", "residents", "economy", "traffic", "emergency")
NOT_REPORTED = "no reporter on this beat yet"

ACCIDENT_SPIKE = 8            # accidents in one week that make the front page
TREASURY_SWING_DOLLARS = 100  # a gain this big (or any drop) makes the front page
MOOD_SWING = 10               # avg mood points gained or lost in a week that make the front page
WIDTH = 60


# --- collecting ---------------------------------------------------------------


def snapshot(town):
    """A deep copy of what the paper reads for one day (people lists left out)."""
    state = {name: copy.deepcopy(town.state[name]) for name in READS if isinstance(town.state.get(name), dict)}
    state.get("residents", {}).pop("people", None)
    return {"day": town.day, **state}


def load_systems():
    """Every installed system; the log gets csv_path=None so nothing is written."""
    engine = importlib.import_module("taro.tinytown")
    systems = []
    for name, module_path in engine.SYSTEM_MODULES.items():
        try:
            system_cls = importlib.import_module(module_path).System
        except (ImportError, AttributeError):
            continue
        systems.append(system_cls(csv_path=None) if name == "log" else system_cls())
    return systems


def collect(systems, days=DAYS, seed=SEED):
    """Run the town and return (daily snapshots, events)."""
    engine = importlib.import_module("taro.tinytown")
    days_seen = []
    town = engine.run_town(systems, days=days, seed=seed, on_day=lambda t: days_seen.append(snapshot(t)))
    return days_seen, list(town.events)


def week_of(items, week):
    """Items (snapshots or events) whose day falls in ``week`` (1-based)."""
    first = (week - 1) * WEEK + 1
    return [item for item in items if first <= item.get("day", 0) < first + WEEK]


# --- reading one week ---------------------------------------------------------


def num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def cents(value):
    return f"${value / 100:,.2f}" if num(value) is not None else "?"


def as_dict(value):
    return value if isinstance(value, dict) else {}


def get(day, system, key):
    return as_dict(as_dict(day).get(system)).get(key)


def storm_days(days, events):
    closed = {e["day"] for e in events if e.get("kind") == "shops_closed" and e.get("reason") == "storm"}
    closed |= {d["day"] for d in days if get(d, "weather", "condition") == "storm" and get(d, "businesses", "open_count") == 0}
    return len(closed)


def accidents(days):
    counts = [c for c in (num(get(d, "traffic", "accidents_today")) for d in days) if c is not None]
    return sum(counts) if counts else None


def treasury_change(days, before):
    """Treasury change since the end of last week (week 1: since day 1)."""
    values = [num(get(d, "economy", "treasury")) for d in ([before] if before else []) + days]
    values = [v for v in values if v is not None]
    return round(values[-1] - values[0], 2) if len(values) > 1 else None


def units_sold(days):
    """Units per shop, or None if no day reported purchases (an empty dict counts as 0)."""
    sold = None
    for d in days:
        purchases = get(d, "residents", "purchases")
        if isinstance(purchases, dict):
            sold = sold if sold is not None else Counter()
            sold.update({shop: units for shop, units in purchases.items() if num(units) is not None})
    return sold


def shop_names(days):
    names = {}
    for d in days:
        for shop_id, shop in as_dict(get(d, "businesses", "shops")).items():
            names[shop_id] = as_dict(shop).get("name", shop_id)
    return names


def projects_finished(days, before):
    """Project names completed this week, from economy.projects_completed."""
    lists = [get(d, "economy", "projects_completed") for d in days]
    lists = [x for x in lists if isinstance(x, list)]
    if not lists:
        return []
    start = get(before, "economy", "projects_completed") if before else None
    start = start if isinstance(start, list) else []
    return [name for name in lists[-1] if name not in start]


def mood_change(days, before):
    """Change in residents.avg_mood since the end of last week (week 1: since day 1)."""
    values = [num(get(d, "residents", "avg_mood")) for d in ([before] if before else []) + days]
    values = [v for v in values if v is not None]
    return values[-1] - values[0] if len(values) > 1 else None


def signed(value):
    return f"{'+' if value >= 0 else '-'}{abs(value)}"


def headline(days, events, before=None):
    """The first rule that fires, in the order documented in README.md."""
    finished = projects_finished(days, before)
    if finished:
        return f"TOWN OPENS NEW {' AND '.join(name.upper() for name in finished)}"
    crashes = accidents(days)
    if crashes is not None and crashes >= ACCIDENT_SPIKE:
        return f"ACCIDENT SPIKE: {crashes} CRASHES ON TOWN ROADS"
    swing = mood_change(days, before)
    if swing is not None and abs(swing) >= MOOD_SWING:
        return f"TOWN MOOD {'LIFTS' if swing > 0 else 'SINKS'} {abs(swing)} POINTS"
    storms = storm_days(days, events)
    if storms:
        return f"STORM SHUTS EVERY SHOP ON {storms} DAY{'S' if storms > 1 else ''}"
    change = treasury_change(days, before)
    if change is not None and (change < 0 or change >= TREASURY_SWING_DOLLARS):
        return f"TREASURY {'DOWN' if change < 0 else 'UP'} ${abs(change):,.2f}"
    sold = units_sold(days)
    if sold:
        shop, units = min(sold.items(), key=lambda item: (-item[1], item[0]))
        return f"{shop_names(days).get(shop, shop).upper()} TOPS SALES WITH {units} UNITS"
    return "QUIET WEEK IN TINY TOWN"


# --- sections -----------------------------------------------------------------


def weather_line(days):
    conditions = Counter(c for c in (get(d, "weather", "condition") for d in days) if isinstance(c, str))
    if not conditions:
        return f"Weather: {NOT_REPORTED}"
    summary = ", ".join(f"{n} {c}" for c, n in sorted(conditions.items(), key=lambda item: (-item[1], item[0])))
    temps = [t for t in (num(get(d, "weather", "temp_c")) for d in days) if t is not None]
    return f"Weather: {summary}" + (f" | {min(temps):.0f} to {max(temps):.0f} C" if temps else "")


def shop_table(days):
    shops = get(days[-1], "businesses", "shops") if days else None
    if not isinstance(shops, dict):
        return [f"Shops: {NOT_REPORTED}"]
    sold = units_sold(days)
    order = [s for s in SHOP_IDS if s in shops] + sorted(s for s in shops if s not in SHOP_IDS)
    rows = [f"{'Shop':<26}{'Open':>5}{'Sold':>6}{'Balance':>13}"]
    for shop_id in order:
        shop = as_dict(shops[shop_id])
        open_days = sum(1 for d in days if as_dict(as_dict(get(d, "businesses", "shops")).get(shop_id)).get("open"))
        units = "?" if sold is None else sold.get(shop_id, 0)
        name = str(shop.get("name", shop_id))[:25]
        rows.append(f"{name:<26}{open_days:>4}d{units:>6}{cents(shop.get('balance_cents')):>13}")
    return rows


def wallets_line(days, before=None):
    last = days[-1].get("residents") if days else None
    if not isinstance(last, dict):
        return f"Wallets: {NOT_REPORTED}"
    line = f"Wallets: {last.get('count', '?')} residents, average {cents(last.get('avg_wallet_cents'))}"
    start = num(get(before or days[0], "residents", "avg_wallet_cents"))
    end = num(last.get("avg_wallet_cents"))
    if start is not None and end is not None:
        line += f" ({'+' if end >= start else '-'}{cents(abs(end - start))} this week)"
    return line


def streets_line(days):
    congestion = [c for c in (num(get(d, "traffic", "congestion")) for d in days) if c is not None]
    if congestion:
        traffic = f"Traffic: {accidents(days) or 0} accidents, congestion {sum(congestion) / len(congestion):.0%}"
        if any(isinstance(get(d, "traffic", "bus_running"), bool) for d in days):
            bus_days = sum(1 for d in days if get(d, "traffic", "bus_running") is True)
            riders = sum(num(get(d, "traffic", "bus_riders")) or 0 for d in days)
            traffic += f", bus ran {bus_days} day{'' if bus_days == 1 else 's'} ({riders} riders)" if bus_days else ", no bus"
    else:
        traffic = f"Traffic: {NOT_REPORTED}"
    incidents = [i for i in (num(get(d, "emergency", "incidents_today")) for d in days) if i is not None]
    responded = [r for r in (num(get(d, "emergency", "responded")) for d in days) if r is not None]
    if incidents:
        emergency = f"Emergency: {sum(incidents)} incidents, {sum(responded)} responded"
    else:
        emergency = f"Emergency: {NOT_REPORTED}"
    return f"{traffic} | {emergency}"


def prices_line(days, events):
    """Price moves from this week's price_change events; None when there were none."""
    moves = [e for e in events if e.get("kind") == "price_change"]
    moves = [e for e in moves if num(e.get("old_price_cents")) is not None and num(e.get("new_price_cents")) is not None]
    if not moves:
        return None
    names = shop_names(days)
    changes = [
        f"{names.get(e.get('shop_id'), e.get('shop_id', '?'))} {cents(e['old_price_cents'])} -> {cents(e['new_price_cents'])}"
        for e in moves
    ]
    return "Prices: " + ", ".join(changes)


def mood_line(days, before=None):
    last = get(days[-1], "residents", "avg_mood") if days else None
    if num(last) is None:
        return None
    line = f"Mood of the town: {last} average"
    change = mood_change(days, before)
    if change is not None:
        line += f" ({signed(change)} this week)"
    bands = get(days[-1], "residents", "mood_bands")
    if isinstance(bands, dict):
        start = get(before or days[0], "residents", "mood_bands")
        start = start if isinstance(start, dict) else {}
        parts = []
        for band, count in bands.items():
            if num(count) is None:
                continue
            delta = f" ({signed(count - start[band])})" if num(start.get(band)) is not None else ""
            parts.append(f"{band} {count}{delta}")
        if parts:
            line += " | " + ", ".join(parts)
    return line


def busiest_street_line(days):
    """Street with the most incidents this week (ties: alphabetical); None without street data."""
    totals = Counter()
    seen = False
    for d in days:
        streets = get(d, "emergency", "incidents_by_street")
        if isinstance(streets, dict):
            seen = True
            totals.update({street: n for street, n in streets.items() if num(n) is not None})
    if not seen:
        return None
    if not +totals:
        return "Streets: no incidents on any street"
    street, count = min(totals.items(), key=lambda item: (-item[1], str(item[0])))
    return f"Streets: busiest for incidents was {street} ({count})"


def town_hall_line(days, before=None):
    """Public works: completions this week and the current project; None without the keys."""
    if not any("project" in as_dict(d.get("economy")) or "projects_completed" in as_dict(d.get("economy")) for d in days):
        return None
    parts = [f"{name} completed" for name in projects_finished(days, before)]
    project = get(days[-1], "economy", "project")
    if isinstance(project, dict) and num(project.get("progress")) is not None:
        percent = math.floor(project["progress"] * 100)  # floor: never 100% while unfinished
        parts.append(f"building {project.get('name', '?')} ({percent}%)")
    elif not parts:
        parts.append("no project under way")
    return "Town Hall: " + " | ".join(parts)


def render_week(days, events, week, before=None):
    """One issue of the paper. ``before`` is the last snapshot of the week before."""
    first = (week - 1) * WEEK + 1
    last = days[-1]["day"] if days else first + WEEK - 1
    return "\n".join(
        [
            "=" * WIDTH,
            f"THE TINY TOWN GAZETTE  |  Week {week}  |  Days {first}-{last}".center(WIDTH),
            "=" * WIDTH,
            headline(days, events, before),
            "-" * WIDTH,
            weather_line(days),
            "",
            *shop_table(days),
            *optional(prices_line(days, events)),
            "",
            wallets_line(days, before),
            *optional(mood_line(days, before)),
            streets_line(days),
            *optional(busiest_street_line(days)),
            *optional(town_hall_line(days, before)),
        ]
    )


def optional(line):
    """A section that only prints when its system reported something."""
    return [] if line is None else [line]


def render(days_seen, events, weeks):
    issues = []
    for week in weeks:
        previous = week_of(days_seen, week - 1)
        before = previous[-1] if previous else None
        issues.append(render_week(week_of(days_seen, week), week_of(events, week), week, before))
    return "\n\n".join(issues)


# --- CLI ----------------------------------------------------------------------


def week_number(text):
    try:
        week = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"week must be a number, got {text!r}") from None
    if not 1 <= week <= WEEKS:
        raise argparse.ArgumentTypeError(f"week must be 1-{WEEKS}, got {week}")
    return week


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m sora.gazette", description="The Tiny Town Gazette.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--week", type=week_number, default=WEEKS, help=f"issue to print, 1-{WEEKS} (default {WEEKS})")
    group.add_argument("--all", action="store_true", help="print every weekly issue")
    args = parser.parse_args(argv)
    try:
        systems = load_systems()
    except ImportError:
        print(f"The presses are cold: taro.tinytown is {NOT_REPORTED}.")
        return 0
    days_seen, events = collect(systems)
    print(render(days_seen, events, range(1, WEEKS + 1) if args.all else [args.week]))
    return 0


__all__ = ["collect", "headline", "load_systems", "main", "render", "render_week", "snapshot", "week_of"]
