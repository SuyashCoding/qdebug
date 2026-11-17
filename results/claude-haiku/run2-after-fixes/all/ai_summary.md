# Haiku 5.5 (Claude Code subagents through the relay) as the oracle, run 2, after the fixes: both suites

| | result |
|---|---|
| buggy function found | 39/39 (100%) |
| true line in region | 34/39 (87%) |
| questions per session (call + line) | 3.1 + 4.3 |
| triage: bug kind right | 35/39 (90%) |
| triage: buggy function among suspects | 37/39 (95%) |
| suggested fix restores the original line | 33/39 (85%) |
| requests per session | 9.4 |
| wall time per session | 70 s |

## Claude's answers against the ground truth

| question | answers | right | wrong | 'unknown' | not gradable |
|---|---|---|---|---|---|
| call | 119 | 110/119 (92%) | 9 (1 misleading) | 0 | 0 |
| line | 169 | 160/169 (95%) | 9 (9 misleading) | 0 | 0 |

Calibration (graded call and line answers):

| stated confidence | answers | right |
|---|---|---|
| 0.0-0.6 | 0 | - |
| 0.6-0.8 | 13 | 9/13 (69%) |
| 0.8-0.9 | 66 | 59/66 (89%) |
| 0.9-1.0 | 209 | 202/209 (97%) |

Wrong answers (question, truth -> Claude):

- line: yes -> no: 9
- call: inadmissible -> yes: 3
- call: inadmissible -> no: 3
- call: yes -> no: 2
- call: no -> yes: 1

## Per bug

| bug | kind | found | line | Q | Claude right / answers | triage | fix | $ |
|---|---|---|---|---|---|---|---|---|
| p01-dict-iteration | crash | ✓ | ✓ | 1+6 | 7/7 | crash * | ✓ | - |
| p02-missing-return | crash | ✓ | ✓ | 1+5 | 6/6 | crash * | ✗ | - |
| p03-case-validation | crash | ✓ | ✓ | 3+5 | 7/8 | crash * | ✓ | - |
| p04-unpack-split | crash | ✓ | ✓ | 1+2 | 3/3 | crash * | ✓ | - |
| p05-untrimmed-deps | crash | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_01 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_02 | state | ✓ | ✓ | 3+4 | 7/7 | state * | ✗ | - |
| bug_03 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_04 | wrong-value | ✓ | ✓ | 12+9 | 21/21 | wrong-value | ✓ | - |
| bug_05 | wrong-value | ✓ | ✓ | 9+5 | 14/14 | wrong-value | ✓ | - |
| p06-empty-guard | crash | ✓ | ✓ | 1+3 | 4/4 | crash * | ✓ | - |
| p07-zero-division | crash | ✓ | ✓ | 1+3 | 4/4 | crash * | ✗ | - |
| p08-missed-cycle | crash | ✓ | ✗ | 4+4 | 7/8 | wrong-value * | ✓ | - |
| p09-weekend-boundary | wrong-value | ✓ | ✓ | 2+1 | 3/3 | wrong-value * | ✓ | - |
| p10-loop-off-by-one | wrong-value | ✓ | ✗ | 5+7 | 10/12 | wrong-value * | ✓ | - |
| p11-range-end | wrong-value | ✓ | ✓ | 9+1 | 9/10 | wrong-value * | ✓ | - |
| p12-wrong-attribute | wrong-value | ✓ | ✓ | 1+4 | 5/5 | wrong-value * | ✓ | - |
| p13-wrong-variable | wrong-value | ✓ | ✓ | 1+8 | 9/9 | wrong-value * | ✓ | - |
| p14-wrong-method | wrong-value | ✓ | ✓ | 1+6 | 7/7 | wrong-value * | ✓ | - |
| p15-swapped-arguments | wrong-value | ✓ | ✓ | 5+4 | 9/9 | wrong-value * | ✓ | - |
| p16-partial-traversal | wrong-value | ✓ | ✓ | 4+4 | 8/8 | wrong-value * | ✓ | - |
| p17-recursion-argument | wrong-value | ✓ | ✓ | 4+5 | 9/9 | wrong-value * | ✓ | - |
| p18-base-case | wrong-value | ✓ | ✓ | 2+4 | 6/6 | wrong-value * | ✓ | - |
| p19-wrong-default | wrong-value | ✓ | ✓ | 3+6 | 9/9 | wrong-value * | ✓ | - |
| p20-limit-boundary | wrong-value | ✓ | ✓ | 2+2 | 4/4 | wrong-value * | ✓ | - |
| p21-truncation | wrong-value | ✓ | ✓ | 1+1 | 2/2 | wrong-value * | ✓ | - |
| p22-sort-direction | wrong-value | ✓ | ✓ | 7+2 | 9/9 | wrong-value * | ✓ | - |
| p23-alignment | wrong-value | ✓ | ✓ | 4+5 | 9/9 | wrong-value * | ✓ | - |
| p24-rounding-direction | wrong-value | ✓ | ✓ | 3+2 | 5/5 | wrong-value * | ✓ | - |
| p25-boolean-logic | wrong-value | ✓ | ✓ | 3+4 | 7/7 | wrong-value * | ✓ | - |
| p26-tag-prefix | wrong-value | ✓ | ✓ | 4+9 | 13/13 | wrong-value * | ✓ | - |
| p27-module-constant | wrong-value | ✓ | ✗ | 1+3 | 4/4 | wrong-value * | ✗ | - |
| p28-generator-numbering | wrong-value | ✓ | ✗ | 2+4 | 6/6 | wrong-value * | ✗ | - |
| p29-accumulator | state | ✓ | ✓ | 3+4 | 7/7 | wrong-value * | ✓ | - |
| p30-shallow-clone | state | ✓ | ✓ | 2+6 | 4/8 | state * | ✗ | - |
| p31-mutable-default | state | ✓ | ✗ | 2+5 | 5/7 | state * | ✓ | - |
| p32-load-bookkeeping | state | ✓ | ✓ | 4+5 | 9/9 | wrong-value * | ✓ | - |
| p33-stale-cache | state | ✓ | ✓ | 3+3 | 4/6 | state * | ✓ | - |
| p34-late-binding | state | ✓ | ✓ | 2+9 | 6/11 | state * | ✓ | - |

triage: the kind Claude chose; * = the buggy function was among its suspects.
