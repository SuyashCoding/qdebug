"""A plain-language terminal interface for people who have never seen qdebug.

Used only by the command line in the main process: the traced pytest runs may
live on an old interpreter without rich, so runner, plugin and tracer must
never import this module.
"""

import re
import time

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from qdebug.oracles import HumanOracle, Oracle, ai_hint
from qdebug.tracer import truncate
from qdebug.tuning import LOW_CONFIDENCE_STOPS

ACCENT = "cyan"
STEPS = {
    1: ("Run the tests", "Which tests pass and which fail tells QDebug where to look first."),
    2: ("Find the broken function",
        "QDebug shows you one call and asks if its result is right. You don't need to read "
        "the code. It picks the question whose answer rules out the most."),
    3: ("Find the exact line",
        "QDebug replays that call and shows you the variables part-way through. "
        "Each answer cuts the remaining code roughly in half."),
}
TOTAL_STEPS = len(STEPS)
ANSWER_WORDS = {"yes": "right", "no": "wrong", "unknown": "not sure",
                "inadmissible": "inputs already wrong"}
ANSWER_STYLES = {"yes": "green", "no": "red", "unknown": "yellow", "inadmissible": "yellow"}
CONFIDENCE_STYLES = {"High": "bold green", "Medium": "bold yellow", "Low": "bold red",
                     "Unknown": "bold red"}
VALUE_WIDTH = 220
BAR_WIDTH = 24

CALL_HELP = """  y  yes, that result is right       n  no, that result is wrong
  ?  I can't tell
  i  the inputs already look wrong
  t  this function is fine, stop asking about it
  s  show the function's code        e  how it behaved in passing tests
  w  why this question?              tree  show every call so far
  u  undo my last answer
  q  stop and show what we have"""
LINE_HELP = """  y  yes, these values look right   n  no, something is already wrong
  ?  I can't tell
  s  show the function's code        u  undo my last answer
  q  stop and show what we have"""


def short_name(qualname):
    return qualname.replace(".<locals>", "")


def failure_summary(text):
    """The pytest "E ..." lines of a failure: what actually went wrong."""
    lines = [line[1:].strip() for line in (text or "").splitlines() if line.startswith("E ")]
    return lines[:3]


def confidence_of(session):
    """(label, one-sentence reason) for the final answer."""
    zoom = session.zoom
    if session.stop_reason == "user quit":
        return "Unknown", "You stopped early, so this is only the best idea so far."
    if session.basis == "no_project_code":
        return "Unknown", "The test failed before it ran any of the project's own functions."
    if session.basis == "sbfl":
        return "Low", ("The questions didn't settle it, so this is the best statistical guess "
                       "from which tests failed.")
    if session.stop_reason in LOW_CONFIDENCE_STOPS:
        return "Low", "QDebug ran out of useful questions before it could be sure."
    if zoom is not None and zoom.status == "localized":
        return "High", "Your answers point directly at this code."
    return "Medium", "Your answers point at this function, but not at one specific line."


