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

# Phase 2 balance amendment: wages only on open days, sustainable vs fixed $30.
# Each open-day staffer gets a small base plus an equal share of a revenue pool.
WAGE_BASE_CENTS = 500         # $5.00 per staffer when the shop is open
WAGE_REVENUE_SHARE_PCT = 20   # 20% of revenue booked this morning, split among staff

# Weather capacity factors when the shop stays open. Storm forces closed.
WEATHER_AVAILABLE_FACTOR = {
    "sun": 1.0,
    "cloud": 1.0,
    "rain": 0.7,
    "snow": 0.5,
    "storm": 0.0,
}
DEFAULT_CONDITION = "sun"

# Systems that tick after residents (or subscribe-only log). Their emits mean
# today's residents.purchases are already written, so we can tag pending by day.
_POST_RESIDENTS_SYSTEMS = frozenset(
    {"residents", "economy", "traffic", "emergency", "log"}
)


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def _nonneg_int(value) -> int:
    return value if type(value) is int and value >= 0 else 0


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


def wage_per_staff(staff_count: int, revenue_booked_cents: int) -> int:
    """Open-day wage for one staffer: base + equal share of the revenue pool."""
    if staff_count <= 0:
        return 0
    pool = (max(0, revenue_booked_cents) * WAGE_REVENUE_SHARE_PCT) // 100
    return WAGE_BASE_CENTS + pool // staff_count


class System:
    """Six storefronts with no-overdraft ledgers, wages, and one-day sales lag."""

    name = "businesses"

    def __init__(self) -> None:
        self._town = None
        # Settlement is keyed by purchase *day*, not by purchase content.
        self._pending_from_day: int | None = None
        self._pending_units: dict[str, int] = {shop_id: 0 for shop_id in SHOP_IDS}
        self._last_settled_day: int | None = None
        # Lifetime revenue credited from settlement (for conservation checks).
        self.revenue_booked_total_cents = 0

    def setup(self, town) -> None:
        self._town = town
        self._pending_from_day = None
        self._pending_units = {shop_id: 0 for shop_id in SHOP_IDS}
        self._last_settled_day = None
        self.revenue_booked_total_cents = 0
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

        # --- 1. Book exactly one unsettled purchase-day (one-day lag)
        pending, units, settled_day = self._batch_to_settle(town, state, shops, residents)
        settled_revenue: dict[str, int] = {shop_id: 0 for shop_id in SHOP_IDS}
        for shop_id in SHOP_IDS:
            shop = shops[shop_id]
            params = SHOP_PARAMS[shop_id]
            revenue = _nonneg_int(pending.get(shop_id))
            sold = _nonneg_int(units.get(shop_id))
            if revenue > 0 and sold == 0:
                price = shop["price_cents"]
                sold = (revenue // price) if price else 0
            shop["sold_yesterday"] = sold
            settled_revenue[shop_id] = revenue

            balance = shop["balance_cents"]
            balance = _credit(balance, revenue)
            if revenue > 0:
                self.revenue_booked_total_cents += revenue
            cogs = sold * params["unit_cost_cents"]
            balance, cogs_paid = _debit(balance, cogs)
            if cogs_paid < cogs:
                town.emit(
                    "cogs_short",
                    shop_id=shop_id,
                    needed=cogs,
                    paid=cogs_paid,
                )
            shop["balance_cents"] = balance

        if settled_day is not None:
            self._last_settled_day = settled_day
        state["pending_revenue_cents"] = {shop_id: 0 for shop_id in SHOP_IDS}
        self._pending_from_day = None
        self._pending_units = {shop_id: 0 for shop_id in SHOP_IDS}

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

        # --- 4. Pay wages only on open days (base + share of booked revenue)
        wages_paid: dict[int, int] = {}
        for shop_id in SHOP_IDS:
            shop = shops[shop_id]
            staff = shop["staff"]
            if not staff or not shop["open"]:
                continue
            needed_each = wage_per_staff(len(staff), settled_revenue[shop_id])
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

    def _batch_to_settle(
        self, town, state: dict, shops: dict, residents: dict
    ) -> tuple[dict[str, int], dict[str, int], int | None]:
        """Return (revenue_by_shop, units_by_shop, purchase_day) to book today.

        Prefers a pending batch captured after residents (tagged by day). Falls
        back to current residents.purchases as yesterday's unsettled day when no
        later system emitted. Never re-books a purchase day already settled.
        """
        empty = {shop_id: 0 for shop_id in SHOP_IDS}
        pending = dict(_mapping(state.get("pending_revenue_cents")))
        if (
            self._pending_from_day is not None
            and self._pending_from_day != self._last_settled_day
        ):
            return pending, dict(self._pending_units), self._pending_from_day

        # Morning fallback: residents still hold yesterday's batch until they tick.
        yday = town.day - 1
        if yday < 1 or yday == self._last_settled_day:
            return empty, empty, None
        purchases = _mapping(residents.get("purchases"))
        spent = _mapping(residents.get("spent_cents"))
        revenue, units = self._revenue_and_units(purchases, spent, shops)
        if not any(revenue.values()):
            # Empty day still counts as settled so we don't re-read it forever.
            return empty, empty, yday
        return revenue, units, yday

    def _revenue_and_units(
        self, purchases: dict, spent: dict, shops: dict
    ) -> tuple[dict[str, int], dict[str, int]]:
        revenue = {}
        units = {}
        for shop_id in SHOP_IDS:
            sold = _nonneg_int(purchases.get(shop_id))
            cents = _nonneg_int(spent.get(shop_id))
            if cents == 0 and sold > 0:
                price = shops.get(shop_id, {}).get("price_cents")
                if type(price) is not int:
                    price = SHOP_PARAMS[shop_id]["price_cents"]
                cents = sold * price
            revenue[shop_id] = cents
            units[shop_id] = sold
        return revenue, units

    def _revenue_from_residents(
        self, purchases: dict, spent: dict, shops: dict
    ) -> dict[str, int]:
        revenue, _ = self._revenue_and_units(purchases, spent, shops)
        return revenue

    def _capture_pending(self, event: dict) -> None:
        """Tag today's residents purchases into pending_revenue_cents by day.

        Runs when a post-residents system emits (residents do not emit themselves).
        Weather emits are ignored: at that point purchases still belong to the
        previous day and are either already pending or booked via morning fallback.
        Day-90 purchases stay visible here with no day-91 tick.
        """
        town = self._town
        if town is None:
            return
        if event.get("system") == self.name:
            return
        if event.get("system") not in _POST_RESIDENTS_SYSTEMS:
            return
        state = town.state.get(self.name)
        if not isinstance(state, dict):
            return
        day = town.day
        if type(day) is not int or day < 1:
            return
        if day == self._last_settled_day:
            return
        residents = _mapping(town.state.get("residents"))
        purchases = _mapping(residents.get("purchases"))
        spent = _mapping(residents.get("spent_cents"))
        shops = _mapping(state.get("shops"))
        for shop_id in SHOP_IDS:
            if shop_id not in shops:
                shops[shop_id] = {"price_cents": SHOP_PARAMS[shop_id]["price_cents"]}
        revenue, units = self._revenue_and_units(purchases, spent, shops)
        state["pending_revenue_cents"] = revenue
        self._pending_units = units
        self._pending_from_day = day


__all__ = [
    "System",
    "SHOP_IDS",
    "SHOP_PARAMS",
    "START_BALANCE_CENTS",
    "WAGE_BASE_CENTS",
    "WAGE_REVENUE_SHARE_PCT",
    "wage_per_staff",
    "WEATHER_AVAILABLE_FACTOR",
]
