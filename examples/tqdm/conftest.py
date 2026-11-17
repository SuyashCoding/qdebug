"""Lets tqdm's 2019 tests run on a current Python.

Added by qdebug's demo, NOT part of tqdm: see nose/__init__.py and QDEBUG_DEMO.md.
"""

import sys

import pytest

# tqdm's test setup writes getattr(sys, 'setswitchinterval', getattr(sys, 'setcheckinterval')),
# which looks up setcheckinterval even when it isn't used; Python 3.9 removed it.
if not hasattr(sys, "setcheckinterval"):
    sys.setcheckinterval = lambda interval: None


@pytest.fixture(autouse=True)
def _nose_with_setup(request):
    """Runs nose-style `@with_setup(setup, teardown)` functions around each test."""
    func = getattr(request, "function", None)
    setup = getattr(func, "_nose_setup", None)
    teardown = getattr(func, "_nose_teardown", None)
    if setup is not None:
        setup()
    yield
    if teardown is not None:
        teardown()
