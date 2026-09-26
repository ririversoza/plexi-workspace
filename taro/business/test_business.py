"""Unit tests for Fold Post (taro/business)."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from taro.business.business import (
    DEFAULT_DAYS,
    DEFAULT_SEED,
    STARTING_BALANCE,
    UNIT_COST,
    FoldPost,
)
from taro.business.ledger import InsufficientFundsError, Ledger


class LedgerTests(unittest.TestCase):
    def test_debit_refuses_overdraft(self) -> None:
        ledger = Ledger(starting_balance=10.0)
        with self.assertRaises(InsufficientFundsError):
            ledger.debit(day=1, amount=10.01, tx_type="supply")
        self.assertEqual(ledger.balance, 10.0)
        self.assertEqual(ledger.transactions, ())

    def test_signed_amounts_reconcile(self) -> None:
        ledger = Ledger(starting_balance=100.0)
        ledger.debit(day=1, amount=40.0, tx_type="supply")
        ledger.credit(day=1, amount=55.0, tx_type="sale")
        total = sum(tx.amount for tx in ledger.transactions)
        self.assertAlmostEqual(ledger.balance, 100.0 + total, places=2)


class FoldPostTests(unittest.TestCase):
    def test_no_overdraft_across_full_run(self) -> None:
        shop = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        shop.run(days=DEFAULT_DAYS)
        for tx in shop.ledger.transactions:
            self.assertGreaterEqual(tx.balance_after, -1e-9)
            if tx.type == "supply":
                self.assertLessEqual(tx.amount, 0.0)
        self.assertGreaterEqual(shop.balance, 0.0)
        for tx in shop.ledger.transactions:
            if tx.type == "supply" and tx.amount != 0:
                units = abs(tx.amount) / UNIT_COST
                self.assertTrue(math.isclose(units, round(units), abs_tol=1e-9))

    def test_determinism_seed_42(self) -> None:
        a = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        b = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        a.run(days=DEFAULT_DAYS)
        b.run(days=DEFAULT_DAYS)
        self.assertEqual(a.balance, b.balance)
        self.assertEqual(
            [(t.day, t.type, t.amount, t.balance_after) for t in a.ledger.transactions],
            [(t.day, t.type, t.amount, t.balance_after) for t in b.ledger.transactions],
        )
        self.assertEqual(
            [(r.day, r.sold, r.revenue, r.balance) for r in a.history],
            [(r.day, r.sold, r.revenue, r.balance) for r in b.history],
        )

    def test_final_balance_equals_start_plus_ledger_sum(self) -> None:
        shop = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        shop.run(days=DEFAULT_DAYS)
        total = sum(tx.amount for tx in shop.ledger.transactions)
        self.assertAlmostEqual(
            shop.balance,
            STARTING_BALANCE + total,
            places=2,
            msg="final balance == 500 + sum of ledger transactions",
        )

    def test_write_csv_round_trip_header(self) -> None:
        shop = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        shop.run(days=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            shop.ledger.write_csv(path)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("day,type,amount,balance_after\n"))
            self.assertGreater(len(text.splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
