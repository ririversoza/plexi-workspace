"""Mochi's Strawberry Daifuku Cart: a 90-day, seeded, ledger-backed simulation.

All money is in integer cents. Every assumption below is documented in README.md.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ledger import Ledger

BUSINESS_NAME = "Strawberry Daifuku Cart"
SEED = 42
DAYS = 90
STARTING_CENTS = 500_00

# Prices and costs (cents)
PRICE_CENTS = 375
REFERENCE_PRICE_CENTS = 350
UNIT_COST_CENTS = 130  # strawberry 55 + rice flour/sugar/starch 25 + bean paste 30 + tray/wrap 20
DAILY_PITCH_FEE_CENTS = 35_00  # street-vending pitch + permit, paid each day the cart opens
STARTUP_EQUIPMENT_CENTS = 150_00  # used steamer, cooler, folding table (day 1 only)
CARD_SHARE = 0.70  # share of customers paying by card
CARD_FEE_RATE = 0.026
CARD_FEE_FIXED_CENTS = 15  # per card transaction; one piece per transaction (conservative)

# Demand and capacity
CAPACITY_PER_DAY = 120  # pieces one person can hand-wrap each morning
FOOT_TRAFFIC_CAP = 150  # hard upper bound on daily demand
BASE_DEMAND_WEEKDAY = 55  # pieces/day at the reference price
BASE_DEMAND_WEEKEND = 90
PRICE_ELASTICITY = 1.5
NOISE_LOW, NOISE_HIGH = 0.75, 1.25
RAIN_PROBABILITY = 0.25
RAIN_DEMAND_FACTOR = 0.5

# Production planning
INITIAL_FORECAST_WEEKDAY = 60
INITIAL_FORECAST_WEEKEND = 90
FORECAST_WINDOW = 3
SELL_OUT_BUMP = 1.20
NORMAL_BUFFER = 1.05


@dataclass(frozen=True)
class DayResult:
    day: int
    rainy: bool
    is_open: bool
    produced: int
    demand: int
    sold: int


@dataclass(frozen=True)
class SimulationResult:
    ledger: Ledger
    days: tuple[DayResult, ...]

    @property
    def final_cents(self) -> int:
        return self.ledger.balance_cents

    @property
    def profit_cents(self) -> int:
        return self.final_cents - self.ledger.starting_cents


def is_weekend(day: int) -> bool:
    """Day 1 is a Monday, so days 6 and 7 of each week are Saturday and Sunday."""
    return (day - 1) % 7 >= 5


def expected_demand(day: int, price_cents: int, rainy: bool) -> float:
    base = BASE_DEMAND_WEEKEND if is_weekend(day) else BASE_DEMAND_WEEKDAY
    price_factor = (REFERENCE_PRICE_CENTS / price_cents) ** PRICE_ELASTICITY
    weather = RAIN_DEMAND_FACTOR if rainy else 1.0
    return base * price_factor * weather


def draw_demand(rng: random.Random, day: int, price_cents: int, rainy: bool) -> int:
    noisy = expected_demand(day, price_cents, rainy) * rng.uniform(NOISE_LOW, NOISE_HIGH)
    return max(0, min(FOOT_TRAFFIC_CAP, round(noisy)))


def forecast(history: list[DayResult], weekend: bool, rainy: bool) -> int:
    """Plan production from recent dry-day sales on the same kind of day (weekday/weekend)."""
    same_kind = [d for d in history if d.is_open and is_weekend(d.day) == weekend and not d.rainy]
    if not same_kind:
        guess = INITIAL_FORECAST_WEEKEND if weekend else INITIAL_FORECAST_WEEKDAY
    else:
        recent = same_kind[-FORECAST_WINDOW:]
        avg = sum(d.sold for d in recent) / len(recent)
        sold_out = recent[-1].sold == recent[-1].produced
        guess = avg * (SELL_OUT_BUMP if sold_out else NORMAL_BUFFER)
    if rainy:
        guess *= RAIN_DEMAND_FACTOR
    return round(guess)


def card_fees_cents(sold: int, price_cents: int) -> int:
    card_txns = round(sold * CARD_SHARE)
    return round(card_txns * price_cents * CARD_FEE_RATE) + card_txns * CARD_FEE_FIXED_CENTS


def simulate_day(rng: random.Random, ledger: Ledger, day: int, history: list[DayResult]) -> DayResult:
    rainy = rng.random() < RAIN_PROBABILITY
    demand = draw_demand(rng, day, PRICE_CENTS, rainy)

    if ledger.balance_cents < DAILY_PITCH_FEE_CENTS + UNIT_COST_CENTS:
        return DayResult(day, rainy, False, 0, demand, 0)
    ledger.record(day, "pitch_fee", -DAILY_PITCH_FEE_CENTS)

    affordable = ledger.balance_cents // UNIT_COST_CENTS
    produced = max(0, min(CAPACITY_PER_DAY, affordable, forecast(history, is_weekend(day), rainy)))
    if produced:
        ledger.record(day, "ingredients", -produced * UNIT_COST_CENTS)

    sold = min(demand, produced)  # unsold pieces are discarded at close (perishable)
    if sold:
        ledger.record(day, "sales", sold * PRICE_CENTS)
        ledger.record(day, "card_fees", -card_fees_cents(sold, PRICE_CENTS))
    return DayResult(day, rainy, True, produced, demand, sold)


def run_simulation(seed: int = SEED, days: int = DAYS, starting_cents: int = STARTING_CENTS) -> SimulationResult:
    rng = random.Random(seed)
    ledger = Ledger(starting_cents)
    ledger.record(1, "equipment", -STARTUP_EQUIPMENT_CENTS)
    history: list[DayResult] = []
    for day in range(1, days + 1):
        history.append(simulate_day(rng, ledger, day, history))
    return SimulationResult(ledger, tuple(history))
