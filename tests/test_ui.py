"""The friendly interface, end to end on a seeded bug."""

import builtins
import io
import os

import pytest
from rich.console import Console

from qdebug import cli
from qdebug.spectrum import TestRecord
from qdebug.ui import UI, failure_summary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUG = os.path.join(ROOT, "variants", "bug_01")
FIXED = os.path.join(ROOT, "sample_project")


def recording_ui(*_args, **_kwargs):
    return UI(console=Console(file=io.StringIO(), width=100, highlight=False))


@pytest.fixture
def ui(monkeypatch):
    made = recording_ui()
    monkeypatch.setattr(cli, "make_ui", lambda args: None if args.plain else made)
    return made


def text_of(ui):
    return ui.console.file.getvalue()


@pytest.mark.e2e
def test_automatic_session_explains_itself(ui):
    code = cli.main(["debug", "--project", BUG, "--oracle", "truth", "--fixed", FIXED,
                     "--policy", "tuned", "--save-dir", ""])
    out = text_of(ui)
    assert code == 0
    assert "Step 1 of 3" in out and "Step 2 of 3" in out and "Step 3 of 3" in out
    assert "Found it" in out and "Confidence: High" in out
    for jargon in ("posterior", "ochiai", "Ochiai", "tier"):
        assert jargon not in out


@pytest.mark.e2e
def test_plain_flag_keeps_the_technical_report(capsys, ui):
    code = cli.main(["debug", "--project", BUG, "--oracle", "truth", "--fixed", FIXED,
                     "--plain", "--save-dir", ""])
    assert code == 0
    assert "qdebug report" in capsys.readouterr().out
    assert text_of(ui) == ""


def test_failure_summary_keeps_only_the_error_lines():
    text = "def test():\n>   assert f() == 1\nE   assert 2 == 1\nE    +  where 2 = f()\ntest.py:2: AssertionError"
    assert failure_summary(text) == ["assert 2 == 1", "+  where 2 = f()"]


def test_choose_test_retries_until_a_valid_number(monkeypatch):
    ui = recording_ui()
    answers = iter(["9", "x", "2"])
    monkeypatch.setattr(builtins, "input", lambda *a: next(answers))
    failing = [TestRecord("t.py::a", "failed"), TestRecord("t.py::b", "failed")]
    assert ui.choose_test(failing) == "t.py::b"


def test_choose_test_skips_the_menu_for_one_failure():
    ui = recording_ui()
    assert ui.choose_test([TestRecord("t.py::a", "failed")]) == "t.py::a"
    assert text_of(ui) == ""
