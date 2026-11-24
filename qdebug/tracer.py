"""sys.settrace / sys.monitoring based tracing of project code.

Three modes, each used for one pytest test call at a time (see plugin.py):

* SpectrumTracer - executed (file, line) pairs and entered functions
                   (MonitoringSpectrumTracer: the same on sys.monitoring).
* TreeTracer     - one node per project function call (the execution tree),
                   bounded by TreeLimits.
                   Monitored functions also get value snapshots: arguments
                   before and after the call, return value or exception.
* ZoomTracer     - inside one target call (identified by its call path id),
                   a snapshot of the frame's locals at every line event and
                   at return.

Only code under the project directory is traced; the stdlib, site-packages
and qdebug itself are excluded. Generator expressions, lambdas and other
generator frames are "transparent": they do not become tree nodes, and the
lines they execute are attributed to the enclosing call.

A test is traced in two phases (see plugin.py): its setup, where pytest runs
the fixtures, and its call. When the test function is known in advance
(begin_test), it is the root of the tree from the start, and project code
that fixtures call during setup becomes the root's first children. Otherwise
only the call phase is traced and its first project frame is the root.
"""

import hashlib
import inspect
import os
import re
import sys
from dataclasses import dataclass

QDEBUG_DIR = os.path.normcase(os.path.dirname(os.path.abspath(__file__)))
TRANSPARENT_NAMES = {"<genexpr>", "<lambda>", "<listcomp>", "<dictcomp>", "<setcomp>"}
TRANSPARENT_FLAGS = inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR
FULL_REPR_LIMIT = 100_000
_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+")
# thread ids change between runs: an RLock's owner, a Thread's _ident / _native_id
_THREAD_ID = re.compile(r"\b(owner=|'_ident': |'_native_id': )\d+")
_PATH_MASKS = []  # [(compiled pattern, placeholder)], see set_path_masks
UNITTEST_FIXTURES = {"setUp", "asyncSetUp"}  # run inside pytest's call phase, before the test


def set_path_masks(paths):
    """Hide machine-specific directories in snapshots: [(path, placeholder), ...].

    The buggy and the fixed copy of a project live in different directories,
    and pytest's tmp_path differs per run, so any value holding such a path
    (a filename, a config dir) would never compare equal between the two
    runs. Each path is matched as written, repr-escaped and with forward
    slashes (case-insensitively on Windows).
    """
    masks = []
    for path, placeholder in paths:
        if not path:
            continue
        path = os.path.abspath(path).rstrip("\\/")
        variants = {path, path.replace("\\", "\\\\"), path.replace("\\", "/")}
        pattern = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
        masks.append((re.compile(pattern, re.IGNORECASE if os.name == "nt" else 0), placeholder))
    _PATH_MASKS[:] = masks


# --------------------------------------------------------------------------
# value snapshots

STRUCT_DEPTH = 5  # nesting levels rendered from attributes / container elements


class _Full(Exception):
    """The rendering reached its size limit."""


def _plain_repr(value):
    try:
        text = repr(value)
    except Exception as exc:  # noqa: BLE001 - user __repr__ may raise anything
        return f"<unrepresentable {type(value).__name__}: {type(exc).__name__}>"
    if not isinstance(text, str):
        return f"<non-string repr of {type(value).__name__}>"
    return text


def _attributes(value):
    """(name, value) pairs of an object's instance state, or None if it has none."""
    try:
        items = list(vars(value).items())
    except TypeError:
        items = []
    for klass in type(value).__mro__:
        slots = klass.__dict__.get("__slots__", ())
        for name in (slots,) if isinstance(slots, str) else slots:
            if name in ("__dict__", "__weakref__"):
                continue
            try:
                items.append((name, object.__getattribute__(value, name)))
            except AttributeError:
                pass  # slot never assigned
    return items or None


