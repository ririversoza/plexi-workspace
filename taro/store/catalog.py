"""Product catalog for the virtual paper store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Product:
    """One sellable paper good on the shelf.

    Attributes:
        sku: Stable product id used in decisions and reports.
        name: Human-readable label.
        unit_cost: Wholesale cost paid when restocking one unit.
        list_price: Default retail price (also the demand baseline).
        price: Current retail price charged to customers.
        stock: Units on hand.
        base_daily_demand: Expected units sold per day at ``list_price``.
    """

    sku: str
    name: str
    unit_cost: float
    list_price: float
    price: float
    stock: int
    base_daily_demand: float

    def __post_init__(self) -> None:
        if self.unit_cost < 0:
            raise ValueError(f"{self.sku}: unit_cost must be >= 0")
        if self.list_price <= 0 or self.price <= 0:
            raise ValueError(f"{self.sku}: prices must be > 0")
        if self.stock < 0:
            raise ValueError(f"{self.sku}: stock must be >= 0")
        if self.base_daily_demand < 0:
            raise ValueError(f"{self.sku}: base_daily_demand must be >= 0")


def default_catalog() -> dict[str, Product]:
    """Starter assortment: printer paper, cardstock, notebooks, sticky notes."""
    products = (
        Product(
            sku="printer-paper",
            name="Printer Paper (ream)",
            unit_cost=3.50,
            list_price=7.00,
            price=7.00,
            stock=120,
            base_daily_demand=18.0,
        ),
        Product(
            sku="cardstock",
            name="Cardstock (pack)",
            unit_cost=4.00,
            list_price=9.50,
            price=9.50,
            stock=60,
            base_daily_demand=8.0,
        ),
        Product(
            sku="notebooks",
            name="Notebooks",
            unit_cost=2.25,
            list_price=5.50,
            price=5.50,
            stock=80,
            base_daily_demand=12.0,
        ),
        Product(
            sku="sticky-notes",
            name="Sticky Notes (pad)",
            unit_cost=0.80,
            list_price=2.25,
            price=2.25,
            stock=200,
            base_daily_demand=25.0,
        ),
    )
    return {product.sku: product for product in products}
