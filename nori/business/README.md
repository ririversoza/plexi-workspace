# Matcha Mile (Nori)

Virtual microbusiness for the office competition: a **mobile matcha latte cart**.
Start with **$500.00** fictional currency, run exactly **90** days with RNG seed
**42**, and compete on final balance.

Zero-dependency Python 3. Every cash move goes through a ledger that refuses
overdrafts and writes `ledger.csv`.

## Credits

- **Demand & no-overdraft cash patterns** — inspired by `taro.store` on main
  (price elasticity around list price, seeded Gaussian demand, ledger that
  never spends what it does not have). Adapted here for a $500 start and a
  full transaction CSV.
- **Restock / pricing heuristic** — follows the growth ideas in
  `nori.store.strategy` (days-of-cover target, ease price when stock is thin
  or sales were missed, take a small premium when shelves are healthy).

## How money works

| Move | Ledger type | Sign |
|---|---|---|
| Buy drink supplies (matcha, milk, cup, lid) | `supply` | negative |
| Sell a finished latte | `sale` | positive |

There are **no loans**, **no free grants**, and **no hardcoded revenue**. Sales
only happen when demand is drawn and stock is on hand. Supplies are paid in
full before drinks can be sold.

Identity checked by tests:

```text
final_balance == 500.00 + sum(ledger amounts)
```

## Assumptions

| Parameter | Value | Why |
|---|---:|---|
| `UNIT_COST` | $1.80 | Real COGS per latte (powder, milk, cup, lid). |
| `LIST_PRICE` | $5.50 | Reference retail where “normal” demand applies. |
| `BASE_DAILY_DEMAND` | 9.0 | Expected drinks/day at list price (small cart). |
| `MAX_DAILY_DEMAND` | 24 | Hard cap — foot traffic is bounded. |
| `ELASTICITY` | 1.25 | Same shape as `taro.store.demand`: raising price above list shrinks demand; discounting grows it. |
| Demand draw | `gauss(mean, sqrt(mean))` then clamp to `[0, MAX]` | Seeded RNG only; reproducible with seed 42. |
| `DAYS_OF_COVER` | 6 | Restock toward ~6 days of expected demand. |
| `PREMIUM` / `DISCOUNT` | 1.06 / 0.96 | Mild price nudge from inventory health. |
| Price floor | `1.20 × UNIT_COST` | Never sell below a 20% margin vs COGS. |
| Opening stock | 0 | Must buy supplies from the $500 before first sales. |
| Days / seed | 90 / 42 | Competition rules. |

Expected demand at price `p`:

```text
mean = BASE_DAILY_DEMAND * (LIST_PRICE / p) ** ELASTICITY
```

## Reproduce

From the repo root:

```bash
python3 -m unittest discover -s nori/business -v
python3 nori/business/run.py
```

`run.py` prints final balance / profit / growth % and regenerates
`nori/business/ledger.csv`. Exact numbers live in `RESULTS.md` (captured from
that command — do not hand-edit).

— Nori · *Teamwork makes the dream work!*
