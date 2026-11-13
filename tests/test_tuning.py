"""The conditional search rules in tuning.py and the tracer fixes they rely on."""

import subprocess
import sys

import pytest

from helpers import make_tree
from qdebug.belief import Belief
from qdebug.strategies import ESCALATE, InfoGainStrategy
from qdebug.tracer import safe_repr
from qdebug.tree import SearchHints
from qdebug.tuning import POLICIES, assertion_cut, resolve_tuning


def flat(_func):
    return 0.5


def test_baseline_policy_turns_everything_off():
    tuning = POLICIES["baseline"]
    assert not (tuning.fallback or tuning.evidence_stop or tuning.exclude_tests)
    assert tuning.assertion_weight == 1.0 and tuning.repeat_discount == 1.0


def test_knob_overrides_keep_the_other_rules():
    tuning = resolve_tuning("tuned", assertion_weight=0.2, repeat_discount=0.7)
    assert tuning.assertion_weight == 0.2 and tuning.repeat_discount == 0.7 and tuning.fallback


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        resolve_tuning("nope")


# ------------------------------------------------------------ evidence rule

def callback_tree():
    return make_tree(("test", [("parent", [("cb", [])] * 28)]))


def test_baseline_is_confident_in_a_popular_function_without_asking():
    tree = callback_tree()
    strategy = InfoGainStrategy(flat)
    assert strategy.next_question(tree, {}) is None
    assert strategy.stop_reason == "confident"


def test_evidence_rule_checks_the_latest_call_first():
    tree = callback_tree()
    tree.hints = SearchHints(evidence_stop=True)
    node = InfoGainStrategy(flat).next_question(tree, {})
    assert node.id == len(tree) - 1


def test_evidence_rule_accepts_a_wrong_call():
    tree = callback_tree()
    tree.hints = SearchHints(evidence_stop=True)
    strategy = InfoGainStrategy(flat)
    assert strategy.next_question(tree, {tree.nodes[-1].path: "no"}) is None
    assert strategy.stop_reason == "confident"


def test_evidence_rule_escalates_when_the_blamed_function_is_opaque():
    tree = make_tree(("test", [("init", [])]), monitored=set())
    tree.hints = SearchHints(evidence_stop=True)
    strategy = InfoGainStrategy(lambda f: 0.0 if f == "m.py::test" else 0.5)
    assert strategy.next_question(tree, {}) == ESCALATE
    strategy.escalation_exhausted = True
    assert strategy.next_question(tree, {}) is None
    assert strategy.stop_reason == "unconfirmed"


# ------------------------------------------------------------ test code

def test_test_helpers_are_never_ranked_first():
    tree = make_tree(("test", [("helper", []), ("code", [])]))
    tree.hints = SearchHints(test_funcs=frozenset({"m.py::helper", "m.py::test"}))
    ranked = InfoGainStrategy(lambda f: 5.0 if f == "m.py::helper" else 0.1).result(tree, {})
    assert ranked[0][0].qualname == "code"


# ------------------------------------------------------------ priors

def test_repeat_discount_moves_mass_away_from_a_function_with_correct_calls():
    tree = make_tree(("test", [("helper", [])] * 5 + [("other", [])]))
    answers = {tree.nodes[1].path: "yes", tree.nodes[2].path: "yes"}
    plain = Belief(tree, flat).posterior(answers)[tree.nodes[-1].id]
    tree.hints = SearchHints(repeat_discount=0.7)
    assert Belief(tree, flat).posterior(answers)[tree.nodes[-1].id] > plain


def test_repeat_discount_stops_once_a_call_is_wrong():
    tree = make_tree(("test", [("helper", [])] * 5 + [("other", [])]))
    answers = {tree.nodes[1].path: "yes", tree.nodes[2].path: "no"}
    plain = Belief(tree, flat).posterior(answers)
    tree.hints = SearchHints(repeat_discount=0.7)
    assert Belief(tree, flat).posterior(answers) == pytest.approx(plain)


def test_prior_scale_multiplies_the_prior():
    tree = make_tree(("test", [("a", []), ("b", [])]))
    tree.hints = SearchHints(prior_scale=[1.0, 0.1, 1.0])
    prior = Belief(tree, flat).prior
    assert prior[2] / prior[1] == pytest.approx(10.0, rel=0.01)


# ------------------------------------------------------------ assertion cut

SOURCE = """\
class T:
    def test_it(self):
        a = make()
        self.assertEqual(a, 1)
        b = other()
        assert b == 2
        c = third()
        self.assertEqual(
            c,
            3)

    def test_loop(self):
        assert first()
        for x in xs:
            y = f(x)
            assert y

    def test_first(self):
        z = g()
        assert z
""".splitlines()


def test_cut_is_the_previous_assertion():
    assert assertion_cut(SOURCE, 2, 8) == 6


def test_cut_handles_a_failure_on_a_continuation_line():
    assert assertion_cut(SOURCE, 2, 10) == 6


def test_no_cut_inside_a_loop():
    assert assertion_cut(SOURCE, 12, 16) is None


def test_no_cut_without_an_earlier_assertion():
    assert assertion_cut(SOURCE, 18, 20) is None


def test_unparsable_source_means_no_cut():
    assert assertion_cut(["print 'py2'"], 1, 1) is None


# ------------------------------------------------------------ tracer fixes

def test_thread_ids_are_masked():
    assert "owner=?" in safe_repr(_held_lock())


def _held_lock():
    import threading
    lock = threading.RLock()
    lock.acquire()
    return lock


def run_tree(project, node_id):
    from qdebug.runner import invoke
    data = invoke(str(project), "tree", test=node_id)
    return next(iter(data["tests"].values()))["nodes"]


def write_unittest_project(path):
    (path / "core.py").write_text(
        "class Parser:\n    def __init__(self):\n        self.n = 1\n"
        "    def run(self):\n        return self.n + 1\n", encoding="utf-8")
    (path / "test_core.py").write_text(
        "import unittest\nfrom core import Parser\n\n\nclass T(unittest.TestCase):\n"
        "    def setUp(self):\n        self.p = Parser()\n\n"
        "    def test_run(self):\n        self.assertEqual(self.p.run(), 99)\n", encoding="utf-8")


def test_unittest_setup_does_not_become_the_root(tmp_path):
    write_unittest_project(tmp_path)
    nodes = run_tree(tmp_path, "test_core.py::T::test_run")
    assert nodes[0]["qualname"] == "T.test_run"
    assert [n["qualname"] for n in nodes] == ["T.test_run", "Parser.run"]
    assert nodes[0]["last_line"] == 10


def test_runner_explains_a_missing_pytest(tmp_path):
    from qdebug.runner import RunnerError, RunOptions, invoke

    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(tmp_path / "env")], check=True)
    (tmp_path / "project").mkdir()
    with pytest.raises(RunnerError, match="pytest is not installed"):
        invoke(str(tmp_path / "project"), "plain", options=RunOptions(python=str(tmp_path / "env")))
