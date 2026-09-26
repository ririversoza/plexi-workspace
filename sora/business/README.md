# One Mug Tea

A single street cart selling hot milk tea. One urn, one price, no bloat.

```
python3 sora/business/run.py                       # prints results, regenerates ledger.csv
python3 -m unittest discover -s sora/business      # tests
```

Zero dependencies, Python 3, seed `42`, 90 days, start $500.00. No code imported from other agents.

## Daily loop

1. Pay the permit.
2. Brew cups for the forecast (expected demand × 1.1), capped by urn capacity and by what the balance can afford.
3. The seeded RNG draws the weather and noise, and actual demand follows.
4. Sell `min(demand, brewed)`. Leftover tea is thrown away because it doesn't keep.
5. Take the card fees out of revenue.

Every cent moves through `Ledger.record`, which raises `OverdraftError` rather than go below $0. Money is kept in integer cents, so the ledger always reconciles exactly.

## Assumptions

| Item | Value | Why |
|---|---|---|
| Starting cash | $500.00 | Competition rule |
| Equipment (day 1, once) | $180.00 | Insulated urn, kettle, two thermoses, sign |
| Permit + pitch fee | $25.00/day | Typical city market day-stall fee |
| Cost per cup | $0.55 | Tea, milk, sugar, 12 oz cup and lid, gas for the burner |
| Price | $3.25/cup | Below café prices (usually $4–5) |
| Card fees | 2.9% of revenue | Standard card-reader rate |
| Capacity | 150 cups/day | One urn refilled during the day, one person serving |
| Base demand | 90 cups/day at $3.00 | Fair-weather weekday at a busy pitch |
| Price elasticity | 1.8 | Demand × (3.00 / price)^1.8, so demand falls as price rises |
| Weekends | ×1.25 | Days 6, 7, 13, 14, … |
| Rain | 20% chance, ×0.6 | Seeded RNG |
| Noise | Gaussian, mean 1, sd 0.15, clamped to [0.6, 1.4] | Seeded RNG |
| Demand bounds | 0 to 150 cups | Can't sell more than capacity |

The forecast doesn't know the weather, so rainy days waste tea and busy days sell out.

## Not modelled

- **Owner labour.** The owner runs the cart and takes no wage, so profit here means cash to the owner before paying themselves. At $15/hr for 8 hours a day, 90 days of wages would be about $10,800.
- Taxes, insurance, equipment wear and restocking trips.
- Growth: the cart doesn't expand or reinvest, so profit is roughly linear in the number of days.

The growth % is high because $500 is small next to a cart's daily cash flow, not because the cart makes much per cup (about $2.60 before fixed costs).
