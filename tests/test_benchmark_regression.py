"""Benchmark regression check: the 39 seeded bugs must stay found, with no more questions.

Runs every bug of both suites once (infogain, tuned policy, no wrong answers), about 2.5 minutes.
The floors are the results when this check was added (2026-11-23). If a change makes qdebug better,
raise them in the same commit; if it makes it worse, this fails and says which bugs changed.
"""

import pytest

from qdebug.evaluate import run_suite
from qdebug.suites import Suite

# suite: (functions found, lines found, total questions over all bugs)
FLOORS = {"shop": (5, 5, 48), "planner": (34, 29, 244)}
QUESTION_SLACK = 1.05  # 5% more questions is noise from ties, not a regression


@pytest.mark.e2e
@pytest.mark.parametrize("name", sorted(FLOORS))
def test_seeded_bugs_stay_found(name):
    rows = run_suite(Suite(f"benchmarks/{name}"), strategies=("infogain",), noise_levels=(0.0,), seeds=1,
                     out_dir=None, policy="tuned", log=lambda *a: None)
    found = sum(r["found_function"] for r in rows)
    lines = sum(r["line_in_region"] for r in rows)
    questions = sum(r["func_questions"] + r["line_questions"] for r in rows)
    want_found, want_lines, want_questions = FLOORS[name]
    missed = [r["bug"] for r in rows if not r["found_function"]]
    no_line = [r["bug"] for r in rows if not r["line_in_region"]]
    assert found >= want_found, f"{name}: buggy function no longer found for {missed}"
    assert lines >= want_lines, f"{name}: line found for {lines} bugs, was {want_lines}; now missed: {no_line}"
    assert questions <= want_questions * QUESTION_SLACK, (
        f"{name}: {questions} questions in total, was {want_questions}; per bug: "
        + ", ".join(f"{r['bug']}={r['func_questions']}+{r['line_questions']}" for r in rows))
