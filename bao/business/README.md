# Spoke & Spanner

A fictional pop-up bicycle tune-up service, funded with $500.00 cash. The
strategy is to keep tooling inexpensive, pay costs before collecting each sale,
and sell a capacity-limited service with a positive contribution margin.

## Reproduce

From the repository root, using Python 3 and no third-party dependencies
(validated with Python 3.9.6):

```sh
python3 bao/business/run.py
python3 -m unittest discover -s bao/business
```

The run always uses seed **42**, simulates exactly **90 calendar days**, and
overwrites `bao/business/ledger.csv`. It prints the report verbatim stored in
`RESULTS.md`. To regenerate that report directly from stdout:

```sh
python3 bao/business/run.py > bao/business/RESULTS.md
```

## Assumptions (fictional, not market measurements)

- Currency is fictional dollars; accounting uses integer cents. Initial cash is
  $500.00, an opening balance rather than income or a ledger deposit. Every
  subsequent cash movement is a signed ledger transaction. No borrowing,
  investment returns, grants, or additional capital are available.
- Day 1 tooling costs $150.00 and a fictional setup permit costs $50.00. Tools
  last the full horizon with no salvage value or additional repairs.
- Each operating day costs $12.00 for shared workspace, $5.00 for insurance,
  and $8.00 for marketing. These are prepaid daily with no long-term commitments.
  Marketing supports the assumed footfall; no causal uplift is claimed.
- Each day draws an independent, uniformly distributed integer count of **3–9**
  potential customers. Each receives an independent reservation budget uniformly
  drawn in cents from **$40.00–$110.00**, inclusive. A customer buys if their budget
  is at least the posted **$75.00** price. Raising the price rejects more customers
  for the same budget draws; demand is neither guaranteed nor unbounded.
- At most **six** tune-ups can be completed per day. Unserved demand expires;
  customers do not carry over, refer friends, or generate compounding demand.
- Every sale first pays **$12.00 parts** and **$28.00 labor** in separate ledger
  entries, then collects **$75.00**. Parts are purchased just in time from an
  assumed reliable supplier. Labor includes all service and administrative time;
  no unpaid owner labor is assumed. The assumed contractor pool supports opening
  seven days a week without increasing daily capacity. No wages accrue on days
  with no jobs. Daily overhead still applies when open with no customers.
- Customers pay immediately in cash after completion. The simplified model has
  no payment fees, sales tax, income tax, refunds, defaults, or service failures.
  Costs are treated as all-in quotes. This is a pre-tax competition model, not a
  forecast or a claim about actual business viability.
- A day opens only if cash covers all daily overhead plus one job's costs.
  Otherwise it remains closed with no expenses or sales. The market is still
  drawn for that day, and simulation continues through day 90. Each job must
  also be affordable before its costs are posted. The ledger independently
  rejects any debit that would cause a negative balance, without partial writes.
- There are no inventory assets, receivables, debts, terminal liquidation, or
  owner withdrawals. Final cash determines the score. Profit is final cash less
  $500.00; growth is profit divided by $500.00 times 100, rounded to two decimals.
- RNG draw order is one `randint(3, 9)` per day followed by one
  `randint(4000, 11000)` per potential customer, using a local `random.Random(42)`.
  Price and capacity stay fixed; there is no seed search or fitted revenue.
  Reproduce with the same Python RNG implementation; future Python versions
  could change `randint` behavior.

## Audit

`ledger.csv` records `day,type,amount,balance_after`, with dollar amounts to two
decimal places. Debits are negative and sales positive. Starting from $500.00,
adding every signed amount reproduces every running balance and the final cash.
Tests cover overdraft rejection, deterministic runs, reconciliation, cost-before-
sale ordering, capacity, price sensitivity, and exact committed artifact contents.

All code here is original for this entry; no code was imported from other agents
or from main. Results depend heavily on the invented demand and cost assumptions;
a high score establishes reproducible arithmetic, not empirical business success.
