# qdebug evaluation: planner (baseline policy)

34 seeded bugs x 1 strategies x noise 0.0 (10 seeds per noise level > 0; noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate ε = 0.1. Questions are function-level oracle answers; line questions are zoom-mode answers.

## Per-strategy comparison

| strategy | noise | runs | function found | func. questions | line questions | true line in region | region size | tiers used | final tier % | monitored / total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| infogain | 0.0 | 34 | 97% | 7.0 | 4.1 | 82% | 1.0 | 2.4 | 18 | 31 / 50 |

## Per-bug results (noise 0.0)

| bug | buggy function | SBFL function rank | SBFL line rank | infogain: Q / found / line / tier |
|---|---|---|---|---|
| p01-dict-iteration | `Plan.drop_done` | 1 | 2 | 2+4 / ✓ / ✓ / 5% |
| p02-missing-return | `parse_duration` | 4 | 1 | 3+4 / ✓ / ✓ / 10% |
| p03-case-validation | `parse_line` | 2 | 4 | 4+5 / ✓ / ✓ / 10% |
| p04-unpack-split | `split_fields` | 2 | 3 | 1+2 / ✓ / ✓ / 5% |
| p05-untrimmed-deps | `parse_deps` | 4 | 29 | 5+3 / ✓ / ✓ / 10% |
| p06-empty-guard | `busiest` | 1 | 2 | 2+3 / ✓ / ✓ / 5% |
| p07-zero-division | `progress` | 1 | 2 | 2+3 / ✓ / ✓ / 5% |
| p08-missed-cycle | `find_cycle.<locals>.follow` | 2 | 8 | 34+0 / ✗ / ✗ / 10% |
| p09-weekend-boundary | `is_workday` | 1 | 1 | 7+1 / ✓ / ✓ / 10% |
| p10-loop-off-by-one | `add_workdays` | 1 | 3 | 7+6 / ✓ / ✓ / 10% |
| p11-range-end | `workdays_between` | 1 | 1 | 12+9 / ✓ / ✓ / 15% |
| p12-wrong-attribute | `earliest_start` | 1 | 1 | 10+3 / ✓ / ✓ / 15% |
| p13-wrong-variable | `build_schedule` | 1 | 2 | 30+6 / ✓ / ✓ / 25% |
| p14-wrong-method | `critical_path` | 1 | 7 | 10+5 / ✓ / ✓ / 50% |
| p15-swapped-arguments | `slack` | 1 | 3 | 13+4 / ✓ / ✓ / 50% |
| p16-partial-traversal | `order.<locals>.place` | 1 | 7 | 4+3 / ✓ / ✓ / 10% |
| p17-recursion-argument | `_collect_dependents` | 1 | 4 | 4+4 / ✓ / ✓ / 15% |
| p18-base-case | `depth` | 1 | 4 | 5+4 / ✓ / ✓ / 5% |
| p19-wrong-default | `load_by_owner` | 1 | 2 | 2+5 / ✓ / ✓ / 15% |
| p20-limit-boundary | `overloaded` | 1 | 1 | 2+2 / ✓ / ✓ / 5% |
| p21-truncation | `format_percent` | 1 | 1 | 1+1 / ✓ / ✓ / 5% |
| p22-sort-direction | `top_priorities` | 1 | 1 | 8+8 / ✓ / ✓ / 10% |
| p23-alignment | `summary_line` | 1 | 3 | 4+6 / ✓ / ✓ / 5% |
| p24-rounding-direction | `Estimator.buffer` | 1 | 1 | 3+2 / ✓ / ✓ / 15% |
| p25-boolean-logic | `Estimator.risk` | 1 | 3 | 3+3 / ✓ / ✓ / 10% |
| p26-tag-prefix | `parse_line` | 2 | 6 | 4+7 / ✓ / ✓ / 10% |
| p27-module-constant | `parse_duration` | 4 | - | 5+3 / ✓ / ✗ / 10% |
| p28-generator-numbering | `iter_lines` | None | 9 | 13+5 / ✓ / ✗ / 15% |
| p29-accumulator | `Plan.complete` | 1 | 5 | 3+4 / ✓ / ✓ / 5% |
| p30-shallow-clone | `Plan.clone` | 1 | 2 | 12+5 / ✓ / ✗ / 100% |
| p31-mutable-default | `owners_of` | 1 | - | 10+4 / ✓ / ✗ / 100% |
| p32-load-bookkeeping | `rebalance` | 1 | 3 | 4+5 / ✓ / ✓ / 10% |
| p33-stale-cache | `Estimator.effort` | 1 | 1 | 7+4 / ✓ / ✓ / 25% |
| p34-late-binding | `owner_views` | 2 | 7 | 3+6 / ✓ / ✗ / 10% |

Q is function-level + line-level questions; found = reported function is the buggy one; line = a true buggy line is inside the reported region.

## Per bug category (noise 0.0)

| category | bugs | infogain: found / line / mean Q |
|---|---|---|
| crash | 8 | 7/8 / 7/8 / 9.6 |
| state | 6 | 6/6 / 3/6 / 11.2 |
| wrong-value | 20 | 20/20 / 18/20 / 11.7 |

## Tracing cost per tier (failing test call only)

| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |
|---|---|---|
| p01-dict-iteration | 0.10 | 3 → 2.1 ms (13/4) |
| p02-missing-return | 0.00 | 3 → 0.0 ms (24/8); 6 → 0.0 ms (24/16) |
| p03-case-validation | 0.08 | 3 → 1.9 ms (5/3); 6 → 3.1 ms (5/4) |
| p04-unpack-split | 0.11 | 3 → 1.6 ms (3/2) |
| p05-untrimmed-deps | 0.00 | 3 → 0.0 ms (40/11); 6 → 0.0 ms (40/25) |
| p06-empty-guard | 0.09 | 3 → 1.8 ms (5/3) |
| p07-zero-division | 0.05 | 3 → 2.6 ms (4/3) |
| p08-missed-cycle | 0.46 | 3 → 14.8 ms (133/9); 6 → 25.5 ms (133/128) |
| p09-weekend-boundary | 0.56 | 3 → 7.8 ms (155/38); 6 → 10.2 ms (155/53) |
| p10-loop-off-by-one | 0.27 | 3 → 5.8 ms (168/51); 6 → 9.3 ms (168/66) |
| p11-range-end | 0.26 | 3 → 7.4 ms (134/29); 6 → 8.4 ms (134/44); 9 → 7.5 ms (134/55) |
| p12-wrong-attribute | 0.29 | 3 → 5.8 ms (154/15); 6 → 6.6 ms (154/26); 9 → 8.8 ms (154/63) |
| p13-wrong-variable | 0.30 | 3 → 6.7 ms (59/9); 6 → 9.0 ms (59/15); 9 → 7.3 ms (59/39); 15 → 7.2 ms (59/58) |
| p14-wrong-method | 0.54 | 3 → 4.3 ms (135/7); 6 → 10.2 ms (135/18); 9 → 8.7 ms (135/48); 15 → 8.6 ms (135/90); 30 → 10.8 ms (135/133) |
| p15-swapped-arguments | 0.66 | 3 → 6.6 ms (125/3); 6 → 8.1 ms (125/18); 9 → 9.5 ms (125/44); 15 → 6.6 ms (125/81); 30 → 17.1 ms (125/123) |
| p16-partial-traversal | 0.22 | 3 → 8.8 ms (39/10); 6 → 10.7 ms (39/31) |
| p17-recursion-argument | 0.31 | 3 → 6.1 ms (48/5); 6 → 3.2 ms (48/11); 9 → 4.6 ms (48/27) |
| p18-base-case | 0.24 | 3 → 11.6 ms (82/35) |
| p19-wrong-default | 0.24 | 3 → 3.9 ms (42/1); 6 → 3.6 ms (42/8); 9 → 3.1 ms (42/9) |
| p20-limit-boundary | 0.45 | 3 → 5.1 ms (11/3) |
| p21-truncation | 0.24 | 3 → 5.2 ms (2/1) |
| p22-sort-direction | 0.19 | 3 → 3.7 ms (47/7); 6 → 5.5 ms (47/19) |
| p23-alignment | 0.32 | 3 → 8.1 ms (5/4) |
| p24-rounding-direction | 0.21 | 3 → 4.4 ms (64/7); 6 → 6.5 ms (64/15); 9 → 4.9 ms (64/31) |
| p25-boolean-logic | 0.26 | 3 → 11.2 ms (12/3); 6 → 9.8 ms (12/8) |
| p26-tag-prefix | 0.43 | 3 → 4.7 ms (5/2); 6 → 4.8 ms (5/4) |
| p27-module-constant | 0.21 | 3 → 2.5 ms (55/12); 6 → 3.5 ms (55/26) |
| p28-generator-numbering | 0.27 | 3 → 5.2 ms (16/6); 6 → 4.6 ms (16/11); 9 → 4.2 ms (16/15) |
| p29-accumulator | 0.28 | 3 → 4.5 ms (12/6) |
| p30-shallow-clone | 0.14 | 3 → 3.4 ms (13/3); 6 → 4.2 ms (13/11); 9 → 3.7 ms (13/11); 15 → 5.8 ms (13/11); 30 → 3.3 ms (13/11); all → 4.0 ms (13/12) |
| p31-mutable-default | 0.30 | 3 → 6.9 ms (12/9); 6 → 19.3 ms (12/10); 9 → 5.4 ms (12/10); 15 → 5.9 ms (12/10); 30 → 6.6 ms (12/10); all → 6.2 ms (12/11) |
| p32-load-bookkeeping | 0.31 | 3 → 7.0 ms (14/3); 6 → 8.4 ms (14/12) |
| p33-stale-cache | 0.20 | 3 → 3.3 ms (54/4); 6 → 4.2 ms (54/10); 9 → 2.8 ms (54/26); 15 → 3.7 ms (54/52) |
| p34-late-binding | 0.66 | 3 → 4.8 ms (15/3); 6 → 7.3 ms (15/13) |
