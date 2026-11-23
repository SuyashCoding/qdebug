"""Small statistics for paired comparisons in studies (no SciPy needed).

- wilson: 95% confidence interval of a proportion.
- mcnemar: exact two-sided McNemar test for paired yes/no outcomes.
- wilcoxon: two-sided Wilcoxon signed-rank test for paired numbers
  (exact for up to 25 non-zero differences, normal approximation above).
- bootstrap_mean: percentile bootstrap interval of a mean.
"""

import math
import random
from collections import Counter


def wilson(k, n, z=1.96):
    """(low, high) Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar(a, b):
    """Exact McNemar test for paired booleans a[i], b[i].

    Returns (only_a, only_b, p): the pairs where only a succeeded, only b, and
    the two-sided p-value of the binomial test on those discordant pairs.
    """
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return only_a, only_b, min(1.0, 2 * tail)


def _ranks(values):
    """Average ranks (1-based) of values, ties sharing their mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def wilcoxon(x, y, exact_limit=25):
    """Two-sided Wilcoxon signed-rank test of paired x[i] - y[i] (zero differences dropped).

    Returns (n, w_plus, p): non-zero pairs, sum of the ranks of positive
    differences, and the p-value.
    """
    diffs = [a - b for a, b in zip(x, y) if a != b]
    n = len(diffs)
    if n == 0:
        return 0, 0.0, 1.0
    ranks = _ranks([abs(d) for d in diffs])
    w_plus = sum(r for r, d in zip(ranks, diffs) if d > 0)
    total = n * (n + 1) / 2
    if n <= exact_limit:
        # exact null distribution of W+ over all 2^n sign patterns, on doubled ranks (ties give halves)
        counts = Counter({0: 1})
        for r in ranks:
            step = round(2 * r)
            nxt = Counter()
            for s, c in counts.items():
                nxt[s] += c
                nxt[s + step] += c
            counts = nxt
        observed = round(2 * w_plus)
        mirror = round(2 * total) - observed
        low, high = min(observed, mirror), max(observed, mirror)
        tail = sum(c for s, c in counts.items() if s <= low or s >= high)
        return n, w_plus, min(1.0, tail / 2 ** n)
    mean = total / 2
    ties = Counter(ranks).values()
    var = n * (n + 1) * (2 * n + 1) / 24 - sum(t ** 3 - t for t in ties) / 48
    z = (abs(w_plus - mean) - 0.5) / math.sqrt(var) if var > 0 else 0.0
    return n, w_plus, min(1.0, math.erfc(max(z, 0.0) / math.sqrt(2)))


def bootstrap_mean(values, reps=5000, seed=0, level=0.95):
    """(low, high) percentile bootstrap interval of the mean of values."""
    values = list(values)
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(reps))
    lo = means[int((1 - level) / 2 * reps)]
    hi = means[min(reps - 1, int((1 + level) / 2 * reps))]
    return (lo, hi)
