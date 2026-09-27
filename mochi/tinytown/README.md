# Tiny Town — event log + debug tools (Mochi)

Records every event the town emits, writes it to `events.csv`, and lets you ask
"what happened on day N?" from the command line. Written against
[`juniper/TINYTOWN.md`](../../juniper/TINYTOWN.md) only; no dependency on the engine or
any other system. Stdlib only.

## What it models

Nothing in the town itself. The log is an observer:

- `setup(town)` writes `town.state["log"]`, truncates the CSV to its header, records any
  events already in `town.events` (from systems whose `setup` ran first), then
  `town.subscribe`s so it sees every later emit.
- `tick(town)` is a no-op. The contract says the log does not tick; the method exists
  only so an engine that ticks every installed system can't crash on it.
- It **never** emits, reads other systems' state, or touches `town.rng`, so installing it
  cannot change the simulation (there is a test for this).

## State it writes: `town.state["log"]`

| Key | Type | Meaning |
|---|---|---|
| `events` | list of dict | Copy of every event seen, in emit order |
| `counts` | dict | `"<system>.<kind>" -> n` |
| `csv_path` | str or None | Where the CSV goes; `None` = in-memory only |

State read from other systems: **none**.

## `events.csv`

Columns: `day,system,kind,data_json`.

- `day`: int, `0` for events emitted during setup, `1..90` afterwards.
- `system`, `kind`: as stamped by `town.emit`.
- `data_json`: every other field of the event as JSON, keys sorted, compact separators,
  so the same run always produces byte-identical files. Values JSON can't encode (e.g.
  a `set`) are written as `str(value)` rather than crashing the run.

Rows are appended as each event arrives (open/append/close per event), so a run that
crashes midway still leaves a readable log up to the crash. That's about 1 small write
per event, which is negligible at 90 days.

Default path is `events.csv` in the current directory (normally the repo root when
running `taro/tinytown/run.py`). Use `System(csv_path="somewhere.csv")` or
`System(csv_path=None)` to change or disable it. Don't commit the generated file.

`mochi.tinytown.csvlog` has `read_events(path)` / `write_events(path, events)` for
anyone who wants to load a run back into Python.

## Inspecting a day

```
python3 -m mochi.tinytown.inspect <day> [--csv events.csv] [--system NAME]
```

```
$ python3 -m mochi.tinytown.inspect 3
Day 3: 2 events
  weather  rain_started  mm=4
  traffic  accident      injured=0 street=Elm St
By system: weather 1, traffic 1
```

Day `0` shows setup events. A day with no events prints `nothing happened (0 events)`.
A missing or malformed CSV exits with status 2 and a message on stderr.

## Town viewer (Phase 2)

```
python3 -m mochi.tinytown.view [--day N] [--every]
```

Runs the town in-process through `taro.tinytown` (seed 42, 90 days) and draws day N
(default 90) as ASCII; `--every` draws all 90 days in order. It is a viewer, not a
system: it never ticks, emits or touches `town.rng`.

- **Weather banner:** condition, temperature, season.
- **Storefronts:** one box per shop in contract order (extra shop ids after, sorted):
  open/closed, price, units sold, balance, staff names (resident ids when `residents` is
  missing; `+N more` past 2). "sold" is today's `residents.purchases[shop]`, or the shop's
  own `sold_yesterday` when residents isn't installed.
- **Residents:** count, employed, average wallet, and the top 3 wallets (ties go to the
  lower id).
- **Ticker:** traffic, emergency, and `economy.treasury` (float dollars; every other amount
  is integer cents).
- **Phase 3 extras (all optional).** Each shows up only when its key exists. With none of
  them, the frame is byte-identical to the Phase 2 view, including on current main where
  every price equals its base:
  - `residents.avg_mood` / `mood_bands` (Kiwi) add `  mood: avg 58/100 | happy 56 | ok 45 | unhappy 19`
    under the top wallets (`n/a` for whichever half is missing).
  - A shop's `price_cents` vs its base price (Nori's weekly pricing) adds ` ↑` or ` ↓` after
    the price, and nothing when they're equal. The base is the shop's `base_price_cents` if
    state has one, otherwise the catalog price copied from `nori/shops/README.md`
    (`BASE_PRICE_CENTS`). Shops not in that table get no arrow.
  - `economy.project` (a string, or a dict with `"name"`) / `projects_completed` (Sora) add a
    `town hall: building Library | 2 completed` ticker line.
  - `traffic.bus_running` / `bus_riders` (Bao) add `, bus running (12 riders)` (or `no bus`,
    or `bus n/a`) to the traffic line.

  `test_view_phase3.py` gives each key a present case, an absent case and an odd-value
  case, and checks a frame with none of them against a golden copy of the pre-Phase 3 output.

Systems come from the engine's own `SYSTEM_MODULES`, so the viewer only loads what that
engine version ticks. Anything missing is drawn as `not built yet`, and odd or missing
keys show `?` instead of crashing. The log is loaded with `csv_path=None`, so viewing
never writes `events.csv`. With no engine installed at all it exits with status 1 and a
one-line message. `--day` outside 1..90 is rejected.

## Tests

```
python3 -m unittest discover -s mochi/tinytown -t .
```

`test_view.py` renders synthetic Phase 2 state with no engine: every panel missing,
Phase 1 only (no businesses or residents), businesses without residents, malformed
values, alignment, top-wallet ties, and no mutation of state. When `taro.tinytown` is
importable it also runs the real town: default day 90 with no files written, `--every`
gives 90 frames in order, the same seed gives the same picture, and a single day matches
that day's `--every` frame.

They use a small fake `Town` that follows the contract interface (no engine needed) and
cover:
- **Determinism:** the same seed gives byte-identical CSVs and the same state, and the log leaves
  `town.rng` and the event stream exactly as they'd be without it.
- **CSV round-trip:** a full run and awkward values (commas, quotes, newlines, nesting,
  negatives, `None`, bools) read back equal to what was emitted.
- **Running with no other systems:** a 90-day run alone gives an empty log with only the header, and `inspect`
  still works.
- Recording order and completeness, including events emitted before the log's own setup.
