"""What running on real repositories needs: robust indexing, value rendering,
bounded trees, plugin handling, interpreter choice and determinism checks.

tests/fixtures/realistic_project is a small src-layout package with the
awkward parts of real code: a Latin-1 source file, a Python 2 script, a
virtualenv directory, __slots__ classes without __repr__, randomness, a
365-iteration loop of identical calls and a hot loop.
"""

import importlib
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

from helpers import make_tree
from qdebug import runner
from qdebug.evaluate import RunCache
from qdebug.oracles import GroundTruthOracle
from qdebug.runner import RunnerError, RunOptions, invoke, resolve_python
from qdebug.session import DebugSession, SessionConfig, SessionError, check_same_execution
from qdebug.spectrum import read_source_lines, scan_functions
from qdebug.tracer import TreeLimits, TreeTracer, safe_repr
from qdebug.tree import ExecutionTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "realistic_project")
BUG_FILE = os.path.join("src", "ledger", "accounts.py")
BUG_LINE = 25  # in the planted bug: "self.balance -= amount" forgets the fee


def plant_bug(dest):
    shutil.copytree(FIXTURE, dest)
    path = os.path.join(dest, BUG_FILE)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    buggy = text.replace("self.balance -= amount + fee", "self.balance -= amount")
    assert buggy != text
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(buggy)
    return str(dest)


# ------------------------------------------------------------ value rendering

class Plain:
    def __init__(self, a, b):
        self.a = a
        self.b = b


class Slotted:
    __slots__ = ("x", "y")

    def __init__(self, x):
        self.x = x  # y deliberately unset


def test_default_repr_objects_render_their_attributes():
    assert safe_repr(Plain(1, "s")) == "Plain(a=1, b='s')"
    assert safe_repr(Slotted(3)) == "Slotted(x=3)"
    # previously both instances were "<Plain object at 0x?>" and compared equal
    assert safe_repr(Plain(1, 2)) != safe_repr(Plain(1, 3))


def test_containers_recurse_and_sets_are_ordered():
    value = {"k": [Plain(1, (2,))], "t": (Slotted(0),)}
    assert safe_repr(value) == "{'k': [Plain(a=1, b=(2,))], 't': (Slotted(x=0),)}"
    a, b = Plain(2, 0), Plain(1, 0)
    assert safe_repr({a, b}) == safe_repr({b, a}) == "{Plain(a=1, b=0), Plain(a=2, b=0)}"
    assert safe_repr(set()) == "set()" and safe_repr(frozenset()) == "frozenset()"


def test_cycles_custom_reprs_and_limits():
    p = Plain(None, [])
    p.b.append(p)
    assert safe_repr(p) == "Plain(a=None, b=[<...>])"

    class Custom:
        def __repr__(self):
            return "Custom!"

    assert safe_repr([Custom()]) == "[Custom!]"
    assert "0x?" in safe_repr(object())  # nothing to show but the (masked) address
    text = safe_repr(list(range(100_000)), limit=50)
    assert text.endswith("...<truncated>") and len(text) == 50 + len("...<truncated>")


def test_numpy_arrays_get_a_digest_of_all_data():
    np = pytest.importorskip("numpy")
    a = np.zeros(5000)
    b = a.copy()
    b[2500] = 1  # hidden in the middle, which numpy's repr elides
    assert repr(a) == repr(b)
    assert safe_repr(a) != safe_repr(b)


# ------------------------------------------------------------ function index

def test_index_reads_any_encoding_and_skips_virtualenvs_and_python2():
    index = scan_functions(FIXTURE)
    assert "src/ledger/legacy_format.py::format_cents" in index      # Latin-1 file
    assert not any(k.startswith("env/") for k in index)               # has pyvenv.cfg
    assert not any("old_script" in k for k in index)                  # SyntaxError
    lines = read_source_lines(FIXTURE, "src/ledger/legacy_format.py")
    assert "é" in lines[1]


def test_root_level_build_dir_is_skipped_but_nested_package_named_build_is_not(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "gen.py").write_text("def generated():\n    pass\n")
    (tmp_path / "src" / "build").mkdir(parents=True)
    (tmp_path / "src" / "build" / "core.py").write_text("def real():\n    pass\n")
    index = scan_functions(str(tmp_path))
    assert "src/build/core.py::real" in index
    assert "build/gen.py::generated" not in index


# ------------------------------------------------------------ tree limits

