"""How well Claude debugs the benchmark suites: `qdebug eval-ai`.

Every session runs with Claude as the oracle (or the hybrid oracle, where
the simulated person is the ground truth), and every question Claude answers
is also put to the ground-truth oracle, so the run measures:

* the result: buggy function found, true line in the reported region;
* the effort: questions asked, and in hybrid mode how many a person still
  had to answer;
* Claude as an oracle: agreement with the ground truth per question,
  separately for call and line questions, and by stated confidence
  (calibration);
* triage: the bug kind against the bug's category, and whether the buggy
  function is among the suspects;
* the explanation: whether the suggested fix restores the original code;
* cost: tokens and dollars.

Results go to <out>/<suite>/ai_results.csv, ai_questions.csv and
ai_summary.md.
"""

import csv
import os
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from qdebug.ai.assistant import Assistant
from qdebug.ai.client import AIUnavailable, Claude, load_sdk
from qdebug.ai.prompts import Agent
from qdebug.evaluate import RunCache
from qdebug.oracles import GroundTruthOracle, Oracle
from qdebug.session import DebugSession, SessionConfig
from qdebug.suites import ensure_variants

# $ per million tokens (input, output) for prompts of up to 100K tokens; cache
# reads cost 0.1x the input rate and 5-minute cache writes 1.25x.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-2": (8.00, 40.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

ROW_FIELDS = [
    "suite", "bug", "category", "mode", "model", "effort", "test", "target_function",
    "reported_function", "found_function", "line_in_region", "region_lines", "stop_reason", "basis",
    "call_questions", "line_questions", "human_questions", "claude_answers", "claude_correct",
    "claude_wrong", "claude_unknown", "triage_kind", "triage_kind_correct", "triage_suspect_hit",
    "fix", "fix_correct", "explain_confidence", "requests", "input_tokens", "cache_read_tokens",
    "cache_write_tokens", "output_tokens", "cost_usd", "seconds", "error",
]
QUESTION_FIELDS = ["suite", "bug", "number", "kind", "path", "line", "claude", "confidence", "truth",
                   "outcome", "misleading", "reason"]


def cost_of(model, usage):
    """Dollars for a Usage, or None for a model without a known price."""
    if model not in PRICES:
        return None
    rate_in, rate_out = PRICES[model]
    return (usage.input_tokens * rate_in + usage.cache_read_tokens * rate_in * 0.1
            + usage.cache_write_tokens * rate_in * 1.25 + usage.output_tokens * rate_out) / 1e6


def grade(claude, truth):
    """correct / wrong / abstained / ungradable, for one answer against the ground truth."""
    if truth not in ("yes", "no", "inadmissible"):
        return "ungradable"
    if claude in (None, "unknown"):
        return "abstained"
    return "correct" if claude == truth else "wrong"


class GradedOracle(Oracle):
    """Passes every question to base and also to the ground truth, and records both.

    A call answer the ground truth calls wrong can still agree with where the
    bug really is: "yes" about a call whose inputs were already infected
    (its output is right for those inputs), or "no" about the buggy function
    when its own earlier call corrupted the state it reads, or about a value
    whose wrongness its repr cannot show (an alias, a closure). Such answers
    do not mislead the search. `misleading` marks the wrong answers that do:
    every wrong line answer, and call answers that point away from the calls
    of the buggy function (accepted).
    """

    def __init__(self, base, truth, records, accepted=()):
        self.base = base
        self.truth = truth
        self.records = records
        self.accepted = set(accepted)
        self.name = base.name

    def _misleading(self, question, verdict, ctx):
        if question.kind != "call" or ctx is None or not self.accepted:
            return 1
        tree, node = ctx.tree, question.node
        holds_bug = any(tree.nodes[i].func in self.accepted for i in tree.subtree_range(node))
        if verdict == "no":
            return int(not holds_bug)
        if verdict == "yes":
            return int(node.func in self.accepted)  # the buggy function itself, cleared
        return 0

    def judge(self, question, ctx=None):
        answer = self.base.judge(question, ctx)
        if answer.verdict is None:
            return answer
        expected = self.truth.judge(question, ctx).verdict
        cp = question.checkpoint or {}
        self.records.append({
            "number": len(self.records) + 1, "kind": question.kind, "path": question.node.path,
            "line": cp.get("line") if cp.get("kind") == "line" else ("return" if cp else ""),
            "claude": answer.verdict, "confidence": round(answer.confidence, 3), "truth": expected,
            "outcome": grade(answer.verdict, expected),
            "misleading": (self._misleading(question, answer.verdict, ctx)
                           if grade(answer.verdict, expected) == "wrong" else 0),
            "reason": answer.note.split(": ", 1)[1] if ": " in answer.note else answer.note,
        })
        return answer


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def fix_restores_original(bug, fix):
    """True if the suggested fix contains every line the seeded bug changed, as it was."""
    if not fix or not fix.strip():
        return False
    fixed = _norm(fix)
    changed = [old for old, new in zip(bug["old"].splitlines(), bug["new"].splitlines()) if old != new]
    return all(_norm(line) in fixed for line in (changed or bug["old"].splitlines()))


