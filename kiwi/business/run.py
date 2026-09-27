"""Bench & Bell: reproducible, fictional bicycle tune-up business."""
import csv
from pathlib import Path
import random

SEED = 42
DAYS = 90
STARTING_CENTS = 50_000
PRICE_CENTS = 6_900
UNIT_COST_CENTS = 3_000
DAILY_COST_CENTS = 3_500
SETUP_COST_CENTS = 22_000
CAPACITY = 6


class Ledger:
    def __init__(self):
        self.balance = STARTING_CENTS
        self.transactions = []

    def post(self, day, kind, amount):
        if type(day) is not int or not 1 <= day <= DAYS:
            raise ValueError("Day must be an integer from 1 to 90")
        if self.transactions and day < self.transactions[-1][0]:
            raise ValueError("Transactions must be chronological")
        if type(amount) is not int or amount == 0:
            raise ValueError("Amount must be nonzero integer cents")
        if kind not in {"setup", "overhead", "service_cost", "sale"}:
            raise ValueError("Unknown transaction type")
        if (kind == "sale") != (amount > 0):
            raise ValueError("Only sales may credit the account")
        if self.balance + amount < 0:
            raise ValueError("Overdraft refused")
        self.balance += amount
        self.transactions.append((day, kind, amount, self.balance))

    def write(self, path):
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["day", "type", "amount", "balance_after"])
            for day, kind, amount, balance in self.transactions:
                writer.writerow([day, kind, money(amount), money(balance)])


def money(cents):
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def acceptance(price_cents):
    if type(price_cents) is not int or price_cents <= 0:
        raise ValueError("Price must be positive integer cents")
    return min(0.95, 0.80 * (5_500 / price_cents) ** 2)


def simulate(price_cents=PRICE_CENTS):
    probability = acceptance(price_cents)
    rng = random.Random(SEED)
    ledger = Ledger()
    ledger.post(1, "setup", -SETUP_COST_CENTS)
    closed = False
    for day in range(1, DAYS + 1):
        # Draw every day's market even if the business has closed.
        leads = rng.randint(4, 14)
        willing = sum(rng.random() < probability for _ in range(leads))
        if closed or ledger.balance < DAILY_COST_CENTS:
            closed = True
            continue
        ledger.post(day, "overhead", -DAILY_COST_CENTS)
        for _ in range(min(CAPACITY, willing)):
            if ledger.balance < UNIT_COST_CENTS:
                break
            ledger.post(day, "service_cost", -UNIT_COST_CENTS)
            ledger.post(day, "sale", price_cents)
    return ledger


def main():
    ledger = simulate()
    ledger.write(Path(__file__).with_name("ledger.csv"))
    profit = ledger.balance - STARTING_CENTS
    print("Bench & Bell | seed=42 | days=90")
    print(f"Starting balance: ${money(STARTING_CENTS)}")
    print(f"Final balance: ${money(ledger.balance)}")
    print(f"Profit: ${money(profit)}")
    # Starting balance is $500, so percentage rounded to two decimals is profit/500.
    from decimal import Decimal, ROUND_HALF_UP
    growth = (Decimal(profit) * 100 / STARTING_CENTS).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    print(f"Growth: {growth}%")
    print(f"Services sold: {sum(row[1] == 'sale' for row in ledger.transactions)}")


if __name__ == "__main__":
    main()