class _Renderer:
    """Builds safe_repr's text piece by piece, stopping at a size limit."""

    def __init__(self, limit):
        self.parts = []
        self.left = limit
        self.active = set()  # ids of containers being rendered (cycle guard)

    def emit(self, text):
        if len(text) >= self.left:
            self.parts.append(text[: self.left])
            self.left = 0
            raise _Full
        self.parts.append(text)
        self.left -= len(text)

    def text_of(self, value, depth):
        """value rendered on its own (within the remaining budget), sharing the cycle guard."""
        sub = _Renderer(self.left)
        sub.active = self.active
        try:
            sub.render(value, depth)
        except _Full:
            pass
        return "".join(sub.parts)

    def seq(self, open_, items, close, render_item):
        self.emit(open_)
        for i, item in enumerate(items):
            if i:
                self.emit(", ")
            render_item(item)
        self.emit(close)

    def render(self, value, depth):
        cls = type(value)
        rep = getattr(cls, "__repr__", None)
        if depth >= STRUCT_DEPTH or rep not in _STRUCTURED:
            if _is_ndarray(value):
                self.emit(_ndarray_repr(value))
            else:
                self.emit(_plain_repr(value))
            return
        if id(value) in self.active:
            self.emit("<...>")
            return
        self.active.add(id(value))
        try:
            nested = lambda v: self.render(v, depth + 1)  # noqa: E731
            if rep is list.__repr__:
                self.seq("[", value, "]", nested)
            elif rep is tuple.__repr__:
                self.seq("(", value, ",)" if len(value) == 1 else ")", nested)
            elif rep is dict.__repr__:
                def pair(kv):
                    nested(kv[0])
                    self.emit(": ")
                    nested(kv[1])
                self.seq("{", list(value.items()), "}", pair)
            elif rep in (set.__repr__, frozenset.__repr__):
                # element order follows hashes, which for objects are addresses
                texts = sorted(self.text_of(v, depth + 1) for v in value)
                name = "set" if rep is set.__repr__ else "frozenset"
                if not texts:
                    self.emit(f"{name}()")
                else:
                    self.seq("{" if name == "set" else "frozenset({", texts,
                             "}" if name == "set" else "})", self.emit)
            else:  # object.__repr__: only an address; show the attributes instead
                attrs = _attributes(value)
                if attrs is None:
                    self.emit(_plain_repr(value))
                    return

                def attr(kv):
                    self.emit(f"{kv[0]}=")
                    nested(kv[1])
                self.seq(f"{cls.__qualname__}(", attrs, ")", attr)
        finally:
            self.active.discard(id(value))


_STRUCTURED = {object.__repr__, list.__repr__, tuple.__repr__, dict.__repr__,
               set.__repr__, frozenset.__repr__}


def _is_ndarray(value):
    # __module__ can be None or missing: pydantic, for one, creates model classes without it
    module = getattr(type(value), "__module__", None)
    return (isinstance(module, str) and module.split(".")[0] == "numpy" and hasattr(value, "tobytes")
            and hasattr(value, "shape") and hasattr(value, "dtype"))


def _ndarray_repr(value):
    """numpy's repr elides the middle of large arrays; add a digest of all the data."""
    text = _plain_repr(value)
    try:
        if value.dtype.kind != "O":  # object arrays hold pointers
            digest = hashlib.sha1(value.tobytes()).hexdigest()[:16]
            text += f" <{value.dtype} {tuple(value.shape)} sha1:{digest}>"
    except Exception:  # noqa: BLE001
        pass
    return text


def safe_repr(value, limit=FULL_REPR_LIMIT):
    """A deterministic, comparable text for value. Never raises.

    Like repr(), except that objects that only have object's default repr
    (a memory address, so any two instances would compare equal) are shown
    through their attributes, the elements of built-in containers are
    rendered the same way, set elements are sorted, numpy arrays get a digest
    of their full data, and memory addresses are masked. Rendering stops
    after limit characters.
    """
    renderer = _Renderer(limit)
    try:
        renderer.render(value, 0)
    except _Full:
        renderer.parts.append("...<truncated>")
    except Exception as exc:  # noqa: BLE001 - this runs inside the trace function: an
        # exception here would escape into the program being debugged and stop the tracing
        renderer.parts.append(f"<unrepresentable {type(value).__name__}: {type(exc).__name__}>")
    text = _ADDRESS.sub(" at 0x?", "".join(renderer.parts))
    text = _THREAD_ID.sub(lambda m: m.group(1) + "?", text)
    for pattern, placeholder in _PATH_MASKS:
        text = pattern.sub(placeholder, text)
    return text


