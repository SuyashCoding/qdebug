"""The agent prompt (agent.md) and the text QDebug sends Claude about a session.

The prompt is split into "## section" blocks. The built-in agent.md defines
every section; a project's own copy (.qdebug/agent.md, or --agent PATH)
replaces the sections it keeps and adds its "project notes".
"""

import os
import re
from dataclasses import dataclass, field
from importlib import resources

from qdebug.tracer import truncate

SECTIONS = ("system", "call", "line", "triage", "explain", "project notes")
PROJECT_AGENT = os.path.join(".qdebug", "agent.md")
VALUE_LIMIT = 1500      # characters of one rendered value
SOURCE_LIMIT = 120      # lines of one function's source
FAILURE_LIMIT = 3000    # characters of pytest's failure text
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.M)


def default_agent_text():
    return resources.files("qdebug.ai").joinpath("agent.md").read_text(encoding="utf-8")


def parse_sections(text):
    """{section name: body} of a markdown text with "## name" headings (lower-cased names)."""
    sections = {}
    matches = list(_HEADING.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1).strip().lower()] = text[match.end():end].strip()
    return sections


@dataclass
class Agent:
    """The prompt sections in use, and where they came from."""

    sections: dict
    source: str = "built-in"
    overridden: list = field(default_factory=list)

    @classmethod
    def load(cls, path=None, project=None):
        """The built-in prompt, with the sections of path (or <project>/.qdebug/agent.md) on top."""
        sections = parse_sections(default_agent_text())
        if path is None and project is not None:
            candidate = os.path.join(project, PROJECT_AGENT)
            path = candidate if os.path.isfile(candidate) else None
        if path is None:
            return cls(sections)
        with open(path, encoding="utf-8") as fh:
            custom = parse_sections(fh.read())
        unknown = sorted(set(custom) - set(SECTIONS))
        if unknown:
            raise ValueError(f"{path}: unknown section(s) {', '.join(unknown)}; "
                             f"the sections are: {', '.join(SECTIONS)}")
        changed = [name for name, body in custom.items() if body and body != sections.get(name)]
        sections.update({name: body for name, body in custom.items() if body})
        return cls(sections, source=path, overridden=changed)

    def system(self, task):
        """The system text for one kind of request: the shared rules, the task, the notes."""
        parts = [self.sections["system"], f"# Task\n\n{self.sections[task]}"]
        notes = self.sections.get("project notes", "").strip()
        if notes:
            parts.append(f"# Project notes\n\n{notes}")
        return "\n\n".join(parts)


def write_project_agent(project, force=False):
    """Copy the built-in prompt to <project>/.qdebug/agent.md. Returns its path."""
    path = os.path.join(project, PROJECT_AGENT)
    if os.path.exists(path) and not force:
        raise FileExistsError(f"{path} already exists (use --force to overwrite it)")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(default_agent_text())
    return path


# --------------------------------------------------------------------------
# session context

def numbered(lines, first, last, marks=(), marker=">>"):
    out = []
    for number in range(max(1, first), min(len(lines), last) + 1):
        mark = marker if number in marks else " " * len(marker)
        out.append(f"{mark} {number:4d} | {lines[number - 1]}")
    return "\n".join(out)


