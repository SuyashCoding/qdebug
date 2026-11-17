"""Read a plan from plain text.

One task per line:

    design: 3d @ana !high #ux
    build: 1w after design @ben #core #backend
    launch: milestone after build, design

A line that starts with '#' is a comment, and so is everything after two
spaces and a '#'.
"""

from planner.models import PRIORITIES, Milestone, Plan, PlanError, Task

WEEK = 5  # working days


class ParseError(PlanError):
    def __init__(self, message, line_no=None):
        super().__init__(message if line_no is None else f"line {line_no}: {message}")
        self.line_no = line_no


def strip_comment(line):
    """The line without its comment and without surrounding spaces."""
    if line.lstrip().startswith("#"):
        return ""
    return line.split("  #", 1)[0].strip()


def parse_duration(text):
    """Working days of '3d', '2w' (5 days each) or a bare number."""
    text = text.strip().lower()
    try:
        if text.endswith("w"):
            return int(text[:-1]) * WEEK
        if text.endswith("d"):
            return int(text[:-1])
        return int(text)
    except ValueError:
        raise ParseError(f"bad duration {text!r}") from None


def parse_deps(text):
    """Task names from 'a, b, c'."""
    return tuple(part.strip() for part in text.split(",") if part.strip())


def split_fields(line):
    """(name, words) of 'name: word word ...'."""
    if ":" not in line:
        raise ParseError(f"expected 'name: ...', got {line!r}")
    name, rest = line.split(":", 1)
    return name.strip(), rest.split()


def parse_line(line):
    """One task from one line of plan text."""
    name, words = split_fields(line)
    if not name:
        raise ParseError("a task needs a name")
    days, deps, owner, priority, tags = None, [], "", "normal", []
    milestone = False
    reading_deps = False
    for word in words:
        if word[0] in "@!#":
            reading_deps = False
        if word.startswith("@"):
            owner = word[1:]
        elif word.startswith("!"):
            priority = word[1:].lower()
            if priority not in PRIORITIES:
                raise ParseError(f"unknown priority {word!r}")
        elif word.startswith("#"):
            tags.append(word[1:])
        elif word == "after":
            reading_deps = True
        elif reading_deps:
            deps.append(word)
        elif word == "milestone":
            milestone = True
        else:
            days = parse_duration(word)
    after = parse_deps(" ".join(deps))
    if milestone:
        return Milestone(name, after=after, owner=owner, priority=priority, tags=tuple(tags))
    if days is None:
        raise ParseError(f"task {name!r} needs a duration")
    return Task(name, days, after, owner, priority, tuple(tags))


def iter_lines(text):
    """(line number, content) of every line that is not empty or a comment."""
    for number, raw in enumerate(text.splitlines(), 1):
        content = strip_comment(raw)
        if content:
            yield number, content


def parse_plan(text, name="plan"):
    """A Plan from plan text. Errors say which line they are on."""
    plan = Plan(name)
    for number, content in iter_lines(text):
        try:
            plan.add(parse_line(content))
        except ParseError as exc:
            raise ParseError(str(exc), number) from None
    for task in plan.tasks():
        for dep in task.after:
            if dep not in plan:
                raise ParseError(f"{task.name!r} comes after unknown task {dep!r}")
    return plan
