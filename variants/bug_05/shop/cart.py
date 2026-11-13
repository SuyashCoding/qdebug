"""Shopping cart: add, remove and merge line items."""

from dataclasses import dataclass


@dataclass
class LineItem:
    """One cart line: quantity units of sku at unit_price cents each."""

    sku: str
    quantity: int
    unit_price: int


class Cart:
    """A cart of line items priced from a Catalog when they are added."""

    def __init__(self, catalog):
        self.catalog = catalog
        self.items = []

    def __repr__(self):
        return f"Cart({self.items!r})"

    def _find(self, sku):
        for item in self.items:
            if item.sku == sku:
                return item
        return None

    def is_empty(self):
        return not self.items

    def add(self, sku, quantity=1):
        """Add quantity units of sku at the current catalog price."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        product = self.catalog.get(sku)
        existing = self._find(sku)
        if existing is None:
            self.items.append(LineItem(sku, quantity, product.price))
        else:
            existing.quantity += quantity
        return self

    def remove(self, sku, quantity=None):
        """Remove quantity units of sku, or the whole line when quantity is None."""
        existing = self._find(sku)
        if existing is None:
            raise KeyError(f"{sku!r} is not in the cart")
        if quantity is None or quantity >= existing.quantity:
            self.items.remove(existing)
        else:
            existing.quantity -= quantity
        return self

    def merge(self, other):
        """Add every line of other into this cart. other is left unchanged."""
        for item in other.items:
            existing = self._find(item.sku)
            if existing is None:
                self.items.append(LineItem(item.sku, item.quantity, item.unit_price))
            else:
                existing.quantity += item.quantity
        return self

    def clear(self):
        self.items = []
        return self

    def total_quantity(self):
        """Number of units in the cart."""
        return sum(item.quantity for item in self.items)

    def total_weight(self):
        """Shipping weight of the whole cart in grams."""
        weight = 0
        for item in self.items:
            product = self.catalog.get(item.sku)
            weight += product.weight
        return weight
