import pytest

from shop.cart import Cart
from shop.catalog import default_catalog
from shop.shipping import Address


@pytest.fixture
def catalog():
    return default_catalog()


@pytest.fixture
def cart(catalog):
    return Cart(catalog)


@pytest.fixture
def california():
    return Address("Ann Lee", "US", "CA", "94105")


@pytest.fixture
def germany():
    return Address("Hans Weber", "DE", "", "10115")
