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
| Buy starter tools (day 1 only) | `equipment` | negative |
| Daily bicycle-cart rental | `cart_rental` | negative |
| Sidewalk / market pitch + permit share | `pitch_permit` | negative |
| Propane + light transport fuel | `fuel` | negative |
| Food-cart liability (prorated) | `insurance` | negative |
| Buy drink supplies (matcha, milk, cup, lid) | `supply` | negative |
| Sell a finished latte | `sale` | positive |

A used bicycle coffee cart would cost about **$750** — more than the $500
start — so the model **does not buy a cart**. Day 1 buys a **$95 starter kit**
(whisks, bowls, thermos, cooler bag, chalkboard) and then pays **$18/day** to
rent the cart. If cash cannot cover that day's overhead total, the cart stays
**closed** (no restock, no sales) rather than skipping the cost.

There are **no loans**, **no free grants**, and **no hardcoded revenue**. Sales
only happen when the cart is open, demand is drawn, and stock is on hand.
Supplies and overhead are paid in full before drinks can be sold.

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
| `CART_PURCHASE_PRICE` | $750.00 | Used bicycle coffee cart — **not purchased** (unaffordable at $500). |
| `STARTER_EQUIPMENT` | $95.00 | Day-1 tools the start balance *can* cover. |
| `DAILY_CART_RENTAL` | $18.00 | Honest substitute for buying the cart. |
| `DAILY_PITCH_PERMIT` | $12.00 | Sidewalk / market pitch fee plus daily permit share. |
| `DAILY_FUEL` | $4.00 | Propane for hot water plus light transport. |
| `DAILY_INSURANCE` | $3.00 | Liability cover, about $1,095/year prorated. |
| Daily overhead total | $37.00 | Sum of rental + pitch + fuel + insurance; paid before restock. |
| `DAYS_OF_COVER` | 6 | Restock toward ~6 days of expected demand. |
| `PREMIUM` / `DISCOUNT` | 1.06 / 0.96 | Mild price nudge from inventory health. |
| Price floor | `1.20 × UNIT_COST` | Never sell below a 20% margin vs COGS. |
| Opening stock | 0 | Must buy supplies from cash after overhead before first sales. |
| Owner labor | unpaid | Owner-operated; profit is pay before their time. |
| Days / seed | 90 / 42 | Competition rules. |

Expected demand at price `p`:

```text
mean = BASE_DAILY_DEMAND * (LIST_PRICE / p) ** ELASTICITY
```

## Order of cash moves each open day

1. Day 1 only: `equipment` ($95 starter kit).
2. `cart_rental` → `pitch_permit` → `fuel` → `insurance`.
3. `supply` restock (capped by cash after overhead).
4. `sale` revenue from drinks sold that day.

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
