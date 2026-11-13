"""Run traced pytest executions in a fresh subprocess.

Subprocess entry:  python -m qdebug.runner --project DIR --mode MODE --out FILE ...
Parent side:       invoke(project, mode, ...) -> dict (the JSON the child wrote)

Every traced run gets its own interpreter so that module caching never mixes
the buggy and the fixed copy of a project. PYTHONHASHSEED=0 keeps set and
dict reprs deterministic across runs.

RunOptions adapt the child to a real project: the interpreter of the
project's own environment (so its dependencies import), its installed pytest
plugins (pytest-django, pytest-asyncio, ...), extra pytest arguments, and the
limits on the size of the recorded execution tree.

This module, plugin.py and tracer.py also run inside the child, i.e. on the
project's interpreter, so they stay compatible with Python 3.8.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from qdebug.tracer import TreeLimits, set_path_masks

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODES = ("spectrum", "tree", "zoom", "plain")
SPECTRUM_BACKENDS = ("auto", "settrace", "monitoring")
# pytest exit codes that mean "no usable results" (1 = some tests failed is expected)
PYTEST_ERROR_CODES = {2: "was interrupted", 3: "hit an internal error",
                      4: "reported a usage error", 5: "collected no tests"}


class RunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunOptions:
    python: str | None = None      # interpreter (or virtualenv dir) of the project; None: this one
    autoload_plugins: bool = True  # load the pytest plugins installed in that environment
    pytest_args: tuple = ()        # extra arguments for every run, e.g. ("--ds=site.settings",)
    suite: tuple = ()              # test paths / selection for the whole-suite spectrum run only
    pythonpath: tuple = ()         # extra import paths, relative to the project (or absolute)
    seed_random: bool = True       # random.seed(0) before every test (determinism across re-runs)
    spectrum_backend: str = "auto"
    max_nodes: int = TreeLimits.max_nodes  # execution-tree limits, see tracer.TreeLimits
    max_repeat: int = TreeLimits.max_repeat
    max_depth: int = TreeLimits.max_depth
    timeout: int = 600


DEFAULT_OPTIONS = RunOptions()


def resolve_python(python):
    """The interpreter to run: an executable, or the python inside a virtualenv dir."""
    if not python:
        return sys.executable
    if os.path.isdir(python):
        for rel in (("Scripts", "python.exe"), ("bin", "python3"), ("bin", "python")):
            candidate = os.path.join(python, *rel)
            if os.path.isfile(candidate):
                return candidate
        raise RunnerError(f"no python interpreter found in virtualenv {python}")
    return python


def make_runner(options):
    """invoke() bound to options, with the same call signature as invoke."""
    return functools.partial(invoke, options=options)


def invoke(project, mode, test=None, monitored=None, target=None, max_repr=300, timeout=None,
           options=None):
    """Run pytest on project in a subprocess and return the decoded results.

    monitored: iterable of function keys, or None to monitor everything
    (only meaningful for mode="tree").
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    opts = options or DEFAULT_OPTIONS
    project = os.path.abspath(project)
    workdir = tempfile.mkdtemp(prefix="qdebug_")
    out_path = os.path.join(workdir, "result.json")
    python = resolve_python(opts.python)
    cmd = [python, "-m", "qdebug.runner", "--project", project,
           "--mode", mode, "--out", out_path, "--max-repr", str(max_repr),
           "--spectrum-backend", opts.spectrum_backend, "--max-nodes", str(opts.max_nodes),
           "--max-repeat", str(opts.max_repeat), "--max-depth", str(opts.max_depth)]
    if test:
        cmd += ["--test", test]
    if target:
        cmd += ["--target", target]
    if not opts.seed_random:
        cmd.append("--no-seed-random")
    if monitored is not None:
        monitor_path = os.path.join(workdir, "monitored.json")
        with open(monitor_path, "w", encoding="utf-8") as fh:
            json.dump(sorted(monitored), fh)
        cmd += ["--monitor-file", monitor_path]
    extra = list(opts.pytest_args) + ([] if test else list(opts.suite))
    if extra:
        # after "--" so that arguments starting with "-" reach pytest untouched
        cmd += ["--", *extra]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if opts.autoload_plugins:
        env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    else:
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    paths = ([REPO_ROOT] + [os.path.normpath(os.path.join(project, p)) for p in opts.pythonpath]
             + [env.get("PYTHONPATH")])
    env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
    start = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=project, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout or opts.timeout)
    except FileNotFoundError:
        raise RunnerError(f"python interpreter not found: {python}") from None
    wall = time.perf_counter() - start
    if not os.path.exists(out_path):
        hint = ""
        if "No module named pytest" in proc.stderr or "No module named 'pytest'" in proc.stderr:
            hint = (f"\npytest is not installed for {python}. Install it there, run `deactivate` "
                    f"if an empty virtualenv is active, or pass --python with one that has pytest.")
        raise RunnerError(f"runner produced no output (exit {proc.returncode}).{hint}\n"
                          f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    with open(out_path, encoding="utf-8") as fh:
        data = json.load(fh)
    errors = data.get("collection_errors") or {}
    if data.get("exit_code") in PYTEST_ERROR_CODES:
        # a collection error explains most of these; pytest's output may bury it under warnings
        first = "".join(f"ERROR collecting {where}:\n{text}\n" for where, text in list(errors.items())[:1])
        raise RunnerError(f"pytest {PYTEST_ERROR_CODES[data['exit_code']]} (exit {data['exit_code']}) "
                          f"in {project}.\n{first}stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}")
    if errors and not data.get("tests"):
        where, text = next(iter(errors.items()))
        raise RunnerError(f"pytest could not collect any test in {project}: {len(errors)} collection "
                          f"error(s), the first in {where}:\n{text}")
    data["wall_time"] = wall
    shutil.rmtree(workdir, ignore_errors=True)  # result, monitored set, pytest's basetemp
    return data


def pytest_version(pytest):
    try:
        return tuple(int(x) for x in pytest.__version__.split(".")[:2])
    except ValueError:  # e.g. "3.2.dev1"
        return (99, 0)


def installed_pytest_plugins():
    """Names of the pytest plugins installed as entry points (group pytest11).

    Both importlib.metadata and pkg_resources are asked: old pytest loads
    plugins through pkg_resources, which also sees distributions that
    importlib.metadata does not (e.g. ones vendored inside setuptools).
    """
    names = set()
    try:
        from importlib import metadata
        eps = metadata.entry_points()
        group = eps.select(group="pytest11") if hasattr(eps, "select") else eps.get("pytest11", [])
        names.update(ep.name for ep in group)
    except Exception:  # noqa: BLE001 - Python < 3.8, or broken metadata
        pass
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import pkg_resources
        names.update(ep.name for ep in pkg_resources.iter_entry_points("pytest11"))
    except Exception:  # noqa: BLE001
        pass
    return sorted(names)


def plugin_neutralizing_args():
    """pytest arguments that keep installed plugins from breaking traced runs.

    Tracing is per process and re-runs must repeat the same execution, so
    pytest-xdist runs in-process (-n 0), pytest-randomly uses a fixed seed,
    and pytest-cov does not install a competing tracer. Each argument is only
    added when the plugin is installed (pytest rejects unknown options). They
    come after the project's addopts, so they win.
    """
    args = []
    if importlib.util.find_spec("xdist") is not None:
        args += ["-n", "0"]
    if importlib.util.find_spec("pytest_randomly") is not None:
        args.append("--randomly-seed=0")
    if importlib.util.find_spec("pytest_cov") is not None:
        args.append("--no-cov")
    return args


def main(argv=None):
    parser = argparse.ArgumentParser(description="qdebug subprocess runner")
    parser.add_argument("--project", required=True)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--out", required=True)
    parser.add_argument("--test")
    parser.add_argument("--target")
    parser.add_argument("--monitor-file")
    parser.add_argument("--max-repr", type=int, default=300)
    parser.add_argument("--spectrum-backend", choices=SPECTRUM_BACKENDS, default="auto")
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_OPTIONS.max_nodes)
    parser.add_argument("--max-repeat", type=int, default=DEFAULT_OPTIONS.max_repeat)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_OPTIONS.max_depth)
    parser.add_argument("--no-seed-random", action="store_true")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args(argv)

    import pytest

    from qdebug.plugin import QDebugPlugin

    monitored = None
    if args.monitor_file:
        with open(args.monitor_file, encoding="utf-8") as fh:
            monitored = set(json.load(fh))
    project = os.path.abspath(args.project)
    limits = TreeLimits(args.max_nodes, args.max_repeat, args.max_depth)
    plugin = QDebugPlugin(args.mode, project, monitored, args.target, args.max_repr,
                          spectrum_backend=args.spectrum_backend, limits=limits,
                          seed_random=not args.no_seed_random)
    pytest_args = ["-q", "-p", "no:cacheprovider"]
    if pytest_version(pytest) >= (3, 5):  # older pytest has no --rootdir; cwd is the project anyway
        pytest_args += ["--rootdir", project]
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1":
        pytest_args += plugin_neutralizing_args()
    else:  # old pytest ignores the variable; blocking each plugin works in every version
        for name in installed_pytest_plugins():
            pytest_args += ["-p", f"no:{name}"]
    if args.mode == "spectrum":
        # one broken test module must not stop the whole-suite run
        pytest_args.append("--continue-on-collection-errors")
    # tmp_path / tmpdir under a per-run directory, masked in snapshots like the project
    basetemp = os.path.join(os.path.dirname(os.path.abspath(args.out)), "basetemp")
    pytest_args += ["--basetemp", basetemp]
    set_path_masks([(project, "<project>"), (basetemp, "<basetemp>")])
    pytest_args += args.pytest_args
    if args.test:
        pytest_args.append(args.test)
    exit_code = pytest.main(pytest_args, plugins=[plugin])
    payload = {"mode": args.mode, "exit_code": int(exit_code), "tests": plugin.results,
               "tree_limits_hit": plugin.limits_hit, "collection_errors": plugin.collection_errors}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
