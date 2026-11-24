"""The BugsInPy harness's pure parts, and the session behaviour it relies on."""

import os

import pytest

from qdebug.bugsinpy import (
    buggy_functions,
    parse_tests,
    patch_locations,
    python_version,
    requirements,
    select_bugs,
    unittest_to_nodeid,
    write_scm_version,
)
from qdebug.session import DebugSession, SessionConfig, SessionError
from qdebug.spectrum import scan_functions

PATCH = """\
diff --git a/pkg/a.py b/pkg/a.py
index 1..2 100644
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -10,5 +10,5 @@ def f():
 x = 1
-y = 2
+y = 3
 z = 3

 w = 4
@@ -30,2 +30,3 @@ def g():
 a = 1
+b = 2
 c = 3
diff --git a/pkg/b.py b/pkg/b.py
--- a/pkg/b.py
+++ b/pkg/b.py
@@ -5,3 +5,2 @@
 keep
--- not a header: a removed line that starts with "-- "
 keep2
\\ No newline at end of file
diff --git a/pkg/c.py b/pkg/c.py
--- a/pkg/c.py
+++ b/pkg/c.py
@@ -7,0 +8,1 @@
+appended()
diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1 +1 @@
-old
+new
"""


def test_patch_locations():
    assert patch_locations(PATCH) == {
        "pkg/a.py": ([11, 30, 31], "change"),  # a changed line; an insertion between 30 and 31
        "pkg/b.py": ([6], "change"),
        "pkg/c.py": ([7, 8], "insert"),        # "-7,0": inserted after line 7
    }                                          # test files are not ground truth


def test_unittest_ids_and_run_test_commands(tmp_path):
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_utils.py").write_text("")
    assert unittest_to_nodeid("test.test_utils.TestUtil.test_x", str(tmp_path)) == \
        "test/test_utils.py::TestUtil::test_x"
    assert unittest_to_nodeid("nope.TestX.test_y", str(tmp_path)) is None
    text = ("python -m unittest -q test.test_utils.TestUtil.test_a;\n"
            "pytest -q -s tests/test_b.py::test_b;python3 -m pytest tests/test_c.py::TestC::test_c\n"
            "tox tests/test_d.py::test_d\n")
    assert parse_tests(text, str(tmp_path)) == [
        "test/test_utils.py::TestUtil::test_a", "tests/test_b.py::test_b",
        "tests/test_c.py::TestC::test_c", "tests/test_d.py::test_d"]
    # scrapy bug 1 names a private helper of the test class first: it is skipped
    helper = ("python -m unittest -q test.test_utils.TestUtil._get_args\n"
              "python -m unittest -q test.test_utils.TestUtil.test_a\n")
    assert parse_tests(helper, str(tmp_path)) == ["test/test_utils.py::TestUtil::test_a"]


def test_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "attrs==19.3.0\nthefuck==3.29\n-e git+https://x/y#egg=z\npkg-resources==0.0.0\n\nmock==4.0.2\n")
    (tmp_path / "setup.sh").write_text("python setup.py install\npip3 install nose\npip install -U flake8\n")
    assert requirements(str(tmp_path), "PySnooper") == [
        "attrs==19.3.0", "mock==4.0.2", "nose", "flake8", "python_toolbox", "future", "six", "pytest<7",
        "setuptools<60"]
    (tmp_path / "requirements.txt").write_text("pytest==5.4.2\nsetuptools==44.0.0\n")
    (tmp_path / "setup.sh").unlink()
    assert requirements(str(tmp_path)) == ["pytest==5.4.2", "setuptools==44.0.0"]


def test_python_version_is_raised_to_the_oldest_available():
    assert python_version({"python_version": "3.6.9"}) == (3, 8)
    assert python_version({"python_version": "3.8.3"}) == (3, 8)
    assert python_version({"python_version": "3.9.1"}) == (3, 9)


def test_buggy_functions_are_innermost(tmp_path):
    (tmp_path / "m.py").write_text(
        "def outer():\n"          # 1
        "    def inner():\n"      # 2
        "        return 1\n"      # 3
        "    return inner()\n"    # 4
        "\n"
        "X = 1\n")                # 6: module level, no function
    functions = scan_functions(str(tmp_path))
    assert buggy_functions(functions, {"m.py": ([3, 4, 6], "change")}) == [
        "m.py::outer", "m.py::outer.<locals>.inner"]


def test_select_bugs(tmp_path):
    for project, ids in (("a", [1, 2, 3, 10]), ("b", [1])):
        for i in ids:
            (tmp_path / "projects" / project / "bugs" / str(i)).mkdir(parents=True)
    assert select_bugs(str(tmp_path), "a:2-3;10,b") == [("a", 2), ("a", 3), ("a", 10), ("b", 1)]
    with pytest.raises(SystemExit):
        select_bugs(str(tmp_path), "nope")


# ------------------------------------------------------------ session

def fake_run(nodes):
    def run(project, mode, test=None, **kwargs):
        if mode == "spectrum":
            return {"tests": {
                "t.py::test_a[1]": {"outcome": "failed", "lines": [["t.py", 1]], "functions": []},
                "t.py::test_a[2]": {"outcome": "failed", "lines": [["t.py", 1]], "functions": []},
                "t.py::test_b": {"outcome": "passed", "lines": [], "functions": []}}}
        if mode == "plain":
            return {"tests": {test: {"outcome": "failed", "call_time": 0.001}}}
        return {"tests": {test: {"outcome": "failed", "nodes": nodes,
                                 "failure": "...\nE   AttributeError: no attribute 'helper'"}}}
    return run


