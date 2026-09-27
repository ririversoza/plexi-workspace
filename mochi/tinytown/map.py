"""Tiny Town map: one self-contained HTML/SVG picture of the town on a chosen day.

    python3 -m mochi.tinytown.map --out PATH [--seed N] [--day N]

Runs the town in-process (like ``view.py``), keeps a plain snapshot of day N (default:
the last day) and writes it to ``--out``: each street with one house per resident who
lives there, streets with incidents (or the day's busiest street) highlighted, and each
shop as a building coloured by balance (red at $0, green for the richest shop).

Read-only: it never draws from ``town.rng``, loads the log with ``csv_path=None`` and
writes nothing but ``--out``. The page is inline CSS + SVG only, with no scripts or
external assets. Shops have no street address in town state, so they get their own block.
"""

import argparse
import html
from pathlib import Path

from mochi.tinytown import bills, history, view

DAYS = view.DAYS
SEED = view.SEED

WIDTH = 480  # SVG user units; narrow so text stays legible when a phone scales it down
MARGIN = 16
SHOP_COLUMNS = 2
SHOP_ROW_HEIGHT = 64
SHOP_SIZE = 34
HOUSE_SIZE = 10
HOUSE_STEP = 13
AVENUE_WIDTH = 10
ROAD_HEIGHT = 22
STREET_GAP = 14
SECTION_GAP = 28
HUE_RED = 0
HUE_GREEN = 120
SATURATION_LIGHTNESS = "62% 48%"
DOT_RADIUS = 3.5

is_number = history.is_number
cents = history.cents
as_dict = view.as_dict


# --- snapshot: plain data read from town.state -------------------------------


def snapshot(state):
    """The parts of ``state`` the map draws, copied into new plain values."""
    state = as_dict(state)
    return {
        "shops": _shops(as_dict(as_dict(state.get("businesses")).get("shops")), bills.shop_arrears(state)),
        "streets": _streets(as_dict(state.get("residents")), as_dict(state.get("emergency"))),
        "bills_reported": bills.reported(state),
        "weather": as_dict(state.get("weather")).get("condition"),
        "congestion": _number(as_dict(state.get("traffic")).get("congestion")),
        "accidents": _number(as_dict(state.get("traffic")).get("accidents_today")),
    }


def _number(value):
    return value if is_number(value) else None


def _shops(shops, arrears):
    return [
        {
            "id": str(shop_id),
            "name": str(shop.get("name") or shop_id),
            "balance_cents": _number(shop.get("balance_cents")),
            "open": shop.get("open") is True,
            "arrears_cents": arrears.get(shop_id),
        }
        for shop_id, shop in shops.items()
        if isinstance(shop, dict)
    ]


def _streets(residents, emergency):
    """Streets in name order; ``behind`` is one flag per home (None before per-person arrears)."""
    homes = {}
    behind = {}
    people = residents.get("people")
    people = [p for p in people if isinstance(p, dict)] if isinstance(people, list) else []
    arrears_known = any(bills.person_arrears(p) is not None for p in people)
    for person in people:
        street = person.get("street")
        if isinstance(street, str) and street:
            homes[street] = homes.get(street, 0) + 1
            behind.setdefault(street, []).append((bills.person_arrears(person) or 0) > 0)
    incidents = {
        str(name): count if is_number(count) else 0
        for name, count in as_dict(emergency.get("incidents_by_street")).items()
    }
    busiest = emergency.get("busiest_street")
    return [
        {
            "name": name,
            "homes": homes.get(name, 0),
            "incidents": incidents.get(name, 0),
            "busiest": name == busiest,
            "behind": behind.get(name, []) if arrears_known else None,
        }
        for name in sorted(set(homes) | set(incidents))
    ]


def capture(day=DAYS, seed=SEED):
    """Run the town and return the snapshot of ``day``."""
    found = {}

    def on_day(town):
        if town.day == day:
            found["snap"] = snapshot(town.state)

    view.run_engine(on_day, DAYS, seed)
    return found.get("snap", snapshot({}))


# --- drawing -----------------------------------------------------------------


def esc(value):
    return html.escape(str(value), quote=True)


