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

Emits: `businesses_init` (setup), `daily`, `shops_closed` (storm), `shop_closed` (can't afford overhead), `wages_short`, `cogs_short`.

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
4. **Wages.** Pay `STAFF_WAGE_CENTS = 3000` ($30) per staff member **every day** (including storm closures). Partial pay if the ledger is short; emit `wages_short`. Listed in `wages_paid` for residents to credit the same day.
5. **Pending refresh.** A `town.subscribe` callback copies new `residents.purchases` into `pending_revenue_cents` when a *later* system emits (residents themselves do not emit). Batches already booked this morning are skipped via a signature, so day-90 sales stay visible in `pending_revenue_cents` with no day-91 tick. If no later system emits, the next morning's fallback still settles from `residents.purchases`.

## Money rules

- All money is **integer cents**.
- No overdraft: debits take `min(needed, balance)` only.
- `balance_cents` never goes negative.
- Setup does not read other systems (contract rule).

## Missing peers

Safe alone: missing weather → treat as sun; missing residents → no staff, no sales settlement, all six shops still open/close on weather and burn overhead.

## Tests

```bash
python3 -m unittest discover -s nori/shops -t .
```

Covers determinism (seed 42), non-negative balances / bounds, storm closure, wage shortfalls, and solo operation with residents/weather absent.
