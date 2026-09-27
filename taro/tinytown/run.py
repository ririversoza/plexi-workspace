"""Load installed Tiny Town systems and run a 90-day simulation.

Works with zero systems installed: still prints 90 daily lines and a final report.
Phase 2 summaries cover residents, wallets, shops, and a shop leaderboard.
Phase 3 adds a small argparse CLI and a multi-seed robustness table.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Allow `python3 taro/tinytown/run.py` from the repo root.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from taro.tinytown.engine import (  # noqa: E402
    DEFAULT_DAYS,
    DEFAULT_SEED,
    SYSTEM_MODULES,
    TICK_ORDER,
    Town,
    run_town,
)

# Phase 2 / 3 acceptance targets (seed-independent thresholds).
MIN_SHOPS_OPEN = 5
MAX_ZERO_STREAK = 3
MAX_AVG_WALLET_CENTS = 600_00  # $600.00

# Re-export for callers that import constants from the runner module.
__all__ = [
    "MAX_AVG_WALLET_CENTS",
    "MAX_ZERO_STREAK",
    "MIN_SHOPS_OPEN",
    "build_parser",
    "cli",
    "daily_summary",
    "evaluate_targets",
    "final_report",
    "format_dollars",
    "format_seeds_table",
    "load_systems",
    "log_counts",
    "main",
    "parse_args",
    "parse_seed_range",
    "run_seed_metrics",
    "run_seeds_report",
    "sales_today",
    "shop_leaderboard",
    "shops_with_balance",
]


def load_systems(*, disable_log_files: bool = False) -> List[Any]:
    """Import every catalogued system package; skip anything not installed.

    When ``disable_log_files`` is true, the log system is constructed with
    ``csv_path=None`` so it never writes ``events.csv`` (used by ``--seeds``).
    """
    loaded: List[Any] = []
    for name, module_path in SYSTEM_MODULES.items():
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        system_cls = getattr(module, "System", None)
        if system_cls is None:
            continue
        if name == "log" and disable_log_files:
            loaded.append(system_cls(csv_path=None))
        else:
            loaded.append(system_cls())
    return loaded


def format_dollars(cents: Any) -> str:
    """Format integer cents as ``$X.YY``; unknown values stay as ``$?``."""
    try:
        value = int(cents)
    except (TypeError, ValueError):
        return "$?"
    sign = "-" if value < 0 else ""
    value = abs(value)
    return f"{sign}${value // 100}.{value % 100:02d}"


def sales_today(town: Town) -> Optional[int]:
    """Units sold today: prefer residents.purchases, else shops' sold_yesterday."""
    residents = town.state.get("residents")
    if residents is not None:
        purchases = residents.get("purchases") or {}
        if isinstance(purchases, dict):
            return sum(int(units) for units in purchases.values())

    businesses = town.state.get("businesses")
    if businesses is not None:
        shops = businesses.get("shops") or {}
        if isinstance(shops, dict):
            total = 0
            for shop in shops.values():
                if isinstance(shop, dict):
                    total += int(shop.get("sold_yesterday") or 0)
            return total
    return None


