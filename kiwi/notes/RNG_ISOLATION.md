# RNG isolation measurements

Measured on 2026-09-27 against current `origin/main`
`8ad2f2d4e73b2926c6f24e90660815773472fc1e`, using **CPython 3.9.6**,
seed **42**, **90 days**, all installed systems, and log `csv_path=None`.
This is a measurement and design note only; no shared-system code was changed.

## Result: constant API calls do not mean constant stream advancement

A Mersenne Twister word here is one 32-bit generator output. The table counts
words consumed during each system tick, excluding setup.

| System | Ticks measured | Min words/tick | Mean words/tick | Max words/tick | Total tick words | Setup words |
|---|---:|---:|---:|---:|---:|---:|
| weather | 90 | 4 | 4.000000 | 4 | 360 | 0 |
| businesses | 90 | 0 | 0.000000 | 0 | 0 | 0 |
| residents | 90 | 405 | 558.011111 | 688 | 50,221 | 696 |
| economy | 90 | 0 | 0.000000 | 0 | 0 | 0 |
| traffic | 90 | 10 | 10.000000 | 10 | 900 | 0 |
| emergency | 90 | 4 | 6.344444 | 19 | 571 | 0 |
| log | 0 (subscriber only) | n/a | n/a | n/a | 0 | 0 |

Total: **52,052 tick words + 696 setup words = 52,748 words**.

The log is not ticked. Its callbacks consume no randomness in this revision.
Economy's zero is specific to the full-town configuration: resident population
and employment are available, so its fallback `randint` and `uniform` do not run.
These are observed extrema, not theoretical bounds or guarantees for other
seeds, Python versions, or system subsets.

First ten daily samples:

- residents: 506, 466, 507, 560, 462, 513, 577, 628, 566, 528
- emergency: 4, 7, 4, 6, 6, 6, 5, 6, 7, 4

Emergency still calls exactly `randint(0, 3)`, `randint(0, 1)`, and
`uniform(4, 8)`. The two integer selections use rejection sampling through
`getrandbits`; retries consume additional words. For example, selecting one
of four values uses a 3-bit candidate and rejects values 4–7 in this runtime.
The float draw consumes two words. Thus a fixed count of three high-level
calls is insufficient to pin the stream position.

Residents vary for **two** reasons: shuffle/choice/randint rejection sampling,
and varying numbers of successful shopping-choice attempts based on weather,
stock, and wallets. Even resident setup consumes 696 words before day 1.
Traffic's one uniform plus four float draws consume exactly ten words here;
weather's weighted choice and uniform consume four.

## Measurement method and validation

The harness subclasses `random.Random`, overriding **both** `random()` and
`getrandbits(k)` and delegating to their superclass implementations. Counting
both preserves the normal getrandbits-based integer-selection path.

- A CPython `random()` float consumes two 32-bit words.
- `getrandbits(k)` consumes `ceil(k / 32)` words, including each rejection retry.
- Setup and tick wrappers record counter differences without drawing anything.
- Every wrapper also checks that the MT state-index delta modulo 624 equals
  the counted words modulo 624.
- Index deltas alone are insufficient: the residents maximum of 688 words
  crosses an entire 624-word state block, so a modulo delta would report 64.
- Attribution includes callbacks executed inside the wrapped method. Current
  subscribers do not draw randomness.

The counting run matched the ordinary run's **all 90 daily state snapshots,
entire event stream, and final RNG state exactly**. This guards against the
instrumentation accidentally changing `Random` selection behavior.
The unmodified day-90 result was 6 shops open and average wallet $500.88.

## Controlled upstream perturbation

The harness made one change in a second run: immediately **after residents'
day-1 tick**, it called `town.rng.random()` and discarded the result.
No system state was modified by the extra draw. The residents, businesses,
weather, and economy day-1 states were asserted identical in both runs.
The extra call consumed two words.

| Day-1 downstream field | Baseline | One extra discarded resident draw |
|---|---:|---:|
| traffic.commuters | 91 | 90 |
| traffic.congestion | 0.2275 | 0.2250 |
| traffic.accidents_today | 0 | 1 |
| emergency.incidents_today | 2 | 4 |
| emergency.responded | 2 | 4 |
| emergency.avg_response_min | 7.89 | 10.77 |
| emergency.open_incidents | 0 | 0 |

Traffic receives identical economic/resident/weather input, so its change is
direct evidence of shared-stream coupling. Emergency is affected by both
shifted randomness and the changed traffic input; its difference is not
attributed exclusively to RNG position.

## Smallest explicit engine API change

Add a lazy cache on `Town` and a deterministic named-stream accessor.
Sketch only, **not implemented**:

```python
# engine.py imports hashlib and json in addition to random.
# Town.__init__, after storing the integer root seed:
self._rngs = {}

def rng_for(self, name):
    if name not in self._rngs:
        payload = json.dumps(
            ["tinytown-rng-v1", self.seed, name],
            separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")
        stream_seed = int.from_bytes(hashlib.sha256(payload).digest(), "big")
        self._rngs[name] = random.Random(stream_seed)
    return self._rngs[name]
```

Use stable contract names (`weather`, `residents`, etc.), not class names,
import order, Python's process-randomized `hash()`, or seeds drawn from another
RNG. JSON framing avoids ambiguous seed/name concatenations; the version tag
makes a future intentional seeding migration explicit. Reuse the same object
through setup and all ticks; never reseed it daily.

The tick order need not change. Keep the existing `town.rng` temporarily for
legacy plugins if necessary, but migrate every installed stochastic system
together; leaving one on the shared stream is not complete isolation.
An automatic `rng` property keyed by `_current_system` could reduce call-site
edits, but explicit names avoid ambiguity for subscribers and code run outside
the tick loop.

