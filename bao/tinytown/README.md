# Tiny Town traffic

`from bao.tinytown import System` provides the contract's `setup(town)` and
`tick(town)` interface. Python standard library only; no engine import required.

## State and lifecycle

Reads `residents.people`, `residents.purchases`, and `weather.condition` read-only.
When `residents` is absent, reads `economy.employed` for the Phase 1 fallback.
When residents are present, only people with `job == "out-of-town"` contribute
work commutes; shop staff walk and unemployed residents have no work commute.
Missing people or purchases default to an empty list or dictionary, respectively.
An empty residents state does not fall back to economy.
Missing economy or employment defaults to **0** workers; missing weather or
condition defaults to **sun**. Unknown condition strings also use sun's effects.
Other weather fields are unused. Values follow the contract's types; malformed
objects and nonnumeric employment are not supported. Negative employment and individual purchase counts are
defensively clamped to zero.

Writes only `state['traffic']`, replacing all three daily values:

- `commuters`: nonnegative integer total road trips (work plus shopping).
  At most out-of-town workers plus `sum(nonnegative purchases) // 4` when
  residents exist; at most employed workers in the Phase 1 fallback.
- `congestion`: float from 0.0 to 1.0.
- `accidents_today`: integer from zero to the number of commuters.

Setup initializes these to `0`, `0.0`, and `0` and consumes no randomness or
events. Each tick emits one `traffic_daily` event with the three output fields;
the town supplies day/system metadata. Counts reset each day; no backlog exists.
The intended order is weather, businesses, residents, economy, traffic, emergency, so traffic uses
today's upstream values. The model also works alone for all 90 days.

## Model and every numeric assumption

Each day draws a commute fraction uniformly between **0.65 and 0.90**, then
rounds `eligible_workers * fraction` down to an integer. This represents daily variation
in attendance and remote work. No weekend, season, temperature, population, or
return-trip effects are modeled. Out-of-town workers use the same daily rate,
including weekends, preserving the existing attendance model.

With residents present, **25%** of today's purchased units become extra driving
trips: `sum(max(0, units) for units in purchases.values()) // 4`. Purchases are a
proxy for shopping visits, not unique shoppers (a resident can buy at two shops).
This deterministic share consumes no additional RNG draws and is bounded by the
purchase count. Work and shopping trips are added before congestion and accidents
are calculated. Zero workers can still produce shopping traffic; zero workers
and zero purchases produce zero trips and accidents. Phase 1 has no shopping trips.

Normal road capacity is **500 commuters/day**. Congestion is commuters divided
by weather-adjusted capacity, capped at **1.0** (zero demand gives **0.0**).

| Weather | Capacity multiplier | Base accident probability per commuter |
| --- | ---: | ---: |
| sun | 1.0 | 0.002 |
| cloud | 1.0 | 0.002 |
| rain | 0.8 | 0.006 |
| snow | 0.6 | 0.010 |
| storm | 0.5 | 0.015 |

Accident risk remains `base_probability + 0.01 * congestion`, between
**0.002 and 0.025**. Trips are divided into **four** balanced integer groups (quotient plus one
for each remainder trip). Each group has expected
accidents `group_trips * risk`. Stochastic rounding chooses the floor of each
expectation, plus one when its uniform draw is below its fractional part.
The four rounded counts are added. This preserves the expected accident count but
has lower variance than independent per-commuter trials: each group count is
the floor or ceiling of its expectation. The total remains bounded by zero and
commuters. Independent rounding of the four groups permits more variation than
rounding the combined expectation once.
These are illustrative simulation constants, not calibrated forecasts.
Accidents do not feed back into same-day congestion.

Only `town.rng` is used: exactly **five draws every tick**: one uniform draw for
the commute share, then four random draws for accident groups, even with an
empty group or an integer expectation. Setup consumes no draws.
Traffic volume therefore cannot shift the RNG position directly for later
systems. Downstream systems may still consume different draws in response to
changed state. This new schedule changes historical seeded output once; it
does not preserve the old per-commuter sequence. Four groups were selected during traffic-only seed-42 acceptance tuning;
this is a simulation parameter, not a calibrated traffic statistic. Accident
sampling takes constant time; counting residents and purchases remains linear in their input sizes.
Equal initial
state, shared RNG seed (normally **42**), upstream inputs, and system execution
order produce identical output and events. Installing other RNG-consuming
systems can change traffic results even with the same seed.

## Validation

From the repository root:

```sh
python3 -m unittest discover -s bao/tinytown -t .
```

Tests use a small fake town, with no dependency on another owner's package.

### Phase 2 combined acceptance (fixed-draw rework)

Combined archive of `origin/main` at `7096e4de` plus this traffic package,
seed 42, 90 days: **6/6 shops open**, average wallet **$500.88**. Every shop
had **zero days at $0** and a maximum zero-balance streak of **0**. All daily
traffic bounds passed. The runner completed all 90 days. Temporary trees were
created in `$TMPDIR` and deleted afterward. Thirteen standalone tests passed,
including a counting RNG regression across missing/resident inputs, varying
traffic volumes and every weather condition.

| Shop | Final balance | Units sold |
| --- | ---: | ---: |
| Spoke & Spanner | $17,635.00 | 452 |
| Bench & Bell | $14,856.20 | 452 |
| One Mug Tea | $3,217.90 | 2710 |
| Strawberry Daifuku Cart | $1,716.00 | 2778 |
| Matcha Mile | $1,415.00 | 1763 |
| Fold Post | $1,057.70 | 595 |

These acceptance results are specific to this combined tree and seed; they do
not guarantee the same weather or balances for other seeds or system changes.
