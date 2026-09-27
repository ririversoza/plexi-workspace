"""Tiny Town viewer: run the town in-process and draw an ASCII snapshot of a day.

    python3 -m mochi.tinytown.view [--day N | --every | --history SHOP_ID|all] [--seed N]

``--history`` charts each shop's balance instead (see ``history.py``); ``--seed`` picks
another town.

Runs every installed system through ``taro.tinytown`` (seed 42, 90 days) and draws
day N (default 90), or every day with ``--every``. Anything not installed yet is
drawn as "not built yet". The log is loaded with ``csv_path=None`` so viewing never
writes the event CSV.
"""

import argparse
import importlib
import sys

from mochi.tinytown import history

DAYS = 90
SEED = 42
NOT_BUILT = "not built yet"

# Contract order from juniper/TINYTOWN.md (Phase 2, shared constants).
SHOP_IDS = (
    "one-mug-tea",
    "bench-and-bell",
    "spoke-and-spanner",
    "matcha-mile",
    "fold-post",
    "daifuku-cart",
)
# Catalog base prices, copied from nori/shops/README.md (not imported). A shop's own
# "base_price_cents", if Nori ever adds one to state, wins over this table.
BASE_PRICE_CENTS = {
    "one-mug-tea": 325,
    "bench-and-bell": 6900,
    "spoke-and-spanner": 7500,
    "matcha-mile": 550,
    "fold-post": 800,
    "daifuku-cart": 375,
}
PRICE_UP = "↑"
PRICE_DOWN = "↓"
MOOD_BANDS = ("happy", "ok", "unhappy")
BOX_INNER = 24
BOXES_PER_ROW = 3
STAFF_LINES = 2
TOP_WALLETS = 3
RULE_WIDTH = BOXES_PER_ROW * (BOX_INNER + 4) + (BOXES_PER_ROW - 1)


# --- formatting helpers -----------------------------------------------------


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cents(value):
    """Integer cents -> "$1,234.56". Anything non-numeric -> "?"."""
    return f"${value / 100:,.2f}" if is_number(value) else "?"


def dollars(value):
    """Float dollars (economy.treasury) -> "$1,234.56"."""
    return f"${value:,.2f}" if is_number(value) else "?"


def fit(text, width):
    """Pad or truncate ``text`` to exactly ``width`` characters."""
    text = str(text)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def as_dict(value):
    return value if isinstance(value, dict) else {}


# --- panels -----------------------------------------------------------------


def weather_banner(state):
    weather = state.get("weather")
    if not isinstance(weather, dict):
        return f"WEATHER  {NOT_BUILT}"
    temp = weather.get("temp_c")
    temp_text = f"{temp:.1f}C" if is_number(temp) else "?C"
    return f"WEATHER  {weather.get('condition', '?')}  {temp_text}  {weather.get('season', '?')}"


def resident_names(state):
    """{resident_id: name} from residents.people, or {} when residents is missing."""
    people = as_dict(state.get("residents")).get("people") or []
    return {p.get("id"): p.get("name", "?") for p in people if isinstance(p, dict)}


def staff_lines(staff, names):
    """Exactly STAFF_LINES labels, so every box has the same height."""
    labels = [names.get(rid, f"#{rid}") for rid in staff or []]
    if not labels:
        labels = ["no staff"]
    if len(labels) > STAFF_LINES:
        labels = labels[: STAFF_LINES - 1] + [f"+{len(labels) - STAFF_LINES + 1} more"]
    return labels + [""] * (STAFF_LINES - len(labels))


def units_sold(shop_id, shop, purchases):
    """Units residents bought today; falls back to the shop's own sold_yesterday."""
    if purchases is not None:
        return purchases.get(shop_id, 0)
    return shop.get("sold_yesterday", 0)


def price_arrow(shop_id, shop):
    """" ↑" / " ↓" when today's price is above / below base; "" when equal or unknown."""
    price = shop.get("price_cents")
    base = shop.get("base_price_cents", BASE_PRICE_CENTS.get(shop_id))
    if not (is_number(price) and is_number(base)) or price == base:
        return ""
    return f" {PRICE_UP}" if price > base else f" {PRICE_DOWN}"


def shop_box(shop_id, shop, names, purchases):
    """One storefront as a list of equal-width lines."""
    status = "OPEN" if shop.get("open") else "CLOSED"
    staff = [f"  {label}" if label else "" for label in staff_lines(shop.get("staff"), names)]
    body = [
        shop.get("name", shop_id),
        f"{status:<8}{cents(shop.get('price_cents'))} each{price_arrow(shop_id, shop)}",
        f"sold {units_sold(shop_id, shop, purchases)}",
        f"bal {cents(shop.get('balance_cents'))}",
    ] + staff
    edge = "+" + "-" * (BOX_INNER + 2) + "+"
    return [edge] + [f"| {fit(line, BOX_INNER)} |" for line in body] + [edge]


