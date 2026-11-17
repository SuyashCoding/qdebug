"""Command line entry point: qdebug {debug,rank,eval,variants,init-agent,bugsinpy} ...

`qdebug debug` asks you the questions by default. With --oracle claude Claude
answers them, with --oracle hybrid Claude answers the ones it is sure about
and you the rest, and --ai keeps you answering but lets Claude tune the
search and explain the result.
"""

import argparse
import os
import sys

from qdebug import __version__
from qdebug.oracles import GroundTruthOracle, HumanOracle, NoisyOracle
from qdebug.ranking import DEFAULT_TIERS, Ranking
from qdebug.report import build_report, format_report, save_session
from qdebug.runner import SPECTRUM_BACKENDS, RunnerError, RunOptions, make_runner
from qdebug.session import DebugSession, SessionConfig, SessionError, tier_list
from qdebug.spectrum import collect_spectrum, scan_functions
from qdebug.tuning import BUG_KINDS, POLICIES

ORACLES = ("human", "claude", "hybrid", "truth")
AI_ORACLES = ("claude", "hybrid")


class CLIError(Exception):
    """A usage problem that ends the command with a message and exit code 2."""


def human_oracle(ui, max_repr):
    if ui is not None:
        from qdebug.ui import FriendlyOracle
        return FriendlyOracle(ui, max_repr=max_repr)
    return HumanOracle(max_repr=max_repr)


def make_oracle(kind, test_id, fixed=None, noise=0.0, seed=0, run=None, max_repr=300, ui=None,
                assistant=None, ai_confidence=0.8):
    if kind == "human":
        oracle = human_oracle(ui, max_repr)
    elif kind == "truth":
        if not fixed:
            raise CLIError("--oracle truth needs --fixed PATH (a copy of the project without the bug)")
        kwargs = {"run": run} if run is not None else {}
        oracle = GroundTruthOracle(fixed, test_id, max_repr=max_repr, **kwargs)
    elif kind in AI_ORACLES:
        if assistant is None:
            raise CLIError(f"--oracle {kind} needs Claude")
        show = ui.show_ai_answer if ui is not None else None
        oracle = assistant.oracle(kind, human=human_oracle(ui, max_repr), threshold=ai_confidence,
                                  show=show)
    else:
        raise CLIError(f"unknown oracle {kind!r}")
    if noise > 0:
        oracle = NoisyOracle(oracle, noise, seed)
    if ui is not None and kind in ("truth", "claude"):
        from qdebug.ui import NarratedOracle
        oracle = NarratedOracle(oracle, ui)
    return oracle


# ------------------------------------------------------------------ options

def add_policy_options(p, default):
    g = p.add_argument_group("search tuning (see qdebug/tuning.py)")
    g.add_argument("--policy", choices=sorted(POLICIES), default=default,
                   help=f"conditional rules for pruning, stopping and falling back (default: {default})")
    g.add_argument("--bug-kind", choices=sorted(BUG_KINDS), default=None,
                   help="adjust the rules for one kind of bug (with Claude, triage picks it)")
    g.add_argument("--assertion-weight", type=float, default=None,
                   help="prior multiplier for calls before the previous passing assertion (1 = off)")
    g.add_argument("--repeat-discount", type=float, default=None,
                   help="multiplier on a function's other calls per correct call (1 = off)")


def add_ai_options(p):
    g = p.add_argument_group("Claude (optional; needs pip install 'qdebug[ai]' and an API key)")
    g.add_argument("--ai", action="store_true",
                   help="with --oracle human: let Claude tune the search and explain the result")
    g.add_argument("--ai-model", default=None,
                   help="Claude model (default: $QDEBUG_AI_MODEL or claude-haiku-5-5)")
    g.add_argument("--ai-effort", default=None, choices=("low", "medium", "high", "xhigh", "max"),
                   help="how hard Claude thinks (default: $QDEBUG_AI_EFFORT or medium)")
    g.add_argument("--ai-confidence", type=float, default=0.8,
                   help="hybrid oracle: Claude answers on its own from this confidence on (default 0.8)")
    g.add_argument("--ai-source", action="store_true",
                   help="also show Claude the body of each function it judges (by default it sees "
                        "the signature, docstring, caller and values only)")
    g.add_argument("--agent", metavar="PATH", default=None,
                   help="prompt file to use (default: <project>/.qdebug/agent.md if it exists)")
    g.add_argument("--no-triage", action="store_true", help="skip Claude's first look at the failure")
    g.add_argument("--no-explain", action="store_true", help="skip Claude's explanation of the result")


