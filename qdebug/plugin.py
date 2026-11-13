"""pytest plugin used inside the subprocess runner.

It wraps only the test call (pytest_runtest_call), so fixtures and pytest
internals are never traced, and records each test's outcome.

The hooks use the old-style ``hookwrapper=True`` form, which every pytest
version since 3 understands; the project's own environment may have an older
pytest than qdebug's.
"""

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


class QDebugPlugin:
    def __init__(self, mode, project_dir, monitored=None, target=None, max_repr=300,
                 spectrum_backend="auto", limits=None, seed_random=True):
        self.mode = mode
        self.project_dir = project_dir
        self.monitored = monitored
        self.target = target
        self.max_repr = max_repr
        self.spectrum_backend = spectrum_backend
        self.limits = limits or TreeLimits()
        self.seed_random = seed_random
        self.results = {}
        self.limits_hit = {}
        self.collection_errors = {}  # module / node id -> error text

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

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        # before any fixture runs, since fixtures may draw random numbers too
        if self.seed_random:
            seed_everything()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        tracer = self._make_tracer()
        start = time.perf_counter()
        if tracer is not None:
            tracer.start()
        try:
            yield
        finally:
            if tracer is not None:
                tracer.stop()
            record = self._record(item.nodeid)
            record["call_time"] = time.perf_counter() - start
            if tracer is not None:
                record.update(tracer.result())
                for kind, count in getattr(tracer, "limits_hit", {}).items():
                    self.limits_hit[kind] = self.limits_hit.get(kind, 0) + count

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
        elif report.skipped and record["outcome"] != "failed":
            record["outcome"] = "skipped"
