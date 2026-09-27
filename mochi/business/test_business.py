import csv
import random
import tempfile
import unittest
from pathlib import Path

import business
from business import DAYS, STARTING_CENTS, run_simulation
from ledger import Ledger, OverdraftError


class LedgerTest(unittest.TestCase):
    def test_refuses_overdraft_and_leaves_balance_unchanged(self):
        ledger = Ledger(10_00)
        with self.assertRaises(OverdraftError):
            ledger.record(1, "ingredients", -10_01)
        self.assertEqual(ledger.balance_cents, 10_00)
        self.assertEqual(ledger.transactions, ())

    def test_allows_spending_to_exactly_zero(self):
        ledger = Ledger(10_00)
        ledger.record(1, "ingredients", -10_00)
        self.assertEqual(ledger.balance_cents, 0)

    def test_csv_has_required_columns(self):
        ledger = Ledger(5_00)
        ledger.record(1, "sales", 3_75)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            ledger.write_csv(path)
            with path.open() as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows, [["day", "type", "amount", "balance_after"], ["1", "sales", "3.75", "8.75"]])


class SimulationTest(unittest.TestCase):
    def setUp(self):
        self.result = run_simulation()

    def test_runs_exactly_90_days_from_500(self):
        self.assertEqual(len(self.result.days), DAYS)
        self.assertEqual(self.result.ledger.starting_cents, STARTING_CENTS)

    def test_no_overdraft_ever(self):
        self.assertTrue(all(t.balance_after_cents >= 0 for t in self.result.ledger.transactions))

    def test_no_overdraft_when_nearly_broke(self):
        poor = run_simulation(starting_cents=160_00)
        self.assertTrue(all(t.balance_after_cents >= 0 for t in poor.ledger.transactions))

    def test_deterministic_with_same_seed(self):
        again = run_simulation()
        self.assertEqual(again.ledger.transactions, self.result.ledger.transactions)
        self.assertEqual(again.final_cents, self.result.final_cents)

    def test_different_seed_changes_outcome(self):
        self.assertNotEqual(run_simulation(seed=7).final_cents, self.result.final_cents)

    def test_final_balance_equals_start_plus_sum_of_transactions(self):
        total = sum(t.amount_cents for t in self.result.ledger.transactions)
        self.assertEqual(self.result.final_cents, STARTING_CENTS + total)

    def test_balance_after_chains_through_every_transaction(self):
        balance = STARTING_CENTS
        for t in self.result.ledger.transactions:
            balance += t.amount_cents
            self.assertEqual(t.balance_after_cents, balance)

    def test_never_sells_more_than_made_or_demanded(self):
        for d in self.result.days:
            self.assertLessEqual(d.sold, d.produced)
            self.assertLessEqual(d.sold, d.demand)
            self.assertLessEqual(d.produced, business.CAPACITY_PER_DAY)

    def test_every_sale_has_ingredient_cost(self):
        for day in self.result.days:
            txns = [t for t in self.result.ledger.transactions if t.day == day.day]
            ingredients = -sum(t.amount_cents for t in txns if t.type == "ingredients")
            self.assertGreaterEqual(ingredients, day.sold * business.UNIT_COST_CENTS)


class DemandTest(unittest.TestCase):
    def test_higher_price_lowers_expected_demand(self):
        self.assertGreater(business.expected_demand(1, 300, False), business.expected_demand(1, 500, False))

    def test_demand_is_bounded(self):
        rng = random.Random(0)
        for day in range(1, 200):
            d = business.draw_demand(rng, day, 1, False)  # absurdly low price still caps
            self.assertGreaterEqual(d, 0)
            self.assertLessEqual(d, business.FOOT_TRAFFIC_CAP)


if __name__ == "__main__":
    unittest.main()