def test_parametrized_base_name_selects_its_first_failing_case(tmp_path):
    session = DebugSession(SessionConfig(project=str(tmp_path), test="t.py::test_a"),
                           oracle=None, run=fake_run([]), out=lambda *a: None)
    session.prepare()
    assert session.test_id == "t.py::test_a[1]"


def test_a_test_that_never_reaches_project_code_is_reported(tmp_path):
    session = DebugSession(SessionConfig(project=str(tmp_path)), oracle=None, run=fake_run([]),
                           out=lambda *a: None)
    session.prepare()
    with pytest.raises(SessionError, match="before its body ran.*no attribute 'helper'"):
        session.run_session()


def test_requirements_written_as_utf16_are_read(tmp_path):
    # some BugsInPy projects (black, fastapi, luigi, sanic, scrapy) ship UTF-16 files from Windows
    text = "aiohttp==3.6.2\r\nblack==19.3b0\r\nattrs==19.3.0\r\n"
    (tmp_path / "requirements.txt").write_bytes(text.encode("utf-16"))
    reqs = requirements(str(tmp_path), "black")
    assert reqs[:2] == ["aiohttp==3.6.2", "attrs==19.3.0"]  # the project's own package is left out
    assert all("\x00" not in r for r in reqs)


def test_setuptools_scm_version_file_is_written(tmp_path):
    # black's later commits import _black_version, which only exists after a pip install
    (tmp_path / "setup.py").write_text(
        'setup(use_scm_version={\n    "write_to": "_black_version.py",\n})\n', encoding="utf-8")
    write_scm_version(str(tmp_path))
    namespace = {}
    exec((tmp_path / "_black_version.py").read_text(encoding="utf-8"), namespace)
    assert namespace["version"] == "0.0.0"
    (tmp_path / "_black_version.py").write_text('version = "kept"\n', encoding="utf-8")
    write_scm_version(str(tmp_path))  # an existing file is left alone
    assert "kept" in (tmp_path / "_black_version.py").read_text(encoding="utf-8")


def test_a_failed_run_is_remembered():
    # a whole-suite run that times out must cost the timeout once per bug, not once per session
    from qdebug.evaluate import RunCache

    calls = []

    def run(project, mode, **kw):
        calls.append(mode)
        raise TimeoutError("timed out after 600 seconds")

    cache = RunCache(run=run)
    for _ in range(3):
        with pytest.raises(TimeoutError):
            cache("proj", "spectrum")
    assert calls == ["spectrum"]


def test_one_uninstallable_requirement_does_not_relax_the_other_pins(tmp_path, monkeypatch):
    # luigi, sanic, scrapy and tornado list pywin32 (or the stdlib's unittest), which cannot install on
    # Linux; installing the rest one at a time let a later package upgrade Twisted past its pin. And uv
    # rejects some old archives pip installs (Twisted 20.3.0, protego 0.1.16).
    import types

    import qdebug.bugsinpy as b

    bug_dir = tmp_path / "BugsInPy" / "projects" / "scrapy" / "bugs" / "1"
    bug_dir.mkdir(parents=True)
    (bug_dir / "requirements.txt").write_text("Twisted==20.3.0\npywin32==227\nlxml==4.5.0\nprotego==0.1.16\n")
    batches = []

    def fake_sh(cmd, cwd=None, timeout=1800, check=True):
        if cmd[:2] == ["uv", "venv"]:
            os.makedirs(cmd[-1], exist_ok=True)
            return types.SimpleNamespace(returncode=0)
        uv = cmd[0] == "uv"

        def bad(req):  # pywin32 never installs; uv also refuses the old Twisted and protego archives
            return "pywin32" in req or (uv and req in ("Twisted==20.3.0", "protego==0.1.16"))
        if "-r" in cmd:
            wanted = open(cmd[cmd.index("-r") + 1]).read().split()
            batches.append(("uv" if uv else "pip", wanted))
            return types.SimpleNamespace(returncode=1 if any(bad(r) for r in wanted) else 0)
        return types.SimpleNamespace(returncode=1 if bad(cmd[-1]) else 0)

    monkeypatch.setattr(b, "sh", fake_sh)
    ws = types.SimpleNamespace(work=str(tmp_path / "work"), bug_dir=lambda project, bug: str(bug_dir))
    envs = b.Environments(ws, log=lambda *a: None)
    monkeypatch.setattr(envs, "interpreter", lambda version: "python3.8")
    env, version, note = envs.get("scrapy", "1", {"python_version": "3.8"})
    tool, last = batches[-1]
    # everything but pywin32 installed together by pip, with every pin
    assert tool == "pip" and "pywin32==227" not in last
    assert {"Twisted==20.3.0", "lxml==4.5.0", "protego==0.1.16"} <= set(last)
    assert note == "v3: all requirements except: dropped pywin32==227"
    # an environment from the older fallback is built again; a plain pinned one is kept
    for old, rebuilt in (("failed: pywin32==227", True), ("all requirements except: newest Twisted", True),
                         ("all requirements", False)):
        with open(os.path.join(env, ".qdebug-ready"), "w") as fh:
            fh.write(old)
        batches.clear()
        envs.get("scrapy", "1", {"python_version": "3.8"})
        assert bool(batches) == rebuilt, old
