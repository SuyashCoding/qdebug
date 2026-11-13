"""Accounts in cents. Plain classes on purpose: no __repr__, no dataclasses."""

import random

FEE_FREE_LIMIT = 50_000


class Account:
    __slots__ = ("number", "owner", "balance", "history")

    def __init__(self, owner, balance=0):
        self.number = random.randint(10_000, 99_999)
        self.owner = owner
        self.balance = balance
        self.history = []

    def deposit(self, amount):
        self.balance += amount
        self.history.append(("deposit", amount))

    def withdraw(self, amount):
        fee = withdrawal_fee(amount)
        if amount + fee > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount + fee
        self.history.append(("withdraw", amount, fee))


def withdrawal_fee(amount):
    """1% of the amount above the fee-free limit, in whole cents."""
    if amount <= FEE_FREE_LIMIT:
        return 0
    return (amount - FEE_FREE_LIMIT) // 100


class Ledger:
    def __init__(self):
        self.accounts = {}

    def open(self, owner, balance=0):
        account = Account(owner, balance)
        self.accounts[owner] = account
        return account

    def total(self):
        return sum(a.balance for a in self.accounts.values())


def transfer(src, dst, amount):
    """Move amount from src to dst; src also pays the withdrawal fee."""
    src.withdraw(amount)
    dst.deposit(amount)
