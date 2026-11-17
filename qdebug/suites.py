"""Benchmark suites: a correct project plus seeded single-line bugs.

A suite is a directory with

    project/     a correct pytest project (every test passes)
    bugs.json    the seeded bugs
    variants/    one buggy copy of project/ per bug (generated, not committed)

Each bug is a single edit ("old" -> "new") in one file that keeps the file's
line count, so line numbers line up between the buggy and the fixed version:

    {"id": "bug_01", "kind": "off-by-one comparison", "category": "boundary",
     "description": "...", "file": "shop/pricing.py",
     "function": "quantity_discount_rate",
     "old": "    if quantity >= 10:", "new": "    if quantity > 10:",
     "buggy_lines": [24]}

Optional keys: "category" (the coarse bug kind, see tuning.BUG_KINDS) and
"accept" (other function qualnames that count as a correct answer, for bugs
in code that is not a call of its own, such as a generator body).
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
STAMP_FILE = ".stamps.json"
MIN_PASSING = 5


class SuiteError(RuntimeError):
    """A suite is missing, malformed, or one of its bugs does not behave as declared."""


@dataclass(frozen=True)
class Suite:
    root: str

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.root))

    @property
    def project(self):
        return os.path.join(self.root, "project")

    @property
    def bugs_path(self):
        return os.path.join(self.root, "bugs.json")

    @property
    def variants(self):
        return os.path.join(self.root, "variants")

    def variant(self, bug_id):
        return os.path.join(self.variants, bug_id)

    def bugs(self):
        return load_bugs(self.bugs_path)


def load_bugs(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def is_suite(path):
    return os.path.isfile(os.path.join(path, "bugs.json")) and os.path.isdir(os.path.join(path, "project"))


def find_suites(base="benchmarks"):
    """Every suite directly under base, by name."""
    if not os.path.isdir(base):
        return []
    return [Suite(os.path.join(base, name)) for name in sorted(os.listdir(base))
            if is_suite(os.path.join(base, name))]


def resolve_suites(paths=(), base="benchmarks"):
    """Suites named on the command line, or every suite under base."""
    if not paths:
        suites = find_suites(base)
        if not suites:
            raise SuiteError(f"no benchmark suite found under {base}/ (a suite has project/ and bugs.json)")
        return suites
    suites = []
    for path in paths:
        if not is_suite(path) and is_suite(os.path.join(base, path)):
            path = os.path.join(base, path)
        if not is_suite(path):
            raise SuiteError(f"{path} is not a benchmark suite (it needs project/ and bugs.json)")
        suites.append(Suite(path))
    return suites


def apply_bug(project_dir, bug):
    """Apply bug's old -> new edit inside project_dir, in place."""
    target = os.path.join(project_dir, bug["file"])
    with open(target, encoding="utf-8") as fh:
        text = fh.read()
    count = text.count(bug["old"])
    if count != 1:
        raise SuiteError(f"{bug['id']}: the 'old' snippet matches {count} times in {bug['file']}")
    edited = text.replace(bug["old"], bug["new"])
    lines = edited.splitlines()
    if len(lines) != len(text.splitlines()):
        raise SuiteError(f"{bug['id']}: the edit changes the line count of {bug['file']}")
    first = bug["new"].strip().splitlines()[0]
    for line_no in bug["buggy_lines"]:
        if not 1 <= line_no <= len(lines) or first not in lines[line_no - 1]:
            raise SuiteError(f"{bug['id']}: buggy line {line_no} does not contain the new snippet")
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(edited)


def run_tests(project_dir):
    """Run a project's pytest suite: (passed, failed, failing test ids)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider"],
        cwd=project_dir, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = proc.stdout

    def count(word):
        match = re.search(rf"(\d+) {word}", out)
        return int(match.group(1)) if match else 0

    return count("passed"), count("failed") + count("error"), re.findall(r"^FAILED (\S+)", out, flags=re.M)


def _tree_digest(project_dir):
    digest = hashlib.sha1()
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", ".pytest_cache"))
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(dirpath, name)
            digest.update(os.path.relpath(path, project_dir).replace(os.sep, "/").encode())
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()


def _stamp(project_digest, bug):
    payload = json.dumps(bug, sort_keys=True).encode()
    return hashlib.sha1(project_digest.encode() + payload).hexdigest()


def _read_stamps(suite):
    try:
        with open(os.path.join(suite.variants, STAMP_FILE), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def make_variant(suite, bug):
    dest = suite.variant(bug["id"])
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(suite.project, dest, ignore=IGNORE)
    apply_bug(dest, bug)
    return dest


def build_variants(suite, check=True, only_stale=False):
    """(Re)create the suite's variants. Returns one summary row per bug.

    check=True also runs the tests: the correct project must pass, and every
    variant must fail at least one test and pass at least MIN_PASSING.
    """
    bugs = suite.bugs()
    ids = [b["id"] for b in bugs]
    if len(set(ids)) != len(ids):
        raise SuiteError(f"{suite.name}: duplicate bug ids in {suite.bugs_path}")
    digest = _tree_digest(suite.project)
    stamps = _read_stamps(suite) if only_stale else {}
    rows = []
    if check and not only_stale:
        passed, failed, _ = run_tests(suite.project)
        if failed or not passed:
            raise SuiteError(f"{suite.name}: the correct project must pass its tests "
                             f"({passed} passed, {failed} failed)")
        rows.append({"id": "correct", "function": "-", "passed": passed, "failed": failed, "failing": []})
    os.makedirs(suite.variants, exist_ok=True)
    for bug in bugs:
        stamp = _stamp(digest, bug)
        if stamps.get(bug["id"]) == stamp and os.path.isdir(suite.variant(bug["id"])):
            continue
        dest = make_variant(suite, bug)
        if check:
            passed, failed, failing = run_tests(dest)
            if failed < 1:
                raise SuiteError(f"{suite.name}/{bug['id']}: expected at least one failing test")
            if passed < MIN_PASSING:
                raise SuiteError(f"{suite.name}/{bug['id']}: expected at least {MIN_PASSING} "
                                 f"passing tests, got {passed}")
            rows.append({"id": bug["id"], "function": bug["function"], "passed": passed,
                         "failed": failed, "failing": failing})
        stamps[bug["id"]] = stamp
    stamps = {k: v for k, v in stamps.items() if k in ids}
    with open(os.path.join(suite.variants, STAMP_FILE), "w", encoding="utf-8") as fh:
        json.dump(stamps, fh, indent=1, sort_keys=True)
    return rows


def ensure_variants(suite):
    """Build the variants that are missing or older than the project / bugs.json."""
    return build_variants(suite, check=False, only_stale=True)


def format_rows(rows):
    header = ("variant", "buggy function", "passed", "failed", "failing tests")
    table = [(r["id"], r["function"], r["passed"], r["failed"],
              ", ".join(t.split("::")[-1] for t in r["failing"])) for r in rows]
    widths = [max(len(str(row[i])) for row in table + [header]) for i in range(4)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths) + "  {}"
    lines = [fmt.format(*header), fmt.format(*("-" * w for w in widths), "-" * 13)]
    lines += [fmt.format(*row) for row in table]
    return "\n".join(lines)
