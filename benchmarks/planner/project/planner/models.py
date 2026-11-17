"""Tasks and the plan that holds them."""

from dataclasses import dataclass, replace

PRIORITIES = {"low": 1, "normal": 2, "high": 3, "urgent": 4}


class PlanError(Exception):
    """Base class of every error the planner raises on purpose."""


class UnknownTask(PlanError):
    pass


class DuplicateTask(PlanError):
    pass


@dataclass
class Task:
    name: str
    days: int = 1
    after: tuple = ()
    owner: str = ""
    priority: str = "normal"
    tags: tuple = ()
    done: bool = False

    @property
    def weight(self):
        """The priority as a number: urgent 4, high 3, normal 2, low 1."""
        return PRIORITIES[self.priority]

    def label(self):
        """Short text for reports, e.g. 'build (5d)'."""
        return f"{self.name} ({self.days}d)"


@dataclass
class Milestone(Task):
    """A zero-day marker: it only waits for the tasks it comes after."""

    days: int = 0

    def label(self):
        """Milestones are shown in angle brackets, without a duration."""
        return f"<{self.name}>"


class Plan:
    """Tasks by name, in the order they were added."""

    def __init__(self, name="plan"):
        self.name = name
        self._tasks = {}
        self.done_days = 0

    def __contains__(self, name):
        return name in self._tasks

    def __len__(self):
        return len(self._tasks)

    def add(self, task):
        """Add a task and return it. Names are unique."""
        if task.name in self._tasks:
            raise DuplicateTask(f"task {task.name!r} is already in the plan")
        self._tasks[task.name] = task
        return task

    def get(self, name):
        """The task called `name`; UnknownTask if there is none."""
        try:
            return self._tasks[name]
        except KeyError:
            raise UnknownTask(f"unknown task {name!r}") from None

    def tasks(self):
        """Every task, in the order they were added."""
        return list(self._tasks.values())

    def names(self):
        return list(self._tasks)

    def open_tasks(self):
        """The tasks that are not done yet."""
        return [task for task in self._tasks.values() if not task.done]

    def complete(self, name):
        """Mark a task done and count its days as finished work."""
        task = self.get(name)
        if not task.done:
            task.done = True
            self.done_days += task.days
        return task

    def remove(self, name):
        """Remove a task; tasks that waited for it no longer do."""
        self.get(name)
        del self._tasks[name]
        for task in self._tasks.values():
            task.after = tuple(dep for dep in task.after if dep != name)

    def drop_done(self):
        """Remove every finished task. Returns how many were removed."""
        removed = 0
        for name in list(self._tasks):
            if self._tasks[name].done:
                self.remove(name)
                removed += 1
        return removed

    def clone(self, name=None):
        """An independent copy, for what-if changes."""
        other = Plan(name or self.name)
        other._tasks = {key: replace(task) for key, task in self._tasks.items()}
        other.done_days = self.done_days
        return other
