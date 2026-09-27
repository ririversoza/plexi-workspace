"""Load installed Tiny Town systems and run a 90-day simulation.

Works with zero systems installed: still prints 90 daily lines and a final report.
Phase 2 summaries cover residents, wallets, shops, and a shop leaderboard.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# Re-export for callers that import constants from the runner module.
__all__ = [
    "daily_summary",
    "final_report",
    "format_dollars",
    "load_systems",
    "log_counts",
    "main",
    "sales_today",
    "shop_leaderboard",
]


def load_systems() -> List[Any]:
    """Import every catalogued system package; skip anything not installed."""
    loaded: List[Any] = []
    for module_path in SYSTEM_MODULES.values():
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        system_cls = getattr(module, "System", None)
        if system_cls is None:
            continue
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


def main(days: int = DEFAULT_DAYS, seed: int = DEFAULT_SEED) -> Town:
    systems = load_systems()
    units_sold: Dict[str, int] = {}

    def on_day(town: Town) -> None:
        print(daily_summary(town))
        _accumulate_sales(town, units_sold)

    town = run_town(systems, days=days, seed=seed, on_day=on_day)
    print(final_report(town, systems, units_sold=units_sold or None))
    return town


if __name__ == "__main__":
    main()