def function_source(session, func_key, marks=(), limit=SOURCE_LIMIT):
    """The source of a function with line numbers (marked lines first in view), or ''."""
    info = session.functions.get(func_key)
    if info is None:
        return ""
    lines = session.file_lines(info.file)
    first, last = info.line, info.end_line
    if last - first + 1 > limit:
        centre = min(marks) if marks else first
        first = max(info.line, centre - limit // 2)
        last = min(info.end_line, first + limit - 1)
    return numbered(lines, first, last, set(marks))


def value(snap):
    return truncate(snap["full"], VALUE_LIMIT)


def failure_text(session):
    text = (session.failure_text or "").strip()
    return text[-FAILURE_LIMIT:]


def test_key(test_id):
    """'tests/t.py::TestX::test_a[1]' -> 'tests/t.py::TestX.test_a' (a function key)."""
    path, _, rest = test_id.split("[", 1)[0].partition("::")
    return f"{path}::{rest.replace('::', '.')}"


test_key.__test__ = False  # a helper, not a pytest test


def test_context(session):
    """The failing test and its error: the same for every request of a session (cached)."""
    func = test_key(session.test_id)
    parts = [f"# The failing test\n\n{session.test_id}"]
    source = function_source(session, func) if func else ""
    if source:
        parts.append(f"Its source:\n\n{source}")
    parts.append(f"How it failed (pytest output):\n\n{failure_text(session)}")
    return "\n\n".join(parts)


def _signature(session, node):
    info = session.functions.get(node.func)
    return info.signature if info else f"{node.qualname}(...)"


def describe_call(session, node, show_source=False):
    """Everything Claude may see about one call question."""
    info = session.functions.get(node.func)
    out = [f"# The call\n\nFunction: {node.qualname}   ({node.file}:{node.line})",
           f"Signature: {_signature(session, node)}"]
    if info is not None and info.doc:
        out.append(f'Docstring:\n"""{info.doc.strip()}"""')
    if show_source and info is not None:
        out.append(f"Source:\n{function_source(session, node.func)}")
    if node.parent is not None:
        parent = session.tree.nodes[node.parent]
        where = f"Called by: {parent.qualname} ({parent.file}:{parent.line})"
        if node.call_line:
            lines = session.file_lines(parent.file)
            if 0 < node.call_line <= len(lines):
                where += f", at line {node.call_line}: {lines[node.call_line - 1].strip()}"
        else:
            where += " (from a test fixture, before the test body ran)"
        out.append(where)
    closure = set(node.closure)
    args = node.args or {}
    out.append("Inputs:" if args else "Inputs: none")
    for name, snap in args.items():
        tag = "  (closure: a variable of the enclosing function)" if name in closure else ""
        out.append(f"  {name} = {value(snap)}{tag}")
    if node.exc:
        out.append(f"It raised: {value(node.exc)}")
    else:
        out.append(f"It returned: {value(node.ret) if node.ret else '?'}")
    if node.mutated:
        out.append("It changed:")
        for name in node.mutated:
            out.append(f"  {name}: {value(args[name])}  ->  {value(node.after[name])}")
    else:
        out.append("It changed none of its inputs.")
    examples = session.passing_examples(node.func, like=node) if hasattr(session, "passing_examples") else []
    if examples:
        out.append("\nCalls of the same function in tests that PASS (usually correct; but a bug can hide "
                   "in a passing test whose assertions do not check this value, so weigh them against the "
                   "docstring and the failing test):")
        for example_args, output, test in examples:
            shown = ", ".join(f"{k}={truncate(v, 200)}" for k, v in example_args.items())
            out.append(f"  ({truncate(shown, 600)}) {output}    [{test.split('::')[-1]}]")
    return "\n".join(out)


def describe_checkpoint(session, question):
    """Everything Claude may see about one line question."""
    node, cp = question.node, question.checkpoint
    marks = [cp["line"]] if cp["kind"] == "line" else []
    out = [f"# Inside {node.qualname}   ({node.file})", f"Signature: {_signature(session, node)}"]
    out.append("The call's inputs:")
    for name, snap in (node.args or {}).items():
        out.append(f"  {name} = {value(snap)}")
    source = function_source(session, node.func, marks)
    if source:
        out.append(f"Source (>> marks the line about to run):\n{source}")
    previous = question.meta.get("previous_line")
    if previous:
        out.append(f"The line that ran just before: {previous}")
    if cp["kind"] == "line":
        out.append(f"The state just BEFORE line {cp['line']} runs (visit #{cp['occurrence']} of that line):")
    else:
        out.append("The state when the call RETURNS:")
    for name, snap in cp["locals"].items():
        out.append(f"  {name} = {value(snap)}")
    for group in cp.get("aliases", []):
        out.append(f"  (these names are the same object: {' is '.join(group)})")
    if cp["kind"] == "return":
        if cp.get("exc"):
            out.append(f"  raising: {value(cp['exc'])}")
        else:
            out.append(f"  returning: {value(cp['ret']) if cp.get('ret') else '?'}")
    return "\n".join(out)


def earlier_answers(session, limit=12):
    """The last call-level answers, so Claude stays consistent with them."""
    rows = []
    for entry in session.log[-limit:]:
        if entry.kind != "answer":
            continue
        args = ", ".join(f"{k}={truncate(v, 60)}" for k, v in entry.summary.get("args", {}).items())
        rows.append(f"  {entry.summary.get('qualname', entry.func)}({truncate(args, 160)}) "
                    f"{truncate(entry.summary.get('output', ''), 80)}  => {entry.verdict}")
    if not rows:
        return ""
    return "Answers given so far in this session:\n" + "\n".join(rows)
