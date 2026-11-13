"""Batch experiments: every bug x strategy x noise level x seed.

Uses the GroundTruthOracle (wrapped in a NoisyOracle when noise > 0) and
writes results/results.csv plus results/summary.md.

Traced runs are deterministic, so their results are cached per
(project, mode, test, monitored set, target): each distinct traced
execution happens once, and its timings are reused by every session that
needs it. With noise 0 the seed has no effect, so only seed 0 is run.
"""

import csv
import json
import os
import statistics
import subprocess
import sys
import time

from qdebug.oracles import GroundTruthOracle, NoisyOracle
from qdebug.ranking import DEFAULT_TIERS
from qdebug.runner import invoke
from qdebug.session import DebugSession, SessionConfig

FIELDS = [
    "bug", "strategy", "noise", "seed", "test", "target_function", "reported_function",
    "found_function", "found_before_zoom", "func_questions", "line_questions",
    "line_in_region", "region_size", "region_lines", "zoom_status", "zoom_attempts",
    "tiers_used", "final_tier", "nodes_total", "nodes_monitored", "untraced_ms",
    "traced_ms_per_tier", "sbfl_func_rank", "sbfl_line_rank", "stop_reason", "flips",
]


class RunCache:
    """Memoizes runner.invoke results (traced runs are deterministic)."""

    def __init__(self, run=invoke):
        self.run = run
        self.cache = {}
        self.misses = 0

    def __call__(self, project, mode, test=None, monitored=None, target=None, max_repr=300):
        key = (os.path.abspath(project), mode, test,
               None if monitored is None else frozenset(monitored), target, max_repr)
        if key not in self.cache:
            self.misses += 1
            self.cache[key] = self.run(project, mode, test=test, monitored=monitored,
                                       target=target, max_repr=max_repr)
        return self.cache[key]


def ensure_variants(bugs_path, variants_dir):
    missing = [b["id"] for b in load_bugs(bugs_path)
               if not os.path.isdir(os.path.join(variants_dir, b["id"]))]
    if missing:
        script = os.path.join(os.path.dirname(os.path.abspath(bugs_path)), "make_variants.py")
        subprocess.run([sys.executable, script, "--bugs", bugs_path, "--dest", variants_dir],
                       check=True)


