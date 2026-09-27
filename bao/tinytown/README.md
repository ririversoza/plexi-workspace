# Tiny Town traffic

`from bao.tinytown import System` provides the contract's `setup(town)` and
`tick(town)` interface. Python standard library only; no engine import required.

## State and lifecycle

Reads `economy.employed` and `weather.condition` without modifying either.
Missing economy or employment defaults to **0** workers; missing weather or
condition defaults to **sun**. Unknown condition strings also use sun's effects.
Other weather fields are unused. Values follow the contract's types; malformed
objects and nonnumeric employment are not supported. Negative employment is
defensively clamped to zero.

Writes only `state['traffic']`, replacing all three daily values:

- `commuters`: nonnegative integer, at most employed workers.
- `congestion`: float from 0.0 to 1.0.
- `accidents_today`: integer from zero to the number of commuters.

Setup initializes these to `0`, `0.0`, and `0` and consumes no randomness or
events. Each tick emits one `traffic_daily` event with the three output fields;
the town supplies day/system metadata. Counts reset each day; no backlog exists.
The intended order is weather, economy, traffic, emergency, so traffic uses
today's upstream values. The model also works alone for all 90 days.

## Model and every numeric assumption

Each day draws a commute fraction uniformly between **0.65 and 0.90**, then
rounds `employed * fraction` down to an integer. This represents daily variation
in attendance and remote work. No weekend, season, temperature, population, or
multi-trip effects are modeled. Zero workers means zero commuters and accidents.

Normal road capacity is **500 commuters/day**. Congestion is commuters divided
by weather-adjusted capacity, capped at **1.0** (zero demand gives **0.0**).

| Weather | Capacity multiplier | Base accident probability per commuter |
| --- | ---: | ---: |
| sun | 1.0 | 0.002 |
| cloud | 1.0 | 0.002 |
| rain | 0.8 | 0.006 |
| snow | 0.6 | 0.010 |
| storm | 0.5 | 0.015 |

Each commuter independently has at most one accident, with probability
`base_probability + 0.01 * congestion`. Thus risk stays between **0.002 and
0.025**. These are illustrative simulation constants, not calibrated forecasts.
Accidents do not feed back into same-day congestion.

Only `town.rng` is used: one uniform draw per tick (even at zero employment),
then one random draw per commuter. Runtime is linear in commuters. Equal initial
state, shared RNG seed (normally **42**), upstream inputs, and system execution
order produce identical output and events. Installing other RNG-consuming
systems can change traffic results even with the same seed.

## Validation

From the repository root:

```sh
python3 -m unittest discover -s bao/tinytown -t .
```

Tests use a small fake town, with no dependency on another owner's package.