def add_run_options(p):
    """Options that adapt the traced pytest runs to the project's environment."""
    g = p.add_argument_group("project environment")
    g.add_argument("--python", help="interpreter or virtualenv directory of the project "
                   "(default: the one running qdebug); it needs pytest installed")
    g.add_argument("--pytest-arg", action="append", default=[], metavar="ARG",
                   help="extra pytest argument for every run, e.g. --pytest-arg=--ds=site.settings "
                        "(repeatable)")
    g.add_argument("--suite", action="append", default=[], metavar="PATH",
                   help="restrict the whole-suite coverage run to these test paths (repeatable)")
    g.add_argument("--pythonpath", action="append", default=[], metavar="DIR",
                   help="extra import path, relative to the project (repeatable)")
    g.add_argument("--no-plugin-autoload", action="store_true",
                   help="do not load the pytest plugins installed in the environment")
    g.add_argument("--no-seed-random", action="store_true",
                   help="do not call random.seed(0) before every test")
    g.add_argument("--no-trace-setup", action="store_true",
                   help="do not trace the fixtures that run before the test")
    g.add_argument("--spectrum-backend", choices=SPECTRUM_BACKENDS, default="auto",
                   help="coverage tracer: sys.monitoring (3.12+, fast) or sys.settrace")
    g.add_argument("--max-nodes", type=int, default=RunOptions.max_nodes,
                   help="execution-tree size limit; later calls are folded into their callers")
    g.add_argument("--max-repeat", type=int, default=RunOptions.max_repeat,
                   help="calls of one function under one caller recorded as separate nodes")
    g.add_argument("--max-depth", type=int, default=RunOptions.max_depth)
    g.add_argument("--timeout", type=int, default=RunOptions.timeout,
                   help="seconds per traced pytest run")


def make_run(args):
    return make_runner(RunOptions(
        python=args.python, autoload_plugins=not args.no_plugin_autoload,
        pytest_args=tuple(args.pytest_arg), suite=tuple(args.suite), pythonpath=tuple(args.pythonpath),
        seed_random=not args.no_seed_random, trace_setup=not args.no_trace_setup,
        spectrum_backend=args.spectrum_backend, max_nodes=args.max_nodes, max_repeat=args.max_repeat,
        max_depth=args.max_depth, timeout=args.timeout))


def check_project(path):
    if not os.path.isdir(path):
        raise CLIError(f"project directory not found: {path}")


# ------------------------------------------------------------------- rank

def cmd_rank(args):
    check_project(args.project)
    spectrum = collect_spectrum(args.project, run=make_run(args))
    ranking = Ranking(spectrum, scan_functions(args.project))
    print(f"{len(spectrum.tests)} tests: {len(spectrum.failing)} failing, "
          f"{len(spectrum.passing)} passing; {len(ranking.ranked_functions)} project functions")
    for t in spectrum.failing:
        print(f"  FAILED {t.nodeid}")
    print("\nFunctions by Ochiai suspiciousness:")
    print(f"  {'#':>3}  {'ochiai':>6}  {'maxline':>7}  {'fail':>4}  {'pass':>4}  function")
    for rank, func, score, maxline, nf, np in ranking.function_table(args.limit):
        print(f"  {rank:>3}  {score:6.3f}  {maxline:7.3f}  {nf:>4}  {np:>4}  {func}")
    print("\nLines by Ochiai suspiciousness:")
    for i, (f, n) in enumerate(ranking.ranked_lines[: args.limit], 1):
        print(f"  {i:>3}  {ranking.line_scores[(f, n)]:6.3f}  {f}:{n}")
    print("\nMonitoring tiers:")
    for pct in DEFAULT_TIERS:
        print(f"  {pct:>3}% -> top {ranking.tier_size(pct)} functions")
    return 0


