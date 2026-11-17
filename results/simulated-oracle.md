# Studies with a simulated model oracle

A model oracle such as Claude differs from the noisy oracle of the main study in two ways: how often it
is wrong varies from question to question, and it says how sure it is. `--noise-model confident` simulates
that: for each question an error rate q is drawn uniformly from [0, 2 × noise], the answer is wrong with
probability q, and the stated confidence is 1 − q / overconfidence (1 = calibrated, 2 = it claims half its
real error rate). All runs: the 39 bugs of both suites, information-gain strategy, tuned policy.

These are simulations. They decide how qdebug should *use* a model's answers; they say nothing about how
often Claude is right, which `qdebug eval-ai` measures.

## How should stated confidence weigh an answer?

Mean error 15%, 4 seeds (156 sessions per row), binary line search.

| confidence is | calibrated: function / line | overconfident ×2: function / line |
|---|---|---|
| ignored (every answer has ε = 0.1) | 134 / 71 | 134 / 71 |
| used to weaken unsure answers only, ε = max(0.1, 1 − c) (**default**) | 139 / 71 | 134 / 70 |
| used fully, ε = 1 − c | 139 / 71 | 138 / 71 |
| as default, and line answers below 75% treated as "don't know" | 137 / 70 | 134 / 70 |

Using the confidence helps the call-level search when it is calibrated (+5 functions, about 3 points, near
one standard error at this sample size). Trusting it fully is no worse in these runs, but a real model can
be confidently wrong in ways this simulation does not produce, so the default never lets a stated confidence
make an answer count for more than a person's. Dropping unsure line answers does not help.

```bash
qdebug eval --strategies infogain --noise 0.15 --seeds 4 --noise-model confident --zoom-search binary \
    --confidence-use ignore|floor|raw [--overconfidence 2]
```

## Line search: binary or Bayesian?

The line search was the weak point under noise: it found the line in 71 of 156 sessions while the call
search found the function in 139. It was a binary search over the variable snapshots, so one wrong answer
sent it into the wrong half. The Bayesian search (`zoom.next_probe_bayes`) keeps a posterior over the line
where the state first goes wrong, asks where that posterior splits in half, and stops only when the likeliest
line is bracketed by a "right" before it and a "wrong" at it.

| | function | line | questions (call + line) |
|---|---|---|---|
| noise 0, binary (39 sessions) | 39 | 34 | 7.4 |
| noise 0, Bayesian | 39 | 34 | 7.5 |
| 15% confident noise, binary (234 sessions) | 202 | 95 | 9.3 |
| 15% confident noise, Bayesian | 200 | 104 | 10.8 |

On synthetic searches over 3 to 39 checkpoints, with every possible change point:

| | no wrong answer | one wrong, 1st question | one wrong, 2nd | 10% random | 20% random |
|---|---|---|---|---|---|
| binary: right line | 100% | 0% | 0% | 60% | 34% |
| Bayesian: right line | 100% | 82% | 63% | 67% | 38% |
| Bayesian: extra questions | 0.35 | 3.6 | 2.9 | 0.9 | 1.1 |

On the 5 shop bugs with the plain noisy oracle (answers flipped at exactly 10% or 20%, 50 sessions per
level), it is no better: 56% of lines at 10% against 58% with the binary search, 28% against 28% at 20%,
with 0.4 to 0.7 more line questions. Both differences are well inside the sampling error of about 7 points.

So the gain is real but modest: large when one answer in a search is wrong, a few points under heavier
noise, and paid for with about one more question. It is part of the tuned policy (`--zoom-search binary`
restores the old search).

```bash
qdebug eval --strategies infogain --noise 0.15 --seeds 6 --noise-model confident --zoom-search binary|bayes
```
