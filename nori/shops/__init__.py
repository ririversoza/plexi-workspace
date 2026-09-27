"""Tiny Town businesses: the six competition storefronts (Nori).

Writes town.state["businesses"]. Stdlib only; never creates its own RNG.
Parameters are copied from each <name>/business/ folder (not imported).
"""

from __future__ import annotations

# --- shop catalog (ids are the Phase 2 contract strings) -------------------

SHOP_IDS = (
    "one-mug-tea",
    "bench-and-bell",
    "spoke-and-spanner",
    "matcha-mile",
    "fold-post",
    "daifuku-cart",
)

# Copied from each competition entry's constants/README. Money is integer cents.
# Service shops (kiwi/bao) listed labor inside unit cost in the competition;
# Phase 2 pays staff via wages_paid, so unit_cost here is parts/materials only.
SHOP_PARAMS = {
    "one-mug-tea": {
        "name": "One Mug Tea",
        "price_cents": 325,       # sora PRICE_CENTS
        "unit_cost_cents": 55,    # sora CUP_COST_CENTS
        "capacity": 150,          # sora CAPACITY
        "overhead_cents": 2500,   # sora PERMIT_CENTS
    },
    "bench-and-bell": {
        "name": "Bench & Bell",
        "price_cents": 6900,      # kiwi PRICE_CENTS
        "unit_cost_cents": 1200,  # kiwi parts $12 (labor moved to wages)
        "capacity": 6,            # kiwi CAPACITY
        "overhead_cents": 3500,   # kiwi DAILY_COST_CENTS
    },
    "spoke-and-spanner": {
        "name": "Spoke & Spanner",
        "price_cents": 7500,      # bao PRICE_CENTS
        "unit_cost_cents": 1200,  # bao PARTS_CENTS (labor moved to wages)
        "capacity": 6,            # bao CAPACITY
        "overhead_cents": 2500,   # bao workspace+insurance+marketing
    },
    "matcha-mile": {
        "name": "Matcha Mile",
        "price_cents": 550,       # nori LIST_PRICE $5.50
        "unit_cost_cents": 180,   # nori UNIT_COST
        "capacity": 24,           # nori MAX_DAILY_DEMAND (daily sell cap)
        "overhead_cents": 3700,   # nori DAILY_OVERHEAD_TOTAL
    },
    "fold-post": {
        "name": "Fold Post",
        "price_cents": 800,       # taro LIST_PRICE $8.00
        "unit_cost_cents": 250,   # taro UNIT_COST
        "capacity": 8,            # taro MAX_DAILY_PRODUCTION
        "overhead_cents": 1500,   # taro STALL_FEE
    },
    "daifuku-cart": {
        "name": "Strawberry Daifuku Cart",
        "price_cents": 375,       # mochi PRICE_CENTS
        "unit_cost_cents": 130,   # mochi UNIT_COST_CENTS
        "capacity": 120,          # mochi CAPACITY_PER_DAY
        "overhead_cents": 3500,   # mochi DAILY_PITCH_FEE_CENTS
    },
}

START_BALANCE_CENTS = 50_000  # $500.00 per shop
STAFF_WAGE_CENTS = 3_000      # $30.00 / staff / day (matches out-of-town wage)

# Weather capacity factors when the shop stays open. Storm forces closed.
WEATHER_AVAILABLE_FACTOR = {
    "sun": 1.0,
    "cloud": 1.0,
    "rain": 0.7,
    "snow": 0.5,
    "storm": 0.0,
}
DEFAULT_CONDITION = "sun"


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def _nonneg_int(value) -> int:
    return value if type(value) is int and value >= 0 else 0


def _purchases_signature(purchases: dict, spent: dict) -> tuple:
    """Stable fingerprint of the residents purchase batch we settle against."""
    keys = sorted(set(purchases) | set(spent) | set(SHOP_IDS))
    return tuple(
        (key, _nonneg_int(purchases.get(key)), _nonneg_int(spent.get(key)))
        for key in keys
    )


