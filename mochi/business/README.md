# 🍓 Strawberry Daifuku Cart (Mochi)

Mochi's entry for the [$500 Business Competition](../../juniper/COMPETITION.md): a one-person street cart selling fresh, hand-wrapped strawberry daifuku (a whole strawberry and sweet red-bean paste wrapped in soft mochi). Fictional virtual currency only.

## Run it

From the repo root:

```bash
python3 mochi/business/run.py                      # prints results, regenerates ledger.csv
python3 -m unittest discover -s mochi/business     # tests
```

Zero dependencies (Python 3 standard library). Seed `42`, exactly 90 days, start at $500.00. Results are in [RESULTS.md](RESULTS.md).

## Files

| File | What it does |
|---|---|
| `ledger.py` | Append-only ledger in **integer cents**. `record()` refuses any transaction that would take the balance below zero. |
| `business.py` | The model: demand, costs, production planning, and the 90-day loop. All assumptions are named constants at the top. |
| `run.py` | Runs the simulation, writes `ledger.csv`, prints the summary. |
| `test_business.py` | No overdraft, determinism, `final == 500 + sum(ledger)`, balance chaining, bounded price-sensitive demand, and every sale carrying a cost. |
| `ledger.csv` | Every transaction: `day, type, amount, balance_after`. |

The code is mine alone. It doesn't import `taro.store`, because exact-sum checks need an integer-cents ledger that records every transaction.

## Assumptions

### Prices and costs

| Item | Value | Notes |
|---|---:|---|
| Selling price | $3.75 / piece | Typical for handmade daifuku from a street stall or market. Fixed for all 90 days. |
| Ingredients + packaging | $1.30 / piece | Strawberry $0.55, glutinous rice flour/sugar/starch $0.25, red-bean paste $0.30, tray and wrap $0.20. |
| Startup equipment | $150.00 once (day 1) | A used steamer, a cooler and a folding table. |
| Pitch fee + permit | $35.00 / day open | Street-vending pitch fee plus the daily share of the permit. |
| Card processing | 2.6% + $0.15 / card transaction | 70% of customers pay by card. Each customer is assumed to buy one piece, so each card sale pays the fixed fee (a conservative choice). |
| Owner's labor | **not paid** | The cart is owner-operated, so profit is the owner's pay before their time. About $62/day for a full day of work is modest, not windfall money. |

No loans, no grants, no hardcoded revenue. The only money coming in is `sales` = pieces sold × price.

### Demand

- **Base demand at the $3.50 reference price:** 55 pieces on weekdays, 90 on weekends (day 1 is a Monday).
- **Price sensitivity:** expected demand × (3.50 / price)^1.5, which gives an elasticity of −1.5. At $3.75 that's about 90% of base.
- **Weather:** each day is rainy with probability 25% (seeded RNG). Rain halves demand.
- **Noise:** the expected value is multiplied by `uniform(0.75, 1.25)` from the seeded RNG.
- **Bounds:** demand is rounded and clamped to 0–150 pieces per day (a foot-traffic ceiling).
- Each day's RNG draws happen in a fixed order, so the same seed always gives the same ledger.

### Capacity and production

- **Capacity:** at most 120 pieces per day, the most one person can hand-wrap each morning.
- **Perishable:** daifuku with fresh strawberry don't keep, so unsold pieces are **thrown away at close**. Their ingredient cost is still paid, which is why the results show 474 wasted pieces.
- **Forecast:** each morning the owner plans from the average sales of the last 3 dry days of the same kind (weekday or weekend). They add 5%, or 20% if the last such day sold out, because sell-outs hide true demand. They make half as many on rainy days (they check the weather before making the batch). The first days use guesses of 60 on weekdays and 90 on weekends.
- **Cash limits:** the batch is capped by capacity and by what the balance can pay for. If the balance can't cover the pitch fee plus one piece, the cart stays closed that day (never happened with seed 42).

### Order of transactions each day

`pitch_fee` → `ingredients` → `sales` → `card_fees`, plus `equipment` once on day 1. Card fees are always smaller than that day's sales, so they can't overdraw.

## Known simplifications

- The price is fixed. There's no price optimization or promotions.
- There's no seasonality, competition or growing reputation over the 90 days.
- There are no taxes, insurance or equipment wear beyond the startup cost.
