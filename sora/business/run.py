"""One Mug Tea: a single-cart tea stand, simulated for 90 days from $500.

Run: python3 sora/business/run.py
"""
import csv
import random
from pathlib import Path

NAME = "One Mug Tea"
SEED = 42
DAYS = 90
START_CENTS = 500_00

# Assumptions (see README.md). Money is in integer cents.
EQUIPMENT_CENTS = 180_00   # day-1 cart kit: urn, kettle, thermoses, sign
PERMIT_CENTS = 25_00       # daily street-vending permit + pitch fee
CUP_COST_CENTS = 55        # tea, milk, sugar, cup, lid
PRICE_CENTS = 3_25         # sell price per cup
CARD_FEE = 0.029           # card processing, share of revenue
CAPACITY = 150             # cups one urn can serve per day
BASE_DEMAND = 90           # cups/day at the reference price, fair weather weekday
REF_PRICE_CENTS = 3_00
ELASTICITY = 1.8
WEEKEND_BOOST = 1.25
RAIN_CHANCE = 0.2
RAIN_FACTOR = 0.6
BREW_BUFFER = 1.1          # brew 10% over forecast; unsold cups are wasted

LEDGER_PATH = Path(__file__).with_name("ledger.csv")


class OverdraftError(Exception):
    pass


class Ledger:
    def __init__(self, start_cents):
        self.balance = start_cents
        self.rows = []  # (day, type, amount_cents, balance_after_cents)

    def record(self, day, kind, amount):
        if self.balance + amount < 0:
            raise OverdraftError(f"day {day}: {kind} {amount} exceeds balance {self.balance}")
        self.balance += amount
        self.rows.append((day, kind, amount, self.balance))


def expected_demand(day):
    price_factor = (REF_PRICE_CENTS / PRICE_CENTS) ** ELASTICITY
    weekend = WEEKEND_BOOST if day % 7 in (6, 0) else 1.0
    return BASE_DEMAND * price_factor * weekend


def simulate(seed=SEED, days=DAYS):
    rng = random.Random(seed)
    ledger = Ledger(START_CENTS)
    ledger.record(1, "equipment", -EQUIPMENT_CENTS)
    for day in range(1, days + 1):
        ledger.record(day, "permit", -PERMIT_CENTS)

        forecast = expected_demand(day)
        affordable = ledger.balance // CUP_COST_CENTS
        brewed = min(round(forecast * BREW_BUFFER), CAPACITY, affordable)
        if brewed:
            ledger.record(day, "ingredients", -brewed * CUP_COST_CENTS)

        weather = RAIN_FACTOR if rng.random() < RAIN_CHANCE else 1.0
        noise = min(max(rng.gauss(1.0, 0.15), 0.6), 1.4)
        demand = min(max(round(forecast * weather * noise), 0), CAPACITY)
        sold = min(demand, brewed)

        revenue = sold * PRICE_CENTS
        if revenue:
            ledger.record(day, "sales", revenue)
            ledger.record(day, "card_fees", -round(revenue * CARD_FEE))
    return ledger


def dollars(cents):
    return f"{cents / 100:.2f}"


def write_csv(ledger, path=LEDGER_PATH):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "type", "amount", "balance_after"])
        for day, kind, amount, after in ledger.rows:
            w.writerow([day, kind, dollars(amount), dollars(after)])


def main():
    ledger = simulate()
    write_csv(ledger)
    profit = ledger.balance - START_CENTS
    print(f"{NAME}: {DAYS} days, seed {SEED}")
    print(f"Final balance: ${dollars(ledger.balance)}")
    print(f"Profit: ${dollars(profit)}")
    print(f"Growth: {profit / START_CENTS * 100:.2f}%")


if __name__ == "__main__":
    main()
