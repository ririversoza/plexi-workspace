"""Bounded emergency demand with a shared police/fire response pool."""

__all__ = ["System"]

# condition -> (additional fire calls, response travel penalty in minutes)
_WEATHER = {
    "sun": (0, 0),
    "cloud": (0, 0),
    "rain": (1, 2),
    "snow": (1, 4),
    "storm": (3, 6),
}
_CAPACITY = 8
_MAX_ACCIDENTS = 1000


def _section(town, name):
    value = town.state.get(name)
    return value if type(value) is dict else {}


class System:
    """Daily emergency response; all randomness comes from town.rng."""

    name = "emergency"

    def setup(self, town):
        self._backlog = 0
        town.state[self.name] = {
            "incidents_today": 0,
            "responded": 0,
            "avg_response_min": 0.0,
            "open_incidents": 0,
        }

    def tick(self, town):
        accidents = _section(town, "traffic").get("accidents_today", 0)
        if type(accidents) is not int or not 0 <= accidents <= _MAX_ACCIDENTS:
            accidents = 0
        condition = _section(town, "weather").get("condition", "sun")
        if type(condition) is not str or condition not in _WEATHER:
            condition = "sun"
        extra_fires, travel_penalty = _WEATHER[condition]

        # Fixed three RNG calls per tick, even if no incidents are served.
        police_calls = town.rng.randint(0, 3)
        fire_calls = town.rng.randint(0, 1) + extra_fires
        base_response = town.rng.uniform(4.0, 8.0)
        incidents = accidents + police_calls + fire_calls
        backlog_responded = min(self._backlog, _CAPACITY)
        responded = min(incidents, _CAPACITY - backlog_responded)
        served = backlog_responded + responded
        self._backlog += incidents - served
        average = round(base_response + travel_penalty + served / _CAPACITY * 4, 2) if served else 0.0
        town.state[self.name] = {
            "incidents_today": incidents,
            "responded": responded,
            "avg_response_min": average,
            "open_incidents": self._backlog,
        }
        town.emit(
            "emergency_summary",
            police_calls=police_calls,
            fire_calls=fire_calls,
            accident_calls=accidents,
            backlog_responded=backlog_responded,
            **town.state[self.name],
        )
