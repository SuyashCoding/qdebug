"""Evaluate qdebug on real bugs from BugsInPy (Widyasari et al., ESEC/FSE 2020).

    python -m qdebug bugsinpy --bugsinpy PATH/TO/BugsInPy --work DIR \\
        --bugs thefuck:1-10,PySnooper,tqdm:3 --strategies infogain,divide,topdown

For every bug this

1. checks out the buggy and the fixed version the way BugsInPy's
   bugsinpy-checkout does: the buggy commit plus the fix commit's test files,
   and for the fixed version also the fix commit's other changed files (one
   partial clone per project, one git worktree per version);
2. builds a virtualenv with uv for the bug's Python version, raised to the
   oldest one uv provides (3.8), from the bug's pinned requirements.txt plus
   the `pip install` lines of its setup.sh (`setup.py install` is skipped:
   the project must be traced from its source tree, not site-packages);
3. checks that the bug's failing tests (run_test.sh) fail on the buggy and
   pass on the fixed version, and skips it otherwise (e.g. POSIX-only tests);
4. takes the ground truth from bug_patch.txt: the buggy-side lines that the
   fix changes or deletes, or, for a hunk that only inserts lines, the lines
   around the insertion point; the buggy functions are the innermost functions
   containing those lines;
5. debugs the first failing test with each strategy and the GroundTruthOracle
   against the fixed version, at noise 0.

The coverage spectrum is restricted to the bug's test file(s) (bug.info
test_file), not the whole suite. That keeps runs short and avoids network
tests, and it makes SBFL weaker than a whole-suite spectrum would.

Everything (clones, checkouts, Pythons, environments) lives under --work.
Results go to results/bugsinpy/results.csv and summary.md.
"""

import csv
import glob
import hashlib
import os
import re
import shutil
import statistics
import subprocess
import time
import traceback

from qdebug.evaluate import RunCache
from qdebug.oracles import GroundTruthOracle
from qdebug.runner import RunnerError, RunOptions, make_runner
from qdebug.session import DebugSession, SessionConfig, SessionError
from qdebug.spectrum import scan_functions

MIN_PYTHON = (3, 8)  # the oldest CPython uv provides
# statuses of bugs that reproduced (failing on buggy, passing on fixed)
REPRODUCED = ("ok", "error", "no trace", "nondeterministic")
FIELDS = [
    "project", "bug", "status", "detail", "python", "test", "buggy_functions", "buggy_lines",
    "patch_kind", "suite_tests", "strategy", "reported_function", "found_function",
    "found_before_zoom", "func_questions", "line_questions", "line_in_region", "region_size",
    "region_lines", "zoom_status", "final_tier", "nodes_total", "nodes_monitored",
    "sbfl_func_rank", "sbfl_line_rank", "functions_total", "stop_reason", "seconds", "basis",
    "policy",
]
# requirement lines that would install the project itself (it is traced from source) or are bogus
OWN_PACKAGES = {"pysnooper", "thefuck", "tqdm", "youtube-dl", "youtube_dl", "httpie",
                "cookiecutter", "black", "pkg-resources", "pkg_resources"}
# test dependencies that BugsInPy gets from `setup.py install` (extras), which we skip
EXTRA_REQUIREMENTS = {"PySnooper": ["python_toolbox", "future", "six"],
                      "cookiecutter": ["pytest-cov", "future"]}  # --cov in setup.cfg; past.builtins
GIT = ["git", "-c", "core.longpaths=true"]  # Windows: deep test-fixture paths


class SetupError(RuntimeError):
    """The bug could not be prepared (clone, environment, reproduction)."""


def sh(cmd, cwd=None, timeout=1800, check=True):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise SetupError(f"{' '.join(cmd[:4])}... failed (exit {proc.returncode}): "
                         f"{(proc.stderr or proc.stdout)[-1500:]}")
    return proc


def read_info(path):
    """key="value" lines of a BugsInPy .info file."""
    info = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r'\s*(\w+)\s*=\s*"([^"]*)"', line)
            if m:
                info[m.group(1)] = m.group(2)
    return info


