"""Session loop: memoization, trust and undo, with a fake runner (no subprocesses)."""

import json

import pytest

from helpers import ScriptedOracle, make_tree
from qdebug.oracles import Answer, Oracle
from qdebug.session import DebugSession, SessionConfig

TEST_ID = "tests/test_m.py::test"


def fake_runner(tree):
    nodes = [
        {"id": n.id, "path": n.path, "qualname": n.qualname, "func": n.func, "file": n.file,
         "line": n.line, "parent": n.parent, "children": n.children, "monitored": n.monitored,
         "own_lines": [], "args": n.args, "after": n.after, "mutated": n.mutated,
         "ret": n.ret, "exc": n.exc}
        for n in tree.nodes
    ]
    funcs = sorted({n.func for n in tree.nodes})

    def run(project, mode, test=None, monitored=None, target=None, max_repr=300):
        if mode == "spectrum":
            return {"tests": {TEST_ID: {"outcome": "failed", "lines": [], "functions": funcs},
                              "tests/test_m.py::ok": {"outcome": "passed", "lines": [], "functions": []}}}
        if mode == "plain":
            return {"tests": {TEST_ID: {"outcome": "failed", "call_time": 0.001}}}
        if mode == "tree":
            return {"tests": {TEST_ID: {"outcome": "failed", "nodes": json.loads(json.dumps(nodes)),
                                        "call_time": 0.002}}, "wall_time": 0.1}
        raise AssertionError(f"unexpected mode {mode}")

    return run


@pytest.fixture
def project(tmp_path):
    names = ["test", "a", "b", "c"]
    (tmp_path / "m.py").write_text("".join(f"def {n}(x):\n    return x\n\n\n" for n in names))
    return str(tmp_path)


def make_session(project, tree, oracle, strategy="topdown"):
    config = SessionConfig(project=project, strategy=strategy, tiers=(100,), zoom=False)
    session = DebugSession(config, oracle, run=fake_runner(tree), out=lambda *a, **k: None)
    session.run_session()
    return session


class SequenceOracle(Oracle):
    """Plays back a list of answers, recording what was asked."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    def judge(self, question, ctx=None):
        self.asked.append(question.node.path)
        return self.answers.pop(0)


def test_identical_calls_are_memoized(project):
    tree = make_tree(("test", [("a", []), ("a", []), ("a", []), ("b", [])]), values={"a": ("1", "2")})
    oracle = ScriptedOracle(tree, bug_id=4)
    session = make_session(project, tree, oracle)
    assert oracle.asked == ["test/a#0", "test/b#0"]
    eff = session.effective_answers()
    assert eff["test/a#1"] == ("yes", "memo") and eff["test/a#2"] == ("yes", "memo")
    assert session.found.path == "test/b#0"
    assert session.questions_asked == 2


def test_different_inputs_are_not_memoized(project):
    tree = make_tree(("test", [("a", []), ("a", []), ("b", [])]))  # default values differ per node
    oracle = ScriptedOracle(tree, bug_id=3)
    make_session(project, tree, oracle)
    assert oracle.asked == ["test/a#0", "test/a#1", "test/b#0"]


def test_trust_marks_every_call_of_a_function_correct(project):
    tree = make_tree(("test", [("a", []), ("b", []), ("a", []), ("c", [])]))
    oracle = SequenceOracle([Answer("yes", action="trust"), Answer("yes"), Answer("no")])
    session = make_session(project, tree, oracle)
    assert oracle.asked == ["test/a#0", "test/b#0", "test/c#0"]
    assert session.effective_answers()["test/a#1"] == ("yes", "trust")
    assert session.found.path == "test/c#0"


def test_undo_removes_the_last_answer_and_asks_again(project):
    tree = make_tree(("test", [("a", [("c", [])]), ("b", [])]))
    oracle = SequenceOracle([Answer("no"), Answer(None, action="undo"), Answer("yes"), Answer("no")])
    session = make_session(project, tree, oracle)
    assert oracle.asked == ["test/a#0", "test/a#0/c#0", "test/a#0", "test/b#0"]
    assert [(e.path, e.verdict) for e in session.log] == [("test/a#0", "yes"), ("test/b#0", "no")]
    assert session.found.path == "test/b#0"


def test_undo_also_removes_trust(project):
    tree = make_tree(("test", [("a", []), ("a", []), ("b", [])]))
    oracle = SequenceOracle([Answer("yes", action="trust"), Answer(None, action="undo"),
                             Answer("yes"), Answer("yes"), Answer("no")])
    session = make_session(project, tree, oracle)
    # trust skips a#1, so the undo is given at b's question; then a#1 is asked normally
    assert oracle.asked == ["test/a#0", "test/b#0", "test/a#0", "test/a#1", "test/b#0"]
    assert all(source == "oracle" for _, source in session.effective_answers().values())


def test_quit_stops_the_search(project):
    tree = make_tree(("test", [("a", []), ("b", [])]))
    oracle = SequenceOracle([Answer(None, action="quit")])
    session = make_session(project, tree, oracle)
    assert session.stop_reason == "user quit"
    assert session.questions_asked == 0


def test_budget_limits_questions(project):
    tree = make_tree(("test", [("a", []), ("b", []), ("c", [])]))
    config = SessionConfig(project=project, strategy="topdown", tiers=(100,), zoom=False, budget=2)
    oracle = ScriptedOracle(tree, bug_id=3)
    session = DebugSession(config, oracle, run=fake_runner(tree), out=lambda *a, **k: None)
    session.run_session()
    assert session.stop_reason == "budget"
    assert len(oracle.asked) == 2
