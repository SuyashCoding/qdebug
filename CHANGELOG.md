# Changelog

## Unreleased

- **Several failing tests, several bugs.** qdebug groups the failing tests by the bug that probably causes
  them (same crash location, or a rarely-passed line they all run) and shows the groups when you pick a test.
  The session ranks code against the chosen test's group only, so another bug's failures don't dilute it, and
  the result says which other failures the bug found probably explains and which need another session.
  `--no-group` turns it off; `qdebug rank` also prints the groups.
- `qdebug eval-groups` puts two seeded bugs into one project and measures the grouping, the ranking and full
  sessions with grouping on and off (`results/multi-bug/`). On 137 planner pairs the groups were exactly right
  for 88%, and the buggy function ranked first for 73% of bugs instead of 39%. Single-bug results are unchanged.

- The README demo is now a real bug in a real library: tqdm bug 4 from BugsInPy, vendored in
  `examples/tqdm` with a small stand-in for the `nose` helpers its 2019 tests import, so they run with
  pytest on Python 3.10+. qdebug finds the line the maintainers fixed in 7 questions.
- A `Dockerfile` runs qdebug (and the demo, by default) the same way on any computer. The README starts
  with the demo in Docker, shows every question with its answer the same way, and explains how to run
  qdebug on your own project, with or without Docker.
- CI replays the README's demo answers on Linux, Windows and macOS, and builds and runs the Docker image.

## 0.2.0

### Claude, optionally

- `qdebug debug --oracle claude` lets Claude answer every question; `--oracle hybrid` lets it answer
  the ones it is sure about (`--ai-confidence`, default 0.8) and asks you the rest, with its opinion
  shown as a hint. `--ai` keeps you answering but adds Claude's first look and explanation.
- Claude's first look (triage) classifies the bug as a crash, a wrong value or a state problem,
  which switches the search to rules tuned for that kind (`tuning.BUG_PROFILES`), and names up to
  three suspects, whose calls get twice the prior. `--bug-kind` does the same by hand.
- After the search, Claude explains the bug and suggests a fix.
- Claude's stated confidence weakens unsure answers in the belief model; it never makes an answer
  count for more than a person's.
- The prompt is a markdown file (`qdebug/ai/agent.md`). `qdebug init-agent` copies it to
  `.qdebug/agent.md` in your project, where each section can be rewritten and project facts added.
- The default model is `claude-haiku-5-5` (`--ai-model`, `$QDEBUG_AI_MODEL`). Without the
  `anthropic` package or credentials, qdebug says how to fix it; hybrid mode falls back to you.

- Questions about a call show Claude (and you, with `e`) calls of the same function from passing tests,
  the closest inputs first: the best evidence of what the function is meant to do.
- `qdebug eval-ai` measures Claude on the benchmark suites: results, Claude's agreement with the ground
  truth per question and by stated confidence (and which wrong answers actually point the search away from
  the bug), triage and fix accuracy, and cost. `--relay DIR` lets another agent answer the requests through
  files when there is no API key.
- Measured with Haiku 5.5 on all 39 bugs (results/claude-haiku): the buggy function every time, the line 34
  times out of 39 after these fixes from the first run: a returned value is part of the state at a
  return; a line is not judged by what it is about to do; the line search's end check no longer overrides
  a surer answer about the call; passing-test examples with the question's own inputs are left out.

### Search

- The line search weighs answers instead of trusting each one (`--zoom-search bayes`, in the tuned
  policy): one wrong answer about the variables is usually outvoted rather than fatal. See
  [results/simulated-oracle.md](results/simulated-oracle.md).
- Fixtures are traced: project code that a fixture calls is part of the execution tree, so bugs
  that surface during test setup can be found (`--no-trace-setup` for the old behaviour).
- New rules in the `tuned` policy (now the default for `eval` too): debug the failing test with the
  smallest tree first; follow the exception's path in a crash; go to the line search early when a
  wrong call has many callees; settle a wrong leading suspect by asking its callees.
- The line search records which calls each line made, so it descends into exactly the callee where
  the state went wrong, and asks a call question before looking inside an unjudged callee.
- Variables that a nested function shares with its enclosing function count as its inputs and
  outputs.
- The ground-truth oracle answers "inadmissible" for a call the fixed program never makes.

### Packaging and tooling

- `pip install qdebug` with a `qdebug` command; `pip install 'qdebug[ai]'` for Claude.
- Benchmarks are suites under `benchmarks/` (`project/` + `bugs.json`); `qdebug variants` builds and
  checks them. A second suite, `planner`, has 34 seeded bugs of many kinds.
- Session files go to `<project>/.qdebug/sessions/` by default.
- A beginner-friendly README: installation on Windows, macOS and Linux, a step-by-step demo answered by
  hand, and how to add a Claude API key. The full description moved to `docs/DETAILS.md`.
- Line questions now say plainly that being at a line a correct program would not reach counts as wrong.
- Lint (ruff), CI on Linux, Windows and macOS, and tests for every new rule and the AI code (a fake
  client, and the real SDK against a local stub server).

## 0.1.0

The research prototype: spectrum-based fault localization plus algorithmic debugging with a
Bayesian belief model, information-gain questions, tiered monitoring, line-level zoom, and the
evaluation on the seeded `shop` bugs and on BugsInPy.
