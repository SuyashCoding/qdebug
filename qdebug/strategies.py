"""Question-selection strategies.

Common interface:
    next_question(tree, answers) -> Node | ESCALATE | None
    result(tree, answers)        -> [(Node, score), ...] best first

answers is {call path: verdict} (yes/no/unknown/inadmissible) and already
includes memoized and trusted answers. ESCALATE asks the session to re-run
the test at the next monitoring tier; if there is none the session sets
`escalation_exhausted` and calls again. None means "stop"; `stop_reason`
says why. Every strategy recomputes its state from `answers`, so undo and
tier re-runs need no special handling.
"""

from qdebug.belief import Belief, entropy

ESCALATE = "escalate"


def askable(node, answers):
    return node.parent is not None and node.monitored and node.path not in answers


class Strategy:
    name = "base"

    def __init__(self, suspiciousness, error_rate=0.1, threshold=0.9, min_gain=0.01,
                 stop_level="function"):
        self.suspiciousness = suspiciousness
        self.error_rate = error_rate
        self.threshold = threshold
        self.min_gain = min_gain
        self.stop_level = stop_level
        self.escalation_exhausted = False
        self.stop_reason = None
        self.escalate_reason = None
        self.last_info = {}

    def belief(self, tree):
        return Belief(tree, self.suspiciousness, self.error_rate)

    def prior_order(self, tree, nodes):
        return sorted(nodes, key=lambda n: (-self.suspiciousness(n.func), n.id))

    def next_question(self, tree, answers):  # pragma: no cover - abstract
        raise NotImplementedError

    def result(self, tree, answers):  # pragma: no cover - abstract
        raise NotImplementedError

    def _stop(self, reason):
        self.stop_reason = reason
        return

    def _escalate(self, reason):
        self.escalate_reason = reason
        return ESCALATE


