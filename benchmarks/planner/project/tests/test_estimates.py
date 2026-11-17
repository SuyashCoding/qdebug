from planner.estimates import Estimator
from planner.models import Plan, Task


def test_chain_lists_each_task_once(plan):
    assert sorted(Estimator(plan).chain("review")) == ["build", "copy", "design", "review"]
    assert Estimator(plan).chain("design") == ["design"]


def test_effort_adds_everything_before(plan):
    estimator = Estimator(plan)
    assert estimator.effort("design") == 3
    assert estimator.effort("review") == 12
    assert estimator.effort("launch") == 12


def test_open_effort_skips_finished_tasks(plan):
    plan.complete("design")
    estimator = Estimator(plan)
    assert estimator.effort("review") == 12
    assert estimator.effort("review", open_only=True) == 9
    assert estimator.effort("review") == 12


def test_reset_forgets_cached_totals(plan):
    estimator = Estimator(plan)
    assert estimator.effort("build") == 8
    plan.get("design").days = 6
    assert estimator.effort("build") == 8
    estimator.reset()
    assert estimator.effort("build") == 11


def test_buffer_rounds_up(plan):
    estimator = Estimator(plan)
    assert estimator.buffer("design") == 1
    assert estimator.buffer("build") == 2
    assert estimator.buffer("review") == 3
    assert estimator.buffer("review", percent=50) == 6


def test_risk_levels(plan):
    estimator = Estimator(plan)
    assert estimator.risk("design") == "low"
    assert estimator.risk("build") == "medium"
    assert estimator.risk("launch") == "medium"


def test_long_work_is_high_risk():
    plan = Plan("big")
    plan.add(Task("migrate", 15))
    plan.add(Task("tidy", 7))
    assert Estimator(plan).risk("migrate") == "high"
    assert Estimator(plan).risk("tidy") == "low"
