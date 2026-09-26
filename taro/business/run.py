#!/usr/bin/env python3
"""Run Fold Post for 90 days and regenerate ledger.csv.

Usage (from repo root)::

    python3 taro/business/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from taro.business.business import (  # noqa: E402
    BUSINESS_NAME,
    DEFAULT_DAYS,
    DEFAULT_SEED,
    STARTING_BALANCE,
    FoldPost,
)

LEDGER_CSV = HERE / "ledger.csv"


def format_report(final_balance: float) -> str:
    profit = final_balance - STARTING_BALANCE
    growth_pct = (profit / STARTING_BALANCE) * 100.0
    return (
        f"{BUSINESS_NAME} · seed={DEFAULT_SEED} · days={DEFAULT_DAYS}\n"
        f"Starting balance: ${STARTING_BALANCE:,.2f}\n"
        f"Final balance:    ${final_balance:,.2f}\n"
        f"Profit:           ${profit:,.2f}\n"
        f"Growth:           {growth_pct:.2f}%\n"
    )


def main() -> int:
    shop = FoldPost(starting_balance=STARTING_BALANCE, seed=DEFAULT_SEED)
    final_balance = shop.run(days=DEFAULT_DAYS)
    shop.ledger.write_csv(LEDGER_CSV)
    text = format_report(final_balance)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
