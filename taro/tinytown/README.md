# Tiny Town — engine + runner (Taro)

Shared seeded city simulation. This package owns the **world** and the **tick loop**; peer agents own one system each and plug in via the contract in `juniper/TINYTOWN.md`.

## What it models

- One `Town`: day clock (`0` during setup, then `1..90`), shared `random.Random(42)`, per-system `state` dict, and an event bus (`emit` / `subscribe` / `events`).
- One daily tick order (Phase 2): **weather → businesses → residents → economy → traffic → emergency**. Mochi's `log` is setup-only (subscribes during `setup`, never ticks).
- Setup follows the same order as ticks, then any leftover systems (log).
- Missing systems are skipped. A run with zero systems still completes 90 quiet days.

## Assumptions and numbers

| Knob | Value | Why |
|---|---|---|
| Seed | `42` | Contract: one shared RNG for every system |
| Days | `90` | Contract run length |
| Tick / setup order | weather, businesses, residents, economy, traffic, emergency | Phase 2 contract; log excluded from ticks |
| System discovery | import catalogued modules (see below) | `ImportError` or missing `System` → skip |
| Money display | integer cents → `$X.YY` | Phase 2 wallets and shop ledgers |
| State ownership | each system writes only `town.state[self.name]` | Engine never mutates peer state |

### System catalog (`SYSTEM_MODULES`)

| Key | Module |
|---|---|
| `weather` | `nori.tinytown` |
| `businesses` | `nori.shops` |
| `residents` | `kiwi.townfolk` |
| `economy` | `sora.tinytown` |
| `traffic` | `bao.tinytown` |
| `emergency` | `kiwi.tinytown` |
| `log` | `mochi.tinytown` |

The engine does **not** invent weather, shops, residents, economy, traffic, or emergency numbers — those live in peer packages and are documented there.

## State keys (read by the runner's summaries)

When present, the daily one-liner reads the contract fields:

- `weather`: `condition`, `temp_c`, `season`
- `residents`: `count`, `employed`, `avg_wallet_cents` (shown as `avg_wallet=$X.YY`)
- `businesses`: `open_count`; `sales` = sum of `residents.purchases` units when residents exist, else sum of shops' `sold_yesterday`
- `economy`: `population`, `employed`, `treasury`, `shops_open`
- `traffic`: `commuters`, `congestion`, `accidents_today`
- `emergency`: `incidents_today`, `responded`, `open_incidents`

### Final report

- Dumps each installed system's state (businesses without the full `shops` map — see leaderboard).
- **`log`**: counts only (list/dict lengths and numeric fields) — never the full event list.
- **Shop leaderboard**: shops ranked by `balance_cents`, showing balance and cumulative units sold across the run (from daily `residents.purchases`, falling back to each day's `sold_yesterday`).

## Interface

```python
town.day                 # int
town.rng                 # random.Random(42)
town.state               # dict[str, dict]
town.emit(kind, **data)  # adds day + system automatically
town.events              # list of event dicts, in order
town.subscribe(callback) # callback(event_dict)
```

## How to run

From the repo root (worktree root):

```bash
python3 -m taro.tinytown.run
# or
python3 taro/tinytown/run.py

# Phase 3 CLI (no flags → same stdout bytes as the plain run above)
python3 -m taro.tinytown.run --seed 42 --days 90
python3 -m taro.tinytown.run --quiet
python3 -m taro.tinytown.run --seeds 1-20
python3 -m taro.tinytown.run --export /tmp/town-timeline.json

python3 -m unittest discover -s taro/tinytown -t .
```

### CLI flags

| Flag | Default | Effect |
|---|---|---|
| `--seed N` | `42` | RNG seed for a single run |
| `--days N` | `90` | simulation length |
| `--quiet` | off | final report only (no daily lines) |
| `--seeds A-B` | off | quiet multi-seed robustness table |
| `--export PATH` | off | write compact JSON timeline to PATH (disables event-log CSV; daily lines and final report still print; incompatible with `--seeds`) |

`--seeds` disables log file writes (`csv_path=None`), tracks max consecutive `$0` shop balances with a read-only feature (no extra `town.rng` draws), and prints one row per seed: seed, shops with balance > 0 on the last day, max `$0` streak, average wallet, treasury, PASS/FAIL against Phase 2 targets (≥5 shops solvent, max `$0` streak ≤3, avg wallet < $600), then `X of N seeds pass`.

Scratch and run output belong in `$TMPDIR`, never in the repo.

### `--export PATH` timeline schema

Writes **one** JSON file to the exact `PATH` (and only when `--export` is given). No extra `town.rng` draws. Plain runs without the flag never write this file. Export disables the event-log CSV (`csv_path=None`) so only the JSON timeline is written; the final report's `log:` line may therefore differ from a plain run (for example CSV path / entry counts). Combining `--seeds` with `--export` is rejected with exit code 2. The path is validated up front (non-empty; not an existing directory; parent directory must exist) and rejected with exit code 2 before the town runs.

Top level:

| Field | Type | Meaning |
|---|---|---|
| `seed` | int | RNG seed used for the run |
| `days` | int | final day index (= length of `daily`) |
| `systems` | string[] | installed system names, in load order |
| `daily` | object[] | one compact snapshot per day |
| `events_by_kind` | object | `{system.kind: count}` over `town.events` (not the full list; `system` is empty if missing) |

Each `daily[]` entry:

| Field | When | Contents |
|---|---|---|
| `day` | always | int |
| `weather` | if present | full compact weather state (`condition`, `temp_c`, `season`, …) |
| `economy` | if present | full compact economy state |
| `traffic` | if present | full compact traffic state |
| `emergency` | if present | full compact emergency state |
| `businesses` | if present | `{shop_id: {open, price_cents, available, balance_cents, sold_yesterday}}` |
| `residents` | if present | `{count, employed, avg_wallet_cents}` plus `avg_mood` / `mood_bands` **only if** those keys exist on resident state |

Intentionally omitted: per-resident `people` lists, shop staff lists, wages maps, and the full event log.

### HTML dashboard

```bash
python3 -m taro.tinytown.dashboard --out /tmp/town.html
python3 -m taro.tinytown.dashboard --out /tmp/town.html --seed 42
python3 -m taro.tinytown.dashboard --out /tmp/town.html --from /tmp/town-timeline.json
```

Writes **one** static HTML file to `--out` only: inline CSS, inline SVG charts, light/dark via `prefers-color-scheme`, phone-readable. No JavaScript libraries and no external assets. When running the town (no `--from`), the log is constructed with `csv_path=None`. Charts: shop balances (front-gapped if a shop opens mid-run), average wallet, weather strip, traffic congestion, final shop leaderboard. Missing wallet/congestion plot as gaps; missing weather shows as `n/a`. `--out` is validated like `--export` (non-empty, not an existing directory, parent must exist) and rejected with exit code 2. Snapshot helpers are imported from `taro.tinytown.run` so the timeline schema cannot drift.
