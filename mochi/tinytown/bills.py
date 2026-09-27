"""Phase 4 taxes and bills, read from town state for the viewer and the map.

Keys (juniper/TINYTOWN.md, Phase 4; all int cents, today's amounts):
- ``residents``/``businesses``: ``taxes_paid_cents``, ``bills_paid_cents`` (treasury-bound
  utilities and licence), ``rent_paid_cents`` and ``arrears_cents`` (the total owed).
- ``residents.in_arrears``: how many people are behind.
- Per entity: ``residents.people[i].arrears_cents`` and ``businesses.shops[id].arrears_cents``.

Totals may also be ``{id: cents}`` dicts. Anything missing or malformed reads as None,
which the viewer and map show as "n/a". Read-only: no writes, no ``town.rng``.
"""

from mochi.tinytown import history

is_number = history.is_number  # int or finite float, never bool

TOTAL_KEYS = ("taxes_paid_cents", "bills_paid_cents", "rent_paid_cents", "arrears_cents", "in_arrears")


def as_dict(value):
    return value if isinstance(value, dict) else {}


def total_cents(value):
    """Cents as a number, or the sum of an ``{id: cents}`` dict; None if unreadable."""
    if is_number(value):
        return value
    if isinstance(value, dict) and all(is_number(v) for v in value.values()):
        return sum(value.values())
    return None


def person_arrears(person):
    value = as_dict(person).get("arrears_cents")
    return value if is_number(value) else None


def shop_arrears(state):
    """``{shop_id: cents or None}``: each shop's own key, else the per-shop totals dict."""
    businesses = as_dict(as_dict(state).get("businesses"))
    per_shop = as_dict(businesses.get("arrears_cents"))
    owed = {}
    for shop_id, shop in as_dict(businesses.get("shops")).items():
        value = as_dict(shop).get("arrears_cents", per_shop.get(shop_id))
        owed[shop_id] = value if is_number(value) else None
    return owed


def _count_behind(values):
    known = [v for v in values if v is not None]
    return sum(1 for v in known if v > 0) if known else None


def residents_behind(residents):
    count = residents.get("in_arrears")
    if is_number(count):
        return count
    people = residents.get("people")
    return _count_behind(person_arrears(p) for p in (people if isinstance(people, list) else []))


def reported(state):
    """True once any Phase 4 key exists; before that the viewer and map draw as they did."""
    state = as_dict(state)
    residents = as_dict(state.get("residents"))
    businesses = as_dict(state.get("businesses"))
    if any(key in part for part in (residents, businesses) for key in TOTAL_KEYS):
        return True
    people = residents.get("people")
    shops = as_dict(businesses.get("shops")).values()
    return any("arrears_cents" in as_dict(x) for x in [*(people if isinstance(people, list) else []), *shops])


def summary(state):
    """Today's taxes, bills and rent paid, and arrears, for residents and shops."""
    state = as_dict(state)
    residents = as_dict(state.get("residents"))
    businesses = as_dict(state.get("businesses"))
    return {
        "resident_taxes": total_cents(residents.get("taxes_paid_cents")),
        "resident_bills": total_cents(residents.get("bills_paid_cents")),
        "resident_rent": total_cents(residents.get("rent_paid_cents")),
        "resident_arrears": total_cents(residents.get("arrears_cents")),
        "residents_behind": residents_behind(residents),
        "shop_taxes": total_cents(businesses.get("taxes_paid_cents")),
        "shop_bills": total_cents(businesses.get("bills_paid_cents")),
        "shop_rent": total_cents(businesses.get("rent_paid_cents")),
        "shop_arrears": total_cents(businesses.get("arrears_cents")),
        "shops_behind": _count_behind(shop_arrears(state).values()),
    }