class InfoGainStrategy(Strategy):
    """Ours: ask the monitored node with maximal expected information gain."""

    name = "infogain"

    def __init__(self, suspiciousness, certificate_stop=True, **kwargs):
        super().__init__(suspiciousness, **kwargs)
        self.certificate_stop = certificate_stop

    @staticmethod
    def _certified(tree, node, answers):
        """The algorithmic-debugging rule holds for node: its output was judged
        wrong (the root is wrong by definition) and every child was judged
        correct or inadmissible.

        With ε = 0.1 the posterior threshold is often unreachable (every
        answered call keeps an ε-sized residual), so without this rule the
        search continues until no question is worth min_gain bits.
        """
        if node.parent is not None and answers.get(node.path) != "no":
            return False
        return all(answers.get(c.path) in ("yes", "inadmissible") for c in tree.children(node))

    @staticmethod
    def _blameable_functions(tree, fpost):
        """fpost without test code, unless the tree holds nothing else."""
        kept = {f: p for f, p in fpost.items() if f not in tree.hints.test_funcs}
        return kept or fpost

    @staticmethod
    def _has_evidence(tree, func, answers):
        return any(n.func == func and answers.get(n.path) == "no" for n in tree.nodes)

    def next_question(self, tree, answers):
        belief = self.belief(tree)
        post = belief.posterior(answers)
        fpost = self._blameable_functions(tree, belief.function_posterior(post))
        top_func = max(fpost, key=fpost.get)
        confidence = fpost[top_func] if self.stop_level == "function" else max(post)
        self.last_info = {"entropy": entropy(post), "confidence": confidence}
        candidates = [n for n in tree.nodes if askable(n, answers)]
        if confidence >= self.threshold:
            if not tree.hints.evidence_stop or self._has_evidence(tree, top_func, answers):
                return self._stop("confident")
            # Blamed without a single answer about it: check its latest call,
            # the one most likely to be wrong (a test stops at its first failure).
            calls = [n for n in candidates if n.func == top_func]
            if calls:
                return max(calls, key=lambda n: n.id)
            if not self.escalation_exhausted and any(n.opaque and n.parent is not None for n in tree.nodes):
                return self._escalate(f"{top_func} is blamed but its calls are not monitored")
            return self._stop("unconfirmed")
        blameable = [i for i in range(len(post)) if tree.nodes[i].func not in tree.hints.test_funcs]
        top = tree.nodes[max(blameable or range(len(post)), key=lambda i: (post[i], -i))]
        if self.certificate_stop and self._certified(tree, top, answers):
            return self._stop("certified")
        opaque = [n for n in tree.nodes if n.opaque and n.parent is not None
                  and n.path not in answers]
        gains = belief.information_gains(post, candidates + opaque)
        step = self._settle_leader(tree, top, answers, gains, belief.p_wrong(post, top))
        if step is not None:
            return step if step != "stop" else None
        best = max(candidates, key=lambda n: (gains[n.id], -n.id)) if candidates else None
        best_gain = gains[best.id] if best is not None else 0.0
        opaque_gain = max((gains[n.id] for n in opaque), default=0.0)
        opaque_mass = sum(post[n.id] for n in opaque)
        self.last_info.update(opaque_mass=opaque_mass, gain=best_gain, opaque_gain=opaque_gain,
                              gains={n.id: gains[n.id] for n in candidates})
        if not self.escalation_exhausted:
            if opaque_mass > 0.5:
                return self._escalate(f"{100 * opaque_mass:.0f}% of the posterior is in opaque calls")
            # Escalating only helps if some currently opaque call would be
            # worth asking about (its gain needs no recorded values).
            if best_gain < self.min_gain and opaque_gain >= self.min_gain:
                return self._escalate(f"no monitored question is informative; an opaque call "
                                      f"would gain {opaque_gain:.2f} bits")
        if best is None or best_gain < self.min_gain:
            return self._stop("no informative question left")
        return best

    def _settle_leader(self, tree, top, answers, gains, p_wrong):
        """Questions that confirm or clear the leading hypothesis (tuning rules).

        The certificate needs the leader judged wrong and every callee
        cleared. Information gain alone gets there slowly: it avoids questions
        whose answer it can predict (the leader itself) and keeps returning to
        large subtrees that were already judged correct.

        * A leader with many open callees is asked about first, and once it is
          wrong the search stops for the line-level search ("fan-out"): that
          needs about log2(lines) questions instead of one per callee, and
          names the callee to descend into.
        * A wrong leader with a few open callees is settled by asking those.
        * A leader whose callees are all cleared, and whose output is more
          likely wrong than not, is asked about: the answer completes the
          certificate.

        Returns a node to ask, ESCALATE, "stop", or None when no rule applies.
        """
        hints = tree.hints
        if top.parent is None or not (hints.zoom_fanout or hints.settle_leader):
            return None
        verdict = answers.get(top.path)
        open_callees = [c for c in tree.children(top) if c.path not in answers]
        if hints.zoom_fanout and len(open_callees) >= hints.zoom_fanout:
            if verdict is None and askable(top, answers):
                return top
            if verdict == "no":
                self._stop("fan-out")
                return "stop"
        elif hints.settle_leader:
            if verdict == "no" and open_callees:
                ready = [c for c in open_callees if askable(c, answers)]
                if ready:
                    return max(ready, key=lambda n: (gains.get(n.id, 0.0), -n.id))
                if not self.escalation_exhausted:
                    return self._escalate(f"the callees of {top.qualname} are not monitored")
            elif verdict is None and not open_callees and p_wrong >= 0.5 and askable(top, answers):
                return top
        return None

    def result(self, tree, answers):
        """Calls by posterior; if one function is confidently buggy, its calls first.

        Function-level sums are not used otherwise: every answered call keeps
        a residual ε-proportional mass, so summing would favour functions that
        are simply called often.
        """
        belief = self.belief(tree)
        post = belief.posterior(answers)
        fpost = self._blameable_functions(tree, belief.function_posterior(post))
        top_func = max(fpost, key=fpost.get)
        confident = self.stop_level == "function" and fpost[top_func] >= self.threshold
        tests = tree.hints.test_funcs
        ranked = sorted(tree.nodes, key=lambda n: (n.func in tests, confident and n.func != top_func,
                                                   -post[n.id], n.id))
        return [(n, post[n.id]) for n in ranked]


