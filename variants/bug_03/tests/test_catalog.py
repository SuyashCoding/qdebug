import pytest

from shop.catalog import Product


def test_get_known_sku(catalog):
    pen = catalog.get("PEN-001")
    assert pen.price == 199
    assert pen.category == "office"


def test_get_unknown_sku_raises(catalog):
    with pytest.raises(KeyError):
        catalog.get("NOPE-404")


def test_duplicate_sku_rejected(catalog):
    with pytest.raises(ValueError):
        catalog.add(Product("PEN-001", "Another Pen", 99, 10, "office"))


def test_find_by_category(catalog):
    books = catalog.find_by_category("books")
    assert [p.sku for p in books] == ["BOOK-001", "BOOK-002"]


def test_search_is_case_insensitive(catalog):
    assert [p.sku for p in catalog.search("COFFEE")] == ["FOOD-001", "MUG-001"]
    assert catalog.search("   ") == []
