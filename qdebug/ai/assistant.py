"""Claude before and after the search: triage tunes it, the explanation reports on it."""

from dataclasses import asdict, dataclass, field

from qdebug.ai.client import AIError, AIUnavailable, Claude
from qdebug.ai.oracle import ClaudeOracle, HybridOracle
from qdebug.ai.prompts import Agent, earlier_answers, function_source, numbered, test_context, test_key, value
from qdebug.tree import crash_chain
from qdebug.tuning import BUG_KINDS

TRIAGE_CANDIDATES = 10   # suspicious functions shown to triage
TRIAGE_SOURCES = 5       # of which this many with their source
MAX_SUSPECTS = 3


@dataclass
class Triage:
    bug_kind: str = "unknown"
    suspects: list = field(default_factory=list)
    reason: str = ""

    def as_dict(self):
        return asdict(self)


@dataclass
class Explanation:
    summary: str = ""
    explanation: str = ""
    fix: str = ""
    confidence: str = "low"

    def as_dict(self):
        return asdict(self)


TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "bug_kind": {"type": "string", "enum": sorted(BUG_KINDS)},
        "suspects": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["bug_kind", "suspects", "reason"],
    "additionalProperties": False,
}

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "explanation": {"type": "string"},
        "fix": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["summary", "explanation", "fix", "confidence"],
    "additionalProperties": False,
}


def triage_candidates(session):
    """The most suspicious project functions that the failing test runs."""
    covered = session.spectrum.tests[session.test_id].functions
    ranked = [f for f in session.ranking.ranked_functions if f in covered]
    return ranked[:TRIAGE_CANDIDATES]


class Assistant:
    """Claude, the agent prompt in use, and what was asked of them in one session."""

    def __init__(self, claude=None, agent=None, show_source=False):
        self.claude = claude or Claude()
        self.agent = agent or Agent.load()
        self.show_source = show_source
        self.notes = []  # problems worth telling the user about (not fatal)

    @property
    def model(self):
        return self.claude.model

    def oracle(self, kind, human=None, threshold=0.8, show=None):
        ai = ClaudeOracle(self.claude, self.agent, show_source=self.show_source)
        if kind == "claude":
            return ai
        if kind == "hybrid":
            if human is None:
                raise ValueError("the hybrid oracle needs a human oracle to fall back on")
            return HybridOracle(ai, human, threshold=threshold, show=show)
        raise ValueError(f"unknown AI oracle {kind!r}")

    # ---------------------------------------------------------------- triage
    def triage_prompt(self, session):
        candidates = triage_candidates(session)
        out = ["# The most suspicious functions",
               "(ranked by how often failing tests run them compared with passing tests; "
               "use these keys for suspects)"]
        for i, func in enumerate(candidates):
            info = session.functions[func]
            out.append(f"\n## {func}\nSignature: {info.signature}")
            if info.doc:
                out.append(f'Docstring: """{info.doc.strip().splitlines()[0]}"""')
            if i < TRIAGE_SOURCES:
                out.append(function_source(session, func, limit=60))
        chain = crash_chain(session.tree) if session.tree is not None else []
        if chain:
            out.append("\nThe test's exception was raised inside: " + chain[-1].qualname)
        out.append("\nClassify the bug and name the suspects.")
        return "\n".join(out), candidates

    def triage(self, session):
        """A Triage for the session's failing test, or None if Claude could not answer."""
        prompt, candidates = self.triage_prompt(session)
        try:
            data = self.claude.ask([self.agent.system("triage"), test_context(session)], prompt,
                                   TRIAGE_SCHEMA)
        except AIUnavailable:
            raise
        except AIError as exc:
            self.notes.append(f"triage failed: {exc}")
            return None
        kind = data.get("bug_kind") if data.get("bug_kind") in BUG_KINDS else "unknown"
        known = set(candidates)
        suspects = [s for s in data.get("suspects", []) if isinstance(s, str) and s in known]
        return Triage(kind, suspects[:MAX_SUSPECTS], str(data.get("reason", "")).strip())

    # --------------------------------------------------------------- explain
    def explain_prompt(self, session):
        found, zoom = session.found, session.zoom
        region = list(zoom.region) if zoom is not None and zoom.status == "localized" else []
        out = [f"# The blamed call\n\nFunction: {found.func}"]
        if found.args is not None:
            out.append("Inputs:")
            out += [f"  {name} = {value(snap)}" for name, snap in found.args.items()]
            if found.exc:
                out.append(f"It raised: {value(found.exc)}")
            elif found.ret:
                out.append(f"It returned: {value(found.ret)}")
            for name in found.mutated:
                out.append(f"It changed {name}: {value(found.args[name])} -> {value(found.after[name])}")
        source = function_source(session, found.func, region)
        if source:
            note = f"lines {', '.join(map(str, region))} marked with >>" if region else "no single line found"
            out.append(f"Source ({note}):\n{source}")
        elif region:
            lines = session.file_lines(found.file)
            out.append(numbered(lines, min(region) - 3, max(region) + 3, set(region)))
        history = earlier_answers(session, limit=20)
        if history:
            out.append(history)
        out.append("Explain the bug and suggest a fix.")
        return "\n\n".join(out)

    def explain(self, session):
        """An Explanation of the session's result, or None."""
        found = session.found
        if found is None or found.func == test_key(session.test_id):
            return None
        try:
            data = self.claude.ask([self.agent.system("explain"), test_context(session)],
                                   self.explain_prompt(session), EXPLAIN_SCHEMA)
        except AIUnavailable as exc:
            self.notes.append(str(exc))
            return None
        except AIError as exc:
            self.notes.append(f"explanation failed: {exc}")
            return None
        confidence = data.get("confidence") if data.get("confidence") in ("high", "medium", "low") else "low"
        return Explanation(str(data.get("summary", "")).strip(), str(data.get("explanation", "")).strip(),
                           str(data.get("fix", "")).rstrip(), confidence)

    def report(self):
        return {"model": self.model, "effort": self.claude.effort, "agent": self.agent.source,
                "agent_sections_changed": self.agent.overridden, "usage": self.claude.usage.as_dict(),
                "notes": self.notes}
