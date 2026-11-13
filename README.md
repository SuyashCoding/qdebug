# qdebug: question-guided algorithmic debugging for pytest

`qdebug` is a low-fidelity research prototype for a graduate course on software testing and debugging.
When a pytest test fails, it combines **spectrum-based fault localization** with **algorithmic debugging**.
It asks an oracle (you, or a simulated oracle) questions of the form

> *given these inputs, is this call's output correct?*

and narrows down first to the buggy **function call**, then to the buggy **line(s)** inside it.
It uses only Python 3.10+, the standard library and pytest. Nothing in it calls an LLM or any network service.

```bash
python make_variants.py                       # build variants/bug_01 … bug_05 and check them
python -m qdebug rank  --project variants/bug_01
python -m qdebug debug --project variants/bug_04 --oracle human
python -m qdebug debug --project variants/bug_01 --oracle truth --fixed sample_project
python -m qdebug eval  --bugs bugs.json --fixed sample_project --strategies infogain,topdown,divide --noise 0.0,0.1,0.2 --seeds 10
python -m qdebug bugsinpy --bugsinpy BugsInPy --work ../bip-work --bugs thefuck:1-5   # real bugs, see below
pytest tests/                                  # unit + end-to-end tests of qdebug itself
```

To see what the real-repo work changed, old version against new on real youtube-dl bugs, follow [demo/DEMO.md](demo/DEMO.md).

## The idea

**Enlighten** (Li et al., ICSE 2018) showed that a developer's feedback can sharpen spectrum-based fault localization (SBFL).
It runs the suite, ranks code by suspiciousness, picks a suspicious method invocation, and asks the developer whether that invocation's input/output is correct.
It then re-weights its spectrum with the answer and repeats.
**Algorithmic debugging** (Shapiro 1983) is older and more structural.
It treats the failing run as a tree of calls and walks down from the wrong root.
If a call's output is wrong but every child's output is correct, the bug is in that call's own code.

qdebug keeps Enlighten's loop (SBFL first, then targeted questions about concrete invocations) and adds algorithmic debugging's structure.
It records the **execution tree** of the failing test: one node per call, not per static function.
It keeps a **Bayesian posterior** over "the bug is in node *b*'s own code".
Priors come from SBFL scores, and each answer is treated as *noisy* evidence.
The next question is the call whose answer has the highest **expected information gain**.
Values are recorded only for the most suspicious functions. When the search needs a value from an unmonitored call, the test is re-run with a larger monitored set.
Once a call is blamed, a second traced run snapshots that call's locals line by line, and a binary search over those checkpoints finds the buggy line.

### What goes beyond Enlighten (the 8 required features)

| # | Feature | Where |
|---|---|---|
| 1 | Execution tree of individual calls + the algorithmic-debugging stopping rule (wrong output, all children correct ⇒ bug in that call). The rule is built into the belief model's likelihood and into the classic strategies. | `tracer.py` (tree mode), `tree.py`, `belief.py` |
| 2 | Bayesian soft updates with oracle error rate ε instead of hard pruning, so one wrong answer cannot discard the branch that holds the bug | `belief.py` |
| 3 | Information-gain question selection with SBFL priors, compared with classic top-down and divide-and-query | `strategies.py` |
| 4 | Tiered selective monitoring (5/10/15/25/50/100 % of functions), with escalation when the search needs opaque calls | `ranking.py` (tiers), `session.py`, `strategies.py` |
| 5 | Sub-function "zoom-in": locals snapshot at every line of one call, then binary search over the checkpoints | `tracer.py` (zoom mode), `zoom.py` |
| 6 | A call's output = return value or exception **plus mutations of its arguments** (including `self.__dict__`) | `tracer.py`, `tree.Node.output_key` |
| 7 | Answer reuse: memoization of identical (function, inputs, output) triples, and "trust this function" | `session.effective_answers` |
| 8 | ASCII hypothesis tree with status markers and posterior % per call | `tree.render_tree` |

### Extensions I added along the way (and why)

These came out of the experiments. Each one is documented in its module, and each fixed a concrete failure observed in `eval`.