def balance_hue(balance, top):
    """0 (red) at $0 or below, up to 120 (green) at ``top``; None when unknown."""
    if not is_number(balance):
        return None
    if balance <= 0 or top <= 0:
        return HUE_RED
    return round(HUE_GREEN * min(balance / top, 1))


def _money(balance):
    return cents(balance) if isinstance(balance, int) else view.dollars(balance)


def _is_behind(owed):
    return is_number(owed) and owed > 0


def _dot(cx, cy, extra=""):
    return f'<circle class="behind"{extra} cx="{cx}" cy="{cy}" r="{DOT_RADIUS}"/>'


def _shop_svg(shop, x, y, top):
    hue = balance_hue(shop["balance_cents"], top)
    classes = "shop" + ("" if shop["open"] else " closed") + (" unknown" if hue is None else "")
    style = "" if hue is None else f' style="fill:hsl({hue} {SATURATION_LIGHTNESS})"'
    status = "open" if shop["open"] else "closed"
    behind = _is_behind(shop["arrears_cents"])
    if behind:
        status += f" · owes {cents(shop['arrears_cents'])}"
        dot = _dot(x + SHOP_SIZE, y + 12, f' data-shop-behind="{esc(shop["id"])}"')
    tx = x + SHOP_SIZE + 8
    return (
        f'<g><title>{esc(shop["name"])}: {esc(_money(shop["balance_cents"]))}, {esc(status)}</title>'
        f'<polygon class="roof" points="{x - 3},{y + 12} {x + SHOP_SIZE / 2},{y} {x + SHOP_SIZE + 3},{y + 12}"/>'
        f'<rect class="{classes}" data-shop="{esc(shop["id"])}"{style} x="{x}" y="{y + 12}" '
        f'width="{SHOP_SIZE}" height="{SHOP_SIZE - 12}" rx="2"/>'
        f'<text class="label strong" x="{tx}" y="{y + 16}">{esc(shop["name"])}</text>'
        f'<text class="label" x="{tx}" y="{y + 32}">{esc(_money(shop["balance_cents"]))}</text>'
        f'<text class="muted" x="{tx}" y="{y + 46}">{esc(status)}</text>'
        + (dot if behind else "")
        + "</g>"
    )


