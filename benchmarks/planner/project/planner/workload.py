"""Who is carrying how much work."""


def load_by_owner(plan, include_done=False):
    """{owner: working days assigned}. Tasks without an owner are left out."""
    load = {}
    for task in plan.tasks():
        if not task.owner or (task.done and not include_done):
            continue
        load[task.owner] = load.get(task.owner, 0) + task.days
    return load


def busiest(plan):
    """The owner with the most open work (the first by name on a tie), or None."""
    load = load_by_owner(plan)
    if not load:
        return None
    return min(load, key=lambda owner: (-load[owner], owner))


def overloaded(plan, limit):
    """Owners whose open work is more than `limit` days, sorted by name."""
    return sorted(owner for owner, days in load_by_owner(plan).items() if days > limit)


def rebalance(plan, limit):
    """Move open tasks from overloaded owners to the least loaded owner, smallest task first.

    Changes the plan in place and returns the names of the tasks that moved.
    """
    moved = []
    load = load_by_owner(plan)
    for owner in overloaded(plan, limit):
        tasks = sorted((t for t in plan.open_tasks() if t.owner == owner), key=lambda t: (t.days, t.name))
        for task in tasks:
            if load[owner] <= limit:
                break
            target = min(load, key=lambda other: (load[other], other))
            if target == owner or load[target] + task.days > limit:
                continue
            task.owner = target
            load[owner] -= task.days
            load[target] += task.days
            moved.append(task.name)
    return moved


def owners_of(plan, tag, found=None):
    """Owners with at least one task tagged `tag`, in plan order, added to `found`."""
    if found is None:
        found = []
    for task in plan.tasks():
        if tag in task.tags and task.owner and task.owner not in found:
            found.append(task.owner)
    return found


def owner_views(plan):
    """{owner: function}; each function tells whether a task belongs to that owner."""
    views = {}
    for owner in sorted(load_by_owner(plan, include_done=True)):
        views[owner] = lambda task, owner=owner: task.owner == owner
    return views


def split_by_owner(plan):
    """{owner: [task names]} for every owner, tasks in plan order."""
    result = {}
    for owner, belongs in owner_views(plan).items():
        result[owner] = [task.name for task in plan.tasks() if belongs(task)]
    return result
