# qdebug

**Find the line behind a failing pytest test by answering yes/no questions — yourself, or with Claude.**

qdebug runs your tests, records the failing test as a tree of function calls, and shows you one call at a
time: *given these inputs, is this output right?* Each answer rules out as much of the program as possible.
When it knows which call is wrong, it replays that call and asks about its variables part-way through,
until it can point at a line. You never have to read the code to answer.

```text
$ qdebug debug --project benchmarks/shop/variants/bug_01      (abridged)

┌─ The failing test ──────────────────────────────────────────────────────────────────────┐
│ tests/test_pricing.py::test_line_total_bulk                                             │
│ AssertionError: assert 1890 == 1791                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
┌─ Question 1 ────────────────────────────────────────────────────────────────────────────┐
│ Bulk discount rate: 10% from 10 units, 5% from 5 units, otherwise none.                 │
│ quantity_discount_rate was called with:                                                 │
│ quantity  10                                                                            │
│                                                                                         │
│ and it returned:                                                                        │
│ 0.05                                                                                    │
└──────────────────────────────────────────────────────────────────── shop/pricing.py:22 ─┘
  Is that the right result? (y yes, n no, ? not sure, h more) > n
  ... two questions about its variables ...
┌─ Found it ──────────────────────────────────────────────────────────────────────────────┐
│ shop/pricing.py, line 24, in quantity_discount_rate                                     │
│                                                                                         │
│ 22    def quantity_discount_rate(quantity):                                             │
│ 23        """Bulk discount rate: 10% from 10 units, 5% from 5 units, otherwise none.""" │
│ 24 >>     if quantity > 10:                                                             │
│ 25            return 0.10                                                               │
│ 26        if quantity >= 5:                                                             │
│                                                                                         │
│ Confidence: High   Your answers point directly at this code.                            │
│ The bad call: quantity_discount_rate(quantity=10) → 0.05                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘
3 questions to search a project with 39 functions, without reading its code.
```

With an Anthropic API key, Claude can answer the questions for you, answer only the ones it is sure about,
pick search rules that suit the kind of bug, and explain what went wrong with a suggested fix. None of that is
required: by hand, qdebug needs only pytest.

## Install

```bash
pip install qdebug            # by hand: needs only pytest and rich
pip install "qdebug[ai]"      # adds the Anthropic SDK for the Claude features
```

Python 3.10+. The project you debug can run on its own interpreter (`--python`), down to Python 3.8.

## Use it

```bash
cd your-project
qdebug debug                          # you answer the questions
qdebug debug --oracle hybrid          # Claude answers when it is sure, you otherwise
qdebug debug --oracle claude          # Claude answers everything
qdebug debug --ai                     # you answer; Claude triages and explains
qdebug rank                           # just the suspiciousness ranking, no questions
```

When several tests fail, qdebug picks the one that runs the least project code (it needs the fewest
questions); `--test NODEID` picks one yourself.

**Answering.** For a call: `y` right, `n` wrong, `?` not sure, `i` the *inputs* are already wrong,
`t` trust this function from now on, `s` show its source, `e` how it behaved in passing tests, `w` why this
question, `tree` the calls so far, `u` undo, `q` stop and report. For a line: `y`, `n`, `?`, `s`, `u`, `q`. A wrong answer is not fatal:
qdebug treats every answer as evidence that may be mistaken, and double-checks its conclusion before
reporting it.

Each session is saved to `.qdebug/sessions/session_<time>.json` in the project (`--save-dir ''` to skip);
`--details` also prints the full technical report.

## Using Claude

Set `ANTHROPIC_API_KEY` (or run `ant auth login`) and install the extra. The default model is
**Claude Haiku 5.5** (`claude-haiku-5-5`): fast and cheap, and a session takes a few dozen small requests.
Use `--ai-model` or `$QDEBUG_AI_MODEL` for another model, and `--ai-effort low|medium|high` to trade speed for
care (default `medium`).

