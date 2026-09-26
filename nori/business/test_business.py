"""Unit tests for Matcha Mile: no overdraft, determinism, ledger identity."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nori.business.business import (  # noqa: E402
    DEFAULT_DAYS,
    DEFAULT_SEED,
    STARTING_BALANCE,
    UNIT_COST,
    MatchaMile,
)
from nori.business.ledger import InsufficientFundsError, Ledger  # noqa: E402


class LedgerTests(unittest.TestCase):
    def test_refuses_overdraft(self) -> None:
        ledger = Ledger(starting_balance=10.0)
        with self.assertRaises(InsufficientFundsError):
            ledger.debit(day=1, amount=10.01, tx_type="supply")
        self.assertEqual(ledger.balance, 10.0)
        self.assertEqual(ledger.transactions, ())

    def test_debit_and_credit_update_balance(self) -> None:
        ledger = Ledger(starting_balance=100.0)
        ledger.debit(day=1, amount=20.0, tx_type="supply")
        ledger.credit(day=1, amount=35.5, tx_type="sale")
        self.assertEqual(ledger.balance, 115.5)
        self.assertEqual(ledger.transactions[0].amount, -20.0)
        self.assertEqual(ledger.transactions[1].amount, 35.5)


class SimulationTests(unittest.TestCase):
    def test_no_overdraft_across_90_days(self) -> None:
        cart = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        cart.run(days=DEFAULT_DAYS)
        self.assertGreaterEqual(cart.balance, 0.0)
        for tx in cart.ledger.transactions:
            self.assertGreaterEqual(tx.balance_after, 0.0)
        # Restock never exceeds what cash can buy.
        for report in cart.history:
            if report.restocked:
                self.assertLessEqual(
                    report.supply_cost,
                    report.restocked * UNIT_COST + 1e-9,
                )

    def test_determinism(self) -> None:
        a = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        b = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        a.run(days=DEFAULT_DAYS)
        b.run(days=DEFAULT_DAYS)
        self.assertEqual(a.balance, b.balance)
        self.assertEqual(
            [(r.day, r.sold, r.revenue, r.balance) for r in a.history],
            [(r.day, r.sold, r.revenue, r.balance) for r in b.history],
        )
        self.assertEqual(
            [(t.day, t.type, t.amount, t.balance_after) for t in a.ledger.transactions],
            [(t.day, t.type, t.amount, t.balance_after) for t in b.ledger.transactions],
        )

    def test_final_balance_equals_start_plus_ledger_sum(self) -> None:
        cart = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        cart.run(days=DEFAULT_DAYS)
        total = sum(tx.amount for tx in cart.ledger.transactions)
        self.assertAlmostEqual(
            cart.balance,
            STARTING_BALANCE + total,
            places=2,
        )

    def test_exactly_90_days(self) -> None:
        cart = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        cart.run(days=DEFAULT_DAYS)
        self.assertEqual(cart.day, 90)
        self.assertEqual(len(cart.history), 90)

    def test_ledger_csv_roundtrip_fields(self) -> None:
        cart = MatchaMile(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
        cart.run(days=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            cart.ledger.write_csv(path)
            text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("day,type,amount,balance_after\n"))
        self.assertIn("supply", text)
        self.assertIn("sale", text)


if __name__ == "__main__":
    unittest.main()
