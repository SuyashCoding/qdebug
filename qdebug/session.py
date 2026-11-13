"""The debugging session: spectrum -> tiered tree -> questions -> zoom -> report."""

from dataclasses import dataclass, field

from qdebug.belief import Belief
from qdebug.oracles import Question
from qdebug.ranking import DEFAULT_TIERS, Ranking
from qdebug.runner import invoke
from qdebug.spectrum import collect_spectrum, read_source_lines, scan_functions
from qdebug.strategies import ESCALATE, InfoGainStrategy, make_strategy
from qdebug.tree import ExecutionTree, SearchHints, render_tree
from qdebug.tuning import LOW_CONFIDENCE_STOPS, assertion_cut, resolve_tuning
from qdebug.zoom import REFUTED_INPUTS, REFUTED_OUTPUT, zoom_into


@dataclass
class SessionConfig:
    project: str
    test: str | None = None
    strategy: str = "infogain"
    tiers: tuple = DEFAULT_TIERS
    error_rate: float = 0.1
    budget: int = 30
    threshold: float = 0.9
    min_gain: float = 0.01
    stop_level: str = "function"   # stop on max function-level or node-level posterior
    max_repr: int = 300
    zoom: bool = True
    zoom_rounds: int = 4           # zoom candidates tried; each refutation resumes the search
    use_inadmissible: bool = True  # False: treat "inputs are wrong" as plain "unknown"
    ascii: bool = False
    policy: str = "baseline"       # conditional search rules, see tuning.py
    assertion_weight: float | None = None  # override the policy's knob
    repeat_discount: float | None = None   # override the policy's knob


@dataclass
class LogEntry:
    """One oracle interaction that changed the evidence (undo pops these)."""

    kind: str                  # "answer" or "trust"
    path: str
    func: str
    verdict: str | None
    tier: int
    number: int
    memo_key: tuple | None = None
    summary: dict = field(default_factory=dict)
    note: str = ""
    source: str = "oracle"     # "oracle" (call question) or "zoom" (end/entry check)


class SessionError(RuntimeError):
    pass