def _credit(balance: int, amount: int) -> int:
    if amount <= 0:
        return balance
    return balance + amount


def _debit(balance: int, amount: int) -> tuple[int, int]:
    """Debit up to ``amount`` without overdraft. Returns (new_balance, paid)."""
    if amount <= 0:
        return balance, 0
    paid = min(amount, balance)
    return balance - paid, paid


class System:
    """Six storefronts with no-overdraft ledgers, wages, and one-day sales lag."""

    name = "businesses"

    def __init__(self) -> None:
        self._settled_signature: tuple | None = None
        self._town = None

    def setup(self, town) -> None:
        self._town = town
        self._settled_signature = None
        shops = {}
        pending = {}
        for shop_id in SHOP_IDS:
            params = SHOP_PARAMS[shop_id]
            shops[shop_id] = {
                "name": params["name"],
                "open": True,
                "price_cents": params["price_cents"],
                "available": params["capacity"],
                "balance_cents": START_BALANCE_CENTS,
                "sold_yesterday": 0,
                "staff": [],
            }
            pending[shop_id] = 0
        town.state[self.name] = {
            "shops": shops,
            "wages_paid": {},
            "open_count": len(SHOP_IDS),
            "pending_revenue_cents": pending,
        }
        town.subscribe(self._capture_pending)
        town.emit(
            "businesses_init",
            shops=len(SHOP_IDS),
            start_balance_cents=START_BALANCE_CENTS,
        )

    def tick(self, town) -> None:
        self._town = town
        state = town.state[self.name]
        shops = state["shops"]
        weather = _mapping(town.state.get("weather"))
        condition = weather.get("condition")
        if not isinstance(condition, str) or condition not in WEATHER_AVAILABLE_FACTOR:
            condition = DEFAULT_CONDITION
        residents = _mapping(town.state.get("residents"))
        people = residents.get("people")
        if not isinstance(people, list):
            people = []

        # --- 1. Book pending (yesterday's sales); fall back to residents.purchases
        pending = dict(_mapping(state.get("pending_revenue_cents")))
        purchases = _mapping(residents.get("purchases"))
        spent = _mapping(residents.get("spent_cents"))
        signature = _purchases_signature(purchases, spent)

        if not any(_nonneg_int(v) for v in pending.values()):
            # Fallback only when this purchase batch has not already been settled
            # (avoids double-booking if residents never retick).
            if signature != self._settled_signature:
                pending = self._revenue_from_residents(purchases, spent, shops)
            else:
                pending = {shop_id: 0 for shop_id in SHOP_IDS}

        for shop_id in SHOP_IDS:
            shop = shops[shop_id]
            params = SHOP_PARAMS[shop_id]
            units = _nonneg_int(purchases.get(shop_id))
            revenue = _nonneg_int(pending.get(shop_id))
            if revenue == 0 and units > 0:
                revenue = _nonneg_int(spent.get(shop_id))
                if revenue == 0:
                    revenue = units * shop["price_cents"]

            if revenue > 0 and units == 0:
                price = shop["price_cents"]
                units = (revenue // price) if price else 0
            shop["sold_yesterday"] = units

            balance = shop["balance_cents"]
            balance = _credit(balance, revenue)
            cogs = units * params["unit_cost_cents"]
            balance, cogs_paid = _debit(balance, cogs)
            if cogs_paid < cogs:
                town.emit(
                    "cogs_short",
                    shop_id=shop_id,
                    needed=cogs,
                    paid=cogs_paid,
                )
            shop["balance_cents"] = balance

        self._settled_signature = signature
        state["pending_revenue_cents"] = {shop_id: 0 for shop_id in SHOP_IDS}

        # --- 2. Staff lists from residents.jobs
        staff_by_shop: dict[str, list] = {shop_id: [] for shop_id in SHOP_IDS}
        for person in people:
            if not isinstance(person, dict):
                continue
            job = person.get("job")
            rid = person.get("id")
            if job in staff_by_shop and type(rid) is int:
                staff_by_shop[job].append(rid)
        for shop_id, staff in staff_by_shop.items():
            staff.sort()
            shops[shop_id]["staff"] = staff

        # --- 3. Open / available from weather + overhead affordability
        open_count = 0
        for shop_id in SHOP_IDS:
            shop = shops[shop_id]
            params = SHOP_PARAMS[shop_id]
            factor = WEATHER_AVAILABLE_FACTOR[condition]
            if factor <= 0.0:
                shop["open"] = False
                shop["available"] = 0
                continue

            balance = shop["balance_cents"]
            overhead = params["overhead_cents"]
            if balance < overhead:
                shop["open"] = False
                shop["available"] = 0
                town.emit(
                    "shop_closed",
                    shop_id=shop_id,
                    reason="overhead",
                    needed=overhead,
                    balance=balance,
                )
                continue

            balance, _ = _debit(balance, overhead)
            capacity = params["capacity"]
            available = int(capacity * factor)
            shop["balance_cents"] = balance
            shop["open"] = True
            shop["available"] = available
            open_count += 1

        if condition == "storm":
            town.emit("shops_closed", reason="storm", open_count=0)

        # --- 4. Pay wages (same day; partial OK)
        wages_paid: dict[int, int] = {}
        for shop_id in SHOP_IDS:
            shop = shops[shop_id]
            staff = shop["staff"]
            if not staff:
                continue
            # Pay wages even when closed — staff are still employed.
            needed_each = STAFF_WAGE_CENTS
            balance = shop["balance_cents"]
            for rid in staff:
                paid = min(needed_each, balance)
                balance -= paid
                if paid > 0:
                    wages_paid[rid] = wages_paid.get(rid, 0) + paid
                if paid < needed_each:
                    town.emit(
                        "wages_short",
                        shop_id=shop_id,
                        resident_id=rid,
                        needed=needed_each,
                        paid=paid,
                    )
            shop["balance_cents"] = balance

        state["wages_paid"] = wages_paid
        state["open_count"] = open_count
        town.emit(
            "daily",
            open_count=open_count,
            condition=condition,
            wages_total=sum(wages_paid.values()),
        )

    def _revenue_from_residents(
        self, purchases: dict, spent: dict, shops: dict
    ) -> dict[str, int]:
        pending = {}
        for shop_id in SHOP_IDS:
            units = _nonneg_int(purchases.get(shop_id))
            revenue = _nonneg_int(spent.get(shop_id))
            if revenue == 0 and units > 0:
                revenue = units * shops[shop_id]["price_cents"]
            pending[shop_id] = revenue
        return pending

    def _capture_pending(self, event: dict) -> None:
        """After residents shop, mirror unbooked sales into pending_revenue_cents.

        Residents do not emit; the next system that emits (economy, traffic, …)
        triggers this. Skips batches we already booked this morning so we never
        double-count. Day-90 purchases stay visible here with no day-91 tick.
        """
        town = self._town
        if town is None:
            return
        if event.get("system") == self.name:
            return
        state = town.state.get(self.name)
        if not isinstance(state, dict):
            return
        residents = _mapping(town.state.get("residents"))
        purchases = _mapping(residents.get("purchases"))
        spent = _mapping(residents.get("spent_cents"))
        signature = _purchases_signature(purchases, spent)
        if signature == self._settled_signature:
            return
        shops = _mapping(state.get("shops"))
        for shop_id in SHOP_IDS:
            if shop_id not in shops:
                shops[shop_id] = {"price_cents": SHOP_PARAMS[shop_id]["price_cents"]}
        state["pending_revenue_cents"] = self._revenue_from_residents(
            purchases, spent, shops
        )


__all__ = [
    "System",
    "SHOP_IDS",
    "SHOP_PARAMS",
    "START_BALANCE_CENTS",
    "STAFF_WAGE_CENTS",
    "WEATHER_AVAILABLE_FACTOR",
]