| mode | who answers | what Claude adds |
|---|---|---|
| `--oracle human` (default) | you | nothing |
| `--oracle human --ai` | you | first look, explanation |
| `--oracle hybrid` | Claude when its confidence ≥ `--ai-confidence` (0.8), else you, with Claude's opinion shown | first look, explanation |
| `--oracle claude` | Claude | first look, explanation |

**First look (triage).** Before the questions, Claude reads the failing test, its error and the most
suspicious functions, and says whether this is a *crash*, a *wrong value* or a *state* bug (aliasing, an
in-place change, a cache, a mutable default...). Each kind switches on search rules that suit it — for
example, a state bug may have been caused by an earlier call in the test, so earlier calls stay in play
(see `BUG_PROFILES` in [`qdebug/tuning.py`](qdebug/tuning.py)). Claude also names up to three suspects,
which get twice the prior; the questions still check them. Without Claude, `--bug-kind` does the same.

**Answering.** Claude sees the call's signature, docstring, caller, inputs and outputs, the failing test,
calls of the same function from passing tests (the closest inputs first), and the answers so far — but not
the function's body, because a model shown the buggy code tends to explain the
bug away as intended (`--ai-source` shows it anyway). Its stated confidence is used: an unsure answer moves
the search less. It never counts for more than a person's answer.

**Explanation.** Once the line is found, Claude explains why it is wrong and suggests a fix.

**Your own prompt.** Everything Claude is told lives in one markdown file. Make a copy for your project and
edit it:

```bash
qdebug init-agent          # writes .qdebug/agent.md, read automatically from then on
```

Each `## section` you keep replaces the built-in one (`system`, `call`, `line`, `triage`, `explain`). Put
facts Claude cannot see in one call — units, invariants, which modules are reliable — under
`## project notes`. `--agent PATH` uses another file.

If Claude is unavailable (no SDK, no credentials, an unknown model), `--oracle claude` stops with a message
saying what to fix, and the other modes carry on with you answering.

## Real projects

```bash
qdebug debug --project ~/src/app --python ~/src/app/.venv
qdebug debug --project ~/src/site --python ~/src/site/.venv --pytest-arg=--ds=site.settings --suite tests/unit
```

* **Its environment.** `--python` takes an interpreter or virtualenv; only pytest has to be installed there.
  qdebug runs every traced test in a fresh subprocess with a private copy of the few modules it needs.
* **Its plugins** load as usual (`--no-plugin-autoload` to stop that). Plugins that would break tracing are
  neutralized when installed: pytest-xdist runs in-process, pytest-randomly gets a fixed seed, pytest-cov is
  switched off. `--pytest-arg` is added to every run; `--suite` restricts the coverage run.
* **Fixtures** are traced too: project code a fixture calls is part of the tree.
* **Big tests.** Calls beyond `--max-nodes` (20 000), `--max-repeat` (50 calls of one function under one
  caller) or `--max-depth` (60) are folded into their caller.
* **Values** are compared by a rendering that shows objects without a `__repr__` through their attributes,
  sorts sets, masks addresses, thread ids and temporary paths, and digests numpy arrays.
* **Determinism.** `random`, numpy and `tempfile` are seeded before every test (`--no-seed-random`), and every
  re-run is checked against the first; a test that takes another path is reported, not guessed at.
* **Any source.** Files are read through their coding cookie; Python 2 files, virtualenvs, `site-packages`,
  `build/` and `dist/` are skipped. On Python 3.12+ the coverage run uses `sys.monitoring` and costs about
  1.5× the untraced time.

Not handled: threads and async code (only the calling thread is traced; coroutines are transparent), code
installed outside the project directory, code that installs its own `sys.settrace`, and time or network
nondeterminism (detected, not fixed).

## How it works

