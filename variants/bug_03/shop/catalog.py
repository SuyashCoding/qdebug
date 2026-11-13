"""Product catalog: the Product record and lookups by SKU, category and text.

All money amounts in this package are integer cents and all weights are
integer grams, so every computation is exact and every repr is deterministic.
"""

from dataclasses import dataclass, replace
from operator import attrgetter


@dataclass(frozen=True)
class Product:
    """A sellable product."""

    sku: str
    name: str
    price: int
    weight: int
    category: str
    taxable: bool = True


class Catalog:
    """An in-memory product catalog keyed by SKU."""

    def __init__(self, products=()):
        self._products = {}
        for product in products:
            self.add(product)

    def __repr__(self):
        return f"Catalog({len(self._products)} products)"

    def __contains__(self, sku):
        return sku in self._products

    def __len__(self):
        return len(self._products)

    def add(self, product):
        """Register a product. SKUs must be unique and prices non-negative."""
        if product.sku in self._products:
            raise ValueError(f"duplicate sku {product.sku!r}")
        if product.price < 0:
            raise ValueError(f"negative price for {product.sku!r}")
        if product.weight < 0:
            raise ValueError(f"negative weight for {product.sku!r}")
        self._products[product.sku] = product

    def get(self, sku):
        """Return the product for sku, raising KeyError if it is unknown."""
        try:
            return self._products[sku]
        except KeyError:
            raise KeyError(f"unknown sku {sku!r}") from None

    def update_price(self, sku, price):
        """Replace the price of sku and return the updated product."""
        if price < 0:
            raise ValueError("price must be non-negative")
        updated = replace(self.get(sku), price=price)
        self._products[sku] = updated
        return updated

    def find_by_category(self, category):
        """Return the products in category, ordered by SKU."""
        found = [p for p in self._products.values() if p.category == category]
        return sorted(found, key=attrgetter("sku"))

    def search(self, text):
        """Case-insensitive substring search over product names, ordered by SKU."""
        needle = text.strip().lower()
        if not needle:
            return []
        found = [p for p in self._products.values() if needle in p.name.lower()]
        return sorted(found, key=attrgetter("sku"))


def default_catalog():
    """The demo catalog used by the examples and the test-suite."""
    return Catalog(
        [
            Product("BOOK-001", "Python Cookbook", 3999, 900, "books"),
            Product("BOOK-002", "Testing Handbook", 2950, 650, "books"),
            Product("PEN-001", "Gel Pen", 199, 15, "office"),
            Product("NOTE-001", "Notebook A5", 549, 220, "office"),
            Product("MUG-001", "Coffee Mug", 1200, 400, "kitchen"),
            Product("KETTLE-01", "Electric Kettle", 4500, 1400, "kitchen"),
            Product("FOOD-001", "Coffee Beans 1kg", 1899, 1000, "grocery", taxable=False),
            Product("FOOD-002", "Green Tea", 799, 250, "grocery", taxable=False),
            Product("GIFT-001", "Gift Card", 2500, 0, "gift", taxable=False),
        ]
    )
