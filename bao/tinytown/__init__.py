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
PURCHASES_PER_DRIVING_TRIP = 4
ACCIDENT_GROUPS = 4
BUS_CONGESTION_THRESHOLD = 0.6
COMMUTERS_PER_BUS_RIDER = 4
BUS_CAPACITY = 40


class System:
    """Owns traffic state; upstream systems are optional and read-only."""

    name = "traffic"

    def setup(self, town):
        town.state[self.name] = {
            "commuters": 0,
            "congestion": 0.0,
            "accidents_today": 0,
            "bus_running": False,
            "bus_riders": 0,
        }

    def tick(self, town):
        bus_running = town.state.get(self.name, {}).get("congestion", 0.0) > BUS_CONGESTION_THRESHOLD
        shopping_trips = 0
        if "residents" in town.state:
            residents = town.state["residents"]
            employed = sum(
                person.get("job") == "out-of-town"
                for person in residents.get("people", [])
            )
            purchased_units = sum(
                max(0, units) for units in residents.get("purchases", {}).values()
            )
            shopping_trips = purchased_units // PURCHASES_PER_DRIVING_TRIP
        else:
            employed = max(0, town.state.get("economy", {}).get("employed", 0))
        condition = town.state.get("weather", {}).get("condition", "sun")
        capacity_factor, base_risk = WEATHER_EFFECTS.get(
            condition, WEATHER_EFFECTS["sun"]
        )
        commute_rate = town.rng.uniform(MIN_COMMUTE_RATE, MAX_COMMUTE_RATE)
        commuters = int(employed * commute_rate) + shopping_trips
        bus_riders = min(BUS_CAPACITY, commuters // COMMUTERS_PER_BUS_RIDER) if bus_running else 0
        commuters -= bus_riders
        congestion = min(1.0, commuters / (ROAD_CAPACITY * capacity_factor))
        accident_risk = base_risk + congestion * CONGESTION_ACCIDENT_FACTOR
        # Always sample four balanced trip groups, including empty groups.
        accidents = 0
        for group in range(ACCIDENT_GROUPS):
            trips = commuters // ACCIDENT_GROUPS + (group < commuters % ACCIDENT_GROUPS)
            expected_accidents = trips * accident_risk
            rounded = int(expected_accidents)
            rounded += town.rng.random() < expected_accidents - rounded
            accidents += rounded
        town.state[self.name] = {
            "commuters": commuters,
            "congestion": congestion,
            "accidents_today": accidents,
            "bus_running": bus_running,
            "bus_riders": bus_riders,
        }
        town.emit("traffic_daily", **town.state[self.name])
