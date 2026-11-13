import pathlib
import re

import pytest

from helpers import make_tree, snap
from qdebug.oracles import (
    Answer,
    GroundTruthOracle,
    HumanOracle,
    LLMOracle,
    NoisyOracle,
    Oracle,
    Question,
)
from qdebug.zoom import REFUTED_INPUTS, REFUTED_OUTPUT, next_probe


class AlwaysYes(Oracle):
    name = "yes"

    def judge(self, question, ctx=None):
        return Answer("yes")


def _q():
    return Question("call", make_tree(("test", [("a", [])])).nodes[1])


def test_noisy_oracle_is_deterministic_for_a_seed():
    def run(seed):
        oracle = NoisyOracle(AlwaysYes(), 0.3, seed=seed)
        return [oracle.judge(_q()).verdict for _ in range(200)]

    assert run(7) == run(7)
    assert run(7) != run(8)
    flips = run(7).count("no")
    assert 30 < flips < 90


def test_noisy_oracle_extremes():
    assert all(NoisyOracle(AlwaysYes(), 0.0).judge(_q()).verdict == "yes" for _ in range(50))
    assert all(NoisyOracle(AlwaysYes(), 1.0).judge(_q()).verdict == "no" for _ in range(50))


def test_llm_oracle_is_a_stub():
    with pytest.raises(NotImplementedError):
        LLMOracle().judge(_q())


def _fixed_run(nodes, checkpoints=None):
    def run(project, mode, test=None, monitored=None, target=None, max_repr=300):
        if mode == "tree":
            return {"tests": {test: {"nodes": nodes}}}
        if mode == "zoom":
            return {"tests": {test: {"found": target in (checkpoints or {}),
                                     "checkpoints": (checkpoints or {}).get(target, [])}}}
        raise AssertionError(mode)
    return run


def _node_dict(path, inp, out, parent=None, node_id=0):
    return {"id": node_id, "path": path, "qualname": path.split("/")[-1].split("#")[0],
            "func": "m.py::f", "file": "m.py", "line": 1, "parent": parent, "children": [],
            "monitored": True, "own_lines": [], "args": {"x": snap(inp)}, "after": {},
            "mutated": [], "ret": snap(out), "exc": None}


def test_ground_truth_call_verdicts():
    fixed = [_node_dict("test", "-", "-"), _node_dict("test/a#0", "1", "2", 0, 1)]
    fixed[0]["children"] = [1]
    oracle = GroundTruthOracle("fixed", "t", run=_fixed_run(fixed))

    def ask(path, inp, out):
        tree = make_tree(("test", [("a", []), ("b", [])]), values={"a": (inp, out)})
        node = tree.by_path[path]
        return oracle.judge(Question("call", node)).verdict

    assert ask("test/a#0", "1", "2") == "yes"
    assert ask("test/a#0", "1", "3") == "no"
    assert ask("test/a#0", "9", "2") == "inadmissible"  # inputs already infected
    assert ask("test/b#0", "1", "2") == "unknown"       # call missing in the fixed run


def test_ground_truth_mutation_counts_as_output():
    fixed = [_node_dict("test", "-", "-"), _node_dict("test/a#0", "[2, 1]", "1", 0, 1)]
    oracle = GroundTruthOracle("fixed", "t", run=_fixed_run(fixed))
    tree = make_tree(("test", [("a", [])]), values={"a": ("[2, 1]", "1")})
    node = tree.nodes[1]
    assert oracle.judge(Question("call", node)).verdict == "yes"
    node.after = {"x": snap("[1, 2]")}
    node.mutated = ["x"]
    assert oracle.judge(Question("call", node)).verdict == "no"


def _cp(index, kind, line, occ, locals_, ret=None, aliases=()):
    return {"index": index, "kind": kind, "line": line, "occurrence": occ,
            "locals": {k: snap(v) for k, v in locals_.items()}, "aliases": list(aliases),
            "ret": snap(ret) if ret is not None else None, "exc": None}


def test_ground_truth_line_verdicts():
    fixed_cps = [_cp(0, "line", 10, 1, {"q": "10"}), _cp(1, "line", 11, 1, {"q": "10"}),
                 _cp(2, "return", None, 1, {"q": "10"}, ret="0.1")]
    oracle = GroundTruthOracle("fixed", "t", run=_fixed_run([], {"test/a#0": fixed_cps}))
    node = make_tree(("test", [("a", [])])).nodes[1]

    def ask(cp):
        return oracle.judge(Question("line", node, checkpoint=cp)).verdict

    assert ask(_cp(0, "line", 10, 1, {"q": "10"})) == "yes"
    assert ask(_cp(1, "line", 12, 1, {"q": "10"})) == "no"     # fixed run never reaches line 12
    assert ask(_cp(2, "return", None, 1, {"q": "10"}, ret="0.05")) == "no"
    assert ask(_cp(0, "line", 10, 1, {"q": "10"}, aliases=[["a", "b"]])) == "no"


def test_next_probe_binary_search():
    n = 10  # checkpoints 0..10, first wrong state at 7

    def oracle(i):
        return "no" if i >= 7 else "yes"

    answers = []
    while True:
        action, arg = next_probe(answers, n, inputs_accepted=True)
        if action != "ask":
            break
        answers.append((arg, oracle(arg)))
    assert action == "done" and arg == (6, 7)
    assert answers[0] == (10, "no")       # the end state is always verified
    assert len(answers) <= 5


def test_next_probe_refutations_and_unknowns():
    assert next_probe([], 5, inputs_accepted=False) == ("ask", 5)
    assert next_probe([(5, "yes")], 5, inputs_accepted=False) == (REFUTED_OUTPUT, None)
    assert next_probe([(5, "no")], 5, inputs_accepted=False) == ("ask", 0)
    assert next_probe([(5, "no"), (0, "no")], 5, inputs_accepted=False) == (REFUTED_INPUTS, None)
    # unknown answers are skipped; with everything unknown the region is the whole range
    answers = [(4, "no")] + [(i, "unknown") for i in (1, 2, 3)]
    assert next_probe(answers, 4, inputs_accepted=True) == ("done", (0, 4))


def test_human_oracle_commands():
    tree = make_tree(("test", [("a", [])]))
    printed = []

    class Ctx:
        def explain(self, node):
            return "WHY"

        def render_tree(self):
            return "TREE"

    def judge(keys):
        it = iter(keys)
        oracle = HumanOracle(input_fn=lambda prompt: next(it), print_fn=printed.append)
        return oracle.judge(Question("call", tree.nodes[1]), Ctx())

    assert judge(["w", "tree", "y"]).verdict == "yes"
    assert "WHY" in printed and "TREE" in printed
    assert judge(["n"]).verdict == "no"
    assert judge(["?"]).verdict == "unknown"
    assert judge(["i"]).verdict == "inadmissible"
    assert judge(["t"]).action == "trust"
    assert judge(["u"]).action == "undo"
    assert judge(["bogus", "q"]).action == "quit"


def test_no_network_or_llm_usage_anywhere():
    root = pathlib.Path(__file__).resolve().parent.parent
    pattern = re.compile(r"^\s*(import|from)\s+(socket|urllib|http|requests|httpx|aiohttp|openai|anthropic)\b",
                         re.M)
    offenders = [str(p) for d in ("qdebug", "sample_project") for p in (root / d).rglob("*.py")
                 if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