def daily_summary(town: Town) -> str:
    """One-line snapshot of whatever state is present today."""
    parts: List[str] = [f"Day {town.day}"]
    weather = town.state.get("weather")
    if weather is not None:
        parts.append(
            f"weather={weather.get('condition')} {weather.get('temp_c')}C/{weather.get('season')}"
        )

    residents = town.state.get("residents")
    if residents is not None:
        parts.append(
            f"residents={residents.get('count')} employed={residents.get('employed')} "
            f"avg_wallet={format_dollars(residents.get('avg_wallet_cents'))}"
        )

    businesses = town.state.get("businesses")
    if businesses is not None:
        sales = sales_today(town)
        sales_part = f" sales={sales}" if sales is not None else ""
        parts.append(f"shops_open={businesses.get('open_count')}{sales_part}")

    economy = town.state.get("economy")
    if economy is not None:
        parts.append(
            f"pop={economy.get('population')} employed={economy.get('employed')} "
            f"treasury={economy.get('treasury')} shops={economy.get('shops_open')}"
        )
    traffic = town.state.get("traffic")
    if traffic is not None:
        parts.append(
            f"commuters={traffic.get('commuters')} congestion={traffic.get('congestion')} "
            f"accidents={traffic.get('accidents_today')}"
        )
    emergency = town.state.get("emergency")
    if emergency is not None:
        parts.append(
            f"incidents={emergency.get('incidents_today')} responded={emergency.get('responded')} "
            f"open={emergency.get('open_incidents')}"
        )
    if len(parts) == 1:
        parts.append("(no systems)")
    today_events = sum(1 for event in town.events if event.get("day") == town.day)
    parts.append(f"events={today_events}")
    return " | ".join(parts)


def log_counts(log_state: Any) -> Dict[str, int]:
    """Reduce log state to counts only (no full event lists)."""
    if not isinstance(log_state, dict):
        return {"entries": 0}
    counts: Dict[str, int] = {}
    for key, value in log_state.items():
        if isinstance(value, (list, dict, set, tuple)):
            counts[key] = len(value)
        elif isinstance(value, bool):
            counts[key] = int(value)
        elif isinstance(value, (int, float)):
            counts[key] = int(value)
        elif value is None:
            counts[key] = 0
        else:
            counts[key] = 1
    return counts


def shop_leaderboard(
    town: Town,
    *,
    units_sold: Optional[Dict[str, int]] = None,
) -> List[str]:
    """Rank shops by balance; show balance and units sold."""
    businesses = town.state.get("businesses")
    if not isinstance(businesses, dict):
        return []
    shops = businesses.get("shops")
    if not isinstance(shops, dict) or not shops:
        return []

    rows: List[tuple[str, int, int]] = []
    for shop_id, shop in shops.items():
        if not isinstance(shop, dict):
            continue
        balance = int(shop.get("balance_cents") or 0)
        if units_sold is not None and shop_id in units_sold:
            sold = int(units_sold[shop_id])
        else:
            sold = int(shop.get("sold_yesterday") or 0)
        rows.append((str(shop_id), balance, sold))

    rows.sort(key=lambda row: (-row[1], row[0]))
    lines = ["shop_leaderboard:"]
    for rank, (shop_id, balance, sold) in enumerate(rows, start=1):
        name = ""
        shop = shops.get(shop_id)
        if isinstance(shop, dict) and shop.get("name"):
            name = f" ({shop['name']})"
        lines.append(
            f"  {rank}. {shop_id}{name}: balance={format_dollars(balance)} sold={sold}"
        )
    return lines


def final_report(
    town: Town,
    systems: List[Any],
    *,
    units_sold: Optional[Dict[str, int]] = None,
) -> str:
    """Short end-of-run report: who ran, events, state, and shop leaderboard."""
    names = [system.name for system in systems]
    lines = [
        "=== Tiny Town final report ===",
        f"days={town.day} seed={town.seed} systems={names or '(none)'}",
        f"total_events={len(town.events)}",
    ]
    report_names = list(TICK_ORDER) + ["log"]
    for name in report_names:
        if name not in town.state:
            continue
        if name == "log":
            lines.append(f"log: {log_counts(town.state['log'])}")
        elif name == "businesses":
            # Shops dump is replaced by the leaderboard below.
            businesses = town.state["businesses"]
            summary = {
                key: value
                for key, value in businesses.items()
                if key != "shops"
            }
            summary["shop_count"] = len(businesses.get("shops") or {})
            lines.append(f"businesses: {summary}")
        else:
            lines.append(f"{name}: {town.state[name]}")

    lines.extend(shop_leaderboard(town, units_sold=units_sold))
    return "\n".join(lines)


