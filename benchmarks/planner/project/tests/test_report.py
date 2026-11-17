from planner.models import Plan, Task
from planner.report import (format_percent, group_by_tag, progress, render, summary_line,
                            top_priorities)
from planner.schedule import Slot, build_schedule


def test_progress(plan):
    assert progress(plan) == 0.0
    plan.complete("design")
    plan.complete("copy")
    assert progress(plan) == 100 * 5 / 12


def test_progress_of_a_plan_without_work():
    assert progress(Plan("empty")) == 0.0


def test_format_percent_rounds():
    assert format_percent(41.666) == "42%"
    assert format_percent(100.0) == "100%"
    assert format_percent(0.4) == "0%"


def test_top_priorities(plan):
    assert [task.name for task in top_priorities(plan)] == ["review", "design", "build"]
    assert [task.name for task in top_priorities(plan, 1)] == ["review"]


def test_top_priorities_skips_finished_work(plan):
    plan.complete("review")
    assert [task.name for task in top_priorities(plan, 2)] == ["design", "build"]


def test_group_by_tag(plan):
    assert group_by_tag(plan) == {"ux": ["design", "review"], "content": ["copy"],
                                  "core": ["build"], "backend": ["build"]}


def test_summary_line():
    line = summary_line(Task("build", 5, owner="ben"), Slot(3, 10))
    assert line == "[ ] build (5d)     ben   W1 Thu -> W2 Thu"
    done = summary_line(Task("spec", 2, done=True), Slot(0, 2))
    assert done == "[x] spec (2d)      -     W1 Mon -> W1 Wed"


def test_render(plan):
    plan.complete("design")
    text = render(plan, build_schedule(plan))
    assert text.splitlines() == [
        "relaunch: 5 tasks, 25% done",
        "[ ] copy (2d)      cy    W1 Mon -> W1 Wed",
        "[x] design (3d)    ana   W1 Mon -> W1 Thu",
        "[ ] build (5d)     ben   W1 Thu -> W2 Thu",
        "[ ] review (2d)    ana   W2 Thu -> W2 Sat",
        "[ ] <launch>       -     W2 Sat -> W2 Sat",
        "finishes W2 Sat",
    ]
