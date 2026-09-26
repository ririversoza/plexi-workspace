import csv
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("kiwi_business", Path(__file__).with_name("run.py"))
business = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(business)


class BusinessTests(unittest.TestCase):
    def test_overdraft_is_atomic_and_exact_balance_is_allowed(self):
        ledger = business.Ledger()
        with self.assertRaises(ValueError):
            ledger.post(1, "setup", -50_001)
        self.assertEqual(ledger.balance, 50_000)
        self.assertEqual(ledger.transactions, [])
        ledger.post(1, "setup", -50_000)
        with self.assertRaises(ValueError):
            ledger.post(1, "overhead", -1)
        self.assertEqual(ledger.balance, 0)
        self.assertEqual(len(ledger.transactions), 1)

    def test_determinism(self):
        first, second = business.simulate(), business.simulate()
        self.assertEqual(first.transactions, second.transactions)
        self.assertEqual(first.balance, second.balance)

    def test_reconciliation_and_paid_services(self):
        ledger = business.simulate()
        self.assertEqual(ledger.balance, 50_000 + sum(row[2] for row in ledger.transactions))
        balance = 50_000
        per_day = {}
        for index, (day, kind, amount, after) in enumerate(ledger.transactions):
            balance += amount
            self.assertEqual(balance, after)
            self.assertGreaterEqual(after, 0)
            self.assertTrue(1 <= day <= 90)
            if kind == "sale":
                self.assertEqual(ledger.transactions[index - 1][:3], (day, "service_cost", -3_000))
                per_day[day] = per_day.get(day, 0) + 1
        self.assertTrue(all(count <= 6 for count in per_day.values()))
        self.assertEqual(sum(row[1] == "overhead" for row in ledger.transactions), 90)

    def test_committed_csv_matches_model(self):
        with Path(__file__).with_name("ledger.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        parsed = [(int(row["day"]), row["type"], int(Decimal(row["amount"]) * 100),
                   int(Decimal(row["balance_after"]) * 100)) for row in rows]
        self.assertEqual(parsed, business.simulate().transactions)
        self.assertEqual(parsed[-1][3], 50_000 + sum(row[2] for row in parsed))

    def test_price_sensitivity_and_bad_inputs(self):
        self.assertGreater(business.acceptance(5_500), business.acceptance(6_900))
        self.assertGreater(business.acceptance(6_900), business.acceptance(10_000))
        for price in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                business.simulate(price)
        for day, kind, amount in [(0, "sale", 1), (91, "sale", 1),
                                  (1, "loan", 100), (1, "sale", -1),
                                  (1, "overhead", 1), (1, "sale", 1.5)]:
            with self.assertRaises(ValueError):
                business.Ledger().post(day, kind, amount)

    def test_loss_making_price_never_borrows(self):
        ledger = business.simulate(1)
        self.assertTrue(all(row[3] >= 0 for row in ledger.transactions))
        self.assertLess(sum(row[1] == "overhead" for row in ledger.transactions), 90)


if __name__ == "__main__":
    unittest.main()
