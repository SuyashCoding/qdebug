"""Effort and risk estimates."""

import math

from planner.graph import depth


class Estimator:
    """Effort totals for one plan, cached. Call reset() after changing the plan."""

    def __init__(self, plan):
        self.plan = plan
        self._cache = {}

    def reset(self):
        self._cache = {}

    def chain(self, name):
        """`name` and every task it directly or indirectly waits for, each once."""
        seen = []
        stack = [name]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.append(current)
            stack.extend(self.plan.get(current).after)
        return seen

    def effort(self, name, open_only=False):
        """Working days of `name` plus everything it waits for; open_only skips finished tasks."""
        key = (name, open_only)
        if key not in self._cache:
            tasks = [self.plan.get(other) for other in self.chain(name)]
            self._cache[key] = sum(task.days for task in tasks if not (open_only and task.done))
        return self._cache[key]

    def buffer(self, name, percent=20):
        """Extra days to reserve: `percent` of the effort, rounded up to a whole day."""
        return math.ceil(self.effort(name) * percent / 100)

    def risk(self, name):
        """'high' for long or deeply chained work, 'medium' in between, otherwise 'low'."""
        days = self.effort(name)
        chain = depth(self.plan, name)
        if days >= 15 or chain >= 4:
            return "high"
        if days >= 8 or chain >= 2:
            return "medium"
        return "low"