def ordered_shop_ids(shops):
    """Contract shops first (in contract order), then any extras sorted."""
    known = [sid for sid in SHOP_IDS if sid in shops]
    extra = sorted(str(sid) for sid in shops if sid not in SHOP_IDS)
    return known + extra


def storefronts(state):
    businesses = state.get("businesses")
    if not isinstance(businesses, dict):
        return [f"STOREFRONTS  {NOT_BUILT}"]
    shops = as_dict(businesses.get("shops"))
    if not shops:
        return ["STOREFRONTS  (no shops)"]
    residents = state.get("residents")
    purchases = as_dict(residents.get("purchases")) if isinstance(residents, dict) else None
    names = resident_names(state)
    boxes = [shop_box(sid, as_dict(shops[sid]), names, purchases) for sid in ordered_shop_ids(shops)]
    lines = [f"STOREFRONTS  {businesses.get('open_count', '?')} open"]
    for start in range(0, len(boxes), BOXES_PER_ROW):
        row = boxes[start : start + BOXES_PER_ROW]
        lines.extend(" ".join(parts) for parts in zip(*row))
    return lines


def top_wallets(people, n=TOP_WALLETS):
    """The ``n`` richest residents; ties go to the lower id."""
    valid = [p for p in people if isinstance(p, dict) and is_number(p.get("wallet_cents"))]
    return sorted(valid, key=lambda p: (-p["wallet_cents"], p.get("id", 0)))[:n]


def residents_panel(state):
    residents = state.get("residents")
    if not isinstance(residents, dict):
        return [f"RESIDENTS  {NOT_BUILT}"]
    lines = [
        f"RESIDENTS  {residents.get('count', '?')} people | "
        f"{residents.get('employed', '?')} employed | "
        f"avg wallet {cents(residents.get('avg_wallet_cents'))}"
    ]
    richest = top_wallets(residents.get("people") or [])
    if richest:
        ranked = "  ".join(
            f"{rank}. {p.get('name', '?')} {cents(p['wallet_cents'])}"
            for rank, p in enumerate(richest, start=1)
        )
        lines.append(f"  top wallets: {ranked}")
    mood = mood_line(residents)
    if mood:
        lines.append(mood)
    return lines


def mood_line(residents):
    """Kiwi's avg_mood (0-100) and mood_bands; None when neither key exists."""
    if "avg_mood" not in residents and "mood_bands" not in residents:
        return None
    avg = residents.get("avg_mood")
    avg_text = f"{avg}/100" if is_number(avg) else "n/a"
    bands = as_dict(residents.get("mood_bands"))
    order = [b for b in MOOD_BANDS if b in bands] + sorted(str(b) for b in bands if b not in MOOD_BANDS)
    bands_text = " | ".join(f"{band} {bands[band]}" for band in order) or "bands n/a"
    return f"  mood: avg {avg_text} | {bands_text}"


def traffic_text(state):
    traffic = state.get("traffic")
    if not isinstance(traffic, dict):
        return NOT_BUILT
    congestion = traffic.get("congestion")
    congestion_text = f"{congestion:.0%}" if is_number(congestion) else "?"
    return (
        f"{traffic.get('commuters', '?')} commuters, congestion {congestion_text}, "
        f"{traffic.get('accidents_today', '?')} accidents{bus_text(traffic)}"
    )


def bus_text(traffic):
    """Bao's bus_running / bus_riders as a traffic suffix; "" when neither key exists."""
    if "bus_running" not in traffic and "bus_riders" not in traffic:
        return ""
    running = traffic.get("bus_running")
    status = "bus running" if running is True else "no bus" if running is False else "bus n/a"
    riders = traffic.get("bus_riders")
    riders_text = f" ({riders} riders)" if is_number(riders) else ""
    return f", {status}{riders_text}"


def emergency_text(state):
    emergency = state.get("emergency")
    if not isinstance(emergency, dict):
        return NOT_BUILT
    avg = emergency.get("avg_response_min")
    avg_text = f"{avg:.1f} min" if is_number(avg) else "?"
    return (
        f"{emergency.get('incidents_today', '?')} incidents, "
        f"{emergency.get('responded', '?')} responded, avg {avg_text}, "
        f"{emergency.get('open_incidents', '?')} open"
    )


def treasury_text(state):
    economy = state.get("economy")
    if not isinstance(economy, dict):
        return NOT_BUILT
    return dollars(economy.get("treasury"))


def project_text(project):
    """Sora's ``project``: a dict with "name" (and "progress" 0..1), a plain string, or None."""
    if project is None:
        return "no project"
    if isinstance(project, str) and project:
        return f"building {project}"
    if isinstance(project, dict) and project.get("name"):
        progress = project.get("progress")
        percent = f" ({int(progress * 100)}%)" if is_number(progress) and 0 <= progress <= 1 else ""
        return f"building {project['name']}{percent}"
    return "building n/a"


