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


def shop_box(shop_id, shop, names, purchases):
    """One storefront as a list of equal-width lines."""
    status = "OPEN" if shop.get("open") else "CLOSED"
    staff = [f"  {label}" if label else "" for label in staff_lines(shop.get("staff"), names)]
    body = [
        shop.get("name", shop_id),
        f"{status:<8}{cents(shop.get('price_cents'))} each",
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
    return lines


def traffic_text(state):
    traffic = state.get("traffic")
    if not isinstance(traffic, dict):
        return NOT_BUILT
    congestion = traffic.get("congestion")
    congestion_text = f"{congestion:.0%}" if is_number(congestion) else "?"
    return (
        f"{traffic.get('commuters', '?')} commuters, congestion {congestion_text}, "
        f"{traffic.get('accidents_today', '?')} accidents"
    )


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


def ticker(state):
    return [
        f"TICKER   traffic:   {traffic_text(state)}",
        f"         emergency: {emergency_text(state)}",
        f"         treasury:  {treasury_text(state)}",
    ]


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
