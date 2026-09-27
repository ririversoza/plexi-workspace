import csv
from decimal import Decimal
import importlib.util
import io
from pathlib import Path
import sys
import unittest


SPEC = importlib.util.spec_from_file_location("bao_business_run", Path(__file__).with_name("run.py"))
business = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = business
SPEC.loader.exec_module(business)


class BusinessTests(unittest.TestCase):
    def test_overdraft_is_atomic(self):
        ledger = business.Ledger(100)
        with self.assertRaisesRegex(ValueError, "Overdraft"):
            ledger.post(1, "cost", -101)
        self.assertEqual(ledger.balance, 100)
        self.assertEqual(ledger.transactions, ())
        ledger.post(1, "cost", -100)
        self.assertEqual(ledger.balance, 0)
        with self.assertRaisesRegex(ValueError, "Overdraft"):
            ledger.post(2, "cost", -1)
        self.assertEqual(len(ledger.transactions), 1)

    def test_determinism(self):
        first, second = business.simulate(), business.simulate()
        self.assertEqual(first.transactions, second.transactions)
        self.assertEqual(business.report(first), business.report(second))

    def test_ledger_reconciles_every_transaction(self):
        ledger = business.simulate()
        balance = 50_000
        for transaction in ledger.transactions:
            balance += transaction.amount
            self.assertEqual(balance, transaction.balance_after)
            self.assertGreaterEqual(balance, 0)
        self.assertEqual(ledger.balance, 50_000 + sum(t.amount for t in ledger.transactions))

    def test_sales_have_costs_and_daily_capacity(self):
        ledger = business.simulate()
        sales_per_day = {}
        transactions = ledger.transactions
        for index, transaction in enumerate(transactions):
            if transaction.amount > 0:
                self.assertEqual(transaction.type, "tune_up_sale")
                self.assertEqual(transaction.amount, business.PRICE_CENTS)
                parts, labor = transactions[index - 2:index]
                self.assertEqual((parts.type, parts.amount, parts.day),
                                 ("parts", -business.PARTS_CENTS, transaction.day))
                self.assertEqual((labor.type, labor.amount, labor.day),
                                 ("labor", -business.LABOR_CENTS, transaction.day))
                sales_per_day[transaction.day] = sales_per_day.get(transaction.day, 0) + 1
        self.assertTrue(sales_per_day)
        self.assertLessEqual(max(sales_per_day.values()), business.CAPACITY)
        self.assertEqual({t.day for t in transactions}, set(range(1, 91)))

    def test_demand_is_price_sensitive(self):
        budgets = [4_000, 7_500, 11_000]
        self.assertEqual(business.willing_customers(budgets, 4_000), 3)
        self.assertEqual(business.willing_customers(budgets, 7_500), 2)
        self.assertEqual(business.willing_customers(budgets, 11_001), 0)

    def test_committed_artifacts_match_model(self):
        ledger = business.simulate()
        folder = Path(__file__).parent
        self.assertEqual((folder / "RESULTS.md").read_text(), business.report(ledger))
        rows = list(csv.DictReader(io.StringIO((folder / "ledger.csv").read_text())))
        self.assertEqual(len(rows), len(ledger.transactions))
        for row, transaction in zip(rows, ledger.transactions):
            self.assertEqual(row, {"day": str(transaction.day), "type": transaction.type,
                                   "amount": business.money(transaction.amount),
                                   "balance_after": business.money(transaction.balance_after)})
        total = sum(Decimal(row["amount"]) for row in rows)
        self.assertEqual(Decimal(rows[-1]["balance_after"]), Decimal("500.00") + total)


if __name__ == "__main__":
    unittest.main()
