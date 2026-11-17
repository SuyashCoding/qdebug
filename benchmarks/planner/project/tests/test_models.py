import pytest

from planner.models import DuplicateTask, Milestone, Plan, Task, UnknownTask


def small_plan():
    plan = Plan("small")
    plan.add(Task("spec", 2, owner="ana"))
    plan.add(Task("code", 4, after=("spec",), owner="ben"))
    plan.add(Task("docs", 1, after=("code", "spec"), owner="ana"))
    return plan


def test_add_returns_the_task_and_get_finds_it():
    plan = Plan()
    task = plan.add(Task("spec", 2))
    assert task.name == "spec"
    assert plan.get("spec") is task
    assert "spec" in plan and len(plan) == 1


def test_duplicate_names_are_rejected():
    plan = small_plan()
    with pytest.raises(DuplicateTask):
        plan.add(Task("spec", 9))


def test_unknown_task_raises():
    with pytest.raises(UnknownTask):
        small_plan().get("deploy")


def test_weight_follows_priority():
    assert Task("a", priority="urgent").weight == 4
    assert Task("a").weight == 2
    assert Task("a", priority="low").weight == 1


def test_labels():
    assert Task("build", 5).label() == "build (5d)"
    assert Milestone("launch").label() == "<launch>"
    assert Milestone("launch").days == 0


def test_complete_counts_days_once():
    plan = small_plan()
    plan.complete("spec")
    plan.complete("code")
    plan.complete("code")
    assert plan.done_days == 6
    assert [task.name for task in plan.open_tasks()] == ["docs"]


def test_remove_clears_dependencies():
    plan = small_plan()
    plan.remove("spec")
    assert plan.names() == ["code", "docs"]
    assert plan.get("code").after == ()
    assert plan.get("docs").after == ("code",)


def test_drop_done_removes_finished_tasks():
    plan = small_plan()
    plan.complete("spec")
    plan.complete("code")
    assert plan.drop_done() == 2
    assert plan.names() == ["docs"]
    assert plan.get("docs").after == ()


def test_clone_is_independent():
    plan = small_plan()
    what_if = plan.clone("what-if")
    what_if.complete("spec")
    what_if.remove("docs")
    assert what_if.done_days == 2
    assert plan.done_days == 0
    assert not plan.get("spec").done
    assert plan.names() == ["spec", "code", "docs"]


def test_clone_keeps_progress():
    plan = small_plan()
    plan.complete("spec")
    assert plan.clone().done_days == 2
