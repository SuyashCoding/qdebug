# User study protocol

Every benchmark result for qdebug uses a *simulated* answerer that compares each call with the fixed
program, so it never misjudges a value. Whether real people answer qdebug's questions well enough, and
whether that saves them time, can only be measured with people. This is a small study a class project can
run in an afternoon.

## Question

Do people find the cause of a failing test **faster** and **more often** with qdebug than with what they
would normally use?

## Design

- **Participants:** 8 to 16 programmers who know Python (for example classmates in a second-year course).
  Record how long each has programmed in Python. Participation is voluntary, and nothing about a person is
  published beyond these numbers. Check whether your school needs ethics approval for studies with students.
- **Tasks:** 4 real bugs from BugsInPy that reproduce in the Docker study, chosen *before* the study and
  never shown to the participants: two crashes and two wrong values, from two projects. Each task gives the
  project, the failing test and its error, nothing else.
- **Conditions:**
  - **qdebug:** `qdebug debug` in the Docker container, answering the questions themselves.
  - **Control:** the same container with their normal tools: reading code, `print`, `pdb`, and the
    `qdebug rank` list of suspicious functions (so the control also gets the statistical hint and only the
    questions differ).
- **Within-subjects, counterbalanced:** everyone does 2 tasks with qdebug and 2 without. Which tasks get
  which condition, and the order, is rotated across participants (a Latin square) so that task difficulty and
  learning even out.
- **Warm-up:** 10 minutes on the README demo (tqdm) before the first qdebug task, so nobody is learning the
  tool during a measured task. Control participants get the same 10 minutes with `qdebug rank` and `pdb`.

## Procedure for each task

1. Start a timer when the participant sees the failing test.
2. The task ends when they name a file and line (or function) and say they're done, or after **20 minutes**.
3. Record: time, the line or function named, and for qdebug every answer they gave (qdebug saves the session
   under `.qdebug/sessions/`).
4. After each task: "How sure are you, 1 to 5?" After all tasks: which way they preferred and why.

## Measures

- **Correct:** the named line is one the real fix changes (strict), or inside a function the fix changes
  (lenient).
- **Time to answer** (20 minutes if they ran out).
- **Answer accuracy (qdebug only):** each of their answers compared with the ground-truth oracle's answer to
  the same question (`qdebug debug --oracle truth` on the saved session's test). This shows how often real
  people answer wrong, which tells us whether the 10% and 20% noise levels in the benchmarks are realistic.
- **Confidence** and **preference** (descriptive only).

## Analysis

- Correct or not: per participant, the share correct with and without qdebug; Wilcoxon signed-rank test on
  the paired shares (`qdebug.stats.wilcoxon`).
- Time: per participant, mean time with and without; Wilcoxon signed-rank test. Report medians and every
  participant's numbers, since small samples hide a lot in averages.
- With 8 to 16 people the study can show a large effect, not a small one. Report it as a pilot study, with
  effect sizes and confidence intervals, not only p-values.

## Threats to validity

- Students are not professional developers. Bugs in unfamiliar projects are harder than bugs in your own
  code, for both conditions alike.
- Participants know which condition is the new tool, and may try harder with it.
- The person running the study should not help during a task. Write down every question a participant asks.
