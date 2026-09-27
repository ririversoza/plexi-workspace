"""Tiny Town economy: population, jobs, shops and the town treasury."""

import math

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

# Public works: funded one at a time, in this order, only from money above the reserve.
PROJECT_RESERVE = 1000.0
PROJECT_INSTALMENT = 20.0
PROJECTS = (("park", 200.0), ("bike lane", 300.0), ("market square", 400.0))


def _read(town, system, key):
    """An int from another system's state, or None if it isn't there."""
    value = (town.state.get(system) or {}).get(key)
    return value if isinstance(value, int) else None


def _public_works(town, prev, treasury):
    """Pay today's instalment. Returns (treasury, project, projects_completed)."""
    project = prev.get("project")
    completed = list(prev.get("projects_completed") or [])
    if project is None:
        remaining = [p for p in PROJECTS if p[0] not in completed]
        if not remaining or treasury <= PROJECT_RESERVE:
            return treasury, None, completed
        name, cost = remaining[0]
        project = {"name": name, "cost": cost, "paid": 0.0, "progress": 0.0}
        town.emit("project_started", name=name, cost=cost)

    # Never below the reserve, so never an overdraft.
    payment = max(0.0, min(PROJECT_INSTALMENT, project["cost"] - project["paid"], treasury - PROJECT_RESERVE))
    paid = round(project["paid"] + payment, 2)
    treasury = round(treasury - payment, 2)
    if paid >= project["cost"]:
        town.emit("project_completed", name=project["name"], cost=project["cost"])
        return treasury, None, completed + [project["name"]]
    progress = math.floor(paid / project["cost"] * 10_000) / 10_000  # floor keeps it < 1 until fully paid
    return treasury, {**project, "paid": paid, "progress": progress}, completed


class System:
    name = "economy"

    def setup(self, town):
        town.state[self.name] = {
            "population": START_POPULATION,
            "employed": round(START_POPULATION * START_EMPLOYMENT_RATE),
            "treasury": START_TREASURY,
            "shops_open": SHOPS,
            "project": None,
            "projects_completed": [],
        }

    def tick(self, town):
        prev = town.state[self.name]
        weather = town.state.get("weather") or {}
        is_storm = weather.get("condition", DEFAULT_CONDITION) == "storm"

        population = _read(town, "residents", "count")
        if population is None:
            population = prev["population"] + town.rng.randint(*DAILY_ARRIVALS)
        population = max(0, population)

        employed = _read(town, "residents", "employed")
        if employed is None:
            employed = round(population * town.rng.uniform(*EMPLOYMENT_RATE))
        employed = max(0, min(population, employed))

        shops_open = _read(town, "businesses", "open_count")
        if shops_open is None:
            shops_open = 0 if is_storm else SHOPS
            if is_storm:
                town.emit("shops_closed", reason="storm")

        income = employed * TAX_PER_WORKER + shops_open * TAX_PER_SHOP
        available = prev["treasury"] + income
        upkeep = population * UPKEEP_PER_RESIDENT
        spent = min(upkeep, available)  # no overdraft: never spend money we don't have
        if spent < upkeep:
            town.emit("budget_shortfall", needed=upkeep, spent=spent)

        treasury, project, completed = _public_works(town, prev, round(available - spent, 2))

        town.state[self.name] = {
            "population": population,
            "employed": employed,
            "treasury": treasury,
            "shops_open": shops_open,
            "project": project,
            "projects_completed": completed,
        }
