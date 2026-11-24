# qdebug on real bugs (BugsInPy)

Plan: [results/bugsinpy-2026/PLAN.md](../bugsinpy-2026/PLAN.md). Ground-truth oracle (each call compared with the fixed version); spectrum from the bug's test file(s). "Found" means qdebug's single reported function is a function the fix changes, and "line" that a line the fix changes is in its reported region. CI: 95% Wilson interval. Ties in the SBFL rankings are broken by name.

## Held-out projects (never used while developing qdebug)

Projects: black, fastapi, luigi, sanic, scrapy, tornado. 133 bugs attempted, 110 reproduced, 105 with a completed qdebug session (infogain, tuned policy, no wrong answers).

| status | bugs |
|---|---|
| error | 2 |
| no trace | 1 |
| nondeterministic | 2 |
| not reproducible | 20 |
| ok | 105 |
| setup failed | 3 |

### RQ1. qdebug against the baselines

| technique | buggy function | buggy line |
|---|---|---|
| **qdebug** (one function, and a 1.0-line region on average) | 49/105 (47%, CI 37–56%) | 37/105 (35%, CI 27–45%) |
| Ochiai top-1 | 23/105 (22%, CI 15–31%) | 13/105 (12%, CI 7–20%) |
| Ochiai top-3 | 41/105 (39%, CI 30–49%) | 29/105 (28%, CI 20–37%) |
| Ochiai top-5 | 54/105 (51%, CI 42–61%) | 36/105 (34%, CI 26–44%) |
| DStar top-1 | 23/105 (22%, CI 15–31%) | 13/105 (12%, CI 7–20%) |
| DStar top-3 | 41/105 (39%, CI 30–49%) | 27/105 (26%, CI 18–35%) |
| DStar top-5 | 52/105 (50%, CI 40–59%) | 33/105 (31%, CI 23–41%) |
| crash location (all bugs) | 11/105 (10%, CI 6–18%) | – |
| crash location (the 20 crashes only) | 11/20 (55%, CI 34–74%) | – |

Paired against qdebug on the same bugs (McNemar, exact): *only qdebug / only the other*, p.

| comparison | function | line |
|---|---|---|
| qdebug vs Ochiai top-1 | 28 / 2, p = <0.001 | 28 / 4, p = <0.001 |
| qdebug vs Ochiai top-3 | 17 / 9, p = 0.169 | 20 / 12, p = 0.215 |
| qdebug vs Ochiai top-5 | 10 / 15, p = 0.424 | 15 / 14, p = 1.000 |
| qdebug vs DStar top-1 | 28 / 2, p = <0.001 | 28 / 4, p = <0.001 |
| qdebug vs DStar top-3 | 17 / 9, p = 0.169 | 20 / 10, p = 0.099 |
| qdebug vs crash location | 41 / 3, p = <0.001 | – |

### RQ2. Tuned search rules against the original search (infogain, no wrong answers)

| | tuned | baseline | paired test |
|---|---|---|---|
| buggy function | 49/105 | 50/105 | McNemar: 1 vs 2 discordant, p = 1.000 |
| buggy line | 37/105 | 36/105 | McNemar: 1 vs 0 discordant, p = 1.000 |
| questions, mean (95% CI) | 10.7 (9.1–12.3) | 13.4 (11.4–15.5) | Wilcoxon: 71 non-tied pairs, p = <0.001 |
| questions, median | 8 | 11 | |

Information gain against the classic strategies (tuned policy):

| | infogain | top-down | paired test |
|---|---|---|---|
| buggy function | 49/105 | 45/105 | McNemar: 5 vs 1 discordant, p = 0.219 |
| buggy line | 37/105 | 33/105 | McNemar: 4 vs 0 discordant, p = 0.125 |
| questions, mean (95% CI) | 10.7 (9.1–12.3) | 11.4 (9.6–13.3) | Wilcoxon: 81 non-tied pairs, p = 0.111 |
| questions, median | 8 | 9 | |

| | infogain | divide-and-query | paired test |
|---|---|---|---|
| buggy function | 49/105 | 49/105 | McNemar: 3 vs 3 discordant, p = 1.000 |
| buggy line | 37/105 | 36/105 | McNemar: 3 vs 2 discordant, p = 1.000 |
| questions, mean (95% CI) | 10.7 (9.1–12.3) | 11.8 (9.9–13.8) | Wilcoxon: 71 non-tied pairs, p = 0.236 |
| questions, median | 8 | 9 | |

### RQ4. Wrong answers (infogain, tuned; every seed counted)

