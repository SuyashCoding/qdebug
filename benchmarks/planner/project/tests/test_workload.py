from planner.models import Plan, Task
from planner.workload import (busiest, load_by_owner, overloaded, owner_views, owners_of, rebalance,
                              split_by_owner)


def team():
    plan = Plan("team")
    plan.add(Task("api", 6, owner="ana", tags=("core",)))
    plan.add(Task("ui", 4, owner="ana", tags=("ux",)))
    plan.add(Task("db", 3, owner="ben", tags=("core",)))
    plan.add(Task("ops", 2, owner="cy", tags=("infra",)))
    plan.add(Task("idea", 5))
    return plan


def test_load_by_owner(plan):
    assert load_by_owner(plan) == {"ana": 5, "cy": 2, "ben": 5}


def test_finished_work_is_left_out_unless_asked():
    plan = team()
    plan.complete("ui")
    assert load_by_owner(plan) == {"ana": 6, "ben": 3, "cy": 2}
    assert load_by_owner(plan, include_done=True) == {"ana": 10, "ben": 3, "cy": 2}


def test_busiest():
    assert busiest(team()) == "ana"


def test_busiest_of_an_empty_plan():
    assert busiest(Plan("empty")) is None


def test_overloaded_means_more_than_the_limit():
    assert overloaded(team(), 3) == ["ana"]
    assert overloaded(team(), 2) == ["ana", "ben"]
    assert overloaded(team(), 10) == []


def test_rebalance_moves_small_tasks_first():
    plan = team()
    assert rebalance(plan, 7) == ["ui"]
    assert plan.get("ui").owner == "cy"
    assert load_by_owner(plan) == {"ana": 6, "ben": 3, "cy": 6}


def test_rebalance_keeps_moving_until_under_the_limit():
    plan = Plan("crunch")
    plan.add(Task("a", 2, owner="ana"))
    plan.add(Task("b", 3, owner="ana"))
    plan.add(Task("c", 6, owner="ana"))
    plan.add(Task("d", 1, owner="ben"))
    plan.add(Task("e", 1, owner="cy"))
    assert rebalance(plan, 8) == ["a", "b"]
    assert load_by_owner(plan) == {"ana": 6, "ben": 3, "cy": 4}


def test_rebalance_stops_when_nobody_has_room():
    plan = team()
    assert rebalance(plan, 4) == []
    assert plan.get("ui").owner == "ana"


def test_owners_of_a_tag():
    plan = team()
    assert owners_of(plan, "core") == ["ana", "ben"]
    assert owners_of(plan, "infra") == ["cy"]
    assert owners_of(plan, "ux", ["zed"]) == ["zed", "ana"]


def test_owner_views():
    views = owner_views(team())
    assert sorted(views) == ["ana", "ben", "cy"]
    assert views["cy"](Task("x", owner="cy"))


def test_split_by_owner():
    assert split_by_owner(team()) == {"ana": ["api", "ui"], "ben": ["db"], "cy": ["ops"]}
