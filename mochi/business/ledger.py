"""Append-only cash ledger in integer cents that refuses overdrafts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class OverdraftError(ValueError):
    """Raised when a transaction would push the balance below zero."""


@dataclass(frozen=True)
class Transaction:
    day: int
    type: str
    amount_cents: int
    balance_after_cents: int


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


class Ledger:
    """Every money movement goes through ``record``; nothing else touches the balance."""

    def __init__(self, starting_cents: int) -> None:
        if starting_cents < 0:
            raise ValueError("starting balance must be >= 0")
        self._starting_cents = starting_cents
        self._balance_cents = starting_cents
        self._transactions: list[Transaction] = []

    @property
    def starting_cents(self) -> int:
        return self._starting_cents

    @property
    def balance_cents(self) -> int:
        return self._balance_cents

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._transactions)

    def record(self, day: int, type_: str, amount_cents: int) -> Transaction:
        """Apply a signed amount (credit > 0, debit < 0). Refuses to overdraw."""
        if amount_cents == 0:
            raise ValueError("zero-amount transactions are not recorded")
        new_balance = self._balance_cents + amount_cents
        if new_balance < 0:
            raise OverdraftError(
                f"day {day} {type_}: {format_cents(amount_cents)} would overdraw "
                f"balance {format_cents(self._balance_cents)}"
            )
        txn = Transaction(day, type_, amount_cents, new_balance)
        self._transactions.append(txn)
        self._balance_cents = new_balance
        return txn

    def write_csv(self, path: Path) -> None:
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["day", "type", "amount", "balance_after"])
            for t in self._transactions:
                writer.writerow(
                    [t.day, t.type, format_cents(t.amount_cents), format_cents(t.balance_after_cents)]
                )
