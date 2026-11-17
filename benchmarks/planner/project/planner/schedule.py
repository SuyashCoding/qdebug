"""Turn a plan into dates: which task runs from which day to which day."""

from dataclasses import dataclass

from planner.graph import order
from planner.workdays import add_workdays, next_workday, workdays_between


@dataclass(frozen=True)
class Slot:
    start: int  # the first day of work
    end: int    # the day after the last day of work


def earliest_start(task, slots, first_day):
    """The first day on which every task that `task` waits for has finished."""
    start = first_day
    for dep in task.after:
        start = max(start, slots[dep].end)
    return start


def build_schedule(plan, first_day=0, holidays=()):
    """{task name: Slot}. A person works on one task at a time, in dependency order."""
    slots = {}
    free_from = {}  # owner -> the first day they are available again
    for name in order(plan):
        task = plan.get(name)
        start = earliest_start(task, slots, first_day)
        if task.owner:
            start = max(start, free_from.get(task.owner, first_day))
        if task.days:
            start = next_workday(start, holidays)
        end = add_workdays(start, task.days, holidays)
        slots[name] = Slot(start, end)
        if task.owner:
            free_from[task.owner] = end
    return slots


def finish_day(slots):
    """The day the whole plan is finished (0 for an empty schedule)."""
    return max((slot.end for slot in slots.values()), default=0)


def critical_path(plan, slots):
    """The chain of tasks that decides the finish day, first task first."""
    if not slots:
        return []
    name = max(slots, key=lambda n: (slots[n].end, plan.names().index(n)))
    path = [name]
    while plan.get(name).after:
        name = max(plan.get(name).after, key=lambda dep: slots[dep].end)
        path.append(name)
    path.reverse()
    return path


def slack(plan, slots, name):
    """Working days by which `name` may slip without delaying anything that waits for it."""
    waiting = [slots[task.name].start for task in plan.tasks() if name in task.after]
    if not waiting:
        return workdays_between(slots[name].end, finish_day(slots))
    return workdays_between(slots[name].end, min(waiting))