| answers wrong | sessions | buggy function | buggy line | questions (mean) |
|---|---|---|---|---|
| 0% | 105 | 49/105 (47%, CI 37–56%) | 37/105 (35%, CI 27–45%) | 10.7 |
| 10% | 315 | 124/315 (39%, CI 34–45%) | 75/315 (24%, CI 19–29%) | 11.5 |
| 20% | 315 | 110/315 (35%, CI 30–40%) | 49/315 (16%, CI 12–20%) | 11.6 |

### RQ5. Where it fails

| bugs | n | buggy function | buggy line | Ochiai top-1 function |
|---|---|---|---|---|
| failing test with < 100 calls | 60 | 28/60 (47%, CI 35–59%) | 21/60 (35%, CI 24–48%) | 17/60 (28%, CI 19–41%) |
| failing test with 100+ calls | 45 | 21/45 (47%, CI 33–61%) | 16/45 (36%, CI 23–50%) | 6/45 (13%, CI 6–26%) |
| crash (exception raised in project code) | 20 | 10/20 (50%, CI 30–70%) | 9/20 (45%, CI 26–66%) | 6/20 (30%, CI 15–52%) |
| no crash (a wrong value) | 85 | 39/85 (46%, CI 36–56%) | 28/85 (33%, CI 24–43%) | 17/85 (20%, CI 13–30%) |
| fix only inserts code (omission) | 10 | 5/10 (50%, CI 24–76%) | 4/10 (40%, CI 17–69%) | 2/10 (20%, CI 6–51%) |
| fix changes existing lines | 95 | 44/95 (46%, CI 37–56%) | 33/95 (35%, CI 26–45%) | 21/95 (22%, CI 15–31%) |
| one failing test | 75 | 35/75 (47%, CI 36–58%) | 27/75 (36%, CI 26–47%) | 16/75 (21%, CI 14–32%) |
| several failing tests | 30 | 14/30 (47%, CI 30–64%) | 10/30 (33%, CI 19–51%) | 7/30 (23%, CI 12–41%) |

### Per project

| project | attempted | reproduced | sessions | qdebug function / line | Ochiai top-1 function |
|---|---|---|---|---|---|
| black | 23 | 22 | 22 | 10 / 7 | 4 |
| fastapi | 16 | 16 | 15 | 4 / 2 | 2 |
| luigi | 33 | 27 | 26 | 12 / 10 | 5 |
| sanic | 5 | 3 | 2 | 2 / 1 | 1 |
| scrapy | 40 | 27 | 26 | 18 / 15 | 9 |
| tornado | 16 | 15 | 14 | 3 / 2 | 2 |

## Development projects (used in version 0.1)

Projects: PySnooper, cookiecutter, httpie, thefuck, tqdm, youtube-dl. 96 bugs attempted, 86 reproduced, 81 with a completed qdebug session (infogain, tuned policy, no wrong answers).

| status | bugs |
|---|---|
| no trace | 5 |
| not reproducible | 10 |
| ok | 81 |

### RQ1. qdebug against the baselines

| technique | buggy function | buggy line |
|---|---|---|
| **qdebug** (one function, and a 1.0-line region on average) | 63/81 (78%, CI 68–85%) | 35/81 (43%, CI 33–54%) |
| Ochiai top-1 | 48/81 (59%, CI 48–69%) | 20/81 (25%, CI 17–35%) |
| Ochiai top-3 | 62/81 (77%, CI 66–84%) | 32/81 (40%, CI 30–50%) |
| Ochiai top-5 | 64/81 (79%, CI 69–86%) | 42/81 (52%, CI 41–62%) |
| DStar top-1 | 45/81 (56%, CI 45–66%) | 19/81 (23%, CI 16–34%) |
| DStar top-3 | 62/81 (77%, CI 66–84%) | 31/81 (38%, CI 28–49%) |
| DStar top-5 | 64/81 (79%, CI 69–86%) | 42/81 (52%, CI 41–62%) |
| crash location (all bugs) | 18/81 (22%, CI 15–32%) | – |
| crash location (the 24 crashes only) | 18/24 (75%, CI 55–88%) | – |

Paired against qdebug on the same bugs (McNemar, exact): *only qdebug / only the other*, p.

| comparison | function | line |
|---|---|---|
| qdebug vs Ochiai top-1 | 19 / 4, p = 0.003 | 20 / 5, p = 0.004 |
| qdebug vs Ochiai top-3 | 7 / 6, p = 1.000 | 12 / 9, p = 0.664 |
| qdebug vs Ochiai top-5 | 6 / 7, p = 1.000 | 8 / 15, p = 0.210 |
| qdebug vs DStar top-1 | 22 / 4, p = <0.001 | 21 / 5, p = 0.002 |
| qdebug vs DStar top-3 | 7 / 6, p = 1.000 | 12 / 8, p = 0.503 |
| qdebug vs crash location | 49 / 4, p = <0.001 | – |

