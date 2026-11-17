"""Two-bug experiments: does grouping the failing tests find the right groups, and does it help?

The benchmark suites seed one bug per variant. Here two of a suite's bugs are
put into one copy of the project (pairs whose edits don't overlap, in
different functions). A failing test belongs to bug A if it also fails with
bug A alone and not with bug B alone; tests that fail with either alone are
left out of the scoring.

Measured per pair:
- grouping: is no group a mix of both bugs (pure), and is each bug's tests in
  one group (complete)?
- ranking: the buggy function's Ochiai rank against every failing test vs
  against its own group only;
- sessions (optional): a full session on each bug's test, answered by the
  ground-truth oracle, with grouping on and off.
"""

import itertools
import os
import random
import shutil
import statistics
import tempfile
import time

from qdebug.evaluate import RunCache
from qdebug.groups import group_failing
from qdebug.oracles import GroundTruthOracle
from qdebug.ranking import Ranking
from qdebug.session import DebugSession, SessionConfig
from qdebug.spectrum import collect_spectrum, scan_functions
from qdebug.suites import IGNORE, SuiteError, apply_bug, ensure_variants


def _target(bug):
    return f"{bug['file']}::{bug['function']}"


def _accepted(bug):
    return {_target(bug)} | {f"{bug['file']}::{name}" for name in bug.get("accept", [])}


def _rank(ranking, bug):
    ranks = [r for r in (ranking.function_rank(f) for f in _accepted(bug)) if r]
    return min(ranks) if ranks else None


def bug_pairs(bugs, limit=None, seed=0):
    pairs = [(a, b) for a, b in itertools.combinations(bugs, 2) if _target(a) != _target(b)]
    if limit is not None and limit < len(pairs):
        random.Random(seed).shuffle(pairs)
        pairs = pairs[:limit]
    return pairs


def _session(project, fixed, test, grouping, cache):
    config = SessionConfig(project=project, test=test, policy="tuned", group_tests=grouping)
    session = DebugSession(config, oracle=None, run=cache, out=lambda *a, **k: None)
    session.prepare()
    session.oracle = GroundTruthOracle(fixed, session.test_id, run=cache)
    session.run_session()
    return session


def run_pairs(suite, pairs=None, sessions=False, seed=0, log=print, work=None):
    """Rows: one per (pair, bug), plus session rows when sessions=True."""
    ensure_variants(suite)
    bugs = suite.bugs()
    cache = RunCache()
    alone = {b["id"]: {t.nodeid for t in collect_spectrum(suite.variant(b["id"]), run=cache).failing}
             for b in bugs}
    work = work or tempfile.mkdtemp(prefix="qdebug-pairs-")
    rows, session_rows, skipped = [], [], 0
    start = time.perf_counter()
    for a, b in bug_pairs(bugs, pairs, seed):
        dest = os.path.join(work, f"{a['id']}+{b['id']}")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(suite.project, dest, ignore=IGNORE)
        try:
            try:
                apply_bug(dest, a)
                apply_bug(dest, b)
            except SuiteError:
                skipped += 1
                continue
            spectrum = collect_spectrum(dest, run=cache)
            functions = scan_functions(dest)
            failing = {t.nodeid for t in spectrum.failing}
            own = {a["id"]: (alone[a["id"]] - alone[b["id"]]) & failing,
                   b["id"]: (alone[b["id"]] - alone[a["id"]]) & failing}
            if not all(own.values()):
                skipped += 1
                continue
            groups = group_failing(spectrum, functions)
            pure = all(not (g.ids & own[a["id"]] and g.ids & own[b["id"]]) for g in groups)
            complete = all(sum(1 for g in groups if g.ids & own[x["id"]]) == 1 for x in (a, b))
            whole = Ranking(spectrum, functions)
            for bug, other in ((a, b), (b, a)):
                mine = own[bug["id"]]
                group = max(groups, key=lambda g: len(g.ids & mine))
                rows.append({
                    "pair": f"{a['id']}+{b['id']}", "bug": bug["id"], "failing": len(failing),
                    "groups": len(groups), "pure": int(pure), "complete": int(complete),
                    "rank_whole": _rank(whole, bug),
                    "rank_group": _rank(Ranking(spectrum, functions, failing=group.tests), bug),
                })
                if not sessions:
                    continue
                test = next((t.nodeid for t in group.tests if t.nodeid in mine), sorted(mine)[0])
                for grouping in (True, False):
                    s = _session(dest, suite.project, test, grouping, cache)
                    found = s.found.func if s.found else ""
                    zoom = s.zoom
                    session_rows.append({
                        "pair": f"{a['id']}+{b['id']}", "bug": bug["id"], "grouping": int(grouping),
                        "found_own": int(found in _accepted(bug)),
                        "found_other": int(found in _accepted(other)),
                        "line_own": int(bool(zoom and s.found and s.found.file == bug["file"]
                                             and any(n in zoom.region for n in bug["buggy_lines"]))),
                        "questions": s.questions_asked + sum(z.questions for z in s.zoom_results),
                        "fallback": int(s.basis != "answers"),
                    })
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        log(f"{suite.name} {a['id']}+{b['id']}: {len(rows) // 2} pairs, "
            f"{time.perf_counter() - start:.0f}s")
    return rows, session_rows, skipped


