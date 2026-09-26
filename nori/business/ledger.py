"""Cash ledger that refuses overdrafts and records every money move."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class InsufficientFundsError(ValueError):
    """Raised when a debit would push the balance below zero."""


@dataclass(frozen=True)
class Transaction:
    """One ledger row.

    ``amount`` is signed: credits positive, debits negative. That way
    ``starting_balance + sum(tx.amount)`` equals the final balance.
    """

    day: int
    type: str
    amount: float
    balance_after: float


class Ledger:
    """Tracks balance and an append-only transaction log."""

    def __init__(self, starting_balance: float = 500.0) -> None:
        if starting_balance < 0:
            raise ValueError("starting_balance must be >= 0")
        self._balance = float(starting_balance)
        self._transactions: list[Transaction] = []

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions)

    def can_afford(self, amount: float) -> bool:
        return amount <= self._balance + 1e-9

    def credit(self, day: int, amount: float, tx_type: str = "sale") -> Transaction:
        """Record revenue (positive cash inflow)."""
        if amount < 0:
            raise ValueError("credit amount must be >= 0")
        if amount == 0:
            return Transaction(
                day=day, type=tx_type, amount=0.0, balance_after=self._balance
            )
        self._balance = round(self._balance + amount, 2)
        tx = Transaction(
            day=day,
            type=tx_type,
            amount=round(amount, 2),
            balance_after=self._balance,
        )
        self._transactions.append(tx)
        return tx

    def debit(self, day: int, amount: float, tx_type: str = "supply") -> Transaction:
        """Spend cash. Refuses to overdraw."""
        if amount < 0:
            raise ValueError("debit amount must be >= 0")
        if amount == 0:
            return Transaction(
                day=day, type=tx_type, amount=0.0, balance_after=self._balance
            )
        if not self.can_afford(amount):
            raise InsufficientFundsError(
                f"need {amount:.2f} but balance is {self._balance:.2f}"
            )
        self._balance = round(self._balance - amount, 2)
        tx = Transaction(
            day=day,
            type=tx_type,
            amount=round(-amount, 2),
            balance_after=self._balance,
        )
        self._transactions.append(tx)
        return tx

    def max_affordable_units(self, unit_cost: float) -> int:
        if unit_cost <= 0:
            return 0
        return int(self._balance // unit_cost)

    def write_csv(self, path: Path | str) -> None:
        """Write `day,type,amount,balance_after` rows to ``path``."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["day", "type", "amount", "balance_after"]
            )
            writer.writeheader()
            for tx in self._transactions:
                writer.writerow(
                    {
                        "day": tx.day,
                        "type": tx.type,
                        "amount": f"{tx.amount:.2f}",
                        "balance_after": f"{tx.balance_after:.2f}",
                    }
                )