# ------------------------------------------------------------------ debug

def make_ui(args):
    """The friendly interface, or None for the plain text output."""
    if args.plain:
        return None
    try:
        from qdebug.ui import UI
    except ImportError:
        print("note: install `rich` for the friendly interface; using plain output", file=sys.stderr)
        return None
    return UI(pause=args.pause)


def make_assistant(args):
    """The Claude assistant if this run uses Claude, else None."""
    if args.oracle not in AI_ORACLES and not args.ai:
        return None
    from qdebug.ai import Agent, Assistant, Claude, sdk_available
    from qdebug.ai.client import INSTALL_HINT
    if not sdk_available():
        raise CLIError(f"the Claude features need the Anthropic SDK: {INSTALL_HINT}")
    try:
        agent = Agent.load(args.agent, project=args.project)
        claude = Claude(model=args.ai_model, effort=args.ai_effort)
    except (OSError, ValueError) as exc:
        raise CLIError(str(exc)) from None
    return Assistant(claude, agent, show_source=args.ai_source)


def session_config(args):
    return SessionConfig(
        project=args.project, test=args.test, strategy=args.strategy,
        tiers=tier_list(args.tiers), error_rate=args.error_rate, budget=args.budget,
        threshold=args.threshold, stop_level=args.stop_level, max_repr=args.max_repr,
        zoom=not args.no_zoom, use_inadmissible=not args.no_inadmissible, ascii=args.ascii,
        policy=args.policy, assertion_weight=args.assertion_weight,
        repeat_discount=args.repeat_discount, bug_kind=args.bug_kind)


def save_dir(args):
    if args.save_dir is None:
        return os.path.join(args.project, ".qdebug", "sessions")
    return args.save_dir


def finish(session, assistant, args, ui=None):
    """Explanation, report and the session file, after the search."""
    if assistant is not None and not args.no_explain and session.found is not None:
        if ui is not None:
            with ui.working("Claude is writing up what went wrong..."):
                session.explanation = assistant.explain(session)
        else:
            session.explanation = assistant.explain(session)
    report = build_report(session, assistant)
    if ui is not None:
        ui.verdict(session)
        ui.explanation(session.explanation)
        for note in (assistant.notes if assistant else []):
            ui.note(note)
        if args.details:
            print()
            print(format_report(report))
    else:
        print()
        print(format_report(report))
    directory = save_dir(args)
    if directory:
        path = save_session(report, directory)
        if ui is not None:
            ui.console.print(f"Full details saved to {path}", style="dim", markup=False)
        else:
            print(f"\nSession saved to {path}")
    return 0


def run_triage(session, assistant, args, ui=None):
    """Claude's first look. Returns the assistant to go on with (None once Claude is unavailable)."""
    from qdebug.ai.client import AIUnavailable
    if assistant is None or args.no_triage:
        return assistant
    try:
        if ui is not None:
            with ui.working("Claude is taking a first look..."):
                triage = assistant.triage(session)
        else:
            triage = assistant.triage(session)
    except AIUnavailable as exc:
        if args.oracle == "claude":
            raise
        message = f"Claude is unavailable, so you answer every question ({exc})"
        (ui.note if ui is not None else print)(message)
        return None
    if triage is None:
        return assistant
    session.apply_triage(triage)
    if ui is not None:
        ui.triage(triage, assistant.model)
    else:
        print(f"Claude's first look: a {triage.bug_kind} bug. {triage.reason}")
        if triage.suspects:
            print(f"  suspects: {', '.join(triage.suspects)}")
    return assistant


def debug_with_ui(args, config, run, ui, assistant):
    session = DebugSession(config, oracle=None, run=run, out=ui.note)
    ui.banner()
    ui.step(1)
    with ui.working("Running the project's tests..."):
        session.collect()
    ui.test_summary(session.spectrum)
    if not config.test and args.oracle in ("human", "hybrid"):
        config.test = ui.choose_test(session.ranked_failing())
    with ui.working("Getting ready..."):
        session.prepare()
    ui.failing_test(session.test_id, session.failure_text)
    assistant = run_triage(session, assistant, args, ui)
    oracle_kind = args.oracle if assistant is not None or args.oracle not in AI_ORACLES else "human"
    session.oracle = make_oracle(oracle_kind, session.test_id, args.fixed, args.noise, args.seed,
                                 run=run, max_repr=args.max_repr, ui=ui, assistant=assistant,
                                 ai_confidence=args.ai_confidence)
    session.run_session()
    return finish(session, assistant, args, ui)


