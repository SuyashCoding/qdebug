"""Oracles judge questions about the failing execution.

Two question kinds:

* "call": given these inputs, is this call's output (return value or
  exception, plus any mutation of its arguments) correct?
* "line": inside the buggy call, is the program state (locals) at this
  checkpoint correct? A line checkpoint is the state *before* that line runs.

judge(question, ctx) returns an Answer. Verdicts: yes, no, unknown, and
inadmissible ("I can't judge the output because the inputs are already
wrong", a refinement of unknown). Interactive oracles may also return control
actions (trust / undo / quit) which the session handles.
"""

import random
from dataclasses import dataclass, field

from qdebug.runner import invoke
from qdebug.tracer import truncate
from qdebug.tree import ExecutionTree

VERDICTS = ("yes", "no", "unknown", "inadmissible")


@dataclass
class Question:
    kind: str                      # "call" or "line"
    node: object                   # tree.Node
    func_info: object = None       # spectrum.FuncInfo (source, signature, docstring)
    number: int = 0
    checkpoint: dict | None = None  # for "line" questions
    file_lines: list | None = None  # source of the node's file, for display
    meta: dict = field(default_factory=dict)


@dataclass
class Answer:
    verdict: str | None            # yes / no / unknown, or None for pure actions
    confidence: float = 1.0
    action: str | None = None      # None, "trust", "undo", "quit"
    note: str = ""


class Oracle:
    """Interface: judge(question, ctx=None) -> Answer."""

    name = "oracle"

    def judge(self, question, ctx=None):  # pragma: no cover - abstract
        raise NotImplementedError


# --------------------------------------------------------------------------
# formatting shared by the human oracle and the report

def describe_call(node, func_info=None, width=110, max_repr=300):
    lines = []
    sig = func_info.signature if func_info else f"{node.qualname}(...)"
    lines.append(f"{node.qualname}   [{sig}]   {node.file}:{node.line}")
    if func_info and func_info.doc:
        doc = func_info.doc.strip().splitlines()
        lines.append(f'  """{doc[0]}' + (' ..."""' if len(doc) > 1 else '"""'))
    lines.append(f"  call path: {node.path}")
    lines.append("  inputs:")
    for name, snap in (node.args or {}).items():
        lines.append(f"    {name:<10} = {truncate(snap['short'], max_repr)}")
    if node.exc:
        lines.append(f"  raised:   {truncate(node.exc['short'], max_repr)}")
    else:
        lines.append(f"  returned: {truncate(node.ret['short'], max_repr) if node.ret else '?'}")
    if node.mutated:
        lines.append("  mutated arguments (before -> after):")
        for name in node.mutated:
            lines.append(f"    {name}:")
            lines.append(f"      before: {truncate(node.args[name]['short'], max_repr)}")
            lines.append(f"      after:  {truncate(node.after[name]['short'], max_repr)}")
    else:
        lines.append("  mutated arguments: none")
    return "\n".join(truncate(line, width) if len(line) > width * 3 else line for line in lines)


