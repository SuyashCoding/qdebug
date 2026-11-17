"""Bayesian belief over where the bug is, and expected information gain.

Hypotheses: for every node b of the execution tree, H_b = "the bug is in b's
own code" (not in its callees). Opaque nodes get hypotheses too.

Prior:  P(H_b) ∝ epsilon_prior + suspiciousness(function of b).

Observation model: under H_b, the output of node q is wrong iff b is q or a
descendant of q. This assumes an infection always propagates to the outputs
of every caller up to the test. It is violated by *failure masking* (a wrong
intermediate value that does not change the caller's output, e.g. a wrong
weight that stays in the same shipping tier). Masking shows up as answers
that contradict the true hypothesis; the error rate below keeps such answers
from eliminating it outright.

Each yes/no answer is treated as noisy evidence: likelihood 1 - ε if it is
consistent with H_b, ε otherwise. An answer that states its own confidence
(Claude's do) uses max(ε, 1 - confidence) instead, see session.answer_error. "unknown" carries no evidence. That the
test root is wrong is consistent with every hypothesis, so it is implicit.

Extension (Naish's three-valued debugging): "inadmissible" means "this
call's *inputs* are already wrong". Then the fault executed before the call
started, i.e. H_b is consistent iff b precedes q in pre-order (b.id < q.id:
an ancestor whose own code ran before the call, or an earlier finished call).

The posterior is recomputed from the full answer set every time, which makes
undo trivial and the computation deterministic.
"""

import math

from qdebug.tuning import REPEAT_FLOOR

EPSILON_PRIOR = 0.01
LN2 = math.log(2)


def entropy(probs):
    """Shannon entropy in bits."""
    return -sum(p * math.log2(p) for p in probs if p > 0)


class Belief:
    def __init__(self, tree, suspiciousness, error_rate=0.1, epsilon_prior=EPSILON_PRIOR):
        """suspiciousness: callable func key -> score >= 0."""
        if not 0 < error_rate < 0.5:
            raise ValueError("error_rate must be in (0, 0.5)")
        self.tree = tree
        self.error_rate = error_rate
        weights = [epsilon_prior + max(0.0, suspiciousness(n.func)) for n in tree.nodes]
        scale = tree.hints.prior_scale
        if scale is not None:
            weights = [w * s for w, s in zip(weights, scale)]
        total = sum(weights)
        self.prior = [w / total for w in weights]

    def _repeat_penalty(self, answers):
        """{func: log factor} for functions with correct calls and no wrong call."""
        discount = self.tree.hints.repeat_discount
        if discount >= 1.0:
            return {}
        correct, wrong = {}, set()
        for path, verdict in answers.items():
            node = self.tree.by_path.get(path)
            if node is None:
                continue
            if verdict == "yes":
                correct[node.func] = correct.get(node.func, 0) + 1
            elif verdict == "no":
                wrong.add(node.func)
        return {func: math.log(max(discount ** count, REPEAT_FLOOR))
                for func, count in correct.items() if func not in wrong}

    def posterior(self, answers):
        """answers: {path: verdict} with verdict in yes/no/unknown."""
        tree = self.tree
        n = len(tree)
        errors = tree.hints.answer_error  # per-answer error rates (stated confidences)
        default_in = math.log(1 - self.error_rate)
        default_out = math.log(self.error_rate)
        # diff[i] accumulates range additions over the pre-order index.
        base = 0.0
        diff = [0.0] * (n + 1)
        for path, verdict in answers.items():
            node = tree.by_path.get(path)
            if node is None or verdict not in ("yes", "no", "inadmissible"):
                continue
            eps = errors.get(path)
            if eps is None:
                log_in, log_out = default_in, default_out
            else:
                log_in, log_out = math.log(1 - eps), math.log(eps)
            lo, hi = node.id, node.id + tree.size[node.id]
            if verdict == "inadmissible":
                lo, hi = 0, node.id  # consistent: everything that started earlier
            # "no": hypotheses inside [lo, hi) are consistent.
            inside, outside = (log_out, log_in) if verdict == "yes" else (log_in, log_out)
            base += outside
            diff[lo] += inside - outside
            diff[hi] -= inside - outside
        logs = []
        running = 0.0
        penalty = self._repeat_penalty(answers)
        for i in range(n):
            running += diff[i]
            p = self.prior[i]
            logs.append(math.log(p) + base + running + penalty.get(tree.nodes[i].func, 0.0)
                        if p > 0 else -math.inf)
        top = max(logs)
        weights = [math.exp(v - top) for v in logs]
        total = sum(weights)
        return [w / total for w in weights]

    def subtree_mass(self, post):
        mass = list(post)
        for node in reversed(self.tree.nodes):
            if node.parent is not None:
                mass[node.parent] += mass[node.id]
        return mass

    def p_wrong(self, post, node):
        """Probability that node's output is wrong, ignoring oracle noise."""
        return sum(post[i] for i in self.tree.subtree_range(node))

    def information_gains(self, post, candidates):
        """{node id: expected entropy reduction in bits} for each candidate node.

        Uses subtree aggregates of p and p·ln p, so each node costs O(1):
        after answer a the posterior is p_b·c_in/Z inside subtree(q) and
        p_b·c_out/Z outside, and its entropy has a closed form in S = mass
        inside, L_in = Σ_in p ln p and L_out = Σ_out p ln p.
        """
        tree = self.tree
        eps = self.error_rate
        plogp = [p * math.log(p) if p > 0 else 0.0 for p in post]
        mass = list(post)
        lmass = list(plogp)
        for node in reversed(tree.nodes):
            if node.parent is not None:
                mass[node.parent] += mass[node.id]
                lmass[node.parent] += lmass[node.id]
        total_l = lmass[0]
        h_now = -total_l / LN2

        def h_after(s, l_in, c_in, c_out):
            z = c_in * s + c_out * (1 - s)
            h = 0.0
            if s > 0:
                h -= (c_in / z) * (l_in + s * math.log(c_in / z))
            if s < 1:
                h -= (c_out / z) * ((total_l - l_in) + (1 - s) * math.log(c_out / z))
            return z, h / LN2

        gains = {}
        for node in candidates:
            s = min(max(mass[node.id], 0.0), 1.0)
            l_in = lmass[node.id]
            p_no, h_no = h_after(s, l_in, 1 - eps, eps)
            p_yes, h_yes = h_after(s, l_in, eps, 1 - eps)
            gains[node.id] = max(0.0, h_now - (p_no * h_no + p_yes * h_yes))
        return gains

    def function_posterior(self, post):
        """{func key: total posterior of all calls of that function}."""
        out = {}
        for node, p in zip(self.tree.nodes, post):
            out[node.func] = out.get(node.func, 0.0) + p
        return out