class UI:
    def __init__(self, console=None, pause=0.0):
        self.console = console or Console(highlight=False)
        self.pause = pause
        self.stage = 0

    # -------------------------------------------------------------- framing
    def banner(self):
        self.console.print(Panel(
            Text.assemble(("QDebug", f"bold {ACCENT}"), "  finds the cause of a failing test by asking "
                          "you simple yes/no questions, so you don't have to read the code."),
            border_style=ACCENT))

    def step(self, number):
        if number == self.stage:
            return
        self.stage = number
        title, explanation = STEPS[number]
        self.console.print()
        self.console.print(Rule(Text(f"Step {number} of {TOTAL_STEPS}: {title}", style=f"bold {ACCENT}"),
                                style=ACCENT, align="left"))
        self.console.print(Text(explanation, style="dim"))

    def working(self, message):
        return self.console.status(message, spinner="dots")

    def note(self, message):
        """Session progress messages, reworded for the audience."""
        text = str(message).strip()
        if text.startswith("escalating"):
            text = "Not enough to go on yet, so QDebug is looking at more functions."
        elif text.startswith("zoom refuted"):
            text = "That call turned out to be fine, so QDebug is moving to the next suspect."
        elif text.startswith("note:") and "folded" in text:
            text = "This test makes a lot of calls, so QDebug grouped some of them together."
        elif text.startswith("undone"):
            text = "Undone."
        self.console.print(Text(f"  {text}", style="yellow"))

    # ---------------------------------------------------------------- tests
    def test_summary(self, spectrum):
        failing, passing = spectrum.failing, spectrum.passing
        summary = Text.assemble(f"{len(spectrum.tests)} tests ran:  ",
                                (f"{len(passing)} passed", "bold green"), "   ",
                                (f"{len(failing)} failed", "bold red"))
        self.console.print(summary)

    def choose_test(self, failing):
        """Ask which failing test to debug; returns its node id."""
        if len(failing) == 1:
            return failing[0].nodeid
        table = Table.grid(padding=(0, 2))
        for i, test in enumerate(failing, 1):
            reason = failure_summary(test.failure)
            table.add_row(Text(str(i), style=f"bold {ACCENT}"), Text(test.nodeid, style="red"),
                          Text(truncate(reason[0], 60) if reason else "", style="dim"))
        self.console.print(table)
        while True:
            try:
                choice = self.console.input(f"  Which test should we debug? (1-{len(failing)}) > ").strip()
            except EOFError:
                choice = "1"
            if choice.isdigit() and 1 <= int(choice) <= len(failing):
                return failing[int(choice) - 1].nodeid
            self.console.print(Text("  Please type one of the numbers above.", style="yellow"))

    def failing_test(self, test_id, failure_text):
        body = [Text(test_id, style="bold")]
        for line in failure_summary(failure_text):
            body.append(Text(line, style="red"))
        self.console.print(Panel(Group(*body), title="The failing test", title_align="left",
                                 border_style="red"))

    # ------------------------------------------------------------ questions
    def _values(self, items):
        table = Table.grid(padding=(0, 2))
        table.add_column(style=ACCENT, no_wrap=True)
        table.add_column(overflow="fold")
        for name, value in items:
            table.add_row(name, Text(truncate(value, VALUE_WIDTH)))
        return table

    def _suspects(self, ctx):
        belief = ctx.belief()
        fpost = belief.function_posterior(belief.posterior(ctx.answers()))
        real = {f: p for f, p in fpost.items() if not ctx._is_test(f)}
        total = sum(real.values())
        if not total:
            return None
        table = Table.grid(padding=(0, 1))
        for func, mass in sorted(real.items(), key=lambda kv: -kv[1])[:3]:
            share = mass / total
            filled = round(share * BAR_WIDTH)
            table.add_row(Text(truncate(short_name(func.split("::", 1)[-1]), 34), no_wrap=True),
                          Text("█" * filled + "░" * (BAR_WIDTH - filled), style="red"),
                          Text(f"{100 * share:3.0f}%"))
        return Group(Text("Most suspected right now:", style="dim"), table)

    def hint(self, question):
        text = ai_hint(question)
        if text:
            self.console.print(Text(f"  {text}", style="magenta"))

    def triage(self, triage, model):
        """What Claude made of the failing test before the questions start."""
        if triage is None:
            return
        kind = {"crash": "a crash", "wrong-value": "a wrong value", "state": "a problem with shared state",
                "unknown": "not clear yet"}.get(triage.bug_kind, triage.bug_kind)
        body = [Text.assemble("Claude reads this as ", (kind, "bold"), ". ", triage.reason)]
        if triage.suspects:
            names = ", ".join(short_name(s.split("::", 1)[-1]) for s in triage.suspects)
            body.append(Text.assemble("First suspects: ", (names, "bold")))
        body.append(Text("QDebug still checks every suspect with questions.", style="dim"))
        self.console.print(Panel(Group(*body), title=f"First look ({model})", title_align="left",
                                 border_style="magenta"))

    def show_ai_answer(self, question, ctx, answer):
        """A question that Claude answered on its own (hybrid oracle)."""
        if question.kind == "call":
            self.show_call(question, ctx)
        else:
            self.show_line(question, ctx)
        self.show_answer(answer.verdict, f"Claude ({answer.confidence:.0%} sure)")
        reason = answer.note.split(": ", 1)[1] if ": " in answer.note else ""
        if reason:
            self.console.print(Text(f"    {reason}", style="dim"))

    def explanation(self, explanation):
        if explanation is None:
            return
        body = [Text(explanation.summary, style="bold")]
        if explanation.explanation:
            body += [Text(), Text(explanation.explanation)]
        if explanation.fix.strip():
            body += [Text(), Text("Suggested fix:", style="dim"), Text(explanation.fix, style="green")]
        body += [Text(), Text.assemble("Claude's confidence: ", (explanation.confidence.capitalize(),
                                       CONFIDENCE_STYLES.get(explanation.confidence.capitalize(), "bold")))]
        self.console.print(Panel(Group(*body), title="What went wrong", title_align="left",
                                 border_style="magenta"))

    def show_call(self, question, ctx):
        self.step(2)
        node, info = question.node, question.func_info
        name = short_name(node.qualname)
        body = []
        if info is not None and info.doc:
            body.append(Text(info.doc.strip().splitlines()[0], style="italic dim"))
        args = node.args or {}
        if args:
            body += [Text.assemble((name, "bold"), " was called with:"),
                     self._values((k, v["short"]) for k, v in args.items())]
        else:
            body.append(Text.assemble((name, "bold"), " was called with no arguments."))
        body.append(Text())
        if node.exc:
            body += [Text("and it raised an error:"),
                     Text(truncate(node.exc["short"], VALUE_WIDTH), style="bold red")]
        else:
            body += [Text("and it returned:"),
                     Text(truncate(node.ret["short"] if node.ret else "?", VALUE_WIDTH), style="bold")]
        if node.mutated:
            body += [Text(), Text("It also changed:")]
            body.append(self._values(
                (k, f"{truncate(args[k]['short'], 100)}  ->  {truncate(node.after[k]['short'], 100)}")
                for k in node.mutated))
        self.console.print()
        self.console.print(Panel(Group(*body), title=f"Question {question.number}", title_align="left",
                                 subtitle=f"{node.file}:{node.line}", subtitle_align="right",
                                 border_style=ACCENT))
        if ctx is not None:
            suspects = self._suspects(ctx)
            if suspects is not None:
                self.console.print(suspects)
        self.hint(question)

    def _code_window(self, lines, first, last, marked, arrow):
        table = Table.grid(padding=(0, 1))
        table.add_column(justify="right", style="dim")
        table.add_column(no_wrap=True)
        table.add_column(overflow="fold")
        for number in range(first, last + 1):
            if number < 1 or number > len(lines):
                continue
            hit = number in marked
            table.add_row(str(number), Text(arrow if hit else " ", style=f"bold {ACCENT}"),
                          Text(lines[number - 1], style="bold" if hit else "dim"))
        return table

    def show_line(self, question, ctx):
        self.step(3)
        node, cp, info = question.node, question.checkpoint, question.func_info
        name = short_name(node.qualname)
        body = []
        if cp["kind"] == "line":
            body.append(Text.assemble("Inside ", (name, "bold"), ", just ", ("before", "bold"),
                                      f" line {cp['line']} runs:"))
            if info is not None and question.file_lines:
                first = max(info.line, cp["line"] - 3)
                last = min(info.end_line, cp["line"] + 2)
                body.append(self._code_window(question.file_lines, first, last, {cp["line"]}, ">"))
                body.append(Text(f"(line {cp['line']} has not run yet)", style="dim"))
        else:
            body.append(Text.assemble("When ", (name, "bold"), " finished:"))
        body += [Text(), Text("The variables held:", style="dim")]
        body.append(self._values((k, v["short"]) for k, v in cp["locals"].items()))
        if cp["kind"] == "return":
            if cp.get("exc"):
                body.append(Text.assemble("Raising: ", (truncate(cp["exc"]["short"], VALUE_WIDTH), "bold red")))
            else:
                body.append(Text.assemble("Returning: ",
                                          (truncate(cp["ret"]["short"] if cp.get("ret") else "?",
                                                    VALUE_WIDTH), "bold")))
        self.console.print()
        self.console.print(Panel(Group(*body), title=f"Line check {question.number}", title_align="left",
                                 subtitle=node.file, subtitle_align="right", border_style=ACCENT))
        self.hint(question)

    def show_answer(self, verdict, source):
        word = ANSWER_WORDS.get(verdict, str(verdict))
        self.console.print(Text.assemble(f"  {source}: ", (word, f"bold {ANSWER_STYLES.get(verdict, 'white')}")))
        if self.pause:
            time.sleep(self.pause)

    # -------------------------------------------------------------- verdict
    def _history(self, session, zoom):
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="right")
        table.add_column(overflow="fold")
        table.add_column(no_wrap=True)

        def row(index, what, verdict):
            table.add_row(str(index), Text(what), Text(ANSWER_WORDS.get(verdict, str(verdict)),
                                                       style=ANSWER_STYLES.get(verdict, "white")))

        index = 0
        for entry in session.log:
            if entry.kind != "answer" or entry.source != "oracle":
                continue
            index += 1
            args = ", ".join(f"{k}={truncate(v, 24)}" for k, v in entry.summary["args"].items() if k != "self")
            row(index, f"{short_name(entry.summary['qualname'])}({truncate(args, 56)}) "
                       f"{truncate(entry.summary['output'], 28)}", entry.verdict)
        for step in (zoom.transcript if zoom else []):
            index += 1
            where = f"variables before line {step['line']}" if step["kind"] == "line" else "variables at the end"
            row(index, where, step["verdict"])
        return table if index else None

    def verdict(self, session):
        self.console.print()
        found, zoom = session.found, session.zoom
        label, reason = confidence_of(session)
        total_functions = len(session.ranking.ranked_functions)
        questions = session.questions_asked + sum(z.questions for z in session.zoom_results)
        if found is None:
            self.console.print(Panel(Text("QDebug could not name a suspect for this test."),
                                     title="No result", title_align="left", border_style="red"))
            return
        localized = zoom is not None and zoom.status == "localized" and zoom.region
        guess = label in ("Low", "Unknown")
        title = "Best guess" if guess else "Found it"
        body = []
        name = short_name(found.qualname)
        if localized:
            where = f"line {zoom.region[0]}" if len(zoom.region) == 1 else \
                f"lines {min(zoom.region)}-{max(zoom.region)}"
            body.append(Text.assemble((f"{found.file}", "bold"), f", {where}, in ", (name, "bold")))
            body.append(Text())
            lines = session.file_lines(found.file)
            body.append(self._code_window(lines, min(zoom.region) - 2, max(zoom.region) + 2,
                                          set(zoom.region), ">>"))
        else:
            body.append(Text.assemble((name, "bold"), f"  in {found.file}, line {found.line}"))
        body.append(Text())
        body.append(Text.assemble("Confidence: ", (label, CONFIDENCE_STYLES[label]), f"   {reason}"))
        if found.args:
            args = ", ".join(f"{k}={truncate(v['short'], 40)}" for k, v in found.args.items() if k != "self")
            body.append(Text.assemble("The bad call: ", (f"{name}({args}) {found.output_summary(width=60)}", "bold")))
        self.console.print(Panel(Group(*body), title=title, title_align="left",
                                 border_style="yellow" if guess else "green"))
        history = self._history(session, zoom)
        if history is not None:
            self.console.print(Text("How we got here:", style="dim"))
            self.console.print(history)
        self.console.print()
        self.console.print(Text.assemble(
            (f"{questions} question{'s' if questions != 1 else ''}", "bold"),
            f" to search a project with {total_functions:,} functions, without reading its code."))


