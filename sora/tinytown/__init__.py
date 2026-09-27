"""Tiny Town economy: population, jobs, shops and the town treasury."""

import math

START_POPULATION = 500
START_EMPLOYMENT_RATE = 0.90
START_TREASURY = 1000.0
SHOPS = 20

DAILY_ARRIVALS = (-2, 3)        # inclusive range of daily population change
EMPLOYMENT_RATE = (0.85, 0.95)  # daily employment rate is drawn from this range
TAX_PER_WORKER = 1.0  # fallback only: conjured income when residents don't report taxes
TAX_PER_SHOP = 5.0    # fallback only: the same for businesses
UPKEEP_PER_RESIDENT = 1.0

# Phase 4: today's int cents paid to the town (arrears paid today included), reported by
# residents and businesses. bills_paid_cents is the treasury-bound share only (utilities,
# licence); rent is reported separately and leaves town.
PAID_KEYS = ("taxes_paid_cents", "bills_paid_cents")

DEFAULT_CONDITION = "sun"

# Public works: funded one at a time, in this order, only from money above the reserve.
PROJECT_RESERVE = 1000.0
PROJECT_INSTALMENT = 20.0
PROJECTS = (("park", 200.0), ("bike lane", 300.0), ("market square", 400.0))


def _read(town, system, key):
    """An int from another system's state, or None if it isn't there."""
    value = (town.state.get(system) or {}).get(key)
    return value if isinstance(value, int) else None


def _cents(value):
    """Cents from an int, or a dict of them (e.g. per shop). Anything else, or negative, is 0."""
    if isinstance(value, dict):
        return sum(_cents(v) for v in value.values())
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _paid(town, system):
    """(tax cents, bill cents) that ``system`` paid the town today; None if it doesn't report them."""
    state = town.state.get(system)
    if not isinstance(state, dict) or not any(key in state for key in PAID_KEYS):
        return None
    return _cents(state.get("taxes_paid_cents")), _cents(state.get("bills_paid_cents"))


def _income(town, employed, shops_open):
    """(tax_income, utility_income) in dollars, rounded to the cent.

    Each source that reports what it paid counts exactly that, so no money is created. A source
    that doesn't falls back to the old conjured formula for its share.
    """
    tax_cents = bill_cents = 0
    conjured = 0.0
    for system, fallback in (("residents", employed * TAX_PER_WORKER), ("businesses", shops_open * TAX_PER_SHOP)):
        paid = _paid(town, system)
        if paid is None:
            conjured += fallback
        else:
            tax_cents += paid[0]
            bill_cents += paid[1]
    # Sum whole cents first and divide once, so 10 + 20 cents is 0.3, not 0.30000000000000004.
    return round(tax_cents / 100 + conjured, 2), round(bill_cents / 100, 2)


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
            "tax_income": 0.0,
            "utility_income": 0.0,
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

        tax_income, utility_income = _income(town, employed, shops_open)
        available = prev["treasury"] + tax_income + utility_income
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
            "tax_income": tax_income,
            "utility_income": utility_income,
        }
