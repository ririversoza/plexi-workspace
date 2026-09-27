# Tiny Town — Businesses (Nori)

Six competition storefronts under `town.state["businesses"]`. Package: `nori.shops`.

## Interface

| Direction | Key | Shape |
|---|---|---|
| **Writes** | `town.state["businesses"]` | `shops`, `wages_paid`, `open_count`, `pending_revenue_cents` |
| **Reads** | `weather.condition` | storm closes; rain/snow shrink `available` |
| **Reads** | `residents.people` | `job` → `staff`; missing → no staff / no wages |
| **Reads** | `residents.purchases`, `residents.spent_cents` | yesterday's sales (one-day lag) |

Each `shops[shop_id]`:

`name`, `open`, `price_cents`, `available`, `balance_cents`, `sold_yesterday`, `staff`

Emits: `businesses_init` (setup), `daily`, `shops_closed` (storm), `shop_closed` (can't afford overhead), `wages_short`, `cogs_short`, `price_change` (weekly).

## Shop ids and copied parameters

Ids are the Phase 2 contract strings. Numbers were **read** from each `<name>/business/` README/constants and copied here — this package does **not** import other agents' code.

| id | Name | price | unit cost | capacity | daily overhead | Source |
|---|---|---:|---:|---:|---:|---|
| `one-mug-tea` | One Mug Tea | $3.25 | $0.55 | 150 | $25.00 | `sora/business` |
| `bench-and-bell` | Bench & Bell | $69.00 | $12.00† | 6 | $35.00 | `kiwi/business` |
| `spoke-and-spanner` | Spoke & Spanner | $75.00 | $12.00† | 6 | $25.00 | `bao/business` |
| `matcha-mile` | Matcha Mile | $5.50 | $1.80 | 24 | $37.00 | `nori/business` |
| `fold-post` | Fold Post | $8.00 | $2.50 | 8 | $15.00 | `taro/business` |
| `daifuku-cart` | Strawberry Daifuku Cart | $3.75 | $1.30 | 120 | $35.00 | `mochi/business` |

† Competition unit costs for the bike shops bundled per-job labor. Phase 2 pays labor through `wages_paid`, so storefront `unit_cost` is **parts only** ($12). Matcha Mile / Fold Post use list price and max daily production/demand as the sell cap.

Card fees, day-1 equipment, and endogenous pricing from the competition entries are **not** re-applied. Each ledger starts at **$500.00** (`50_000` cents) as a fresh Phase 2 opening balance.

## Daily tick (after weather, before residents)

1. **Settle lag.** Credit each shop for `pending_revenue_cents` (or, if empty, for current `residents.purchases` / `spent_cents` — still yesterday because residents have not ticked yet). Debit COGS = `sold_yesterday * unit_cost` with no overdraft. Prefer `spent_cents` when present.
2. **Staff.** `staff` = resident ids whose `job` equals the shop id (sorted). Missing residents → empty staff.
3. **Open / available.** Storm → every shop `open=False`, `available=0`. Otherwise pay daily overhead if affordable; if not, close and emit `shop_closed`. Rain keeps the shop open at 70% capacity; snow at 50%; sun/cloud at 100% (`int(capacity * factor)`).
4. **Wages (open days only).** Pay only when `open` is true after overhead. Each staffer gets `WAGE_BASE_CENTS = 500` ($5) plus an equal share of `20%` of the revenue booked that morning (`WAGE_REVENUE_SHARE_PCT`). Closed / storm days pay **$0** (no `wages_short` for being closed). Partial pay if cash is short; emit `wages_short`. Listed in `wages_paid` for residents to credit the same day.
5. **Weekly pricing (Phase 3).** On days `7, 14, 21, …` (`town.day % 7 == 0`), each **open** shop revises `price_cents` from open-day sell-through logged since the last adjust. **No `town.rng` draws** (businesses already draws zero times per tick; pricing keeps that constant).
6. **Pending refresh (by day, not content).** After residents shop, a post-residents system emit (`economy` / `traffic` / `emergency` / `log`) copies that day's `purchases`/`spent_cents` into `pending_revenue_cents` and records `_pending_from_day = town.day`. The next businesses tick books that day exactly once (`_last_settled_day`), even if two days have identical purchase dicts. Weather emits are ignored (purchases still belong to the previous day). If no later system emits, the morning fallback books `town.day - 1` from residents exactly once. Day-90 sales stay visible in `pending_revenue_cents` with no day-91 tick.

### Weekly pricing rule

Each open day is logged as `(sold_yesterday, available_yesterday)` on the next morning (one-day settlement lag). Closed days are not logged.

On a pricing day, for each shop that is open right now:

| Condition | Action |
|---|---|
| Sold out (`sold >= available`) on **most** logged open days this week (`sold_out * 2 > open_days`) | **+5%** (`PRICE_BUMP_PCT`) |
| Else week fill `(total_sold * 100) // total_avail < 40` | **−5%** (`PRICE_CUT_PCT`) |
| Else | hold |

Then clamp to integer cents in
`[max(80% of base, 115% of unit cost), 125% of base]`.
Emit `price_change` only when the price actually moves (`shop_id`, `old_price_cents`, `new_price_cents`, `reason` ∈ `bump|cut`).

### Why this wage rule

Fixed $30/day × 2 staff, paid even when closed, bankrupted small carts by days 8–11. Open-only base + revenue share scales with sales and skips storm / overhead-closed days, so thin-margin shops can survive while staff still share in good days.

## Money rules

- All money is **integer cents**.
- No overdraft: debits take `min(needed, balance)` only.
- `balance_cents` never goes negative.
- Setup does not read other systems (contract rule).
- **Constant RNG:** this system makes **zero** `town.rng` draws every tick (read-only features included).

## Missing peers

Safe alone: missing weather → treat as sun; missing residents → no staff, no sales settlement, all six shops still open/close on weather and burn overhead. Weekly pricing still runs from whatever sell-through was logged (often empty → hold).

## Tests

```bash
python3 -m unittest discover -s nori/shops -t .
```

Covers determinism (seed 42), price bounds, zero rng draws per tick, settlement-by-day, non-negative balances, storm closure, and solo operation with residents/weather absent.