def evaluate_bug(suite, bug, mode="claude", model=None, effort=None, client=None, policy="tuned",
                 threshold=0.8, show_source=False, triage=True, explain=True):
    """One Claude session on one seeded bug: (row, question records)."""
    start = time.perf_counter()
    cache = RunCache()
    claude = Claude(model=model, effort=effort, client=client)
    assistant = Assistant(claude, Agent.load(), show_source=show_source)
    session = DebugSession(SessionConfig(project=suite.variant(bug["id"]), policy=policy),
                           oracle=None, run=cache, out=lambda *a, **k: None)
    session.prepare()
    truth = GroundTruthOracle(suite.project, session.test_id, run=cache)
    records = []
    target = f"{bug['file']}::{bug['function']}"
    accepted = {target} | {f"{bug['file']}::{name}" for name in bug.get("accept", [])}
    row = {"suite": suite.name, "bug": bug["id"], "category": bug.get("category", ""), "mode": mode,
           "model": claude.model, "effort": claude.effort, "test": session.test_id,
           "target_function": target, "error": ""}
    if triage:
        result = assistant.triage(session)
        if result is not None:
            session.apply_triage(result)
            row.update(triage_kind=result.bug_kind,
                       triage_kind_correct=int(result.bug_kind == bug.get("category")),
                       triage_suspect_hit=int(bool(accepted & set(result.suspects))))
    graded = GradedOracle(assistant.oracle("claude"), truth, records, accepted)
    if mode == "hybrid":
        oracle = assistant.oracle("hybrid", human=truth, threshold=threshold)
        oracle.ai = graded
    else:
        oracle = graded
    session.oracle = oracle
    session.run_session()
    if explain and session.found is not None:
        session.explanation = assistant.explain(session)
    found, zoom = session.found, session.zoom
    outcomes = [r["outcome"] for r in records]
    row.update(
        reported_function=found.func if found else "",
        found_function=int(bool(found and found.func in accepted)),
        line_in_region=int(bool(zoom and found is not None and found.file == bug["file"]
                                and any(line in zoom.region for line in bug["buggy_lines"]))),
        region_lines=" ".join(map(str, zoom.region)) if zoom else "",
        stop_reason=session.stop_reason, basis=session.basis,
        call_questions=session.questions_asked,
        line_questions=sum(z.questions for z in session.zoom_results),
        human_questions=getattr(oracle, "human_answers", 0),
        claude_answers=len(records), claude_correct=outcomes.count("correct"),
        claude_wrong=outcomes.count("wrong"), claude_unknown=outcomes.count("abstained"),
        requests=claude.usage.requests, input_tokens=claude.usage.input_tokens,
        cache_read_tokens=claude.usage.cache_read_tokens,
        cache_write_tokens=claude.usage.cache_write_tokens, output_tokens=claude.usage.output_tokens,
        # no token counts (e.g. answered through the relay): the cost is unknown, not zero
        cost_usd=(cost_of(claude.model, claude.usage)
                  if claude.usage.input_tokens or claude.usage.output_tokens else None),
        seconds=round(time.perf_counter() - start, 1))
    if session.explanation is not None:
        row.update(fix=session.explanation.fix, explain_confidence=session.explanation.confidence,
                   fix_correct=int(fix_restores_original(bug, session.explanation.fix)))
    for record in records:
        record.update(suite=suite.name, bug=bug["id"])
    return row, records


