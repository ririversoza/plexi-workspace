# Residents

`kiwi.townfolk.System` exports `name = "residents"`. Stdlib only; all random
draws use `town.rng`. Setup reads no other system's state.

Assumptions and numbers:

- Exactly 120 people, integer IDs 1–120. The 15 first names × 8 surnames in
  `__init__.py` give 120 unique full names, shuffled once. Each person draws
  one of four streets uniformly (streets may repeat) and an initial wallet
  uniformly from 2,000–10,000 cents inclusive. These are starting savings.
- Jobs are independently shuffled: two staff each for `bench-and-bell` and
  `spoke-and-spanner`, one for each of the other four contract shop IDs,
  94 out-of-town workers (78.3% of all residents), and 18
  unemployed. Jobs and addresses stay fixed; 102 people are employed.
- Day 1 is Monday. Out-of-town workers receive 2,000 cents per weekday,
  including bad-weather days, from employers outside the modeled town. The balance amendment reduces
  the original 3,000-cent wage to 2,000 cents to limit outside cash inflow.
  Shop wages come only from today's `businesses.wages_paid`, keyed by integer
  resident ID. All valid listed payments are credited before shopping; no
  additional shop wage is invented. Unknown IDs are ignored.
- Each day uses a shuffled resident visiting order to avoid permanent ID
  priority for scarce stock. Visit probabilities: sun 65%, cloud 55%, rain
  35%, snow 20%, storm 0%. Missing/unknown weather defaults to sun. Storms
  prevent purchases even if a shop incorrectly advertises itself as open.
- After wages, a visitor with more than 10,000 cents ($100) may buy one
  unit at each of up to two different shops; everyone else may buy one unit
  at one shop. This daily limit is fixed before the first purchase. Each
  selection is uniform among currently open, stocked, affordable contract
  shops not already visited today; affordability is checked again after the
  first purchase. If none qualify, shopping stops. A single weather-dependent
  visit draw gates the whole outing. No credit, debt, repeated-shop visits,
  or other wallet expenses. The extra demand and revised eight-person staffing
  implement the Phase 2 balance amendment.
- Only strictly positive integer prices are accepted; stock and wage inputs
  must be nonnegative integers (booleans are not money). Missing/invalid
  values imply zero stock/wages or an unusable price. Missing businesses or
  shops means no shopping, while outside wages continue. Missing `open`
  means closed. Unknown shop IDs are ignored.
- Local remaining-stock counters enforce capacity without changing business
  state. Wallets cannot overdraw. `purchases` and `spent_cents` are sparse
  dictionaries, replaced daily; absent shop entries mean zero.
- Businesses settle these purchases next day under the shared contract.
  This system debits wallets immediately and does not book shop revenue,
  change pending revenue, or emit events. The engine must tick once per day
  after businesses; repeated ticks for the same day are not deduplicated.
- `avg_wallet_cents` is the floor of total wallets divided by 120, calculated
  at setup and after shopping. All monetary values are integer cents.

Reads: `town.day`, `town.rng`, `weather.condition`, `businesses.shops`
(`open`, `price_cents`, `available`), and `businesses.wages_paid`.
Writes only `residents`: `people`, `purchases`, `spent_cents`, `count`,
`employed`, and `avg_wallet_cents`.

Run standalone tests from the repository root:

```sh
python3 -m unittest discover -s kiwi/townfolk -t .
```

## Combined balance verification

Seed 42, 90 days: **6/6 shops open**, **$467.80 average wallet**, and
**zero days at $0 for every shop** (longest zero streak: 0 days).

| Shop | Day-90 balance | Units bought, days 1–90 | Days at $0 | Longest $0 streak |
|---|---:|---:|---:|---:|
| spoke-and-spanner | $18580.00 | 431 | 0 | 0 |
| bench-and-bell | $15663.20 | 431 | 0 | 0 |
| one-mug-tea | $3248.45 | 2525 | 0 | 0 |
| matcha-mile | $1536.90 | 1698 | 0 | 0 |
| daifuku-cart | $1524.50 | 2496 | 0 | 0 |
| fold-post | $1103.30 | 567 | 0 | 0 |

The leaderboard uses settled shop cash; day-90 purchases await next-day
settlement. Units count residents purchases exactly once, including day 90.
Zero-day counts are end-of-day observations, not intraday cash movements.

Verified in a temporary directory under the workspace: `git archive` of
`origin/main`, overlaid with `sora/tinytown`, `taro/tinytown`, and `nori/shops`
from their Phase 2 branches, then this `kiwi/townfolk` package. Ran
`python3 -m taro.tinytown.run` and a second run with an `on_day` callback
counting zero balances, consecutive-zero streaks, purchases, and bounds.
Every daily wallet and shop balance was nonnegative and sales stayed within
each shop's available stock. Nine standalone resident tests and six existing
emergency tests pass.

Input revisions:

- `origin/main`: `9f4d0be97b46629501886ca7b0330a9998f16460`
- `origin/sora-town2`: `1b0fa37bbaf20f94c990147dfbabd5300d59ac99`
- `origin/taro-town2`: `8e81e4424d2e73c532e5105c39f335106db52850`
- `origin/nori-town2`: `7fe08be48a049aa807f52f2ec7f8e3d95c146aeb`

These acceptance results cover the specified seed and 90-day horizon; they
are not a guarantee for every seed or an indefinitely sustainable economy.
