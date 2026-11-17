"""Execution tree of one failing test: nodes are individual function calls.

Node ids are assigned at call time, so they are a pre-order numbering and the
subtree of node q is the contiguous id range [q.id, q.id + size(q)).

A node's call path id (e.g. ``test_x/build_invoice#0/line_total#2``) is its
parent's path plus ``qualname#k`` where k counts earlier calls of the same
qualname under the same parent. It identifies "the same call" across tier
re-runs and between the buggy and the fixed program.
"""

from dataclasses import dataclass, field

from qdebug.tracer import truncate

MARKERS = {
    "yes": "[✓]",
    "no": "[✗]",
    "unknown": "[?]",
    "inadmissible": "[!]",
    "pending": "[ ]",
    "opaque": "[○]",
    "trust": "[T]",
}
ASCII_MARKERS = {"yes": "[v]", "no": "[x]", "unknown": "[?]", "inadmissible": "[!]", "pending": "[ ]",
                 "opaque": "[o]", "trust": "[T]"}


@dataclass
class Node:
    id: int
    path: str
    qualname: str
    func: str
    file: str
    line: int
    parent: int | None
    children: list
    monitored: bool
    own_lines: list = field(default_factory=list)
    args: dict | None = None
    after: dict | None = None
    mutated: list = field(default_factory=list)
    ret: dict | None = None
    exc: dict | None = None
    incomplete: bool = False
    call_line: int | None = None   # line in the parent that made this call
    last_line: int | None = None   # root only: the line the test was on when it ended
    raised: str | None = None      # type name of the exception the call ended with, if any
    closure: list = field(default_factory=list)  # inputs that are variables of the enclosing function
    depth: int = 0

    @property
    def opaque(self):
        return not self.monitored

    @classmethod
    def from_json(cls, d):
        return cls(
            id=d["id"], path=d["path"], qualname=d["qualname"], func=d["func"],
            file=d["file"], line=d["line"], parent=d["parent"], children=list(d["children"]),
            monitored=d["monitored"], own_lines=[tuple(x) for x in d.get("own_lines", [])],
            args=d.get("args"), after=d.get("after"), mutated=d.get("mutated", []),
            ret=d.get("ret"), exc=d.get("exc"), incomplete=d.get("incomplete", False),
            call_line=d.get("call_line"), last_line=d.get("last_line"), raised=d.get("raised"),
            closure=d.get("closure", []),
        )

    # -- values ---------------------------------------------------------
    def input_key(self):
        if self.args is None:
            return None
        return tuple((name, snap["full"]) for name, snap in self.args.items())

    def after_full(self, name):
        if self.after and name in self.after:
            return self.after[name]["full"]
        return self.args[name]["full"]

    def output_key(self):
        """Return value, exception and post-call state of every argument."""
        if self.args is None:
            return None
        return (
            self.ret["full"] if self.ret else None,
            self.exc["full"] if self.exc else None,
            tuple((name, self.after_full(name)) for name in self.args),
        )

    def memo_key(self):
        if self.args is None:
            return None
        return (self.func, self.input_key(), self.output_key())

    def args_summary(self, width=60, each=24):
        if self.args is None:
            return "…"
        parts = [f"{n}={truncate(s['short'], each)}" for n, s in self.args.items() if n != "self"]
        return truncate(", ".join(parts), width)

    def output_summary(self, width=30):
        if self.args is None:
            return ""
        if self.exc:
            text = "raises " + self.exc["short"]
        else:
            text = "→ " + self.ret["short"] if self.ret else "→ ?"
        if self.mutated:
            text += f" (mutates {', '.join(self.mutated)})"
        return truncate(text, width)


@dataclass
class SearchHints:
    """What the tuning policy adds to the search over this tree (defaults: nothing)."""

    prior_scale: list | None = None       # per-node multiplier on the prior
    repeat_discount: float = 1.0          # factor per "yes" about another call of the function
    test_funcs: frozenset = frozenset()   # function keys that may never be the reported bug
    evidence_stop: bool = False           # "confident" needs a "no" about the blamed function
    zoom_fanout: int = 0                  # a wrong call with this many open callees goes to zoom
    settle_leader: bool = False           # ask the open callees of a wrong leading hypothesis first
    answer_error: dict = field(default_factory=dict)  # {path: error rate} of answers with a confidence


