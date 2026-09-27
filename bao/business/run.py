"""Spoke & Spanner: a deterministic, cash-funded bicycle tune-up business."""

import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import random


SEED = 42
DAYS = 90
STARTING_CENTS = 50_000
PRICE_CENTS = 7_500
PARTS_CENTS = 1_200
LABOR_CENTS = 2_800
CAPACITY = 6
DAILY_COSTS = (("workspace", 1_200), ("insurance", 500), ("marketing", 800))


def money(cents):
    """Format integer cents without floating-point rounding."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"


@dataclass(frozen=True)
class Transaction:
    day: int
    type: str
    amount: int
    balance_after: int


class Ledger:
    def __init__(self, opening_cents=STARTING_CENTS):
        if type(opening_cents) is not int or opening_cents < 0:
            raise ValueError("Opening cash must be nonnegative integer cents")
        self._balance = opening_cents
        self._transactions = []

    @property
    def balance(self):
        return self._balance

    @property
    def transactions(self):
        return tuple(self._transactions)

    def post(self, day, kind, amount_cents):
        if type(day) is not int or not 1 <= day <= DAYS:
            raise ValueError("Transaction day must be between 1 and 90")
        if type(amount_cents) is not int or amount_cents == 0:
            raise ValueError("Transaction amount must be nonzero integer cents")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("Transaction type is required")
        next_balance = self._balance + amount_cents
        if next_balance < 0:
            raise ValueError("Overdraft refused")
        if self._transactions and day < self._transactions[-1].day:
            raise ValueError("Transaction days must be chronological")
        self._transactions.append(Transaction(day, kind, amount_cents, next_balance))
        self._balance = next_balance

    def write_csv(self, path):
        with Path(path).open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(("day", "type", "amount", "balance_after"))
            for transaction in self.transactions:
                writer.writerow((transaction.day, transaction.type,
                                 money(transaction.amount), money(transaction.balance_after)))


def willing_customers(budgets, price_cents):
    return sum(budget >= price_cents for budget in budgets)


def simulate():
    rng = random.Random(SEED)
    ledger = Ledger()
    ledger.post(1, "tools", -15_000)
    ledger.post(1, "setup_permit", -5_000)
    daily_overhead = sum(cost for _, cost in DAILY_COSTS)
    unit_cost = PARTS_CENTS + LABOR_CENTS
    for day in range(1, DAYS + 1):
        # Draw every day's market even if cash constraints force closure.
        budgets = [rng.randint(4_000, 11_000) for _ in range(rng.randint(3, 9))]
        if ledger.balance < daily_overhead + unit_cost:
            continue
        for kind, cost in DAILY_COSTS:
            ledger.post(day, kind, -cost)
        demand = min(CAPACITY, willing_customers(budgets, PRICE_CENTS))
        for _ in range(demand):
            if ledger.balance < unit_cost:
                break
            ledger.post(day, "parts", -PARTS_CENTS)
            ledger.post(day, "labor", -LABOR_CENTS)
            ledger.post(day, "tune_up_sale", PRICE_CENTS)
    return ledger


def report(ledger):
    profit = ledger.balance - STARTING_CENTS
    # Decimal keeps percentage rounding independent of binary floating point.
    growth = (Decimal(profit) * 100 / STARTING_CENTS).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (f"Business: Spoke & Spanner\n"
            f"Seed: {SEED}\n"
            f"Days: {DAYS}\n"
            f"Starting balance: ${money(STARTING_CENTS)}\n"
            f"Final balance: ${money(ledger.balance)}\n"
            f"Profit: ${money(profit)}\n"
            f"Growth: {growth}%\n")


def main():
    ledger = simulate()
    ledger.write_csv(Path(__file__).with_name("ledger.csv"))
    print(report(ledger), end="")


if __name__ == "__main__":
    main()
