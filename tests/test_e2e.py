"""End-to-end: seeded bugs, real subprocess runs, ground-truth oracle."""

import os
import subprocess
import sys

import pytest

from helpers import PLANNER, ROOT, SHOP
from qdebug.evaluate import RunCache, evaluate_one
from qdebug.suites import ensure_variants

pytestmark = pytest.mark.e2e

SHOP_BUGS = SHOP.bugs()
# one planner bug per kind of difficulty: a crash inside a fixture, a crash far
# from its cause behind deep recursion, a nested function, an accumulator, a
# stale cache and a wrong call in the middle of a long function
PLANNER_IDS = ["p02-missing-return", "p08-missed-cycle", "p16-partial-traversal",
               "p29-accumulator", "p33-stale-cache", "p13-wrong-variable"]
# found as a function, but their line cannot be: a default argument is on the
# def line, which does not run during the call; a lambda runs in its caller
FUNCTION_ONLY_IDS = ["p31-mutable-default", "p34-late-binding"]
PLANNER_BUGS = [bug for bug in PLANNER.bugs() if bug["id"] in PLANNER_IDS + FUNCTION_ONLY_IDS]


def evaluate(suite, bugs, **options):
    ensure_variants(suite)
    cache = RunCache()
    return {bug["id"]: evaluate_one(bug, "infogain", 0.0, 0, cache, suite.project, suite.variants,
                                    **options) for bug in bugs}


@pytest.fixture(scope="module")
def shop_results():
    return evaluate(SHOP, SHOP_BUGS)


@pytest.fixture(scope="module")
def planner_results():
    return evaluate(PLANNER, PLANNER_BUGS, policy="tuned")


@pytest.mark.parametrize("bug", SHOP_BUGS, ids=[b["id"] for b in SHOP_BUGS])
def test_infogain_finds_the_buggy_function(shop_results, bug):
    row = shop_results[bug["id"]]
    assert row["reported_function"] == f"{bug['file']}::{bug['function']}", row


def test_zoom_puts_the_true_line_in_the_region_for_at_least_4_bugs(shop_results):
    hits = [bug_id for bug_id, row in shop_results.items() if row["line_in_region"]]
    assert len(hits) >= 4, shop_results


@pytest.mark.parametrize("bug_id", PLANNER_IDS)
def test_other_kinds_of_bugs_are_found_down_to_the_line(planner_results, bug_id):
    row = planner_results[bug_id]
    assert row["found_function"] == 1, row
    assert row["line_in_region"] == 1, row


@pytest.mark.parametrize("bug_id", FUNCTION_ONLY_IDS)
def test_bugs_outside_any_executed_line_are_found_as_a_function(planner_results, bug_id):
    assert planner_results[bug_id]["found_function"] == 1, planner_results[bug_id]


def test_cli_debug_runs_end_to_end(tmp_path):
    ensure_variants(SHOP)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "qdebug", "debug", "--project", SHOP.variant("bug_01"),
         "--oracle", "truth", "--fixed", SHOP.project, "--plain", "--save-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr
    assert "quantity_discount_rate" in proc.stdout
    assert "Execution tree:" in proc.stdout
    assert list(tmp_path.glob("session_*.json"))
