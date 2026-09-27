# Tiny Town Gazette

A weekly newspaper for Tiny Town (Phase 3 in `juniper/TINYTOWN.md`).

```
python3 -m sora.gazette             # week 13 (the last issue)
python3 -m sora.gazette --week 4    # one issue, weeks 1-13
python3 -m sora.gazette --all       # every issue
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
| Shop table | per shop: days `open`, units sold (sum of daily `residents.purchases`), and `balance_cents` on the last day of the week |
| Wallets | `residents.count` and `avg_wallet_cents` on the last day, plus the change since the end of last week |
| Streets | the week's total `traffic.accidents_today` and average `congestion`, and total `emergency.incidents_today` / `responded` |

## Headline rules

The first rule that fires wins:

1. **Accident spike:** at least 8 accidents in the week (`ACCIDENT_SPIKE`).
2. **Storm closures:** any day with a `shops_closed` event whose reason is `storm`, or with a storm and `businesses.open_count == 0`. The headline says how many days.
3. **Treasury change:** `economy.treasury` fell, or rose by at least $100 (`TREASURY_SWING_DOLLARS`), since the end of last week. Week 1 measures from day 1.
4. **Best seller:** the shop with the most units sold that week. A tie goes to the shop id that sorts first.
5. **Quiet week:** when nothing above fires, or no system reports anything.

At seed 42, the 13 issues cover the accident spike (week 4), storm closures, and best sellers. The treasury rule fires only in weeks without a storm or spike where money dropped or jumped $100.

## Missing systems

Every section falls back to "no reporter on this beat yet" when its system isn't installed or its state is malformed. With zero systems, every issue is a quiet week. If `taro.tinytown` itself is missing, the CLI prints one line and exits 0.

## Tests

```
python3 -m unittest discover -s sora/gazette -t .
```

The tests cover identical output across runs, all 13 issues printed, read-only behaviour (RNG state, events and final state unchanged), no files written (run inside a temporary directory), week bounds (full coverage, the short last week, out-of-range rejection), zero systems, weather only, malformed state, and each headline rule in priority order.
