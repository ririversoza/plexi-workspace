"""Tests for the paper-store simulation engine."""

from __future__ import annotations

import unittest

from taro.store import DayDecisions, Product, Store, default_catalog
from taro.store.ledger import InsufficientFundsError, Ledger


class LedgerTests(unittest.TestCase):
    def test_starting_balance(self) -> None:
        self.assertEqual(Ledger(5000).balance, 5000.0)

    def test_debit_refuses_overdraft(self) -> None:
        ledger = Ledger(10.0)
        with self.assertRaises(InsufficientFundsError):
            ledger.debit(10.01)
        self.assertEqual(ledger.balance, 10.0)

    def test_max_affordable_units(self) -> None:
        ledger = Ledger(10.0)
        self.assertEqual(ledger.max_affordable_units(3.5), 2)


class StoreTests(unittest.TestCase):
    def test_default_catalog_has_expected_skus(self) -> None:
        skus = set(default_catalog())
        self.assertEqual(
            skus,
            {"printer-paper", "cardstock", "notebooks", "sticky-notes"},
        )

    def test_starts_at_five_thousand(self) -> None:
        store = Store()
        self.assertEqual(store.balance, 5000.0)
        self.assertEqual(store.day, 0)

    def test_run_day_returns_day_report(self) -> None:
        store = Store(seed=42)
        report = store.run_day()
        self.assertEqual(report.day, 1)
        self.assertEqual(store.day, 1)
        self.assertEqual(len(report.products), 4)
        self.assertGreaterEqual(report.balance, 0.0)
        for line in report.products:
            self.assertEqual(line.sold + line.missed_sales, line.demand)
            self.assertGreaterEqual(line.stock, 0)

    def test_deterministic_with_fixed_seed(self) -> None:
        first = Store(seed=42)
        second = Store(seed=42)
        reports_a = [first.run_day() for _ in range(5)]
        reports_b = [second.run_day() for _ in range(5)]
        self.assertEqual(
            [(r.balance, r.total_revenue, tuple(p.sold for p in r.products)) for r in reports_a],
            [(r.balance, r.total_revenue, tuple(p.sold for p in r.products)) for r in reports_b],
        )

    def test_higher_price_reduces_demand(self) -> None:
        cheap = Store(seed=7)
        pricey = Store(seed=7)
        cheap_demand = sum(
            cheap.run_day(DayDecisions(prices={"notebooks": 4.00})).product("notebooks").demand
            for _ in range(20)
        )
        pricey_demand = sum(
            pricey.run_day(DayDecisions(prices={"notebooks": 12.00})).product("notebooks").demand
            for _ in range(20)
        )
        self.assertGreater(cheap_demand, pricey_demand)

    def test_restock_spends_and_increases_stock(self) -> None:
        store = Store(seed=42)
        before = store.catalog["sticky-notes"].stock
        report = store.run_day(DayDecisions(restock={"sticky-notes": 10}))
        line = report.product("sticky-notes")
        self.assertEqual(line.restocked, 10)
        self.assertEqual(line.restock_cost, 8.0)  # 10 * 0.80
        # Stock after sales = before + restocked - sold
        self.assertEqual(line.stock, before + 10 - line.sold)
        self.assertAlmostEqual(
            report.balance,
            5000.0 - line.restock_cost + report.total_revenue,
            places=2,
        )

    def test_restock_never_overdraws(self) -> None:
        # Tiny bankroll: can afford at most one ream of printer paper (3.50).
        tiny = Store(
            starting_balance=3.50,
            seed=42,
            catalog={
                "printer-paper": Product(
                    sku="printer-paper",
                    name="Printer Paper",
                    unit_cost=3.50,
                    list_price=7.00,
                    price=7.00,
                    stock=0,
                    base_daily_demand=0.0,
                )
            },
        )
        report = tiny.run_day(DayDecisions(restock={"printer-paper": 100}))
        line = report.product("printer-paper")
        self.assertEqual(line.restocked, 1)
        self.assertGreaterEqual(report.balance, 0.0)
        self.assertLessEqual(report.total_restock_cost, 3.50)

    def test_unknown_sku_raises(self) -> None:
        store = Store(seed=42)
        with self.assertRaises(KeyError):
            store.run_day(DayDecisions(prices={"glitter-glue": 1.0}))


if __name__ == "__main__":
    unittest.main()
