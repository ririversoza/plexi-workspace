# Tiny Town: economy

The town's people, jobs, shops, budget and public works. Follows the contract in `juniper/TINYTOWN.md`.

## State

**Writes** `town.state["economy"]`:

| Key | Type | Meaning |
|---|---|---|
| `population` | int ≥ 0 | residents |
| `employed` | int, 0 ≤ employed ≤ population | residents with a job today |
| `treasury` | float ≥ 0 | town budget, rounded to cents |
| `shops_open` | int ≥ 0 | shops trading today (0–20 in the Phase 1 model, 0–6 from `businesses`) |
| `project` | dict or `None` | public works in progress: `name`, `cost`, `paid` (dollars), `progress` (0 ≤ p < 1). `None` when nothing is being built |
| `projects_completed` | list of str | finished projects, in build order |

**Reads** (read-only, in `tick` only; each is optional):

| Key | Used for |
|---|---|
| `weather.condition` | storms, Phase 1 model only. Defaults to `"sun"` |
| `residents.count` | `population` |
| `residents.employed` | `employed` |
| `businesses.open_count` | `shops_open` |

Each key is used on its own: if it's missing or not an int, that one value falls back to the Phase 1 model below. So residents without businesses still gets 20 Phase 1 shops, and vice versa.

## Model (one tick = one day)

1. **Population:** `residents.count` if present. Otherwise changes by `rng.randint(-2, 3)` a day, floored at 0.
2. **Jobs:** `residents.employed` if present. Otherwise `employed = round(population × rng.uniform(0.85, 0.95))`, capped at population. Always clamped to `0 ≤ employed ≤ population`.
3. **Shops:** `businesses.open_count` if present (businesses handle their own storm closures, so no event here). Otherwise a `storm` closes all 20 shops (emits `shops_closed`). No other weather affects shops.
4. **Treasury:**
   - income = `employed × 1.0 + shops_open × 5.0`
   - upkeep = `population × 1.0`
   - Income is added first, then upkeep is paid out of what's available.
   - **No overdraft:** spending is capped at the money on hand. If upkeep can't be covered in full, the town spends everything it has, the treasury lands at exactly 0, and `budget_shortfall` is emitted (`needed`, `spent`). Unpaid upkeep isn't carried over as debt.

5. **Public works** (after upkeep, no RNG):
   - Projects are funded one at a time, in this fixed order: `park` $200, `bike lane` $300, `market square` $400.
   - The next project starts (`project_started {name, cost}`) on the first day the treasury is above the **reserve of $1,000** (the starting treasury).
   - Each day it pays an instalment of `min($20, cost left, treasury − reserve)`. Spending never takes the treasury below the reserve, so it can't overdraw. On days at or below the reserve, the project pauses.
   - When it's fully paid, `project_completed {name, cost}` is emitted, `project` returns to `None`, and the next one can start the following day.
   - Upkeep is always paid first, so a bad day can still take the treasury below the reserve (storm deficits). Projects simply wait until it recovers.
   - Once the list is done, nothing more is spent.

## Assumptions and numbers

- `setup` still seeds the Phase 1 values (it can't read other systems); day 1's tick replaces them with `residents`/`businesses` numbers when those exist.
- The Phase 1 starting town has 500 people, 450 employed (90%), a treasury of 1000.0 and 20 shops open.
- On a normal Phase 1 day there's a small surplus: about 450 + 100 income vs 500 upkeep. A storm day runs a deficit of about 50.
- With Phase 2 systems (120 residents, ~100 employed, 6 shops) it's about 100 + 30 income vs 120 upkeep.
- The only randomness is `town.rng`, and only for fallback values: `randint` (population) then `uniform` (employed), each skipped when `residents` supplies it. With both present, economy draws nothing. There's no other RNG.
- Every tick writes a new dict, and the previous one isn't mutated.
- Events emitted: `shops_closed {reason}` (Phase 1 shops only), `budget_shortfall {needed, spent}`, `project_started {name, cost}` and `project_completed {name, cost}`.
- Other systems don't read `project` or `projects_completed` yet.
- The project numbers are scaled to the Phase 2 town's surplus (about $8 a day at seed 42), so some projects finish within 90 days. A $1,500 reserve would first be passed on day 60 and nothing would complete.

## Public works: seed 42, 90 days, before and after

| | Before | After |
|---|---|---|
| Treasury, day 30 / 60 / 90 | $1,240 / $1,510 / $1,780 | $994 / $1,010 / $1,000 |
| Projects | none | park done day 22, bike lane done day 60, market square 70% |
| Shop balances, population, employed, shops_open, `town.rng` state | unchanged | unchanged |

The $780 difference in the treasury is exactly what the projects cost: $200 + $300 + $280. `bao.tinytown.test_town_acceptance` passes.

## Tests

```
python3 -m unittest discover -s sora/tinytown -t .
```

These run with a fake town and no engine, and cover determinism, per-day bounds, storms closing shops, no overdraft from an empty treasury, and running with weather missing. Economy v2 tests cover reading `residents` and `businesses`, each one alone, missing or malformed keys, the employed cap, no RNG draws when both are present, and no overdraft with Phase 2 numbers. Public works tests cover building the list in order with the right events, daily progress and the reserve, nothing starting at or below the reserve, only the treasury changing (same RNG state and other keys as a run with no projects, and the difference equals the amount paid), and older state without the project keys.