def truncate(text, limit):
    if limit and len(text) > limit:
        return text[: max(limit - 3, 1)] + "..."
    return text


def snapshot(value, max_repr=300):
    """A display repr (truncated) plus a full repr used for comparisons."""
    full = safe_repr(value)
    return {"short": truncate(full, max_repr), "full": full, "type": type(value).__name__}


def state_of(name, value):
    """The observable state of an argument; for `self` that is its __dict__."""
    if name == "self":
        try:
            return dict(vars(value))
        except TypeError:
            return value
    return value


def exception_snapshot(exc_info, max_repr):
    exc_type, exc_value = exc_info[0], exc_info[1]
    text = f"{exc_type.__name__}: {safe_repr(exc_value) if exc_value is not None else ''}"
    return {"short": truncate(text, max_repr), "full": text, "type": exc_type.__name__}


def arg_names(code):
    n = code.co_argcount + code.co_kwonlyargcount
    if code.co_flags & inspect.CO_VARARGS:
        n += 1
    if code.co_flags & inspect.CO_VARKEYWORDS:
        n += 1
    return code.co_varnames[:n]


IMMUTABLE_TYPES = (int, float, complex, str, bytes, bool, type(None), tuple, frozenset, range)


def alias_groups(local_items):
    """Groups of local names bound to the same mutable object (e.g. [['a', 'b']])."""
    by_id = {}
    for name, value in local_items:
        if isinstance(value, IMMUTABLE_TYPES):
            continue
        by_id.setdefault(id(value), []).append(name)
    return sorted(sorted(names) for names in by_id.values() if len(names) > 1)


# --------------------------------------------------------------------------
# code classification

_SOURCE_QUALNAMES = {}  # filename -> {(line, name): qualname}


def source_qualnames(filename):
    """{(line, name): qualname} for the functions and classes defined in a file.

    Pythons before 3.11 have no code.co_qualname, but function keys must
    match the ones the parent builds from co_qualname (e.g. "Account.withdraw",
    "outer.<locals>.inner"). Keys use both the def line and the first
    decorator line, since co_firstlineno is one or the other across versions.
    """
    if filename in _SOURCE_QUALNAMES:
        return _SOURCE_QUALNAMES[filename]
    import ast
    import tokenize

    table = {}
    try:
        with tokenize.open(filename) as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        tree = None

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualname = prefix + child.name
                for line in [child.lineno] + [d.lineno for d in child.decorator_list]:
                    table[(line, child.name)] = qualname
                is_class = isinstance(child, ast.ClassDef)
                visit(child, qualname + ("." if is_class else ".<locals>."))
            else:
                visit(child, prefix)

    if tree is not None:
        visit(tree, "")
    _SOURCE_QUALNAMES[filename] = table
    return table


def code_qualname(code):
    qualname = getattr(code, "co_qualname", None)
    if qualname is not None:
        return qualname
    return source_qualnames(code.co_filename).get((code.co_firstlineno, code.co_name), code.co_name)


class CodeInfo:
    __slots__ = ("relfile", "qualname", "func", "transparent", "firstlineno")

    def __init__(self, relfile, code):
        self.relfile = relfile
        self.qualname = code_qualname(code)
        self.func = f"{relfile}::{self.qualname}"
        self.transparent = (code.co_name in TRANSPARENT_NAMES
                            or bool(code.co_flags & TRANSPARENT_FLAGS))
        self.firstlineno = code.co_firstlineno