LOOP_SOURCE = textwrap.dedent('''
    def leaf(i):
        return i


    def recurse(n):
        return 0 if n == 0 else 1 + recurse(n - 1)


    def root():
        total = sum(leaf(i) for i in range(10))
        for i in range(10):
            total += leaf(i)
        return total + recurse(8)
''')


@pytest.fixture
def loop_module(tmp_path, monkeypatch):
    (tmp_path / "loopmod.py").write_text(LOOP_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("loopmod", None)
    yield tmp_path, importlib.import_module("loopmod")
    sys.modules.pop("loopmod", None)


def run_tree(project, func, limits):
    tracer = TreeTracer(str(project), limits=limits)
    tracer.start()
    try:
        func()
    finally:
        tracer.stop()
    return tracer, ExecutionTree.from_json(tracer.result()["nodes"])


def test_repeat_and_depth_limits_fold_calls_without_changing_paths(loop_module):
    project, mod = loop_module
    _, full = run_tree(project, mod.root, TreeLimits())
    tracer, small = run_tree(project, mod.root, TreeLimits(max_repeat=3, max_depth=4))
    assert len(full) == 1 + 20 + 9
    assert tracer.limits_hit == {"max_repeat": 17, "max_depth": 6}
    full_paths = {n.path for n in full.nodes}
    assert {n.path for n in small.nodes} <= full_paths  # recorded calls keep their ids
    assert [n.path for n in small.children(small.root)] == [
        "root/leaf#0", "root/leaf#1", "root/leaf#2", "root/recurse#0"]
    # folded calls' lines count as the nearest recorded ancestor's own code
    deepest = max(small.nodes, key=lambda n: n.path.count("/"))
    assert deepest.path.count("/") == 3


def test_node_limit(loop_module):
    project, mod = loop_module
    tracer, tree = run_tree(project, mod.root, TreeLimits(max_nodes=5))
    assert len(tree) == 5 and tracer.limits_hit["max_nodes"] > 0


def test_fixture_loop_is_folded_and_zoom_still_finds_recorded_calls():
    test = "tests/test_ledger.py::test_interest_for_a_year"
    data = invoke(FIXTURE, "tree", test=test, options=RunOptions(max_repeat=50))
    nodes = next(iter(data["tests"].values()))["nodes"]
    paths = [n["path"] for n in nodes]
    assert data["tree_limits_hit"] == {"max_repeat": 2 * (365 - 50)}
    assert sum(p.split("/")[-1].startswith("daily_interest#") for p in paths) == 50
    target = next(p for p in paths if p.endswith("daily_interest#49"))
    zoom = invoke(FIXTURE, "zoom", test=test, target=target)
    assert next(iter(zoom["tests"].values()))["found"]


# ------------------------------------------------------------ determinism

def test_check_same_execution():
    a = make_tree(("test", [("f", []), ("g", [])]))
    check_same_execution(a, make_tree(("test", [("f", []), ("g", [])])))
    with pytest.raises(SessionError, match="different path"):
        check_same_execution(a, make_tree(("test", [("f", []), ("h", [])])))
    with pytest.raises(SessionError, match="3 vs 2 calls"):
        check_same_execution(a, make_tree(("test", [("f", [])])))


def test_random_is_seeded_before_every_test():
    test = "tests/test_ledger.py::test_small_transfer"
    numbers = []
    for _ in range(2):
        data = invoke(FIXTURE, "tree", test=test)
        nodes = next(iter(data["tests"].values()))["nodes"]
        opened = next(n for n in nodes if n["qualname"] == "Ledger.open")
        numbers.append(opened["ret"]["full"])
    assert numbers[0] == numbers[1] and "number=" in numbers[0]


# ------------------------------------------------------------ runner

def test_spectrum_backends_agree_on_the_fixture():
    if not hasattr(sys, "monitoring"):
        pytest.skip("sys.monitoring needs Python 3.12+")
    results = [invoke(FIXTURE, "spectrum", options=RunOptions(spectrum_backend=b))["tests"]
               for b in ("settrace", "monitoring")]
    assert results[0].keys() == results[1].keys() and len(results[0]) == 7
    for nodeid in results[0]:
        assert results[0][nodeid]["lines"] == results[1][nodeid]["lines"], nodeid
        assert results[0][nodeid]["functions"] == results[1][nodeid]["functions"], nodeid
    hot = "tests/test_ledger.py::test_hot_loop"
    # one event per line instead of one per executed line
    assert results[1][hot]["call_time"] < results[0][hot]["call_time"]


def test_resolve_python(tmp_path):
    assert resolve_python(None) == sys.executable
    venv = tmp_path / "venv"
    exe = venv / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert resolve_python(str(venv)) == str(exe)
    with pytest.raises(RunnerError, match="no python interpreter"):
        resolve_python(str(tmp_path))


def test_missing_interpreter_is_reported(tmp_path):
    with pytest.raises(RunnerError, match="not found"):
        invoke(FIXTURE, "plain", options=RunOptions(python=str(tmp_path / "nope.exe")))


def test_pytest_errors_are_reported_instead_of_empty_results(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    with pytest.raises(RunnerError, match="collected no tests"):
        invoke(str(tmp_path), "spectrum")


def test_extra_pytest_args_and_suite_selection():
    opts = RunOptions(pytest_args=("-k", "transfer"), suite=("tests/test_ledger.py",))
    tests = invoke(FIXTURE, "spectrum", options=opts)["tests"]
    assert sorted(t.split("::")[1] for t in tests) == ["test_large_transfer_charges_fee",
                                                       "test_small_transfer"]


def test_plugin_neutralizing_args(monkeypatch):
    installed = {"xdist", "pytest_randomly", "pytest_cov"}
    monkeypatch.setattr(runner.importlib.util, "find_spec",
                        lambda name: object() if name in installed else None)
    assert runner.plugin_neutralizing_args() == ["-n", "0", "--randomly-seed=0", "--no-cov"]
    installed.clear()
    assert runner.plugin_neutralizing_args() == []


# ------------------------------------------------------------ end to end

@pytest.mark.e2e
def test_planted_bug_in_slotted_class_is_localized_to_its_line(tmp_path):
    buggy = plant_bug(tmp_path / "buggy")
    cache = RunCache()
    session = DebugSession(SessionConfig(project=buggy), oracle=None, run=cache,
                           out=lambda *a, **k: None)
    session.prepare()
    session.oracle = GroundTruthOracle(FIXTURE, session.test_id, run=cache)
    found = session.run_session()
    assert found.func == "src/ledger/accounts.py::Account.withdraw"
    assert found.file == BUG_FILE.replace(os.sep, "/")
    assert session.zoom.status == "localized" and BUG_LINE in session.zoom.region


@pytest.mark.e2e
def test_cli_with_a_separate_virtualenv(tmp_path):
    """--python points at another environment; qdebug itself is not installed there."""
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip",
                    str(venv)], check=True, timeout=300)
    buggy = plant_bug(tmp_path / "buggy")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "qdebug", "rank", "--project", buggy, "--python", str(venv),
         "--limit", "3"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr
    assert "FAILED tests/test_ledger.py::test_large_transfer_charges_fee" in proc.stdout


