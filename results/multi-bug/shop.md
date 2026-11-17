# Two bugs at once: shop

10 pairs of the suite's seeded bugs in one copy of the project (0 pairs skipped: their edits overlap, or one bug's failures are all also caused by the other).

## Grouping

| | |
|---|---|
| single-bug variants kept in one group | 5/5 (100%) |
| pairs where no group mixes the two bugs | 9/10 (90%) |
| pairs where each bug's tests form one group | 10/10 (100%) |
| pairs grouped exactly right | 9/10 (90%) |

## Ranking the buggy function

Ochiai rank of each bug's function, against every failing test or against its own group only.

| ranked against | mean rank | top 1 | top 3 |
|---|---|---|---|
| every failing test | 4.20 | 4/20 (20%) | 9/20 (45%) |
| its own group | 3.75 | 4/20 (20%) | 11/20 (55%) |

## Full sessions

Each bug's test debugged with the ground-truth oracle (tuned policy, no noise).

| grouping | sessions | found its bug | found the other bug | exact line | mean questions | fell back to a guess |
|---|---|---|---|---|---|---|
| on | 20 | 20/20 (100%) | 0/20 (0%) | 20/20 (100%) | 9.65 | 0/20 (0%) |
| off | 20 | 20/20 (100%) | 0/20 (0%) | 20/20 (100%) | 9.45 | 0/20 (0%) |
