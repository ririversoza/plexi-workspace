"""Run a 90-day paper-store simulation and print growth metrics."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# Repo root on path so `taro.store` and `nori.store` import cleanly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from taro.store import DayReport, Store

from nori.store.strategy import GrowthStrategy, NaiveBaseline, Strategy

STARTING_BALANCE = 5000.0
DEFAULT_DAYS = 90
DEFAULT_SEED = 42


@dataclass(frozen=True)
class SimulationResult:
    strategy_name: str
    days: int
    seed: int
    starting_balance: float
    final_balance: float
    reports: tuple[DayReport, ...]

    @property
    def profit(self) -> float:
        return round(self.final_balance - self.starting_balance, 2)

    @property
    def growth_pct(self) -> float:
        if self.starting_balance == 0:
            return 0.0
        return round(100.0 * self.profit / self.starting_balance, 2)


def simulate(
    strategy: Strategy,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    starting_balance: float = STARTING_BALANCE,
) -> SimulationResult:
    """Run ``days`` of simulation under ``strategy`` (deterministic)."""
    store = Store(starting_balance=starting_balance, seed=seed)
    history: list[DayReport] = []
    for _ in range(days):
        decisions = strategy.decide(store, history)
        report = store.run_day(decisions)
        history.append(report)
    return SimulationResult(
        strategy_name=strategy.name,
        days=days,
        seed=seed,
        starting_balance=starting_balance,
        final_balance=store.balance,
        reports=tuple(history),
    )


def format_daily_summary(report: DayReport) -> str:
    sold = sum(line.sold for line in report.products)
    missed = sum(line.missed_sales for line in report.products)
    return (
        f"day {report.day:3d} | bal ${report.balance:9.2f} | "
        f"rev ${report.total_revenue:7.2f} | restock ${report.total_restock_cost:7.2f} | "
        f"sold {sold:4d} | missed {missed:4d}"
    )


def format_final(result: SimulationResult) -> str:
    return (
        f"\n=== {result.strategy_name} | {result.days} days | seed={result.seed} ===\n"
        f"starting: ${result.starting_balance:.2f}\n"
        f"final:    ${result.final_balance:.2f}\n"
        f"profit:   ${result.profit:.2f}\n"
        f"growth:   {result.growth_pct:.2f}% over {result.starting_balance:.0f}\n"
    )


def available_strategies() -> dict[str, Strategy]:
    return {
        "naive": NaiveBaseline(),
        "growth": GrowthStrategy(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        choices=["naive", "growth", "both"],
        default="both",
        help="Which strategy to run (default: both)",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Skip daily lines; print finals only",
    )
    args = parser.parse_args(argv)

    names = (
        ["naive", "growth"] if args.strategy == "both" else [args.strategy]
    )
    strategies = available_strategies()

    for name in names:
        strategy = strategies[name]
        result = simulate(
            strategy, days=args.days, seed=args.seed
        )
        if not args.quiet:
            print(f"\n--- daily summary: {result.strategy_name} ---")
            for report in result.reports:
                print(format_daily_summary(report))
        print(format_final(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
