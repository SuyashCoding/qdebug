from ledger.accounts import Ledger, transfer, withdrawal_fee
from ledger.interest import apply_interest, busy_sum
from ledger.legacy_format import format_cents, statement


def test_fee_free_withdrawal():
    ledger = Ledger()
    alice = ledger.open("alice", 10_000)
    alice.withdraw(2_500)
    assert alice.balance == 7_500


def test_fee_above_limit():
    assert withdrawal_fee(80_000) == 300


def test_large_transfer_charges_fee():
    ledger = Ledger()
    alice, bob = ledger.open("alice", 200_000), ledger.open("bob")
    transfer(alice, bob, 100_000)
    assert (alice.balance, bob.balance) == (99_500, 100_000)


def test_small_transfer():
    ledger = Ledger()
    alice, bob = ledger.open("alice", 1_000), ledger.open("bob", 5)
    transfer(alice, bob, 400)
    assert ledger.total() == 1_005


def test_interest_for_a_year():
    ledger = Ledger()
    saver = ledger.open("saver", 1_000_000)
    assert apply_interest(saver, 365) == 1_051_081


def test_statement_uses_latin1_module():
    ledger = Ledger()
    statement_lines = statement(ledger.open("carol", -1_234))
    assert statement_lines == ["carol: -12.34 \xa4"]
    assert format_cents(5) == "0.05 \xa4"


def test_hot_loop():
    assert busy_sum(200_000) == 599_994