class BaseTracer:
    """Shared project filtering. Subclasses implement _on_call/_local."""

    def __init__(self, project_dir, max_repr=300):
        self.project_dir = os.path.normcase(os.path.realpath(project_dir))
        self.max_repr = max_repr
        self._file_cache = {}
        self._code_cache = {}
        self._fixture_frame = None  # a unittest setUp currently running
        self.phase = "call"         # "setup" while pytest runs the test's fixtures
        self.root_code = None       # code object of the test function, when known in advance

    def begin_test(self, code):
        """Called before the setup phase with the test function's code object (or None).

        Returns True if setup will be traced, i.e. the test function is
        project code and can be the root before it runs.
        """
        self.phase = "setup"
        info = self.code_info(code) if code is not None else None
        if info is None or info.transparent:
            return False
        self.root_code = code
        self._open_root(info)
        return True

    def enter_call(self):
        """Called when the setup phase is over and the test itself is about to run."""
        self.phase = "call"

    def _open_root(self, info):
        """Subclasses that build call paths create their root here."""

    def _in_fixture(self, frame, at_top):
        """True while a unittest setUp runs: it must not become the root of the tree."""
        if self._fixture_frame is not None:
            return True
        if at_top and frame.f_code.co_name in UNITTEST_FIXTURES:
            self._fixture_frame = frame
            return True
        return False

    def _fixture_local(self, frame, event, arg):
        if event == "return" and frame is self._fixture_frame:
            self._fixture_frame = None
        return self._fixture_local

    def relfile(self, filename):
        """Project-relative path of filename, or None if it is not project code."""
        try:
            return self._file_cache[filename]
        except KeyError:
            pass
        rel = None
        if filename and not filename.startswith("<"):
            path = os.path.normcase(os.path.realpath(filename))
            inside = path.startswith(self.project_dir + os.sep)
            excluded = (path.startswith(QDEBUG_DIR + os.sep)
                        or "site-packages" in path or "dist-packages" in path)
            if inside and not excluded:
                rel = os.path.relpath(path, self.project_dir).replace(os.sep, "/")
        self._file_cache[filename] = rel
        return rel

    def code_info(self, code):
        try:
            return self._code_cache[code]
        except KeyError:
            pass
        rel = self.relfile(code.co_filename)
        info = CodeInfo(rel, code) if rel is not None else None
        self._code_cache[code] = info
        return info

    def start(self):
        self._previous = sys.gettrace()  # e.g. a coverage tool's tracer; restored on stop
        sys.settrace(self._global)

    def stop(self):
        sys.settrace(getattr(self, "_previous", None))

    def _global(self, frame, event, arg):  # pragma: no cover - overridden
        raise NotImplementedError


# --------------------------------------------------------------------------
# spectrum mode

class SpectrumTracer(BaseTracer):
    """Collects the executed lines and entered functions of one test."""

    def __init__(self, project_dir, max_repr=300):
        super().__init__(project_dir, max_repr)
        self.lines = set()
        self.functions = set()

    def _global(self, frame, event, arg):
        info = self.code_info(frame.f_code)
        if info is None:
            return None
        if not info.transparent:
            self.functions.add(info.func)
        relfile = info.relfile
        lines = self.lines

        def local(frame, event, arg):
            if event == "line":
                lines.add((relfile, frame.f_lineno))
            return local

        return local

    def result(self):
        return {"lines": sorted([f, n] for f, n in self.lines),
                "functions": sorted(self.functions)}


class MonitoringSpectrumTracer(SpectrumTracer):
    """SpectrumTracer on sys.monitoring (PEP 669, Python 3.12+).

    Each line and each function start is reported once per test and then
    disabled at that location, so the test runs at nearly full speed after
    its first pass over the code (the approach coverage.py uses). The result
    is the same set of lines and functions as the settrace version.
    """

    TOOL_PREFERENCE = (2, 3, 4, 1, 5, 0)  # profiler id first; leave debugger/coverage ids free

    def start(self):
        mon = sys.monitoring
        self.tool = next((t for t in self.TOOL_PREFERENCE if mon.get_tool(t) is None), None)
        if self.tool is None:  # every tool id taken: fall back to settrace
            return super().start()
        mon.use_tool_id(self.tool, "qdebug")
        mon.register_callback(self.tool, mon.events.LINE, self._on_line)
        mon.register_callback(self.tool, mon.events.PY_START, self._on_start)
        mon.restart_events()  # re-enable locations disabled during the previous test
        mon.set_events(self.tool, mon.events.LINE | mon.events.PY_START)

    def stop(self):
        if getattr(self, "tool", None) is None:
            return super().stop()
        mon = sys.monitoring
        mon.set_events(self.tool, 0)
        mon.register_callback(self.tool, mon.events.LINE, None)
        mon.register_callback(self.tool, mon.events.PY_START, None)
        mon.free_tool_id(self.tool)
        self.tool = None

    def _on_line(self, code, line):
        info = self.code_info(code)
        if info is not None:
            self.lines.add((info.relfile, line))
        return sys.monitoring.DISABLE

    def _on_start(self, code, offset):
        info = self.code_info(code)
        if info is not None and not info.transparent:
            self.functions.add(info.func)
        return sys.monitoring.DISABLE


