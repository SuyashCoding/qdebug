"""The real-bug study report: results.csv of `qdebug bugsinpy` -> study.md.

Follows results/bugsinpy-2026/PLAN.md: every research question answered separately
for the development and the held-out projects, paired tests on the same bugs.
"""

import csv
import statistics

from qdebug.bugsinpy import REPRODUCED
from qdebug.stats import bootstrap_mean, mcnemar, wilcoxon, wilson

MAIN = ("infogain", "tuned", 0.0)


def load(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_at_most(row, field, k):
    value = str(row.get(field) or "")
    return value.isdigit() and int(value) <= k


def _found(row):
    return row.get("found_function") in ("1", 1)


def _line(row):
    return row.get("line_in_region") in ("1", 1)


def _key(row):
    return (row["project"], int(row["bug"]))


def sessions(rows, strategy, policy, noise=0.0, seed=None):
    """{bug: row} of the completed sessions of one configuration."""
    out = {}
    for r in rows:
        if r.get("status") != "ok" or r.get("strategy") != strategy:
            continue
        if (r.get("policy") or "baseline") != policy or abs(_f(r.get("noise")) - noise) > 1e-9:
            continue
        if seed is not None and int(_f(r.get("seed"))) != seed:
            continue
        out.setdefault(_key(r), []).append(r)
    return out


def _share(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%, CI {100 * lo:.0f}–{100 * hi:.0f}%)"


def _p(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def _status_table(rows, projects):
    status = {}
    for r in rows:
        if r["project"] in projects:
            status.setdefault(_key(r), r["status"])
    out = ["| status | bugs |", "|---|---|"]
    for name in sorted(set(status.values())):
        out.append(f"| {name} | {sum(1 for s in status.values() if s == name)} |")
    reproduced = sum(1 for s in status.values() if s in REPRODUCED)
    return out, len(status), reproduced


def _rq1(main):
    rows = [rs[0] for rs in main.values()]
    n = len(rows)
    crashes = [r for r in rows if r.get("crash_function")]
    regions = [_f(r["region_size"]) for r in rows if r.get("region_size")]
    region = f"{statistics.mean(regions):.1f}" if regions else "-"
    out = ["| technique | buggy function | buggy line |", "|---|---|---|",
           f"| **qdebug** (one function, and a {region}-line region on average) "
           f"| {_share(sum(map(_found, rows)), n)} | {_share(sum(map(_line, rows)), n)} |"]
    for name, field in (("Ochiai", "sbfl"), ("DStar", "dstar")):
        for k in (1, 3, 5):
            out.append(f"| {name} top-{k} | {_share(sum(_rank_at_most(r, f'{field}_func_rank', k) for r in rows), n)} "
                       f"| {_share(sum(_rank_at_most(r, f'{field}_line_rank', k) for r in rows), n)} |")
    out.append(f"| crash location (all bugs) | {_share(sum(r.get('crash_found') in ('1', 1) for r in rows), n)} | – |")
    out.append(f"| crash location (the {len(crashes)} crashes only) "
               f"| {_share(sum(r.get('crash_found') in ('1', 1) for r in crashes), len(crashes))} | – |")
    q = rows
    out += ["", "Paired against qdebug on the same bugs (McNemar, exact): *only qdebug / only the other*, p.", "",
            "| comparison | function | line |", "|---|---|---|"]
    for label, ffield, lfield, k in (("Ochiai top-1", "sbfl_func_rank", "sbfl_line_rank", 1),
                                     ("Ochiai top-3", "sbfl_func_rank", "sbfl_line_rank", 3),
                                     ("Ochiai top-5", "sbfl_func_rank", "sbfl_line_rank", 5),
                                     ("DStar top-1", "dstar_func_rank", "dstar_line_rank", 1),
                                     ("DStar top-3", "dstar_func_rank", "dstar_line_rank", 3)):
        fa, fb, fp = mcnemar([_found(r) for r in q], [_rank_at_most(r, ffield, k) for r in q])
        la, lb, lp = mcnemar([_line(r) for r in q], [_rank_at_most(r, lfield, k) for r in q])
        out.append(f"| qdebug vs {label} | {fa} / {fb}, p = {_p(fp)} | {la} / {lb}, p = {_p(lp)} |")
    ca, cb, cp = mcnemar([_found(r) for r in q], [r.get("crash_found") in ("1", 1) for r in q])
    out.append(f"| qdebug vs crash location | {ca} / {cb}, p = {_p(cp)} | – |")
    return out


def _compare(rows, a_cfg, b_cfg, a_label, b_label):
    a, b = sessions(rows, *a_cfg), sessions(rows, *b_cfg)
    both = sorted(set(a) & set(b))
    ra, rb = [a[k][0] for k in both], [b[k][0] for k in both]
    if not both:
        return [f"No bug has both {a_label} and {b_label} sessions."]
    qa = [_f(r["func_questions"]) + _f(r["line_questions"]) for r in ra]
    qb = [_f(r["func_questions"]) + _f(r["line_questions"]) for r in rb]
    fa, fb, fp = mcnemar([_found(r) for r in ra], [_found(r) for r in rb])
    la, lb, lp = mcnemar([_line(r) for r in ra], [_line(r) for r in rb])
    wn, _, wp = wilcoxon(qa, qb)
    lo_a, hi_a = bootstrap_mean(qa)
    lo_b, hi_b = bootstrap_mean(qb)
    return [f"| | {a_label} | {b_label} | paired test |", "|---|---|---|---|",
            f"| buggy function | {sum(map(_found, ra))}/{len(both)} | {sum(map(_found, rb))}/{len(both)} "
            f"| McNemar: {fa} vs {fb} discordant, p = {_p(fp)} |",
            f"| buggy line | {sum(map(_line, ra))}/{len(both)} | {sum(map(_line, rb))}/{len(both)} "
            f"| McNemar: {la} vs {lb} discordant, p = {_p(lp)} |",
            f"| questions, mean (95% CI) | {statistics.mean(qa):.1f} ({lo_a:.1f}–{hi_a:.1f}) "
            f"| {statistics.mean(qb):.1f} ({lo_b:.1f}–{hi_b:.1f}) "
            f"| Wilcoxon: {wn} non-tied pairs, p = {_p(wp)} |",
            f"| questions, median | {statistics.median(qa):g} | {statistics.median(qb):g} | |"]


def _rq4(rows):
    out = ["| answers wrong | sessions | buggy function | buggy line | questions (mean) |", "|---|---|---|---|---|"]
    levels = sorted({_f(r.get("noise")) for r in rows if r.get("status") == "ok"})
    for noise in levels:
        sel = [r for rs in sessions(rows, "infogain", "tuned", noise).values() for r in rs]
        if not sel:
            continue
        out.append(f"| {100 * noise:.0f}% | {len(sel)} | {_share(sum(map(_found, sel)), len(sel))} "
                   f"| {_share(sum(map(_line, sel)), len(sel))} "
                   f"| {statistics.mean(_f(r['func_questions']) + _f(r['line_questions']) for r in sel):.1f} |")
    return out


def _rq5(main):
    rows = [rs[0] for rs in main.values()]
    groups = [
        ("failing test with < 100 calls", lambda r: _f(r["nodes_total"]) < 100),
        ("failing test with 100+ calls", lambda r: _f(r["nodes_total"]) >= 100),
        ("crash (exception raised in project code)", lambda r: bool(r.get("crash_function"))),
        ("no crash (a wrong value)", lambda r: not r.get("crash_function")),
        ("fix only inserts code (omission)", lambda r: r.get("patch_kind") == "insert"),
        ("fix changes existing lines", lambda r: r.get("patch_kind") != "insert"),
        ("one failing test", lambda r: _f(r.get("failing_tests"), 1) <= 1),
        ("several failing tests", lambda r: _f(r.get("failing_tests"), 1) > 1),
    ]
    out = ["| bugs | n | buggy function | buggy line | Ochiai top-1 function |", "|---|---|---|---|---|"]
    for label, pred in groups:
        sel = [r for r in rows if pred(r)]
        if not sel:
            continue
        out.append(f"| {label} | {len(sel)} | {_share(sum(map(_found, sel)), len(sel))} "
                   f"| {_share(sum(map(_line, sel)), len(sel))} "
                   f"| {_share(sum(_rank_at_most(r, 'sbfl_func_rank', 1) for r in sel), len(sel))} |")
    return out


def _per_project(rows, projects, main):
    out = ["| project | attempted | reproduced | sessions | qdebug function / line | Ochiai top-1 function |",
           "|---|---|---|---|---|---|"]
    for project in sorted(projects):
        status = {}
        for r in rows:
            if r["project"] == project:
                status.setdefault(_key(r), r["status"])
        if not status:
            continue
        sel = [rs[0] for k, rs in main.items() if k[0] == project]
        out.append(f"| {project} | {len(status)} | {sum(1 for s in status.values() if s in REPRODUCED)} "
                   f"| {len(sel)} | {sum(map(_found, sel))} / {sum(map(_line, sel))} "
                   f"| {sum(_rank_at_most(r, 'sbfl_func_rank', 1) for r in sel)} |")
    return out


def report_set(rows, title, projects):
    rows = [r for r in rows if r["project"] in projects]
    status, attempted, reproduced = _status_table(rows, projects)
    main = sessions(rows, *MAIN)
    out = [f"## {title}", "", f"Projects: {', '.join(sorted(projects))}. {attempted} bugs attempted, "
           f"{reproduced} reproduced, {len(main)} with a completed qdebug session (infogain, tuned policy, "
           "no wrong answers).", "", *status, ""]
    if not main:
        return out + ["No completed sessions.", ""]
    out += ["### RQ1. qdebug against the baselines", "", *_rq1(main), "",
            "### RQ2. Tuned search rules against the original search (infogain, no wrong answers)", "",
            *_compare(rows, ("infogain", "tuned", 0.0), ("infogain", "baseline", 0.0), "tuned", "baseline"), "",
            "Information gain against the classic strategies (tuned policy):", "",
            *_compare(rows, ("infogain", "tuned", 0.0), ("topdown", "tuned", 0.0), "infogain", "top-down"), "",
            *_compare(rows, ("infogain", "tuned", 0.0), ("divide", "tuned", 0.0), "infogain",
                      "divide-and-query"), "",
            "### RQ4. Wrong answers (infogain, tuned; every seed counted)", "", *_rq4(rows), "",
            "### RQ5. Where it fails", "", *_rq5(main), "",
            "### Per project", "", *_per_project(rows, projects, main), ""]
    return out


def write_report(results_csv, out_path, held_out, development=None):
    rows = load(results_csv)
    projects = {r["project"] for r in rows}
    held = set(held_out) & projects
    dev = set(development) & projects if development else projects - held
    out = ["# qdebug on real bugs (BugsInPy)", "",
           "Plan: [results/bugsinpy-2026/PLAN.md](../bugsinpy-2026/PLAN.md). Ground-truth oracle (each call "
           "compared with the fixed version); spectrum from the bug's test file(s). \"Found\" means qdebug's "
           "single reported function is a function the fix changes, and \"line\" that a line the fix changes is "
           "in its reported region. CI: 95% Wilson interval. Ties in the SBFL rankings are broken by name.", ""]
    if held:
        out += report_set(rows, "Held-out projects (never used while developing qdebug)", held)
    if dev:
        out += report_set(rows, "Development projects (used in version 0.1)", dev)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return out_path