### RQ2. Tuned search rules against the original search (infogain, no wrong answers)

| | tuned | baseline | paired test |
|---|---|---|---|
| buggy function | 63/81 | 61/81 | McNemar: 2 vs 0 discordant, p = 0.500 |
| buggy line | 35/81 | 34/81 | McNemar: 1 vs 0 discordant, p = 1.000 |
| questions, mean (95% CI) | 7.4 (6.4–8.6) | 11.1 (9.1–13.4) | Wilcoxon: 51 non-tied pairs, p = <0.001 |
| questions, median | 6 | 7 | |

Information gain against the classic strategies (tuned policy):

| | infogain | top-down | paired test |
|---|---|---|---|
| buggy function | 63/81 | 59/81 | McNemar: 6 vs 2 discordant, p = 0.289 |
| buggy line | 35/81 | 32/81 | McNemar: 3 vs 0 discordant, p = 0.250 |
| questions, mean (95% CI) | 7.4 (6.4–8.6) | 13.0 (10.8–15.3) | Wilcoxon: 73 non-tied pairs, p = <0.001 |
| questions, median | 6 | 9 | |

| | infogain | divide-and-query | paired test |
|---|---|---|---|
| buggy function | 63/81 | 62/81 | McNemar: 2 vs 1 discordant, p = 1.000 |
| buggy line | 35/81 | 34/81 | McNemar: 1 vs 0 discordant, p = 1.000 |
| questions, mean (95% CI) | 7.4 (6.4–8.6) | 11.6 (9.6–13.8) | Wilcoxon: 63 non-tied pairs, p = <0.001 |
| questions, median | 6 | 8 | |

### RQ4. Wrong answers (infogain, tuned; every seed counted)

| answers wrong | sessions | buggy function | buggy line | questions (mean) |
|---|---|---|---|---|
| 0% | 81 | 63/81 (78%, CI 68–85%) | 35/81 (43%, CI 33–54%) | 7.4 |
| 10% | 243 | 166/243 (68%, CI 62–74%) | 72/243 (30%, CI 24–36%) | 8.6 |
| 20% | 243 | 152/243 (63%, CI 56–68%) | 53/243 (22%, CI 17–27%) | 9.3 |

### RQ5. Where it fails

| bugs | n | buggy function | buggy line | Ochiai top-1 function |
|---|---|---|---|---|
| failing test with < 100 calls | 68 | 55/68 (81%, CI 70–88%) | 31/68 (46%, CI 34–57%) | 44/68 (65%, CI 53–75%) |
| failing test with 100+ calls | 13 | 8/13 (62%, CI 36–82%) | 4/13 (31%, CI 13–58%) | 4/13 (31%, CI 13–58%) |
| crash (exception raised in project code) | 24 | 17/24 (71%, CI 51–85%) | 11/24 (46%, CI 28–65%) | 13/24 (54%, CI 35–72%) |
| no crash (a wrong value) | 57 | 46/57 (81%, CI 69–89%) | 24/57 (42%, CI 30–55%) | 35/57 (61%, CI 48–73%) |
| fix only inserts code (omission) | 5 | 2/5 (40%, CI 12–77%) | 2/5 (40%, CI 12–77%) | 2/5 (40%, CI 12–77%) |
| fix changes existing lines | 76 | 61/76 (80%, CI 70–88%) | 33/76 (43%, CI 33–55%) | 46/76 (61%, CI 49–71%) |
| one failing test | 55 | 44/55 (80%, CI 68–88%) | 24/55 (44%, CI 31–57%) | 33/55 (60%, CI 47–72%) |
| several failing tests | 26 | 19/26 (73%, CI 54–86%) | 11/26 (42%, CI 26–61%) | 15/26 (58%, CI 39–74%) |

### Per project

| project | attempted | reproduced | sessions | qdebug function / line | Ochiai top-1 function |
|---|---|---|---|---|---|
| PySnooper | 3 | 2 | 1 | 0 / 0 | 1 |
| cookiecutter | 4 | 3 | 3 | 2 / 1 | 2 |
| httpie | 5 | 5 | 5 | 2 / 0 | 1 |
| thefuck | 32 | 24 | 24 | 19 / 12 | 15 |
| tqdm | 9 | 9 | 9 | 6 / 6 | 4 |
| youtube-dl | 43 | 43 | 39 | 34 / 16 | 25 |

