import pytest

from shop.invoice import build_invoice, format_invoice
from shop.pricing import Coupon
from shop.shipping import Address


def test_simple_domestic_invoice(cart, california):
    cart.add("PEN-001", 2).add("NOTE-001")
    invoice = build_invoice(cart, california)
    assert invoice.subtotal == 947
    assert invoice.tax == 69
    assert invoice.shipping == 499
    assert invoice.total == 1515


def test_bulk_invoice_qty_ten(cart):
    cart.add("PEN-001", 10)
    invoice = build_invoice(cart, Address("Tom", "US", "TX"))
    assert invoice.subtotal == 1791
    assert invoice.total == 2402


def test_invoice_with_percent_coupon(cart):
    cart.add("BOOK-001").add("FOOD-001")
    coupon = Coupon("SAVE10", "percent", 10)
    invoice = build_invoice(cart, Address("Nia", "US", "NY"), coupon)
    assert invoice.discount == 590
    assert invoice.tax == 144
    assert invoice.total == 6351


def test_invoice_does_not_modify_cart(cart, california):
    cart.add("MUG-001").add("PEN-001", 2).add("NOTE-001")
    invoice = build_invoice(cart, california, Coupon("B3", "bundle", 3))
    assert invoice.discount == 199
    assert [item.sku for item in cart.items] == ["MUG-001", "PEN-001", "NOTE-001"]


def test_bundle_invoice_is_repeatable(cart, california):
    cart.add("MUG-001").add("PEN-001", 2).add("NOTE-001")
    coupon = Coupon("B3", "bundle", 3)
    first = build_invoice(cart, california, coupon)
    second = build_invoice(cart, california, coupon, number="INV-0002")
    assert [line.sku for line in second.lines] == [line.sku for line in first.lines]


def test_eu_invoice(cart, germany):
    cart.add("KETTLE-01")
    invoice = build_invoice(cart, germany)
    assert invoice.zone == "eu"
    assert invoice.tax == 900
    assert invoice.shipping == 2199
    assert invoice.total == 7599


def test_heavy_remote_invoice(cart):
    cart.add("BOOK-001", 3)
    invoice = build_invoice(cart, Address("Kai", "US", "HI"))
    assert invoice.tax == 600
    assert invoice.shipping == 2999
    assert invoice.total == 15596


def test_free_shipping_hides_weight(cart, california):
    cart.add("KETTLE-01", 3)
    invoice = build_invoice(cart, california)
    assert invoice.shipping == 0
    assert invoice.total == 14479
    assert "free shipping" in invoice.notes


def test_empty_cart_rejected(cart, california):
    with pytest.raises(ValueError):
        build_invoice(cart, california)


def test_format_invoice(cart, california):
    cart.add("PEN-001", 2).add("NOTE-001")
    text = format_invoice(build_invoice(cart, california))
    assert "TOTAL" in text and "$15.15" in text
    assert "ships to domestic zone" in text
