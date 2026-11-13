import math

import pytest

from helpers import SMALL, make_tree
from qdebug.belief import Belief, entropy


def uniform(_func):
    return 0.0


def test_prior_follows_suspiciousness():
    tree = make_tree(SMALL)
    belief = Belief(tree, lambda f: 0.99 if f == "m.py::d" else 0.0, epsilon_prior=0.01)
    post = belief.posterior({})
    assert post[4] == pytest.approx(1.0 / (1.0 + 7 * 0.01))
    assert sum(post) == pytest.approx(1.0)


def test_no_answer_moves_mass_into_subtree():
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform, error_rate=0.1)
    post = belief.posterior({"test/a#0": "no"})
    # subtree(a) = {1,2,3,4} gets 0.9 each, the other 4 nodes 0.1 each
    inside = 0.9 / (4 * 0.9 + 4 * 0.1)
    outside = 0.1 / (4 * 0.9 + 4 * 0.1)
    assert post[1:5] == pytest.approx([inside] * 4)
    assert [post[0]] + post[5:] == pytest.approx([outside] * 4)


def test_yes_answer_moves_mass_out_and_unknown_is_ignored():
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform, error_rate=0.2)
    post = belief.posterior({"test/a#0/c#0": "yes", "test/e#0": "unknown"})
    # subtree(c) = {3, 4}: likelihood 0.2, others 0.8
    z = 2 * 0.2 + 6 * 0.8
    assert post[3] == pytest.approx(0.2 / z)
    assert post[5] == pytest.approx(0.8 / z)


def test_inadmissible_favours_earlier_calls():
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform, error_rate=0.1)
    post = belief.posterior({"test/e#0": "inadmissible"})  # e is node 5
    assert all(post[i] > post[5] for i in range(5))
    assert post[5] == pytest.approx(post[6]) == pytest.approx(post[7])


def test_soft_update_keeps_wrongly_pruned_branch_alive():
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform, error_rate=0.1)
    # bug is in d, but the oracle wrongly said a is correct
    post = belief.posterior({"test/a#0": "yes", "test/a#0/c#0": "no", "test/a#0/c#0/d#0": "no"})
    assert max(range(len(post)), key=post.__getitem__) == 4
    assert post[4] > 0.3


def test_posterior_is_recomputed_from_answers():
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform)
    before = belief.posterior({"test/a#0": "no"})
    belief.posterior({"test/a#0": "no", "test/e#0": "yes"})
    assert belief.posterior({"test/a#0": "no"}) == before


def brute_force_gain(belief, post, node):
    eps = belief.error_rate
    n = len(post)
    inside = set(belief.tree.subtree_range(node))
    s = sum(post[i] for i in inside)
    expected = 0.0
    for verdict, p_answer in (("no", (1 - eps) * s + eps * (1 - s)), ("yes", eps * s + (1 - eps) * (1 - s))):
        lik = [(1 - eps if i in inside else eps) if verdict == "no" else (eps if i in inside else 1 - eps)
               for i in range(n)]
        unnorm = [p * l for p, l in zip(post, lik)]
        z = sum(unnorm)
        expected += p_answer * entropy([u / z for u in unnorm])
    return entropy(post) - expected


def test_information_gain_matches_brute_force():
    tree = make_tree(SMALL)
    belief = Belief(tree, lambda f: {"m.py::d": 0.8, "m.py::f": 0.3}.get(f, 0.05), error_rate=0.1)
    post = belief.posterior({"test/e#0/g#0": "yes"})
    gains = belief.information_gains(post, tree.nodes[1:])
    for node in tree.nodes[1:]:
        assert gains[node.id] == pytest.approx(brute_force_gain(belief, post, node), abs=1e-9)


def test_information_gain_prefers_balanced_split():
    # with a uniform prior over 8 nodes, a (4 nodes) splits better than d (1 node)
    tree = make_tree(SMALL)
    belief = Belief(tree, uniform, error_rate=0.05)
    gains = belief.information_gains(belief.posterior({}), tree.nodes[1:])
    assert gains[1] > gains[3] > gains[4]
    assert 0 < gains[1] <= 1.0


def test_function_posterior_sums_calls():
    tree = make_tree(("test", [("a", []), ("a", []), ("b", [])]))
    belief = Belief(tree, uniform)
    post = belief.posterior({})
    assert belief.function_posterior(post)["m.py::a"] == pytest.approx(2 * post[1])


def test_entropy():
    assert entropy([0.5, 0.5]) == pytest.approx(1.0)
    assert entropy([1.0, 0.0]) == 0.0
    assert entropy([0.25] * 4) == pytest.approx(math.log2(4))
