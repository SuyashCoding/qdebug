"""The dependency structure of a plan."""

from planner.models import PlanError


class CycleError(PlanError):
    pass


def find_cycle(plan):
    """Names of tasks that wait for each other in a circle, or [] if there are none."""
    state = {}  # name -> "open" while its dependencies are followed, then "done"

    def follow(name, trail):
        if state.get(name) == "done":
            return []
        if state.get(name) == "open":
            return trail[trail.index(name):] + [name]
        state[name] = "open"
        for dep in plan.get(name).after:
            found = follow(dep, trail + [name])
            if found:
                return found
        state[name] = "done"
        return []

    for name in plan.names():
        found = follow(name, [])
        if found:
            return found
    return []


def order(plan):
    """Task names so that every task comes after the tasks it waits for.

    Tasks that could go either way keep the order they have in the plan.
    """
    cycle = find_cycle(plan)
    if cycle:
        raise CycleError("tasks wait for each other: " + " -> ".join(cycle))
    placed, result = set(), []

    def place(name):
        if name in placed:
            return
        for dep in plan.get(name).after:
            place(dep)
        placed.add(name)
        result.append(name)

    for name in plan.names():
        place(name)
    return result


def dependents(plan, name):
    """Names of the tasks that wait directly for `name`, in plan order."""
    return [task.name for task in plan.tasks() if name in task.after]


def _collect_dependents(plan, name, found):
    for child in dependents(plan, name):
        if child not in found:
            found.add(child)
            _collect_dependents(plan, child, found)


def all_dependents(plan, name):
    """Every task that directly or indirectly waits for `name`, in plan order."""
    found = set()
    _collect_dependents(plan, name, found)
    return [other for other in plan.names() if other in found]


def depth(plan, name, _memo=None):
    """Length of the longest chain of tasks that must finish before `name` starts."""
    memo = {} if _memo is None else _memo
    if name not in memo:
        after = plan.get(name).after
        memo[name] = 1 + max(depth(plan, dep, memo) for dep in after) if after else 0
    return memo[name]