* **"Inadmissible" answers** (Naish's three-valued debugging). `i` in the human oracle means *"I can't judge the output, the inputs are already wrong"*.
  The ground-truth oracle still answers "can't judge" whenever the inputs differ from the fixed run, as specified, but it gives this reason.
  It is evidence that the fault ran *before* this call, i.e. in a node with a smaller pre-order id.
  Without it, bug_04 is a coin flip: `build_invoice` and the `compute_tax` call it feeds wrong inputs to end up with identical posteriors.
  `--no-inadmissible` turns this off and gives the pure "unknown carries no evidence" behaviour.
* **Results ranked by call posterior, not by function sums.** Every answered call keeps an ε-sized residual, so summing per function favours functions that are simply called often (`round_cents`, `Catalog.get`).
  Function-level sums are used only for the stopping rule (`--stop-level function`, the default). A function is reported first only when it is confidently above the threshold, e.g. three `zone_for` calls in bug_03.
* **Certificate stop.** With ε = 0.1, the 0.9 posterior threshold is usually unreachable: every answered call keeps an ε-sized residual, and a wrong call with 16 children leaves 16 residuals.
  InfoGain therefore also stops when the top-posterior call satisfies the algorithmic-debugging rule: it was judged wrong, and every child was judged correct or inadmissible.
  At noise 0 this halves InfoGain's questions (13.6 → 6.8) at no cost in accuracy. The `infogain-full` strategy is the ablation without it.
* **Zoom refutations are evidence, and the search resumes.** A refuted zoom is itself an answer about the call: "end state correct" is logged as `yes` on that call, and "entry state wrong" as `inadmissible`.
  The strategy then resumes, possibly asking more questions, before the next untried top candidate is zoomed (up to 4 rounds).
  This applies to all three strategies. It is what lets the certificate stop survive noise: a lie that certifies the wrong call is usually caught by the zoom's end-state check.
* **Escalation only when it can help.** Besides "more than 50 % of the posterior is in opaque calls", a low best gain triggers a re-run only if some *opaque* call would have gain ≥ the threshold.
  Gains can be computed without values. Without this, every session ran up to 100 % monitoring for nothing.
* **Zoom checks the end state, then descends into implicated callees.** The zoom phase always asks whether the call's final state is wrong, an independent check of the call-level answer.
  If the binary search shows the state going wrong across a line that *calls a child*, the zoom also checks that child, even if the child was answered "correct".
  Under noise, these two checks are what recover from a lie on the decisive question.
* **Alias-aware line snapshots.** Zoom snapshots also record which locals refer to the same mutable object.
  bug_02 (`remaining = lines` instead of `list(lines)`) produces equal `repr`s at the buggy line. Without alias groups the region is line 89 (the in-place `sort`), not the true line 88; I verified this.

## Install and run

Python 3.10+ and pytest. There is nothing to install: run from the repository root.

```bash
python make_variants.py          # creates variants/bug_XX and prints a summary table
python -m qdebug rank --project variants/bug_03
python -m qdebug debug --project variants/bug_04 --oracle human
```

`debug` options: `--test NODEID` (default: the first failing test), `--oracle human|truth`, `--fixed PATH` (needed for `truth`), `--strategy infogain|topdown|divide`, `--tiers 5,10,15,25,50,100`, `--error-rate 0.1` (ε of the belief model), `--noise 0.0` (wraps the oracle in a `NoisyOracle`), `--seed 0`, `--budget 30`, `--threshold 0.9`, `--no-zoom`, `--no-inadmissible`, `--ascii`, `--save-dir .` (where `session_<timestamp>.json` goes; `''` to skip).

`rank` and `debug` also take the project-environment options described in [Running on a real project](#running-on-a-real-project).

Human-oracle commands: `y` / `n` / `?` (don't know) / `i` (inputs already wrong) / `t` (trust this function) / `s` (show source) / `w` (why this question: information gain and top posteriors) / `tree` / `u` (undo) / `q` (quit and report).
Line-level questions take `y` / `n` / `?` / `s` / `u` / `q`.

### Example transcript (bug_04, interactive, abridged)

bug_04 computes tax on the pre-discount amount in the middle of the 90-line `build_invoice`.
The session is shown exactly as the tool prints it. The answers are what a careful human would give (here produced by consulting the fixed program). Repetitive questions are cut.

```text
$ python -m qdebug debug --project variants/bug_04 --oracle human
Debugging tests/test_invoice.py::test_invoice_with_percent_coupon with the infogain strategy (1 failing / 35 tests)
  ↑ escalating monitoring tier 5% -> 10% (91% of the posterior is in opaque calls); 45 calls, 4 monitored
  ↑ escalating monitoring tier 10% -> 15% (85% of the posterior is in opaque calls); 45 calls, 7 monitored
  ↑ escalating monitoring tier 15% -> 25% (77% of the posterior is in opaque calls); 45 calls, 11 monitored
  ↑ escalating monitoring tier 25% -> 50% (67% of the posterior is in opaque calls); 45 calls, 44 monitored

── Question 1  (tier 50%) ───────────────────────────────────
coupon_discount   [coupon_discount(coupon, items, catalog)]   shop/pricing.py:99
  """Discount in cents that coupon grants for the given cart items."""
  call path: test_invoice_with_percent_coupon/build_invoice#0/coupon_discount#0
  inputs:
    coupon     = Coupon(code='SAVE10', kind='percent', value=10, min_subtotal=0, categories=())
    items      = [LineItem(sku='BOOK-001', quantity=1, unit_price=3999), LineItem(sku='FOOD-001', quantity=1, unit_price=1899)]
    catalog    = Catalog(9 products)
  returned: 590
  mutated arguments: none
Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > w
  strategy: infogain
  expected information gain of this question: 0.409 bits (current entropy 5.425 bits)
  P(output wrong) = 0.247: a 'no' moves belief into its 11 call subtree, a 'yes' moves it out
  top hypotheses (bug in this call's own code):
      4.5%  test_invoice_with_percent_coupon/build_invoice#0/describe_coupon#0
      4.5%  test_invoice_with_percent_coupon/build_invoice#0/validate_coupon#0
      3.2%  test_invoice_with_percent_coupon/build_invoice#0/coupon_discount#0
  ...
Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > y

── Question 2  (tier 50%) ───────────────────────────────────
build_invoice   [build_invoice(cart, address, coupon=None, number='INV-0001')]   shop/invoice.py:51
  ...
  returned: Invoice(number='INV-0001', ..., subtotal=5898, discount=590, tax=160, shipping=899, total=6367, ...
Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > n

── Question 3  (tier 50%) ───────────────────────────────────
compute_tax   [compute_tax(amount, address)]   shop/pricing.py:124
  inputs:
    amount     = 3999
    address    = Address(name='Nia', country='US', region='NY', postal_code='')
  returned: 160
Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > tree
[✗] test_invoice_with_percent_coupon(…)                                                        0.0%
  [ ] Cart.add(sku='BOOK-001', quantity=1) ×2                                                  0.3%
  [✗] build_invoice(cart=Cart([LineItem(sku='B..., address=Address(name='Nia'...) → Invoice(...   3.6%
    [ ] Catalog.__contains__(sku='BOOK-001') → True                                            3.8%
    [ ] validate_coupon(coupon=Coupon(code='SAVE10',...) → None                                6.6%
    [✓] coupon_discount(coupon=Coupon(code='SAVE10',..., items=[LineItem(sku='BOO...) → 590    0.5%
    [ ] compute_tax(amount=3999, address=Address(name='Nia', c...) → 160                       3.6%
  ...
Is this output correct for these inputs? [y/n/?/i/t/s/w/tree/u/q/h] > i       # 3999 is the pre-discount amount: inputs already wrong

  ... 18 more questions about build_invoice's other children (all y): the certificate stop then fires ...

── Line question 2 ────────────────────────────────────────
Inside build_invoice  (shop/invoice.py)  call path: test_invoice_with_percent_coupon/build_invoice#0
State just BEFORE line 97 runs (visit #1):
      96 |     # ---- 3. discounts --------------------------------------------------
  ->  97 |     discount = 0
      98 |     if coupon is not None:
  locals:
    subtotal           = 5898
    taxable_subtotal   = 3999
    ...
Is this state correct? [y/n/?/s/u/q/h] > y
  ... 5 more line questions ...

Buggy call found:
  function : shop/invoice.py::build_invoice  (line 51)
  call path: test_invoice_with_percent_coupon/build_invoice#0
  posterior: call 32.8%, function 32.8%
Line-level zoom:
  localized       test_invoice_with_percent_coupon/build_invoice#0  (7 questions, 71 checkpoints)
  region (1 line(s)) in shop/invoice.py:
    line  114  ochiai 0.333  tax = compute_tax(taxable_subtotal, address)
Questions: 21 function-level, 7 line-level
```

The full report also lists the SBFL ranking, the posterior top 5, the Q&A transcript, the tiers used with node counts and traced vs untraced times, and the final tree.
Everything is saved to `session_<timestamp>.json`.

## Running on a real project

`--project` can be any pytest project, not only the sample.
The traced runs adapt to it as follows. Each option works with `rank` and `debug`.

```bash
python -m qdebug debug --project ~/src/myapp --python ~/src/myapp/.venv --oracle human
python -m qdebug debug --project ~/src/site --python ~/src/site/.venv --pytest-arg=--ds=site.settings --suite tests/unit
```

* **The project's own environment.** `--python` takes an interpreter or a virtualenv directory, so the project's dependencies import. qdebug is not installed there: it is put on `PYTHONPATH`, and only pytest has to be installed in that environment.
* **Its pytest plugins.** Installed plugins (pytest-django, pytest-asyncio, ...) are loaded, and `--no-plugin-autoload` turns that off.
  Plugins that would break tracing are neutralized, but only when they are installed: pytest-xdist runs in-process (`-n 0`), pytest-randomly gets `--randomly-seed=0`, and pytest-cov gets `--no-cov`.
  `--pytest-arg ARG` (repeatable) is added to every run. `--suite PATH` (repeatable) restricts the whole-suite coverage run.
  The coverage run continues past collection errors. A pytest usage error, an internal error or an empty collection is reported, never treated as "no failing test".
* **Fast coverage.** On Python 3.12+ the coverage run uses `sys.monitoring`. Each line reports once per test and is then disabled, as in coverage.py.
  It gives exactly the same lines and functions as `sys.settrace` on all six sample projects and on the fixture (tested). On the fixture's hot loop it costs 1.5× the untraced time instead of 9× (8.9 vs 52.6 ms, untraced 5.8 ms). Use `--spectrum-backend settrace` to compare.
* **Any source file.** The function index reads files through their PEP 263 coding cookie, skips files that do not decode or compile (Python 2 scripts, null bytes), and skips every directory that holds a `pyvenv.cfg` (a virtualenv, whatever its name).
  It also skips `site-packages`, `*.egg-info`, hidden directories, and top-level `build/`, `dist/` and `htmlcov/`.
* **Bounded execution trees.** A call beyond `--max-nodes` (20000), `--max-repeat` (50 calls of one function under one caller) or `--max-depth` (60) is *folded*: its lines and callees count as its nearest recorded caller's own code.
  A recorded call keeps the same path id as without folding, so zoom and the ground-truth oracle still match calls. The session prints how many calls each limit folded.
* **Values that real classes can be compared by.** Most classes have no `__repr__`, so `repr` shows only a (masked) address and any two instances compare equal.
  Snapshots therefore render such objects from their attributes (`__dict__` and `__slots__`), recurse into built-in containers, sort set elements, guard against cycles, stop at 100 000 characters, and add a SHA-1 of the full data to numpy arrays (whose repr elides the middle).
  Arguments are rendered at call time instead of being deep-copied, since sessions, connections or locks often cannot be copied.
* **Old Pythons and old pytest.** The code that runs inside the project's interpreter (`runner.py`, `plugin.py`, `tracer.py`) works on Python 3.8+ and pytest 3.2+.
  Before 3.11 there is no `code.co_qualname`, so qualified names (`Account.withdraw`, `outer.<locals>.inner`) are rebuilt from the source's syntax tree. For pytest older than 3.5, `--rootdir` is left out.
  Class test ids of pytest < 4 (`file::Class::()::test`) are normalized. With autoload off, every installed plugin is also blocked by name (`-p no:NAME`), because old pytest ignores `PYTEST_DISABLE_PLUGIN_AUTOLOAD`.
  `--pythonpath DIR` (repeatable, relative to the project) adds import paths, e.g. `--pythonpath src` for a src layout whose pytest predates the `pythonpath` ini option.
* **Determinism.** `random` (and numpy's global generator, if loaded) is seeded before every test, and so is the private generator behind `tempfile`'s random names (`mkdtemp`, `NamedTemporaryFile`). `--no-seed-random` turns this off.
  Every tier re-run is checked against the previous run's call structure. If the test took a different path, qdebug stops and names the first differing call, because answers are keyed by call path ids.
* **Paths that differ between runs.** Each run gets its own pytest `--basetemp`. The project directory and that basetemp are replaced by `<project>` and `<basetemp>` in every snapshot (as written, repr-escaped and with forward slashes).
  Without this, a value holding a filename never compares equal between the buggy and the fixed checkout.
* **Clear failures.** Collection errors are reported first, not buried under pytest's warnings. A test that fails before its body runs any project code (in a fixture, a decorator or `mock.patch`) is reported as such. `--test` accepts a parametrized test's base name and picks its first failing case.

`tests/fixtures/realistic_project` exercises all of this. It is a src-layout package with a Latin-1 module, a Python 2 script, a virtualenv directory, `__slots__` classes without `__repr__`, `random`, a 365-day loop and a hot loop.
`tests/test_realworld.py` plants a one-line bug in a copy of it (`Account.withdraw` forgets the fee) and checks that qdebug finds the call and the line.
The version before these changes crashes on the Latin-1 file. Given UTF-8 copies, it blames `transfer` after 9 questions, because every `Account` printed as `<ledger.accounts.Account object at 0x?>`. Now it takes 3 call questions and 3 line questions, and the region is exactly `accounts.py:25`.
On the sample project nothing changed: all 420 evaluation sessions give the same results, apart from timings.

Not handled yet: async code and threads (coroutine frames are transparent, and `sys.settrace` only traces the calling thread), packages installed outside the project directory (they are not traced), code under test that installs its own `sys.settrace` (debuggers, PySnooper), and time or network nondeterminism (detected, not fixed).

## Architecture

```
qdebug/
  cli.py        argparse entry point (python -m qdebug rank|debug|eval)
  runner.py     subprocess entry (python -m qdebug.runner) + invoke(); RunOptions (interpreter, plugins, limits)
  plugin.py     pytest plugin: wraps only pytest_runtest_call, records outcomes
  tracer.py     tracers: spectrum (settrace or sys.monitoring) / tree (bounded) / zoom, value snapshots
  spectrum.py   per-test coverage, static function index (signature, docstring, source)
  ranking.py    Ochiai for lines and functions, monitoring tiers
  tree.py       Node, ExecutionTree, call path ids, ASCII rendering
  belief.py     posterior over "bug in node b's own code", closed-form information gain
  strategies.py InfoGainStrategy (ours), TopDownStrategy, DivideAndQueryStrategy
  oracles.py    Oracle interface, HumanOracle, GroundTruthOracle, NoisyOracle, LLMOracle stub
  session.py    main loop, tier escalation, memoization, trust, undo, zoom orchestration
  zoom.py       line-level localization inside the blamed call
  report.py     text report + session JSON
  evaluate.py   batch experiments (results/results.csv, results/summary.md)
  bugsinpy.py   evaluation on BugsInPy real bugs (results/bugsinpy/)
sample_project/ correct order-processing library (shop/) + 35 pytest tests
bugs.json       5 seeded, line-count-preserving bugs with ground-truth locations
make_variants.py
tests/          unit tests + end-to-end tests of qdebug (fixtures/realistic_project: real-repo hazards)
```

Every traced execution runs in a fresh subprocess (`python -m qdebug.runner`) with `PYTHONHASHSEED=0`, so module caches never mix the buggy and the fixed copy, and set/dict reprs are stable.
Only files under the project directory are traced (never the stdlib, site-packages or qdebug). The test function is the root.
Generator expressions and lambdas are *transparent*: they are not nodes, and their lines count towards the enclosing call.
A **call path id** such as `test_x/build_invoice#0/line_total#1` is the parent's id plus `qualname#k`, where *k* counts earlier calls of the same qualname under the same parent.
It matches the same call across tier re-runs and between the buggy and the fixed program.

### Belief model in one paragraph

Hypotheses: H_b = "the bug is in b's own code", for every node b, including unmonitored ones.
Prior: P(H_b) ∝ 0.01 + Ochiai(function of b), plus a 10⁻³ tie-break on the function's best line score.
Under H_b, the output of node q is wrong iff b is in q's subtree.
A yes/no answer has likelihood 1 − ε when it is consistent with H_b and ε otherwise. "Unknown" has no effect, and "inadmissible" is consistent iff b started before q.
The posterior is recomputed from the full answer set after every answer, using range updates over the pre-order numbering, which makes undo trivial.
The expected information gain of asking q has a closed form in the subtree sums of p and p·ln p, so all candidates are scored in O(n).
InfoGain asks the best monitored, unanswered call. It escalates when more than 50 % of the posterior sits in opaque calls (or the best gain is below 0.01 bits while an opaque call would do better).
It stops when one function holds ≥ 90 % of the posterior, when the top call has an algorithmic-debugging certificate, when no question is worth ≥ 0.01 bits, or when the budget of 30 questions is used up.

## Sample project and seeded bugs

`sample_project/shop/` is a ~560-line order-processing library: `catalog.py`, `cart.py`, `pricing.py`, `shipping.py` and `invoice.py`.
`invoice.py` holds the deliberately long `build_invoice`, which has validate / subtotal / discounts / tax / shipping / totals sections.
Calls nest 4 deep (test → `build_invoice` → `line_total` → `quantity_discount_rate`).
Everything is integer cents and grams, with deterministic dataclass reprs.
The 35 tests pass on the correct version. Each bug in `bugs.json` is a single-line, line-count-preserving edit.

| bug | kind | function | line | failing tests |
|---|---|---|---|---|
| bug_01 | off-by-one comparison in a deep helper (`>` instead of `>=` for the 10-unit discount) | `quantity_discount_rate` | pricing.py:24 | 2 |
| bug_02 | side effect: aliasing (`remaining = lines`) makes an in-place sort reorder the caller's cart | `cheapest_units` | pricing.py:88 | 2 |
| bug_03 | wrong branch condition (`not in EU_COUNTRIES`): EU ⇄ international zones | `zone_for` | shipping.py:41 | 4 |
| bug_04 | wrong operation order in the middle of `build_invoice`: tax before discount | `build_invoice` | invoice.py:114 | 1 |
| bug_05 | masked fault: `total_weight` ignores quantities; only visible when the wrong weight changes the paid shipping tier | `Cart.total_weight` | cart.py:80 | 1 |

bug_05 shows masking in two places.
`test_total_weight_single_units` uses quantity 1, so it passes.
`test_free_shipping_hides_weight` has a wrong weight that free shipping hides, so it also passes.
Only `test_heavy_remote_invoice` crosses a tier boundary and fails.

## Results

Full tables are in [results/summary.md](results/summary.md) (per-run rows in `results/results.csv`). They come from:

```bash
python -m qdebug eval --bugs bugs.json --fixed sample_project \
    --strategies infogain,infogain-full,topdown,divide --noise 0.0,0.1,0.2 --seeds 10
```

This is 420 sessions with the GroundTruthOracle, wrapped in a `NoisyOracle` when noise > 0, and assumed ε = 0.1. It takes about 2 minutes, because each distinct traced run is executed once and cached.
`infogain-full` is the ablation without the certificate stop.

| strategy | noise | function found | function-level Q | line-level Q | true line in region | final tier |
|---|---|---|---|---|---|---|
| **infogain** | 0.0 | 100% | 6.8 | 3.8 | 100% | 37% |
| infogain-full | 0.0 | 100% | 13.6 | 3.8 | 100% | 52% |
| topdown | 0.0 | 100% | 11.8 | 3.8 | 100% | 60% |
| divide | 0.0 | 100% | **5.4** | 3.8 | 100% | 24% |
| **infogain** | 0.1 | 78% | 7.3 | 4.5 | 44% | 38% |
| infogain-full | 0.1 | 78% | 14.5 | 4.6 | 54% | 51% |
| topdown | 0.1 | 52% | 11.0 | 4.7 | 42% | 58% |
| divide | 0.1 | **82%** | 4.9 | 4.3 | 46% | 23% |
| **infogain** | 0.2 | 54% | 8.1 | 4.4 | 26% | 42% |
| infogain-full | 0.2 | **62%** | 14.9 | 4.3 | 32% | 53% |
| topdown | 0.2 | 28% | 8.4 | 3.8 | 18% | 59% |
| divide | 0.2 | 52% | 6.5 | 4.6 | 30% | 31% |

Per bug, noise 0 (function-level + line-level questions; every strategy finds every buggy function and its line, with a 1-line region):

| bug | SBFL rank: function / line | infogain | infogain-full | topdown | divide |
|---|---|---|---|---|---|
| bug_01 `quantity_discount_rate` | 3 / 9 | 2+2 | 6+2 | 6+2 | 2+2 |
| bug_02 `cheapest_units` | 2 / 12 | 3+4 | 18+4 | 17+4 | 1+4 |
| bug_03 `zone_for` | 1 / 1 | 2+3 | 3+3 | 9+3 | 2+3 |
| bug_04 `build_invoice` | 7 / 49 | 21+7 | 25+7 | 19+7 | 17+7 |
| bug_05 `Cart.total_weight` | 4 / 62 | 6+3 | 16+3 | 8+3 | 5+3 |

What I take from this:

* **Without noise, every strategy localizes every bug to the exact line.** This includes the masked bug_05 and the long-function bug_04.
  Plain SBFL ranks those two buggy lines 62nd and 49th. Line-level zoom needs 2–7 questions even for `build_invoice`'s 71 checkpoints.
* **Divide-and-query is the most question-efficient strategy here, and InfoGain is close behind** (5.4 vs 6.8). Tiered monitoring helps divide a lot.
  At the 5–10% tiers only the top SBFL functions are monitored, so divide's first askable call is often the buggy one: bug_02 takes 1 question.
  InfoGain follows the required ">50% of the posterior in opaque calls ⇒ escalate" rule, so it escalates to 25–50% before asking anything and loses that shortcut.
* **Hard pruning top-down collapses under noise** (52% at 0.1, 28% at 0.2). Any lie on the path to the bug is fatal.
* **Soft updates pay off only at higher noise, and only if allowed to ask more.** `infogain-full` reaches 62% at noise 0.2, against 52–54% for the others, at roughly twice the questions.
  At noise 0.1 the differences between infogain, infogain-full and divide (78–82%) are within sampling error: with 50 runs, one standard error is about 6 points.
  Divide stays robust mainly because it asks few questions (fewer chances to be lied to), and because a refuted zoom resumes its search.
* **Under noise, line-level hits drop to 26–54% for every strategy.** The zoom's binary search makes hard decisions, and the line questions are noisy too.
  bug_04 is hardest for everyone, because blaming `build_invoice` requires clearing all 16 of its children, and every one of those answers can be a lie.
* **Tracing cost.** The failing test call takes about 0.2 ms untraced and 3–6 ms traced (15–30×). Monitoring more functions adds only about 10–50% on this tiny project, because recording the structure (line events in every project frame) dominates.
  Wall time is dominated by subprocess and pytest start-up (about 0.35 s per traced run).

The required end-to-end check, `debug --oracle truth --strategy infogain --noise 0`, finds the buggy function for all 5 bugs, and puts the true line in the reported region for all 5.
For bug_02 this depends on alias-aware snapshots. With `repr` comparison alone, the region would be line 89 instead of 88, because `remaining = lines` and `list(lines)` print the same.

## Results on real bugs (BugsInPy)

The seeded bugs above were written for qdebug. [BugsInPy](https://github.com/soarsmu/BugsInPy) (Widyasari et al., ESEC/FSE 2020) has real bugs from real Python projects, each with a buggy commit, a fixed commit and the tests that expose it.
`python -m qdebug bugsinpy` runs qdebug on them. For every bug it follows BugsInPy's own checkout procedure (the buggy commit plus the fix commit's test files), builds a virtualenv with uv from the bug's pinned requirements, checks that the failing tests fail on the buggy version and pass on the fixed one, takes the ground truth from `bug_patch.txt`, and debugs with the GroundTruthOracle at noise 0.
The module docstring of `qdebug/bugsinpy.py` lists every step and deviation.

```bash
git clone https://github.com/soarsmu/BugsInPy
python -m qdebug bugsinpy --bugsinpy BugsInPy --work ../bip-work \
    --bugs PySnooper,thefuck,tqdm,youtube-dl,httpie,cookiecutter --strategies infogain,divide,topdown
```

All 96 bugs of six projects were run on Windows with Python 3.8 (the oldest uv provides; BugsInPy asks for 3.6–3.8). The debugging sessions of all three strategies took 22 minutes in total, plus checkouts and environment setup. Full tables are in [results/bugsinpy/summary.md](results/bugsinpy/summary.md).

| outcome | bugs |
|---|---|
| completed session | 80 |
| test does not reach project code on the buggy version (it imports or mocks a name the fix adds) | 6 |
| nondeterministic (tqdm 1: `format_meter` branches on elapsed time) | 1 |
| not reproducible here (7 thefuck tests pass on the buggy version; thefuck 11 and cookiecutter 3 fail on the fixed one; not investigated further) | 9 |

On the 80 completed sessions (infogain; divide and topdown are within 2 bugs of it):

| | qdebug | SBFL top-1 | SBFL top-3 | SBFL top-5 |
|---|---|---|---|---|
| buggy function | **50** (62%) | 46 | 58 | 60 |
| buggy line | **31** (39%), region 1.6 lines | 18 | 30 | 39 |

SBFL is Ochiai on the same spectrum, so "top-3" means a developer reads the three most suspicious entries.
When qdebug finds the function, it needs a median of 2 call questions and 4 line questions.

What this says, honestly:

* **On real bugs qdebug is about as good as reading SBFL's first few entries, not clearly better.** It names the right function slightly more often than SBFL's top-1 (50 vs 46), and the right line about as often as SBFL's top-3 (31 vs 30). It is not a replacement for a ranked list.
  It wins on 15 of the 34 bugs where SBFL does not rank the buggy function first, and it loses 11 of the 46 where SBFL does.
* **It does not scale to large failing runs yet.** It finds 50 of the 68 bugs whose failing test makes fewer than 100 calls, and none of the 12 with 100 or more (up to 1 685 calls, mostly youtube-dl's `test_YoutubeDL`). Eight of those use up the 30-question budget.
  That is the fan-out problem bug_04 already showed, at real scale. It is the clearest argument for Enlighten-style dependence information: only the calls whose values flow into the wrong output are worth asking about.
* **The other misses:** 14 sessions blame another function; I have not yet classified why. 4 blame the test function itself (three of these trees have only 1–4 calls). 2 are PySnooper, whose tests install their own `sys.settrace` and replace qdebug's tracer. 2 have fixes outside any function, which a function-level answer cannot name.
* **Line-level misses are partly a scoring artefact.** A fix inside a lambda (youtube-dl 1) is localized to the line that calls the lambda, because lambdas are transparent. A fix that only adds lines is scored against the lines around the insertion.

The evaluation also found problems in qdebug itself, now fixed; the sample results above did not change.
Python 3.8 / old-pytest support, `--pythonpath`, and collection errors reported first came from setting the projects up.
Seeded `tempfile` names, `--basetemp` and path masking came from httpie, where every value holding a temporary config directory differed between the buggy and the fixed run, so the oracle blamed the test helper that created it.
A call check before zooming came from youtube-dl: when the search blames a function with several calls, qdebug now asks about the latest call before zooming into it (a test stops at its first failing assertion). It previously zoomed into the earliest calls, which were correct.
Together the last two raised infogain from 47 to 50 functions and from 24 to 31 lines on the same bugs.

## Search tuning: where to prune, cut and continue

`--policy baseline` is the search described above. `--policy tuned` adds conditional rules, all in `qdebug/tuning.py`, chosen from a classification of the 30 BugsInPy misses:

| rule | kind | what it does | why |
|---|---|---|---|
| fallback | cut | if the search stops on its budget or with nothing informative to ask, report the top SBFL function, labelled as a low-confidence guess | those stops were right 1 time in 18; confident or certified stops 49 in 62 |
| evidence_stop | cut | "confident" needs a "no" about the blamed function; its latest call is asked first | function mass is a sum over calls, so a callback called 28 times reached 96% before any question (youtube-dl 10) |
| exclude_tests | prune | test code is never the reported bug | 6 misses blamed the test or a test helper |
| assertion_weight = 0.05 | prune | calls made before the previous passing assertion of the test get 5% of their prior | they ran before an assertion that passed; youtube-dl's `test_match_filter` checks 12 filters in a row |
| repeat_discount | prune | each correct call of f scales f's other calls by 0.7 | **off by default**: on the seeded bugs at 10% noise it lost 4 of 50 sessions, because a wrong "yes" then discounts the buggy function |

Two tracer fixes came out of the same classification and apply to both policies: a unittest `setUp` no longer becomes the root of the tree (the test body was never recorded, httpie 5), and thread ids in lock and thread state are masked (they differ between runs, so the automatic oracle answered "wrong", tqdm).

Checks: with `--policy baseline` the seeded results are identical to the table above (315 of 315 sessions). With `--policy tuned` they are identical at noise 0 and slightly lower under noise (see `demo/DEMO_TODAY.md`). The real-bug numbers so far are in `demo/DEMO_TODAY.md`; they come from a partial run on the bugs the old version missed, then on bugs it found, and are not yet a full 80-bug rerun.

## Modeling assumptions

* **Deterministic tests.** Every re-run (tiers, zoom, the fixed program) must take the same path. qdebug aborts if the failing test stops failing.
* **A single fault per variant**, located in one function's own code.
* **Infection propagates to the caller's output.** Under H_b, every ancestor of b produces a wrong output.
  This is false under *failure masking*: a wrong intermediate value that does not change the caller's output, like bug_05's weight that stays in the same shipping tier.
  The noisy likelihood absorbs such contradictions instead of pruning on them. They still lower confidence, and they can mislead when masking is frequent.
* **Snapshot comparison by rendering.** Values are compared through their full rendering: `repr`, except that objects with only the default address repr are shown through their attributes (see [Running on a real project](#running-on-a-real-project)). Memory addresses are masked. Zoom also compares which locals alias each other.
  Objects whose custom `repr` hides state, or is nondeterministic, cannot be judged reliably.
* The per-node hypothesis space treats each *call* as a separate hypothesis. A buggy function that is called several times (bug_03: three `zone_for` calls) splits its mass across those calls. The function-level stopping rule compensates.

## Known limitations

* The confidence threshold is often unreachable with ε = 0.1, because each answered call keeps an ε-sized residual and a wrong call with many children leaves many residuals.
  The certificate stop works around this, but it reintroduces a structural (hard) decision. A lie can certify the wrong call, and only the zoom phase's checks catch that.
* A wrong call with high fan-out is expensive for every strategy: to blame `build_invoice` (bug_04), all 16 of its children must be cleared. Memoization only helps when calls repeat with identical values.
* Under the noise model, a lie on the single question that separates the buggy leaf from its parent is unrecoverable at the call level. Only the zoom phase's independent checks can repair it.
* Line-level search is a plain binary search (hard decisions) and assumes the state, once wrong, stays wrong. Noise on line questions hurts all strategies equally.
* The region is the statement(s) executed between the last correct and the first wrong checkpoint. A wrong *condition* is blamed on the line of the `if`, which is correct here, but a missing statement cannot be pointed at.
* Generators, threads and async code are not modelled (generator frames are transparent). Only one test is debugged at a time.
* `sys.settrace` is slow. Tree and zoom tracing make the failing test call roughly 15–30× slower here (milliseconds, see Results), which is why values are recorded only for monitored functions. Only the coverage run uses `sys.monitoring` so far.
* The ground-truth oracle judges a call by comparing it with the *same call path* in the fixed program. A call whose path differs (different control flow) is "unknown".

## Where an LLM oracle would plug in

`oracles.LLMOracle` is a documented stub that raises `NotImplementedError`. A real implementation would only need to provide `judge(question, ctx) -> Answer`.
The intended design is that the model sees the signature, the docstring, the caller's context, the concrete inputs/outputs (with argument mutations), and examples of the same function from *passing* tests.
It deliberately would **not** see the function body, so it cannot rationalize the buggy implementation.
Its calibrated confidence would map onto a per-answer error rate ε in `Belief`, which is the reason answers are already treated as noisy evidence.
Register it in `cli.make_oracle`.