# ------------------------------------------------------------ oracle comparability

def test_project_and_temp_paths_are_masked_in_snapshots(tmp_path):
    from qdebug.tracer import set_path_masks
    project = tmp_path / "checkout" / "buggy"
    try:
        set_path_masks([(str(project), "<project>")])
        values = [str(project / "pkg" / "a.py"), project.as_posix() + "/b", project / "c"]  # str, posix, Path
        assert safe_repr(values).count("<project>") == 3
        assert str(tmp_path) not in safe_repr(values).replace("<project>", "")
    finally:
        set_path_masks([])


def test_tempfile_names_are_seeded():
    import random
    import tempfile

    from qdebug.plugin import seed_everything

    state = random.getstate()
    try:
        names = []
        for _ in range(2):
            seed_everything()
            names.append(next(tempfile._get_candidate_names()))
        assert names[0] == names[1]
    finally:
        random.setstate(state)
        tempfile._name_sequence = None


def test_zoom_prefers_the_latest_of_equally_likely_calls():
    tree = make_tree(("test", [("f", []), ("f", []), ("f", []), ("g", [])]))
    f0, f1, f2, g = tree.nodes[1:]
    ranked = [(f0, 0.3), (f1, 0.3), (f2, 0.3), (g, 0.1)]
    assert DebugSession.zoom_candidate(ranked, set()) is f2
    assert DebugSession.zoom_candidate(ranked, {f2.path}) is f1
    assert DebugSession.zoom_candidate(ranked, {f0.path, f1.path, f2.path}) is g
    assert DebugSession.zoom_candidate([], set()) is None
