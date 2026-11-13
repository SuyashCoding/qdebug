"""Daily compounding, one helper call per day (a long loop of identical calls)."""


def daily_interest(balance, yearly_rate_bp):
    return balance * yearly_rate_bp // (365 * 10_000)


def apply_interest(account, days, yearly_rate_bp=500):
    for _ in range(days):
        account.deposit(daily_interest(account.balance, yearly_rate_bp))
    return account.balance


def busy_sum(n):
    """A hot loop in project code, used to compare tracer overheads."""
    total = 0
    for i in range(n):
        total += i % 7
    return total
