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

python3 -m unittest discover -s taro/tinytown -t .
```