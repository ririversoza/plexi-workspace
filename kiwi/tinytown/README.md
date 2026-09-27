# Emergency services

Stdlib-only plugin exporting `kiwi.tinytown.System` with name `emergency`.
Call `setup(town)` once, then `tick(town)` daily for 90 days, after weather,
economy, and traffic. No engine import is needed.

## Inputs and validation

- Reads only `traffic.accidents_today` and `weather.condition` from other systems.
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

Writes only `state['emergency']`, with exactly these keys:

- `incidents_today`: new calls today, integer 0–1,007, excluding old backlog.
- `responded`: today's new calls served, integer 0–min(8, incidents_today).
- `avg_response_min`: modeled mean for all calls served, including old backlog.
- `open_incidents`: old plus new calls remaining, nonnegative integer.

The contract requires responded <= incidents_today, so backlog responses are
reported separately in an `emergency_summary` event. One event is emitted per
tick, none during setup. It includes the four state keys, `police_calls`,
`fire_calls`, `accident_calls`, and `backlog_responded`. Conservation is:
new backlog = old backlog + incidents_today - responded - backlog_responded.
Town supplies the day and system event metadata.

Backlog is held on the System instance and mirrored into output state; setup
resets it. One instance belongs to one town. State-only checkpoint restoration
and repeated ticks for the same day are not supported by this daily interface.
No files, subscriptions, or external system state are modified.

## Tests

From the repo root: `python3 -m unittest discover -s kiwi/tinytown -t .`
Tests use a fake Town and cover 90-day determinism, missing systems, exact
capacity/backlog conservation, response bounds, hostile input values, shared
RNG draw order, read-only inputs, and setup reset.
