# Two bugs at once: planner

137 pairs of the suite's seeded bugs in one copy of the project (13 pairs skipped: their edits overlap, or one bug's failures are all also caused by the other).

## Grouping

| | |
|---|---|
| single-bug variants kept in one group | 34/34 (100%) |
| pairs where no group mixes the two bugs | 120/137 (88%) |
| pairs where each bug's tests form one group | 129/137 (94%) |
| pairs grouped exactly right | 120/137 (88%) |

## Ranking the buggy function

Ochiai rank of each bug's function, against every failing test or against its own group only.

| ranked against | mean rank | top 1 | top 3 |
|---|---|---|---|
| every failing test | 4.47 | 108/274 (39%) | 173/274 (63%) |
| its own group | 1.64 | 201/274 (73%) | 251/274 (92%) |

## Full sessions

Each bug's test debugged with the ground-truth oracle (tuned policy, no noise).

| grouping | sessions | found its bug | found the other bug | exact line | mean questions | fell back to a guess |
|---|---|---|---|---|---|---|
| on | 274 | 269/274 (98%) | 4/274 (1%) | 231/274 (84%) | 7.28 | 19/274 (7%) |
| off | 274 | 265/274 (97%) | 4/274 (1%) | 230/274 (84%) | 7.57 | 20/274 (7%) |
