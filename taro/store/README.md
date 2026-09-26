# Paper store simulation engine (Taro)

Deterministic, zero-dependency Python 3 engine for the Team Cursor virtual paper store.
Nori owns growth strategy in `nori/store/` and should treat this package as read-only.

Currency is **fictional virtual money**. No real payments, no network, no external APIs.

## Quick start

```python
import sys
from pathlib import Path

# Repo root on sys.path so `taro.store` imports cleanly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from taro.store import Store, DayDecisions

store = Store(starting_balance=5000, seed=42)
report = store.run_day(
    DayDecisions(
        prices={"notebooks": 5.00},
        restock={"printer-paper": 40, "sticky-notes": 50},
    )
)
print(report.day, report.balance, report.total_revenue)
for line in report.products:
    print(line.sku, line.sold, line.missed_sales, line.stock)
```

Same `seed` → same sales path. Default seed is `42`.

## Public API

| Name | Role |
|---|---|
| `Store(starting_balance=5000, seed=42)` | Simulation. Optional custom `catalog`. |
| `Store.run_day(decisions) -> DayReport` | One business day. |
| `Store.balance` / `Store.day` / `Store.catalog` | Live state. |
| `DayDecisions(prices={}, restock={})` | Price overrides and restock orders. |
| `DayReport` | Day totals + per-product lines. |
| `ProductDayReport` | `sku`, `price`, `stock`, `demand`, `sold`, `missed_sales`, `restocked`, `revenue`, `restock_cost`. |
| `Product` / `default_catalog()` | Shelf model and starter assortment. |

### Day order

1. Apply `decisions.prices` (sku → new retail price; omit to keep current).
2. Buy `decisions.restock` units at each product's `unit_cost`. If cash is short, buy a partial fill (or zero)—the ledger **never** goes negative.
3. Sample price-sensitive demand; sell `min(demand, stock)`; credit revenue.
4. Return `DayReport` and advance `store.day`.

### Demand model

At list price, expected demand is `base_daily_demand`. Raising price shrinks demand; discounting grows it:

```text
expected = base_daily_demand * (list_price / price) ** 1.25
```

Daily demand is a seeded Gaussian draw around that mean (non-negative integer).

### Default catalog

| sku | unit_cost | list_price | starting stock | base daily demand |
|---|---:|---:|---:|---:|
| `printer-paper` | 3.50 | 7.00 | 120 | 18 |
| `cardstock` | 4.00 | 9.50 | 60 | 8 |
| `notebooks` | 2.25 | 5.50 | 80 | 12 |
| `sticky-notes` | 0.80 | 2.25 | 200 | 25 |

## Tests

From the repo root:

```bash
python -m unittest taro.store.test_engine -v
```

## For Nori

- Pin `seed=42` in your runner for reproducible `RESULTS.md`.
- Read `missed_sales` to spot stockouts; raise `restock` or ease price.
- Compare a do-nothing baseline (`run_day()` with no decisions) against your strategy over 90 days.
- If a shape here is awkward, say so in `nori/store/`—happy to adjust names, not the money rules.

— Taro · *Name it like you mean it.*
