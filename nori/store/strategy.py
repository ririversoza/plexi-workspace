"""Restock and pricing strategies for the paper store."""

from __future__ import annotations

import sys
from pathlib import Path

def _ensure_import_paths() -> None:
    """Put this worktree and Taro's sibling worktree on sys.path."""
    here = Path(__file__).resolve()
    for path in (
        here.parents[2],
        here.parents[3] / "taro",
        here.parents[2].parent.parent,
    ):
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


_ensure_import_paths()

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from taro.store import DayDecisions, DayReport, Product, Store


class Strategy(Protocol):
    """Decides prices and restock orders for the next day."""

    name: str

    def decide(self, store: Store, history: list[DayReport]) -> DayDecisions:
        """Return operator decisions given live shelf state and past reports."""


@dataclass
class NaiveBaseline:
    """Do-nothing baseline: keep list prices, never restock."""

    name: str = "naive-baseline"

    def decide(self, store: Store, history: list[DayReport]) -> DayDecisions:
        return DayDecisions()


@dataclass
class GrowthStrategy:
    """Restock toward a days-of-cover target and nudge prices by stock health.

    - When stock is thin or we missed sales, restock toward ``days_of_cover``
      of expected demand and ease price slightly to clear the aisle.
    - When stock is healthy, take a small premium above list price.
    - Prefer higher-margin SKUs when cash is tight (restock map is ordered
      by margin; the engine fills in sorted-sku order, so we cap each order
      to what we can afford in margin-priority passes).
    """

    name: str = "growth-strategy"
    days_of_cover: float = 7.0
    low_stock_days: float = 3.0
    premium: float = 1.06
    discount: float = 0.96
    min_margin_ratio: float = 1.05  # price floor vs unit_cost
    _prior_missed: dict[str, int] = field(default_factory=dict)

    def decide(self, store: Store, history: list[DayReport]) -> DayDecisions:
        if history:
            last = history[-1]
            self._prior_missed = {
                line.sku: line.missed_sales for line in last.products
            }

        prices: dict[str, float] = {}
        desired_restock: dict[str, int] = {}

        for sku, product in store.catalog.items():
            prices[sku] = self._price_for(product)
            qty = self._restock_for(product)
            if qty > 0:
                desired_restock[sku] = qty

        restock = self._affordable_restock(store, desired_restock)
        return DayDecisions(prices=prices, restock=restock)

    def _price_for(self, product: Product) -> float:
        floor = product.unit_cost * self.min_margin_ratio
        missed = self._prior_missed.get(product.sku, 0)
        thin = product.stock < product.base_daily_demand * self.low_stock_days

        if missed > 0 or thin:
            target = product.list_price * self.discount
        else:
            target = product.list_price * self.premium

        return round(max(floor, target), 2)

    def _restock_for(self, product: Product) -> int:
        target = int(round(product.base_daily_demand * self.days_of_cover))
        missed = self._prior_missed.get(product.sku, 0)
        # Cover yesterday's stockouts immediately so growth does not stall.
        need = max(0, target - product.stock) + missed
        return int(need)

    def _affordable_restock(
        self, store: Store, desired: Mapping[str, int]
    ) -> dict[str, int]:
        """Allocate cash to highest unit-margin SKUs first."""
        if not desired:
            return {}

        ranked = sorted(
            desired.items(),
            key=lambda item: store.catalog[item[0]].list_price
            - store.catalog[item[0]].unit_cost,
            reverse=True,
        )

        cash = store.balance
        filled: dict[str, int] = {}
        for sku, want in ranked:
            cost = store.catalog[sku].unit_cost
            if cost <= 0 or want <= 0:
                continue
            can_buy = int(cash // cost)
            units = min(want, can_buy)
            if units <= 0:
                filled[sku] = 0
                continue
            filled[sku] = units
            cash -= units * cost
        return filled
