from shop.cart import LineItem
from shop.pricing import (
    Coupon,
    compute_tax,
    coupon_discount,
    line_total,
    quantity_discount_rate,
    round_cents,
    tax_rate_for,
)
from shop.shipping import Address


def test_round_cents():
    assert round_cents(10.5) == 11
    assert round_cents(10.49) == 10
    assert round_cents(-0.5) == 0


def test_quantity_discount_tiers():
    rates = [quantity_discount_rate(q) for q in (1, 4, 5, 9, 12)]
    assert rates == [0.0, 0.0, 0.05, 0.05, 0.10]


def test_line_total_bulk():
    assert line_total(LineItem("PEN-001", 10, 199)) == 1791


def test_percent_coupon_category(catalog, cart):
    cart.add("BOOK-001").add("PEN-001", 2)
    coupon = Coupon("BOOKS15", "percent", 15, categories=("books",))
    assert coupon_discount(coupon, cart.items, catalog) == 600


def test_fixed_coupon_min_subtotal(catalog, cart):
    coupon = Coupon("BIG5", "fixed", 500, min_subtotal=5000)
    cart.add("BOOK-001")
    assert coupon_discount(coupon, cart.items, catalog) == 0
    cart.add("BOOK-002")
    assert coupon_discount(coupon, cart.items, catalog) == 500


def test_bundle_coupon_sorted_cart(catalog, cart):
    cart.add("PEN-001").add("NOTE-001").add("MUG-001")
    coupon = Coupon("B3", "bundle", 3)
    assert coupon_discount(coupon, cart.items, catalog) == 199
    assert [item.sku for item in cart.items] == ["PEN-001", "NOTE-001", "MUG-001"]


def test_compute_tax_us_states(california):
    assert compute_tax(10000, california) == 725
    assert compute_tax(10000, Address("Bo", "US", "OR")) == 0
    assert compute_tax(0, california) == 0


def test_tax_rate_abroad(germany):
    assert tax_rate_for(germany) == 0.20
    assert tax_rate_for(Address("Yuki", "JP")) == 0.0
