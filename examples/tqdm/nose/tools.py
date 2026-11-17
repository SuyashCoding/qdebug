"""Stand-in for nose.tools (qdebug demo, NOT part of tqdm): see nose/__init__.py."""

from pytest import raises as assert_raises  # noqa: F401
