# Evaluation plan: qdebug on real bugs

Written on 2026-11-23, **before** running the study it describes, so the questions, data, metrics and
analysis can't be bent to fit the results afterwards. Anything changed after the run is listed at the end
under *Deviations*, with the reason.

## Why

qdebug's only real-bug result is from version 0.1 (80 BugsInPy bugs, 2026). Every improvement since then
(the tuned search rules, the Bayesian line search, grouping failing tests, Claude) was measured only on the
39 bugs we seeded ourselves, and the tuned rules were designed by looking at failures on those same bugs.
So we don't know whether they help on real code, or only on the code they were tuned on.

## Research questions

- **RQ1. Real bugs.** How often does qdebug name the buggy function and the buggy line on real bugs, and how
  does that compare with reading the top 1, 3 or 5 entries of a spectrum-based ranking (Ochiai, DStar) or the
  crash location?
- **RQ2. Progress since 0.1.** Do the tuned search rules (`--policy tuned`) beat the original search
  (`--policy baseline`) on real bugs, in bugs found and in questions asked?
- **RQ3. Generalization.** Do the answers to RQ1 and RQ2 hold on projects that were never used while
  developing qdebug?
- **RQ4. Wrong answers.** How much does accuracy drop when 10% or 20% of the answers are wrong?
- **RQ5. Where it fails.** Which bugs does it miss: large failing runs (100+ calls), bugs whose fix only
  inserts code (an omission), crashes vs wrong values?

## Data

[BugsInPy](https://github.com/soarsmu/BugsInPy) (Widyasari et al., ESEC/FSE 2020): real bugs from 17 Python
projects, each with the buggy commit, the fix and the tests that show it.

- **Development set:** the 6 projects of the 0.1 study (PySnooper, cookiecutter, httpie, thefuck, tqdm,
  youtube-dl; 96 bugs). We have seen these results, and tqdm bug 4 is the README demo.
- **Held-out set:** projects qdebug has never been run on: black, fastapi, luigi, sanic, tornado, scrapy
  (all their bugs). These are run **once**, after the code is frozen. No setting is changed after seeing them.

The projects left out (ansible, keras, matplotlib, pandas, spacy) need heavy native builds; they are left
out for cost, not because of results. The study runs in a Linux Docker container with Python 3.8+
(BugsInPy's bugs target 3.6–3.8; 3.8 is the oldest our tooling installs). A bug counts only if its failing
test fails on the buggy version and passes on the fixed one in that environment.

## What is run

For every reproduced bug, on its first failing test, with answers from the ground-truth oracle (each call
compared with the same call in the fixed version):

| setting | strategies | policies | noise (wrong answers) |
|---|---|---|---|
| main | infogain, topdown, divide | baseline, tuned | 0 |
| robustness | infogain | tuned | 10% and 20%, 3 seeds each |

Same spectrum for everyone: the bug's own test file(s), as in 0.1 (whole suites are slow and need network).

## Baselines (computed from the same run, no extra cost)

- **Ochiai** and **DStar** (\*=2) function and line rankings: hit if the buggy function or line is in the top
  1, 3 or 5.
- **Crash location:** the innermost project function in the failing test's traceback (only for crashes;
  this is the "stack trace" technique of FauxPy, Rezaalipour & Furia).
- **Classic algorithmic debugging:** top-down and divide-and-query, on the same tree and oracle.

## Metrics

- **Primary:** buggy function found (qdebug's single reported function is one of the functions the fix
  changes) and buggy line found (a changed line is in qdebug's reported region).
- **Secondary:** questions asked (call + line), region size, wall time, Ochiai/DStar rank of the buggy
  function.

## Analysis

- Headline numbers are reported **separately** for the development and held-out sets; conclusions rest on
  the held-out set.
- Paired comparisons on the same bugs: **McNemar's exact test** for found / not found (qdebug vs each
  baseline, tuned vs baseline policy) and the **Wilcoxon signed-rank test** for question counts.
  Two-sided, α = 0.05. With several comparisons, p-values are reported as they are and read with care.
- 95% confidence intervals: Wilson intervals for proportions, bootstrap for means.
- Results are reported whether they favour qdebug or not, including every bug that could not be set up.

## What would count as success

qdebug (tuned, infogain) finds the buggy function more often than Ochiai top-1 on the held-out set, with
p < 0.05, and the tuned policy is not worse than the baseline policy there. Matching Ochiai top-3 with a
single answer would be a strong result; falling below Ochiai top-1 would mean the question-asking adds
nothing on real code.

## Threats to validity

- **Simulated answers.** The ground-truth oracle is a perfect, consistent answerer. Real people make mistakes
  (RQ4 simulates that) and may judge values differently. A user study is needed for that:
  [USER_STUDY.md](USER_STUDY.md).
- **Spectrum limited to the bug's test files** weakens the SBFL baselines and qdebug's prior equally.
- **Environment drift.** Old pins are relaxed when they no longer install; a few bugs may behave differently
  than in 2019–2020. Bugs that don't reproduce are reported, not hidden.
- **Ground truth from the fix.** A fix can change more than the bug (refactoring), or insert code where
  nothing was before; insert-only fixes are reported separately.

## Deviations

(Filled in after the run.)
