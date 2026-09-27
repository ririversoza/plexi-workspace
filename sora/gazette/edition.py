"""The Gazette's HTML edition: one self-contained page (inline CSS and SVG, no JS).

    python3 -m sora.gazette --html --out gazette.html

Read-only like the text paper: it renders the same daily snapshots and reuses its sections.
"""

from html import escape

from sora.gazette import (
    DAYS,
    NOT_REPORTED,
    SEED,
    WEEK,
    as_dict,
    busiest_street_line,
    get,
    headline,
    mood_line,
    num,
    prices_line,
    shop_rows,
    streets_line,
    town_hall_line,
    wallets_line,
    weather_line,
    week_of,
)

SPARK_WIDTH = 240
SPARK_HEIGHT = 48
SPARK_PAD = 6  # keeps the line and end dot inside the box

# Tokens from the dataviz reference palette: surfaces, inks, and categorical slot 1 as the accent.
CSS = """
:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink-2:#52514e;--muted:#898781;
--rule:#c3c2b7;--grid:#e1e0d9;--accent:#2a78d6;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--surface:#1a1a19;--ink:#fff;
--ink-2:#c3c2b7;--muted:#898781;--rule:#383835;--grid:#2c2c2a;--accent:#3987e5}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 48px}
.masthead{text-align:center;border-bottom:4px double var(--ink);padding-bottom:12px}
.masthead h1{margin:0;font:700 clamp(30px,8vw,54px)/1.05 Georgia,"Times New Roman",serif}
.masthead p{margin:8px 0 0;color:var(--ink-2);font-size:14px}
nav{display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:center;padding:10px 0;
border-bottom:1px solid var(--rule);font-size:14px}
nav a{color:var(--ink-2)}
article{background:var(--surface);border:1px solid var(--grid);border-radius:4px;
padding:16px;margin-top:24px}
.dateline{margin:0;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.headline{margin:8px 0 16px;padding:12px 14px;border:2px solid var(--ink);
font:700 clamp(19px,5vw,27px)/1.2 Georgia,"Times New Roman",serif;overflow-wrap:anywhere}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:16px}
.tile{margin:0;border:1px solid var(--grid);border-radius:4px;padding:10px 12px}
.tile figcaption{font-size:13px;color:var(--ink-2)}
.value{font-size:22px;font-weight:600}
.delta{margin-left:6px;font-size:13px;font-weight:400;color:var(--ink-2)}
.tile svg{display:block;width:100%;height:auto;margin-top:6px}
.history,.week{fill:none;stroke-linejoin:round;stroke-linecap:round}
.history{stroke:var(--muted);stroke-width:1.5}
.week{stroke:var(--accent);stroke-width:2.5}
.dot{fill:var(--accent);stroke:var(--surface);stroke-width:2}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--grid);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal}
th{color:var(--ink-2);font-weight:600;border-bottom-color:var(--rule)}
.lines p{margin:8px 0;overflow-wrap:anywhere}
.label{font-weight:600}
footer{margin-top:24px;text-align:center;font-size:13px;color:var(--muted)}
"""


# --- series -------------------------------------------------------------------


def mood_series(days_seen):
    """[(day, residents.avg_mood or None)] for the whole run."""
    return [(d["day"], num(get(d, "residents", "avg_mood"))) for d in days_seen]


def price_series(days_seen):
    """[(day, average shop price as a % of that shop's first observed price, or None)]."""
    base, series = {}, []
    for d in days_seen:
        ratios = []
        for shop_id, shop in as_dict(get(d, "businesses", "shops")).items():
            price = num(as_dict(shop).get("price_cents"))
            if price is None:
                continue
            base.setdefault(shop_id, price)
            if base[shop_id] > 0:
                ratios.append(100 * price / base[shop_id])
        series.append((d["day"], sum(ratios) / len(ratios) if ratios else None))
    return series


# --- sparkline tiles ------------------------------------------------------------


def path(points):
    """SVG path data; a None point breaks the line instead of joining across the gap."""
    parts, pen = [], "M"
    for point in points:
        if point is None:
            pen = "M"
            continue
        parts.append(f"{pen}{point[0]:.1f} {point[1]:.1f}")
        pen = "L"
    return " ".join(parts)


