"""Daily traffic model using only the town's shared random generator."""

# condition: (fraction of normal road capacity, base accident probability)
WEATHER_EFFECTS = {
    "sun": (1.0, 0.002),
    "cloud": (1.0, 0.002),
    "rain": (0.8, 0.006),
    "snow": (0.6, 0.010),
    "storm": (0.5, 0.015),
}
ROAD_CAPACITY = 500
MIN_COMMUTE_RATE = 0.65
MAX_COMMUTE_RATE = 0.90
CONGESTION_ACCIDENT_FACTOR = 0.01


class System:
    """Owns traffic state; upstream systems are optional and read-only."""

    name = "traffic"

    def setup(self, town):
        town.state[self.name] = {
            "commuters": 0,
            "congestion": 0.0,
            "accidents_today": 0,
        }

    def tick(self, town):
        employed = max(0, town.state.get("economy", {}).get("employed", 0))
        condition = town.state.get("weather", {}).get("condition", "sun")
        capacity_factor, base_risk = WEATHER_EFFECTS.get(
            condition, WEATHER_EFFECTS["sun"]
        )
        commute_rate = town.rng.uniform(MIN_COMMUTE_RATE, MAX_COMMUTE_RATE)
        commuters = int(employed * commute_rate)
        congestion = min(1.0, commuters / (ROAD_CAPACITY * capacity_factor))
        accident_risk = base_risk + congestion * CONGESTION_ACCIDENT_FACTOR
        accidents = sum(town.rng.random() < accident_risk for _ in range(commuters))
        town.state[self.name] = {
            "commuters": commuters,
            "congestion": congestion,
            "accidents_today": accidents,
        }
        town.emit("traffic_daily", **town.state[self.name])
