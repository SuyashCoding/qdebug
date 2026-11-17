import pytest

from planner.models import Milestone
from planner.parser import (ParseError, parse_deps, parse_duration, parse_line, parse_plan,
                            split_fields, strip_comment)


def test_strip_comment():
    assert strip_comment("build: 2d  # the backend") == "build: 2d"
    assert strip_comment("   # only a comment") == ""
    assert strip_comment("  build: 2d #core  ") == "build: 2d #core"


def test_duration_in_days():
    assert parse_duration("3d") == 3
    assert parse_duration(" 12D ") == 12
    assert parse_duration("4") == 4


def test_duration_in_weeks():
    assert parse_duration("1w") == 5
    assert parse_duration("3w") == 15


def test_bad_duration_is_a_parse_error():
    with pytest.raises(ParseError):
        parse_duration("soon")


def test_deps_are_split_and_trimmed():
    assert parse_deps("build, copy ,design") == ("build", "copy", "design")
    assert parse_deps("") == ()


def test_split_fields():
    assert split_fields("  build : 2d @ben") == ("build", ["2d", "@ben"])
    with pytest.raises(ParseError):
        split_fields("no colon here")


def test_line_with_everything():
    task = parse_line("review: 2d after build, copy @ana !urgent #ux #qa")
    assert task.name == "review"
    assert task.days == 2
    assert task.after == ("build", "copy")
    assert task.owner == "ana"
    assert task.priority == "urgent"
    assert task.tags == ("ux", "qa")


def test_priority_is_case_insensitive():
    assert parse_line("fix: 1d !High").priority == "high"
    with pytest.raises(ParseError):
        parse_line("fix: 1d !whenever")


def test_tag_may_contain_a_colon():
    task = parse_line("sync: 1d #time:utc")
    assert task.name == "sync"
    assert task.tags == ("time:utc",)


def test_milestone_line():
    task = parse_line("launch: milestone after review")
    assert isinstance(task, Milestone)
    assert task.days == 0 and task.after == ("review",)


def test_duration_is_required():
    with pytest.raises(ParseError):
        parse_line("idea: @ana")


def test_plan_from_text(plan):
    assert plan.name == "relaunch"
    assert plan.names() == ["design", "copy", "build", "review", "launch"]
    assert plan.get("build").days == 5
    assert plan.get("review").after == ("build", "copy")
    assert plan.get("copy").tags == ("content",)


def test_errors_carry_the_line_number():
    text = "a: 1d\n# note\nb: soon\n"
    with pytest.raises(ParseError) as caught:
        parse_plan(text)
    assert caught.value.line_no == 3
    assert str(caught.value).startswith("line 3:")


def test_unknown_dependency_is_reported():
    with pytest.raises(ParseError) as caught:
        parse_plan("a: 1d after b\n")
    assert "unknown task 'b'" in str(caught.value)
