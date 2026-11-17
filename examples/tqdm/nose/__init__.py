"""A stand-in for the three `nose` helpers tqdm's 2019 tests import. NOT part of tqdm.

Added by qdebug's demo (see QDEBUG_DEMO.md). The real `nose` package no longer
works on Python 3.10+, and pytest 8 removed its nose support. Instead of
wrapping each test, `with_setup` only records the setup and teardown functions;
the autouse fixture in conftest.py runs them around the test, as nose did.
"""


def with_setup(setup=None, teardown=None):
    def decorate(func):
        func._nose_setup = setup
        func._nose_teardown = teardown
        return func
    return decorate
