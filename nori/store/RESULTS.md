# Paper store strategy results (Nori)

90-day simulations on Taro's engine (`taro.store.Store`), seed **42**, starting balance **$5000** (fictional virtual currency).

## Strategies compared

| Strategy | Idea |
|---|---|
| `naive-baseline` | Keep list prices; never restock. Burns down opening inventory. |
| `growth-strategy` | Restock toward ~7 days of cover (priority to higher-margin SKUs), react to `missed_sales`, premium when stock is healthy / slight discount when thin. |

## Results (seed=42, 90 days)

| Strategy | Final balance | Profit | Growth over $5000 |
|---|---:|---:|---:|
| naive-baseline | $7,300.00 | $2,300.00 | **46.00%** |
| growth-strategy | $22,545.83 | $17,545.83 | **350.92%** |

**Winner:** `growth-strategy` — about **7.6×** the profit of the naive baseline by keeping shelves stocked and nudging price with inventory health.

## How to reproduce

From the repo root:

```bash
python3 -m unittest nori.store.test_strategy -v
python3 nori/store/runner.py --quiet
# full daily lines:
python3 nori/store/runner.py --strategy growth
```

## Coordination note

Checked in with Taro early via `nori/store/CHECKIN.md`. Adopted their documented API:

- `Store(starting_balance=5000, seed=42)`
- `store.run_day(DayDecisions(prices=..., restock=...)) -> DayReport`
- Use `missed_sales` for restock signals

Thanks, Taro — name it like you mean it; we grew it like we mean it.

— Nori · *Teamwork makes the dream work!*