def sparkline_tile(series, first, last, caption, fmt, fmt_delta):
    """A stat tile: the value at the end of days first..last, its change over the week, and a
    sparkline of the run so far (muted) with this week in the accent. None without data this week.

    One scale for the whole run, so every week's tile is comparable.
    """
    week = [(day, v) for day, v in series if first <= day <= last and v is not None]
    if not week:
        return None
    values = [v for _, v in series if v is not None]
    low, high = min(values), max(values)
    run_days = max(day for day, _ in series)

    def point(day, value):
        x = (day - 1) * SPARK_WIDTH / max(run_days - 1, 1)
        if high == low:
            return x, SPARK_HEIGHT / 2
        return x, SPARK_HEIGHT - SPARK_PAD - (value - low) * (SPARK_HEIGHT - 2 * SPARK_PAD) / (high - low)

    def points(start, end):
        return [point(day, v) if v is not None else None for day, v in series if start <= day <= end]

    earlier = [v for day, v in series if day < first and v is not None]
    start_value = earlier[-1] if earlier else week[0][1]
    end_day, end_value = week[-1]
    dot_x, dot_y = point(end_day, end_value)
    summary = f"{caption}, days {first}-{last}: {fmt(start_value)} to {fmt(end_value)}"
    return (
        f'<figure class="tile"><figcaption>{escape(caption)}</figcaption>'
        f'<div class="value">{escape(fmt(end_value))}'
        f'<span class="delta">{escape(fmt_delta(end_value - start_value))} this week</span></div>'
        f'<svg viewBox="0 0 {SPARK_WIDTH} {SPARK_HEIGHT}" role="img" aria-label="{escape(summary)}">'
        f"<title>{escape(summary)}</title>"
        f'<path class="history" d="{path(points(1, first))}"/>'
        f'<path class="week" d="{path(points(first, last))}"/>'
        f'<circle class="dot" cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="4"/>'
        "</svg></figure>"
    )


# --- one week -----------------------------------------------------------------


def line_html(line):
    """A text-paper line ("Label: text") as a paragraph with the label in bold."""
    label, _, text = line.partition(": ")
    return f'<p><span class="label">{escape(label)}:</span> {escape(text)}</p>'


def shop_table_html(days):
    rows = shop_rows(days)
    if rows is None:
        return f'<div class="lines">{line_html(f"Shops: {NOT_REPORTED}")}</div>'
    body = "".join(
        f"<tr><td>{escape(name)}</td><td>{open_days}d</td><td>{escape(str(units))}</td><td>{escape(balance)}</td></tr>"
        for name, open_days, units, balance in rows
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th scope="col">Shop</th><th scope="col">Open</th>'
        f'<th scope="col">Sold</th><th scope="col">Balance</th></tr></thead><tbody>{body}</tbody></table></div>'
    )


def week_html(days, events, week, before, moods, prices):
    first = (week - 1) * WEEK + 1
    last = days[-1]["day"] if days else first + WEEK - 1
    tiles = [
        sparkline_tile(moods, first, last, "Mood (avg, 0-100)", lambda v: f"{v:.0f}", lambda d: f"{d:+.0f}"),
        sparkline_tile(prices, first, last, "Prices (% of day-1 price)", lambda v: f"{v:.1f}%", lambda d: f"{d:+.1f} pts"),
    ]
    tiles = [tile for tile in tiles if tile]
    lines = [
        weather_line(days),
        prices_line(days, events),
        wallets_line(days, before),
        mood_line(days, before),
        streets_line(days),
        busiest_street_line(days),
        town_hall_line(days, before),
    ]
    return (
        f'<article id="week-{week}"><p class="dateline">Week {week} &middot; Days {first}&ndash;{last}</p>'
        f'<h2 class="headline">{escape(headline(days, events, before))}</h2>'
        + (f'<div class="tiles">{"".join(tiles)}</div>' if tiles else "")
        + shop_table_html(days)
        + f'<div class="lines">{"".join(line_html(line) for line in lines if line is not None)}</div>'
        + "</article>"
    )


# --- the page -----------------------------------------------------------------


def render_html(days_seen, events, weeks, seed=SEED, days=DAYS):
    """The whole page as a string. Series span the full run, so each week shows its context."""
    moods, prices = mood_series(days_seen), price_series(days_seen)
    weeks = list(weeks)
    articles = []
    for week in weeks:
        previous = week_of(days_seen, week - 1)
        before = previous[-1] if previous else None
        articles.append(week_html(week_of(days_seen, week), week_of(events, week), week, before, moods, prices))
    nav = ""
    if len(weeks) > 1:
        nav = "<nav>" + "".join(f'<a href="#week-{w}">Week {w}</a>' for w in weeks) + "</nav>"
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Tiny Town Gazette</title><style>{CSS}</style></head><body><main>"
        '<header class="masthead"><h1>The Tiny Town Gazette</h1>'
        f"<p>Weekly edition &middot; seed {seed} &middot; {days} days</p></header>"
        f"{nav}{''.join(articles)}"
        "<footer>Printed read-only from a finished town run. Each sparkline shares one scale "
        "across the run; the accent marks that week.</footer></main></body></html>\n"
    )