def debug_plain(args, config, run, assistant):
    session = DebugSession(config, oracle=None, run=run)
    session.prepare()
    assistant = run_triage(session, assistant, args)
    oracle_kind = args.oracle if assistant is not None or args.oracle not in AI_ORACLES else "human"
    session.oracle = make_oracle(oracle_kind, session.test_id, args.fixed, args.noise, args.seed,
                                 run=run, max_repr=args.max_repr, assistant=assistant,
                                 ai_confidence=args.ai_confidence)
    print(f"Debugging {session.test_id} with the {args.strategy} strategy "
          f"({len(session.spectrum.failing)} failing / {len(session.spectrum.tests)} tests)")
    if args.oracle in ("human", "hybrid"):
        print("Answer each question about a single call: is its output correct for its inputs?")
        print("Type h for help.")
    session.run_session()
    return finish(session, assistant, args)


def cmd_debug(args):
    check_project(args.project)
    try:
        config = session_config(args)
    except ValueError as exc:
        raise CLIError(str(exc)) from None
    run = make_run(args)
    assistant = make_assistant(args)
    ui = make_ui(args)
    if ui is not None:
        return debug_with_ui(args, config, run, ui, assistant)
    return debug_plain(args, config, run, assistant)


# --------------------------------------------------------- benchmarks etc.

def _suites(args):
    from qdebug.suites import SuiteError, resolve_suites
    try:
        return resolve_suites(args.suite, base=args.benchmarks)
    except SuiteError as exc:
        raise CLIError(str(exc)) from None


def cmd_eval(args):
    from qdebug.evaluate import run_evaluation

    run_evaluation(
        _suites(args),
        strategies=[s.strip() for s in args.strategies.split(",") if s.strip()],
        noise_levels=[float(x) for x in args.noise.split(",") if x.strip()],
        seeds=args.seeds, out_dir=args.out, tiers=tier_list(args.tiers),
        error_rate=args.error_rate, budget=args.budget, policy=args.policy,
        bug_ids=set(args.bug) or None, triage=args.triage, noise_model=args.noise_model,
        overconfidence=args.overconfidence, confidence_use=args.confidence_use,
        zoom_search=args.zoom_search)
    return 0


def cmd_eval_ai(args):
    from qdebug.ai import sdk_available
    from qdebug.ai.benchmark import run_ai_benchmark
    from qdebug.ai.client import INSTALL_HINT
    if not args.relay and not sdk_available():
        raise CLIError(f"eval-ai needs the Anthropic SDK: {INSTALL_HINT}")
    run_ai_benchmark(_suites(args), mode=args.oracle, model=args.ai_model, effort=args.ai_effort,
                     relay=args.relay,
                     out_dir=args.out, bug_ids=set(args.bug) or None, workers=args.workers,
                     policy=args.policy, threshold=args.ai_confidence, show_source=args.ai_source,
                     triage=not args.no_triage, explain=not args.no_explain)
    return 0


def cmd_variants(args):
    from qdebug.suites import SuiteError, build_variants, format_rows
    for suite in _suites(args):
        print(f"{suite.name}: building and checking variants in {suite.variants}")
        try:
            rows = build_variants(suite, check=not args.no_check)
        except SuiteError as exc:
            raise CLIError(str(exc)) from None
        if rows:
            print(format_rows(rows))
        print()
    return 0


def cmd_init_agent(args):
    from qdebug.ai.prompts import write_project_agent
    check_project(args.project)
    try:
        path = write_project_agent(args.project, force=args.force)
    except FileExistsError as exc:
        raise CLIError(str(exc)) from None
    print(f"Wrote {path}. Edit it to change how Claude debugs this project; qdebug reads it "
          f"automatically. Put facts about your code under '## project notes'.")
    return 0


