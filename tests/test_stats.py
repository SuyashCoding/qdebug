"""The study statistics, checked against hand-worked and textbook values."""

import pytest

from qdebug.stats import bootstrap_mean, mcnemar, wilcoxon, wilson


def test_wilson_matches_the_textbook_interval():
    low, high = wilson(8, 10)
    assert low == pytest.approx(0.4902, abs=1e-3)
    assert high == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 0) == (0.0, 1.0)


def test_mcnemar_counts_discordant_pairs_and_is_exact():
    a = [1, 1, 1, 1, 1, 1, 0, 1]
    b = [0, 0, 0, 0, 0, 0, 0, 1]
    only_a, only_b, p = mcnemar(a, b)
    assert (only_a, only_b) == (6, 0)
    assert p == pytest.approx(2 / 64)          # 2 * 0.5^6
    assert mcnemar([1, 0], [1, 0])[2] == 1.0   # no discordant pairs
    assert mcnemar([1, 0], [0, 1])[2] == 1.0   # one each way


def test_wilcoxon_exact_small_sample():
    # all 5 differences positive: W+ = 15, p = 2 / 2^5
    n, w, p = wilcoxon([2, 3, 4, 5, 6], [1, 1, 1, 1, 1])
    assert (n, w) == (5, 15)
    assert p == pytest.approx(2 / 32)


def test_wilcoxon_drops_zeros_and_handles_ties():
    n, w, p = wilcoxon([1, 2, 3, 3], [1, 1, 2, 4])
    assert n == 3                  # the first pair is a zero difference
    assert w == pytest.approx(4.0)  # |d| = 1, 1, 1 all tie at rank 2; two are positive
    assert 0 < p <= 1


def test_wilcoxon_normal_approximation_for_large_samples():
    x = list(range(40))
    y = [v - 1 for v in x]          # every difference +1
    n, _, p = wilcoxon(x, y)
    assert n == 40 and p < 1e-6
    assert wilcoxon(x, x)[2] == 1.0


def test_bootstrap_interval_contains_the_mean():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    low, high = bootstrap_mean(values, reps=2000)
    assert low < 5.5 < high