class FriendlyOracle(HumanOracle):
    """The human oracle, with the questions shown through the UI."""

    call_prompt = "  Is that the right result? (y yes, n no, ? not sure, h more) > "
    line_prompt = "  Do these values look right so far? (y yes, n no, ? not sure, h more) > "
    call_help = CALL_HELP
    line_help = LINE_HELP

    def __init__(self, ui, max_repr=300):
        console = ui.console
        super().__init__(input_fn=console.input,
                         print_fn=lambda text: console.print(Text(str(text))),
                         max_repr=max_repr)
        self.ui = ui

    def show_call(self, question, ctx):
        self.ui.show_call(question, ctx)

    def show_line(self, question, ctx):
        self.ui.show_line(question, ctx)


class NarratedOracle(Oracle):
    """Shows an automatic oracle's questions and answers, so a watcher can follow along."""

    LABELS = {"truth": "Automatic answer (compared with the fixed version)", "claude": "Claude"}

    def __init__(self, base, ui):
        self.base = base
        self.ui = ui
        self.name = base.name
        inner = getattr(base, "base", base)  # through a NoisyOracle
        self.label = self.LABELS.get(inner.name, "Automatic answer")

    def judge(self, question, ctx=None):
        if question.kind == "call":
            self.ui.show_call(question, ctx)
        else:
            self.ui.show_line(question, ctx)
        answer = self.base.judge(question, ctx)
        if answer.verdict is not None:
            label = self.label
            if answer.confidence < 1.0:
                label += f" ({answer.confidence:.0%} sure)"
            self.ui.show_answer(answer.verdict, label)
            if self.label == "Claude" and ": " in answer.note:
                self.ui.console.print(Text(f"    {answer.note.split(': ', 1)[1]}", style="dim"))
        return answer


def strip_markup(text):
    """Plain text of a rendered line (used by tests)."""
    return re.sub(r"\s+", " ", text).strip()
