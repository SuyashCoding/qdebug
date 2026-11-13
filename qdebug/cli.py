"""Command line entry point: python -m qdebug {rank,debug,eval} ..."""

import argparse
import sys

from qdebug.oracles import GroundTruthOracle, HumanOracle, LLMOracle, NoisyOracle
from qdebug.ranking import DEFAULT_TIERS, Ranking
from qdebug.report import build_report, format_report, save_session
from qdebug.runner import SPECTRUM_BACKENDS, RunnerError, RunOptions, make_runner
from qdebug.session import DebugSession, SessionConfig, SessionError, tier_list
from qdebug.spectrum import collect_spectrum, scan_functions
from qdebug.tuning import POLICIES


def make_oracle(kind, test_id, fixed=None, noise=0.0, seed=0, run=None, max_repr=300, ui=None):
    if kind == "human":
        if ui is not None:
            from qdebug.ui import FriendlyOracle
            oracle = FriendlyOracle(ui, max_repr=max_repr)
        else:
            oracle = HumanOracle(max_repr=max_repr)
    elif kind == "truth":
        if not fixed:
            raise SystemExit("--oracle truth needs --fixed PATH (the correct project)")
        kwargs = {"run": run} if run is not None else {}
        oracle = GroundTruthOracle(fixed, test_id, max_repr=max_repr, **kwargs)
    elif kind == "llm":
        oracle = LLMOracle()
    else:
        raise SystemExit(f"unknown oracle {kind!r}")
    if noise > 0:
        oracle = NoisyOracle(oracle, noise, seed)
    if ui is not None and kind != "human":
        from qdebug.ui import NarratedOracle
        oracle = NarratedOracle(oracle, ui)
    return oracle


def add_policy_options(p, default):
    g = p.add_argument_group("search tuning (see qdebug/tuning.py)")
    g.add_argument("--policy", choices=sorted(POLICIES), default=default,
                   help="conditional rules for pruning, stopping and falling back")
    g.add_argument("--assertion-weight", type=float, default=None,
                   help="prior multiplier for calls before the previous passing assertion (1 = off)")
    g.add_argument("--repeat-discount", type=float, default=None,
                   help="multiplier on a function's other calls per correct call (1 = off)")


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
        seed_random=not args.no_seed_random, spectrum_backend=args.spectrum_backend,
        max_nodes=args.max_nodes, max_repeat=args.max_repeat, max_depth=args.max_depth,
        timeout=args.timeout))


def cmd_rank(args):
    try:
        spectrum = collect_spectrum(args.project, run=make_run(args))
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
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


def debug_with_ui(args, config, run, ui):
    session = DebugSession(config, oracle=None, run=run, out=ui.note)
    ui.banner()
    ui.step(1)
    try:
        with ui.working("Running the project's tests..."):
            session.collect()
        ui.test_summary(session.spectrum)
        if not config.test and args.oracle == "human":
            config.test = ui.choose_test(session.spectrum.failing)
        with ui.working("Getting ready..."):
            session.prepare()
        ui.failing_test(session.test_id, session.failure_text)
        session.oracle = make_oracle(args.oracle, session.test_id, args.fixed, args.noise, args.seed,
                                     run=run, max_repr=args.max_repr, ui=ui)
        session.run_session()
    except (SessionError, RunnerError) as exc:
        ui.console.print()
        ui.note(f"QDebug could not finish: {exc}")
        return 2
    ui.verdict(session)
    report = build_report(session)
    if args.details:
        print()
        print(format_report(report))
    if args.save_dir:
        path = save_session(report, args.save_dir)
        ui.console.print(f"Full details saved to {path}", style="dim", markup=False)
    return 0


