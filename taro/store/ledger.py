"""Cash ledger that never spends money the store does not have."""

from __future__ import annotations


class InsufficientFundsError(ValueError):
    """Raised when a debit would push the balance below zero."""


class Ledger:
    """Tracks the store balance in fictional virtual currency."""

    def __init__(self, starting_balance: float = 5000.0) -> None:
        if starting_balance < 0:
            raise ValueError("starting_balance must be >= 0")
        self._balance = float(starting_balance)

    @property
    def balance(self) -> float:
        return self._balance

    def credit(self, amount: float) -> None:
        """Add revenue from sales."""
        if amount < 0:
            raise ValueError("credit amount must be >= 0")
        self._balance += amount

    def can_afford(self, amount: float) -> bool:
        return amount <= self._balance + 1e-9

    def debit(self, amount: float) -> None:
        """Spend on restocking. Refuses to overdraw."""
        if amount < 0:
            raise ValueError("debit amount must be >= 0")
        if not self.can_afford(amount):
            raise InsufficientFundsError(
                f"need {amount:.2f} but balance is {self._balance:.2f}"
            )
        self._balance -= amount

    def max_affordable_units(self, unit_cost: float) -> int:
        """How many units can be bought at ``unit_cost`` without overdrawing."""
        if unit_cost <= 0:
            return 0
        return int(self._balance // unit_cost)
