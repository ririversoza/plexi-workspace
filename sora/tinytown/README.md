# Tiny Town: economy

The town's people, jobs, shops and budget. Follows the contract in `juniper/TINYTOWN.md`.

## State

**Writes** `town.state["economy"]`:

| Key | Type | Meaning |
|---|---|---|
| `population` | int ≥ 0 | residents |
| `employed` | int, 0 ≤ employed ≤ population | residents with a job today |
| `treasury` | float ≥ 0 | town budget, rounded to cents |
| `shops_open` | int ≥ 0 | shops trading today (0–20 in the Phase 1 model, 0–6 from `businesses`) |

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

## Assumptions and numbers

- `setup` still seeds the Phase 1 values (it can't read other systems); day 1's tick replaces them with `residents`/`businesses` numbers when those exist.
- The Phase 1 starting town has 500 people, 450 employed (90%), a treasury of 1000.0 and 20 shops open.
- On a normal Phase 1 day there's a small surplus: about 450 + 100 income vs 500 upkeep. A storm day runs a deficit of about 50.
- With Phase 2 systems (120 residents, ~100 employed, 6 shops) it's about 100 + 30 income vs 120 upkeep.
- The only randomness is `town.rng`, and only for fallback values: `randint` (population) then `uniform` (employed), each skipped when `residents` supplies it. With both present, economy draws nothing. There's no other RNG.
- Every tick writes a new dict, and the previous one isn't mutated.
- Events emitted: `shops_closed {reason}` (Phase 1 shops only) and `budget_shortfall {needed, spent}`.

## Tests

```
python3 -m unittest discover -s sora/tinytown -t .
```

These run with a fake town and no engine, and cover determinism, per-day bounds, storms closing shops, no overdraft from an empty treasury, and running with weather missing. Economy v2 tests cover reading `residents` and `businesses`, each one alone, missing or malformed keys, the employed cap, no RNG draws when both are present, and no overdraft with Phase 2 numbers.
