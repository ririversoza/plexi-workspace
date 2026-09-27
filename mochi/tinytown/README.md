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

## Tests

```
python3 -m unittest discover -s mochi/tinytown -t .
```

They use a small fake `Town` that follows the contract interface (no engine needed) and
cover:
- **Determinism:** the same seed gives byte-identical CSVs and the same state, and the log leaves
  `town.rng` and the event stream exactly as they'd be without it.
- **CSV round-trip:** a full run and awkward values (commas, quotes, newlines, nesting,
  negatives, `None`, bools) read back equal to what was emitted.
- **Running with no other systems:** a 90-day run alone gives an empty log with only the header, and `inspect`
  still works.
- Recording order and completeness, including events emitted before the log's own setup.
