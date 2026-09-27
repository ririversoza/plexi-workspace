# Tiny Town Gazette

A weekly newspaper for Tiny Town (Phase 3 in `juniper/TINYTOWN.md`).

```
python3 -m sora.gazette             # week 13 (the last issue)
python3 -m sora.gazette --week 4    # one issue, weeks 1-13
python3 -m sora.gazette --all       # every issue
python3 -m sora.gazette --html --out gazette.html   # HTML edition, every week
```

It runs the town in-process through `taro.tinytown` (seed 42, 90 days) with every installed system. The log gets `csv_path=None`, and nothing is written to disk.

## Read-only

- It makes no `town.rng` draws and never writes `town.state`. The engine's `on_day` hook takes a deep copy of the state it needs (`residents.people` is left out), and every section reads only those copies.
- It isn't a system and doesn't change the tick order, so the town runs exactly as it would without the paper. `test_read_only` checks the RNG state, events and final state against a plain run.

## Weeks

Week N covers days `7(N-1)+1` to `7N`. A 90-day run has 13 weeks, and week 13 is short (days 85-90). A week outside 1-13 is an argparse error.

## An issue

| Section | Source |
|---|---|
| Headline | rules below |
| Weather | count of each `weather.condition`, plus the `temp_c` range |
| Shop table | per shop: days `open`, units sold (sum of daily `residents.purchases`; an empty dict counts as 0, and `?` means residents never reported purchases), and `balance_cents` on the last day of the week |
| Prices* | each `price_change` event this week: `Shop $old -> $new` |
| Wallets | `residents.count` and `avg_wallet_cents` on the last day, plus the change since the end of last week |
| Taxes & bills* | Phase 4: the week's total `economy.tax_income` and `utility_income` (what the treasury actually collected), plus `residents.in_arrears` people behind (with `arrears_cents` owed) and the number of shops whose `arrears_cents` is above 0 (with the total owed), each only when those keys exist |
| Mood of the town* | `residents.avg_mood` on the last day and its change since the end of last week, plus each `mood_bands` count and its change |
| Traffic / Emergency | the week's total `traffic.accidents_today` and average `congestion`, and total `emergency.incidents_today` / `responded`. When `traffic.bus_running` is present, it adds `bus ran N days (R riders)` (sum of `bus_riders`) or `no bus` |
| Streets* | the street with the most incidents this week (sum of daily `emergency.incidents_by_street`, ties go to the name that sorts first), or `no incidents on any street` |
| Town Hall* | projects completed this week (new names in `economy.projects_completed` since the end of last week) and the current `economy.project` with progress rounded down to a whole percent, or `no project under way` |

\* Optional Phase 3 sections. Each prints only when its keys (or, for Prices, `price_change` events that week) are there, so a week without them renders byte-for-byte as it did before. Prices only lists actual moves, so a week where no price changed has no Prices line.

## Headline rules

The first rule that fires wins:

1. **Project completed:** a public works project finished this week (`TOWN OPENS NEW PARK`).
2. **Accident spike:** at least 8 accidents in the week (`ACCIDENT_SPIKE`).
3. **Mood swing:** `residents.avg_mood` moved at least 10 points since the end of last week (`MOOD_SWING`). Week 1 measures from day 1.
4. **Storm closures:** any day with a `shops_closed` event whose reason is `storm`, or with a storm and `businesses.open_count == 0`. The headline says how many days.
5. **Treasury change:** `economy.treasury` fell, or rose by at least $100 (`TREASURY_SWING_DOLLARS`), since the end of last week. Week 1 measures from day 1.
6. **Best seller:** the shop with the most units sold that week. A tie goes to the shop id that sorts first.
7. **Quiet week:** when nothing above fires, or no system reports anything.

Rules 1 and 3 need the Phase 3 keys, so without them the headlines are exactly the Phase 2 ones. At seed 42 on today's main, the 13 issues cover project openings (park in week 4, bike lane in week 8), mood swings (weeks 9, 10 and 12), storm closures and best sellers. The bus never runs at seed 42, because congestion never goes above 0.6.

## HTML edition

`--html` renders a newspaper-style page instead of text: a masthead, a week index, and one section per week with a boxed headline, a shop table, and the same lines as the text issue. `--out PATH` writes it there (the only file the gazette ever writes); without `--out` it goes to stdout. It covers every week unless `--week N` is given. `--out` without `--html` is an error.

Each week has up to two stat tiles, each with a small inline-SVG sparkline: **Mood** (`residents.avg_mood`) and **Prices** (the average shop `price_cents` as a % of each shop's first observed price). The line shows the run up to that week in muted ink and the week itself in the accent, on one scale for the whole run so weeks compare. The SVG `<title>` says the week's start and end values. A tile only appears when its keys are there, and missing days break the line rather than bridging it.

The page is self-contained: inline CSS and SVG, no JavaScript, fonts or other external assets. It follows `prefers-color-scheme` for light and dark, and fits a phone (the shop table scrolls sideways if it must). All state text is HTML-escaped. The HTML reuses the text sections, so the text output is unchanged.

## Missing systems

Every section falls back to "no reporter on this beat yet" when its system isn't installed or its state is malformed. With zero systems, every issue is a quiet week. If `taro.tinytown` itself is missing, the CLI prints one line and exits 0.

## Tests

```
python3 -m unittest discover -s sora/gazette -t .
```

The tests cover a golden Phase 2 issue that must stay byte-identical, each Phase 3 section with its keys present and absent, the project-completion and mood-swing headlines, identical output across runs, all 13 issues printed, read-only behaviour (RNG state, events and final state unchanged), no files written (run inside a temporary directory), week bounds (full coverage, the short last week, out-of-range rejection), zero systems, weather only, malformed state, each headline rule in priority order, and the HTML edition (self-contained page, one article per week, `--out` writes only that file, escaping, tiles present only with their keys, the price index, gaps in sparklines).
