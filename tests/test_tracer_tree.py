"""The tracer and execution tree, exercised in-process on a temporary module."""

import importlib
import sys
import textwrap

import pytest

from helpers import SMALL, make_tree
from qdebug.tracer import TreeTracer, ZoomTracer, alias_groups, safe_repr, snapshot
from qdebug.tree import ExecutionTree, render_tree

SOURCE = textwrap.dedent('''
    class Box:
        def __init__(self):
            self.items = []

        def put(self, x):
            self.items.append(x)
            return len(self.items)


    def helper(x):
        return x * 2


    def sorts_in_place(values):
        values.sort()
        return values[0]


    def boom():
        raise ValueError("bad")


    def root():
        box = Box()
        box.put(helper(1))
        box.put(helper(2))
        total = sum(v for v in box.items)
        smallest = sorts_in_place([3, 1, 2])
        try:
            boom()
        except ValueError:
            pass
        return total + smallest
''')


@pytest.fixture
def module(tmp_path, monkeypatch):
    (tmp_path / "tmod.py").write_text(SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("tmod", None)
    mod = importlib.import_module("tmod")
    yield tmp_path, mod
    sys.modules.pop("tmod", None)


def trace(tracer, func):
    tracer.start()
    try:
        func()
    finally:
        tracer.stop()
    return tracer.result()


def test_tree_structure_and_call_paths(module):
    project, mod = module
    data = trace(TreeTracer(str(project)), mod.root)
    tree = ExecutionTree.from_json(data["nodes"])
    paths = [n.path for n in tree.nodes]
    assert paths == [
        "root",
        "root/Box.__init__#0",
        "root/helper#0",
        "root/Box.put#0",
        "root/helper#1",
        "root/Box.put#1",
        "root/sorts_in_place#0",
        "root/boom#0",
    ]
    assert tree.size[0] == len(tree)
    # the generator expression is transparent: its line belongs to root
    assert all("genexpr" not in p for p in paths)
    assert tree.root.call_line is None
    assert tree.by_path["root/helper#0"].call_line == tree.by_path["root/Box.put#0"].call_line


def test_values_mutations_and_exceptions(module):
    project, mod = module
    tree = ExecutionTree.from_json(trace(TreeTracer(str(project)), mod.root)["nodes"])
    assert not tree.root.monitored  # the test itself is never asked about
    helper = tree.by_path["root/helper#1"]
    assert helper.args["x"]["full"] == "2" and helper.ret["full"] == "4"
    put = tree.by_path["root/Box.put#1"]
    assert put.mutated == ["self"]  # self.__dict__ changed
    assert put.after["self"]["full"] == "{'items': [2, 4]}"
    sorter = tree.by_path["root/sorts_in_place#0"]
    assert sorter.mutated == ["values"]
    assert sorter.args["values"]["full"] == "[3, 1, 2]"
    assert sorter.after["values"]["full"] == "[1, 2, 3]"
    boom = tree.by_path["root/boom#0"]
    assert boom.ret is None and boom.exc["full"].startswith("ValueError")
    assert tree.root.ret is None  # root is unmonitored: no values


def test_selective_monitoring(module):
    project, mod = module
    data = trace(TreeTracer(str(project), monitored={"tmod.py::helper"}), mod.root)
    tree = ExecutionTree.from_json(data["nodes"])
    assert len(tree) == 8  # structure is always recorded
    assert {n.qualname for n in tree.nodes if n.monitored} == {"helper"}
    assert tree.by_path["root/Box.put#0"].args is None


def test_call_paths_are_stable_across_monitoring_tiers(module):
    project, mod = module
    a = ExecutionTree.from_json(trace(TreeTracer(str(project), monitored=set()), mod.root)["nodes"])
    b = ExecutionTree.from_json(trace(TreeTracer(str(project)), mod.root)["nodes"])
    assert [n.path for n in a.nodes] == [n.path for n in b.nodes]


def test_zoom_checkpoints(module):
    project, mod = module
    data = trace(ZoomTracer(str(project), "root/sorts_in_place#0"), mod.root)
    cps = data["checkpoints"]
    assert data["found"]
    assert [c["kind"] for c in cps] == ["line", "line", "return"]
    assert cps[0]["locals"]["values"]["full"] == "[3, 1, 2]"   # before values.sort()
    assert cps[1]["locals"]["values"]["full"] == "[1, 2, 3]"   # before the return line
    assert cps[2]["ret"]["full"] == "1"
    assert cps[0]["occurrence"] == 1


def test_safe_repr_and_snapshots():
    class Unprintable:
        def __repr__(self):
            raise RuntimeError("no")

    assert safe_repr(Unprintable()).startswith("<unrepresentable Unprintable")
    assert "0x?" in safe_repr(object())
    s = snapshot("x" * 1000, max_repr=20)
    assert len(s["short"]) == 20 and len(s["full"]) == 1002


def test_alias_groups():
    shared = [1]
    assert alias_groups([("a", shared), ("b", shared), ("c", [1]), ("n", 5), ("m", 5)]) == [["a", "b"]]


def test_render_tree_markers_posterior_and_collapse():
    spec = ("test", [("a", [("b", []), ("b", []), ("b", [])]), ("e", [])])
    tree = make_tree(spec, monitored={"a", "b"})
    answers = {"test/a#0": ("no", "oracle")}
    posterior = [0.0, 0.05, 0.0, 0.0, 0.0, 0.95]
    text = render_tree(tree, answers, posterior, highlight=5)
    lines = text.splitlines()
    assert lines[0].startswith("[✗] test")
    assert "[✗] a" in lines[1]
    assert "×3" in lines[2]            # irrelevant identical siblings collapsed
    assert lines[3].strip().startswith("[○] e")  # opaque
    assert "95.0%" in lines[3] and "top hypothesis" in lines[3]
    ascii_text = render_tree(tree, answers, posterior, highlight=5, ascii_only=True)
    assert "[x] a" in ascii_text and "[o] e" in ascii_text


def test_subtree_helpers():
    tree = make_tree(SMALL)
    a, d, e = tree.nodes[1], tree.nodes[4], tree.nodes[5]
    assert list(tree.subtree_range(a)) == [1, 2, 3, 4]
    assert tree.in_subtree(d, a) and not tree.in_subtree(e, a)
    assert [n.id for n in tree.ancestors(d)] == [3, 1, 0]
