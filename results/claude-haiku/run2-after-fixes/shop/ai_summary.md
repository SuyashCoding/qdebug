# Haiku 5.5 (Claude Code subagents through the relay) as the oracle, run 2, after the fixes: shop

| | result |
|---|---|
| buggy function found | 5/5 (100%) |
| true line in region | 5/5 (100%) |
| questions per session (call + line) | 5.2 + 4.8 |
| triage: bug kind right | 5/5 (100%) |
| triage: buggy function among suspects | 3/5 (60%) |
| suggested fix restores the original line | 4/5 (80%) |
| requests per session | 12.0 |
| wall time per session | 87 s |

## Claude's answers against the ground truth

| question | answers | right | wrong | 'unknown' | not gradable |
|---|---|---|---|---|---|
| call | 26 | 26/26 (100%) | 0 (0 misleading) | 0 | 0 |
| line | 24 | 24/24 (100%) | 0 (0 misleading) | 0 | 0 |

Calibration (graded call and line answers):

| stated confidence | answers | right |
|---|---|---|
| 0.0-0.6 | 0 | - |
| 0.6-0.8 | 1 | 1/1 (100%) |
| 0.8-0.9 | 17 | 17/17 (100%) |
| 0.9-1.0 | 32 | 32/32 (100%) |

## Per bug

| bug | kind | found | line | Q | Claude right / answers | triage | fix | $ |
|---|---|---|---|---|---|---|---|---|
| bug_01 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_02 | state | ✓ | ✓ | 3+4 | 7/7 | state * | ✗ | - |
| bug_03 | wrong-value | ✓ | ✓ | 1+3 | 4/4 | wrong-value * | ✓ | - |
| bug_04 | wrong-value | ✓ | ✓ | 12+9 | 21/21 | wrong-value | ✓ | - |
| bug_05 | wrong-value | ✓ | ✓ | 9+5 | 14/14 | wrong-value | ✓ | - |

triage: the kind Claude chose; * = the buggy function was among its suspects.
