import pathlib
import re

from helpers import make_tree, snap
from qdebug.oracles import (
    Answer,
    GroundTruthOracle,
    HumanOracle,
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
    # a call the fixed run never makes: whatever caused it ran before it started
    assert ask("test/b#0", "1", "2") == "inadmissible"
    oracle.absent_call = "unknown"                      # the older, weaker answer
    assert ask("test/b#0", "1", "2") == "unknown"


def test_ground_truth_rejects_every_state_of_a_call_the_fixed_run_never_makes():
    oracle = GroundTruthOracle("fixed", "t", run=_fixed_run([], {}))
    node = make_tree(("test", [("a", [])])).nodes[1]
    entry = _cp(0, "line", 10, 1, {"q": "10"})
    assert oracle.judge(Question("line", node, checkpoint=entry)).verdict == "no"


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


def test_the_core_never_imports_a_network_or_llm_library():
    """Only qdebug/ai may talk to a model, and it imports the SDK lazily, inside functions."""
    root = pathlib.Path(__file__).resolve().parent.parent
    names = "socket|urllib|http|requests|httpx|httpx2|aiohttp|openai|anthropic"
    anywhere = re.compile(rf"^\s*(import|from)\s+({names})", re.M)
    top_level = re.compile(rf"^(import|from)\s+({names})", re.M)
    core = [p for d in ("qdebug", "benchmarks") for p in (root / d).rglob("*.py")
            if "variants" not in p.parts and p.parent.name != "ai"]
    assert [str(p) for p in core if anywhere.search(p.read_text(encoding="utf-8"))] == []
    ai = list((root / "qdebug" / "ai").glob("*.py"))
    assert [str(p) for p in ai if top_level.search(p.read_text(encoding="utf-8"))] == []


def _search(probe, n, k, lie_at=None):
    answers, inside = [], 0
    while True:
        action, arg = probe(answers, n, True)
        if action != "ask":
            return arg, len(answers)
        verdict = "yes" if arg < k else "no"
        if 0 < arg < n:
            inside += 1
            if inside == lie_at:
                verdict = "no" if verdict == "yes" else "yes"
        answers.append((arg, verdict))


def test_bayesian_line_search_matches_binary_search_without_errors():
    from qdebug.zoom import next_probe_bayes
    for n in range(2, 30):
        for k in range(1, n + 1):
            region, _ = _search(next_probe_bayes, n, k)
            assert region == (k - 1, k)


def test_bayesian_line_search_recovers_from_one_wrong_answer():
    from qdebug.zoom import next_probe_bayes
    cases = [(n, k) for n in range(8, 30) for k in range(1, n + 1)]
    binary = sum(_search(next_probe, n, k, lie_at=1)[0] == (k - 1, k) for n, k in cases)
    bayes = sum(_search(next_probe_bayes, n, k, lie_at=1)[0] == (k - 1, k) for n, k in cases)
    assert binary == 0 and bayes > 0.7 * len(cases)


def test_confident_noisy_oracle_reports_its_error_rate():
    from qdebug.oracles import ConfidentNoisyOracle
    oracle = ConfidentNoisyOracle(AlwaysYes(), 0.2, seed=3)
    answers = [oracle.judge(_q()) for _ in range(400)]
    wrong = [a for a in answers if a.verdict == "no"]
    assert 0.1 < len(wrong) / len(answers) < 0.3
    assert sum(a.confidence for a in wrong) / len(wrong) < sum(a.confidence for a in answers) / len(answers)


class _ZoomSession:
    """What zoom_into needs: a recorded call with 6 checkpoints, an oracle and a config."""

    def __init__(self, answers):
        from types import SimpleNamespace

        from qdebug.session import SessionConfig, answer_error
        self.config = SessionConfig(project=".", policy="tuned")
        self.tuning = SimpleNamespace(zoom_search="bayes")
        self.test_id = "t"
        cps = [_cp(i, "line", 10 + i, 1, {"x": str(i)}) for i in range(5)] + [_cp(5, "return", None, 1, {}, "r")]
        self.run = lambda *a, **k: {"tests": {"t": {"found": True, "checkpoints": cps}}}
        self.functions = {}
        self.ranking = SimpleNamespace(line_scores={})
        self.answers_given = answers
        self.oracle = self
        self._answer_error = lambda c: answer_error(c, 0.1)

    def file_lines(self, relfile):
        return [f"line {i}" for i in range(1, 30)]

    def judge(self, question, ctx=None):
        from qdebug.oracles import Answer
        index = question.checkpoint["index"]
        verdict, confidence = self.answers_given(index)
        return Answer(verdict, confidence)


def test_an_unsure_end_check_does_not_refute_a_surer_call_answer():
    from qdebug.zoom import REFUTED_OUTPUT, zoom_into
    node = make_tree(("test", [("a", [])])).nodes[1]
    # the end state is (wrongly) judged right at 60%; the state goes wrong at checkpoint 3
    answers = lambda i: ("yes", 0.6) if i == 5 else (("yes", 0.95) if i < 3 else ("no", 0.95))
    sure_call = zoom_into(_ZoomSession(answers), node, "no", call_error=0.1)
    assert sure_call.status == "localized" and sure_call.region == [12]
    unsure_call = zoom_into(_ZoomSession(answers), node, "no", call_error=0.45)
    assert unsure_call.status == REFUTED_OUTPUT
    plain = zoom_into(_ZoomSession(answers), node, "no")  # a person's answer: the end check still decides
    assert plain.status == REFUTED_OUTPUT