| Owner/system | Required system change |
|---|---|
| Nori/weather | Get `rng = town.rng_for(self.name)` in tick; use it for weighted choices and temperature uniform. |
| Kiwi/residents | Use its named stream for setup's two shuffles, street choice and initial wallet randint, plus tick's shuffle, visit random and shop choices. Both phases must migrate. |
| Sora/economy | Use its named stream for fallback population randint and employment uniform, even though full-town runs currently skip them. |
| Bao/traffic | Use its named stream for the commute uniform and all four accident floats. |
| Kiwi/emergency | Use its named stream for both randints and the response uniform. |
| Nori/businesses | No RNG calls at this revision; no algorithm change needed. |
| Mochi/log and read-only reports | Continue making no RNG draws; do not request or advance a stream just to observe. |

Test fake towns must expose `rng_for(name)`; RNG-state comparisons should
inspect each named stream rather than only `town.rng.getstate()`. Update the
contract's single-RNG rule only after manager approval.

### Migration checks and limits

1. Verify repeated seed/name requests return the same stream object; access
   order and absent unrelated systems must not affect its sequence.
2. Repeat the discarded-resident-draw experiment: with unchanged upstream
   state, weather/traffic/emergency stream states and results must stay equal.
3. Compare repeated complete runs for determinism, and run seeds 1–20 plus 42
   through the existing balance and no-overdraft acceptance tests.
4. Rebaseline exact-seed snapshots deliberately: **named seeding changes the
   current seed-42 trajectory**. It does not preserve the $500.88 result or
   guarantee the existing acceptance targets without measurement.
5. Real data dependencies remain: changing purchases or employment should
   still change traffic. Isolation separates random streams, not causality.
   Rejection sampling and conditional calls still shift later draws *within*
   that system; per-system isolation does not promise per-day isolation.
6. Pin the runtime/algorithm for exact replay and include each cached stream's
   state in future checkpoints. Stable hashing alone does not guarantee that
   every Python release implements higher-level selections identically.

## Reproduction harness

Run the following Python in a `git archive` copy of the pinned main revision
under `$TMPDIR`, using `python3 -B`. No CSV is enabled. The measurement used
`tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])`, ran the archive in a
subprocess, and removed the directory on exit. The cleanup check confirmed
the directory no longer existed. The code below is the complete instrumented
measurement; it prints its JSON report to stdout only.

```python
import copy
import json
import platform
import random
from collections import defaultdict
from statistics import mean
from unittest.mock import patch
import taro.tinytown.engine as engine
from taro.tinytown.run import load_systems

class CountingRandom(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self.words = 0

    def random(self):
        self.words += 2
        return super().random()

    def getrandbits(self, k):
        value = super().getrandbits(k)
        self.words += (k + 31) // 32
        return value

OriginalTown = engine.Town
class MeasuredTown(OriginalTown):
    def __init__(self, seed=42):
        super().__init__(seed)
        self.rng = CountingRandom(seed)

class Probe:
    def __init__(self, system, samples, setup_words, perturb=False):
        self.system = system
        self.name = system.name
        self.samples = samples
        self.setup_words = setup_words
        self.perturb = perturb

    def measure(self, town, method):
        before = town.rng.words
        index = town.rng.getstate()[1][-1]
        getattr(self.system, method)(town)
        used = town.rng.words - before
        assert (town.rng.getstate()[1][-1] - index) % 624 == used % 624
        return used

    def setup(self, town):
        self.setup_words[self.name] = self.measure(town, "setup")

    def tick(self, town):
        self.samples[self.name].append(self.measure(town, "tick"))
        if self.perturb and self.name == "residents" and town.day == 1:
            town.rng.random()  # discard one extra float; no state change

def systems():
    result = load_systems()
    for system in result:
        if system.name == "log":
            system.csv_path = None
    return result

def run(measured=False, perturb=False):
    samples, setup_words, history = defaultdict(list), {}, []
    installed = systems()
    if measured:
        installed = [Probe(s, samples, setup_words, perturb) for s in installed]
    with patch.object(engine, "Town", MeasuredTown if measured else OriginalTown):
        town = engine.run_town(installed, seed=42, days=90,
                              on_day=lambda t: history.append(copy.deepcopy(t.state)))
    return town, history, samples, setup_words

plain, plain_history, _, _ = run()
town, history, samples, setup_words = run(True)
assert plain_history == history
assert plain.events == town.events
assert plain.rng.getstate() == town.rng.getstate()
shifted, shifted_history, _, _ = run(True, True)
assert history[0]["residents"] == shifted_history[0]["residents"]
for name in ("weather", "businesses", "economy"):
    assert history[0][name] == shifted_history[0][name]
print(json.dumps({
    "python": platform.python_version(),
    "implementation": platform.python_implementation(),
    "setup_words": setup_words,
    "tick_words": {name: {"min": min(values), "mean": mean(values),
                         "max": max(values), "sum": sum(values), "ticks": len(values)}
                   for name, values in samples.items()},
    "first_10_ticks": {name: values[:10] for name, values in samples.items()},
    "day1_baseline_traffic": history[0]["traffic"],
    "day1_extra_draw_traffic": shifted_history[0]["traffic"],
    "day1_baseline_emergency": history[0]["emergency"],
    "day1_extra_draw_emergency": shifted_history[0]["emergency"],
    "baseline_day90": {"wallet_cents": history[-1]["residents"]["avg_wallet_cents"],
                       "shops_open": history[-1]["businesses"]["open_count"]},
    "total_words_including_setup": town.rng.words,
    "unmodified_baseline_identical": True
}, indent=2))
```

