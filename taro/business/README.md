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

1. **Materials cost.** Every finished pack costs `$2.50` in paper, envelope, and
   adhesive (`UNIT_COST`). Materials are paid via a ledger `materials` debit
   before that day's sales. No free inventory, no loans, no gifts.
2. **Labour cost.** Folding is not free. Each pack produced costs `$3.00`
   (`LABOUR_PER_PACK`) — about 20–25 minutes of careful folding at a modest
   craft wage — recorded as a `labour` debit the same day.
3. **Daily production capacity.** One person can finish at most
   `MAX_DAILY_PRODUCTION = 8` handmade packs per day. Materials do **not**
   become finished stock instantly beyond that cap.
4. **Stall fee.** Opening the craft-market booth costs `$15.00` per day
   (`STALL_FEE`), debited as `stall`. If cash cannot cover the fee, the stall
   stays closed and there are no sales that day (stock is held).
5. **Card fees.** Card-reader fees take `2.9%` of sale revenue (`CARD_FEE_RATE`),
   debited as `card_fee` after each sale credit.
6. **Revenue only from sales.** Cash rises only when packs sell
   (`sold * price`). Zero sales → no credit that day. Nothing is hardcoded as
   “daily revenue.”
7. **Price-sensitive demand.** Expected demand at list price `$8.00` is
   `BASE_DAILY_DEMAND = 6` packs/day. Mean demand scales as
   `(list_price / price) ** 1.3`. Raising price shrinks demand; discounting
   grows it. The price floor is `1.15 × (materials + labour)`.
8. **Bounded demand.** After Gaussian noise around that mean (seeded), demand is
   clamped to `[0, MAX_DAILY_DEMAND]` where `MAX_DAILY_DEMAND = 18`. A stall
   cannot invent infinite foot traffic.
9. **Stock constraint.** You cannot sell more packs than you hold. Missed demand
   is recorded and used only as a production signal — not as free money.
10. **No overdraft.** The ledger refuses any debit larger than the current
    balance (`InsufficientFundsError`). Production quantity is capped with
    `max_affordable_units` on the combined materials+labour cash cost before
    debiting.
11. **Operator policy is endogenous.** Price floats between the cost floor and a
    small premium/discount vs list based on stock health and yesterday's
    stockouts. Production targets ~5 days of cover, then clips to capacity and
    cash. This changes *inputs*; revenue still comes only from the demand draw
    × stock on open stall days.
12. **Ledger identity.** Every money move is a signed row
    `(day, type, amount, balance_after)` with credits positive and debits
    negative, so
    `final_balance == 500 + sum(ledger amounts)`.

## Layout

| Path | Role |
|---|---|
| `business.py` | `FoldPost` simulator |
| `ledger.py` | Recording, no-overdraft ledger + CSV writer |
| `run.py` | 90-day entrypoint; prints totals; writes `ledger.csv` |
| `test_business.py` | Overdraft, determinism, ledger identity, capacity, costs |
| `RESULTS.md` | Exact `run.py` stdout |
| `ledger.csv` | Regenerated transaction log |

— Taro
