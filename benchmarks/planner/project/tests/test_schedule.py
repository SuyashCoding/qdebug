from planner.models import Plan, Task
from planner.schedule import Slot, build_schedule, critical_path, earliest_start, finish_day, slack


def test_earliest_start_waits_for_every_dependency():
    slots = {"a": Slot(0, 4), "b": Slot(2, 9), "c": Slot(1, 3)}
    assert earliest_start(Task("x", 1, after=("a", "b", "c")), slots, 0) == 9
    assert earliest_start(Task("y", 1), slots, 5) == 5


def test_sample_schedule(plan):
    slots = build_schedule(plan)
    assert slots["design"] == Slot(0, 3)
    assert slots["copy"] == Slot(0, 2)
    assert slots["build"] == Slot(3, 10)
    assert slots["review"] == Slot(10, 12)
    assert slots["launch"] == Slot(12, 12)


def test_one_person_does_one_task_at_a_time():
    plan = Plan("solo")
    plan.add(Task("first", 2, owner="ana"))
    plan.add(Task("second", 2, owner="ana"))
    plan.add(Task("third", 1, owner="ana"))
    plan.add(Task("other", 1, owner="ben"))
    slots = build_schedule(plan)
    assert slots["first"] == Slot(0, 2)
    assert slots["second"] == Slot(2, 4)
    assert slots["third"] == Slot(4, 5)
    assert slots["other"] == Slot(0, 1)


def test_work_never_starts_on_a_weekend():
    plan = Plan("late")
    plan.add(Task("a", 5))
    plan.add(Task("b", 1, after=("a",)))
    slots = build_schedule(plan)
    assert slots["b"] == Slot(7, 8)


def test_schedule_with_a_late_start_and_holidays(plan):
    slots = build_schedule(plan, first_day=1, holidays=(2,))
    assert slots["design"] == Slot(1, 5)
    assert slots["copy"] == Slot(1, 4)


def test_finish_day(plan):
    assert finish_day(build_schedule(plan)) == 12
    assert finish_day({}) == 0


def test_critical_path(plan):
    slots = build_schedule(plan)
    assert critical_path(plan, slots) == ["design", "build", "review", "launch"]
    assert critical_path(plan, {}) == []


def test_slack(plan):
    slots = build_schedule(plan)
    assert slack(plan, slots, "copy") == 6
    assert slack(plan, slots, "design") == 0
    assert slack(plan, slots, "launch") == 0
