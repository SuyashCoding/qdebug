"""Create variants/bug_XX/ copies of sample_project/ with one seeded bug each.

Usage: python make_variants.py [--bugs bugs.json] [--source sample_project] [--dest variants]

Every bug edit must match exactly once and preserve the file's line count, so
that line numbers line up between the buggy and the fixed versions. Each
variant must fail at least 1 test and pass at least 5, and the correct version
must pass everything.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")


def load_bugs(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def apply_bug(project_dir, bug):
    """Apply bug's old->new edit inside project_dir (in place)."""
    target = Path(project_dir) / bug["file"]
    text = target.read_text(encoding="utf-8")
    count = text.count(bug["old"])
    assert count == 1, f"{bug['id']}: 'old' snippet matches {count} times in {bug['file']}"
    edited = text.replace(bug["old"], bug["new"])
    assert len(edited.splitlines()) == len(text.splitlines()), (
        f"{bug['id']}: edit changes the line count of {bug['file']}"
    )
    lines = edited.splitlines()
    for line_no in bug["buggy_lines"]:
        assert bug["new"].strip().splitlines()[0] in lines[line_no - 1], (
            f"{bug['id']}: buggy line {line_no} does not contain the new snippet"
        )
    target.write_text(edited, encoding="utf-8")


def run_suite(project_dir):
    """Run the project's pytest suite; return (passed, failed, failing test ids)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider"],
        cwd=project_dir, env=env, capture_output=True, text=True,
    )
    out = proc.stdout
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", out)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", out)) else 0
    failing = re.findall(r"^FAILED (\S+)", out, flags=re.M)
    return passed, failed, failing


def make_variant(source, dest_root, bug):
    dest = Path(dest_root) / bug["id"]
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=IGNORE)
    apply_bug(dest, bug)
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bugs", default=str(ROOT / "bugs.json"))
    parser.add_argument("--source", default=str(ROOT / "sample_project"))
    parser.add_argument("--dest", default=str(ROOT / "variants"))
    args = parser.parse_args(argv)

    bugs = load_bugs(args.bugs)
    passed, failed, _ = run_suite(args.source)
    assert failed == 0 and passed > 0, f"correct version must pass: {passed} passed, {failed} failed"
    rows = [("correct", "-", passed, failed, "")]
    for bug in bugs:
        dest = make_variant(args.source, args.dest, bug)
        p, f, failing = run_suite(dest)
        assert f >= 1, f"{bug['id']}: expected at least one failing test"
        assert p >= 5, f"{bug['id']}: expected at least 5 passing tests, got {p}"
        names = ", ".join(t.split("::")[-1] for t in failing)
        rows.append((bug["id"], bug["function"], p, f, names))

    header = ("variant", "buggy function", "passed", "failed", "failing tests")
    widths = [max(len(str(r[i])) for r in rows + [header]) for i in range(4)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths) + "  {}"
    print(fmt.format(*header))
    print(fmt.format(*("-" * w for w in widths), "-" * 13))
    for row in rows:
        print(fmt.format(*row))
    print(f"\nCreated {len(bugs)} variants in {args.dest}")


if __name__ == "__main__":
    main()
