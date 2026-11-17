import pytest

from planner.graph import CycleError, all_dependents, dependents, depth, find_cycle, order
from planner.models import Plan, Task


def diamond():
    """base <- left, right <- top; 'extra' waits for nothing."""
    plan = Plan("diamond")
    plan.add(Task("top", 1, after=("left", "right")))
    plan.add(Task("left", 2, after=("base",)))
    plan.add(Task("right", 3, after=("base",)))
    plan.add(Task("base", 1))
    plan.add(Task("extra", 1))
    return plan


def test_order_puts_dependencies_first(plan):
    assert order(plan) == ["design", "copy", "build", "review", "launch"]


def test_order_of_a_diamond():
    assert order(diamond()) == ["base", "left", "right", "top", "extra"]


def test_order_refuses_a_cycle():
    plan = Plan("loop")
    plan.add(Task("a", 1, after=("c",)))
    plan.add(Task("b", 1, after=("a",)))
    plan.add(Task("c", 1, after=("b",)))
    with pytest.raises(CycleError):
        order(plan)


def test_find_cycle():
    plan = Plan("loop")
    plan.add(Task("a", 1, after=("b",)))
    plan.add(Task("b", 1, after=("a",)))
    plan.add(Task("free", 1))
    assert find_cycle(plan) == ["a", "b", "a"]
    assert find_cycle(diamond()) == []


def test_direct_dependents():
    assert dependents(diamond(), "base") == ["left", "right"]
    assert dependents(diamond(), "top") == []


def test_all_dependents_follows_chains(plan):
    assert all_dependents(plan, "design") == ["build", "review", "launch"]
    assert all_dependents(plan, "copy") == ["review", "launch"]
    assert all_dependents(plan, "launch") == []


def test_depth():
    plan = diamond()
    assert depth(plan, "base") == 0
    assert depth(plan, "left") == 1
    assert depth(plan, "top") == 2


def test_depth_of_the_sample(plan):
    assert [depth(plan, name) for name in plan.names()] == [0, 0, 1, 2, 3]
