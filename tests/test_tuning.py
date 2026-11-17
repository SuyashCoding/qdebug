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


def run_tree(project, node_id, **options):
    from qdebug.runner import RunOptions, invoke
    data = invoke(str(project), "tree", test=node_id, options=RunOptions(**options))
    return next(iter(data["tests"].values())).get("nodes", [])


def write_unittest_project(path):
    (path / "core.py").write_text(
        "class Parser:\n    def __init__(self):\n        self.n = 1\n"
        "    def run(self):\n        return self.n + 1\n", encoding="utf-8")
    (path / "test_core.py").write_text(
        "import unittest\nfrom core import Parser\n\n\nclass T(unittest.TestCase):\n"
        "    def setUp(self):\n        self.p = Parser()\n\n"
        "    def test_run(self):\n        self.assertEqual(self.p.run(), 99)\n", encoding="utf-8")


def test_unittest_setup_is_a_call_of_the_test_not_the_root(tmp_path):
    write_unittest_project(tmp_path)
    nodes = run_tree(tmp_path, "test_core.py::T::test_run")
    assert [n["qualname"] for n in nodes] == ["T.test_run", "T.setUp", "Parser.__init__", "Parser.run"]
    assert [n["path"] for n in nodes][1:3] == ["T.test_run/T.setUp#0", "T.test_run/T.setUp#0/Parser.__init__#0"]
    assert nodes[0]["last_line"] == 10


def test_unittest_setup_is_skipped_when_only_the_call_is_traced(tmp_path):
    write_unittest_project(tmp_path)
    nodes = run_tree(tmp_path, "test_core.py::T::test_run", trace_setup=False)
    assert [n["qualname"] for n in nodes] == ["T.test_run", "Parser.run"]
    assert nodes[0]["last_line"] == 10


def test_runner_explains_a_missing_pytest(tmp_path):
    from qdebug.runner import RunnerError, RunOptions, invoke

    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(tmp_path / "env")], check=True)
    (tmp_path / "project").mkdir()
    with pytest.raises(RunnerError, match="pytest is not installed"):
        invoke(str(tmp_path / "project"), "plain", options=RunOptions(python=str(tmp_path / "env")))


# ---------------------------------------------- rules added for wider bugs

def leader_tree(callees):
    return make_tree(("test", [("lead", [(f"c{i}", []) for i in range(callees)]), ("other", [])]))


def lead_prior(func):
    return 0.9 if func == "m.py::lead" else 0.05


def test_a_wrong_leader_with_many_callees_goes_to_the_line_search():
    tree = leader_tree(6)
    tree.hints = SearchHints(zoom_fanout=5)
    strategy = InfoGainStrategy(lead_prior)
    strategy.escalation_exhausted = True
    assert strategy.next_question(tree, {}).qualname == "lead"   # asked about first
    assert strategy.next_question(tree, {"test/lead#0": "no"}) is None
    assert strategy.stop_reason == "fan-out"


def test_a_wrong_leader_with_few_callees_is_settled_by_asking_them():
    tree = leader_tree(2)
    tree.hints = SearchHints(zoom_fanout=5, settle_leader=True)
    strategy = InfoGainStrategy(flat)
    strategy.escalation_exhausted = True
    answers = {"test/lead#0": "no"}
    first = strategy.next_question(tree, answers)
    assert first.qualname in ("c0", "c1")
    answers[first.path] = "yes"
    second = strategy.next_question(tree, answers)
    answers[second.path] = "yes"
    assert {first.qualname, second.qualname} == {"c0", "c1"}
    assert strategy.next_question(tree, answers) is None
    assert strategy.stop_reason == "certified"


def test_crash_chain_follows_the_exception_down():
    from qdebug.tree import crash_chain
    tree = make_tree(("test", [("a", [("b", []), ("c", [("d", [])])]), ("e", [])]))
    for i in (0, 1, 3, 4):
        tree.nodes[i].raised = "KeyError"
    assert [n.qualname for n in crash_chain(tree)] == ["a", "c", "d"]
    tree.nodes[0].raised = "AssertionError"   # the test's own assertion failed
    assert crash_chain(tree) == []


def test_bug_kinds_adjust_the_tuned_policy():
    from qdebug.tuning import BUG_KINDS, BUG_PROFILES
    assert set(BUG_PROFILES) == set(BUG_KINDS)
    assert resolve_tuning("tuned", bug_kind="state").assertion_weight == 1.0
    assert resolve_tuning("tuned", bug_kind="crash").crash_boost == 8.0
    assert resolve_tuning("tuned", bug_kind="wrong-value") == POLICIES["tuned"]
    with pytest.raises(ValueError):
        resolve_tuning("tuned", bug_kind="cosmic-ray")


def write_fixture_project(path):
    (path / "core.py").write_text(
        "def load(name):\n    return {'a': 1}[name]\n\n\ndef use(x):\n    return x + 1\n", encoding="utf-8")
    (path / "test_core.py").write_text(
        "import pytest\nfrom core import load, use\n\n\n@pytest.fixture\ndef value():\n"
        "    return load('b')\n\n\ndef test_use(value):\n    assert use(value) == 2\n", encoding="utf-8")


def test_project_code_called_by_a_fixture_is_part_of_the_tree(tmp_path):
    write_fixture_project(tmp_path)
    nodes = run_tree(tmp_path, "test_core.py::test_use")
    assert [n["path"] for n in nodes] == ["test_use", "test_use/value#0", "test_use/value#0/load#0"]
    assert nodes[1]["call_line"] is None              # made by pytest, not by a line of the test
    assert nodes[2]["raised"] == "KeyError"            # the exception's path is recorded
    assert run_tree(tmp_path, "test_core.py::test_use", trace_setup=False) == []