# ------------------------------------------------------------ bug selection

def select_bugs(bugsinpy, spec):
    """spec: "thefuck:1-5,PySnooper,tqdm:3;7" -> [(project, bug id), ...]."""
    out = []
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        project, _, ids = part.partition(":")
        bug_dir = os.path.join(bugsinpy, "projects", project, "bugs")
        if not os.path.isdir(bug_dir):
            raise SystemExit(f"unknown BugsInPy project {project!r}")
        available = sorted(int(b) for b in os.listdir(bug_dir) if b.isdigit())
        if not ids:
            chosen = available
        else:
            chosen = []
            for piece in ids.split(";"):
                lo, _, hi = piece.partition("-")
                chosen += [b for b in available if int(lo) <= b <= int(hi or lo)]
        out += [(project, b) for b in chosen]
    return out


# ------------------------------------------------------------ tests and patch

def unittest_to_nodeid(dotted, project_dir):
    """test.test_utils.TestUtil.test_x -> test/test_utils.py::TestUtil::test_x."""
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        path = "/".join(parts[:i]) + ".py"
        if os.path.isfile(os.path.join(project_dir, path)):
            return "::".join([path] + parts[i:])
    return None


def parse_tests(run_test_text, project_dir):
    """pytest node ids of the failing tests named in run_test.sh."""
    tests = []
    for command in re.split(r"[;\n]", run_test_text):
        tokens = command.split()
        if not tokens:
            continue
        if "unittest" in tokens:
            targets = [t for t in tokens[tokens.index("unittest") + 1:] if not t.startswith("-")]
            tests += [n for n in (unittest_to_nodeid(t, project_dir) for t in targets) if n]
        elif any(t in ("pytest", "tox", "py.test") for t in tokens):
            tests += [t for t in tokens if "::" in t or t.endswith(".py")]
    return list(dict.fromkeys(tests))


def patch_locations(patch_text):
    """{buggy file: (sorted lines, kind)} from a unified diff (buggy -> fixed).

    Changed or deleted buggy-side lines; for a hunk that only inserts, the
    buggy lines just before and after the insertion point. kind is "change"
    if any hunk of the file removes lines, else "insert". Hunk line counts
    decide what is a hunk line, so a removed line that itself starts with
    "-- " is not mistaken for a file header.
    """
    files = {}    # file -> set of buggy-side lines
    changes = set()  # files with at least one removed line
    current = None
    old = old_left = new_left = 0
    removed = anchors = None

    def close_hunk():
        if current is not None and removed is not None:
            files[current].update(removed or anchors)
            if removed:
                changes.add(current)

    for line in patch_text.splitlines():
        if old_left > 0 or new_left > 0:
            tag = line[0] if line else " "
            if tag == "\\":
                continue  # "\ No newline at end of file"
            if tag == "-":
                removed.add(old)
                old, old_left = old + 1, old_left - 1
            elif tag == "+":
                anchors.update({max(old - 1, 1), old})
                new_left -= 1
            else:  # context (an empty line is context whose space was stripped)
                old, old_left, new_left = old + 1, old_left - 1, new_left - 1
            continue
        if line.startswith("--- "):
            close_hunk()
            removed = None
            name = line[4:].split("\t")[0].strip()
            current = None if name == "/dev/null" else (name[2:] if name.startswith("a/") else name)
            if current is not None:
                files.setdefault(current, set())
            continue
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,(\d+))? @@", line)
        if m and current is not None:
            close_hunk()
            old = int(m.group(1))
            old_left = int(m.group(2)) if m.group(2) is not None else 1
            new_left = int(m.group(3)) if m.group(3) is not None else 1
            if old_left == 0:
                old += 1  # "-7,0": the insertion comes after line 7
            removed, anchors = set(), set()
    close_hunk()
    return {name: (sorted(lines), "change" if name in changes else "insert")
            for name, lines in files.items() if lines and not is_test_path(name)}


def is_test_path(relfile):
    parts = relfile.split("/")
    return any(p in ("test", "tests", "testing") for p in parts[:-1]) or parts[-1].startswith("test_")