def _accumulate_sales(town: Town, totals: Dict[str, int]) -> None:
    """Add today's per-shop unit sales into ``totals``."""
    residents = town.state.get("residents")
    if isinstance(residents, dict):
        purchases = residents.get("purchases") or {}
        if isinstance(purchases, dict) and purchases:
            for shop_id, units in purchases.items():
                totals[str(shop_id)] = totals.get(str(shop_id), 0) + int(units)
            return

    businesses = town.state.get("businesses")
    if isinstance(businesses, dict):
        shops = businesses.get("shops") or {}
        if isinstance(shops, dict):
            for shop_id, shop in shops.items():
                if isinstance(shop, dict):
                    totals[str(shop_id)] = totals.get(str(shop_id), 0) + int(
                        shop.get("sold_yesterday") or 0
                    )


def shops_with_balance(town: Town) -> Dict[str, int]:
    """Map shop_id -> balance_cents for every shop present today."""
    businesses = town.state.get("businesses")
    if not isinstance(businesses, dict):
        return {}
    shops = businesses.get("shops")
    if not isinstance(shops, dict):
        return {}
    out: Dict[str, int] = {}
    for shop_id, shop in shops.items():
        if isinstance(shop, dict):
            out[str(shop_id)] = int(shop.get("balance_cents") or 0)
    return out


def _update_zero_streaks(
    balances: Dict[str, int],
    current: Dict[str, int],
    maxima: Dict[str, int],
) -> None:
    """Read-only streak bookkeeping: no town.rng draws."""
    for shop_id, balance in balances.items():
        if balance == 0:
            streak = current.get(shop_id, 0) + 1
            current[shop_id] = streak
            maxima[shop_id] = max(maxima.get(shop_id, 0), streak)
        else:
            current[shop_id] = 0
            maxima.setdefault(shop_id, 0)


def evaluate_targets(
    *,
    shops_open: int,
    max_zero_streak: int,
    avg_wallet_cents: Optional[int],
) -> bool:
    """Phase 2/3 acceptance: open shops, $0 streak, and wallet cap."""
    if shops_open < MIN_SHOPS_OPEN:
        return False
    if max_zero_streak > MAX_ZERO_STREAK:
        return False
    if avg_wallet_cents is None or avg_wallet_cents >= MAX_AVG_WALLET_CENTS:
        return False
    return True


def run_seed_metrics(
    seed: int,
    *,
    days: int = DEFAULT_DAYS,
) -> Dict[str, Any]:
    """Run one quiet seed with log files disabled; return robustness metrics."""
    systems = load_systems(disable_log_files=True)
    units_sold: Dict[str, int] = {}
    zero_current: Dict[str, int] = {}
    zero_max: Dict[str, int] = {}

    def on_day(town: Town) -> None:
        _accumulate_sales(town, units_sold)
        _update_zero_streaks(shops_with_balance(town), zero_current, zero_max)

    town = run_town(systems, days=days, seed=seed, on_day=on_day)
    balances = shops_with_balance(town)
    shops_open = sum(1 for balance in balances.values() if balance > 0)
    max_zero = max(zero_max.values()) if zero_max else 0
    residents = town.state.get("residents") if isinstance(town.state.get("residents"), dict) else None
    avg_wallet = None
    if residents is not None and residents.get("avg_wallet_cents") is not None:
        avg_wallet = int(residents["avg_wallet_cents"])
    economy = town.state.get("economy") if isinstance(town.state.get("economy"), dict) else None
    treasury = economy.get("treasury") if economy is not None else None
    passed = evaluate_targets(
        shops_open=shops_open,
        max_zero_streak=max_zero,
        avg_wallet_cents=avg_wallet,
    )
    return {
        "seed": seed,
        "shops_open": shops_open,
        "max_zero_streak": max_zero,
        "avg_wallet_cents": avg_wallet,
        "treasury": treasury,
        "pass": passed,
        "town": town,
        "systems": systems,
        "units_sold": units_sold,
        "zero_max_by_shop": dict(zero_max),
    }


