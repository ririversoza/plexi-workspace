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
- After wages and fixed bills, a visitor with more than 10,000 cents ($100) may buy one
  unit at each of up to two different shops; everyone else may buy one unit
  at one shop. This daily limit is fixed before the first purchase. Each
  selection is uniform among currently open, stocked, affordable contract
  shops not already visited today; affordability is checked again after the
  first purchase. If none qualify, shopping stops. A single weather-dependent
  visit draw gates the whole outing. Shopping uses no credit or repeated-shop visits.
  The extra demand and revised eight-person staffing
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
  change pending revenue. It emits missed-payment events for unpaid bills.
  The engine must tick once per day
  after businesses; repeated ticks for the same day are not deduplicated.
- `avg_wallet_cents` is the floor of total wallets divided by 120, calculated
  at setup and after shopping. All monetary values are integer cents.

Reads: `town.day`, `town.rng`, `weather.condition`, `businesses.shops`
(`open`, `price_cents`, `available`), and `businesses.wages_paid`.
Writes only `residents`: `people`, `purchases`, `spent_cents`, `count`,
`employed`, `avg_wallet_cents`, `avg_mood`, `mood_bands`, daily
`taxes_paid_cents`, `rent_paid_cents`, `bills_paid_cents`, plus aggregate
`arrears_cents` and `in_arrears`. Each person also has an integer `mood` and
the payment and arrears fields described below.

## Phase 4 taxes and bills

Each day, wages are credited after withholding 10% income tax (`wage_cents // 10`).
Unemployed residents also receive the previous economy tick's
`benefit_per_head_cents`, if present; that $7.50 starting benefit is not taxed.
Then old rent arrears, old utility arrears, today's $6 rent, and today's $1.50
utilities are paid in that order, before shopping. Old arrears may be paid
partially; a new bill is paid in full or its full amount becomes arrears.
`missed_rent` and `missed_bill` events carry `resident_id` and `amount_cents`
when a current bill is missed. Neither payment nor mood logic draws RNG.
Wallets cannot go below zero.

The root `taxes_paid_cents`, `rent_paid_cents`, and `bills_paid_cents` are
**daily actual payments**. `bills_paid_cents` means utilities only, including
payments against older utility arrears; rent is separate and leaves town.
Tax and utilities are available for the economy's treasury that day. Each
person carries `rent_arrears_cents`, `utility_arrears_cents`, their sum in
`arrears_cents`, and daily `taxes_paid_cents`, `rent_paid_cents`, and
`utilities_paid_cents` plus `benefit_received_cents`. The root
`benefits_received_cents` sums benefits credited that day. The root
`arrears_cents` sums unpaid amounts, while
`in_arrears` counts people with any unpaid amount.

## Phase 3 mood

Mood is a fictional, descriptive score, not an input to shopping, wages, or
any other economic decision. Each tick recomputes it after wages and purchases:

```text
mood = clamp(40 + wallet_points + employment_points + purchase_points
             - weather_penalty - arrears_penalty, 0, 100)
```

- Wallet points: one point per complete 1,000 cents ($10) of remaining wallet,
  capped at 40 points ($400). No fractions; more savings above $400 have no effect.
- Employment: +10 if `job is not None`, otherwise -10. This records employment
  status, not whether wages were actually received today.
- Purchases: +10 if at least one purchase succeeded today, otherwise 0.
  Two purchases still give only +10. Failed visits do not count; the bonus
  resets each tick. Wallet points use the balance after paying for purchases.
- Weather penalties: sun 0, cloud 5, rain 10, snow 15, storm 25. Missing,
  invalid, or unknown weather has no penalty, matching the sun fallback.
- Arrears penalty: 15 points while any rent or utility payment is overdue.
- Bands: `happy` = 70–100, `ok` = 40–69, `unhappy` = 0–39. `mood_bands`
  always contains all three integer counts, totaling 120. `avg_mood` is the
  floor of the sum of scores divided by 120.
- Setup initializes mood from starting wallets and jobs, with no purchases
  and neutral weather. It does not read another system's state.
- No mood history, mood events, or RNG draws. Shopping retains its existing
  random calls; available cash can change which purchases are affordable.

