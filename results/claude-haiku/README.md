# Claude Haiku 5.5 as the oracle

Every bug of both suites (39) was debugged with Claude Haiku answering every question: the first look
(triage), the call and line questions, and the final explanation. Each answer was also graded against the
ground truth. Run 1 used the prompt and search as they were; what went wrong there led to four changes, and
run 2 repeats the whole benchmark with them.

## How it was run

No API key was available, so the model calls went through the file relay (`qdebug eval-ai --relay DIR`,
[`qdebug/ai/relay.py`](../../qdebug/ai/relay.py)): QDebug writes each request (the same system text, prompt
and JSON schema it would send to the API) to a file, and a Claude Code subagent running Haiku answers it.
One fresh agent per bug, instructed to use nothing but the printed request.

That differs from the API in ways that matter for reading the numbers:

* The agents ran with Claude Code's own system prompt in addition to QDebug's, and the JSON schema was an
  instruction, not enforced by structured outputs.
* There are no token counts, so there is no measured cost. From the prompt sizes (about 1k tokens of
  cacheable system text and 1k per question, 9 to 10 requests per bug), the API cost on Haiku 5.5 should be
  well under one cent per bug; that is an estimate.
* The agents could technically read the repository. Their recorded tool calls show only the relay command
  and the answer files, but the stored transcripts did not contain every call, so the audit is incomplete.
  Two agents reported one stray read-only call each (listing browser tabs, listing session targets).
* Each configuration was run once. Run-to-run variance was not measured.

## Results

| | perfect answerer (simulated) | Haiku, run 1 | Haiku, run 2 |
|---|---|---|---|
| buggy function found | 39 / 39 | 39 / 39 | 39 / 39 |
| true line in the region | 34 / 39 | 29 / 39 | **34 / 39** |
| questions per bug (call + line) | 3.6 + 3.5 | 4.3 + 4.1 | 3.1 + 4.3 |
| call answers right | – | 92% | 92% |
| line answers right | – | 91% | 95% |
| triage: bug kind right / buggy function among suspects | – | 90% / 97% | 90% / 95% |
| suggested fix restores the original line | – | 33 / 39 | 33 / 39 |

After the fixes, Haiku localizes as many lines as the simulated perfect answerer, but not the same ones. It
finds the lines of the shallow-copy bug (`p30`) and the late-bound-lambda bug (`p34`), which the simulated
answerer cannot: it compares printed values, and those look the same, while Haiku reasons that two objects
are shared. It misses `p08` (a nested function in a cycle search) and `p10` (a loop condition), which the
simulated answerer finds. The other three misses are the same for both: a module-level constant, a
generator body and a mutable default argument have no executed line of their own.

Stated confidence is informative: in run 2, answers given with 90% or more were right 97% of the time,
80-90% → 89%, 60-80% → 69%.

The fix check is strict (the suggested code must contain the original line); several "misses" are valid
alternative fixes, such as adding a `return days` line instead of restoring `return int(...) * WEEK`.

## What run 1 showed, and what changed

28 of 329 answers in run 1 disagreed with the ground truth. Reading them one by one:

* **9 were grading artifacts.** On `p30` and `p34` Haiku said "wrong: these objects are shared" and "every
  lambda tests the last owner". That is correct; the ground truth compares reprs and cannot see it.
* **11 were "the inputs were already wrong" cases.** Haiku answered whether the output was right for those
  inputs (for example `compute_tax(3999) → 160`, correct arithmetic on an amount that should have been
  3599). That is a legitimate answer and does not mislead the search; and wherever it answered "wrong"
  instead, the call it blamed was the buggy function itself. The grader now separates answers that point
  the search away from the bug (`misleading` in `ai_questions.csv`): in run 2, 1 of the 9 wrong call
  answers was misleading.
* **The real mistakes had three patterns**, each fixed in run 2:
  1. *A wrong expression on the `return` line* (`p15`, `p23`, `p24`): Haiku judged the end state right
     because every variable was right, ignoring the returned value. The line prompt now says the returned
     value is part of the state.
  2. *A line about to run judged by what it will do* (a loop header): the prompt now says a correct
     implementation also reaches that line.
  3. *The pilot showed a branch bug*: the variables were right but a correct program would not be on that
     line; the prompt now says so and shows the line that ran just before.
* **One unsure answer could undo a sure one.** In `p15` and `p24` Haiku blamed the right call by question
  3 (90-95% sure); then the line search's end check got a 60-70% "the end state is right" (pattern 1), which
  overrode the call answer and sent the search through 27 unrelated questions until the budget ran out.
  Now, when the end check contradicts the call answer, the more confident answer wins
  (`zoom_into(..., call_error=)`); a person's answers are unaffected.
* **Examples from passing tests can repeat a bug.** In `p10` a passing test showed the same wrong value
  for the same inputs, labelled as very likely correct. Examples with the same inputs as the question are
  now left out (they carry no evidence), and the label says passing tests can hide bugs.

## Files

`run1-before-fixes/` and `run2-after-fixes/`, each with `all/`, `shop/` and `planner/`:
`ai_summary.md` (the tables), `ai_results.csv` (one row per bug) and `ai_questions.csv` (every answer with
Claude's reason, the ground truth, and whether it was misleading).
