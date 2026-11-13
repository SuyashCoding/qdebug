"""Pricing rules: rounding, quantity discounts, coupons and sales tax."""

import math
from dataclasses import dataclass
from operator import attrgetter

from shop.shipping import EU_COUNTRIES, HOME_COUNTRY

# Sales tax by US state; states not listed use DEFAULT_TAX_RATE.
TAX_RATES = {"CA": 0.0725, "NY": 0.04, "TX": 0.0625, "OR": 0.0}
DEFAULT_TAX_RATE = 0.05
EU_VAT_RATE = 0.20

COUPON_KINDS = ("percent", "fixed", "bundle")


def round_cents(amount):
    """Round a (possibly fractional) amount of cents to an int, halves up."""
    return int(math.floor(amount + 0.5))


def quantity_discount_rate(quantity):
    """Bulk discount rate: 10% from 10 units, 5% from 5 units, otherwise none."""
    if quantity >= 10:
        return 0.10
    if quantity >= 5:
        return 0.05
    return 0.0


def line_total(item):
    """Price of a cart line in cents after its quantity discount."""
    gross = item.unit_price * item.quantity
    rate = quantity_discount_rate(item.quantity)
    return gross - round_cents(gross * rate)


@dataclass(frozen=True)
class Coupon:
    """A discount coupon.

    kind "percent": value is a percentage of the eligible subtotal.
    kind "fixed":   value is an amount in cents, capped at the eligible subtotal.
    kind "bundle":  buy `value` units (any category), get the cheapest one free.
    categories restricts percent/fixed coupons; empty means every category.
    """

    code: str
    kind: str
    value: int = 0
    min_subtotal: int = 0
    categories: tuple = ()


def validate_coupon(coupon):
    """Raise ValueError if coupon is malformed."""
    if not coupon.code:
        raise ValueError("coupon has no code")
    if coupon.kind not in COUPON_KINDS:
        raise ValueError(f"unknown coupon kind {coupon.kind!r}")
    if coupon.value <= 0:
        raise ValueError("coupon value must be positive")
    if coupon.kind == "percent" and coupon.value > 100:
        raise ValueError("percent coupons cannot exceed 100")


def describe_coupon(coupon):
    """Short human readable description of a coupon."""
    if coupon.kind == "percent":
        return f"{coupon.value}% off"
    if coupon.kind == "fixed":
        return f"{coupon.value} cents off"
    return f"buy {coupon.value}, cheapest free"


def eligible_subtotal(coupon, items, catalog):
    """Sum of line totals that the coupon's category filter applies to."""
    total = 0
    for item in items:
        product = catalog.get(item.sku)
        if not coupon.categories or product.category in coupon.categories:
            total += line_total(item)
    return total


def cheapest_units(lines, count):
    """Unit prices of the `count` cheapest units across lines (lines is not modified)."""
    remaining = list(lines)
    remaining.sort(key=attrgetter("unit_price", "sku"))
    prices = []
    for line in remaining:
        take = min(line.quantity, count - len(prices))
        prices.extend([line.unit_price] * take)
        if len(prices) >= count:
            break
    return prices


def coupon_discount(coupon, items, catalog):
    """Discount in cents that coupon grants for the given cart items."""
    base = eligible_subtotal(coupon, items, catalog)
    if base == 0 or base < coupon.min_subtotal:
        return 0
    if coupon.kind == "percent":
        return round_cents(base * coupon.value / 100)
    if coupon.kind == "fixed":
        return min(coupon.value, base)
    if coupon.kind == "bundle":
        units = sum(item.quantity for item in items)
        free = units // coupon.value
        return sum(cheapest_units(items, free))
    raise ValueError(f"unknown coupon kind {coupon.kind!r}")


def tax_rate_for(address):
    """Sales tax / VAT rate for goods shipped to address."""
    if address.country == HOME_COUNTRY:
        return TAX_RATES.get(address.region, DEFAULT_TAX_RATE)
    if address.country in EU_COUNTRIES:
        return EU_VAT_RATE
    return 0.0


def compute_tax(amount, address):
    """Tax in cents on a taxable amount shipped to address."""
    if amount <= 0:
        return 0
    return round_cents(amount * tax_rate_for(address))
