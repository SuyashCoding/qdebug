"""Final report (text) and the session JSON dump."""

import json
import os
from dataclasses import asdict
from datetime import datetime

from qdebug.tracer import truncate


def build_report(session, assistant=None):
    """Collect everything worth keeping from a finished session into a dict."""
    cfg = session.config
    tree = session.tree
    answers = session.answers()
    belief = session.belief()
    post = belief.posterior(answers)
    fpost = belief.function_posterior(post)
    found = session.found
    ranking = session.ranking

    def call_info(node):
        if node is None:
            return None
        return {
            "func": node.func, "qualname": node.qualname, "path": node.path,
            "file": node.file, "line": node.line, "monitored": node.monitored,
            "inputs": {k: v["short"] for k, v in (node.args or {}).items()},
            "output": node.output_summary(width=cfg.max_repr) if node.args else None,
            "mutated": {k: {"before": node.args[k]["short"], "after": node.after[k]["short"]}
                        for k in node.mutated} if node.args else {},
            "posterior": post[node.id],
            "function_posterior": fpost.get(node.func, 0.0),
        }

    zoom = session.zoom
    report = {
        "project": os.path.abspath(cfg.project),
        "test": session.test_id,
        "failure": session.failure_text,
        "strategy": cfg.strategy,
        "oracle": session.oracle.name,
        "config": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()},
        "stop_reason": session.stop_reason,
        "policy": cfg.policy,
        "basis": session.basis,
        "sbfl_functions": [
            {"rank": r, "func": f, "ochiai": s, "max_line": m, "failed": nf, "passed": np}
            for r, f, s, m, nf, np in ranking.function_table(10)],
        "sbfl_lines": [
            {"rank": i, "file": f, "line": n, "ochiai": ranking.line_scores[(f, n)]}
            for i, (f, n) in enumerate(ranking.ranked_lines[:10], 1)],
        "found": call_info(found),
        "found_before_zoom": call_info(session.ranked_before_zoom[0][0]) if session.ranked_before_zoom else None,
        "posterior_top5": [
            {"path": n.path, "func": n.func, "p": post[n.id]}
            for n in sorted(tree.nodes, key=lambda n: (-post[n.id], n.id))[:5]],
        "function_posterior_top5": [
            {"func": f, "p": p} for f, p in sorted(fpost.items(), key=lambda kv: -kv[1])[:5]],
        "zoom": None,
        "zoom_attempts": [
            {"path": z.path, "status": z.status, "questions": z.questions, "checkpoints": z.checkpoints}
            for z in session.zoom_results],
        "line_questions": sum(z.questions for z in session.zoom_results),
        "questions": session.questions_asked,
        "transcript": [
            {"number": e.number, "kind": e.kind, "path": e.path, "verdict": e.verdict,
             "tier": e.tier, "note": e.note, "source": e.source, **e.summary} for e in session.log],
        "escalations": session.events,
        "tiers": session.tier_runs,
        "untraced_time": session.untraced_time,
        "nodes_total": len(tree),
        "nodes_monitored": tree.monitored_count(),
        "tree": session.render_tree(found.id if found is not None and found.path in tree.by_path else None),
        "bug_kind": session.config.bug_kind or (session.triage.bug_kind if session.triage else None),
        "groups": [{"tests": [t.nodeid for t in g.tests], "reason": g.reason, "why": g.describe()}
                   for g in session.groups],
        # how many failing tests the ranking used, when only this test's group
        "ranked_against": ranking.total_failed if ranking is not session.suite_ranking else None,
        "also_explained": session.also_explained(),
        "ai": None,
    }
    if assistant is not None:
        report["ai"] = dict(assistant.report(),
                            triage=session.triage.as_dict() if session.triage else None,
                            explanation=session.explanation.as_dict() if session.explanation else None)
    if zoom is not None:
        report["zoom"] = {
            "path": zoom.path, "status": zoom.status, "checkpoints": zoom.checkpoints,
            "region": zoom.region, "file": found.file if found else None,
            "ranked_lines": [{"line": l, "ochiai": s, "text": t} for l, s, t in zoom.ranked_lines],
            "transcript": zoom.transcript, "trace_time": zoom.trace_time,
        }
    return report


