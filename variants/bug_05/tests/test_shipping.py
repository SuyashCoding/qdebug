from shop.shipping import (
    Address,
    estimate_delivery_days,
    shipping_cost,
    weight_cost,
    zone_for,
)


def test_zone_domestic_and_remote(california):
    assert zone_for(california) == "domestic"
    assert zone_for(Address("Kai", "US", "HI")) == "remote"


def test_zone_eu(germany):
    assert zone_for(germany) == "eu"
    assert estimate_delivery_days(germany) == 6


def test_zone_international():
    assert zone_for(Address("Yuki", "JP")) == "international"


def test_weight_cost_tiers():
    assert weight_cost("domestic", 500) == 499
    assert weight_cost("domestic", 501) == 899
    assert weight_cost("domestic", 6200) == 1899


def test_free_shipping_threshold(california):
    assert shipping_cost(california, 1000, 10000) == 0
    assert shipping_cost(california, 1000, 9999) == 899


def test_shipping_eu_parcel(germany):
    assert shipping_cost(germany, 1200, 5000) == 2199
