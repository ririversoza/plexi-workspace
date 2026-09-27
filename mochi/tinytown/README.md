# Tiny Town — event log + debug tools (Mochi)

Records every event the town emits, writes it to a CSV in the system temp dir, and lets you ask
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

## The event CSV

Columns: `day,system,kind,data_json`.

- `day`: int, `0` for events emitted during setup, `1..90` afterwards.
- `system`, `kind`: as stamped by `town.emit`.
- `data_json`: every other field of the event as JSON, keys sorted, compact separators,
  so the same run always produces byte-identical files. Values JSON can't encode (e.g.
  a `set`) are written as `str(value)` rather than crashing the run.

Rows are appended as each event arrives (open/append/close per event), so a run that
crashes midway still leaves a readable log up to the crash. That's about 1 small write
per event, which is negligible at 90 days.

**Default path:** `tinytown-events.csv` in the system temp dir, i.e.
`os.path.join(tempfile.gettempdir(), "tinytown-events.csv")` (see `default_csv_path()`). It is
resolved when `System()` is created, so it honours `$TMPDIR`. A default run, such as
`python3 -m taro.tinytown.run` from the repo root, never writes into the current directory,
and each run overwrites the previous one. Use `System(csv_path="somewhere.csv")` to choose
a file, or `System(csv_path=None)` to keep the log in memory only.

`mochi.tinytown.csvlog` has `read_events(path)` / `write_events(path, events)` for
anyone who wants to load a run back into Python.

## Inspecting a day

```
python3 -m mochi.tinytown.inspect <day> [--csv PATH] [--system NAME]
```

Without `--csv` it reads the same default file the log writes (`default_csv_path()`), so
`run` and then `inspect` work with no flags.

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
python3 -m mochi.tinytown.view [--day N | --every | --history SHOP_ID|all] [--seed N]
```

Runs the town in-process through `taro.tinytown` (seed 42 unless `--seed N`, 90 days) and draws day N
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
    the price, and nothing when they're equal. Arrows appear only when the base is actually
    known: the shop's own `base_price_cents` if state has one, otherwise the price the
    viewer's run saw on day 1 (weekly pricing first moves on day 7). `render()` on a bare
    state, with no `base_prices`, draws no arrows. Nothing is guessed from a copied table.
  - `mood_bands` keys are normalised to strings once, so odd keys (`{1: 2}`) still render.
  - `economy.project` / `projects_completed` (Sora's public works) add a ticker line like
    `town hall: building market square (70%) | 2 completed`. `project` is a dict with
    `"name"` and `"progress"` (0..1); `None` shows `no project` (between projects, or all
    done). `projects_completed` is a list of names and is shown as a count. A plain string
    project or an int count also work.
  - `traffic.bus_running` / `bus_riders` (Bao) add `, bus running (12 riders)` (or `no bus`,
    or `bus n/a`) to the traffic line.

  `test_view_phase3.py` gives each key a present case, an absent case and an odd-value
  case, and checks a frame with none of them against a golden copy of the pre-Phase 3 output.

Systems come from the engine's own `SYSTEM_MODULES`, so the viewer only loads what that
engine version ticks. Anything missing is drawn as `not built yet`, and odd or missing
keys show `?` instead of crashing. The log is loaded with `csv_path=None`, so viewing
never writes the event CSV. With no engine installed at all it exits with status 1 and a
one-line message. `--day` outside 1..90 is rejected.

### Shop balance history (`--history`)

```
python3 -m mochi.tinytown.view --history daifuku-cart [--seed 7]
python3 -m mochi.tinytown.view --history all
```

Draws each shop's `balance_cents` over the run as a 60-column by 12-row ASCII chart
(`mochi/tinytown/history.py`, pure functions over daily state snapshots):

- **x:** days 1..90 spread over 60 columns (`(day - 1) * 60 // 90`). A column shows the
  balance on the last day that falls in it.
- **y:** from `min(0, lowest balance)` on the bottom row to `max(0, highest balance)` on
  the top row, rounded to the nearest row. So $0 is the bottom for normal shops, and a
  negative balance extends the axis downward instead of flattening onto the $0 row. Labels
  are the top, the middle and the bottom. The label column is at least 12 wide and grows to
  fit the longest label, and the grid, axis, day labels and marker rows all share that
  width, so huge balances can't misalign them.
- **Big or odd numbers:** amounts are formatted and scaled in exact integer arithmetic
  (`Fraction`), so a balance like `10**400` can't raise `OverflowError`. NaN and infinite
  balances count as missing.
- **Marker rows** under the axis: `S` where a day in that column was *storm-closed*
  (`weather.condition == "storm"` and the shop is closed), `0` where the balance was
  exactly $0.
- **Summary:** min, max and final balance, each with its day, plus the counts of
  storm-closed days and $0 days.

`all` charts every shop seen, in contract order. It reads state only: no `town.rng` draws
(a test compares the rng state with a plain run), no emits, no files. When businesses isn't
built it prints `history: businesses not built yet` and exits 0. An unknown shop id exits 2
with the list of known ids. A shop missing on some days is charted from the days it exists.

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
`test_history.py` checks chart bounds on synthetic series: exactly 12x60 grid cells, one
point per column, max on the top row and $0 on the bottom, marker columns matching the
storm and $0 days, the day-to-column mapping covering 0..59, clamping, all-zero, empty
and gappy series, and `not built yet` or unknown-shop handling through a stand-in engine.
With the engine it also checks that the same seed gives the same chart, another seed
changes it, the rng state is untouched, and no files are written.

`test_log.py` uses a small fake `Town` that follows the contract interface (no engine needed) and
covers:
- **Determinism:** the same seed gives byte-identical CSVs and the same state, and the log leaves
  `town.rng` and the event stream exactly as they'd be without it.
- **CSV round-trip:** a full run and awkward values (commas, quotes, newlines, nesting,
  negatives, `None`, bools) read back equal to what was emitted.
- **Running with no other systems:** a 90-day run alone gives an empty log with only the header, and `inspect`
  still works.
- Recording order and completeness, including events emitted before the log's own setup.
- **Default path:** with `tempfile.tempdir` pointed at a throwaway dir and the cwd at
  another, a default run writes only to `<tempdir>/tinytown-events.csv` and leaves the cwd
  empty. `inspect` with no `--csv` reads that same file, and `csv_path=None` still disables
  it. When `taro.tinytown` is importable, a real default engine run is checked the same way.
