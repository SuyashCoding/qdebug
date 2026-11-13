"""Shipping: destination zones, weight tiers and parcel splitting."""

import math
from dataclasses import dataclass

HOME_COUNTRY = "US"
REMOTE_REGIONS = ("AK", "HI", "PR")
EU_COUNTRIES = ("AT", "BE", "DE", "ES", "FR", "IE", "IT", "NL", "PL", "SE")

# Domestic orders whose (discounted) subtotal reaches this ship for free.
FREE_SHIPPING_THRESHOLD = 10000

# Per zone: ((max grams, cost in cents), ...) in increasing weight order.
WEIGHT_TIERS = {
    "domestic": ((500, 499), (2000, 899), (5000, 1499)),
    "remote": ((500, 999), (2000, 1799), (5000, 2999)),
    "eu": ((500, 1299), (2000, 2199), (5000, 3499)),
    "international": ((500, 1999), (2000, 3499), (5000, 5999)),
}
# Charged per started kilogram above the heaviest tier.
HEAVY_SURCHARGE_PER_KG = {"domestic": 200, "remote": 400, "eu": 500, "international": 800}
DELIVERY_DAYS = {"domestic": 3, "remote": 7, "eu": 6, "international": 12}
MAX_PARCEL_GRAMS = 5000


@dataclass(frozen=True)
class Address:
    name: str
    country: str
    region: str = ""
    postal_code: str = ""


def zone_for(address):
    """Shipping zone of an address: domestic, remote, eu or international."""
    country = address.country.upper()
    if country == HOME_COUNTRY:
        if address.region in REMOTE_REGIONS:
            return "remote"
        return "domestic"
    if country not in EU_COUNTRIES:
        return "eu"
    return "international"


def weight_cost(zone, grams):
    """Base cost in cents of shipping grams to zone."""
    tiers = WEIGHT_TIERS[zone]
    for max_grams, cost in tiers:
        if grams <= max_grams:
            return cost
    heaviest_limit, heaviest_cost = tiers[-1]
    extra_kg = math.ceil((grams - heaviest_limit) / 1000)
    return heaviest_cost + extra_kg * HEAVY_SURCHARGE_PER_KG[zone]


def shipping_cost(address, grams, subtotal):
    """Shipping charge in cents. Domestic orders above the threshold ship free."""
    if grams <= 0:
        return 0
    zone = zone_for(address)
    if zone == "domestic" and subtotal >= FREE_SHIPPING_THRESHOLD:
        return 0
    return weight_cost(zone, grams)


def estimate_delivery_days(address):
    """Typical number of days until delivery."""
    return DELIVERY_DAYS[zone_for(address)]


def split_parcels(grams, max_parcel=MAX_PARCEL_GRAMS):
    """Split a shipment into parcels of at most max_parcel grams each."""
    if grams <= 0:
        return []
    parcels = []
    while grams > max_parcel:
        parcels.append(max_parcel)
        grams -= max_parcel
    parcels.append(grams)
    return parcels