def cmd_debug(args):
    config = SessionConfig(
        project=args.project, test=args.test, strategy=args.strategy,
        tiers=tier_list(args.tiers), error_rate=args.error_rate, budget=args.budget,
        threshold=args.threshold, stop_level=args.stop_level, max_repr=args.max_repr,
        zoom=not args.no_zoom, use_inadmissible=not args.no_inadmissible, ascii=args.ascii,
        policy=args.policy, assertion_weight=args.assertion_weight,
        repeat_discount=args.repeat_discount)
    run = make_run(args)
    ui = make_ui(args)
    if ui is not None:
        return debug_with_ui(args, config, run, ui)
    session = DebugSession(config, oracle=None, run=run)
    try:
        session.prepare()
    except (SessionError, RunnerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    session.oracle = make_oracle(args.oracle, session.test_id, args.fixed, args.noise,
                                 args.seed, run=run, max_repr=args.max_repr)
    print(f"Debugging {session.test_id} with the {args.strategy} strategy "
          f"({len(session.spectrum.failing)} failing / {len(session.spectrum.tests)} tests)")
    if args.oracle == "human":
        print("Answer each question about a single call: is its output correct for its inputs?")
        print("Type h for help.")
    try:
        session.run_session()
    except (SessionError, RunnerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = build_report(session)
    print()
    print(format_report(report))
    if args.save_dir:
        path = save_session(report, args.save_dir)
        print(f"\nSession saved to {path}")
    return 0


def cmd_eval(args):
    from qdebug.evaluate import run_evaluation

    run_evaluation(
        bugs_path=args.bugs, fixed=args.fixed, variants_dir=args.variants,
        strategies=[s.strip() for s in args.strategies.split(",") if s.strip()],
        noise_levels=[float(x) for x in args.noise.split(",") if x.strip()],
        seeds=args.seeds, out_dir=args.out, tiers=tier_list(args.tiers),
        error_rate=args.error_rate, budget=args.budget, policy=args.policy)
    return 0


def cmd_bugsinpy(args):
    from qdebug.bugsinpy import run_bugsinpy

    run_bugsinpy(args.bugsinpy, args.work, args.bugs,
                 [s.strip() for s in args.strategies.split(",") if s.strip()],
                 args.out, timeout=args.timeout, policy=args.policy,
                 policies=[p.strip() for p in (args.policies or "").split(",") if p.strip()],
                 assertion_weight=args.assertion_weight, repeat_discount=args.repeat_discount)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="qdebug", description="Question-guided algorithmic debugger for pytest")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rank", help="rank functions and lines by Ochiai suspiciousness")
    p.add_argument("--project", required=True)
    p.add_argument("--limit", type=int, default=15)
    add_run_options(p)
    p.set_defaults(func=cmd_rank)

    p = sub.add_parser("debug", help="debug one failing test interactively or with a simulated oracle")
    p.add_argument("--project", required=True)
    p.add_argument("--test", help="node id of the failing test (default: the first failing test)")
    p.add_argument("--oracle", choices=["human", "truth", "llm"], default="human")
    p.add_argument("--fixed", help="path to the correct project (for --oracle truth)")
    p.add_argument("--strategy", choices=["infogain", "infogain-full", "topdown", "divide"],
                   default="infogain")
    p.add_argument("--tiers", default=",".join(map(str, DEFAULT_TIERS)))
    p.add_argument("--error-rate", type=float, default=0.1, help="assumed oracle error rate ε")
    p.add_argument("--noise", type=float, default=0.0, help="flip probability for a NoisyOracle wrapper")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--budget", type=int, default=30)
    p.add_argument("--threshold", type=float, default=0.9)
    p.add_argument("--stop-level", choices=["function", "node"], default="function")
    p.add_argument("--max-repr", type=int, default=300)
    p.add_argument("--no-zoom", action="store_true")
    p.add_argument("--no-inadmissible", action="store_true",
                   help="treat 'inputs are already wrong' answers as plain 'unknown'")
    p.add_argument("--ascii", action="store_true", help="ASCII-only tree markers")
    p.add_argument("--plain", action="store_true", help="plain text output instead of the friendly interface")
    p.add_argument("--details", action="store_true", help="also print the full technical report")
    p.add_argument("--pause", type=float, default=0.0,
                   help="seconds to wait after each automatic answer, so an audience can follow")
    p.add_argument("--save-dir", default=".", help="where to write session_<timestamp>.json ('' to skip)")
    add_policy_options(p, default="tuned")
    add_run_options(p)
    p.set_defaults(func=cmd_debug)

    p = sub.add_parser("eval", help="batch experiments over the seeded bugs")
    p.add_argument("--bugs", default="bugs.json")
    p.add_argument("--fixed", default="sample_project")
    p.add_argument("--variants", default="variants")
    p.add_argument("--strategies", default="infogain,topdown,divide")
    p.add_argument("--noise", default="0.0,0.1,0.2")
    p.add_argument("--seeds", type=int, default=10)
    p.add_argument("--tiers", default=",".join(map(str, DEFAULT_TIERS)))
    p.add_argument("--error-rate", type=float, default=0.1)
    p.add_argument("--budget", type=int, default=30)
    p.add_argument("--out", default="results")
    p.add_argument("--policy", choices=sorted(POLICIES), default="baseline")
    p.set_defaults(func=cmd_eval)

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
    args = build_parser().parse_args(argv)
    return args.func(args)
