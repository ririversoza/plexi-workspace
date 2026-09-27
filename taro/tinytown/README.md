# Tiny Town — engine + runner (Taro)

Shared seeded city simulation. This package owns the **world** and the **tick loop**; peer agents own one system each and plug in via the contract in `juniper/TINYTOWN.md`.

## What it models

- One `Town`: day clock (`0` during setup, then `1..90`), shared `random.Random(42)`, per-system `state` dict, and an event bus (`emit` / `subscribe` / `events`).
- One daily tick order: **weather → economy → traffic → emergency**. Mochi's `log` is setup-only (subscribes during `setup`, never ticks).
- Missing systems are skipped. A run with zero systems still completes 90 quiet days.

## Assumptions and numbers

| Knob | Value | Why |
|---|---|---|
| Seed | `42` | Contract: one shared RNG for every system |
| Days | `90` | Contract run length |
| Tick order | weather, economy, traffic, emergency | Contract; log excluded |
| System discovery | import `nori/sora/bao/kiwi/mochi.tinytown` | `ImportError` or missing `System` → skip |
| State ownership | each system writes only `town.state[self.name]` | Engine never mutates peer state |

The engine does **not** invent weather, economy, traffic, or emergency numbers — those live in peer packages and are documented there.

## State keys (read by the runner's summaries)

When present, the daily one-liner reads the contract fields:

- `weather`: `condition`, `temp_c`, `season`
- `economy`: `population`, `employed`, `treasury`, `shops_open`
- `traffic`: `commuters`, `congestion`, `accidents_today`
- `emergency`: `incidents_today`, `responded`, `open_incidents`

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