def describe_checkpoint(question, context=3, max_repr=300):
    node, cp = question.node, question.checkpoint
    out = [f"Inside {node.qualname}  ({node.file})  call path: {node.path}"]
    if cp["kind"] == "line":
        out.append(f"State just BEFORE line {cp['line']} runs (visit #{cp['occurrence']}):")
    else:
        out.append("State at RETURN:")
    if question.func_info and question.file_lines and cp["kind"] == "line":
        fi = question.func_info
        for no in range(max(fi.line, cp["line"] - context), min(fi.end_line, cp["line"] + context) + 1):
            mark = "->" if no == cp["line"] else "  "
            out.append(f"  {mark}{no:4d} | {question.file_lines[no - 1]}")
    out.append("  locals:")
    for name, snap in cp["locals"].items():
        out.append(f"    {name:<18} = {truncate(snap['short'], max_repr)}")
    for group in cp.get("aliases", []):
        out.append(f"    (same object: {' is '.join(group)})")
    if cp["kind"] == "return":
        if cp.get("exc"):
            out.append(f"  raising: {cp['exc']['short']}")
        else:
            out.append(f"  returning: {cp['ret']['short'] if cp.get('ret') else '?'}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# human

CALL_HELP = """  y  correct        n  wrong          ?  don't know
  i  the inputs are already wrong (can't judge the output)
  t  trust this function (all its calls are correct)
  s  show source    w  why this question    tree  show the execution tree
  u  undo last answer                     q  quit and report"""
LINE_HELP = """  y  state is correct    n  state is wrong    ?  don't know
  s  show the whole function    u  undo last line answer    q  stop zooming"""


class HumanOracle(Oracle):
    """Interactive command-line oracle."""

    name = "human"

    call_prompt = "Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > "
    line_prompt = "Is this state correct? [y/n/?/s/u/q/h] > "
    call_help = CALL_HELP
    line_help = LINE_HELP

    def __init__(self, input_fn=input, print_fn=print, max_repr=300):
        self.input_fn = input_fn
        self.print = print_fn
        self.max_repr = max_repr

    def _read(self, prompt):
        try:
            return self.input_fn(prompt).strip().lower()
        except EOFError:
            return "q"

    def show_call(self, question, ctx):
        self.print("")
        header = f"── Question {question.number}"
        if question.meta.get("tier") is not None:
            header += f"  (tier {question.meta['tier']}%)"
        self.print(header + " " + "─" * max(0, 60 - len(header)))
        self.print(describe_call(question.node, question.func_info, max_repr=self.max_repr))

    def show_line(self, question, ctx):
        self.print("")
        self.print(f"── Line question {question.number} " + "─" * 40)
        self.print(describe_checkpoint(question, max_repr=self.max_repr))

    def judge(self, question, ctx=None):
        if question.kind == "call":
            self.show_call(question, ctx)
            prompt, helptext = self.call_prompt, self.call_help
        else:
            self.show_line(question, ctx)
            prompt, helptext = self.line_prompt, self.line_help
        while True:
            cmd = self._read(prompt)
            if cmd in ("y", "yes"):
                return Answer("yes")
            if cmd in ("n", "no"):
                return Answer("no")
            if cmd in ("?", "d", "dk"):
                return Answer("unknown")
            if cmd in ("i", "inadmissible") and question.kind == "call":
                return Answer("inadmissible")
            if cmd in ("q", "quit"):
                return Answer(None, action="quit")
            if cmd in ("u", "undo"):
                return Answer(None, action="undo")
            if cmd in ("t", "trust") and question.kind == "call":
                return Answer("yes", action="trust")
            if cmd in ("s", "source"):
                fi = question.func_info
                if fi is None:
                    self.print("  (source not available)")
                else:
                    for i, text in enumerate(fi.source.splitlines(), fi.line):
                        self.print(f"  {i:4d} | {text}")
                continue
            if cmd in ("w", "why") and question.kind == "call" and ctx is not None:
                self.print(ctx.explain(question.node))
                continue
            if cmd == "tree" and question.kind == "call" and ctx is not None:
                self.print(ctx.render_tree())
                continue
            self.print(helptext)


# --------------------------------------------------------------------------
# simulated ground truth

class GroundTruthOracle(Oracle):
    """Answers by comparing against the same test run on the fixed program.

    "call": yes iff the fixed run has a call with the same path id, equal
    inputs and equal outputs (return, exception, post-call argument state),
    all compared by full repr. If the path is missing the answer is
    "unknown". If the inputs differ, the inputs are already infected and the
    output cannot be judged on its own: the answer is "inadmissible", the
    refinement of "unknown" that says why (the session downgrades it to plain
    "unknown" when inadmissible answers are disabled).

    "line": compares locals (and aliasing between locals) at the same
    (line, occurrence) checkpoint of the same call. A checkpoint the fixed
    run never reaches means control flow already diverged: "no".
    """

    name = "truth"

    def __init__(self, fixed_project, test_id, run=invoke, max_repr=300):
        self.fixed_project = fixed_project
        self.test_id = test_id
        self.run = run
        self.max_repr = max_repr
        self._tree = None
        self._zooms = {}

    def fixed_tree(self):
        if self._tree is None:
            data = self.run(self.fixed_project, "tree", test=self.test_id, monitored=None,
                            max_repr=self.max_repr)
            record = next(iter(data["tests"].values()))
            self._tree = ExecutionTree.from_json(record.get("nodes", []), self.test_id)
        return self._tree

    def fixed_checkpoints(self, path):
        if path not in self._zooms:
            data = self.run(self.fixed_project, "zoom", test=self.test_id, target=path,
                            max_repr=self.max_repr)
            record = next(iter(data["tests"].values()))
            self._zooms[path] = record if record.get("found") else None
        return self._zooms[path]

    def judge(self, question, ctx=None):
        if question.kind == "call":
            return self._judge_call(question.node)
        return self._judge_line(question.node, question.checkpoint)

    def _judge_call(self, node):
        if node.args is None:
            return Answer("unknown", note="no values recorded")
        fixed = self.fixed_tree().by_path.get(node.path)
        if fixed is None or fixed.args is None:
            return Answer("unknown", note="call does not exist in the fixed run")
        if fixed.input_key() != node.input_key():
            return Answer("inadmissible", note="inputs differ from the fixed run (already infected)")
        if fixed.output_key() == node.output_key():
            return Answer("yes")
        return Answer("no")

    @staticmethod
    def _cp_key(cp):
        return (cp["kind"], cp["line"], cp["occurrence"])

    def _judge_line(self, node, cp):
        record = self.fixed_checkpoints(node.path)
        if record is None:
            return Answer("unknown", note="call does not exist in the fixed run")
        fixed = {self._cp_key(c): c for c in record["checkpoints"]}
        other = fixed.get(self._cp_key(cp))
        if other is None:
            return Answer("no", note="the fixed program never reaches this checkpoint")
        same = ({k: v["full"] for k, v in cp["locals"].items()}
                == {k: v["full"] for k, v in other["locals"].items()}
                and cp.get("aliases", []) == other.get("aliases", []))
        if cp["kind"] == "return":
            for key in ("ret", "exc"):
                a, b = cp.get(key), other.get(key)
                same = same and (a and a["full"]) == (b and b["full"])
        return Answer("yes" if same else "no")


class NoisyOracle(Oracle):
    """Wraps another oracle and flips its yes/no verdicts with probability flip_prob."""

    def __init__(self, base, flip_prob, seed=0):
        self.base = base
        self.flip_prob = flip_prob
        self.rng = random.Random(seed)
        self.name = f"noisy({base.name},{flip_prob})"
        self.flips = 0

    def judge(self, question, ctx=None):
        answer = self.base.judge(question, ctx)
        draw = self.rng.random()  # drawn for every question to keep runs aligned
        if answer.verdict in ("yes", "no") and answer.action is None and draw < self.flip_prob:
            self.flips += 1
            flipped = "no" if answer.verdict == "yes" else "yes"
            return Answer(flipped, answer.confidence, None, note="flipped by NoisyOracle")
        return answer


class LLMOracle(Oracle):
    """Placeholder for a language-model oracle. Not implemented on purpose.

    Intended design: for a "call" question the model would see the function's
    signature and docstring, the caller's context (the caller's signature,
    docstring and the line that makes the call), the concrete inputs and
    outputs (including argument mutations), and examples of the same function
    taken from *passing* tests (input/output pairs recorded in spectrum or tree
    mode). It would deliberately NOT see the function body: an LLM shown the
    buggy implementation tends to rationalize the buggy behaviour as intended.
    It would answer yes/no/unknown with a calibrated confidence that the
    session can map onto a per-answer error rate in belief.Belief. For "line"
    questions it would see the statement just executed plus the locals before
    and after. Plug it in by implementing judge() and registering it in
    cli.make_oracle.
    """

    name = "llm"

    def judge(self, question, ctx=None):
        raise NotImplementedError("LLMOracle is a design stub; no LLM is called in this prototype")
