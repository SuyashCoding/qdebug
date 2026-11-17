"""Grouping failing tests by the bug that probably causes them."""

import builtins
import io

import pytest
from rich.console import Console

from qdebug.groups import explained_by, format_groups, group_failing, group_of, raised_at
from qdebug.ranking import Ranking
from qdebug.spectrum import FuncInfo, Spectrum, TestRecord, is_test_file
from qdebug.ui import UI


def _func(name, line, end, file="m.py"):
    return FuncInfo(func=f"{file}::{name}", file=file, qualname=name, line=line, def_line=line,
                    end_line=end, signature=f"{name}()", doc="", source="", is_test=is_test_file(file))


FUNCS = {f.func: f for f in [_func("common", 1, 3), _func("price", 5, 9), _func("zone", 11, 15),
                             _func("test_x", 1, 50, file="tests/test_m.py")]}
COMMON = {("m.py", 2)}                     # run by every test
PRICE_BUG = {("m.py", 6), ("m.py", 7)}     # line 7 is the price bug: only failing tests reach it
ZONE_BUG = {("m.py", 12), ("m.py", 13)}    # line 13 is the zone bug
PRICE_OK = {("m.py", 6), ("m.py", 8)}
ZONE_OK = {("m.py", 12), ("m.py", 14)}


def _record(nodeid, outcome, lines, failure=""):
    funcs = {f.func for f in FUNCS.values() if any(f.file == fl and f.line <= n <= f.end_line
                                                   for fl, n in lines)}
    return TestRecord(nodeid, outcome, set(lines) | {("tests/test_m.py", 20)}, funcs, failure=failure)


def _two_bug_spectrum():
    tests = [
        _record("t::price_a", "failed", COMMON | PRICE_BUG),
        _record("t::price_b", "failed", COMMON | PRICE_BUG | ZONE_OK),
        _record("t::zone_a", "failed", COMMON | ZONE_BUG),
        _record("t::zone_b", "failed", COMMON | ZONE_BUG | PRICE_OK),
        _record("t::ok_1", "passed", COMMON | PRICE_OK),
        _record("t::ok_2", "passed", COMMON | ZONE_OK),
        _record("t::ok_3", "passed", COMMON | PRICE_OK | ZONE_OK),
    ]
    return Spectrum({t.nodeid: t for t in tests})


def ids(group):
    return {t.nodeid for t in group.tests}


def test_two_bugs_make_two_groups():
    groups = group_failing(_two_bug_spectrum(), FUNCS)
    assert [ids(g) for g in groups] == [{"t::price_a", "t::price_b"}, {"t::zone_a", "t::zone_b"}]
    assert groups[0].best_line == ("m.py", 7) and groups[0].best_line_passing == 0
    assert groups[0].reason == "shared code"
    assert groups[0].representative.nodeid == "t::price_a"  # runs the fewest project functions
    assert group_of(groups, "t::zone_b") is groups[1]


def test_one_bug_makes_one_group():
    spectrum = _two_bug_spectrum()
    for nodeid in ("t::zone_a", "t::zone_b"):
        del spectrum.tests[nodeid]
    groups = group_failing(spectrum, FUNCS)
    assert len(groups) == 1 and len(groups[0]) == 2


def test_a_shared_line_that_passing_tests_also_run_does_not_merge():
    # both failing tests share only COMMON and line 6/12 entries that every passing test runs
    groups = group_failing(_two_bug_spectrum(), FUNCS)
    assert all(not (ids(g) & {"t::price_a"} and ids(g) & {"t::zone_a"}) for g in groups)


def test_same_crash_goes_together_even_without_shared_rare_code():
    crash = "def f():\n>   x * None\nE   TypeError: bad\n\nm.py:3: TypeError"
    tests = [
        _record("t::one", "failed", COMMON | PRICE_OK, failure=crash),
        _record("t::two", "failed", COMMON | ZONE_OK, failure=crash),
        _record("t::ok", "passed", COMMON | PRICE_OK | ZONE_OK),
    ]
    groups = group_failing(Spectrum({t.nodeid: t for t in tests}), FUNCS)
    assert len(groups) == 1
    assert groups[0].crash == ("TypeError", "m.py", 3)
    assert groups[0].describe() == "TypeError at m.py:3"


