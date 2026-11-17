"""Text reports about a plan and its schedule."""

from planner.schedule import finish_day
from planner.workdays import format_day


def progress(plan):
    """Percent of the planned working days that are done (0.0 for a plan without work)."""
    total = sum(task.days for task in plan.tasks())
    if total == 0:
        return 0.0
    return 100 * plan.done_days / total


def format_percent(value):
    """'67%' for 66.67: rounded to a whole percent."""
    return f"{round(value)}%"


def top_priorities(plan, count=3):
    """The `count` most important open tasks: highest priority first, then by name."""
    ranked = sorted(plan.open_tasks(), key=lambda task: (-task.weight, task.name))
    return ranked[:count]


def group_by_tag(plan):
    """{tag: [task names]} in plan order. A task is listed under each of its tags."""
    groups = {}
    for task in plan.tasks():
        for tag in task.tags:
            groups.setdefault(tag, []).append(task.name)
    return groups


def summary_line(task, slot):
    """One aligned report line for a scheduled task."""
    mark = "x" if task.done else " "
    owner = task.owner or "-"
    return f"[{mark}] {task.label():<14} {owner:<5} {format_day(slot.start)} -> {format_day(slot.end)}"


def render(plan, slots):
    """The plan as text: a header, one line per task by start day, and the finish day."""
    lines = [f"{plan.name}: {len(plan)} tasks, {format_percent(progress(plan))} done"]
    for name in sorted(slots, key=lambda n: (slots[n].start, n)):
        lines.append(summary_line(plan.get(name), slots[name]))
    lines.append(f"finishes {format_day(finish_day(slots))}")
    return "\n".join(lines)
