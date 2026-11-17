# Haiku 5.5 (Claude Code subagents through the relay) as the oracle, run 1, before the fixes: shop

| | result |
|---|---|
| buggy function found | 5/5 (100%) |
| true line in region | 5/5 (100%) |
| questions per session (call + line) | 4.2 + 5.0 |
| triage: bug kind right | 5/5 (100%) |
| triage: buggy function among suspects | 4/5 (80%) |
| suggested fix restores the original line | 4/5 (80%) |
| requests per session | 11.2 |
| wall time per session | 145 s |

## Claude's answers against the ground truth

| question | answers | right | wrong | 'unknown' | not gradable |
|---|---|---|---|---|---|
| call | 21 | 20/21 (95%) | 1 (0 misleading) | 0 | 0 |
| line | 25 | 24/25 (96%) | 1 (0 misleading) | 0 | 0 |

Calibration (graded call and line answers):

| stated confidence | answers | right |
|---|---|---|
| 0.0-0.6 | 0 | - |
| 0.6-0.8 | 5 | 3/5 (60%) |
| 0.8-0.9 | 18 | 18/18 (100%) |
| 0.9-1.0 | 23 | 23/23 (100%) |

Wrong answers (question, truth -> Claude):

- call: inadmissible -> yes: 1
- line: no -> yes: 1

## Per bug

| bug | kind | found | line | Q | Claude right / answers | triage | fix | $ |
|---|---|---|---|---|---|---|---|---|
| bug_01 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_02 | state | ✓ | ✓ | 3+4 | 7/7 | state * | ✗ | - |
| bug_03 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_04 | wrong-value | ✓ | ✓ | 7+10 | 15/17 | wrong-value * | ✓ | - |
| bug_05 | wrong-value | ✓ | ✓ | 9+5 | 14/14 | wrong-value | ✓ | - |

triage: the kind Claude chose; * = the buggy function was among its suspects.