def test_a_test_that_runs_no_project_code_stands_alone_and_last():
    spectrum = _two_bug_spectrum()
    spectrum.tests["t::broken"] = TestRecord("t::broken", "failed", {("tests/test_m.py", 30)}, set())
    groups = group_failing(spectrum, FUNCS)
    assert ids(groups[-1]) == {"t::broken"} and groups[-1].reason == "no project code"


def test_raised_at_only_counts_project_code():
    files = {"pkg/mod.py"}
    assert raised_at("a\npkg/mod.py:12: ValueError\n", files) == ("ValueError", "pkg/mod.py", 12)
    assert raised_at("pkg\\mod.py:12: ValueError", files) == ("ValueError", "pkg/mod.py", 12)
    assert raised_at("tests/test_mod.py:4: AssertionError", files) is None   # an assertion in a test
    assert raised_at("/usr/lib/python3/json/x.py:9: KeyError", files) is None  # a library
    assert raised_at("", files) is None


def test_ranking_a_group_alone_puts_its_bug_first():
    spectrum = _two_bug_spectrum()
    groups = group_failing(spectrum, FUNCS)
    whole = Ranking(spectrum, FUNCS)
    price = Ranking(spectrum, FUNCS, failing=groups[0].tests)
    assert whole.line_scores[("m.py", 7)] < 1.0      # diluted by the zone failures
    assert price.line_scores[("m.py", 7)] == pytest.approx(1.0)
    assert price.ranked_lines[0] == ("m.py", 7)
    assert price.total_failed == 2


def test_explained_by_lists_other_tests_that_ran_the_line():
    spectrum = _two_bug_spectrum()
    assert explained_by(spectrum, "t::price_a", "m.py", lines=[7]) == ["t::price_b"]
    assert explained_by(spectrum, "t::price_a", "m.py", func="m.py::zone") == ["t::price_b", "t::zone_a",
                                                                              "t::zone_b"]


def test_format_groups_lists_every_failing_test():
    text = format_groups(group_failing(_two_bug_spectrum(), FUNCS))
    assert "4 failing, 2 groups" in text
    assert text.count("FAILED") == 4


def test_menu_shows_the_groups(monkeypatch):
    ui = UI(console=Console(file=io.StringIO(), width=120, highlight=False))
    groups = group_failing(_two_bug_spectrum(), FUNCS)
    monkeypatch.setattr(builtins, "input", lambda *a: "3")
    chosen = ui.choose_test([(g, list(g.tests)) for g in groups])
    out = ui.console.file.getvalue()
    assert chosen == "t::zone_a"  # numbering runs on across the groups
    assert "2 different bugs" in out
    assert "Probable bug 1 (2 tests)" in out and "Probable bug 2 (2 tests)" in out


@pytest.mark.e2e
def test_session_on_two_bugs_ranks_its_group_and_reports_the_rest(tmp_path, monkeypatch):
    import shutil

    from helpers import SHOP
    from qdebug import cli
    from qdebug.suites import IGNORE, apply_bug

    project = tmp_path / "shop"
    shutil.copytree(SHOP.project, project, ignore=IGNORE)
    bugs = {b["id"]: b for b in SHOP.bugs()}
    apply_bug(str(project), bugs["bug_01"])  # quantity discount: 2 failing tests
    apply_bug(str(project), bugs["bug_03"])  # EU zone: 4 failing tests
    ui = UI(console=Console(file=io.StringIO(), width=120, highlight=False))
    monkeypatch.setattr(cli, "make_ui", lambda args: ui)
    code = cli.main(["debug", "--project", str(project), "--test", "test_line_total_bulk",
                     "--oracle", "truth", "--fixed", SHOP.project, "--save-dir", ""])
    out = ui.console.file.getvalue()
    assert code == 0
    assert "shop/pricing.py, line 24" in out
    assert "1 other failing test has the same bug and 4 have a different one" in out
    assert "probably also explains 1 other failing test" in out
    assert "test_bulk_invoice_qty_ten" in out
    assert "4 failing tests probably have a different bug" in out
