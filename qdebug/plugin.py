"""pytest plugin used inside the subprocess runner.

It traces a test's setup phase (the fixtures) and its call phase, never
pytest's own code, and records each test's outcome.

The hooks use the old-style ``hookwrapper=True`` form, which every pytest
version since 3 understands; the project's own environment may have an older
pytest than qdebug's.
"""

import inspect
import os
import random
import sys
import tempfile
import time

import pytest

from qdebug.tracer import TreeLimits, TreeTracer, ZoomTracer, make_spectrum_tracer

FAILURE_TEXT_LIMIT = 2000


def seed_everything(seed=0):
    """Seed the random generators a test may use, so re-runs repeat themselves.

    This includes the private generator behind tempfile's random names
    (mkdtemp, NamedTemporaryFile), which random.seed does not reach.
    """
    random.seed(seed)
    try:
        sequence = tempfile._RandomNameSequence()
        sequence._rng = random.Random(seed)
        sequence._rng_pid = os.getpid()
        tempfile._name_sequence = sequence
    except Exception:  # noqa: BLE001 - private API; skip if it changes
        pass
    numpy = sys.modules.get("numpy")
    if numpy is not None:
        try:
            numpy.random.seed(seed)
        except Exception:  # noqa: BLE001 - an unusual numpy must not break the run
            pass


def item_code(item):
    """The code object of the function a test item runs, or None.

    Decorators that set __wrapped__ (functools.wraps, mock.patch) are looked
    through, because the innermost function is the one whose frame runs the
    test body.
    """
    func = getattr(item, "function", None) or getattr(item, "obj", None)
    func = getattr(func, "__func__", func)
    try:
        func = inspect.unwrap(func)
    except Exception:  # noqa: BLE001 - a broken __wrapped__ chain
        pass
    return getattr(func, "__code__", None)


class QDebugPlugin:
    def __init__(self, mode, project_dir, monitored=None, target=None, max_repr=300,
                 spectrum_backend="auto", limits=None, seed_random=True, trace_setup=True):
        self.mode = mode
        self.project_dir = project_dir
        self.monitored = monitored
        self.target = target
        self.max_repr = max_repr
        self.spectrum_backend = spectrum_backend
        self.limits = limits or TreeLimits()
        self.seed_random = seed_random
        self.trace_setup = trace_setup
        self.results = {}
        self.limits_hit = {}
        self.collection_errors = {}  # module / node id -> error text
        self._tracer = None          # the tracer of the test that is being set up or run
        self._setup_traced = False

    def _make_tracer(self):
        if self.mode == "spectrum":
            return make_spectrum_tracer(self.project_dir, self.max_repr, self.spectrum_backend)
        if self.mode == "tree":
            return TreeTracer(self.project_dir, self.monitored, self.max_repr, self.limits)
        if self.mode == "zoom":
            return ZoomTracer(self.project_dir, self.target, self.max_repr)
        return None  # "plain": untraced, used to measure the baseline time

    def _record(self, nodeid):
        # pytest < 4 writes class tests as "file::Class::()::test"; use the modern id
        return self.results.setdefault(nodeid.replace("::()", ""), {"outcome": "passed"})

    def _store(self, item, tracer, call_time):
        record = self._record(item.nodeid)
        record["call_time"] = call_time
        if tracer is not None:
            record.update(tracer.result())
            for kind, count in getattr(tracer, "limits_hit", {}).items():
                self.limits_hit[kind] = self.limits_hit.get(kind, 0) + count

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item):
        # seeded before any fixture runs, since fixtures may draw random numbers too
        if self.seed_random:
            seed_everything()
        self._tracer = tracer = self._make_tracer()
        self._setup_traced = False
        if tracer is not None and self.trace_setup:
            # the spectrum has no root to prepare; it simply records the fixtures too
            self._setup_traced = tracer.begin_test(item_code(item)) or self.mode == "spectrum"
        if self._setup_traced:
            tracer.start()
        try:
            outcome = yield
        finally:
            if self._setup_traced:
                tracer.stop()
        if getattr(outcome, "excinfo", None) is not None:
            # a fixture failed (or skipped the test): the call phase will not run
            self._store(item, tracer if self._setup_traced else None, 0.0)
            self._tracer = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        tracer = self._tracer
        if tracer is None and self.mode != "plain":  # setup hook did not run for this item
            tracer = self._make_tracer()
        self._tracer = None
        start = time.perf_counter()
        if tracer is not None:
            tracer.enter_call()
            tracer.start()
        try:
            yield
        finally:
            if tracer is not None:
                tracer.stop()
            self._store(item, tracer, time.perf_counter() - start)

    def pytest_collectreport(self, report):
        if report.failed:
            text = report.longreprtext or ""
            self.collection_errors[report.nodeid or "<session>"] = text[-FAILURE_TEXT_LIMIT:]

    def pytest_runtest_logreport(self, report):
        record = self._record(report.nodeid)
        if report.failed:
            record["outcome"] = "failed"
            text = report.longreprtext or ""
            record.setdefault("failure", text[-FAILURE_TEXT_LIMIT:])
            record.setdefault("failed_in", report.when)
        elif report.skipped and record["outcome"] != "failed":
            record["outcome"] = "skipped"
