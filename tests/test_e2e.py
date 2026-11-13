"""End-to-end: every seeded bug, real subprocess runs, ground-truth oracle."""

import os
import subprocess
import sys

import pytest

from qdebug.evaluate import RunCache, ensure_variants, evaluate_one, load_bugs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUGS_PATH = os.path.join(ROOT, "bugs.json")
VARIANTS = os.path.join(ROOT, "variants")
FIXED = os.path.join(ROOT, "sample_project")
BUGS = load_bugs(BUGS_PATH)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def results():
    ensure_variants(BUGS_PATH, VARIANTS)
    cache = RunCache()
    return {bug["id"]: evaluate_one(bug, "infogain", 0.0, 0, cache, FIXED, VARIANTS) for bug in BUGS}


@pytest.mark.parametrize("bug", BUGS, ids=[b["id"] for b in BUGS])
def test_infogain_finds_the_buggy_function(results, bug):
    row = results[bug["id"]]
    assert row["reported_function"] == f"{bug['file']}::{bug['function']}", row


def test_zoom_puts_the_true_line_in_the_region_for_at_least_4_bugs(results):
    hits = [bug_id for bug_id, row in results.items() if row["line_in_region"]]
    assert len(hits) >= 4, results


def test_cli_debug_runs_end_to_end(tmp_path):
    ensure_variants(BUGS_PATH, VARIANTS)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "qdebug", "debug", "--project", os.path.join(VARIANTS, "bug_01"),
         "--oracle", "truth", "--fixed", FIXED, "--plain", "--save-dir", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr
    assert "quantity_discount_rate" in proc.stdout
    assert "Execution tree:" in proc.stdout
    assert list(tmp_path.glob("session_*.json"))
