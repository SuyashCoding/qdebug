import pytest

from shop.cart import Cart, LineItem


def test_add_accumulates_quantity(cart):
    cart.add("PEN-001", 2).add("PEN-001", 3)
    assert cart.items == [LineItem("PEN-001", 5, 199)]


def test_add_rejects_non_positive(cart):
    with pytest.raises(ValueError):
        cart.add("PEN-001", 0)


def test_remove_partial_and_all(cart):
    cart.add("PEN-001", 4).add("MUG-001")
    cart.remove("PEN-001", 1)
    assert cart.items[0].quantity == 3
    cart.remove("PEN-001")
    assert [item.sku for item in cart.items] == ["MUG-001"]


def test_merge_leaves_other_unchanged(catalog, cart):
    other = Cart(catalog).add("PEN-001", 2).add("BOOK-001")
    cart.add("PEN-001", 1)
    cart.merge(other)
    cart.add("BOOK-001")
    assert cart.items == [LineItem("PEN-001", 3, 199), LineItem("BOOK-001", 2, 3999)]
    assert other.items == [LineItem("PEN-001", 2, 199), LineItem("BOOK-001", 1, 3999)]


def test_total_quantity(cart):
    cart.add("PEN-001", 3).add("MUG-001", 2)
    assert cart.total_quantity() == 5


def test_total_weight_single_units(cart):
    cart.add("PEN-001").add("MUG-001")
    assert cart.total_weight() == 415
