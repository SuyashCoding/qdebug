import math

import pytest

from qdebug.ranking import Ranking, ochiai
from qdebug.spectrum import FuncInfo, Spectrum, TestRecord, is_test_file


def test_ochiai_formula():
    assert ochiai(2, 0, 2) == 1.0
    assert ochiai(0, 5, 2) == 0.0
    assert ochiai(1, 3, 2) == pytest.approx(1 / math.sqrt(2 * 4))
    assert ochiai(1, 1, 0) == 0.0


def _func(name, line, end, file="m.py"):
    return FuncInfo(func=f"{file}::{name}", file=file, qualname=name, line=line, def_line=line,
                    end_line=end, signature=f"{name}()", doc="", source="", is_test=is_test_file(file))


def _spectrum():
    # f (lines 1-3) runs in every test; g (lines 5-7) only in the failing ones;
    # line 7 of g only runs in the first failing test.
    tests = {
        "t_fail1": TestRecord("t_fail1", "failed", {("m.py", 2), ("m.py", 6), ("m.py", 7)}, {"m.py::f", "m.py::g"}),
        "t_fail2": TestRecord("t_fail2", "failed", {("m.py", 2), ("m.py", 6)}, {"m.py::f", "m.py::g"}),
        "t_pass1": TestRecord("t_pass1", "passed", {("m.py", 2)}, {"m.py::f"}),
        "t_pass2": TestRecord("t_pass2", "passed", {("m.py", 2), ("m.py", 10)}, {"m.py::f", "m.py::h"}),
    }
    funcs = {f.func: f for f in [_func("f", 1, 3), _func("g", 5, 7), _func("h", 9, 11),
                                 _func("test_x", 1, 2, file="tests/test_m.py")]}
    return Spectrum(tests), funcs


def test_function_and_line_scores():
    spectrum, funcs = _spectrum()
    r = Ranking(spectrum, funcs)
    assert r.func_scores["m.py::g"] == pytest.approx(1.0)
    assert r.func_scores["m.py::f"] == pytest.approx(2 / math.sqrt(2 * 4))
    assert r.func_scores["m.py::h"] == 0.0
    assert r.line_scores[("m.py", 7)] == pytest.approx(1 / math.sqrt(2 * 1))
    assert r.ranked_functions[0] == "m.py::g"
    assert "tests/test_m.py::test_x" not in r.functions  # test code is never ranked
    assert r.function_rank("m.py::g") == 1
    assert r.line_rank("m.py", 6) == 1


def test_tie_break_by_max_line_score():
    tests = {
        "t1": TestRecord("t1", "failed", {("m.py", 2), ("m.py", 6)}, {"m.py::f", "m.py::g"}),
        "t2": TestRecord("t2", "passed", {("m.py", 3), ("m.py", 6)}, {"m.py::f", "m.py::g"}),
    }
    funcs = {f.func: f for f in [_func("f", 1, 3), _func("g", 5, 7)]}
    r = Ranking(Spectrum(tests), funcs)
    assert r.func_scores["m.py::f"] == r.func_scores["m.py::g"]
    assert r.ranked_functions == ["m.py::f", "m.py::g"]  # f has line 2 with score 1.0


def test_tiers_use_ceil_and_at_least_one():
    spectrum, funcs = _spectrum()
    r = Ranking(spectrum, funcs)  # 3 project functions
    assert r.tier_size(5) == 1
    assert r.tier_size(50) == 2
    assert r.tier_size(100) == 3
    assert r.tier_set(5) == {"m.py::g"}