class DebugSession:
    def __init__(self, config, oracle, run=invoke, out=print):
        self.config = config
        self.oracle = oracle
        self.run = run
        self.out = out
        self.log = []
        self.events = []
        self.tier_runs = []
        self.tree = None
        self.tier_index = 0
        self.strategy = None
        self.stop_reason = None
        self.zoom_results = []
        self.limits_hit = {}
        self.spectrum = None
        self.tuning = resolve_tuning(config.policy, config.assertion_weight, config.repeat_discount)
        # how the final answer was reached: "answers", "sbfl" (best guess after
        # a search that ended without evidence) or "no_project_code"
        self.basis = "answers"

    # ------------------------------------------------------------------ setup
    def collect(self):
        """Run the whole suite once. Separate from prepare so a UI can offer the failing tests."""
        if self.spectrum is not None:
            return
        cfg = self.config
        self.functions = scan_functions(cfg.project)
        self.spectrum = collect_spectrum(cfg.project, run=self.run)
        self.ranking = Ranking(self.spectrum, self.functions)
        if not self.spectrum.failing:
            raise SessionError(f"no failing test in {cfg.project}")

    def prepare(self):
        cfg = self.config
        self.collect()
        failing = [t.nodeid for t in self.spectrum.failing]
        if cfg.test:
            # a parametrized test's base name selects its first failing case
            matches = [t for t in failing if t == cfg.test or t.endswith(cfg.test)
                       or t.split("[", 1)[0] == cfg.test or t.split("[", 1)[0].endswith(cfg.test)]
            if not matches:
                raise SessionError(f"{cfg.test} is not a failing test; failing: {failing}")
            self.test_id = matches[0]
        else:
            self.test_id = failing[0]
        self.failure_text = self.spectrum.tests[self.test_id].failure
        plain = self.run(cfg.project, "plain", test=self.test_id)
        self.untraced_time = next(iter(plain["tests"].values())).get("call_time", 0.0)
        self.strategy = make_strategy(
            cfg.strategy, self.ranking.suspiciousness, error_rate=cfg.error_rate,
            threshold=cfg.threshold, min_gain=cfg.min_gain, stop_level=cfg.stop_level)
        self._file_lines = {}

    def file_lines(self, relfile):
        if relfile not in self._file_lines:
            self._file_lines[relfile] = read_source_lines(self.config.project, relfile)
        return self._file_lines[relfile]

    @property
    def tier(self):
        return self.config.tiers[self.tier_index]

    def search_hints(self, tree):
        tuning = self.tuning
        tests = frozenset(n.func for n in tree.nodes
                          if tuning.exclude_tests and self._is_test(n.func))
        return SearchHints(prior_scale=self._assertion_scale(tree),
                           repeat_discount=tuning.repeat_discount, test_funcs=tests,
                           evidence_stop=tuning.evidence_stop)

    def _is_test(self, func):
        info = self.functions.get(func)
        return info is None or info.is_test

    def _assertion_scale(self, tree):
        """Prior multipliers that down-weight calls made before the previous passing assertion."""
        weight = self.tuning.assertion_weight
        root = tree.root
        if weight >= 1.0 or root.last_line is None:
            return None
        cut = assertion_cut(self.file_lines(root.file), root.line, root.last_line)
        if cut is None:
            return None
        scale = [1.0] * len(tree)
        for child in tree.children(root):
            if child.call_line is not None and child.call_line <= cut:
                for i in tree.subtree_range(child):
                    scale[i] = weight
        return scale

    def build_tree(self):
        pct = self.tier
        monitored = None if pct >= 100 else self.ranking.tier_set(pct)
        data = self.run(self.config.project, "tree", test=self.test_id, monitored=monitored,
                        max_repr=self.config.max_repr)
        record = next(iter(data["tests"].values()))
        if record.get("outcome") != "failed":
            raise SessionError(f"{self.test_id} did not fail when re-run (non-deterministic test?)")
        if not record.get("nodes"):
            last = (record.get("failure") or "").strip().splitlines()[-1:] or ["?"]
            raise SessionError(f"{self.test_id} failed before its body ran any project code "
                               f"(in a fixture, decorator or mock.patch): {last[0][:200]}")
        tree = ExecutionTree.from_json(record["nodes"], self.test_id)
        if self.tree is not None:
            check_same_execution(self.tree, tree)
        tree.hints = self.search_hints(tree)
        self.tree = tree
        limits_hit = data.get("tree_limits_hit") or {}
        if limits_hit and limits_hit != self.limits_hit:
            folded = ", ".join(f"{n} by {k}" for k, n in sorted(limits_hit.items()))
            self.out(f"  note: {len(tree)} calls recorded; calls beyond the tree limits were folded "
                     f"into their callers ({folded}). Raise --max-nodes/--max-repeat/--max-depth "
                     f"to record them.")
        self.limits_hit = limits_hit
        self.tier_runs.append({
            "tier": pct,
            "monitored_functions": self.ranking.tier_size(pct) if pct < 100 else len(self.ranking.functions),
            "nodes": len(self.tree),
            "monitored_nodes": self.tree.monitored_count(),
            "call_time": record.get("call_time", 0.0),
            "wall_time": data.get("wall_time", 0.0),
        })

    # ---------------------------------------------------------------- answers
    def effective_answers(self, tree=None):
        """{path: (verdict, source)} with source in oracle / memo / trust."""
        tree = tree or self.tree
        eff, memo, trusted = {}, {}, set()
        for entry in self.log:
            if entry.kind == "trust":
                trusted.add(entry.func)
                continue
            eff[entry.path] = (entry.verdict, entry.source)  # later evidence wins
            if entry.verdict in ("yes", "no") and entry.memo_key is not None:
                memo[entry.memo_key] = entry.verdict
        for node in tree.nodes:
            if node.parent is None:
                continue
            if node.func in trusted:
                eff[node.path] = ("yes", "trust")
            elif node.path not in eff and node.monitored:
                verdict = memo.get(node.memo_key())
                if verdict is not None:
                    eff[node.path] = (verdict, "memo")
        return eff

    def answers(self):
        return {p: v for p, (v, _) in self.effective_answers().items()}

    @property
    def questions_asked(self):
        return sum(1 for e in self.log if e.source == "oracle")

    def belief(self):
        return Belief(self.tree, self.ranking.suspiciousness, self.config.error_rate)

    def posterior(self):
        return self.belief().posterior(self.answers())

    # ------------------------------------------------------- oracle callbacks
    def explain(self, node):
        """Text for the human oracle's "w" (why this question?) command."""
        belief = self.belief()
        answers = self.answers()
        post = belief.posterior(answers)
        gain = belief.information_gains(post, [node])[node.id]
        p_wrong = belief.p_wrong(post, node)
        lines = [f"  strategy: {self.strategy.name}"]
        info = self.strategy.last_info
        if isinstance(self.strategy, InfoGainStrategy):
            lines.append(f"  expected information gain of this question: {gain:.3f} bits "
                         f"(current entropy {info.get('entropy', 0):.3f} bits)")
        elif self.strategy.name == "topdown":
            lines.append(f"  next unanswered child (execution order) of the wrong call "
                         f"{info.get('current')}; information gain would be {gain:.3f} bits")
        else:
            lines.append(f"  its subtree holds {info.get('weight')} of the {info.get('candidates')} "
                         f"remaining candidate calls; information gain {gain:.3f} bits")
        lines.append(f"  P(output wrong) = {p_wrong:.3f}: a 'no' moves belief into its "
                     f"{self.tree.size[node.id]} call subtree, a 'yes' moves it out")
        lines.append("  top hypotheses (bug in this call's own code):")
        for n in sorted(self.tree.nodes, key=lambda n: -post[n.id])[:5]:
            lines.append(f"    {100 * post[n.id]:5.1f}%  {n.path}")
        lines.append("  by function:")
        fpost = belief.function_posterior(post)
        for func, p in sorted(fpost.items(), key=lambda kv: -kv[1])[:5]:
            lines.append(f"    {100 * p:5.1f}%  {func}")
        return "\n".join(lines)

    def render_tree(self, highlight=None):
        post = self.posterior()
        if highlight is None:
            ranked = self.strategy.result(self.tree, self.answers())
            highlight = ranked[0][0].id if ranked else None
        return render_tree(self.tree, self.effective_answers(), post, highlight,
                           ascii_only=self.config.ascii)

    # ------------------------------------------------------------------ loop
    def undo(self):
        if not self.log:
            self.out("  nothing to undo")
            return
        entry = self.log.pop()
        self.out(f"  undone: {entry.kind} {entry.path} ({entry.verdict})")

    def _summary(self, node):
        return {
            "qualname": node.qualname,
            "args": {k: v["short"] for k, v in (node.args or {}).items()},
            "output": node.output_summary(width=300),
        }

    def search(self, resume=False):
        """Function-level search. Returns the strategy's ranked result.

        resume=True continues on the current tree after new evidence (a zoom
        refutation) was added to the log.
        """
        cfg = self.config
        if not resume:
            self.tier_index = 0
            self.build_tree()
        while True:
            answers = self.answers()
            if self.questions_asked >= cfg.budget:
                self.stop_reason = "budget"
                break
            step = self.strategy.next_question(self.tree, answers)
            if step == ESCALATE:
                if self.tier_index + 1 < len(cfg.tiers):
                    old = self.tier
                    self.tier_index += 1
                    self.build_tree()
                    self.events.append({"after_question": self.questions_asked, "from": old,
                                        "to": self.tier, "reason": self.strategy.escalate_reason})
                    self.out(f"  ↑ escalating monitoring tier {old}% -> {self.tier}% "
                             f"({self.strategy.escalate_reason}); {len(self.tree)} calls, "
                             f"{self.tree.monitored_count()} monitored")
                else:
                    self.strategy.escalation_exhausted = True
                continue
            if step is None:
                self.stop_reason = self.strategy.stop_reason
                break
            answer = self.ask(step)
            if answer.action == "quit":
                self.stop_reason = "user quit"
                break
            if answer.action == "undo":
                self.undo()
        return self.strategy.result(self.tree, self.answers())

    def ask(self, node):
        """Ask the oracle the call question about node and log the evidence."""
        question = Question("call", node, self.functions.get(node.func),
                            number=self.questions_asked + 1, meta={"tier": self.tier})
        answer = self.oracle.judge(question, self)
        if answer.action in ("quit", "undo"):
            return answer
        verdict = answer.verdict
        if verdict == "inadmissible" and not self.config.use_inadmissible:
            verdict = "unknown"
        self.log.append(LogEntry(
            kind="trust" if answer.action == "trust" else "answer", path=node.path,
            func=node.func, verdict=verdict, tier=self.tier, number=question.number,
            memo_key=node.memo_key(), summary=self._summary(node), note=answer.note))
        return answer

    @staticmethod
    def zoom_candidate(ranked, tried):
        """The next call to zoom into: the best untried one, latest first among ties.

        Equal posteriors are typical for several calls of one function that
        the search blamed as a whole. A test stops at its first failing
        assertion, so among them the latest call is the likeliest wrong one.
        """
        open_ = [(n, p) for n, p in ranked if n.path not in tried]
        if not open_:
            return None
        best = max(p for _, p in open_)
        return max((n for n, p in open_ if p >= best * (1 - 1e-9)), key=lambda n: n.id)

    def localize(self, ranked):
        """Zoom into the best candidate; on refutation, add evidence and search on.

        A refuted zoom is an answer about the call itself: "end state correct"
        means its output is correct ("yes"), "entry state wrong" means its
        inputs were already infected ("inadmissible"). It is logged as
        evidence (overriding the call-level answer), the strategy resumes, and
        the next untried top candidate is zoomed. A confirmed zoom then
        descends into implicated callees.
        """
        tried = set()
        for _ in range(self.config.zoom_rounds):
            tests = self.tree.hints.test_funcs
            node = self.zoom_candidate([(n, p) for n, p in ranked if n.func not in tests], tried)
            if node is None:
                break
            tried.add(node.path)
            eff = self.answers()
            if eff.get(node.path) is None and node.monitored:
                # the search blamed a function, not this call: check the call first
                answer = self.ask(node)
                if answer.action == "quit":
                    return node, None
                if answer.verdict in ("yes", "inadmissible"):
                    ranked = self.search(resume=True)
                    continue
                eff = self.answers()
            result = zoom_into(self, node, eff.get(node.path))
            self.zoom_results.append(result)
            if result.status == "localized":
                return self.descend(node, result, eff, tried)
            if result.status == "quit":
                return node, result
            if result.status in (REFUTED_OUTPUT, REFUTED_INPUTS):
                verdict = "yes" if result.status == REFUTED_OUTPUT else "inadmissible"
                self.log.append(LogEntry(
                    kind="answer", path=node.path, func=node.func, verdict=verdict,
                    tier=self.tier, number=len(self.log) + 1, summary=self._summary(node),
                    note=f"zoom: {result.status.replace('_', ' ')}", source="zoom"))
                self.out(f"  zoom refuted {node.path} ({result.status}); resuming the search")
                ranked = self.search(resume=True)
        return (ranked[0][0] if ranked else None), None

    def descend(self, node, result, eff, tried, max_depth=5):
        """Cross-check callees implicated by the line-level region.

        If the state first goes wrong across a line that calls a child, that
        child is implicated even if it was answered "yes" (the answer may
        have been wrong) or never asked (opaque / unknown). Zoom into such
        children; a child whose zoom is confirmed replaces the current call.
        Children whose inputs were already wrong (inadmissible) are skipped.
        """
        for _ in range(max_depth):
            region = set(result.region)
            implicated = [c for c in self.tree.children(node)
                          if c.call_line in region and c.path not in tried
                          and eff.get(c.path) != "inadmissible"]
            moved = False
            for child in implicated:
                tried.add(child.path)
                child_result = zoom_into(self, child, eff.get(child.path))
                self.zoom_results.append(child_result)
                if child_result.status == "quit":
                    return node, result
                if child_result.status == "localized":
                    node, result, moved = child, child_result, True
                    break
            if not moved:
                break
        return node, result

    def _needs_fallback(self, found):
        if not self.tuning.fallback or self.stop_reason == "user quit":
            return False
        return (self.stop_reason in LOW_CONFIDENCE_STOPS
                or found is None or found.func in self.tree.hints.test_funcs)

    def fallback(self, found):
        """The search ended without evidence: report SBFL's best function in this run.

        Up to three of its latest calls are checked, and the first one the
        oracle confirms is zoomed, so a best guess can still end on a line.
        """
        in_tree = {}
        for node in self.tree.nodes:
            in_tree.setdefault(node.func, []).append(node)
        func = next((f for f in self.ranking.ranked_functions
                     if f in in_tree and self.ranking.func_scores[f] > 0), None)
        if func is None:
            self.basis = "no_project_code"
            return found, None
        self.basis = "sbfl"
        calls = sorted(in_tree[func], key=lambda n: -n.id)
        for node in calls[:3]:
            verdict = self.answers().get(node.path)
            if verdict is None and node.monitored:
                answer = self.ask(node)
                if answer.action == "quit":
                    return calls[0], None
                verdict = answer.verdict
            if verdict in ("yes", "inadmissible"):
                continue
            result = zoom_into(self, node, verdict)
            self.zoom_results.append(result)
            if result.status in ("localized", "quit"):
                return node, result
        return calls[0], None

    def run_session(self):
        if self.strategy is None:
            self.prepare()
        ranked = self.search()
        self.ranked_before_zoom = ranked
        found, zoom = (ranked[0][0] if ranked else None), None
        if self._needs_fallback(found):
            found, zoom = self.fallback(found) if self.config.zoom else (found, None)
        elif self.config.zoom and ranked and self.stop_reason != "user quit":
            found, zoom = self.localize(ranked)
            if (zoom is None or zoom.status != "localized") and self._needs_fallback(found):
                found, zoom = self.fallback(found)
        self.found = found
        self.zoom = zoom
        return found