def _shops_svg(shops, y):
    parts = [f'<text class="heading" x="{MARGIN}" y="{y}">Shops</text>']
    y += 14
    if not shops:
        parts.append(f'<text class="muted" x="{MARGIN}" y="{y + 16}">no shops yet</text>')
        return parts, y + 28
    top = max((s["balance_cents"] for s in shops if is_number(s["balance_cents"])), default=0)
    column = (WIDTH - 2 * MARGIN) / SHOP_COLUMNS
    for i, shop in enumerate(shops):
        row, col = divmod(i, SHOP_COLUMNS)
        parts.append(_shop_svg(shop, MARGIN + 3 + col * column, y + row * SHOP_ROW_HEIGHT, top))
    rows = -(-len(shops) // SHOP_COLUMNS)
    return parts, y + rows * SHOP_ROW_HEIGHT


def _house(x, y, behind=False):
    h = HOUSE_SIZE
    house = f'<path class="home" d="M{x},{y + h} v{-h * 0.55} l{h / 2},{-h * 0.45} l{h / 2},{h * 0.45} v{h * 0.55} z"/>'
    return house + (_dot(x + h, y + 1) if behind else "")


def _street_svg(street, y):
    x0 = MARGIN + AVENUE_WIDTH + 6
    per_row = max(int((WIDTH - x0 - MARGIN) // HOUSE_STEP), 1)
    rows = -(-street["homes"] // per_row)
    flags = street["behind"] or [False] * street["homes"]
    parts = [
        _house(x0 + (i % per_row) * HOUSE_STEP, y + (i // per_row) * HOUSE_STEP, flags[i])
        for i in range(street["homes"])
    ]
    road_y = y + rows * HOUSE_STEP + 4
    hot = street["incidents"] > 0 or street["busiest"]
    notes = [f"{street['homes']} home{'' if street['homes'] == 1 else 's'}"]
    notes.append(f"{street['incidents']} incident{'' if street['incidents'] == 1 else 's'}")
    if street["busiest"]:
        notes.append("busiest")
    if street["behind"] and any(street["behind"]):
        notes.append(f"{sum(street['behind'])} behind")
    parts.append(
        f'<rect class="road{" hot" if hot else ""}" data-street="{esc(street["name"])}" '
        f'x="{MARGIN}" y="{road_y}" width="{WIDTH - 2 * MARGIN}" height="{ROAD_HEIGHT}">'
        f'<title>{esc(street["name"])}: {esc(", ".join(notes))}</title></rect>'
        f'<text class="on-road strong" x="{x0}" y="{road_y + 15}">{esc(street["name"])}</text>'
        f'<text class="on-road" x="{WIDTH - MARGIN - 6}" y="{road_y + 15}" text-anchor="end">'
        f'{esc(" · ".join(notes))}</text>'
    )
    return parts, road_y + ROAD_HEIGHT


def _streets_svg(streets, y):
    parts = [f'<text class="heading" x="{MARGIN}" y="{y}">Streets and homes</text>']
    y += 14
    if not streets:
        parts.append(f'<text class="muted" x="{MARGIN}" y="{y + 16}">no streets yet</text>')
        return parts, y + 28
    top = y
    drawn = []
    for street in streets:
        street_parts, y = _street_svg(street, y)
        drawn.extend(street_parts)
        y += STREET_GAP
    # A cross avenue on the left turns the street rows into a grid.
    parts.append(f'<rect class="road" x="{MARGIN}" y="{top}" width="{AVENUE_WIDTH}" height="{y - STREET_GAP - top}"/>')
    return parts + drawn, y - STREET_GAP


def _legend_svg(y, bills_reported=False):
    bar_x, bar_w = MARGIN, 140
    swatch_x = bar_x + bar_w + 70
    return [
        '<defs><linearGradient id="balance-scale">'
        f'<stop offset="0" stop-color="hsl({HUE_RED} {SATURATION_LIGHTNESS})"/>'
        f'<stop offset="0.5" stop-color="hsl({(HUE_RED + HUE_GREEN) // 2} {SATURATION_LIGHTNESS})"/>'
        f'<stop offset="1" stop-color="hsl({HUE_GREEN} {SATURATION_LIGHTNESS})"/>'
        "</linearGradient></defs>",
        f'<rect x="{bar_x}" y="{y}" width="{bar_w}" height="10" fill="url(#balance-scale)"/>',
        f'<text class="muted" x="{bar_x}" y="{y + 24}">$0</text>',
        f'<text class="muted" x="{bar_x + bar_w}" y="{y + 24}" text-anchor="end">richest shop</text>',
        f'<rect class="road hot" x="{swatch_x}" y="{y}" width="24" height="10"/>',
        f'<text class="muted" x="{swatch_x + 30}" y="{y + 9}">incidents or busiest</text>',
    ] + ([_dot(swatch_x + 12, y + 20).replace('class="behind"', 'class="behind legend"'), f'<text class="muted" x="{swatch_x + 30}" y="{y + 24}">behind on payments</text>']
         if bills_reported else [])


def render_svg(snap):
    shops, y = _shops_svg(snap["shops"], MARGIN + 12)
    streets, y = _streets_svg(snap["streets"], y + SECTION_GAP)
    legend = _legend_svg(y + SECTION_GAP - 8, snap["bills_reported"])
    height = y + SECTION_GAP + 28
    return (
        f'<svg viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Map of Tiny Town">'
        + "".join(shops + streets + legend)
        + "</svg>"
    )


def _facts(snap, day, seed):
    facts = [f"Day {day} of {DAYS}", f"seed {seed}"]
    if snap["weather"]:
        facts.append(str(snap["weather"]))
    if snap["congestion"] is not None:
        facts.append(f"congestion {snap['congestion']:.0%}")
    if snap["accidents"] is not None:
        facts.append(f"{snap['accidents']} accident{'' if snap['accidents'] == 1 else 's'}")
    if snap["bills_reported"]:
        facts.append(_behind_fact(snap))
    return " · ".join(facts)


def _behind_fact(snap):
    """Households and shops behind on payments, matching the red dots; n/a when unreported."""
    homes = [st["behind"] for st in snap["streets"] if st["behind"] is not None]
    owed = [s["arrears_cents"] for s in snap["shops"] if s["arrears_cents"] is not None]
    if not homes and not owed:
        return "behind n/a"
    households = sum(sum(flags) for flags in homes)
    shops = sum(1 for cents_owed in owed if cents_owed > 0)
    home_text = f"{households} household{'' if households == 1 else 's'}" if homes else "households n/a"
    shop_text = f"{shops} shop{'' if shops == 1 else 's'}" if owed else "shops n/a"
    return f"{home_text}, {shop_text} behind"


CSS = """
/* Road colours keep 11px street names at 5:1+ contrast in both themes. */
:root { --bg:#f6f1e7; --fg:#1f1b16; --muted:#6b6358; --card:#fffaf1; --road:#6f6a61;
  --road-text:#ffffff; --hot:#b0510f; --home:#7a8fa6; --roof:#5b4a3a; --unknown:#b9b2a6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#17150f; --fg:#f1ebe0; --muted:#a8a092; --card:#221f18; --road:#4a463f;
    --road-text:#ffffff; --hot:#9a4d10; --home:#8ea4bb; --roof:#c8b8a4; --unknown:#5d574e; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:760px; margin:0 auto; padding:16px; }
h1 { font-size:1.4rem; margin:0 0 4px; }
p { margin:0 0 12px; color:var(--muted); }
.card { background:var(--card); border-radius:12px; padding:8px; }
svg { display:block; width:100%; height:auto; }
svg text { font-family:inherit; font-size:12px; }
.heading { font-size:14px; font-weight:700; fill:var(--fg); }
.label { fill:var(--fg); } .muted { fill:var(--muted); } .strong { font-weight:700; }
.on-road { fill:var(--road-text); font-size:11px; }
.road { fill:var(--road); } .road.hot { fill:var(--hot); }
.home { fill:var(--home); } .roof { fill:var(--roof); }
.shop { stroke:var(--fg); stroke-width:1.5; } .shop.unknown { fill:var(--unknown); }
.shop.closed { stroke-dasharray:4 3; opacity:.55; }
"""

# Only once Phase 4 keys exist, so earlier towns render byte-identically.
BILLS_CSS = """:root { --alarm:#d11a1a; }
@media (prefers-color-scheme: dark) { :root { --alarm:#ff5c5c; } }
.behind { fill:var(--alarm); stroke:var(--card); stroke-width:1.2; }
"""


def render_html(snap, day, seed):
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Tiny Town map</title>\n<style>{CSS}{BILLS_CSS if snap['bills_reported'] else ''}</style>\n</head>\n<body>\n<main>\n"
        f"<h1>Tiny Town map</h1>\n<p>{esc(_facts(snap, day, seed))}</p>\n"
        f'<div class="card">{render_svg(snap)}</div>\n'
        "<p>One house per resident. Shops have no street address in town state, "
        "so they sit in their own block.</p>\n</main>\n</body>\n</html>\n"
    )


# --- command line ------------------------------------------------------------


def out_path(text):
    """``--out`` must name a file whose folder exists; checked before the town runs."""
    if not text.strip():
        raise argparse.ArgumentTypeError("path must not be empty")
    path = Path(text)
    if path.is_dir():
        raise argparse.ArgumentTypeError(f"{text} is a directory")
    if not path.parent.is_dir():
        raise argparse.ArgumentTypeError(f"folder does not exist: {path.parent}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3 -m mochi.tinytown.map", description="Draw Tiny Town as an HTML/SVG map.")
    parser.add_argument("--out", required=True, type=out_path, metavar="PATH", help="HTML file to write (the only file written)")
    parser.add_argument("--seed", type=int, default=SEED, help=f"town seed (default {SEED})")
    parser.add_argument("--day", type=view.day_number, default=DAYS, help=f"day to draw, 1-{DAYS} (default {DAYS})")
    args = parser.parse_args(argv)
    page = render_html(capture(args.day, args.seed), args.day, args.seed)
    args.out.write_text(page, encoding="utf-8")
    print(f"map: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
