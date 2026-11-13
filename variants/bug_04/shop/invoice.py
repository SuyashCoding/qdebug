"""Invoices: turn a cart into a priced, taxed and shipped Invoice."""

from dataclasses import dataclass, field

from shop.pricing import (
    compute_tax,
    coupon_discount,
    describe_coupon,
    line_total,
    round_cents,
    validate_coupon,
)
from shop.shipping import (
    estimate_delivery_days,
    shipping_cost,
    split_parcels,
    zone_for,
)


@dataclass(frozen=True)
class InvoiceLine:
    sku: str
    name: str
    quantity: int
    unit_price: int
    total: int


@dataclass
class Invoice:
    number: str
    lines: list
    subtotal: int
    discount: int
    tax: int
    shipping: int
    total: int
    zone: str
    parcels: int = 1
    notes: list = field(default_factory=list)


def money(cents):
    """Format cents as dollars, e.g. 1515 -> '$15.15'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"


def build_invoice(cart, address, coupon=None, number="INV-0001"):
    """Turn a cart into an Invoice.

    The computation runs in six sections:
      1. validate   - reject empty carts, missing addresses, bad items/coupons
      2. subtotal   - one InvoiceLine per cart line, quantity discounts applied
      3. discounts  - coupon discount, capped at the subtotal and split
                      proportionally between taxable and non-taxable goods
      4. tax        - tax on the *discounted* taxable amount
      5. shipping   - by zone and weight; domestic orders over the threshold
                      (after discounts) ship free
      6. totals     - grand total and notes
    The cart is not modified.
    """
    # ---- 1. validate ---------------------------------------------------
    if not cart.items:
        raise ValueError("cannot invoice an empty cart")
    if address is None or not address.country:
        raise ValueError("a shipping address with a country is required")
    for item in cart.items:
        if item.quantity <= 0:
            raise ValueError(f"invalid quantity {item.quantity} for {item.sku}")
        if item.sku not in cart.catalog:
            raise ValueError(f"unknown sku {item.sku}")
    if coupon is not None:
        validate_coupon(coupon)

    # ---- 2. subtotal ---------------------------------------------------
    lines = []
    subtotal = 0
    taxable_subtotal = 0
    for item in cart.items:
        product = cart.catalog.get(item.sku)
        total = line_total(item)
        lines.append(
            InvoiceLine(item.sku, product.name, item.quantity, item.unit_price, total)
        )
        subtotal += total
        if product.taxable:
            taxable_subtotal += total
    notes = []
    list_price = sum(item.unit_price * item.quantity for item in cart.items)
    if list_price > subtotal:
        notes.append(f"bulk savings {money(list_price - subtotal)}")

    # ---- 3. discounts --------------------------------------------------
    discount = 0
    if coupon is not None:
        discount = coupon_discount(coupon, cart.items, cart.catalog)
        if discount == 0:
            notes.append(f"coupon {coupon.code} not applicable")
        else:
            notes.append(f"coupon {coupon.code} ({describe_coupon(coupon)})")
    discount = min(discount, subtotal)
    if subtotal > 0:
        taxable_share = taxable_subtotal / subtotal
    else:
        taxable_share = 0.0
    taxable_discount = round_cents(discount * taxable_share)
    discounted_taxable = taxable_subtotal - taxable_discount
    discounted_subtotal = subtotal - discount

    # ---- 4. tax --------------------------------------------------------
    tax = compute_tax(taxable_subtotal, address)
    if tax < 0:
        raise ArithmeticError("negative tax")
    if tax == 0 and discounted_taxable > 0:
        notes.append("tax exempt destination")

    # ---- 5. shipping ---------------------------------------------------
    grams = cart.total_weight()
    zone = zone_for(address)
    shipping = shipping_cost(address, grams, discounted_subtotal)
    parcels = len(split_parcels(grams))
    if shipping == 0 and grams > 0:
        notes.append("free shipping")
    days = estimate_delivery_days(address)
    notes.append(f"ships to {zone} zone in about {days} days")

    # ---- 6. totals -----------------------------------------------------
    total = discounted_subtotal + tax + shipping
    if total < 0:
        raise ArithmeticError("negative invoice total")
    return Invoice(
        number=number,
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        shipping=shipping,
        total=total,
        zone=zone,
        parcels=max(parcels, 1),
        notes=notes,
    )


def format_invoice(invoice):
    """Render an invoice as plain text."""
    out = [f"Invoice {invoice.number}"]
    for line in invoice.lines:
        out.append(
            f"  {line.quantity:>3} x {line.name:<20} {money(line.total):>10}"
        )
    out.append(f"  {'Subtotal':<26} {money(invoice.subtotal):>10}")
    if invoice.discount:
        out.append(f"  {'Discount':<26} {money(-invoice.discount):>10}")
    out.append(f"  {'Tax':<26} {money(invoice.tax):>10}")
    out.append(f"  {'Shipping':<26} {money(invoice.shipping):>10}")
    out.append(f"  {'TOTAL':<26} {money(invoice.total):>10}")
    for note in invoice.notes:
        out.append(f"  * {note}")
    return "\n".join(out)


def invoice_summary(invoice):
    """A small dict summary of an invoice, e.g. for logging."""
    return {
        "number": invoice.number,
        "items": sum(line.quantity for line in invoice.lines),
        "total": invoice.total,
        "zone": invoice.zone,
    }
