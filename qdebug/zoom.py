"""Sub-function localization ("zoom-in") inside the buggy call.

The failing test is re-run while snapshotting the locals of the one target
call at every line event (the state *before* that line runs) and at return.
We then binary-search the checkpoint sequence for the first state that the
oracle judges incorrect. The lines executed between the last correct and the
first incorrect checkpoint form the reported region, ranked by Ochiai.

Before the search the two ends are checked:
* end state correct   -> the call is not buggy after all ("refuted_output").
  Always asked: it is an independent check of the call-level answer, which
  matters when the oracle can be wrong.
* entry state wrong   -> its inputs were already infected ("refuted_inputs").
  Skipped when the call itself was answered "no" (its inputs were accepted).
A refuted candidate makes the session try the next hypothesis.
"""

import math
from dataclasses import dataclass, field

from qdebug.oracles import Question

REFUTED_OUTPUT = "refuted_output"
REFUTED_INPUTS = "refuted_inputs"
UNDECIDED = "undecided"   # the end state could not be judged, and nothing else blames the call


@dataclass
class ZoomResult:
    path: str
    func: str
    status: str                       # localized / refuted_* / undecided / not_found / quit
    checkpoints: int = 0
    lo: int | None = None
    hi: int | None = None
    region: list = field(default_factory=list)          # line numbers
    ranked_lines: list = field(default_factory=list)    # [(line, ochiai, text)]
    callees: list | None = None       # paths of the calls made inside the region (None: unknown)
    transcript: list = field(default_factory=list)
    trace_time: float = 0.0

    @property
    def questions(self):
        return len(self.transcript)


def next_probe(answers, n, inputs_accepted):
    """Decide what to ask next from the ordered [(index, verdict)] list.

    Returns ("ask", index), (REFUTED_*, None), (UNDECIDED, None) or
    ("done", (lo, hi)). inputs_accepted: the call itself was judged wrong,
    so its inputs were accepted and its output is known to be wrong.
    """
    given = dict(answers)
    if n not in given:
        return "ask", n
    if given[n] == "yes":
        return REFUTED_OUTPUT, None
    if not inputs_accepted:
        if given[n] != "no":
            return UNDECIDED, None  # nothing says this call is wrong: do not search inside it
        if 0 not in given:
            return "ask", 0
        if given[0] == "no":
            return REFUTED_INPUTS, None
    lo, hi = 0, n
    for index, verdict in answers:
        if lo < index < hi:
            if verdict == "yes":
                lo = index
            elif verdict == "no":
                hi = index
    options = [i for i in range(lo + 1, hi) if i not in given]
    if not options:
        return "done", (lo, hi)
    mid = (lo + hi) / 2
    return "ask", min(options, key=lambda i: (abs(i - mid), i))


def change_point_posterior(answers, n, errors=None, default_error=0.1):
    """P(the state first goes wrong at checkpoint k) for k = 1..n, as a list indexed by k.

    Hypothesis k: checkpoints 0..k-1 are right and k..n are wrong. A "yes" at
    checkpoint i is consistent with k > i, a "no" with k <= i; each answer
    counts with likelihood 1 - e if consistent and e otherwise, where e is
    that answer's error rate. Answers at 0 and n are the end checks.
    """
    errors = errors or {}
    logs = [0.0] * (n + 1)
    logs[0] = -math.inf
    for position, (index, verdict) in enumerate(answers):
        if verdict not in ("yes", "no"):
            continue
        e = errors.get(position, default_error)
        good, bad = math.log(1 - e), math.log(e)
        for k in range(1, n + 1):
            consistent = (k > index) if verdict == "yes" else (k <= index)
            logs[k] += good if consistent else bad
    top = max(logs[1:])
    weights = [0.0] + [math.exp(v - top) for v in logs[1:]]
    total = sum(weights)
    return [w / total for w in weights]


def next_probe_bayes(answers, n, inputs_accepted, errors=None, default_error=0.1, confidence=0.6,
                     extra=4):
    """Like next_probe, but a wrong answer can be outvoted instead of misleading the search.

    The end checks are the same. Inside the call, the next checkpoint is the
    unasked one that splits the posterior over change points most evenly
    (the noisy analogue of the midpoint). The search stops when the likeliest
    change point k holds `confidence` of the posterior and is bracketed: the
    checkpoint before it was judged right and k itself wrong. Without errors
    that is exactly when the binary search stops; when answers contradict
    each other it keeps asking where the posterior is split. It never asks
    more than ceil(log2(n)) + extra questions inside the call.
    """
    first = next_probe(answers, n, inputs_accepted)
    if first[0] not in ("ask", "done") or (first[0] == "ask" and first[1] in (0, n)):
        return first
    post = change_point_posterior(answers, n, errors, default_error)
    best = max(range(1, n + 1), key=lambda k: (post[k], -k))
    given = {}
    for index, verdict in answers:
        given[index] = verdict
    before_right = best - 1 == 0 or given.get(best - 1) == "yes"
    at_wrong = given.get(best) == "no"
    options = [i for i in range(1, n) if i not in given]
    inside = sum(1 for index, _ in answers if 0 < index < n)
    settled = before_right and at_wrong and post[best] >= confidence
    out_of_budget = inside >= math.ceil(math.log2(max(n, 2))) + extra
    if settled or not options or out_of_budget:
        return "done", (best - 1, best)
    cumulative, below = {}, 0.0
    for i in range(1, n):
        below += post[i]
        cumulative[i] = below
    return "ask", min(options, key=lambda i: (abs(cumulative[i] - 0.5), i))


