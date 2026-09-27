# Tiny Town — Weather (Nori)

Models a temperate mid-latitude town's daily sky and temperature for the shared 90-day simulation.

## Interface

| Direction | Key | Shape |
|---|---|---|
| **Writes** | `town.state["weather"]` | `condition`, `temp_c`, `season` |
| **Reads** | _(none)_ | Weather ticks first; no other system state needed |

`condition` ∈ `sun | cloud | rain | snow | storm`  
`season` ∈ `spring | summer | autumn | winter`  
`temp_c` is a float (°C), rounded to 1 decimal.

Emits:
- `weather_init` once in `setup`
- `daily` each `tick` with the same three fields

## Assumptions

### Calendar / seasons

| Season | Days (inclusive) | Length |
|---|---|---|
| spring | 1–23 | 23 |
| summer | 24–45 | 22 |
| autumn | 46–68 | 23 |
| winter | 69–90 | 22 |

Setup (`town.day == 0`) seeds state as spring / sun / 12.0°C. Day 0 maps to spring if queried.

### Climate (before condition delta)

Temperate mid-latitude. Each day draws  
`base = mean + uniform(-spread, +spread)` from `town.rng`.

| Season | mean °C | spread °C |
|---|---|---|
| spring | 12.0 | 5.0 |
| summer | 24.0 | 6.0 |
| autumn | 14.0 | 5.0 |
| winter | 2.0 | 6.0 |

### Condition probabilities (relative weights)

Order: sun, cloud, rain, snow, storm. Storm weight ≤ **0.10** in every season.

| Season | sun | cloud | rain | snow | storm |
|---|---|---|---|---|---|
| spring | 0.32 | 0.30 | 0.26 | 0.04 | 0.08 |
| summer | 0.42 | 0.28 | 0.20 | 0.00 | 0.10 |
| autumn | 0.28 | 0.32 | 0.26 | 0.06 | 0.08 |
| winter | 0.22 | 0.28 | 0.12 | 0.30 | 0.08 |

### Condition temperature deltas (°C)

| sun | cloud | rain | storm | snow |
|---|---|---|---|---|
| +3.0 | 0.0 | −2.0 | −4.0 | −6.0 |

Extra rules:
- Snow is clamped to `temp_c ≤ 1.5` (light wet snow allowed just above freezing).
- Final clamp: `temp_c ∈ [-15.0, 38.0]`.

### Bounded storm frequency

1. **Cooldown:** at least **3** days since the last storm before another is allowed (`STORM_MIN_GAP_DAYS = 3`).
2. **Hard cap:** at most **12** storms in a 90-day run (`STORM_MAX_TOTAL = 12`).
3. When blocked, the storm weight is set to 0 for that day's `rng.choices` draw (no remapping after the fact).

Instance counters `_last_storm_day` / `_storm_count` live on the `System` object; they are **not** part of the public state contract. A new storm is allowed only when `town.day - last_storm_day >= 3` (calendar gap).

### RNG

Every random draw uses `town.rng` only (`choices` for condition, `uniform` for temperature base). No `random.Random` of our own, no global `random`.

### Missing peers

Weather does not read other systems. Safe to run alone with a fake `Town`.

## Tests

```bash
python3 -m unittest discover -s nori/tinytown -t .
```

Covers determinism (seed 42), value bounds / storm limits, and solo operation with no other systems.
