# Bench & Bell

A fictional bicycle tune-up bench competing on cash after 90 simulated days.
Python 3 standard library only; no imported project code or dependencies.

Run from the repository root:

```sh
python3 kiwi/business/run.py
python3 -m unittest discover -s kiwi/business
```

The run regenerates `ledger.csv` beside the script regardless of the current
working directory. `RESULTS.md` contains the exact stdout from the submitted run.

## Model assumptions

- Opening capital is $500.00, an initial account balance, not revenue and not a
  ledger transaction. Every subsequent cash movement passes through the ledger.
- The horizon is exactly days 1–90; there are no weekends or holidays in this
  fictional market. The private RNG is `random.Random(42)`.
- On day 1 a used tool kit and repair stand cost $220.00 combined. They have no
  terminal resale value in this cash competition.
- Each operating day costs $35.00: $20 bench rental and utilities plus $15 local
  advertising. These costs are paid before any service or customer payment.
- Advertising generates an independent uniform integer 4–14 prospective customers
  per day, inclusive. Each independently buys with probability
  `min(0.95, 0.80 * (5500 / price_in_cents) ** 2)`. At the $55 reference price
  conversion is 80%; higher prices reduce demand. These are invented assumptions,
  not measured customer acquisition or market data.
- The fixed advertised price is $69.00 throughout. No seed search or adaptive
  price optimization is used. The price targets a margin while reducing conversion
  relative to the reference price; it is not claimed to be optimal.
- Capacity is six tune-ups per day. Each uses 45 minutes of paid technician labor
  at $24/hour ($18) plus $12 parts, consumables, and payment handling: $30 total.
  Labor is purchased per job with no minimum shift. The proprietor performs no
  additional unpaid delivery or service labor in the model; administration is
  assumed covered by the per-job labor allowance. This is a simplifying assumption.
- Each service cost is debited before its $69 sale is credited. No sale happens
  unless its cost can be funded. Excess demand is lost without a waitlist.
- If daily overhead cannot be funded, the business closes for the remaining days.
  Daily market draws still occur for all 90 days. If a job cannot be funded, the
  remaining jobs that day are skipped. There are no loans or overdrafts.
- Jobs complete and pay immediately. There are no refunds, defaults, equipment
  failures, inventory carrying costs, taxes, interest, tips, grants, or owner
  withdrawals. This is fictional pre-tax cash profit, not a real-world forecast.
  Stable demand, flexible labor, and no failures favor this model; actual outcomes
  could be substantially worse. Competitors' balances are only comparable insofar
  as their market assumptions are comparable.
- Money is integer cents internally. CSV amounts are signed decimal dollars;
  `balance_after` is the balance after that row. Growth is profit divided by $500,
  expressed as a percentage rounded half-up to two decimal places.

Tests check rejected overdrafts leave the ledger unchanged, repeated runs agree,
all balances reconcile, the committed CSV matches the simulation, each sale has
an immediately preceding paid cost, daily capacity, price sensitivity, invalid
inputs, and closure under a deliberately loss-making price.