def make_spectrum_tracer(project_dir, max_repr=300, backend="auto"):
    """backend: "monitoring" (3.12+), "settrace", or "auto" (monitoring when available)."""
    available = hasattr(sys, "monitoring")
    if backend == "monitoring" and not available:
        raise RuntimeError("sys.monitoring needs Python 3.12+")
    if backend == "monitoring" or (backend == "auto" and available):
        return MonitoringSpectrumTracer(project_dir, max_repr)
    return SpectrumTracer(project_dir, max_repr)


# --------------------------------------------------------------------------
# tree mode

class _Active:
    """Book-keeping for a call that is currently on the stack."""

    __slots__ = ("frame", "node", "child_counts", "orig", "pre", "pending_exc", "free")

    def __init__(self, frame, node):
        self.frame = frame
        self.node = node
        self.child_counts = {}
        self.orig = None
        self.pre = None
        self.pending_exc = None
        self.free = ()


@dataclass(frozen=True)
class TreeLimits:
    """Bounds on the recorded execution tree of a real-sized test.

    A call beyond a limit is *folded*: it is not a node, and its lines and
    callees count as the nearest recorded ancestor's own code (exactly like
    transparent frames). Folding is deterministic, and a recorded node's path
    id is the same as without folding, because only later siblings or deeper
    calls are folded. Zoom mode therefore still finds every recorded call.
    """

    max_nodes: int = 20_000   # total nodes; later calls are folded
    max_repeat: int = 50      # calls of one qualname under one parent (loops)
    max_depth: int = 60       # call depth (deep recursion)