def zoom_into(session, node, node_verdict, call_error=None):
    """Line-level search inside node's call. call_error: the error rate of the call-level answer.

    The end check asks again, in another form, what the call question asked.
    When the two disagree and both come with a stated confidence, the more
    confident one wins: a less sure "the end state is right" does not refute
    a surer "this call is wrong", and the search goes on inside the call.
    """
    cfg = session.config
    data = session.run(cfg.project, "zoom", test=session.test_id, target=node.path,
                       max_repr=cfg.max_repr)
    record = next(iter(data["tests"].values()))
    cps = record.get("checkpoints", [])
    result = ZoomResult(path=node.path, func=node.func, status="not_found",
                        checkpoints=len(cps), trace_time=record.get("call_time", 0.0))
    if not record.get("found") or len(cps) < 2:
        return result
    n = len(cps) - 1
    func_info = session.functions.get(node.func)
    file_lines = session.file_lines(node.file)
    answers = []
    errors = {}  # position in answers -> that answer's own error rate
    tuning = getattr(session, "tuning", None)
    bayes = (cfg.zoom_search or (tuning.zoom_search if tuning is not None else "binary")) == "bayes"
    outvoted = False
    while True:
        if bayes:
            action, arg = next_probe_bayes(answers, n, node_verdict == "no", errors, cfg.error_rate)
        else:
            action, arg = next_probe(answers, n, inputs_accepted=(node_verdict == "no"))
        if action == REFUTED_OUTPUT and node_verdict == "no" and call_error is not None and not outvoted:
            position = next(i for i, (index, _) in enumerate(answers) if index == n)
            end_error = errors.get(position)
            if end_error is not None and end_error > call_error:
                outvoted = True
                answers[position] = (n, "no")
                result.transcript[position]["note"] += " (outvoted by the surer answer about the call)"
                continue
        if action != "ask":
            break
        previous = next((cps[i]["line"] for i in range(arg - 1, -1, -1) if cps[i]["kind"] == "line"), None)
        question = Question("line", node, func_info, number=len(result.transcript) + 1,
                            checkpoint=cps[arg], file_lines=file_lines,
                            meta={"previous_line": previous} if previous else {})
        answer = session.oracle.judge(question, session)
        if answer.action == "quit":
            action = "quit"
            break
        if answer.action == "undo":
            if answers:
                errors.pop(len(answers) - 1, None)
                answers.pop()
                result.transcript.pop()
            continue
        verdict = answer.verdict
        if verdict in ("yes", "no") and answer.confidence < cfg.min_line_confidence:
            verdict = "unknown"  # an unsure answer would steer the binary search; step around it
        error = session._answer_error(answer.confidence) if hasattr(session, "_answer_error") else None
        if error is not None:
            errors[len(answers)] = error
        answers.append((arg, verdict))
        cp = cps[arg]
        result.transcript.append({
            "number": question.number, "checkpoint": arg, "kind": cp["kind"],
            "line": cp["line"], "occurrence": cp["occurrence"],
            "verdict": verdict, "note": answer.note,
        })
    if action in (REFUTED_OUTPUT, REFUTED_INPUTS, UNDECIDED):
        result.status = action
        return result
    if action == "quit":
        result.status = "quit"
        lo, hi = 0, n
        for index, verdict in answers:
            if lo < index < hi:
                lo, hi = (index, hi) if verdict == "yes" else (lo, index) if verdict == "no" else (lo, hi)
    else:
        result.status = "localized"
        lo, hi = arg
    result.lo, result.hi = lo, hi
    if "calls" in cps[lo] and "calls" in cps[hi]:
        result.callees = list(record.get("callees", [])[cps[lo]["calls"]:cps[hi]["calls"]])
    region = []
    for i in range(lo, hi):
        if cps[i]["kind"] == "line" and cps[i]["line"] not in region:
            region.append(cps[i]["line"])
    result.region = region
    scores = session.ranking.line_scores
    result.ranked_lines = sorted(
        ((line, scores.get((node.file, line), 0.0), file_lines[line - 1].strip()) for line in region),
        key=lambda t: (-t[1], t[0]))
    return result
