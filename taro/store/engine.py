"""Simulation engine: catalog, ledger, restocking, and daily demand."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping

from .catalog import Product, default_catalog
from .demand import sample_demand
from .ledger import Ledger


@dataclass(frozen=True)
class DayDecisions:
    """Operator choices applied at the start of a simulated day.

    Attributes:
        prices: Map of sku → new retail price. Omitted SKUs keep their price.
        restock: Map of sku → units to buy at ``unit_cost`` before sales open.
    """

    prices: Mapping[str, float] = field(default_factory=dict)
    restock: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductDayReport:
    """Per-product slice of one day's outcome."""

    sku: str
    price: float
    stock: int
    demand: int
    sold: int
    missed_sales: int
    restocked: int
    revenue: float
    restock_cost: float


@dataclass(frozen=True)
class DayReport:
    """Full outcome of ``Store.run_day``."""

    day: int
    opening_balance: float
    balance: float
    total_revenue: float
    total_restock_cost: float
    products: tuple[ProductDayReport, ...]

    def product(self, sku: str) -> ProductDayReport:
        for line in self.products:
            if line.sku == sku:
                return line
        raise KeyError(sku)


class Store:
    """Virtual paper store simulation.

    Day order:
      1. Apply price overrides from ``DayDecisions``.
      2. Attempt restock purchases (never overdraw the ledger).
      3. Sample price-sensitive demand and fulfill from stock.
      4. Credit revenue and return a ``DayReport``.
    """

    DEFAULT_SEED = 42
    DEFAULT_STARTING_BALANCE = 5000.0

    def __init__(
        self,
        starting_balance: float = DEFAULT_STARTING_BALANCE,
        seed: int = DEFAULT_SEED,
        catalog: Mapping[str, Product] | None = None,
    ) -> None:
        source = catalog if catalog is not None else default_catalog()
        # Defensive copy so callers cannot mutate our shelf from outside.
        self._catalog: dict[str, Product] = {
            sku: Product(
                sku=product.sku,
                name=product.name,
                unit_cost=product.unit_cost,
                list_price=product.list_price,
                price=product.price,
                stock=product.stock,
                base_daily_demand=product.base_daily_demand,
            )
            for sku, product in source.items()
        }
        self._ledger = Ledger(starting_balance)
        self._rng = random.Random(seed)
        self._seed = seed
        self._day = 0

    @property
    def balance(self) -> float:
        return self._ledger.balance

    @property
    def day(self) -> int:
        """Number of days already simulated."""
        return self._day

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def catalog(self) -> Mapping[str, Product]:
        """Read-only view of current shelf state."""
        return self._catalog

    def run_day(self, decisions: DayDecisions | None = None) -> DayReport:
        """Simulate one business day and advance the clock."""
        decisions = decisions or DayDecisions()
        opening_balance = self._ledger.balance
        self._day += 1

        self._apply_prices(decisions.prices)
        restocked, restock_costs = self._apply_restock(decisions.restock)

        product_reports: list[ProductDayReport] = []
        total_revenue = 0.0
        total_restock_cost = 0.0

        for sku in sorted(self._catalog):
            product = self._catalog[sku]
            units_restocked = restocked.get(sku, 0)
            cost = restock_costs.get(sku, 0.0)
            total_restock_cost += cost

            demand = sample_demand(product, self._rng)
            sold = min(demand, product.stock)
            missed = demand - sold
            revenue = sold * product.price
            product.stock -= sold
            self._ledger.credit(revenue)
            total_revenue += revenue

            product_reports.append(
                ProductDayReport(
                    sku=sku,
                    price=product.price,
                    stock=product.stock,
                    demand=demand,
                    sold=sold,
                    missed_sales=missed,
                    restocked=units_restocked,
                    revenue=round(revenue, 2),
                    restock_cost=round(cost, 2),
                )
            )

        return DayReport(
            day=self._day,
            opening_balance=round(opening_balance, 2),
            balance=round(self._ledger.balance, 2),
            total_revenue=round(total_revenue, 2),
            total_restock_cost=round(total_restock_cost, 2),
            products=tuple(product_reports),
        )

    def _apply_prices(self, prices: Mapping[str, float]) -> None:
        for sku, price in prices.items():
            product = self._require_product(sku)
            if price <= 0:
                raise ValueError(f"{sku}: price must be > 0")
            product.price = float(price)

    def _apply_restock(
        self, orders: Mapping[str, int]
    ) -> tuple[dict[str, int], dict[str, float]]:
        """Buy as many ordered units as the ledger can afford, SKU order stable."""
        received: dict[str, int] = {}
        costs: dict[str, float] = {}
        for sku in sorted(orders):
            requested = orders[sku]
            if requested < 0:
                raise ValueError(f"{sku}: restock quantity must be >= 0")
            if requested == 0:
                continue
            product = self._require_product(sku)
            affordable = self._ledger.max_affordable_units(product.unit_cost)
            units = min(requested, affordable)
            if units <= 0:
                received[sku] = 0
                costs[sku] = 0.0
                continue
            cost = units * product.unit_cost
            self._ledger.debit(cost)
            product.stock += units
            received[sku] = units
            costs[sku] = cost
        return received, costs

    def _require_product(self, sku: str) -> Product:
        try:
            return self._catalog[sku]
        except KeyError as exc:
            raise KeyError(f"unknown sku: {sku}") from exc
