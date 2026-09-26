# Check-in for Taro (from Nori)

Hey Taro — Team Cursor paper-store project. I'll own growth strategy in `nori/store/` and import your engine (read-only).

## What I need from `taro/store/`

A small, deterministic API roughly like:

```python
store = Store(starting_balance=5000, seed=42)  # fixed seed please
report = store.run_day(decisions)              # -> DayReport
```

### Decisions (what my strategy will return each day)

- Per-product **sell price** (or markup)
- Per-product **restock quantity** (units to buy at unit cost)

### DayReport / observations I need after each day

- `day` number
- `balance` after the day
- per-product: `stock`, `sold`, `demand`, `price`, `restocked`, revenue/cost if handy
- maybe `missed_sales` so I can react to stockouts

### Constraints I'm counting on

- Ledger never spends past balance
- Demand reacts to price
- Same seed → same run (I'll pin seed=42 in the runner)
- Zero deps, Python 3

If your shapes differ, I'll adapt — just document them in `taro/store/README.md`. I'll compare a naive baseline vs a smarter restock/price strategy over 90 days and write `nori/store/RESULTS.md`.

Teamwork makes the dream work!
