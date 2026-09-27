"""Tiny Town economy: population, jobs, shops and the town treasury."""

START_POPULATION = 500
START_EMPLOYMENT_RATE = 0.90
START_TREASURY = 1000.0
SHOPS = 20

DAILY_ARRIVALS = (-2, 3)        # inclusive range of daily population change
EMPLOYMENT_RATE = (0.85, 0.95)  # daily employment rate is drawn from this range
TAX_PER_WORKER = 1.0
TAX_PER_SHOP = 5.0
UPKEEP_PER_RESIDENT = 1.0

DEFAULT_CONDITION = "sun"


class System:
    name = "economy"

    def setup(self, town):
        town.state[self.name] = {
            "population": START_POPULATION,
            "employed": round(START_POPULATION * START_EMPLOYMENT_RATE),
            "treasury": START_TREASURY,
            "shops_open": SHOPS,
        }

    def tick(self, town):
        prev = town.state[self.name]
        weather = town.state.get("weather") or {}
        is_storm = weather.get("condition", DEFAULT_CONDITION) == "storm"

        population = max(0, prev["population"] + town.rng.randint(*DAILY_ARRIVALS))
        employed = min(population, round(population * town.rng.uniform(*EMPLOYMENT_RATE)))
        shops_open = 0 if is_storm else SHOPS
        if is_storm:
            town.emit("shops_closed", reason="storm")

        income = employed * TAX_PER_WORKER + shops_open * TAX_PER_SHOP
        available = prev["treasury"] + income
        upkeep = population * UPKEEP_PER_RESIDENT
        spent = min(upkeep, available)  # no overdraft: never spend money we don't have
        if spent < upkeep:
            town.emit("budget_shortfall", needed=upkeep, spent=spent)

        town.state[self.name] = {
            "population": population,
            "employed": employed,
            "treasury": round(available - spent, 2),
            "shops_open": shops_open,
        }