class TreeTracer(BaseTracer):
    """Records the execution tree of one test call.

    monitored: set of function keys ("file::qualname") whose values are
    recorded, or None to monitor every function.
    """

    def __init__(self, project_dir, monitored=None, max_repr=300, limits=None):
        super().__init__(project_dir, max_repr)
        self.monitored = monitored
        self.limits = limits or TreeLimits()
        self.nodes = []
        self.stack = []
        self.folded = []       # frames of folded calls currently running (innermost last)
        self.fold_reason = None  # the limit that folded the outermost of them
        self.limits_hit = {}   # limit name -> number of calls folded by it (callees included)
        self.finished = False

    def _fold_reason(self, info):
        lim = self.limits
        if len(self.nodes) >= lim.max_nodes:
            return "max_nodes"
        if len(self.stack) >= lim.max_depth:
            return "max_depth"
        if self.stack[-1].child_counts.get(info.qualname, 0) >= lim.max_repeat:
            return "max_repeat"
        return None

    def _fold(self, frame, reason):
        if not self.folded:
            self.fold_reason = reason
        self.limits_hit[self.fold_reason] = self.limits_hit.get(self.fold_reason, 0) + 1
        self.folded.append(frame)
        return self._folded_local

    def _folded_local(self, frame, event, arg):
        if event == "line" and self.stack:
            info = self.code_info(frame.f_code)
            self.stack[-1].node["own_lines"].add((info.relfile, frame.f_lineno))
        elif event == "return" and self.folded and self.folded[-1] is frame:
            self.folded.pop()
        return self._folded_local

    def _is_monitored(self, info, is_root):
        if is_root:
            return False  # the test itself is known to fail; never asked about
        return self.monitored is None or info.func in self.monitored

    def _child_path(self, qualname):
        if not self.stack:
            return qualname
        top = self.stack[-1]
        k = top.child_counts.get(qualname, 0)
        top.child_counts[qualname] = k + 1
        return f"{top.node['path']}/{qualname}#{k}"

    def _new_node(self, info, frame):
        parent = self.stack[-1] if self.stack else None
        node = {
            "id": len(self.nodes),
            "path": self._child_path(info.qualname),
            "qualname": info.qualname,
            "func": info.func,
            "file": info.relfile,
            "line": info.firstlineno,
            "parent": parent.node["id"] if parent else None,
            # None for calls made by fixtures: no line of the test makes them
            "call_line": parent.frame.f_lineno if parent and parent.frame is not None else None,
            "children": [],
            "monitored": self._is_monitored(info, parent is None),
            "own_lines": set(),
        }
        if parent:
            parent.node["children"].append(node["id"])
        self.nodes.append(node)
        return _Active(frame, node)

    def _open_root(self, info):
        self.stack.append(self._new_node(info, None))

    def _root_unbound(self):
        """The root exists but the test function has not been entered yet."""
        return len(self.stack) == 1 and self.stack[0].frame is None

    def _global(self, frame, event, arg):
        if self.finished:
            return None
        info = self.code_info(frame.f_code)
        if info is None:
            return None
        if self.root_code is None:
            if self.phase == "setup":
                return None  # the test function is unknown: only its call phase is traced
            if self._in_fixture(frame, not self.stack):
                return self._fixture_local if frame is self._fixture_frame else None
        elif self._root_unbound() and self.phase == "call" and frame.f_code is self.root_code:
            self.stack[0].frame = frame  # the test function itself: the root starts running
            return self._local
        if info.transparent:
            return self._transparent if self.stack else None
        if self.folded:
            return self._fold(frame, None)  # inside a folded call: fold its callees too
        if self.stack:
            reason = self._fold_reason(info)
            if reason is not None:
                return self._fold(frame, reason)
        active = self._new_node(info, frame)
        node = active.node
        if node["monitored"]:
            # A nested function also reads and changes the variables of the
            # function around it: they are inputs and outputs like arguments.
            active.free = tuple(n for n in frame.f_code.co_freevars if n != "__class__")
            names = arg_names(frame.f_code) + active.free
            f_locals = frame.f_locals
            active.orig = {n: f_locals[n] for n in names if n in f_locals}
            if active.free:
                node["closure"] = [n for n in active.free if n in active.orig]
            # rendered now, before the call can mutate them (no deepcopy: real
            # objects such as connections or sessions often cannot be copied)
            active.pre = {n: snapshot(state_of(n, v), self.max_repr) for n, v in active.orig.items()}
        self.stack.append(active)
        return self._local

    def _transparent(self, frame, event, arg):
        if event == "line" and self.stack:
            info = self.code_info(frame.f_code)
            self.stack[-1].node["own_lines"].add((info.relfile, frame.f_lineno))
        return self._transparent

    def _local(self, frame, event, arg):
        if not self.stack or self.stack[-1].frame is not frame:
            return self._local
        active = self.stack[-1]
        if event == "line":
            active.pending_exc = None
            active.node["own_lines"].add((active.node["file"], frame.f_lineno))
        elif event == "exception":
            active.pending_exc = arg
        elif event == "return":
            if len(self.stack) == 1:
                active.node["last_line"] = frame.f_lineno
            self._finish(active, arg)
            self.stack.pop()
            if not self.stack:
                self.finished = True
        return self._local

    def _finish(self, active, retval):
        node = active.node
        node["own_lines"] = sorted([f, n] for f, n in node["own_lines"])
        if active.pending_exc is not None:
            # kept for every call: the calls an exception travelled through
            node["raised"] = active.pending_exc[0].__name__
        if not node["monitored"]:
            return
        mr = self.max_repr
        node["args"] = active.pre
        after = {}
        f_locals = active.frame.f_locals if active.free else {}
        for name, value in active.orig.items():
            if name in active.free:  # may have been rebound (nonlocal), not only mutated
                value = f_locals.get(name, value)
            snap = snapshot(state_of(name, value), mr)
            if snap["full"] != node["args"][name]["full"]:
                after[name] = snap
        node["after"] = after
        node["mutated"] = sorted(after)
        if active.pending_exc is not None:
            node["exc"] = exception_snapshot(active.pending_exc, mr)
            node["ret"] = None
        else:
            node["exc"] = None
            node["ret"] = snapshot(retval, mr)

    def result(self):
        # Calls still open (e.g. tracing stopped by a crash) keep their state.
        for active in self.stack:
            active.node["incomplete"] = True
        for node in self.nodes:
            # also a call whose return was never seen, if tracing stopped while it ran
            if isinstance(node["own_lines"], set):
                node["own_lines"] = sorted([f, n] for f, n in node["own_lines"])
                node["incomplete"] = True
        return {"nodes": self.nodes}