qdebug combines **spectrum-based fault localization** (which code do failing tests run more than passing
ones?) with **algorithmic debugging** (Shapiro 1983: if a call's output is wrong but all of its callees'
outputs are right, the bug is in that call's own code), in the spirit of Enlighten (Li et al., ICSE 2018).

1. **Spectrum.** The whole suite runs once with coverage; each function gets an Ochiai suspiciousness score.
2. **Execution tree.** The failing test runs again, recording one node per call. Values (arguments before and
   after, return value or exception, variables shared with an enclosing function) are recorded only for the
   most suspicious 5% of functions at first; when the search needs more, the test is re-run at the next tier
   (10, 15, 25, 50, 100%).
3. **Belief.** For every call *b*, qdebug keeps the probability that the bug is in *b*'s own code. Priors come
   from the spectrum. Each answer is evidence with an error rate ε (0.1 by default), so one wrong answer
   cannot discard the right branch. "Inputs already wrong" means the bug ran *before* that call.
4. **Questions.** The next question is the call whose answer has the highest expected information gain,
   computed in closed form for all calls at once. The search stops when one function holds 90% of the
   belief, or when the top call is *certified* (judged wrong, every callee judged right).
5. **Lines.** The blamed call is replayed with its local variables recorded before every line, and a search
   over those checkpoints finds the line where the state first goes wrong. Like the call search, it keeps a
   probability over the candidate lines, so one wrong answer can be outvoted. If that line called another
   function, qdebug checks that callee as well.

### Search rules

`--policy tuned` (the default) adds conditional rules on top of that search; `--policy baseline` turns them
all off. Every rule came from a failure observed in the benchmarks; each is documented in
[`qdebug/tuning.py`](qdebug/tuning.py).

| rule | what it does | why |
|---|---|---|
| focus test | debug the failing test with the least project code | small trees need few questions |
| crash path | in a crash, raise the prior of the calls the exception passed through | the exception's origin is the likeliest place |
| fan-out | a wrong call with ≥ 5 unjudged callees goes to the line search | log₂(lines) questions instead of one per callee |
| settle leader | once the top suspect is wrong, ask its few remaining callees | lets the certificate stop fire early |
| evidence stop | "confident" needs a "no" about the blamed function | a function called 28 times can reach 90% unasked |
| exclude tests | test code is never reported as the bug | |
| assertion weight | calls before the previous passing assertion get 5% of their prior | they passed a check already |
| fallback | a search that ends without evidence reports SBFL's best function, labelled low confidence | |
| Bayesian line search | weigh answers about variables instead of trusting each one | one wrong answer no longer sends the line search into the wrong half |

## Results

Two benchmark suites of seeded single-line bugs, each a correct project plus edits listed in `bugs.json`.
Sessions use the simulated *ground-truth oracle*, which answers by comparing every call with the same call in
the correct project — a stand-in for a careful person. `qdebug eval` reproduces every table.

**planner** — 34 bugs of many kinds in a project-planning library: crashes (a missing `return`, a dict
changed while iterating, unbounded recursion behind a missed cycle, a crash inside a fixture), wrong values
(boundaries, swapped arguments, wrong attributes and methods, recursion, nested functions, rounding, a module
constant, a generator) and state (an accumulator, a shallow copy, a mutable default, a stale cache, a late-bound
closure). Noise 0, information-gain strategy:

| | function found | exact line found | questions (call + line) |
|---|---|---|---|
| original search (`--policy baseline`) | 33 / 34 | 28 / 34 | 7.0 + 4.1 |
| **current search (`--policy tuned`)** | **34 / 34** | **29 / 34** | **3.6 + 3.5** |
| current search, tuned for each bug's labelled kind (`--triage category`) | 34 / 34 | 29 / 34 | 3.4 + 3.5 |

| kind | bugs | function | line | questions |
|---|---|---|---|---|
| crash | 8 | 8 | 8 | 5.6 |
| wrong value | 20 | 20 | 18 | 7.0 |
| state | 6 | 6 | 3 | 9.7 |

The 5 lines it misses are the ones that cannot be named by watching code run: a module-level constant, a
generator body, a lambda, a mutable default argument (on the `def` line) and a shallow copy whose sharing is
invisible in the values it returns. For each, qdebug names the right function. Divide-and-query and top-down
find the same functions and lines with 8.3 and 9.2 questions.

Tuning the search for the bug's kind barely helps here (−0.2 questions), so the value of Claude's triage lies
mostly in its suspects, not in the profile it picks.

**shop** — the original 5 bugs (off-by-one, aliasing, a wrong branch, operation order in a 90-line function,
a masked fault), with the simulated oracle lying at 0, 10 and 20%:

| oracle lies | function found (before → now) | exact line found (before → now) | call questions (before → now) |
|---|---|---|---|
| 0% | 100% → 100% | 100% → 100% | 6.8 → 5.4 |
| 10% | 78% → 80% | 44% → 56% | 7.3 → 7.1 |
| 20% | 54% → 60% | 26% → 28% | 8.1 → 9.6 |

"Before" is version 0.1 with its default (baseline) search; 50 sessions per noise level. Re-running those
420 sessions with the current code, `--policy baseline` and the old settings (`--no-trace-setup`, and the
ground-truth oracle's old answer for calls missing from the fixed run) gives the same function and line in
all 420, and the same question counts in 414; in the other 6, all under noise, one line question became a
call question.

**Real bugs (BugsInPy).** On 80 real bugs from six projects (PySnooper, thefuck, tqdm, youtube-dl, httpie,
cookiecutter), version 0.1 found the buggy function for 50 and the line for 31, against 46 and 18 for the top
entry of an Ochiai ranking — about as good as reading the ranking's top three, not clearly better. It found
none of the 12 bugs whose failing test makes 100 calls or more. Details are in
[results/bugsinpy/summary.md](results/bugsinpy/summary.md); this study has not been re-run with the current
search.

Full tables: [results/planner](results/planner/summary.md), [results/shop](results/shop/summary.md),
[baseline](results/baseline/planner/summary.md), [per-kind tuning](results/perfect-triage/planner/summary.md).

## Measuring Claude

`qdebug eval-ai` runs Claude as the oracle on the benchmark suites and grades every answer it gives against
the ground truth. It reports whether the function and line were found, the questions asked (and in
`--oracle hybrid` mode how many a person would still have answered), Claude's accuracy on call and line
questions, its calibration (accuracy per stated-confidence band), whether triage picked the right bug kind
and named the buggy function, whether the suggested fix restores the original line, and the cost.

```bash
export ANTHROPIC_API_KEY=...
qdebug eval-ai --suite planner --bug p13-wrong-variable     # one bug first
qdebug eval-ai                                              # both suites, Haiku 5.5
qdebug eval-ai --oracle hybrid --ai-model claude-sonnet-5-5
```

Results go to `results/claude/<suite>/` (`ai_summary.md`, plus one CSV row per session and per question).
Without an API key, `--relay DIR` writes every request to a file instead, so that another agent (for
example a Claude Code subagent running `python -m qdebug.ai.relay next DIR/<suite>-<bug>`) can answer it.

**Haiku 5.5 on all 39 bugs** (through the relay, so without enforced structured outputs and without token
counts; details and caveats in [results/claude-haiku](results/claude-haiku/README.md)):

| | simulated perfect answerer | Haiku, before the fixes below | Haiku, after |
|---|---|---|---|
| buggy function found | 39 / 39 | 39 / 39 | 39 / 39 |
| true line in the region | 34 / 39 | 29 / 39 | **34 / 39** |
| questions per bug | 7.1 | 8.4 | 7.4 |
| answers right (call / line) | – | 92% / 91% | 92% / 95% |
| triage: right bug kind / buggy function among suspects | – | 90% / 97% | 90% / 95% |
| suggested fix restores the original line | – | 33 / 39 | 33 / 39 |

The first run's mistakes led to four changes: the line prompt now counts the returned value as part of the
state and does not judge a line by what it is about to do; when the end check of the line search
contradicts a surer answer about the call, the surer one wins; and examples from passing tests with the
same inputs are left out. Haiku also finds two lines the simulated answerer cannot (an aliased copy and a
late-bound lambda, which look the same when printed), and misses two it finds.

How qdebug weighs a model's stated confidence, and the line search, were tuned on a simulated model oracle:
see [results/simulated-oracle.md](results/simulated-oracle.md).

## Benchmarks and experiments

```bash
qdebug variants                                     # build and check every suite's buggy copies
qdebug eval --suite planner --strategies infogain --noise 0
qdebug eval --suite shop --noise 0.0,0.1,0.2 --seeds 10
qdebug eval --suite planner --triage category       # tune each bug for its labelled kind (a perfect triage)
qdebug debug --project benchmarks/shop/variants/bug_04 --oracle truth --fixed benchmarks/shop/project
qdebug bugsinpy --bugsinpy BugsInPy --work ../bip-work --bugs thefuck:1-5
```

A suite is a directory with `project/` (a correct pytest project) and `bugs.json` (each bug an `old` → `new`
edit that keeps the line count, with its function, buggy lines and category). Add your own and pass
`--suite DIR`. `--strategy` also offers `topdown` and `divide` (classic algorithmic debugging) and
`infogain-full` (no certificate stop) for comparison; `--noise` makes the simulated oracle lie at a rate.

## Repository layout

```
qdebug/
  cli.py         command line (qdebug debug | rank | init-agent | eval | variants | bugsinpy)
  session.py     the debugging session: tiers, questions, memoization, undo, zoom, fallback
  strategies.py  information gain (ours), top-down and divide-and-query
  belief.py      posterior over "the bug is in this call's own code", closed-form information gain
  tuning.py      the search rules, policies and bug-kind profiles
  zoom.py        the line-level search inside the blamed call
  oracles.py     human and ground-truth oracles, noise
  ai/            optional Claude integration: client, oracle, triage, explanation, agent.md
  runner.py      traced pytest runs in a subprocess (runner, plugin and tracer support Python 3.8+)
  plugin.py      the pytest plugin inside that subprocess
  tracer.py      coverage, execution-tree and line tracers; comparable value snapshots
  spectrum.py    per-test coverage and the static function index
  ranking.py     Ochiai scores and monitoring tiers
  tree.py        execution tree, call paths, rendering
  ui.py          the friendly terminal interface (rich)
  report.py      text report and session JSON
  suites.py      benchmark suites and their buggy variants
  evaluate.py    batch experiments; bugsinpy.py: the BugsInPy study
benchmarks/      shop (5 bugs) and planner (34 bugs), each project/ + bugs.json
results/         the tables below, as CSV and markdown
tests/           unit and end-to-end tests (pytest -m "not e2e" for the fast ones)
```

## Development

```bash
pip install -e ".[ai,dev]"
ruff check qdebug tests
pytest -m "not e2e"     # about 10 s
pytest                  # with the end-to-end runs on seeded bugs, about 3 min
```

## Limitations

* **One fault, deterministic tests.** qdebug assumes a single fault located in one function's own code, and a
  test that takes the same path on every run.
* **Infection must reach the caller's output.** A wrong value that is masked before the caller returns makes
  answers contradict each other; the error rate absorbs this, at the cost of confidence.
* **Not every bug lives on a line that runs.** A wrong default argument sits on the `def` line, a wrong
  module-level constant outside any call, a lambda or generator body inside its caller. qdebug then names
  the function that uses it, not the line.
* **Large failing runs.** On real projects qdebug is about as good as reading the top few entries of a
  suspiciousness ranking; a failing test with hundreds of calls can use up the question budget.
* **Value judgments by rendering.** Objects whose `repr` hides state, or changes between runs, cannot be judged
  reliably.
* **Claude was measured on seeded bugs only, through the relay, once.** The Haiku numbers come from
  Claude Code subagents answering qdebug's prompts, not from the API with structured outputs, on 39 small
  seeded bugs, in a single run per configuration. No cost was measured, and BugsInPy was not run with
  Claude.

## License

MIT
