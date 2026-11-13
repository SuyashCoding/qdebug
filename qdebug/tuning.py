"""Conditional search rules: where to prune, where to cut, where to continue.

A Tuning is a set of switches applied on top of the plain search. "baseline"
turns everything off and reproduces the original behaviour exactly. "tuned"
turns on the rules below.

Cut      fallback           When the search ends without evidence (out of
                            budget, nothing informative left to ask), say so
                            and report the top SBFL function instead of a
                            guess. Stopping this way was right 1 time in 18.
Cut      evidence_stop      "Confident" needs a "no" about the blamed
                            function. Function mass is a sum over calls, so a
                            function that is simply called often can reach the
                            threshold before any question has been asked.
Prune    exclude_tests      Test code is scaffolding, never the reported bug.
Prune    assertion_weight   Calls made before the previous passing assertion
                            are unlikely to explain this failure: scale their
                            prior down (soft, because state can be shared).
Prune    repeat_discount    Every "yes" about a call of f is weak evidence
                            that f is fine: scale down f's other calls, unless
                            some call of f was judged wrong.
"""

import ast
import warnings
from dataclasses import dataclass, replace

LOW_CONFIDENCE_STOPS = {"budget", "no informative question left", "unconfirmed"}
REPEAT_FLOOR = 0.05  # repeated "yes" answers never rule a function out completely


@dataclass(frozen=True)
class Tuning:
    # The search stopped on its budget (30 questions)
    fallback: bool = False

    # One function is over 90% likely, but nobody has answered wrong
    evidence_stop: bool = False

    # A call belongs to a test file
    exclude_tests: bool = False

    # A call was made before the previous passing assertion
    assertion_weight: float = 1.0  # 1.0 = off

    # A function got a right answer and never a wrong answer
    repeat_discount: float = 1.0   # 1.0 = off


POLICIES = {
    "baseline": Tuning(),
    # repeat_discount stays off: on the seeded bugs at 10% noise it lost 4 of 50
    # sessions, because a wrong "yes" then also discounts the buggy function's
    # other calls. It is available as --repeat-discount for experiments.
    "tuned": Tuning(fallback=True, evidence_stop=True, exclude_tests=True,
                    assertion_weight=0.05),
}


def resolve_tuning(policy, assertion_weight=None, repeat_discount=None):
    """The Tuning of a named policy, with optional knob overrides."""
    try:
        tuning = POLICIES[policy]
    except KeyError:
        raise ValueError(f"unknown policy {policy!r}; choose from {sorted(POLICIES)}") from None
    if assertion_weight is not None:
        tuning = replace(tuning, assertion_weight=assertion_weight)
    if repeat_discount is not None:
        tuning = replace(tuning, repeat_discount=repeat_discount)
    return tuning


def _is_assertion_call(expr):
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return name.startswith("assert") or name in ("raises", "fail")


def _is_assertion(stmt):
    if isinstance(stmt, ast.Assert):
        return True
    if isinstance(stmt, ast.Expr):
        return _is_assertion_call(stmt.value)
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return any(_is_assertion_call(item.context_expr) for item in stmt.items)
    return False


LOOPS = (ast.For, ast.AsyncFor, ast.While)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _statements(body, in_loop=False):
    """Yield (statement, in_loop) in source order, entering blocks but not nested scopes."""
    for stmt in body:
        if isinstance(stmt, SCOPES):
            continue
        blocks = [getattr(stmt, name, None) for name in ("body", "orelse", "finalbody")]
        blocks += [h.body for h in getattr(stmt, "handlers", [])]
        blocks = [b for b in blocks if isinstance(b, list) and b]
        if not blocks or _is_assertion(stmt):
            yield stmt, in_loop
        for block in blocks:
            yield from _statements(block, in_loop or isinstance(stmt, LOOPS))


def _find_function(tree, first_line):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            if first_line in (start, node.lineno):
                return node
    return None


def assertion_cut(source_lines, first_line, last_line):
    """The line up to which calls in the test ran before the previous passing assertion.

    first_line: where the test function starts; last_line: the line it was on
    when it failed. Returns None (no pruning) when the failing statement is
    inside a loop, because earlier iterations then share its lines, or when
    no assertion precedes it.
    """
    if not source_lines or first_line is None or last_line is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse("\n".join(source_lines))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    func = _find_function(tree, first_line)
    if func is None:
        return None
    statements = list(_statements(func.body))
    failing = None
    for stmt, in_loop in statements:
        if stmt.lineno <= last_line <= stmt.end_lineno:
            failing = (stmt, in_loop)  # keep the innermost, i.e. the last match
    if failing is None or failing[1]:
        return None
    ends = [stmt.end_lineno for stmt, _ in statements
            if _is_assertion(stmt) and stmt.end_lineno < failing[0].lineno]
    return max(ends) if ends else None