def format_report(report):
    out = []
    bar = "═" * 78
    out += [bar, f"qdebug report — {report['test']}", bar]
    out.append(f"strategy: {report['strategy']}   oracle: {report['oracle']}   "
               f"stopped: {report['stop_reason']}")
    ai = report.get("ai")
    if ai:
        usage = ai["usage"]
        line = (f"claude: {ai['model']} ({ai['effort']} effort), {usage['requests']} requests, "
                f"{usage['input_tokens'] + usage['cache_read_tokens']} input / {usage['output_tokens']} "
                f"output tokens; prompt: {ai['agent']}")
        out.append(line)
        if ai.get("triage"):
            t = ai["triage"]
            out.append(f"triage: {t['bug_kind']} bug; suspects: {', '.join(t['suspects']) or '-'}; {t['reason']}")
    if report["basis"] != "answers":
        out.append("low confidence: the questions did not settle it; "
                   + ("this is SBFL's best guess" if report["basis"] == "sbfl"
                      else "the test did not reach project code"))
    out.append("")
    groups = report.get("groups") or []
    if sum(len(g["tests"]) for g in groups) > 1:
        out.append(f"Failing tests by likely bug ({len(groups)} group{'s' if len(groups) != 1 else ''}):")
        for i, g in enumerate(groups, 1):
            mark = "  <- this test's group" if report["test"] in g["tests"] else ""
            out.append(f"  group {i}: {len(g['tests'])} test(s)" + (f", {g['why']}" if g["why"] else "")
                       + mark)
            out += [f"    {t}" for t in g["tests"]]
        out.append("")
    if report.get("ranked_against"):
        out.append(f"SBFL ranking (Ochiai, this test's group of {report['ranked_against']} failing tests):")
    else:
        out.append("SBFL ranking (Ochiai, whole suite):")
    for row in report["sbfl_functions"]:
        out.append(f"  {row['rank']:>2}. {row['ochiai']:.3f}  {row['func']}  "
                   f"(failed {row['failed']}, passed {row['passed']})")
    out.append("")
    found = report["found"]
    if found:
        out.append("Buggy call found:")
        out.append(f"  function : {found['func']}  (line {found['line']})")
        out.append(f"  call path: {found['path']}")
        for k, v in found["inputs"].items():
            out.append(f"  input    : {k} = {truncate(v, 100)}")
        if found["output"]:
            out.append(f"  output   : {truncate(found['output'], 100)}")
        for k, v in found["mutated"].items():
            out.append(f"  mutates  : {k}: {truncate(v['before'], 60)} -> {truncate(v['after'], 60)}")
        out.append(f"  posterior: call {100 * found['posterior']:.1f}%, "
                   f"function {100 * found['function_posterior']:.1f}%")
    out.append("")
    out.append("Posterior top 5 (bug in this call's own code):")
    for row in report["posterior_top5"]:
        out.append(f"  {100 * row['p']:5.1f}%  {row['path']}")
    out.append("")
    zoom = report["zoom"]
    if report["zoom_attempts"]:
        out.append("Line-level zoom:")
        for z in report["zoom_attempts"]:
            out.append(f"  {z['status']:<15} {z['path']}  ({z['questions']} questions, "
                       f"{z['checkpoints']} checkpoints)")
    if zoom:
        out.append(f"  region ({len(zoom['region'])} line(s)) in {zoom['file']}:")
        for row in zoom["ranked_lines"]:
            out.append(f"    line {row['line']:>4}  ochiai {row['ochiai']:.3f}  {row['text']}")
    ai = report.get("ai")
    if ai and ai.get("explanation"):
        exp = ai["explanation"]
        out.append(f"Claude's explanation ({ai['model']}, confidence {exp['confidence']}):")
        out.append(f"  {exp['summary']}")
        if exp["explanation"]:
            out.append(f"  {exp['explanation']}")
        if exp["fix"].strip():
            out.append("  suggested fix:")
            out += [f"    {line}" for line in exp["fix"].splitlines()]
    if report.get("also_explained"):
        out.append("Other failing tests that ran this code (the same bug may explain them):")
        out += [f"  {t}" for t in report["also_explained"]]
    out.append("")
    out.append(f"Questions: {report['questions']} function-level, {report['line_questions']} line-level")
    out.append("Transcript:")
    for e in report["transcript"]:
        what = "trust" if e["kind"] == "trust" else e["verdict"]
        args = ", ".join(f"{k}={truncate(v, 30)}" for k, v in e["args"].items() if k != "self")
        tag = "Q" if e.get("source", "oracle") == "oracle" else "Z"
        out.append(f"  {tag}{e['number']:<3} [{e['tier']:>3}%] {e['qualname']}({truncate(args, 60)}) "
                   f"{truncate(e['output'], 40)}  => {what}"
                   + (f"  ({e['note']})" if e.get("note") else ""))
    if zoom:
        for e in zoom["transcript"]:
            where = f"line {e['line']} #{e['occurrence']}" if e["kind"] == "line" else "return"
            out.append(f"  L{e['number']:<3} state before {where}  => {e['verdict']}"
                       + (f"  ({e['note']})" if e.get("note") else ""))
    out.append("")
    out.append(f"Monitoring tiers (untraced test call: {1000 * report['untraced_time']:.1f} ms):")
    for t in report["tiers"]:
        out.append(f"  {t['tier']:>3}%  {t['monitored_functions']:>3} functions  "
                   f"{t['nodes']:>4} calls / {t['monitored_nodes']:>4} monitored  "
                   f"traced call {1000 * t['call_time']:.1f} ms (subprocess {t['wall_time']:.2f} s)")
    for e in report["escalations"]:
        out.append(f"  escalated {e['from']}% -> {e['to']}% after {e['after_question']} questions: {e['reason']}")
    out.append("")
    out.append("Execution tree:")
    out.append(report["tree"])
    return "\n".join(out)


def save_session(report, directory="."):
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(directory, f"session_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return path
