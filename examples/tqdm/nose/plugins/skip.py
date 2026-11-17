"""Stand-in for nose.plugins.skip (qdebug demo, NOT part of tqdm): see nose/__init__.py."""

from unittest import SkipTest  # noqa: F401  (pytest treats it as a skip)
