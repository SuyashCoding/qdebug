from planner.workdays import add_workdays, format_day, is_workday, next_workday, workdays_between


def test_weekdays_and_weekends():
    assert [is_workday(day) for day in range(7)] == [True] * 5 + [False] * 2
    assert is_workday(7) and not is_workday(12)


def test_holidays_are_not_workdays():
    assert not is_workday(2, holidays=(2, 3))
    assert is_workday(4, holidays=(2, 3))


def test_next_workday():
    assert next_workday(3) == 3
    assert next_workday(5) == 7
    assert next_workday(4, holidays=(4,)) == 7


def test_add_workdays_inside_a_week():
    assert add_workdays(0, 3) == 3
    assert add_workdays(1, 1) == 2


def test_add_workdays_across_a_weekend():
    assert add_workdays(3, 5) == 10
    assert add_workdays(5, 1) == 8


def test_zero_days_end_where_they_start():
    assert add_workdays(4, 0) == 4
    assert add_workdays(12, 0) == 12


def test_add_workdays_skips_holidays():
    assert add_workdays(0, 3, holidays=(1,)) == 4


def test_workdays_between():
    assert workdays_between(0, 5) == 5
    assert workdays_between(3, 10) == 5
    assert workdays_between(4, 4) == 0
    assert workdays_between(0, 7, holidays=(2,)) == 4


def test_format_day():
    assert format_day(0) == "W1 Mon"
    assert format_day(8) == "W2 Tue"
    assert format_day(20) == "W3 Sun"
