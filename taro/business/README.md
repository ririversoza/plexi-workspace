# Fold Post (Taro) — business competition

Handmade **origami greeting-card packs** sold from a market stall / online booth.
Currency is **fictional virtual money**. Zero third-party dependencies; Python 3 stdlib only.

## Credits

Demand elasticity shaping and the “never overdraw cash” rule are inspired by the
paper-store engine already on `main` (`taro.store`). This package does **not**
import that engine: the competition starts at **$500** (not $5,000) and requires
a transaction CSV the store ledger does not emit.

## Reproduce

From the repo root:

```bash
python3 -m unittest discover -s taro/business -v
python3 taro/business/run.py
```

`run.py` always regenerates `taro/business/ledger.csv`. Exact printed totals live
in `RESULTS.md` — Juniper re-runs and diffs.

## Fixed competition parameters

| Knob | Value |
|---|---|
| Seed | `42` (`random.Random(42)`) |
| Days | exactly `90` |
| Starting cash | `$500.00` |
| Product | one SKU — origami card pack |

## Model assumptions (honest)

1. **Real unit cost.** Every finished pack costs `$2.50` in paper, envelope, and
   adhesive (`UNIT_COST`). Supplies are paid **before** that day's sales via a
   ledger debit. No free inventory, no loans, no gifts.
2. **Revenue only from sales.** Cash rises only when packs sell
   (`sold * price`). Zero sales → no credit that day. Nothing is hardcoded as
   “daily revenue.”
3. **Price-sensitive demand.** Expected demand at list price `$8.00` is
   `BASE_DAILY_DEMAND = 6` packs/day. Mean demand scales as
   `(list_price / price) ** 1.3`. Raising price shrinks demand; discounting
   grows it.
4. **Bounded demand.** After Gaussian noise around that mean (seeded), demand is
   clamped to `[0, MAX_DAILY_DEMAND]` where `MAX_DAILY_DEMAND = 18`. A stall
   cannot invent infinite foot traffic.
5. **Stock constraint.** You cannot sell more packs than you hold. Missed demand
   is recorded and used only as a restock signal — not as free money.
6. **No overdraft.** The ledger refuses any debit larger than the current
   balance (`InsufficientFundsError`). Restock quantity is capped with
   `max_affordable_units` before debiting.
7. **Operator policy is endogenous.** Price floats between a cost floor
   (`unit_cost * 1.15`) and a small premium/discount vs list based on stock
   health and yesterday's stockouts. Restock targets ~5 days of cover. This
   changes *inputs* (price, supply buys); revenue still comes only from the
   demand draw × stock.
8. **Ledger identity.** Every money move is a signed row
   `(day, type, amount, balance_after)` with credits positive and debits
   negative, so
   `final_balance == 500 + sum(ledger amounts)`.

## Layout

| Path | Role |
|---|---|
| `business.py` | `FoldPost` simulator |
| `ledger.py` | Recording, no-overdraft ledger + CSV writer |
| `run.py` | 90-day entrypoint; prints totals; writes `ledger.csv` |
| `test_business.py` | Overdraft, determinism, ledger identity |
| `RESULTS.md` | Exact `run.py` stdout |
| `ledger.csv` | Regenerated transaction log |

— Taro