def _single_bug_groups(suite):
    out = []
    for bug in suite.bugs():
        path = suite.variant(bug["id"])
        out.append(len(group_failing(collect_spectrum(path), scan_functions(path))))
    return out


def summarize(suite, rows, session_rows, skipped, single):
    pairs = {r["pair"]: r for r in rows}
    n, nb = len(pairs), len(rows)

    def share(k, of):
        return f"{k}/{of} ({100 * k / of:.0f}%)" if of else "-"

    def ranks(key):
        values = [r[key] or 99 for r in rows]
        top1 = sum(1 for v in values if v == 1)
        top3 = sum(1 for v in values if v <= 3)
        return f"{statistics.mean(values):.2f} | {share(top1, nb)} | {share(top3, nb)}"

    out = [f"# Two bugs at once: {suite.name}", "",
           f"{n} pairs of the suite's seeded bugs in one copy of the project ({skipped} pairs skipped: "
           "their edits overlap, or one bug's failures are all also caused by the other).", "",
           "## Grouping", "",
           "| | |", "|---|---|",
           f"| single-bug variants kept in one group | {share(sum(1 for g in single if g == 1), len(single))} |",
           f"| pairs where no group mixes the two bugs | {share(sum(r['pure'] for r in pairs.values()), n)} |",
           f"| pairs where each bug's tests form one group | "
           f"{share(sum(r['complete'] for r in pairs.values()), n)} |",
           f"| pairs grouped exactly right | "
           f"{share(sum(r['pure'] and r['complete'] for r in pairs.values()), n)} |", "",
           "## Ranking the buggy function", "",
           "Ochiai rank of each bug's function, against every failing test or against its own group only.", "",
           "| ranked against | mean rank | top 1 | top 3 |", "|---|---|---|---|",
           f"| every failing test | {ranks('rank_whole')} |",
           f"| its own group | {ranks('rank_group')} |", ""]
    if session_rows:
        out += ["## Full sessions", "",
                "Each bug's test debugged with the ground-truth oracle (tuned policy, no noise).", "",
                "| grouping | sessions | found its bug | found the other bug | exact line | mean questions "
                "| fell back to a guess |", "|---|---|---|---|---|---|---|"]
        for grouping in (1, 0):
            r = [x for x in session_rows if x["grouping"] == grouping]
            out.append(f"| {'on' if grouping else 'off'} | {len(r)} | "
                       f"{share(sum(x['found_own'] for x in r), len(r))} | "
                       f"{share(sum(x['found_other'] for x in r), len(r))} | "
                       f"{share(sum(x['line_own'] for x in r), len(r))} | "
                       f"{statistics.mean(x['questions'] for x in r):.2f} | "
                       f"{share(sum(x['fallback'] for x in r), len(r))} |")
        out.append("")
    return "\n".join(out)


def run_suite(suite, pairs=None, sessions=False, out_dir="results/multi-bug", seed=0, log=print):
    rows, session_rows, skipped = run_pairs(suite, pairs, sessions, seed, log)
    text = summarize(suite, rows, session_rows, skipped, _single_bug_groups(suite))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{suite.name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        log(f"wrote {path}")
    return text
