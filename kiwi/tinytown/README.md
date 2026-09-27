# Emergency services

Stdlib-only plugin exporting `kiwi.tinytown.System` with name `emergency`.
Call `setup(town)` once, then `tick(town)` daily for 90 days, after weather,
economy, and traffic. No engine import is needed.

## Inputs and validation

- Reads `traffic.accidents_today`, `weather.condition`, and
  `residents.people[*].street` from other systems during ticks only.
- Missing or non-dict sections become empty dictionaries. Only plain dictionaries
  are accepted, avoiding calls into custom mapping implementations.
- Accidents must be a plain integer from 0 through 1,000 inclusive. Booleans,
  floats (including NaN/infinity), negatives, oversized integers, and other
  types default to zero. This is a model input limit, not a contract-wide limit.
- Condition must be a plain string: sun, cloud, rain, snow, or storm. Everything
  else defaults to sun. Type checking precedes lookup, including unhashable data.
- Temperature, season, congestion, economy, and other fields are not read.
- The Town interface itself is trusted: state is a dict, RNG and emit work.
  Setup is required; malformed external state values never need an exception.

## Model and all numeric assumptions

Each accident produces one emergency call. Police generate 0–3 additional calls
uniformly per day. Fires generate 0–1 calls uniformly, plus 0 for sun/cloud,
1 for rain/snow, or 3 for storms. Rain calls represent weather-related fire
service work. These are illustrative simulation rates, not real-world estimates.

Police and fire share a pool capable of answering 8 calls daily; accidents use
this same pool and are not counted again as police/fire calls. Older backlog
is served first. Calls are fungible; no severity or per-call age is modeled.
Backlog is never dropped or capped. Maximum new demand is 1,007 per day, and
maximum backlog after a fresh 90-day run is 89,910 (999 net per day).

Every tick consumes exactly three calls from `town.rng`, in order:
`randint(0, 3)`, `randint(0, 1)`, and `uniform(4.0, 8.0)`. No private or global
RNG is used. Determinism assumes the same shared RNG seed and preceding calls.

Response minutes are the uniform 4–8 minute base, plus a weather penalty
(sun/cloud 0, rain 2, snow 4, storm 6), plus 4 times the fraction of today's
8-call capacity used. Round to two decimals. The result is 0.0 when no calls
are served, otherwise a float from 4.0 through 18.0. This is a modeled service
response duration across all calls served today; it excludes days spent queued.

## Output semantics

Writes only `state['emergency']`, preserving these Phase 1 keys:

- `incidents_today`: new calls today, integer 0–1,007, excluding old backlog.
- `responded`: today's new calls served, integer 0–min(8, incidents_today).
- `avg_response_min`: modeled mean for all calls served, including old backlog.
- `open_incidents`: old plus new calls remaining, nonnegative integer.

When the resident roster has at least one recognized street, ticks also add:

- `incidents_by_street`: all four street names mapped to nonnegative integers,
  summing exactly to `incidents_today`.
- `busiest_street`: the street with the highest count, or `None` if there were
  no new incidents. Ties use the daily rotation described below.

Setup does not read other systems and initializes only the Phase 1 keys.
Missing/invalid/empty resident rosters, or rosters with no recognized streets,
keep exactly the Phase 1 shape and behavior. Removing residents between ticks
removes the street fields; no stale breakdown is carried forward.

### Deterministic street allocation

The fixed street order is Clover Lane, Maple Street, Orchard Road, Willow Way,
matching the residents contract. No other package is imported. Each valid
resident entry contributes one to its street population. Only a plain `people`
list, plain person dictionaries, and exact plain-string street names are used;
unknown streets and malformed entries are ignored. Empty streets receive zero.

Allocate today's new incidents in proportion to these populations: first give
each street `incidents_today * population // total_population`, then distribute
the remaining incidents to streets with the largest integer remainders. At
most three incidents remain. For tied remainders, use the fixed street order
rotated left by `(town.day - 1) % 4`; the same rotation resolves busiest-street
ties. Day 1 starts at Clover Lane, day 2 at Maple Street, and so on. All four
keys remain present when allocation is active, including zero-count streets.

This is an illustrative distribution of incident locations, not per-resident
attribution. Population is recomputed each tick. Only new incidents are assigned;
old backlog, response capacity, and response times are unchanged. Allocation
uses integer arithmetic and makes **zero** RNG calls. The original three calls,
their order, and all pre-existing simulation outputs remain unchanged.

The contract requires responded <= incidents_today, so backlog responses are
reported separately in an `emergency_summary` event. One event is emitted per
tick, none during setup. It includes the four state keys, `police_calls`,
`fire_calls`, `accident_calls`, and `backlog_responded`. Conservation is:
new backlog = old backlog + incidents_today - responded - backlog_responded.
Town supplies the day and system event metadata.
The street fields are state-only; the existing summary event remains exactly
unchanged so subscribers and their logs retain the same contents.

Backlog is held on the System instance and mirrored into output state; setup
resets it. One instance belongs to one town. State-only checkpoint restoration
and repeated ticks for the same day are not supported by this daily interface.
No files, subscriptions, or external system state are modified.

## Tests

From the repo root: `python3 -m unittest discover -s kiwi/tinytown -t .`
Tests use a fake Town and cover 90-day determinism, missing systems, exact
capacity/backlog conservation, response bounds, hostile input values, shared
RNG draw order, read-only inputs, and setup reset.
Street tests cover proportional allocation, daily tie rotation, conservation
over every incident count 0–1,007, zero-population streets, missing/invalid
rosters, and removal between ticks. `fixtures/phase1_emergency.py` is a frozen
reference from main `8ad2f2d4e73b2926c6f24e90660815773472fc1e`; do not update it
alongside production changes. Both standalone and optional full-town 90-day
tests compare the existing state, event stream, and exact final RNG state with
that reference. Full-town logging uses `csv_path=None`; no output files.

Validation: all 11 emergency tests pass, including the full-town comparison.
`python3 -B -m unittest bao.tinytown.test_town_acceptance` also passes: seed-42
90-day balance targets and determinism remain intact. All edits stay in
`kiwi/tinytown/`; no scratch trees are needed.