class TopDownStrategy(Strategy):
    """Classic Shapiro top-down algorithmic debugging with hard pruning.

    Start at the (wrong) root and ask its children in execution order;
    descend into the first wrong child. If every child is correct (or
    unknown), the current node is the buggy one.
    """

    name = "topdown"

    def _walk(self, tree, answers):
        """Return (current wrong node, next child to ask or None)."""
        current = tree.root
        while True:
            descended = False
            for child in tree.children(current):
                verdict = answers.get(child.path)
                if verdict == "no":
                    current, descended = child, True
                    break
                if verdict in ("yes", "unknown", "inadmissible"):
                    continue
                if child.opaque and self.escalation_exhausted:
                    continue  # cannot be asked: treat like "don't know"
                return current, child
            if not descended:
                return current, None

    def next_question(self, tree, answers):
        current, child = self._walk(tree, answers)
        self.last_info = {"current": current.path}
        if child is None:
            return self._stop("localized")
        if child.opaque:
            return self._escalate(f"next child {child.qualname} is not monitored")
        return child

    def result(self, tree, answers):
        current, _ = self._walk(tree, answers)
        undecided = [c for c in tree.children(current)
                     if answers.get(c.path) not in ("yes", "no")]
        ranked = [(current, 1.0)]
        ranked += [(c, 0.0) for c in self.prior_order(tree, undecided)]
        ranked += [(a, 0.0) for a in tree.ancestors(current)]
        return ranked


class DivideAndQueryStrategy(Strategy):
    """Classic divide-and-query (Shapiro) with hard pruning.

    Ask the node whose subtree holds closest to half of the remaining
    candidates. "no" makes that node the new suspect root; "yes" (and
    "inadmissible": the fault ran before this call) removes its subtree.
    Answers are applied in the order they were given.
    """

    name = "divide"

    def _state(self, tree, answers):
        suspect = tree.root
        excluded = [False] * len(tree)
        skipped = set()

        def candidate(node):
            return tree.in_subtree(node, suspect) and not excluded[node.id]

        for path, verdict in answers.items():
            node = tree.by_path.get(path)
            if node is None or node is suspect or not candidate(node):
                continue
            if verdict == "no":
                suspect = node
            elif verdict in ("yes", "inadmissible"):
                for i in tree.subtree_range(node):
                    excluded[i] = True
            else:
                skipped.add(node.id)
        cands = [n for n in tree.nodes if candidate(n)]
        return suspect, cands, excluded

    def next_question(self, tree, answers):
        suspect, cands, excluded = self._state(tree, answers)
        n = len(cands)
        self.last_info = {"suspect": suspect.path, "candidates": n}
        if n <= 1:
            return self._stop("localized")
        weight = {}
        for node in reversed(cands):
            weight[node.id] = weight.get(node.id, 0) + 1
            if node.parent is not None and node is not suspect:
                weight[node.parent] = weight.get(node.parent, 0) + weight[node.id]
        options = [c for c in cands if c is not suspect and askable(c, answers)]
        if not options:
            if not self.escalation_exhausted and any(c.opaque for c in cands if c is not suspect):
                return self._escalate("all remaining candidates are unmonitored")
            return self._stop("no askable candidate left")
        best = min(options, key=lambda c: (abs(weight[c.id] - n / 2), c.id))
        self.last_info.update(weight=weight[best.id])
        return best

    def result(self, tree, answers):
        suspect, cands, _ = self._state(tree, answers)
        if len(cands) <= 1:
            # ancestors are fallbacks for the zoom phase if the suspect is refuted
            return [(suspect, 1.0)] + [(a, 0.0) for a in tree.ancestors(suspect)]
        return [(c, 1.0 / len(cands)) for c in self.prior_order(tree, cands)]


class InfoGainFullStrategy(InfoGainStrategy):
    """Ablation: InfoGain without the certificate stop (asks until gains vanish)."""

    name = "infogain-full"

    def __init__(self, suspiciousness, **kwargs):
        super().__init__(suspiciousness, certificate_stop=False, **kwargs)


STRATEGIES = {
    "infogain": InfoGainStrategy,
    "infogain-full": InfoGainFullStrategy,
    "topdown": TopDownStrategy,
    "divide": DivideAndQueryStrategy,
}


def make_strategy(name, suspiciousness, **kwargs):
    try:
        cls = STRATEGIES[name]
    except KeyError:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(STRATEGIES)}") from None
    return cls(suspiciousness, **kwargs)
