# Matcha Mile (Nori) — PIP revision

Virtual microbusiness for the office competition: a **mobile matcha latte cart**.
Start with **$500.00** fictional currency, run exactly **90** days with RNG seed
**42**, and compete on final balance.

Zero-dependency Python 3. Every cash move goes through a ledger that refuses
overdrafts and writes `ledger.csv`.

## Break-even check (written before re-running)

Contribution margin at list price:

```text
profit_per_unit = LIST_PRICE − UNIT_COST
                = $5.50 − $1.80
                = $3.70
```

Daily fixed costs (open day):

```text
daily_fixed = cart_rental + pitch_permit + fuel + insurance
            = $10.00 + $14.00 + $3.00 + $2.00
            = $29.00
```

Units needed each open day just to cover overhead (before equipment):

```text
break_even_units = daily_fixed / profit_per_unit
                 = $29.00 / $3.70
                 ≈ 7.84 drinks/day
```

Expected demand at list price is **`BASE_DAILY_DEMAND = 14`**, which is above
the 7.84 break-even by about **6 drinks/day** (~78% cushion). That cushion has
to absorb: day-1 `$95` starter kit, premium/discount price moves (elasticity),
seeded demand noise, and any closed days when cash cannot cover overhead.

**Why the first entry failed:** PR #12 used `$37/day` fixed costs → break-even
`37 / 3.70 ≈ 10.0` drinks/day against expected demand of only **9**. The cart
was underwater on a typical day, so the 90-day run finished at `$30.25`.

**What changed for viability (still realistic):** relocate to a weekday
**office-plaza** pitch (more foot traffic, slightly higher permit) and rent the
bike cart through a **co-op** at `$10/day` instead of a solo `$18/day` rental.
Demand of ~14 specialty drinks near lunchtime at a plaza is ordinary for a
one-person cart; it is not a stadium-scale assumption.

Only after this check was the simulation re-run.

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
| Daily bicycle-cart rental (co-op) | `cart_rental` | negative |
| Office-plaza pitch + permit share | `pitch_permit` | negative |
| Propane + light transport fuel | `fuel` | negative |
| Food-cart liability (prorated) | `insurance` | negative |
| Buy drink supplies (matcha, milk, cup, lid) | `supply` | negative |
| Sell a finished latte | `sale` | positive |

A used bicycle coffee cart would cost about **$750** — more than the $500
start — so the model **does not buy a cart**. Day 1 buys a **$95 starter kit**
(whisks, bowls, thermos, cooler bag, chalkboard) and then pays **$10/day** to
rent the cart via a shared co-op. If cash cannot cover that day's overhead
total, the cart stays **closed** (no restock, no sales) rather than skipping
the cost.

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
| `BASE_DAILY_DEMAND` | 14.0 | Expected drinks/day at list price (office-plaza lunch). |
| `MAX_DAILY_DEMAND` | 32 | Hard cap — foot traffic is bounded. |
| `ELASTICITY` | 1.25 | Same shape as `taro.store.demand`: raising price above list shrinks demand; discounting grows it. |
| Demand draw | `gauss(mean, sqrt(mean))` then clamp to `[0, MAX]` | Seeded RNG only; reproducible with seed 42. |
| `CART_PURCHASE_PRICE` | $750.00 | Used bicycle coffee cart — **not purchased** (unaffordable at $500). |
| `STARTER_EQUIPMENT` | $95.00 | Day-1 tools the start balance *can* cover. |
| `DAILY_CART_RENTAL` | $10.00 | Shared bike-cart co-op rate (was $18 solo). |
| `DAILY_PITCH_PERMIT` | $14.00 | Office-plaza pitch + daily permit share (better spot). |
| `DAILY_FUEL` | $3.00 | Propane for hot water plus short plaza commute. |
| `DAILY_INSURANCE` | $2.00 | Liability cover, about $730/year prorated. |
| Daily overhead total | $29.00 | Sum of rental + pitch + fuel + insurance; paid before restock. |
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

## Sensitivity

Honesty check for the PIP follow-up: a small override-only script in `$TMPDIR`
temporarily sets `BASE_DAILY_DEMAND` (or the seed) on the imported module, runs
the same 90-day loop, then restores the defaults. Defaults and `RESULTS.md`
were not changed.

**Plainly:** at seed 42 the cart **stops clearing $500 when `BASE_DAILY_DEMAND`
falls to 8** (final `$426.76`). `BASE=9` still clears (`$751.70`). Within the
requested sweeps — demand 10 / 12 / 14 at seed 42, and seeds 1–10 at default
demand 14 — every case still clears $500.

Exact stdout from `python3 "$TMPDIR/nori_sensitivity.py"` (run from the repo
root after writing the script into `$TMPDIR`):

```
Matcha Mile sensitivity (overrides only; defaults unchanged)
Defaults: BASE_DAILY_DEMAND=14.0, seed=42, days=90

## BASE_DAILY_DEMAND sweep (seed=42)
  BASE_DAILY_DEMAND=  10  final=$1,088.73  clears_$500=yes
  BASE_DAILY_DEMAND=  12  final=$1,730.55  clears_$500=yes
  BASE_DAILY_DEMAND=  14  final=$2,388.49  clears_$500=yes

## Seeds 1–10 (default BASE_DAILY_DEMAND)
  seed= 1  final=$2,368.21  clears_$500=yes
  seed= 2  final=$1,930.26  clears_$500=yes
  seed= 3  final=$2,111.24  clears_$500=yes
  seed= 4  final=$2,385.71  clears_$500=yes
  seed= 5  final=$2,554.63  clears_$500=yes
  seed= 6  final=$2,443.26  clears_$500=yes
  seed= 7  final=$2,341.93  clears_$500=yes
  seed= 8  final=$2,627.82  clears_$500=yes
  seed= 9  final=$2,275.50  clears_$500=yes
  seed=10  final=$2,334.15  clears_$500=yes

## Threshold probe (seed=42, lower BASE until final < $500)
  BASE_DAILY_DEMAND=  14  final=$2,388.49  clears
  BASE_DAILY_DEMAND=  13  final=$2,059.52  clears
  BASE_DAILY_DEMAND=  12  final=$1,730.55  clears
  BASE_DAILY_DEMAND=  11  final=$1,409.64  clears
  BASE_DAILY_DEMAND=  10  final=$1,088.73  clears
  BASE_DAILY_DEMAND=   9  final=$751.70  clears
  BASE_DAILY_DEMAND=   8  final=$426.76  FAILS

## Where it stops clearing $500
  Requested sweeps (BASE in {10,12,14} at seed 42; seeds 1–10 at default BASE=14): every case still clears $500.
  Plainly: at seed 42 the cart stops clearing $500 when BASE_DAILY_DEMAND falls to 8 (final=$426.76). BASE=9 still clears (final=$751.70).

Default check (BASE=14, seed=42): final=$2,388.49
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
