"""Fold Post — handmade origami greeting-card microbusiness.

Simulates 90 seeded days of buying card materials and selling finished packs.
Patterns (price-sensitive demand, no-overdraft cash) are inspired by the
paper-store engine on main (`taro.store`); this package is standalone so the
competition can start at $500 and emit a full transaction CSV.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .ledger import Ledger

# --- Economics (documented in README.md) ------------------------------------

BUSINESS_NAME = "Fold Post"
STARTING_BALANCE = 500.0
DEFAULT_SEED = 42
DEFAULT_DAYS = 90

UNIT_COST = 2.50  # paper, envelope, adhesive per finished pack (materials only)
STALL_FEE = 15.00  # daily craft-market / booth pitch fee
CARD_FEE_RATE = 0.029  # card-reader fee as a share of sale revenue
MAX_DAILY_PRODUCTION = 8  # handmade packs one person can finish in a day
LIST_PRICE = 8.00  # reference retail when demand is "normal"
BASE_DAILY_DEMAND = 6.0  # expected packs/day at list price
MAX_DAILY_DEMAND = 18  # hard cap — stall foot traffic is bounded
ELASTICITY = 1.3  # demand falls as price rises above list

# Operator policy (still endogenous: no hardcoded revenue)
DAYS_OF_COVER = 5.0
LOW_STOCK_DAYS = 2.0
PREMIUM = 1.05
DISCOUNT = 0.97
MIN_MARGIN_RATIO = 1.15  # price floor vs materials cost


@dataclass(frozen=True)
class DayReport:
    day: int
    price: float
    restocked: int
    supply_cost: float
    demand: int
    sold: int
    missed_sales: int
    revenue: float
    stock: int
    balance: float


class FoldPost:
    """One-product origami card stand with a recording ledger."""

    def __init__(
        self,
        starting_balance: float = STARTING_BALANCE,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self._ledger = Ledger(starting_balance)
        self._starting_balance = float(starting_balance)
        self._rng = random.Random(seed)
        self._seed = seed
        self._day = 0
        self._stock = 0
        self._price = LIST_PRICE
        self._prior_missed = 0
        self.history: list[DayReport] = []

    @property
    def balance(self) -> float:
        return self._ledger.balance

    @property
    def starting_balance(self) -> float:
        return self._starting_balance

    @property
    def stock(self) -> int:
        return self._stock

    @property
    def day(self) -> int:
        return self._day

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def ledger(self) -> Ledger:
        return self._ledger

    def run(self, days: int = DEFAULT_DAYS) -> float:
        """Simulate ``days`` business days; return final balance."""
        for _ in range(days):
            self.run_day()
        return self.balance

    def run_day(self) -> DayReport:
        self._day += 1
        price = self._choose_price()
        self._price = price

        # Handmade production: materials only, capped by daily capacity.
        want = self._choose_production()
        affordable = self._ledger.max_affordable_units(UNIT_COST)
        units = min(want, affordable, MAX_DAILY_PRODUCTION)
        supply_cost = 0.0
        if units > 0:
            supply_cost = round(units * UNIT_COST, 2)
            self._ledger.debit(self._day, supply_cost, tx_type="materials")
            self._stock += units

        # Stall fee required to open and sell; skip sales if unaffordable.
        opened = False
        if self._ledger.can_afford(STALL_FEE):
            self._ledger.debit(self._day, STALL_FEE, tx_type="stall")
            opened = True

        demand = self._sample_demand(price)
        sold = min(demand, self._stock) if opened else 0
        missed = demand - sold
        revenue = round(sold * price, 2)
        self._stock -= sold
        if revenue > 0:
            self._ledger.credit(self._day, revenue, tx_type="sale")
            card_fee = round(revenue * CARD_FEE_RATE, 2)
            if card_fee > 0:
                self._ledger.debit(self._day, card_fee, tx_type="card_fee")

        self._prior_missed = missed
        report = DayReport(
            day=self._day,
            price=price,
            restocked=units,
            supply_cost=supply_cost,
            demand=demand,
            sold=sold,
            missed_sales=missed,
            revenue=revenue,
            stock=self._stock,
            balance=self._ledger.balance,
        )
        self.history.append(report)
        return report

    def _choose_price(self) -> float:
        floor = round(UNIT_COST * MIN_MARGIN_RATIO, 2)
        thin = self._stock < BASE_DAILY_DEMAND * LOW_STOCK_DAYS
        if self._prior_missed > 0 or thin:
            target = LIST_PRICE * DISCOUNT
        else:
            target = LIST_PRICE * PREMIUM
        return round(max(floor, target), 2)

    def _choose_production(self) -> int:
        target = int(round(BASE_DAILY_DEMAND * DAYS_OF_COVER))
        need = max(0, target - self._stock) + self._prior_missed
        return int(need)

    def _sample_demand(self, price: float) -> int:
        """Price-sensitive demand from the seeded RNG, hard-capped."""
        if price <= 0:
            return 0
        mean = BASE_DAILY_DEMAND * ((LIST_PRICE / price) ** ELASTICITY)
        if mean <= 0:
            return 0
        noise = self._rng.gauss(mean, math.sqrt(mean))
        drawn = max(0, int(round(noise)))
        return min(drawn, MAX_DAILY_DEMAND)
