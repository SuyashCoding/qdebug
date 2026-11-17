"""Working-day arithmetic on day numbers. Day 0 is a Monday."""

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def is_workday(day, holidays=()):
    """Monday to Friday, unless the day is a holiday."""
    return day % 7 < 5 and day not in holidays


def next_workday(day, holidays=()):
    """`day` itself if it is a working day, else the first working day after it."""
    while not is_workday(day, holidays):
        day += 1
    return day


def add_workdays(start, days, holidays=()):
    """The day after the last of `days` working days that begin on or after `start`.

    add_workdays(0, 5) is 5: Monday to Friday are used, so the work is over by
    Saturday (day 5). Zero days of work end where they start.
    """
    day = start
    remaining = days
    while remaining > 0:
        day = next_workday(day, holidays)
        day += 1
        remaining -= 1
    return day


def workdays_between(first, last, holidays=()):
    """The number of working days d with first <= d < last."""
    return sum(1 for day in range(first, last) if is_workday(day, holidays))


def format_day(day):
    """'W2 Tue' for day 8: weeks are numbered from 1."""
    return f"W{day // 7 + 1} {DAY_NAMES[day % 7]}"
