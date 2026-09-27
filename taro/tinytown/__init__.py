"""Tiny Town engine package (Taro).

Exports the shared ``Town`` world and tick helpers. Other agents provide
``System`` classes in their own ``<name>.tinytown`` packages.
"""

from taro.tinytown.engine import (
    DEFAULT_DAYS,
    DEFAULT_SEED,
    SYSTEM_MODULES,
    TICK_ORDER,
    Town,
    run_town,
)

__all__ = [
    "DEFAULT_DAYS",
    "DEFAULT_SEED",
    "SYSTEM_MODULES",
    "TICK_ORDER",
    "Town",
    "run_town",
]
