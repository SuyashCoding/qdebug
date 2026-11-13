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

from dataclasses import dataclass, field

from qdebug.oracles import Question

REFUTED_OUTPUT = "refuted_output"
REFUTED_INPUTS = "refuted_inputs"


@dataclass
class ZoomResult:
    path: str
    func: str
    status: str                       # localized / refuted_* / not_found / quit
    checkpoints: int = 0
    lo: int | None = None
    hi: int | None = None
    region: list = field(default_factory=list)          # line numbers
    ranked_lines: list = field(default_factory=list)    # [(line, ochiai, text)]
    transcript: list = field(default_factory=list)
    trace_time: float = 0.0

    @property
    def questions(self):
        return len(self.transcript)


def next_probe(answers, n, inputs_accepted):
    """Decide what to ask next from the ordered [(index, verdict)] list.

    Returns ("ask", index), (REFUTED_*, None) or ("done", (lo, hi)).
    """
    given = dict(answers)
    if n not in given:
        return "ask", n
    if given[n] == "yes":
        return REFUTED_OUTPUT, None
    if not inputs_accepted:
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


def zoom_into(session, node, node_verdict):
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
    while True:
        action, arg = next_probe(answers, n, inputs_accepted=(node_verdict == "no"))
        if action != "ask":
            break
        question = Question("line", node, func_info, number=len(result.transcript) + 1,
                            checkpoint=cps[arg], file_lines=file_lines)
        answer = session.oracle.judge(question, session)
        if answer.action == "quit":
            action = "quit"
            break
        if answer.action == "undo":
            if answers:
                answers.pop()
                result.transcript.pop()
            continue
        answers.append((arg, answer.verdict))
        cp = cps[arg]
        result.transcript.append({
            "number": question.number, "checkpoint": arg, "kind": cp["kind"],
            "line": cp["line"], "occurrence": cp["occurrence"],
            "verdict": answer.verdict, "note": answer.note,
        })
    if action in (REFUTED_OUTPUT, REFUTED_INPUTS):
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