def completed_text(done):
    """Sora's ``projects_completed`` is a list of names; a plain count is accepted too."""
    if isinstance(done, (list, tuple)):
        return f"{len(done)} completed"
    if is_number(done):
        return f"{done} completed"
    return "completed n/a"


def town_hall_text(state):
    """Sora's economy project / projects_completed; None when neither key exists."""
    economy = state.get("economy")
    if not isinstance(economy, dict) or ("project" not in economy and "projects_completed" not in economy):
        return None
    project = economy.get("project") if "project" in economy else ""
    return f"{project_text(project)} | {completed_text(economy.get('projects_completed'))}"


def ticker(state):
    lines = [
        f"TICKER   traffic:   {traffic_text(state)}",
        f"         emergency: {emergency_text(state)}",
        f"         treasury:  {treasury_text(state)}",
    ]
    town_hall = town_hall_text(state)
    if town_hall:
        lines.append(f"         town hall: {town_hall}")
    return lines


def render(state, day, days=DAYS):
    """Draw the whole town for one day. ``state`` is ``town.state``; never raises on gaps."""
    state = as_dict(state)
    title = f" Tiny Town | Day {day} / {days} "
    lines = [title.center(RULE_WIDTH, "="), weather_banner(state), ""]
    lines += storefronts(state) + [""]
    lines += residents_panel(state) + [""]
    lines += ticker(state)
    lines.append("=" * RULE_WIDTH)
    return "\n".join(lines)


# --- running the town -------------------------------------------------------


def load_systems(modules):
    """Instantiate ``System`` from each ``{name: module_path}``; skip what isn't installed.

    The log (``name == "log"``) gets ``csv_path=None`` so viewing writes no files.
    """
    systems = []
    for name, module_path in modules.items():
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        system_cls = getattr(module, "System", None)
        if system_cls is None:
            continue
        systems.append(system_cls(csv_path=None) if name == "log" else system_cls())
    return systems


def run_engine(on_day, days=DAYS, seed=SEED):
    """Run every installed system through ``taro.tinytown``, calling ``on_day(town)`` daily.

    The viewer only reads ``town.state`` in ``on_day``: it makes no ``town.rng`` draws.
    """
    try:
        engine = importlib.import_module("taro.tinytown")
    except ImportError:
        raise SystemExit(f"view: the engine (taro.tinytown) is {NOT_BUILT}")
    # Use the engine's own catalog, so only systems this engine version ticks are loaded.
    systems = load_systems(engine.SYSTEM_MODULES)
    return engine.run_town(systems, days=days, seed=seed, on_day=on_day)


def run(show_day, days=DAYS, seed=SEED):
    """Run the town and return rendered frames: just ``show_day``, or every day if None."""
    frames = []

    def on_day(town):
        if show_day is None or town.day == show_day:
            frames.append(render(town.state, town.day, days))

    run_engine(on_day, days, seed)
    return frames


def run_history(target, days=DAYS, seed=SEED):
    """Balance charts for ``target`` (a shop id or "all"). Returns ``(text, exit_code)``."""
    frames = []
    run_engine(lambda town: frames.append((town.day, history.snapshot(town.state, town.day))), days, seed)
    if all(shops is None for _, shops in frames):
        return f"history: businesses {NOT_BUILT}", 0
    shop_ids = history.known_shops(frames, SHOP_IDS)
    if target != "all" and target not in shop_ids:
        known = ", ".join(shop_ids) or "(none)"
        return f"history: no shop {target!r} in this town. Known: {known}, or all", 2
    wanted = shop_ids if target == "all" else [target]
    charts = [history.chart(sid, *history.series_for(frames, sid), days, seed) for sid in wanted]
    return "\n\n".join(charts), 0


def day_number(text):
    try:
        day = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text!r}")
    if not 1 <= day <= DAYS:
        raise argparse.ArgumentTypeError(f"day must be 1..{DAYS}, got {day}")
    return day


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m mochi.tinytown.view",
        description=f"Run Tiny Town ({DAYS} days) and draw it as ASCII.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--day", type=day_number, default=DAYS, help=f"day to draw, 1..{DAYS} (default {DAYS})")
    group.add_argument("--every", action="store_true", help=f"draw all {DAYS} days in sequence")
    group.add_argument("--history", metavar="SHOP_ID|all", help="chart shop balances over all days")
    parser.add_argument("--seed", type=int, default=SEED, help=f"town seed (default {SEED})")
    args = parser.parse_args(argv)
    if args.history is not None:
        text, code = run_history(args.history, seed=args.seed)
        print(text, file=sys.stderr if code else sys.stdout)
        return code
    print("\n\n".join(run(None if args.every else args.day, seed=args.seed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