def cmd_bugsinpy(args):
    from qdebug.bugsinpy import run_bugsinpy

    run_bugsinpy(args.bugsinpy, args.work, args.bugs,
                 [s.strip() for s in args.strategies.split(",") if s.strip()],
                 args.out, timeout=args.timeout, policy=args.policy,
                 policies=[p.strip() for p in (args.policies or "").split(",") if p.strip()],
                 assertion_weight=args.assertion_weight, repeat_discount=args.repeat_discount)
    return 0


# ----------------------------------------------------------------- parser

def build_parser():
    parser = argparse.ArgumentParser(
        prog="qdebug",
        description="Find the line behind a failing pytest test by answering yes/no questions, "
                    "yourself or with Claude.",
        epilog="Start with: qdebug debug --project PATH   (run `qdebug debug -h` for every option)")
    parser.add_argument("--version", action="version", version=f"qdebug {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("debug", help="debug a failing test by answering questions (or let Claude answer)")
    p.add_argument("--project", default=".", help="the pytest project (default: the current directory)")
    p.add_argument("--test", help="node id of the failing test (default: the easiest failing test)")
    p.add_argument("--oracle", choices=ORACLES, default="human",
                   help="who answers: you (human), Claude (claude), Claude when it is sure and you "
                        "otherwise (hybrid), or a comparison with a fixed copy (truth)")
    p.add_argument("--fixed", help="path to a copy of the project without the bug (for --oracle truth)")
    p.add_argument("--plain", action="store_true", help="plain text output instead of the friendly interface")
    p.add_argument("--details", action="store_true", help="also print the full technical report")
    p.add_argument("--save-dir", default=None,
                   help="where to write session_<timestamp>.json (default: <project>/.qdebug/sessions; "
                        "'' to skip)")
    add_ai_options(p)
    g = p.add_argument_group("search")
    g.add_argument("--strategy", choices=["infogain", "infogain-full", "topdown", "divide"],
                   default="infogain")
    g.add_argument("--tiers", default=",".join(map(str, DEFAULT_TIERS)),
                   help="monitoring tiers in percent of the project's functions")
    g.add_argument("--error-rate", type=float, default=0.1, help="assumed error rate ε of an answer")
    g.add_argument("--budget", type=int, default=30, help="most call questions to ask")
    g.add_argument("--threshold", type=float, default=0.9, help="posterior that counts as confident")
    g.add_argument("--stop-level", choices=["function", "node"], default="function")
    g.add_argument("--no-zoom", action="store_true", help="stop at the function, skip the line search")
    g.add_argument("--no-inadmissible", action="store_true",
                   help="treat 'inputs are already wrong' answers as plain 'unknown'")
    g = p.add_argument_group("display and experiments")
    g.add_argument("--max-repr", type=int, default=300, help="characters shown per value")
    g.add_argument("--ascii", action="store_true", help="ASCII-only tree markers")
    g.add_argument("--pause", type=float, default=0.0,
                   help="seconds to wait after each automatic answer, so an audience can follow")
    g.add_argument("--noise", type=float, default=0.0, help="flip each answer with this probability")
    g.add_argument("--seed", type=int, default=0)
    add_policy_options(p, default="tuned")
    add_run_options(p)
    p.set_defaults(func=cmd_debug)

    p = sub.add_parser("rank", help="rank functions and lines by suspiciousness (no questions)")
    p.add_argument("--project", default=".")
    p.add_argument("--limit", type=int, default=15)
    add_run_options(p)
    p.set_defaults(func=cmd_rank)

    p = sub.add_parser("init-agent", help="copy Claude's prompt into the project to customise it")
    p.add_argument("--project", default=".")
    p.add_argument("--force", action="store_true", help="overwrite an existing .qdebug/agent.md")
    p.set_defaults(func=cmd_init_agent)

    p = sub.add_parser("eval", help="batch experiments on the benchmark suites")
    p.add_argument("--suite", action="append", default=[], metavar="DIR",
                   help="benchmark suite (project/ + bugs.json); default: every suite in --benchmarks")
    p.add_argument("--benchmarks", default="benchmarks", help="where suites are found by name")
    p.add_argument("--bug", action="append", default=[], metavar="ID", help="only these bugs (repeatable)")
    p.add_argument("--strategies", default="infogain,topdown,divide")
    p.add_argument("--noise", default="0.0,0.1,0.2")
    p.add_argument("--seeds", type=int, default=10)
    p.add_argument("--tiers", default=",".join(map(str, DEFAULT_TIERS)))
    p.add_argument("--error-rate", type=float, default=0.1)
    p.add_argument("--budget", type=int, default=30)
    p.add_argument("--out", default="results")
    p.add_argument("--policy", choices=sorted(POLICIES), default="tuned")
    p.add_argument("--triage", choices=["none", "category"], default="none",
                   help="category: tune each session for its bug's labelled category (a perfect triage)")
    p.add_argument("--noise-model", choices=["flip", "confident"], default="flip",
                   help="flip: wrong at exactly --noise; confident: wrong at a varying rate around "
                        "--noise and says how sure it is (a stand-in for a model oracle)")
    p.add_argument("--overconfidence", type=float, default=1.0,
                   help="confident noise: stated error = real error / this (1 = calibrated)")
    p.add_argument("--confidence-use", choices=["floor", "raw", "ignore"], default="floor",
                   help="how stated confidences weigh answers (see session.answer_error)")
    p.add_argument("--zoom-search", choices=["binary", "bayes"], default=None,
                   help="line search (default: the policy's)")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("eval-ai", help="measure Claude as the oracle on the benchmark suites (costs API usage)")
    p.add_argument("--suite", action="append", default=[], metavar="DIR")
    p.add_argument("--benchmarks", default="benchmarks")
    p.add_argument("--bug", action="append", default=[], metavar="ID", help="only these bugs (repeatable)")
    p.add_argument("--oracle", choices=AI_ORACLES, default="claude",
                   help="claude: Claude answers everything; hybrid: the simulated person answers when "
                        "Claude is unsure")
    p.add_argument("--ai-model", default=None)
    p.add_argument("--ai-effort", default=None, choices=("low", "medium", "high", "xhigh", "max"))
    p.add_argument("--ai-confidence", type=float, default=0.8)
    p.add_argument("--ai-source", action="store_true")
    p.add_argument("--no-triage", action="store_true")
    p.add_argument("--no-explain", action="store_true")
    p.add_argument("--policy", choices=sorted(POLICIES), default="tuned")
    p.add_argument("--workers", type=int, default=4, help="sessions run in parallel")
    p.add_argument("--relay", metavar="DIR", default=None,
                   help="answer through files in DIR instead of the API, e.g. by a Claude Code agent "
                        "(python -m qdebug.ai.relay next DIR/<suite>-<bug>)")
    p.add_argument("--out", default="results/claude")
    p.set_defaults(func=cmd_eval_ai)

    p = sub.add_parser("variants", help="build and check the buggy copies of the benchmark suites")
    p.add_argument("--suite", action="append", default=[], metavar="DIR")
    p.add_argument("--benchmarks", default="benchmarks")
    p.add_argument("--no-check", action="store_true", help="do not run the tests of each variant")
    p.set_defaults(func=cmd_variants)

    p = sub.add_parser("bugsinpy", help="evaluate on real bugs from the BugsInPy benchmark")
    p.add_argument("--bugsinpy", required=True, help="a clone of github.com/soarsmu/BugsInPy")
    p.add_argument("--work", required=True,
                   help="directory for project clones, checkouts, Pythons and virtualenvs")
    p.add_argument("--bugs", required=True,
                   help="e.g. thefuck:1-10,PySnooper,tqdm:3;7 (project[:ids])")
    p.add_argument("--strategies", default="infogain,divide,topdown")
    p.add_argument("--timeout", type=int, default=600, help="seconds per traced pytest run")
    p.add_argument("--out", default="results/bugsinpy")
    p.add_argument("--policies", help="run several policies per bug on the same checkout, "
                                      "e.g. baseline,tuned (overrides --policy)")
    add_policy_options(p, default="baseline")
    p.set_defaults(func=cmd_bugsinpy)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    from qdebug.ai.client import AIUnavailable
    try:
        return args.func(args)
    except (CLIError, SessionError, RunnerError, AIUnavailable) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
