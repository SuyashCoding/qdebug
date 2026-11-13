# -*- coding: latin-1 -*-
"""Statement formatting (this file is Latin-1 encoded: é)."""

CURRENCY = "¤"


def format_cents(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d} {CURRENCY}"


def statement(account):
    return [f"{account.owner}: {format_cents(account.balance)}"]