def load_bugs(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def evaluate_one(bug, strategy, noise, seed, cache, fixed, variants_dir,
                 tiers=DEFAULT_TIERS, error_rate=0.1, budget=30, **overrides):
    project = os.path.join(variants_dir, bug["id"])
    config = SessionConfig(project=project, strategy=strategy, tiers=tiers,
                           error_rate=error_rate, budget=budget, **overrides)
    session = DebugSession(config, oracle=None, run=cache, out=lambda *a, **k: None)
    session.prepare()
    oracle = GroundTruthOracle(fixed, session.test_id, run=cache)
    if noise > 0:
        oracle = NoisyOracle(oracle, noise, seed)
    session.oracle = oracle
    session.run_session()

    target = f"{bug['file']}::{bug['function']}"
    found = session.found
    before = session.ranked_before_zoom[0][0] if session.ranked_before_zoom else None
    zoom = session.zoom
    in_region = bool(zoom and found is not None and found.file == bug["file"]
                     and any(line in zoom.region for line in bug["buggy_lines"]))
    ranking = session.ranking
    line_ranks = [r for r in (ranking.line_rank(bug["file"], n) for n in bug["buggy_lines"]) if r]
    return {
        "bug": bug["id"], "strategy": strategy, "noise": noise, "seed": seed,
        "test": session.test_id, "target_function": target,
        "reported_function": found.func if found else "",
        "found_function": int(bool(found and found.func == target)),
        "found_before_zoom": int(bool(before and before.func == target)),
        "func_questions": session.questions_asked,
        "line_questions": sum(z.questions for z in session.zoom_results),
        "line_in_region": int(in_region),
        "region_size": len(zoom.region) if zoom else "",
        "region_lines": " ".join(map(str, zoom.region)) if zoom else "",
        "zoom_status": zoom.status if zoom else (session.zoom_results[-1].status if session.zoom_results else "none"),
        "zoom_attempts": len(session.zoom_results),
        "tiers_used": len(session.tier_runs),
        "final_tier": session.tier_runs[-1]["tier"],
        "nodes_total": len(session.tree),
        "nodes_monitored": session.tree.monitored_count(),
        "untraced_ms": round(1000 * session.untraced_time, 3),
        "traced_ms_per_tier": ";".join(f"{t['tier']}%:{1000 * t['call_time']:.2f}"
                                       for t in session.tier_runs),
        "sbfl_func_rank": ranking.function_rank(target),
        "sbfl_line_rank": min(line_ranks) if line_ranks else "",
        "stop_reason": session.stop_reason,
        "flips": getattr(oracle, "flips", 0),
    }


def run_evaluation(bugs_path="bugs.json", fixed="sample_project", variants_dir="variants",
                   strategies=("infogain", "topdown", "divide"), noise_levels=(0.0, 0.1, 0.2),
                   seeds=10, out_dir="results", tiers=DEFAULT_TIERS, error_rate=0.1, budget=30,
                   log=print, policy="baseline"):
    ensure_variants(bugs_path, variants_dir)
    bugs = load_bugs(bugs_path)
    cache = RunCache()
    rows = []
    start = time.perf_counter()
    for bug in bugs:
        for strategy in strategies:
            for noise in noise_levels:
                for seed in (range(seeds) if noise > 0 else [0]):
                    row = evaluate_one(bug, strategy, noise, seed, cache, fixed, variants_dir,
                                       tiers, error_rate, budget, policy=policy)
                    rows.append(row)
            done = [r for r in rows if r["bug"] == bug["id"] and r["strategy"] == strategy]
            log(f"{bug['id']} {strategy:<9} runs={len(done):>3} "
                f"found={sum(r['found_function'] for r in done)}/{len(done)} "
                f"line={sum(r['line_in_region'] for r in done)}/{len(done)} "
                f"meanQ={statistics.mean(r['func_questions'] for r in done):.1f}")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    timing = timing_table(bugs, cache, variants_dir, rows)
    summary = summarize(rows, bugs, strategies, noise_levels, seeds, error_rate, timing)
    md_path = os.path.join(out_dir, "summary.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(summary)
    log(f"\n{len(rows)} sessions, {cache.misses} distinct traced runs, "
        f"{time.perf_counter() - start:.0f}s. Wrote {csv_path} and {md_path}")
    return rows


def timing_table(bugs, cache, variants_dir, rows):
    """{bug: {"untraced": ms, tier: (ms, nodes, monitored)}} from the cached tree runs."""
    out = {}
    for bug in bugs:
        project = os.path.abspath(os.path.join(variants_dir, bug["id"]))
        test = next(r["test"] for r in rows if r["bug"] == bug["id"])
        entry = {}
        for key, data in cache.cache.items():
            if key[0] != project or key[2] != test:
                continue
            record = next(iter(data["tests"].values()))
            if key[1] == "plain":
                entry["untraced"] = 1000 * record.get("call_time", 0.0)
            elif key[1] == "tree":
                nodes = record.get("nodes", [])
                entry[len(key[3]) if key[3] is not None else "all"] = (
                    1000 * record.get("call_time", 0.0), len(nodes),
                    sum(1 for n in nodes if n["monitored"]))
        out[bug["id"]] = entry
    return out


def _mean(values):
    values = [v for v in values if v != "" and v is not None]
    return statistics.mean(values) if values else float("nan")


def _pct(values):
    values = list(values)
    return f"{100 * sum(values) / len(values):.0f}%" if values else "-"


def summarize(rows, bugs, strategies, noise_levels, seeds, error_rate, timing):
    out = ["# qdebug evaluation summary", ""]
    out.append(f"{len(bugs)} seeded bugs x {len(strategies)} strategies x noise "
               f"{', '.join(str(n) for n in noise_levels)} ({seeds} seeds per noise level > 0; "
               f"noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate "
               f"ε = {error_rate}. Questions are function-level oracle answers; line questions are "
               f"zoom-mode answers.")
    out.append("")
    out.append("## Per-strategy comparison")
    out.append("")
    out.append("| strategy | noise | runs | function found | func. questions | line questions "
               "| true line in region | region size | tiers used | final tier % | monitored / total calls |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for noise in noise_levels:
        for strategy in strategies:
            sel = [r for r in rows if r["strategy"] == strategy and r["noise"] == noise]
            if not sel:
                continue
            out.append(
                f"| {strategy} | {noise} | {len(sel)} | {_pct(r['found_function'] for r in sel)} "
                f"| {_mean(r['func_questions'] for r in sel):.1f} "
                f"| {_mean(r['line_questions'] for r in sel):.1f} "
                f"| {_pct(r['line_in_region'] for r in sel)} "
                f"| {_mean(r['region_size'] for r in sel):.1f} "
                f"| {_mean(r['tiers_used'] for r in sel):.1f} "
                f"| {_mean(r['final_tier'] for r in sel):.0f} "
                f"| {_mean(r['nodes_monitored'] for r in sel):.0f} / {_mean(r['nodes_total'] for r in sel):.0f} |")
    out.append("")
    out.append("## Per-bug results (noise 0)")
    out.append("")
    header = "| bug | buggy function | SBFL function rank | SBFL line rank |"
    sep = "|---|---|---|---|"
    for s in strategies:
        header += f" {s}: Q / found / line / tier |"
        sep += "---|"
    out += [header, sep]
    for bug in bugs:
        sel0 = [r for r in rows if r["bug"] == bug["id"] and r["noise"] == noise_levels[0]]
        if not sel0:
            continue
        line = (f"| {bug['id']} | `{bug['function']}` | {sel0[0]['sbfl_func_rank']} "
                f"| {sel0[0]['sbfl_line_rank'] or '-'} |")
        for s in strategies:
            r = next((r for r in sel0 if r["strategy"] == s), None)
            if r is None:
                line += " - |"
                continue
            line += (f" {r['func_questions']}+{r['line_questions']} / {'✓' if r['found_function'] else '✗'}"
                     f" / {'✓' if r['line_in_region'] else '✗'} / {r['final_tier']}% |")
        out.append(line)
    out.append("")
    out.append("Q is function-level + line-level questions; found = reported function is the buggy one; "
               "line = a true buggy line is inside the reported region.")
    noisy = [n for n in noise_levels if n > 0]
    if noisy:
        out.append("")
        out.append("## Robustness per bug (function found rate under noise)")
        out.append("")
        header = "| bug |" + "".join(f" {s} @ {n} |" for n in noisy for s in strategies)
        out += [header, "|---|" + "---|" * (len(noisy) * len(strategies))]
        for bug in bugs:
            line = f"| {bug['id']} |"
            for n in noisy:
                for s in strategies:
                    sel = [r for r in rows if r["bug"] == bug["id"] and r["strategy"] == s and r["noise"] == n]
                    line += f" {_pct(r['found_function'] for r in sel)} |"
            out.append(line)
    out.append("")
    out.append("## Tracing cost per tier (failing test call only)")
    out.append("")
    out.append("| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |")
    out.append("|---|---|---|")
    for bug in bugs:
        entry = timing.get(bug["id"], {})
        parts = []
        for k in sorted((k for k in entry if k != "untraced"), key=lambda k: (k == "all", k if k != "all" else 0)):
            ms, nodes, mon = entry[k]
            parts.append(f"{k} → {ms:.1f} ms ({nodes}/{mon})")
        out.append(f"| {bug['id']} | {entry.get('untraced', float('nan')):.2f} | {'; '.join(parts)} |")
    out.append("")
    return "\n".join(out)