`fixtures/phase2_residents.py` is a frozen test reference from main commit
`1c3a689c0c575a9c0413c36a714334682b94923e`, not a second production system.
The Phase 3 regression compared UTF-8 JSON bytes for all pre-existing resident
fields and exact RNG states at setup and after every tick. Phase 4 changes
wallets and affordability by design; current tests still compare the setup
roster and no-shopping RNG states against the frozen reference.

Full-town validation against that main revision (CSV logging disabled, no
scratch/output files) also compared every day's non-mood state bytes, RNG state,
and events for seed 42 and seeds 1–20 over 90 days: all identical. Seed 42 ends
with 6 shops open, $500.88 average wallet, and no zero-balance streaks. Mood is
65 on average, with 87 happy, 15 ok, and 18 unhappy residents. 18/20 seeds meet
all balance targets; seeds 10 and 17 fail in both baseline and mood runs.
These Phase 3 results and the older Phase 2 archive below are historical.

Run standalone tests from the repository root:

```sh
python3 -m unittest discover -s kiwi/townfolk -t .
```

## Historical Phase 2 combined balance verification

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

## Resident diary

```sh
python3 -m kiwi.townfolk.diary 34
python3 -m kiwi.townfolk.diary "Gia Chen" --seed 42
python3 -m kiwi.townfolk.diary --random-pick --seed 42
```

The diary runs one 90-day town in-process through `taro.tinytown`, with the
installed systems and the log's `csv_path=None` before setup. It prints to
stdout and creates no reports, CSVs, or scratch files. Use Python's `-B` option
if you also want to suppress interpreter bytecode caches.

Each row shows day, weather, job, actual gross wages and benefits received, successful purchases
(shop ID and the actual price paid), wallet after, and mood. Assumptions:

- IDs are exact integers; full names match case-insensitively with surrounding
  whitespace ignored. Quote names containing spaces. Unknown IDs/names and
  duplicate-name matches produce a clear error; use an ID to resolve ambiguity.
- Provide either a selector or `--random-pick`, never both. Default seed: 42.
  Random-pick hashes the decimal seed with SHA-256, interprets the digest as
  an unsigned big-endian integer, and takes modulo the number of residents
  sorted by ID. It makes no `town.rng` draws and is stable for a given roster
  and seed. It is a deterministic selection, not a separate simulated event.
- The optional `System(purchase_observer=callback)` reporting hook receives
  `(resident_id, shop_id, price_cents)` immediately after each successful
  purchase. These are immutable values; no town or person reference is passed.
  The diary stores receipts outside town state and emits no events. The hook
  adds no RNG draws and does not alter purchase selection or wages.
- A wrapper snapshots wallets immediately before the residents tick and
  records rows immediately after it. Actual gross wage income is the closing
  wallet minus opening wallet plus receipts, taxes, rent, and utilities paid,
  then minus benefits received. This includes arrears payments and keeps the
  reported wage exact. Starting
  savings are excluded from total earned. Prices are captured at purchase
  time, so later price changes cannot rewrite history.
- Favourite shop means most successful purchases; ties use ascending shop ID.
  With no purchases, it is `none`. Happiest/saddest compare available mood
  scores; tied scores use the earliest day. Mood and those summary days show
  `n/a` until the happiness system (#35) is merged. The diary never invents
  mood scores. Missing weather likewise displays `n/a`; unemployed jobs are
  labeled explicitly. Missing businesses still permits outside wages.
- Missing residents or engine produces a readable message and exit status 1.
  CLI syntax errors return 2; success returns 0. Other optional systems are
  skipped by the engine loader. No simulation data is persisted.

Validation: fourteen resident tests (including diary determinism, lookup,
missing systems, variable-price receipts, wage/wallet conservation, summaries,
and exact observed-versus-unobserved daily state/RNG) plus six emergency tests
pass. A full-town seed-42 comparison at main `8ad2f2d` also confirmed identical
state, events, and RNG after 90 days with CSV writer calls forbidden. It
produced 120 in-memory diaries of 90 days each. The CLI random pick selected
Gia Chen (#34), with $1,300 earned, $976.50 spent, and favourite `daifuku-cart`.
