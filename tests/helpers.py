"""Synthetic trees and scripted oracles shared by the unit tests."""

from qdebug.oracles import Answer, Oracle
from qdebug.tree import ExecutionTree


def snap(text):
    return {"short": text, "full": text, "type": "str"}


def make_tree(spec, monitored=None, values=None):
    """Build an ExecutionTree from a nested spec.

    spec: ("name", [child specs]) where name may be "func" or "func@label";
    the qualname is the part before "@". Nodes are numbered in pre-order.
    monitored: set of qualnames whose nodes are monitored (default: all but root).
    values: {label or qualname: (input text, output text)} for memo tests.
    """
    nodes = []
    values = values or {}

    def visit(item, parent, parent_path, counts):
        name, children = item
        qualname = name.split("@")[0]
        k = counts.get(qualname, 0)
        counts[qualname] = k + 1
        path = qualname if parent is None else f"{parent_path}/{qualname}#{k}"
        node_id = len(nodes)
        is_mon = parent is not None and (monitored is None or qualname in monitored)
        inp, out = values.get(name, values.get(qualname, (f"in{node_id}", f"out{node_id}")))
        nodes.append({
            "id": node_id, "path": path, "qualname": qualname, "func": f"m.py::{qualname}",
            "file": "m.py", "line": 1, "parent": parent, "children": [], "monitored": is_mon,
            "own_lines": [], "args": {"x": snap(inp)} if is_mon else None,
            "after": {} if is_mon else None, "mutated": [],
            "ret": snap(out) if is_mon else None, "exc": None,
        })
        if parent is not None:
            nodes[parent]["children"].append(node_id)
        child_counts = {}
        for child in children:
            visit(child, node_id, path, child_counts)

    visit(spec, None, "", {})
    return ExecutionTree.from_json(nodes, "test")


def wrong_set(tree, bug_id):
    """Ids of nodes whose output is wrong when the bug is in node bug_id."""
    bug = tree.nodes[bug_id]
    return {bug.id} | {a.id for a in tree.ancestors(bug)}


class ScriptedOracle(Oracle):
    """Answers call questions from a fixed set of wrong node ids."""

    name = "scripted"

    def __init__(self, tree, bug_id, unknown=()):
        self.wrong = wrong_set(tree, bug_id)
        self.unknown = set(unknown)
        self.asked = []

    def judge(self, question, ctx=None):
        node = question.node
        self.asked.append(node.path)
        if node.id in self.unknown:
            return Answer("unknown")
        return Answer("no" if node.id in self.wrong else "yes")


def ask_loop(strategy, tree, oracle, limit=50):
    """Drive a strategy against an oracle without a session. Returns answers."""
    from qdebug.oracles import Question
    from qdebug.strategies import ESCALATE

    answers = {}
    for _ in range(limit):
        step = strategy.next_question(tree, answers)
        if step == ESCALATE:
            strategy.escalation_exhausted = True
            continue
        if step is None:
            break
        answers[step.path] = oracle.judge(Question("call", step)).verdict
    return answers


# A small tree used by several tests:
#   0 test
#   ├─ 1 a
#   │  ├─ 2 b
#   │  └─ 3 c
#   │     └─ 4 d
#   └─ 5 e
#      ├─ 6 f
#      └─ 7 g
SMALL = ("test", [
    ("a", [("b", []), ("c", [("d", [])])]),
    ("e", [("f", []), ("g", [])]),
])
