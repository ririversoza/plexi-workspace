"""Run the 90-day Strawberry Daifuku Cart simulation and regenerate ledger.csv."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from business import BUSINESS_NAME, DAYS, SEED, SimulationResult, run_simulation
from ledger import format_cents

LEDGER_PATH = Path(__file__).resolve().parent / "ledger.csv"


def growth_percent(result: SimulationResult) -> str:
    growth = Decimal(result.profit_cents) * 100 / Decimal(result.ledger.starting_cents)
    return str(growth.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def summary_lines(result: SimulationResult) -> list[str]:
    days = result.days
    produced = sum(d.produced for d in days)
    sold = sum(d.sold for d in days)
    return [
        f"Business: {BUSINESS_NAME}",
        f"Days simulated: {len(days)} (seed {SEED})",
        f"Days open: {sum(d.is_open for d in days)}",
        f"Pieces made: {produced}",
        f"Pieces sold: {sold}",
        f"Pieces discarded: {produced - sold}",
        f"Missed demand: {sum(d.demand - d.sold for d in days if d.is_open)}",
        f"Ledger transactions: {len(result.ledger.transactions)}",
        f"Starting balance: ${format_cents(result.ledger.starting_cents)}",
        f"Final balance: ${format_cents(result.final_cents)}",
        f"Profit: ${format_cents(result.profit_cents)}",
        f"Growth: {growth_percent(result)}%",
    ]


def main() -> None:
    result = run_simulation(seed=SEED, days=DAYS)
    result.ledger.write_csv(LEDGER_PATH)
    print("\n".join(summary_lines(result)))


if __name__ == "__main__":
    main()