def buggy_functions(functions, locations):
    """Innermost function keys that contain the ground-truth lines."""
    found = set()
    for relfile, (lines, _) in locations.items():
        defs = [f for f in functions.values() if f.file == relfile]
        for line in lines:
            inside = [f for f in defs if f.line <= line <= f.end_line]
            if inside:
                found.add(min(inside, key=lambda f: f.end_line - f.line).func)
    return sorted(found)


# ------------------------------------------------------------ checkout

class Workspace:
    def __init__(self, bugsinpy, work):
        self.bugsinpy = os.path.abspath(bugsinpy)
        self.work = os.path.abspath(work)
        for sub in ("repos", "checkouts", "envs", "pythons"):
            os.makedirs(os.path.join(self.work, sub), exist_ok=True)

    def bug_dir(self, project, bug):
        return os.path.join(self.bugsinpy, "projects", project, "bugs", str(bug))

    def repo(self, project):
        path = os.path.join(self.work, "repos", project)
        if not os.path.isdir(os.path.join(path, ".git")):
            url = read_info(os.path.join(self.bugsinpy, "projects", project, "project.info"))["github_url"]
            sh(GIT + ["clone", "-q", "--filter=blob:none", "--no-checkout", url.rstrip("/"), path])
        return path

    def checkout(self, project, bug):
        """(buggy dir, fixed dir), created once."""
        info = read_info(os.path.join(self.bug_dir(project, bug), "bug.info"))
        base = os.path.join(self.work, "checkouts", f"{project}-{bug}")
        done = os.path.join(base, ".ready")
        buggy, fixed = os.path.join(base, "buggy"), os.path.join(base, "fixed")
        if os.path.exists(done):
            return buggy, fixed, info
        repo = self.repo(project)
        shutil.rmtree(base, ignore_errors=True)
        sh(GIT + ["-C", repo, "worktree", "prune"])
        bug_commit, fix_commit = info["buggy_commit_id"], info["fixed_commit_id"]
        tests = [t for t in info.get("test_file", "").split(";") if t]
        changed = sh(GIT + ["-C", repo, "show", "--name-only", "--format=", fix_commit]).stdout.split()
        for dest, overlay in ((buggy, tests), (fixed, list(dict.fromkeys(tests + changed)))):
            sh(GIT + ["-C", repo, "worktree", "add", "-q", "--detach", "--force", dest, bug_commit])
            for relfile in overlay:
                show = subprocess.run(GIT + ["-C", repo, "show", f"{fix_commit}:{relfile}"],
                                      capture_output=True, timeout=600)
                if show.returncode != 0:
                    continue  # deleted by the fix
                target = os.path.join(dest, *relfile.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as fh:
                    fh.write(show.stdout)
        with open(done, "w") as fh:
            fh.write("ok\n")
        return buggy, fixed, info


# ------------------------------------------------------------ environments

def python_version(info):
    parts = tuple(int(x) for x in re.findall(r"\d+", info.get("python_version", "3.8"))[:2])
    return max(parts or MIN_PYTHON, MIN_PYTHON)


def requirements(bug_dir, project=None):
    """Pinned requirements without the project itself, plus setup.sh's pip installs.

    Also pytest and setuptools if missing (uv's virtualenvs have no
    setuptools, and old pytest imports pkg_resources).
    """
    reqs = []
    path = os.path.join(bug_dir, "requirements.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(("#", "-e", "git+")) or "@ file" in line:
                    continue
                name = re.split(r"[=<>!~\[ ;]", line, maxsplit=1)[0].lower()
                if name not in OWN_PACKAGES:
                    reqs.append(line)
    setup = os.path.join(bug_dir, "setup.sh")
    if os.path.exists(setup):
        with open(setup, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*pip3?\s+install\s+(.+)", line)
                if m:
                    reqs += [p for p in m.group(1).split() if not p.startswith("-")]
    reqs += EXTRA_REQUIREMENTS.get(project, [])
    names = {re.split(r"[=<>!~\[ ;]", r, maxsplit=1)[0].lower() for r in reqs}
    if "pytest" not in names:
        reqs.append("pytest<7")
    if "setuptools" not in names:
        reqs.append("setuptools<60")  # newer ones vendor a typeguard pytest plugin old pytest trips on
    return list(dict.fromkeys(reqs))


class Environments:
    def __init__(self, ws, log=print):
        self.ws = ws
        self.log = log

    def interpreter(self, version):
        root = os.path.join(self.ws.work, "pythons")
        pattern = os.path.join(root, f"cpython-{version[0]}.{version[1]}.*")
        if not glob.glob(pattern):
            # installed under --work: some Windows Pythons cannot see %APPDATA% from children
            sh(["uv", "python", "install", f"{version[0]}.{version[1]}", "--install-dir", root,
                "--no-bin"], check=False)
        for home in sorted(glob.glob(pattern)):
            for exe in ("python.exe", os.path.join("bin", "python3")):
                if os.path.isfile(os.path.join(home, exe)):
                    return os.path.join(home, exe)
        raise SetupError(f"no CPython {version[0]}.{version[1]} under {root}")

    def get(self, project, bug, info):
        version = python_version(info)
        reqs = requirements(self.ws.bug_dir(project, bug), project)
        key = hashlib.sha1("\n".join([f"{version}"] + reqs).encode()).hexdigest()[:10]
        env = os.path.join(self.ws.work, "envs", f"{project}-py{version[0]}{version[1]}-{key}")
        done = os.path.join(env, ".qdebug-ready")
        if os.path.exists(done):
            with open(done, encoding="utf-8") as fh:
                return env, f"{version[0]}.{version[1]}", fh.read().strip()
        shutil.rmtree(env, ignore_errors=True)
        sh(["uv", "venv", "-q", "--python", self.interpreter(version), env])
        req_file = os.path.join(env, "qdebug-requirements.txt")
        with open(req_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(reqs) + "\n")
        note = "all requirements"
        if sh(["uv", "pip", "install", "-q", "--python", env, "-r", req_file], check=False).returncode:
            # one at a time; a pin that does not install falls back to the newest compatible version
            failed = []
            for req in reqs:
                if sh(["uv", "pip", "install", "-q", "--python", env, req], check=False).returncode:
                    name = re.split(r"[=<>!~\[ ;]", req, maxsplit=1)[0]
                    if sh(["uv", "pip", "install", "-q", "--python", env, name], check=False).returncode:
                        failed.append(req)
            note = f"failed: {' '.join(failed)}" if failed else "some pins relaxed"
        with open(done, "w", encoding="utf-8") as fh:
            fh.write(note)
        return env, f"{version[0]}.{version[1]}", note


# ------------------------------------------------------------ evaluation

def outcome(run, project, test):
    data = run(project, "plain", test=test)
    tests = data.get("tests") or {}
    return next(iter(tests.values()))["outcome"] if tests else "not collected"


def evaluate_bug(ws, envs, project, bug, strategies, timeout=600, log=print, **session_options):
    """Rows (one per strategy, or one status row) for one BugsInPy bug."""
    base = {"project": project, "bug": bug, "status": "ok", "detail": ""}
    start = time.perf_counter()
    try:
        buggy, fixed, info = ws.checkout(project, bug)
        env, version, env_note = envs.get(project, bug, info)
        base["python"] = version
        bug_dir = ws.bug_dir(project, bug)
        with open(os.path.join(bug_dir, "run_test.sh"), encoding="utf-8", errors="replace") as fh:
            tests = parse_tests(fh.read(), buggy)
        if not tests:
            raise SetupError("no test found in run_test.sh")
        suite = tuple(t for t in info.get("test_file", "").split(";") if t)
        options = RunOptions(python=env, pythonpath=(".",), suite=suite, timeout=timeout)
        run = make_runner(options)
        try:
            outcome(run, buggy, tests[0])
        except RunnerError as exc:
            # relaxed pins can pull in a plugin that breaks the old pytest
            if "Plugin" not in str(exc) and "plugin" not in str(exc):
                raise
            options = RunOptions(python=env, pythonpath=(".",), suite=suite, timeout=timeout,
                                 autoload_plugins=False)
            run = make_runner(options)
            env_note += "; plugin autoload off"
        failing = [t for t in tests if outcome(run, buggy, t) == "failed"]
        if not failing:
            return [dict(base, status="not reproducible",
                         detail=f"buggy: {outcome(run, buggy, tests[0])} ({env_note})")]
        fixed_outcome = outcome(run, fixed, failing[0])
        if fixed_outcome != "passed":
            return [dict(base, status="not reproducible", detail=f"fixed: {fixed_outcome} ({env_note})")]
        with open(os.path.join(bug_dir, "bug_patch.txt"), encoding="utf-8", errors="replace") as fh:
            locations = patch_locations(fh.read())
        functions = scan_functions(buggy)
        targets = buggy_functions(functions, locations)
        kinds = {kind for _, kind in locations.values()}
        base.update(test=failing[0], buggy_functions=" ".join(targets),
                    buggy_lines=" ".join(f"{f}:{','.join(map(str, ls))}" for f, (ls, _) in locations.items()),
                    patch_kind="+".join(sorted(kinds)))
    except (SetupError, subprocess.TimeoutExpired, OSError, KeyError) as exc:
        return [dict(base, status="setup failed", detail=str(exc)[:500])]
    except RunnerError as exc:
        text = str(exc)
        if ("could not collect" in text or "ERROR collecting" in text) and "cannot import name" in text:
            # the fixed test imports something the fix adds: nothing can run on the buggy side
            line = next((l for l in text.splitlines() if "cannot import name" in l), "")
            return [dict(base, status="no trace",
                         detail=f"test module does not import on the buggy version: {line.strip()[:300]}")]
        return [dict(base, status="setup failed", detail=f"RunnerError: {text[:1500]}")]
    except Exception as exc:  # noqa: BLE001 - record and go on
        return [dict(base, status="setup failed", detail=f"{type(exc).__name__}: {str(exc)[-1500:]}")]

    rows = []
    cache = RunCache(run=run)
    policies = session_options.pop("policies", None) or [session_options.pop("policy", "baseline")]
    session_options.pop("policy", None)
    for strategy, policy in [(s, p) for p in policies for s in strategies]:
        t0 = time.perf_counter()
        row = dict(base, strategy=strategy, policy=policy)
        try:
            session = DebugSession(SessionConfig(project=buggy, test=failing[0], strategy=strategy,
                                                 policy=policy, **session_options),
                                   oracle=None, run=cache, out=lambda *a, **k: None)
            session.prepare()
            session.oracle = GroundTruthOracle(fixed, session.test_id, run=cache)
            session.run_session()
            row.update(session_row(session, targets, locations))
        except SessionError as exc:
            text = str(exc)
            status = ("no trace" if "before its body ran" in text
                      else "nondeterministic" if "different path" in text else "error")
            row.update(status=status, detail=text[:1500])
        except Exception:  # noqa: BLE001 - keep the traceback, go on with the next strategy
            row.update(status="error", detail=traceback.format_exc()[-1500:])
        row["seconds"] = round(time.perf_counter() - t0, 1)
        rows.append(row)
    log(f"  {project} {bug}: {time.perf_counter() - start:.0f}s")
    return rows


def session_row(session, targets, locations):
    found = session.found
    before = session.ranked_before_zoom[0][0] if session.ranked_before_zoom else None
    zoom = session.zoom
    true_lines = set(locations.get(found.file, ([], ""))[0]) if found else set()
    ranking = session.ranking
    func_ranks = [r for r in (ranking.function_rank(t) for t in targets) if r]
    line_ranks = [r for f, (ls, _) in locations.items() for r in (ranking.line_rank(f, n) for n in ls) if r]
    return {
        "suite_tests": len(session.spectrum.tests),
        "reported_function": found.func if found else "",
        "found_function": int(bool(found and found.func in targets)),
        "found_before_zoom": int(bool(before and before.func in targets)),
        "func_questions": session.questions_asked,
        "line_questions": sum(z.questions for z in session.zoom_results),
        "line_in_region": int(bool(zoom and true_lines & set(zoom.region))),
        "region_size": len(zoom.region) if zoom else "",
        "region_lines": " ".join(map(str, zoom.region)) if zoom else "",
        "zoom_status": zoom.status if zoom else (session.zoom_results[-1].status
                                                 if session.zoom_results else "none"),
        "final_tier": session.tier_runs[-1]["tier"],
        "nodes_total": len(session.tree),
        "nodes_monitored": session.tree.monitored_count(),
        "sbfl_func_rank": min(func_ranks) if func_ranks else "",
        "sbfl_line_rank": min(line_ranks) if line_ranks else "",
        "functions_total": len(ranking.ranked_functions),
        "stop_reason": session.stop_reason,
        "basis": session.basis,
    }


# ------------------------------------------------------------ reporting

def _num(values):
    vals = [float(v) for v in values if v not in ("", None)]
    return vals


def _pct(values):
    vals = _num(values)
    return f"{100 * sum(vals) / len(vals):.0f}%" if vals else "-"


def _mean(values):
    vals = _num(values)
    return f"{statistics.mean(vals):.1f}" if vals else "-"


def _median(values):
    vals = _num(values)
    return f"{statistics.median(vals):g}" if vals else "-"


def write_summary(rows, path, strategies):
    ok = [r for r in rows if r.get("status") == "ok"]
    bugs = sorted({(r["project"], int(r["bug"])) for r in rows})
    status = {}
    for r in rows:
        status.setdefault((r["project"], int(r["bug"])), r["status"])
    out = ["# qdebug on BugsInPy", "",
           f"{len(bugs)} bugs attempted, {sum(1 for s in status.values() if s in REPRODUCED)} "
           f"reproduced on this machine. GroundTruthOracle, noise 0, assumed ε = 0.1. "
           f"Spectrum: the bug's test file(s) only.", "",
           "## Setup outcome", "", "| status | bugs |", "|---|---|"]
    for name in sorted(set(status.values())):
        out.append(f"| {name} | {sum(1 for s in status.values() if s == name)} |")
    def rank_at_most(r, field, k):
        return str(r.get(field) or "").isdigit() and int(r[field]) <= k

    out += ["", "## Per strategy (bugs with a completed session)", "",
            "| strategy | sessions | function found | found before zoom | func. Q (mean / median) "
            "| line Q (mean) | true line in region | region size |",
            "|---|---|---|---|---|---|---|---|"]
    for s in strategies:
        good = [r for r in ok if r.get("strategy") == s]
        out.append(f"| {s} | {len(good)} | {_pct(r['found_function'] for r in good)} "
                   f"| {_pct(r['found_before_zoom'] for r in good)} "
                   f"| {_mean(r['func_questions'] for r in good)} / {_median(r['func_questions'] for r in good)} "
                   f"| {_mean(r['line_questions'] for r in good)} | {_pct(r['line_in_region'] for r in good)} "
                   f"| {_mean(r['region_size'] for r in good)} |")
    first = [r for r in ok if r.get("strategy") == strategies[0]]
    n = len(first)

    def count(pred):
        return f"{sum(1 for r in first if pred(r))} / {n}"

    small = [r for r in first if int(r["nodes_total"]) < 100]
    out += ["", f"## {strategies[0]} against SBFL (Ochiai on the same spectrum)", "",
            f"The same {n} sessions. SBFL \"top-k\" means the buggy function or line is among the "
            f"k most suspicious; qdebug reports one function and a region of "
            f"{_mean(r['region_size'] for r in first)} lines on average.", "",
            "| | qdebug | SBFL top-1 | SBFL top-3 | SBFL top-5 |", "|---|---|---|---|---|",
            f"| buggy function | {count(lambda r: r['found_function'] in (1, '1'))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_func_rank', 1))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_func_rank', 3))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_func_rank', 5))} |",
            f"| buggy line | {count(lambda r: r['line_in_region'] in (1, '1'))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_line_rank', 1))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_line_rank', 3))} "
            f"| {count(lambda r: rank_at_most(r, 'sbfl_line_rank', 5))} |", "",
            f"By tree size: {sum(1 for r in small if r['found_function'] in (1, '1'))} of {len(small)} "
            f"failing tests with fewer than 100 calls, "
            f"{sum(1 for r in first if int(r['nodes_total']) >= 100 and r['found_function'] in (1, '1'))} "
            f"of {n - len(small)} with 100 or more (median tree: "
            f"{_median(r['nodes_total'] for r in first)} calls).", "",
            "## Per project", "",
            "| project | attempted | reproduced | " + " | ".join(f"{s}: found / line" for s in strategies) + " |",
            "|---|---|---|" + "---|" * len(strategies)]
    for project in sorted({p for p, _ in bugs}):
        att = [b for b in bugs if b[0] == project]
        rep = [b for b in att if status[b] in REPRODUCED]
        cells = []
        for s in strategies:
            sel = [r for r in ok if r["project"] == project and r.get("strategy") == s]
            cells.append(f"{sum(int(r['found_function']) for r in sel)} / "
                         f"{sum(int(r['line_in_region']) for r in sel)} of {len(sel)}")
        out.append(f"| {project} | {len(att)} | {len(rep)} | " + " | ".join(cells) + " |")
    out += ["", "## Per bug", "",
            "| bug | status | patch | buggy function(s) | SBFL func / line rank | "
            + " | ".join(f"{s}: Q / found / line" for s in strategies) + " |",
            "|---|---|---|---|---|" + "---|" * len(strategies)]
    for key in bugs:
        sel = {r.get("strategy"): r for r in rows if (r["project"], int(r["bug"])) == key}
        any_row = next(iter(sel.values()))
        if any_row["status"] not in REPRODUCED:
            detail = any_row.get("detail", "").replace("|", "/").replace("\n", " ")[:80]
            out.append(f"| {key[0]} {key[1]} | {any_row['status']}: {detail} | | | |" + " |" * len(strategies))
            continue
        cells = []
        for s in strategies:
            r = sel.get(s)
            if r is None or r["status"] != "ok":
                cells.append(r["status"] if r else "-")
            else:
                cells.append(f"{r['func_questions']}+{r['line_questions']} / "
                             f"{'✓' if int(r['found_function']) else '✗'} / {'✓' if int(r['line_in_region']) else '✗'}")
        funcs = any_row.get("buggy_functions") or "(module level)"
        out.append(f"| {key[0]} {key[1]} | ok | {any_row.get('patch_kind', '')} | `{funcs}` "
                   f"| {any_row.get('sbfl_func_rank') or '-'} / {any_row.get('sbfl_line_rank') or '-'} | "
                   + " | ".join(cells) + " |")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


def run_bugsinpy(bugsinpy, work, bug_spec, strategies, out_dir, timeout=600, log=print, **session_options):
    ws = Workspace(bugsinpy, work)
    envs = Environments(ws, log)
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "results.csv")
    done = {}
    if os.path.exists(csv_path):  # resume: keep rows of bugs already evaluated
        with open(csv_path, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                done.setdefault((r["project"], int(r["bug"])), []).append(r)
    selected = select_bugs(ws.bugsinpy, bug_spec)
    rows = []
    for i, (project, bug) in enumerate(selected, 1):
        if (project, bug) in done:
            rows += done[(project, bug)]
            continue
        log(f"[{i}/{len(selected)}] {project} {bug}")
        new = evaluate_bug(ws, envs, project, bug, strategies, timeout=timeout, log=log, **session_options)
        for r in new:
            log(f"    {r.get('strategy') or '-':9} {r['status']}: "
                + (f"found={r.get('found_function')} line={r.get('line_in_region')} "
                   f"Q={r.get('func_questions')}+{r.get('line_questions')}" if r["status"] == "ok"
                   else r.get("detail", "")[:200]))
        rows += new
        done[(project, bug)] = new
        all_rows = [r for rs in done.values() for r in rs]
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)
    write_summary(rows, os.path.join(out_dir, "summary.md"), strategies)
    log(f"Wrote {csv_path} and summary.md")
    return rows