def format_seeds_table(rows: Sequence[Dict[str, Any]]) -> str:
    """Render the robustness table plus ``X of N seeds pass``."""
    header = (
        f"{'seed':>4}  {'shops':>5}  {'max_$0':>6}  "
        f"{'avg_wallet':>10}  {'treasury':>10}  result"
    )
    lines = [header]
    passed = 0
    for row in rows:
        if row.get("pass"):
            passed += 1
        wallet = row.get("avg_wallet_cents")
        wallet_s = format_dollars(wallet) if wallet is not None else "?"
        treasury = row.get("treasury")
        treasury_s = "?" if treasury is None else str(treasury)
        result = "PASS" if row.get("pass") else "FAIL"
        lines.append(
            f"{int(row['seed']):>4}  {int(row['shops_open']):>5}  "
            f"{int(row['max_zero_streak']):>6}  {wallet_s:>10}  "
            f"{treasury_s:>10}  {result}"
        )
    total = len(rows)
    lines.append(f"{passed} of {total} seeds pass")
    return "\n".join(lines)


def run_seeds_report(
    seeds: Iterable[int],
    *,
    days: int = DEFAULT_DAYS,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Run each seed quietly and return (table_text, row_dicts)."""
    rows = [run_seed_metrics(seed, days=days) for seed in seeds]
    # Drop heavy objects before returning rows for callers that only need metrics.
    slim = [
        {
            "seed": row["seed"],
            "shops_open": row["shops_open"],
            "max_zero_streak": row["max_zero_streak"],
            "avg_wallet_cents": row["avg_wallet_cents"],
            "treasury": row["treasury"],
            "pass": row["pass"],
            "zero_max_by_shop": row["zero_max_by_shop"],
        }
        for row in rows
    ]
    return format_seeds_table(slim), slim


def main(
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    *,
    quiet: bool = False,
) -> Town:
    """Run the town. Default (quiet=False) prints every daily line + final report."""
    systems = load_systems()
    units_sold: Dict[str, int] = {}

    def on_day(town: Town) -> None:
        if not quiet:
            print(daily_summary(town))
        _accumulate_sales(town, units_sold)

    town = run_town(systems, days=days, seed=seed, on_day=on_day)
    print(final_report(town, systems, units_sold=units_sold or None))
    return town


def parse_seed_range(text: str) -> range:
    """Parse ``A-B`` into an inclusive ``range(A, B+1)``."""
    if "-" not in text:
        raise argparse.ArgumentTypeError(
            f"expected A-B seed range, got {text!r}"
        )
    left, right = text.split("-", 1)
    try:
        start = int(left)
        end = int(right)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected integer seed range A-B, got {text!r}"
        ) from exc
    if end < start:
        raise argparse.ArgumentTypeError(
            f"seed range end must be >= start, got {text!r}"
        )
    return range(start, end + 1)


def build_parser() -> argparse.ArgumentParser:
    """Argparse for ``python3 -m taro.tinytown.run``."""
    parser = argparse.ArgumentParser(
        prog="taro.tinytown.run",
        description="Run the Tiny Town simulation (Taro engine).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        metavar="N",
        help=f"RNG seed (default {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        metavar="N",
        help=f"days to simulate (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print the final report only (no daily lines)",
    )
    parser.add_argument(
        "--seeds",
        type=parse_seed_range,
        default=None,
        metavar="A-B",
        help="run each seed quietly and print a robustness table",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI argv (None → sys.argv[1:])."""
    return build_parser().parse_args(argv)


def cli(argv: Optional[Sequence[str]] = None) -> Any:
    """CLI entry: default argv preserves today's plain-run stdout."""
    args = parse_args(argv)
    if args.seeds is not None:
        table, rows = run_seeds_report(args.seeds, days=args.days)
        print(table)
        return rows
    return main(days=args.days, seed=args.seed, quiet=args.quiet)


if __name__ == "__main__":
    cli()