# --------------------------------------------------------------------------
# zoom mode

class ZoomTracer(BaseTracer):
    """Snapshots the locals of one target call at every line and at return."""

    def __init__(self, project_dir, target_path, max_repr=300):
        super().__init__(project_dir, max_repr)
        self.target_path = target_path
        self.stack = []  # list of [frame, path, child_counts]
        self.target_frame = None
        self.checkpoints = []
        self.callees = []  # paths of the target's direct callees; checkpoints index into it
        self.occurrences = {}
        self.pending_exc = None
        self.found = False
        self.finished = False

    def _open_root(self, info):
        self.stack.append([None, info.qualname, {}])

    def _global(self, frame, event, arg):
        if self.finished:
            return None
        info = self.code_info(frame.f_code)
        if info is None:
            return None
        if self.root_code is None:
            if self.phase == "setup":
                return None
            if self._in_fixture(frame, not self.stack):
                return self._fixture_local if frame is self._fixture_frame else None
        elif (len(self.stack) == 1 and self.stack[0][0] is None and self.phase == "call"
              and frame.f_code is self.root_code):
            self.stack[0][0] = frame
            return self._local
        if info.transparent:
            return None
        if self.stack:
            counts = self.stack[-1][2]
            k = counts.get(info.qualname, 0)
            counts[info.qualname] = k + 1
            path = f"{self.stack[-1][1]}/{info.qualname}#{k}"
            if self.target_frame is not None and self.stack[-1][0] is self.target_frame:
                self.callees.append(path)  # a direct callee of the target, in call order
        else:
            path = info.qualname
        self.stack.append([frame, path, {}])
        if path == self.target_path and not self.found:
            self.found = True
            self.target_frame = frame
        return self._local

    def _locals(self, frame):
        items = list(frame.f_locals.items())
        snaps = {name: snapshot(state_of(name, value), self.max_repr) for name, value in items}
        return snaps, alias_groups(items)

    def _local(self, frame, event, arg):
        if not self.stack or self.stack[-1][0] is not frame:
            return self._local
        if frame is self.target_frame:
            if event == "line":
                self.pending_exc = None
                line = frame.f_lineno
                occ = self.occurrences.get(line, 0) + 1
                self.occurrences[line] = occ
                snaps, aliases = self._locals(frame)
                self.checkpoints.append({"index": len(self.checkpoints), "kind": "line",
                                         "line": line, "occurrence": occ,
                                         "locals": snaps, "aliases": aliases,
                                         "calls": len(self.callees)})
            elif event == "exception":
                self.pending_exc = arg
            elif event == "return":
                snaps, aliases = self._locals(frame)
                cp = {"index": len(self.checkpoints), "kind": "return", "line": None,
                      "occurrence": 1, "locals": snaps, "aliases": aliases,
                      "calls": len(self.callees)}
                if self.pending_exc is not None:
                    cp["exc"] = exception_snapshot(self.pending_exc, self.max_repr)
                    cp["ret"] = None
                else:
                    cp["exc"] = None
                    cp["ret"] = snapshot(arg, self.max_repr)
                self.checkpoints.append(cp)
                self.target_frame = None
        if event == "return":
            self.stack.pop()
            if not self.stack:
                self.finished = True
        return self._local

    def result(self):
        return {"target": self.target_path, "found": self.found, "checkpoints": self.checkpoints,
                "callees": self.callees}
