"""Group a project's failing tests by the bug that probably causes them.

When several tests fail, some of them often fail because of the same bug.
qdebug guesses which ones, from what it already recorded in the whole-suite
run (no extra test runs):

1. **Same crash.** Tests that raise the same exception at the same line of
   project code go together.
2. **Shared suspicious code.** A test's *best line* is the line it runs that
   the fewest passing tests run: the line spectrum-based fault localization
   would blame first. Two groups are merged when some line that every one of
   their tests runs is run by no more passing tests than the best line of
   one of the two groups. Then one bug in that line explains both groups
   at least as well as that group's own best line does. One bug that both run
   passes this test; two separate bugs usually don't, because the only code
   their tests share is code that passing tests run too.

It is a guess, made to be cautious: when in doubt, tests stay apart, which
only costs an extra session. A test that runs no project code at all (it
fails in the test file itself) gets a group of its own.

Each group can then be ranked on its own (Ranking(..., failing=group.tests)):
mixing failures of different bugs dilutes spectrum-based scores, which
assume a single bug.
"""

import re
from dataclasses import dataclass, field

# the last "path:line: ExceptionName" line of a pytest traceback is where it was raised
_RAISED_AT = re.compile(r"^(?P<file>[^\s:][^:\n]*\.py):(?P<line>\d+): (?P<exc>[A-Za-z_][\w.]*)[ \t]*$",
                        re.M)

# best-first merging compares every pair of groups; past this many tests it
# merges in one pass instead
MAX_PAIRWISE = 60


@dataclass
class TestGroup:
    __test__ = False  # not a pytest test class

    tests: list                    # TestRecords, the cheapest to debug first
    crash: tuple | None = None     # (exception name, relfile, line) shared by all its tests
    best_line: tuple | None = None  # (relfile, line) every test runs, run by the fewest passing tests
    best_line_passing: int | None = None
    reason: str = "single"         # "single", "same crash", "shared code" or "no project code"
    ids: set = field(default_factory=set)

    def __post_init__(self):
        self.ids = {t.nodeid for t in self.tests}

    @property
    def representative(self):
        return self.tests[0]

    def __contains__(self, nodeid):
        return nodeid in self.ids

    def __len__(self):
        return len(self.tests)

    def describe(self):
        """One short line on why these tests are together, e.g. 'TypeError at tqdm/_tqdm.py:323'."""
        if self.crash:
            exc, relfile, line = self.crash
            return f"{exc} at {relfile}:{line}"
        if self.reason == "no project code":
            return "fails before reaching the project's code"
        if self.best_line and len(self.tests) > 1:
            return f"they all run {self.best_line[0]}:{self.best_line[1]}"
        return ""


def raised_at(failure_text, project_files):
    """(exception name, relfile, line) where a failing test's exception was raised in project code.

    None when it was raised in a test file or outside the project (an
    assertion in the test, or a library), since tests that fail that way
    can still have different causes.
    """
    matches = list(_RAISED_AT.finditer(failure_text or ""))
    if not matches:
        return None
    last = matches[-1]
    relfile = last.group("file").replace("\\", "/")
    if relfile.startswith("./"):
        relfile = relfile[2:]
    if relfile not in project_files:
        return None
    return last.group("exc").rsplit(".", 1)[-1], relfile, int(last.group("line"))


class _Builder:
    def __init__(self, spectrum, functions):
        self.test_files = {f.file for f in functions.values() if f.is_test}
        self.project_files = {f.file for f in functions.values() if not f.is_test}
        self.passing = {}
        for test in spectrum.passing:
            for e in test.lines:
                if e[0] not in self.test_files:
                    self.passing[e] = self.passing.get(e, 0) + 1
        self.size = {}
        for test in spectrum.failing:
            self.size[test.nodeid] = sum(1 for f in test.functions if f in functions
                                         and not functions[f].is_test)

    def lines(self, test):
        return frozenset(e for e in test.lines if e[0] not in self.test_files)

    def best(self, shared):
        """(line, passing count) of the shared line the fewest passing tests run."""
        if not shared:
            return None, None
        line = min(shared, key=lambda e: (self.passing.get(e, 0), e))
        return line, self.passing.get(line, 0)


