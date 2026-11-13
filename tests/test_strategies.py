import pytest

from helpers import SMALL, ScriptedOracle, ask_loop, make_tree
from qdebug.strategies import (
    ESCALATE,
    DivideAndQueryStrategy,
    InfoGainFullStrategy,
    InfoGainStrategy,
    TopDownStrategy,
    make_strategy,
)


def flat(_func):
    return 0.1


# Deeper tree for search tests:
#   0 test
#   ├─ 1 a
#   │  ├─ 2 b
#   │  │  ├─ 3 c
#   │  │  └─ 4 d
#   │  └─ 5 e
#   ├─ 6 f
#   │  ├─ 7 g
#   │  └─ 8 h
#   │     └─ 9 i
#   └─ 10 j
DEEP = ("test", [
    ("a", [("b", [("c", []), ("d", [])]), ("e", [])]),
    ("f", [("g", []), ("h", [("i", [])])]),
    ("j", []),
])


@pytest.mark.parametrize("cls", [InfoGainStrategy, InfoGainFullStrategy, TopDownStrategy,
                                 DivideAndQueryStrategy])
@pytest.mark.parametrize("bug", range(1, 11))
def test_every_strategy_finds_every_bug(cls, bug):
    tree = make_tree(DEEP)
    oracle = ScriptedOracle(tree, bug)
    strategy = cls(flat, error_rate=0.05)
    answers = ask_loop(strategy, tree, oracle)
    top = strategy.result(tree, answers)[0][0]
    assert top.id == bug
    assert len(oracle.asked) == len(set(oracle.asked))  # nothing asked twice


def test_topdown_asks_children_in_execution_order():
    tree = make_tree(DEEP)
    oracle = ScriptedOracle(tree, 9)  # bug in i under f/h
    ask_loop(TopDownStrategy(flat), tree, oracle)
    assert oracle.asked == ["test/a#0", "test/f#0", "test/f#0/g#0", "test/f#0/h#0", "test/f#0/h#0/i#0"]


def test_topdown_skips_unknown_children():
    tree = make_tree(DEEP)
    oracle = ScriptedOracle(tree, 9, unknown={6})  # f is unknown -> bug can't be reached
    strategy = TopDownStrategy(flat)
    answers = ask_loop(strategy, tree, oracle)
    assert answers["test/f#0"] == "unknown"
    assert strategy.result(tree, answers)[0][0].id == 0  # root: every child correct/unknown
    assert strategy.stop_reason == "localized"


def test_divide_asks_closest_to_half():
    tree = make_tree(DEEP)  # 11 candidates; subtree sizes: a=5, f=4, b=3
    strategy = DivideAndQueryStrategy(flat)
    first = strategy.next_question(tree, {})
    assert first.path == "test/a#0"
    # after "a is correct", 6 candidates remain (test, f, g, h, i, j): f (4) or h (2)... f is |4-3|=1
    second = strategy.next_question(tree, {"test/a#0": "yes"})
    assert second.path in ("test/f#0", "test/f#0/h#0")


def test_hard_pruning_is_fooled_by_one_wrong_answer_but_soft_updates_are_not():
    tree = make_tree(DEEP)
    bug = 4  # d, under a/b
    lie = {"test/a#0": "yes"}  # a wrong answer on the path to the bug
    truth = ScriptedOracle(tree, bug)

    def run(strategy):
        answers = dict(lie)
        for _ in range(40):
            step = strategy.next_question(tree, answers)
            if step is None:
                break
            if step == ESCALATE:
                strategy.escalation_exhausted = True
                continue
            from qdebug.oracles import Question
            answers[step.path] = truth.judge(Question("call", step)).verdict
        return strategy.result(tree, answers)[0][0].id

    assert run(DivideAndQueryStrategy(flat)) != bug
    assert run(TopDownStrategy(flat)) != bug
    assert run(InfoGainFullStrategy(flat, error_rate=0.1, min_gain=0.001)) == bug
    # With the certificate stop, the lie makes the root look certified (all its
    # children "correct"); the session's zoom/descend phase is what recovers.
    assert run(InfoGainStrategy(flat, error_rate=0.1, min_gain=0.001)) == 0


def test_infogain_requests_escalation_when_mass_is_opaque():
    tree = make_tree(DEEP, monitored={"j"})
    strategy = InfoGainStrategy(flat)
    assert strategy.next_question(tree, {}) == ESCALATE
    strategy.escalation_exhausted = True
    assert strategy.next_question(tree, {}).path == "test/j#0"


def test_topdown_and_divide_escalate_for_opaque_nodes():
    tree = make_tree(DEEP, monitored=set())
    assert TopDownStrategy(flat).next_question(tree, {}) == ESCALATE
    assert DivideAndQueryStrategy(flat).next_question(tree, {}) == ESCALATE


def test_infogain_stops_when_confident():
    tree = make_tree(SMALL)
    strategy = InfoGainStrategy(flat, error_rate=0.01, threshold=0.9)
    answers = {"test/a#0": "no", "test/a#0/b#0": "yes", "test/a#0/c#0": "no",
               "test/a#0/c#0/d#0": "no", "test/e#0": "yes"}
    assert strategy.next_question(tree, answers) is None
    assert strategy.stop_reason == "confident"
    assert strategy.result(tree, answers)[0][0].path == "test/a#0/c#0/d#0"


def test_certificate_stop():
    tree = make_tree(DEEP)
    strategy = InfoGainStrategy(flat, error_rate=0.1)
    answers = {"test/a#0": "no", "test/a#0/b#0": "yes", "test/a#0/e#0": "inadmissible"}
    # a is wrong and all of its children are correct or inadmissible -> certified
    assert strategy.next_question(tree, answers) is None
    assert strategy.stop_reason == "certified"
    assert InfoGainFullStrategy(flat, error_rate=0.1).next_question(tree, answers) is not None


def test_make_strategy():
    assert make_strategy("divide", flat).name == "divide"
    with pytest.raises(ValueError):
        make_strategy("nope", flat)