class ExecutionTree:
    def __init__(self, nodes, test_id="", meta=None):
        self.nodes = nodes
        self.test_id = test_id
        self.meta = meta or {}
        self.hints = SearchHints()
        self.by_path = {n.path: n for n in nodes}
        self.size = [1] * len(nodes)
        for node in reversed(nodes):
            if node.parent is not None:
                self.size[node.parent] += self.size[node.id]
        for node in nodes:
            node.depth = 0 if node.parent is None else nodes[node.parent].depth + 1

    @classmethod
    def from_json(cls, node_dicts, test_id="", meta=None):
        return cls([Node.from_json(d) for d in node_dicts], test_id, meta)

    @property
    def root(self):
        return self.nodes[0]

    def __len__(self):
        return len(self.nodes)

    def children(self, node):
        return [self.nodes[c] for c in node.children]

    def subtree_range(self, node):
        return range(node.id, node.id + self.size[node.id])

    def in_subtree(self, b, q):
        """True if node b is q or a descendant of q."""
        return q.id <= b.id < q.id + self.size[q.id]

    def ancestors(self, node):
        out = []
        while node.parent is not None:
            node = self.nodes[node.parent]
            out.append(node)
        return out

    def monitored_count(self):
        return sum(1 for n in self.nodes if n.monitored)


# how a test ends when an assertion fails, as opposed to code under test raising
ASSERTION_FAILURES = frozenset({"AssertionError", "Failed"})


def crash_chain(tree):
    """The calls the test's fatal exception travelled through, outermost first.

    Empty when the test failed on an assertion of its own. Otherwise the chain
    follows, from the test down, the last callee that ended with an exception;
    its last element is the call in which the exception started. The test
    itself is not part of the chain. A test whose fixture failed never ran, so
    it has no exception of its own and the chain starts at the fixture.
    """
    node = tree.root
    if node.raised in ASSERTION_FAILURES:
        return []
    chain = []
    while True:
        raising = [child for child in tree.children(node) if child.raised]
        if not raising:
            return chain
        node = raising[-1]
        chain.append(node)


def node_status(node, answers):
    """Marker key for node given {path: (verdict, source)}."""
    entry = answers.get(node.path)
    if entry is not None:
        verdict, source = entry
        if source == "trust":
            return "trust"
        return verdict
    if node.parent is None:
        return "no"  # the failing test itself
    return "opaque" if node.opaque else "pending"


def render_tree(tree, answers=None, posterior=None, highlight=None, collapse=True,
                ascii_only=False, max_lines=400):
    """ASCII rendering of the tree with status markers and posterior %."""
    answers = answers or {}
    markers = ASCII_MARKERS if ascii_only else MARKERS
    mass = None
    if posterior is not None:
        mass = [0.0] * len(tree)
        for node in reversed(tree.nodes):
            mass[node.id] += posterior[node.id]
            if node.parent is not None:
                mass[node.parent] += mass[node.id]
    on_path = set()
    if highlight is not None:
        on_path = {highlight} | {a.id for a in tree.ancestors(tree.nodes[highlight])}

    def relevant(node):
        if node.id in on_path:
            return True
        if mass is not None and mass[node.id] >= 0.01:
            return True
        return answers.get(node.path, (None, None))[0] == "no"

    out = []

    def line_for(node, indent, count=1):
        status = node_status(node, answers)
        text = f"{'  ' * indent}{markers[status]} {node.qualname}({node.args_summary()})"
        if count > 1:
            text += f" ×{count}"
        else:
            summary = node.output_summary()
            if summary:
                text += f" {summary}"
        if posterior is not None:
            text = f"{text:<92} {100 * posterior[node.id]:5.1f}%"
        if node.id == highlight:
            text += "  ◀ top hypothesis" if not ascii_only else "  <- top hypothesis"
        return text

    def visit(node, indent):
        if len(out) >= max_lines:
            return
        out.append(line_for(node, indent))
        kids = tree.children(node)
        i = 0
        while i < len(kids):
            j = i + 1
            if collapse:
                status = node_status(kids[i], answers)
                while (j < len(kids) and kids[j].qualname == kids[i].qualname
                       and node_status(kids[j], answers) == status):
                    j += 1
            group = kids[i:j]
            if len(group) > 1 and not any(relevant(k) for k in group):
                out.append(line_for(group[0], indent + 1, count=len(group)))
            else:
                for k in group:
                    visit(k, indent + 1)
            i = j

    visit(tree.root, 0)
    if len(out) >= max_lines:
        out.append(f"... (truncated at {max_lines} lines)")
    return "\n".join(out)