class _Cluster:
    def __init__(self, tests, shared, crash=None, reason="single"):
        self.tests = tests
        self.shared = shared
        self.crash = crash
        self.reason = reason


def group_failing(spectrum, functions):
    """The failing tests in groups that probably share a bug, the largest group first.

    functions: {func key: FuncInfo} from spectrum.scan_functions.
    """
    failing = spectrum.failing
    if not failing:
        return []
    b = _Builder(spectrum, functions)
    order = {t.nodeid: i for i, t in enumerate(failing)}

    clusters, by_crash, orphans = [], {}, []
    for test in failing:
        lines = b.lines(test)
        if not lines:
            orphans.append(test)
            continue
        crash = raised_at(test.failure, b.project_files)
        if crash is not None and crash in by_crash:
            c = by_crash[crash]
            c.tests.append(test)
            c.shared = c.shared & lines
            c.reason = "same crash"
            continue
        c = _Cluster([test], lines, crash)
        clusters.append(c)
        if crash is not None:
            by_crash[crash] = c

    def score(c):
        return b.best(c.shared)[1]

    def mergeable(x, y):
        shared = x.shared & y.shared
        if not shared:
            return None
        _, passing = b.best(shared)
        bar = max(score(x), score(y))
        if passing <= bar:
            return passing, shared
        return None

    def merge(x, y, shared):
        x.tests += y.tests
        x.shared = shared
        x.crash = x.crash if x.crash == y.crash else None
        x.reason = "same crash" if x.crash else "shared code"
        clusters.remove(y)

    if len(clusters) <= MAX_PAIRWISE:
        while True:
            best = None
            for i, x in enumerate(clusters):
                for y in clusters[i + 1:]:
                    found = mergeable(x, y)
                    if found and (best is None or found[0] < best[0]):
                        best = (found[0], x, y, found[1])
            if best is None:
                break
            merge(best[1], best[2], best[3])
    else:
        i = 0
        while i < len(clusters):
            x = clusters[i]
            j = i + 1
            while j < len(clusters):
                found = mergeable(x, clusters[j])
                if found:
                    merge(x, clusters[j], found[1])
                else:
                    j += 1
            i += 1

    groups = []
    for c in clusters:
        tests = sorted(c.tests, key=lambda t: (b.size[t.nodeid], order[t.nodeid]))
        line, passing = b.best(c.shared)
        groups.append(TestGroup(tests, c.crash, line, passing, c.reason if len(tests) > 1 else "single"))
    for test in orphans:
        groups.append(TestGroup([test], reason="no project code"))
    groups.sort(key=lambda g: (g.reason == "no project code", -len(g),
                               b.size[g.representative.nodeid], order[g.representative.nodeid]))
    return groups


def group_of(groups, nodeid):
    return next((g for g in groups if nodeid in g), None)


def format_groups(groups):
    """Plain-text listing of the failing tests by likely bug."""
    total = sum(len(g) for g in groups)
    out = [f"Failing tests by likely bug ({total} failing, {len(groups)} "
           f"group{'s' if len(groups) != 1 else ''}):"]
    for i, group in enumerate(groups, 1):
        what = group.describe()
        out.append(f"  group {i}: {len(group)} test{'s' if len(group) != 1 else ''}"
                   + (f", {what}" if what else ""))
        out += [f"    FAILED {t.nodeid}" for t in group.tests]
    return "\n".join(out)


def explained_by(spectrum, nodeid, relfile, lines=None, func=None):
    """Other failing tests that also ran the found line(s), or the found function.

    Running the buggy code is necessary for a test to fail because of it, so
    these are the failing tests this bug may also explain.
    """
    wanted = {(relfile, n) for n in (lines or ())}

    def ran(test):
        return bool(wanted & test.lines) if wanted else bool(func and func in test.functions)

    return [t.nodeid for t in spectrum.failing if t.nodeid != nodeid and ran(t)]
