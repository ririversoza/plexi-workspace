"""Taro's paper-store simulation engine.

Nori (and anyone else) should import from here::

    from taro.store import Store, DayDecisions, DayReport
"""

from .catalog import Product, default_catalog
from .engine import DayDecisions, DayReport, ProductDayReport, Store
from .ledger import InsufficientFundsError, Ledger

__all__ = [
    "DayDecisions",
    "DayReport",
    "InsufficientFundsError",
    "Ledger",
    "Product",
    "ProductDayReport",
    "Store",
    "default_catalog",
]