def run_ai_benchmark(suites, mode="claude", model=None, effort=None, out_dir="results/claude",
                     bug_ids=None, workers=4, log=print, client=None, relay=None, **options):
    """evaluate_bug for every bug of every suite, in parallel; writes the CSVs and the summary.

    relay: a directory; every session then talks to a RelayClient in its own
    subdirectory (see relay.py) instead of the API.
    """
    if client is None and relay is None:
        client = load_sdk().Anthropic(max_retries=4, timeout=180.0)
    rows, questions = [], []
    for suite in suites:
        ensure_variants(suite)
        bugs = [b for b in suite.bugs() if not bug_ids or b["id"] in bug_ids]
        start = time.perf_counter()
        suite_rows, suite_questions = [], []

        def one(bug, suite=suite):
            session_client = client
            if relay is not None:
                from qdebug.ai.relay import RelayClient
                session_client = RelayClient(os.path.join(relay, f"{suite.name}-{bug['id']}"))
            try:
                return evaluate_bug(suite, bug, mode, model, effort, session_client, **options)
            except AIUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - one broken session must not end the run
                return ({"suite": suite.name, "bug": bug["id"], "category": bug.get("category", ""),
                         "mode": mode, "error": f"{type(exc).__name__}: {exc}"[:300]}, [])
            finally:
                if hasattr(session_client, "close"):
                    session_client.close()

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for row, records in pool.map(one, bugs):
                suite_rows.append(row)
                suite_questions += records
                log(f"{suite.name}/{row['bug']:<24} found={row.get('found_function', '-')} "
                    f"line={row.get('line_in_region', '-')} Q={row.get('call_questions', '-')}+"
                    f"{row.get('line_questions', '-')} claude {row.get('claude_correct', 0)}/"
                    f"{row.get('claude_answers', 0)} right {row.get('error', '')}")
        if out_dir:
            write_results(os.path.join(out_dir, suite.name), suite_rows, suite_questions,
                          title=f"Claude on {suite.name} ({mode}, {suite_rows[0].get('model', model)})")
        log(f"{suite.name}: {len(suite_rows)} sessions in {time.perf_counter() - start:.0f}s")
        rows += suite_rows
        questions += suite_questions
    return rows, questions


def write_results(directory, rows, questions, title):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "ai_results.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ROW_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(directory, "ai_questions.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=QUESTION_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(questions)
    with open(os.path.join(directory, "ai_summary.md"), "w", encoding="utf-8") as fh:
        fh.write(summarize(rows, questions, title))


def _share(n, d):
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "-"


