# Tiny Town: economy

The town's people, jobs, shops and budget. Follows the contract in `juniper/TINYTOWN.md`.

## State

**Writes** `town.state["economy"]`:

| Key | Type | Meaning |
|---|---|---|
| `population` | int ≥ 0 | residents |
| `employed` | int, 0 ≤ employed ≤ population | residents with a job today |
| `treasury` | float ≥ 0 | town budget, rounded to cents |
| `shops_open` | int, 0–20 | shops trading today |

**Reads** `town.state["weather"]["condition"]` (read-only). If weather is missing, or has no `condition`, it defaults to `"sun"`.

## Model (one tick = one day)

1. **Population:** changes by `rng.randint(-2, 3)` a day, floored at 0.
2. **Jobs:** `employed = round(population × rng.uniform(0.85, 0.95))`, capped at population.
3. **Shops:** a `storm` closes all 20 shops (emits `shops_closed`). No other weather affects shops.
4. **Treasury:**
   - income = `employed × 1.0 + shops_open × 5.0`
   - upkeep = `population × 1.0`
   - Income is added first, then upkeep is paid out of what's available.
   - **No overdraft:** spending is capped at the money on hand. If upkeep can't be covered in full, the town spends everything it has, the treasury lands at exactly 0, and `budget_shortfall` is emitted (`needed`, `spent`). Unpaid upkeep isn't carried over as debt.

## Assumptions and numbers

- The starting town has 500 people, 450 employed (90%), a treasury of 1000.0 and 20 shops open.
- On a normal day there's a small surplus: about 450 + 100 income vs 500 upkeep. A storm day runs a deficit of about 50.
- The only randomness is 2 draws per tick from `town.rng`, always in the same order: `randint` then `uniform`. There's no other RNG.
- Every tick writes a new dict, and the previous one isn't mutated.
- Events emitted: `shops_closed {reason}` and `budget_shortfall {needed, spent}`.

## Tests

```
python3 -m unittest discover -s sora/tinytown -t .
```

These run with a fake town and no engine, and cover determinism, per-day bounds, storms closing shops, no overdraft from an empty treasury, and running with weather missing.
