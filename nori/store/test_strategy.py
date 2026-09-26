"""Tests for Nori growth strategies (deterministic)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from nori.store.runner import STARTING_BALANCE, simulate
from nori.store.strategy import GrowthStrategy, NaiveBaseline
from taro.store import DayDecisions, Store


class StrategyTests(unittest.TestCase):
    def test_naive_returns_empty_decisions(self) -> None:
        store = Store(seed=42)
        decisions = NaiveBaseline().decide(store, [])
        self.assertEqual(decisions.prices, {})
        self.assertEqual(decisions.restock, {})

    def test_growth_sets_prices_and_may_restock(self) -> None:
        store = Store(seed=42)
        decisions = GrowthStrategy().decide(store, [])
        self.assertTrue(decisions.prices)
        for sku in store.catalog:
            self.assertIn(sku, decisions.prices)
            self.assertGreater(decisions.prices[sku], 0)

    def test_growth_reacts_to_missed_sales(self) -> None:
        store = Store(seed=42)
        # Burn down stock with naive days so stockouts appear.
        history = []
        for _ in range(15):
            history.append(store.run_day(DayDecisions()))
        decisions = GrowthStrategy().decide(store, history)
        # After stockouts we should request some restock.
        self.assertTrue(
            any(qty > 0 for qty in decisions.restock.values()),
            msg=f"expected restock after stockouts, got {decisions.restock}",
        )

    def test_simulate_is_deterministic(self) -> None:
        a = simulate(GrowthStrategy(), days=30, seed=42)
        b = simulate(GrowthStrategy(), days=30, seed=42)
        self.assertEqual(a.final_balance, b.final_balance)
        self.assertEqual(
            [r.total_revenue for r in a.reports],
            [r.total_revenue for r in b.reports],
        )

    def test_growth_beats_naive_over_90_days(self) -> None:
        naive = simulate(NaiveBaseline(), days=90, seed=42)
        growth = simulate(GrowthStrategy(), days=90, seed=42)
        self.assertGreater(growth.final_balance, naive.final_balance)
        self.assertGreater(growth.final_balance, STARTING_BALANCE)

    def test_growth_pct_math(self) -> None:
        result = simulate(NaiveBaseline(), days=5, seed=42)
        expected = round(
            100.0
            * (result.final_balance - STARTING_BALANCE)
            / STARTING_BALANCE,
            2,
        )
        self.assertEqual(result.growth_pct, expected)


if __name__ == "__main__":
    unittest.main()
