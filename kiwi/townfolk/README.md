# Residents

`kiwi.townfolk.System` exports `name = "residents"`. Stdlib only; all random
draws use `town.rng`. Setup reads no other system's state.

Assumptions and numbers:

- Exactly 120 people, integer IDs 1–120. The 15 first names × 8 surnames in
  `__init__.py` give 120 unique full names, shuffled once. Each person draws
  one of four streets uniformly (streets may repeat) and an initial wallet
  uniformly from 2,000–10,000 cents inclusive. These are starting savings.
- Jobs are independently shuffled: exactly two staff for each of the six
  contract shop IDs, 90 out-of-town workers (75% of all residents), and 18
  unemployed. Jobs and addresses stay fixed; 102 people are employed.
- Day 1 is Monday. Out-of-town workers receive 3,000 cents per weekday,
  including bad-weather days, from employers outside the modeled town.
  Shop wages come only from today's `businesses.wages_paid`, keyed by integer
  resident ID. All valid listed payments are credited before shopping; no
  additional shop wage is invented. Unknown IDs are ignored.
- Each day uses a shuffled resident visiting order to avoid permanent ID
  priority for scarce stock. Visit probabilities: sun 65%, cloud 55%, rain
  35%, snow 20%, storm 0%. Missing/unknown weather defaults to sun. Storms
  prevent purchases even if a shop incorrectly advertises itself as open.
- A visitor uniformly selects one open, stocked contract shop and attempts
  to buy exactly one unit. If unaffordable, they leave without trying another
  shop. No credit, debt, multi-unit purchases, or other wallet expenses.
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
