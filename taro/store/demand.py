"""Price-sensitive daily customer demand (deterministic)."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import Product

# Higher elasticity → demand falls faster as price rises above list.
DEFAULT_ELASTICITY = 1.25


def expected_demand(product: Product, elasticity: float = DEFAULT_ELASTICITY) -> float:
    """Mean units demanded today given current price vs list price.

    Raising price above ``list_price`` shrinks demand; discounting grows it.
    """
    price_ratio = product.list_price / product.price
    return product.base_daily_demand * (price_ratio**elasticity)


def sample_demand(
    product: Product,
    rng: random.Random,
    elasticity: float = DEFAULT_ELASTICITY,
) -> int:
    """Draw a non-negative integer demand for one product.

    Uses a seeded Gaussian around ``expected_demand`` so the same seed
    always yields the same sales path.
    """
    mean = expected_demand(product, elasticity=elasticity)
    if mean <= 0:
        return 0
    # Variance scales with mean so quiet SKUs stay quiet.
    noise = rng.gauss(mean, math.sqrt(mean))
    return max(0, int(round(noise)))
