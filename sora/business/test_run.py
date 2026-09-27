import csv
import tempfile
import unittest
from pathlib import Path

import run


class TestOneMugTea(unittest.TestCase):
    def test_ledger_refuses_overdraft(self):
        ledger = run.Ledger(100)
        with self.assertRaises(run.OverdraftError):
            ledger.record(1, "ingredients", -101)
        self.assertEqual(ledger.balance, 100)
        self.assertEqual(ledger.rows, [])

    def test_balance_never_negative(self):
        for _, _, _, after in run.simulate().rows:
            self.assertGreaterEqual(after, 0)

    def test_deterministic(self):
        self.assertEqual(run.simulate(42).rows, run.simulate(42).rows)

    def test_final_balance_equals_start_plus_transactions(self):
        ledger = run.simulate()
        self.assertEqual(ledger.balance, run.START_CENTS + sum(r[2] for r in ledger.rows))

    def test_csv_reconciles(self):
        ledger = run.simulate()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            run.write_csv(ledger, path)
            with open(path) as f:
                rows = list(csv.DictReader(f))
        total = sum(round(float(r["amount"]) * 100) for r in rows)
        self.assertEqual(run.START_CENTS + total, ledger.balance)
        self.assertEqual(round(float(rows[-1]["balance_after"]) * 100), ledger.balance)
        self.assertEqual(int(rows[-1]["day"]), run.DAYS)


if __name__ == "__main__":
    unittest.main()