def summarize(rows, questions, title):
    ok = [r for r in rows if not r.get("error")]
    out = [f"# {title}", ""]
    errors = [r for r in rows if r.get("error")]
    if errors:
        out += [f"{len(errors)} session(s) failed: " + "; ".join(f"{r['bug']}: {r['error']}" for r in errors), ""]
    if not ok:
        return "\n".join(out) + "\n"
    out += ["| | result |", "|---|---|"]
    out.append(f"| buggy function found | {_share(sum(r['found_function'] for r in ok), len(ok))} |")
    out.append(f"| true line in region | {_share(sum(r['line_in_region'] for r in ok), len(ok))} |")
    out.append(f"| questions per session (call + line) | "
               f"{statistics.mean(r['call_questions'] for r in ok):.1f} + "
               f"{statistics.mean(r['line_questions'] for r in ok):.1f} |")
    if any(r["mode"] == "hybrid" for r in ok):
        asked = sum(r["call_questions"] + r["line_questions"] for r in ok)
        human = sum(r["human_questions"] for r in ok)
        out.append(f"| questions a person still answered | {_share(human, asked)} |")
    triaged = [r for r in ok if r.get("triage_kind")]
    if triaged:
        kind_right = sum(r["triage_kind_correct"] for r in triaged)
        out.append(f"| triage: bug kind right | {_share(kind_right, len(triaged))} |")
        out.append(f"| triage: buggy function among suspects | "
                   f"{_share(sum(r['triage_suspect_hit'] for r in triaged), len(triaged))} |")
    explained = [r for r in ok if r.get("explain_confidence")]
    if explained:
        out.append(f"| suggested fix restores the original line | "
                   f"{_share(sum(r['fix_correct'] for r in explained), len(explained))} |")
    costs = [r["cost_usd"] for r in ok if r.get("cost_usd") is not None]
    out.append(f"| requests per session | {statistics.mean(r['requests'] for r in ok):.1f} |")
    if costs:
        out.append(f"| cost | ${sum(costs):.3f} total, ${statistics.mean(costs):.4f} per session |")
    out.append(f"| wall time per session | {statistics.mean(r['seconds'] for r in ok):.0f} s |")
    out += ["", "## Claude's answers against the ground truth", "",
            "| question | answers | right | wrong | 'unknown' | not gradable |", "|---|---|---|---|---|---|"]
    for kind in ("call", "line"):
        sel = [q for q in questions if q["kind"] == kind]
        if not sel:
            continue
        counts = {o: sum(1 for q in sel if q["outcome"] == o)
                  for o in ("correct", "wrong", "abstained", "ungradable")}
        decided = counts["correct"] + counts["wrong"]
        misleading = sum(int(q.get("misleading") or 0) for q in sel)
        out.append(f"| {kind} | {len(sel)} | {_share(counts['correct'], decided)} | {counts['wrong']} "
                   f"({misleading} misleading) | {counts['abstained']} | {counts['ungradable']} |")
    out += ["", "Calibration (graded call and line answers):", "",
            "| stated confidence | answers | right |", "|---|---|---|"]
    for lo, hi in ((0.0, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 1.01)):
        sel = [q for q in questions if q["outcome"] in ("correct", "wrong") and lo <= q["confidence"] < hi]
        right = sum(1 for q in sel if q["outcome"] == "correct")
        out.append(f"| {lo:.1f}-{min(hi, 1.0):.1f} | {len(sel)} | {_share(right, len(sel))} |")
    confusion = {}
    for q in questions:
        if q["outcome"] == "wrong":
            key = (q["kind"], q["truth"], q["claude"])
            confusion[key] = confusion.get(key, 0) + 1
    if confusion:
        out += ["", "Wrong answers (question, truth -> Claude):", ""]
        out += [f"- {kind}: {t} -> {c}: {n}" for (kind, t, c), n in
                sorted(confusion.items(), key=lambda kv: -kv[1])]
    out += ["", "## Per bug", "",
            "| bug | kind | found | line | Q | Claude right / answers | triage | fix | $ |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            out.append(f"| {r['bug']} | {r.get('category', '')} | error | | | | | | |")
            continue
        triage = (f"{r['triage_kind']}{' *' if r['triage_suspect_hit'] else ''}"
                  if r.get("triage_kind") else "-")
        fix = ("✓" if r["fix_correct"] else "✗") if r.get("explain_confidence") else "-"
        cost = f"{r['cost_usd']:.4f}" if r.get("cost_usd") is not None else "-"
        out.append(f"| {r['bug']} | {r['category']} | {'✓' if r['found_function'] else '✗'} | "
                   f"{'✓' if r['line_in_region'] else '✗'} | {r['call_questions']}+{r['line_questions']} | "
                   f"{r['claude_correct']}/{r['claude_answers']} | {triage} | {fix} | {cost} |")
    out += ["", "triage: the kind Claude chose; * = the buggy function was among its suspects."]
    return "\n".join(out) + "\n"
