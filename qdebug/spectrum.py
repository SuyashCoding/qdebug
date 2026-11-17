"""Per-test coverage spectra and a static index of the project's functions."""

import ast
import os
import tokenize
import warnings
from dataclasses import dataclass, field

from qdebug.runner import invoke
from qdebug.tracer import TRANSPARENT_FLAGS, TRANSPARENT_NAMES, code_qualname

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "venv", "node_modules",
             "site-packages", "dist-packages"}
ROOT_SKIP_DIRS = {"build", "dist", "htmlcov"}  # only at the top: src/build/ may be a real package


def read_source(path):
    """Source text honouring PEP 263 coding cookies and BOMs; None if undecodable."""
    try:
        with tokenize.open(path) as fh:
            return fh.read()
    except (SyntaxError, UnicodeDecodeError, LookupError, OSError):
        return None  # bad/unknown coding cookie, undecodable bytes, unreadable file


def _skipped_dir(dirpath, name, top):
    if name in SKIP_DIRS or name.startswith(".") or name.endswith(".egg-info"):
        return True
    if dirpath == top and name in ROOT_SKIP_DIRS:
        return True
    # any virtualenv, whatever its name (env/, py312/, ...)
    return os.path.isfile(os.path.join(dirpath, name, "pyvenv.cfg"))


def is_test_file(relfile):
    parts = relfile.split("/")
    name = parts[-1]
    return ("tests" in parts[:-1] or "test" in parts[:-1] or name.startswith("test_")
            or name.endswith("_test.py") or name == "conftest.py")


@dataclass
class FuncInfo:
    func: str            # "relfile::qualname", the key used everywhere
    file: str
    qualname: str
    line: int            # co_firstlineno (first decorator line if decorated)
    def_line: int
    end_line: int
    signature: str
    doc: str
    source: str
    is_test: bool


def _walk_code(code):
    for const in code.co_consts:
        if hasattr(const, "co_code"):
            yield const
            yield from _walk_code(const)


def scan_functions(project):
    """Index every function defined in project/*.py by its function key."""
    project = os.path.abspath(project)
    index = {}
    for dirpath, dirnames, filenames in os.walk(project):
        dirnames[:] = sorted(d for d in dirnames if not _skipped_dir(dirpath, d, project))
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            relfile = os.path.relpath(path, project).replace(os.sep, "/")
            source = read_source(path)
            if source is None:
                continue
            try:
                with warnings.catch_warnings():  # old code: invalid escapes, "is" with literals
                    warnings.simplefilter("ignore")
                    tree = ast.parse(source)
                    module_code = compile(source, path, "exec")
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                continue  # e.g. Python 2 files, null bytes, generated giant literals
            lines = source.splitlines()
            defs = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = min([d.lineno for d in node.decorator_list] + [node.lineno])
                    defs[start] = node
            for code in _walk_code(module_code):
                if code.co_name in TRANSPARENT_NAMES or code.co_flags & TRANSPARENT_FLAGS:
                    continue
                node = defs.get(code.co_firstlineno)
                if node is None or node.name != code.co_name:
                    continue  # class bodies and other non-function code objects
                # co_qualname is 3.11+; before that it is rebuilt from the source, exactly
                # as the tracer does, so that both sides build the same function keys
                qualname = code_qualname(code)
                key = f"{relfile}::{qualname}"
                index[key] = FuncInfo(
                    func=key, file=relfile, qualname=qualname, line=code.co_firstlineno,
                    def_line=node.lineno, end_line=node.end_lineno,
                    signature=f"{node.name}({ast.unparse(node.args)})",
                    doc=ast.get_docstring(node) or "",
                    source="\n".join(lines[code.co_firstlineno - 1:node.end_lineno]),
                    is_test=is_test_file(relfile),
                )
    return index


def read_source_lines(project, relfile):
    source = read_source(os.path.join(project, relfile))
    return source.splitlines() if source is not None else []


@dataclass
class TestRecord:
    __test__ = False  # not a pytest test class

    nodeid: str
    outcome: str
    lines: set = field(default_factory=set)       # {(relfile, line)}
    functions: set = field(default_factory=set)   # {func key}
    call_time: float = 0.0
    failure: str = ""


@dataclass
class Spectrum:
    tests: dict           # nodeid -> TestRecord, in execution order
    wall_time: float = 0.0

    @property
    def failing(self):
        return [t for t in self.tests.values() if t.outcome == "failed"]

    @property
    def passing(self):
        return [t for t in self.tests.values() if t.outcome == "passed"]

    @classmethod
    def from_json(cls, data):
        tests = {}
        for nodeid, rec in data["tests"].items():
            tests[nodeid] = TestRecord(
                nodeid=nodeid,
                outcome=rec.get("outcome", "passed"),
                lines={(f, n) for f, n in rec.get("lines", [])},
                functions=set(rec.get("functions", [])),
                call_time=rec.get("call_time", 0.0),
                failure=rec.get("failure", ""),
            )
        return cls(tests=tests, wall_time=data.get("wall_time", 0.0))


def collect_spectrum(project, run=invoke):
    """Run the whole suite of project in spectrum mode."""
    return Spectrum.from_json(run(project, "spectrum"))
