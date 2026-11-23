"""Ochiai suspiciousness for lines and functions, and monitoring tiers."""

import math

DEFAULT_TIERS = (5, 10, 15, 25, 50, 100)


def ochiai(failed, passed, total_failed):
    """failed(e) / sqrt(total_failed * (failed(e) + passed(e)))."""
    if total_failed == 0 or failed == 0:
        return 0.0
    return failed / math.sqrt(total_failed * (failed + passed))


def dstar(failed, passed, total_failed, star=2):
    """DStar (Wong et al. 2014): failed(e)^* / (passed(e) + not-failed(e)); a baseline for studies."""
    if failed == 0:
        return 0.0
    denominator = passed + (total_failed - failed)
    return float("inf") if denominator == 0 else failed ** star / denominator


FORMULAS = {"ochiai": ochiai, "dstar": dstar}


class Ranking:
    """SBFL ranking of a project's (non-test) functions and lines.

    functions: {func key: FuncInfo} from spectrum.scan_functions.
    failing: the failing tests to rank for (default: all of them). Ranking
    one group of failures that share a bug keeps the other bugs' failures
    from diluting its scores (see groups.py). formula: "ochiai" (used by the
    search) or "dstar" (a baseline in studies).
    """

    def __init__(self, spectrum, functions, failing=None, formula="ochiai"):
        self.functions = {k: f for k, f in functions.items() if not f.is_test}
        failing = spectrum.failing if failing is None else list(failing)
        score = FORMULAS[formula]
        passing = spectrum.passing
        self.total_failed = len(failing)
        self.total_passed = len(passing)

        def counts(attr, keep):
            fail, pas = {}, {}
            for test in failing:
                for e in getattr(test, attr):
                    if keep(e):
                        fail[e] = fail.get(e, 0) + 1
            for test in passing:
                for e in getattr(test, attr):
                    if keep(e):
                        pas[e] = pas.get(e, 0) + 1
            return fail, pas

        test_files = {f.file for f in functions.values() if f.is_test}
        lf, lp = counts("lines", lambda e: e[0] not in test_files)
        self.line_counts = {e: (lf.get(e, 0), lp.get(e, 0)) for e in set(lf) | set(lp)}
        self.line_scores = {e: score(f, p, self.total_failed)
                            for e, (f, p) in self.line_counts.items()}
        ff, fp = counts("functions", lambda e: e in self.functions)
        self.func_counts = {k: (ff.get(k, 0), fp.get(k, 0)) for k in self.functions}
        self.func_scores = {k: score(f, p, self.total_failed)
                            for k, (f, p) in self.func_counts.items()}
        self.max_line_score = {}
        for key, info in self.functions.items():
            best = 0.0
            for line in range(info.line, info.end_line + 1):
                best = max(best, self.line_scores.get((info.file, line), 0.0))
            self.max_line_score[key] = best
        self.ranked_functions = sorted(
            self.functions,
            key=lambda k: (-self.func_scores[k], -self.max_line_score[k], k))
        self.ranked_lines = sorted(
            self.line_scores, key=lambda e: (-self.line_scores[e], e[0], e[1]))

    def suspiciousness(self, func):
        """Function score used for priors: Ochiai plus a tiny max-line tie-break."""
        return self.func_scores.get(func, 0.0) + 1e-3 * self.max_line_score.get(func, 0.0)

    def tier_size(self, pct):
        return max(1, math.ceil(pct / 100.0 * len(self.ranked_functions)))

    def tier_set(self, pct):
        """Function keys monitored at tier pct%: the top ceil(pct% of all functions)."""
        return set(self.ranked_functions[: self.tier_size(pct)])

    def function_rank(self, func):
        """1-based position in the ranked function list (None if unknown)."""
        try:
            return self.ranked_functions.index(func) + 1
        except ValueError:
            return None

    def line_rank(self, relfile, line):
        """1-based position of a line in the Ochiai line list (None if never executed)."""
        try:
            return self.ranked_lines.index((relfile, line)) + 1
        except ValueError:
            return None

    def function_table(self, limit=None):
        rows = []
        for i, key in enumerate(self.ranked_functions[:limit], 1):
            f, p = self.func_counts[key]
            rows.append((i, key, self.func_scores[key], self.max_line_score[key], f, p))
        return rows
