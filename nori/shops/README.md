# Tiny Town — Businesses (Nori)

Six competition storefronts under `town.state["businesses"]`. Package: `nori.shops`.

## Interface

| Direction | Key | Shape |
|---|---|---|
| **Writes** | `town.state["businesses"]` | `shops`, `wages_paid`, `open_count`, `pending_revenue_cents`, `taxes_paid_cents`, `bills_paid_cents`, `arrears_cents` |
| **Reads** | `weather.condition` | storm closes; rain/snow shrink `available` |
| **Reads** | `residents.people` | `job` → `staff`; missing → no staff / no wages |
| **Reads** | `residents.purchases`, `residents.spent_cents` | yesterday's sales (one-day lag) |

Each `shops[shop_id]`:

`name`, `open`, `price_cents`, `available`, `balance_cents`, `sold_yesterday`, `staff`,
`tax_arrears_cents`, `bill_arrears_cents`, `arrears_cents` (sum)

Emits: `businesses_init` (setup), `daily`, `shops_closed` (storm), `shop_closed` (can't afford overhead), `wages_short`, `cogs_short`, `price_change` (weekly), `missed_shop_bill` (Phase 4).

## Shop ids and copied parameters

Ids are the Phase 2 contract strings. Numbers were **read** from each `<name>/business/` README/constants and copied here — this package does **not** import other agents' code.

| id | Name | price | unit cost | capacity | daily overhead | Source |
|---|---|---:|---:|---:|---:|---|
| `one-mug-tea` | One Mug Tea | $3.25 | $0.55 | 150 | $25.00 | `sora/business` |
| `bench-and-bell` | Bench & Bell | $69.00 | $12.00† | 6 | $35.00 | `kiwi/business` |
| `spoke-and-spanner` | Spoke & Spanner | $75.00 | $12.00† | 6 | $25.00 | `bao/business` |
| `matcha-mile` | Matcha Mile | $5.50 | $1.80 | 24 | $37.00 | `nori/business` |
| `fold-post` | Fold Post | $8.00 | $2.50 | 8 | $15.00 | `taro/business` |
| `daifuku-cart` | Strawberry Daifuku Cart | $3.75 | $1.30 | 120 | $20.00‡ | `mochi/business` |

† Competition unit costs for the bike shops bundled per-job labor. Phase 2 pays labor through `wages_paid`, so storefront `unit_cost` is **parts only** ($12). Matcha Mile / Fold Post use list price and max daily production/demand as the sell cap.

‡ Competition pitch was $35/day. Phase 4 adds shared commercial rent ($8) + licence ($2) on top; the cart’s residual overhead is **$20** so the seed-42 shop targets still hold without changing shared Phase 4 rates (proposed rent/licence cuts in chat if preferred).

Card fees, day-1 equipment, and endogenous pricing from the competition entries are **not** re-applied. Each ledger starts at **$500.00** (`50_000` cents) as a fresh Phase 2 opening balance.

## Daily tick (after weather, before residents)

1. **Settle lag / revenue.** Credit each shop for `pending_revenue_cents` (or morning fallback). Prefer `spent_cents` when present.
2. **Sales tax (Phase 4).** Debit `5%` of booked revenue (`SALES_TAX_PCT`). Pay what you can; unpaid → `tax_arrears_cents` + `missed_shop_bill`. **No RNG.**
3. **Arrears first.** Pay `tax_arrears_cents` then `bill_arrears_cents` from cash on hand (still no overdraft).
4. **Staff.** `staff` = resident ids whose `job` equals the shop id (sorted).
5. **Open / available + bills.** Storm → every shop closed. Else pay daily overhead if affordable; if not, close and emit `shop_closed`. While **open**, also pay commercial rent `$8` (`COMMERCIAL_RENT_CENTS`) and licence+utilities `$2` (`LICENCE_UTILITIES_CENTS`); shortfalls → `bill_arrears_cents` + `missed_shop_bill`. Rain/snow shrink `available`.
6. **Restock / COGS.** Debit `sold * unit_cost` after tax and bills. Partial → `cogs_short`.
7. **Weekly pricing (Phase 3).** On days `7, 14, …`, open shops revise `price_cents` (zero RNG).
8. **Wages (open days only).** Base + revenue share as before.
9. **Expose totals.** `taxes_paid_cents`, `bills_paid_cents` (today), `arrears_cents` (outstanding across shops).

### Why this wage rule

Fixed $30/day × 2 staff, paid even when closed, bankrupted small carts by days 8–11. Open-only base + revenue share scales with sales and skips storm / overhead-closed days, so thin-margin shops can survive while staff still share in good days.

## Phase 4 money movement

| Line | Amount | When | Destination (contract) |
|---|---:|---|---|
| Sales tax | 5% of booked revenue | every settlement | treasury |
| Commercial rent | $8.00/day | while open | out of town |
| Licence + utilities | $2.00/day | while open | treasury |

Pay what you can; never go negative. Arrears are paid first the next day.

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