def check_same_execution(old, new):
    """Raise SessionError if a re-run of the test took a different path.

    Every re-run (tier escalation, zoom) assumes the same execution: answers
    are keyed by call path ids. Monitoring only changes which values are
    recorded, never the structure, so any difference means the test is not
    deterministic (time, randomness, network, shared state, test order).
    """
    old_paths = [n.path for n in old.nodes]
    new_paths = [n.path for n in new.nodes]
    if old_paths == new_paths:
        return
    first = next((i for i, (a, b) in enumerate(zip(old_paths, new_paths)) if a != b),
                 min(len(old_paths), len(new_paths)))
    before = old_paths[first] if first < len(old_paths) else "(end of run)"
    after = new_paths[first] if first < len(new_paths) else "(end of run)"
    raise SessionError(
        f"the test took a different path when re-run ({len(old_paths)} vs {len(new_paths)} calls; "
        f"call #{first} was {before}, now {after}). qdebug needs a deterministic test: "
        f"fix time, randomness, network and shared state (random is already seeded).")


def tier_list(text):
    tiers = tuple(int(x) for x in str(text).split(",") if x.strip())
    if not tiers or any(t <= 0 or t > 100 for t in tiers) or list(tiers) != sorted(tiers):
        raise ValueError("tiers must be increasing percentages in (0, 100]")
    return tiers
