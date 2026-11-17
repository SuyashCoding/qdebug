# qdebug evaluation: planner (tuned policy)

34 seeded bugs x 3 strategies x noise 0.0 (10 seeds per noise level > 0; noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate ε = 0.1. Questions are function-level oracle answers; line questions are zoom-mode answers.

## Per-strategy comparison

| strategy | noise | runs | function found | func. questions | line questions | true line in region | region size | tiers used | final tier % | monitored / total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| infogain | 0.0 | 34 | 100% | 3.6 | 3.5 | 85% | 1.0 | 2.0 | 15 | 12 / 23 |
| divide | 0.0 | 34 | 100% | 4.4 | 3.9 | 85% | 1.0 | 2.1 | 16 | 17 / 23 |
| topdown | 0.0 | 34 | 100% | 5.3 | 3.9 | 85% | 1.0 | 3.7 | 50 | 22 / 23 |

## Per-bug results (noise 0.0)

| bug | buggy function | SBFL function rank | SBFL line rank | infogain: Q / found / line / tier | divide: Q / found / line / tier | topdown: Q / found / line / tier |
|---|---|---|---|---|---|---|
| p01-dict-iteration | `Plan.drop_done` | 1 | 2 | 2+4 / ✓ / ✓ / 5% | 2+4 / ✓ / ✓ / 5% | 5+4 / ✓ / ✓ / 100% |
| p02-missing-return | `parse_duration` | 4 | 1 | 2+4 / ✓ / ✓ / 10% | 2+4 / ✓ / ✓ / 10% | 2+4 / ✓ / ✓ / 10% |
| p03-case-validation | `parse_line` | 2 | 4 | 4+5 / ✓ / ✓ / 10% | 4+5 / ✓ / ✓ / 10% | 4+5 / ✓ / ✓ / 10% |
| p04-unpack-split | `split_fields` | 2 | 3 | 1+2 / ✓ / ✓ / 5% | 2+2 / ✓ / ✓ / 5% | 2+2 / ✓ / ✓ / 5% |
| p05-untrimmed-deps | `parse_deps` | 4 | 29 | 1+3 / ✓ / ✓ / 10% | 1+3 / ✓ / ✓ / 10% | 1+3 / ✓ / ✓ / 10% |
| p06-empty-guard | `busiest` | 1 | 2 | 2+3 / ✓ / ✓ / 5% | 2+3 / ✓ / ✓ / 5% | 3+3 / ✓ / ✓ / 10% |
| p07-zero-division | `progress` | 1 | 2 | 2+3 / ✓ / ✓ / 5% | 2+3 / ✓ / ✓ / 5% | 3+3 / ✓ / ✓ / 5% |
| p08-missed-cycle | `find_cycle.<locals>.follow` | 2 | 8 | 3+4 / ✓ / ✓ / 10% | 4+4 / ✓ / ✓ / 10% | 9+4 / ✓ / ✓ / 15% |
| p09-weekend-boundary | `is_workday` | 1 | 1 | 2+1 / ✓ / ✓ / 5% | 6+1 / ✓ / ✓ / 5% | 6+1 / ✓ / ✓ / 5% |
| p10-loop-off-by-one | `add_workdays` | 1 | 3 | 5+6 / ✓ / ✓ / 5% | 5+6 / ✓ / ✓ / 5% | 5+6 / ✓ / ✓ / 5% |
| p11-range-end | `workdays_between` | 1 | 1 | 9+1 / ✓ / ✓ / 5% | 9+8 / ✓ / ✓ / 5% | 10+8 / ✓ / ✓ / 5% |
| p12-wrong-attribute | `earliest_start` | 1 | 1 | 1+4 / ✓ / ✓ / 5% | 1+4 / ✓ / ✓ / 5% | 1+4 / ✓ / ✓ / 5% |
| p13-wrong-variable | `build_schedule` | 1 | 2 | 1+7 / ✓ / ✓ / 5% | 18+7 / ✓ / ✓ / 25% | 19+7 / ✓ / ✓ / 25% |
| p14-wrong-method | `critical_path` | 1 | 7 | 1+5 / ✓ / ✓ / 5% | 7+5 / ✓ / ✓ / 50% | 8+5 / ✓ / ✓ / 100% |
| p15-swapped-arguments | `slack` | 1 | 3 | 5+4 / ✓ / ✓ / 50% | 4+4 / ✓ / ✓ / 50% | 5+4 / ✓ / ✓ / 100% |
| p16-partial-traversal | `order.<locals>.place` | 1 | 7 | 4+3 / ✓ / ✓ / 10% | 5+3 / ✓ / ✓ / 10% | 7+3 / ✓ / ✓ / 100% |
| p17-recursion-argument | `_collect_dependents` | 1 | 4 | 4+4 / ✓ / ✓ / 15% | 4+4 / ✓ / ✓ / 5% | 5+4 / ✓ / ✓ / 100% |
| p18-base-case | `depth` | 1 | 4 | 2+4 / ✓ / ✓ / 10% | 2+4 / ✓ / ✓ / 5% | 3+4 / ✓ / ✓ / 100% |
| p19-wrong-default | `load_by_owner` | 1 | 2 | 3+5 / ✓ / ✓ / 10% | 3+5 / ✓ / ✓ / 10% | 4+5 / ✓ / ✓ / 100% |
| p20-limit-boundary | `overloaded` | 1 | 1 | 2+2 / ✓ / ✓ / 5% | 2+2 / ✓ / ✓ / 5% | 3+2 / ✓ / ✓ / 100% |
| p21-truncation | `format_percent` | 1 | 1 | 1+1 / ✓ / ✓ / 5% | 1+1 / ✓ / ✓ / 5% | 1+1 / ✓ / ✓ / 5% |
| p22-sort-direction | `top_priorities` | 1 | 1 | 7+2 / ✓ / ✓ / 5% | 7+8 / ✓ / ✓ / 5% | 8+8 / ✓ / ✓ / 100% |
| p23-alignment | `summary_line` | 1 | 3 | 4+5 / ✓ / ✓ / 5% | 4+5 / ✓ / ✓ / 5% | 4+5 / ✓ / ✓ / 5% |
| p24-rounding-direction | `Estimator.buffer` | 1 | 1 | 3+2 / ✓ / ✓ / 15% | 2+2 / ✓ / ✓ / 5% | 6+2 / ✓ / ✓ / 100% |
| p25-boolean-logic | `Estimator.risk` | 1 | 3 | 3+3 / ✓ / ✓ / 10% | 3+3 / ✓ / ✓ / 5% | 7+3 / ✓ / ✓ / 15% |
| p26-tag-prefix | `parse_line` | 2 | 6 | 4+7 / ✓ / ✓ / 10% | 4+7 / ✓ / ✓ / 10% | 4+7 / ✓ / ✓ / 10% |
| p27-module-constant | `parse_duration` | 4 | - | 1+3 / ✓ / ✗ / 10% | 1+3 / ✓ / ✗ / 10% | 1+3 / ✓ / ✗ / 10% |
| p28-generator-numbering | `iter_lines` | None | 9 | 6+4 / ✓ / ✗ / 10% | 10+5 / ✓ / ✗ / 15% | 9+5 / ✓ / ✗ / 15% |
| p29-accumulator | `Plan.complete` | 1 | 5 | 3+4 / ✓ / ✓ / 5% | 3+4 / ✓ / ✓ / 5% | 4+4 / ✓ / ✓ / 100% |
| p30-shallow-clone | `Plan.clone` | 1 | 2 | 12+0 / ✓ / ✗ / 100% | 9+0 / ✓ / ✗ / 100% | 5+0 / ✓ / ✗ / 100% |
| p31-mutable-default | `owners_of` | 1 | - | 10+0 / ✓ / ✗ / 100% | 9+0 / ✓ / ✗ / 100% | 3+0 / ✓ / ✗ / 100% |
| p32-load-bookkeeping | `rebalance` | 1 | 3 | 4+5 / ✓ / ✓ / 10% | 4+5 / ✓ / ✓ / 10% | 10+5 / ✓ / ✓ / 15% |
| p33-stale-cache | `Estimator.effort` | 1 | 1 | 7+4 / ✓ / ✓ / 15% | 6+4 / ✓ / ✓ / 25% | 9+4 / ✓ / ✓ / 100% |
| p34-late-binding | `owner_views` | 2 | 7 | 3+6 / ✓ / ✗ / 10% | 3+6 / ✓ / ✗ / 10% | 4+6 / ✓ / ✗ / 100% |

Q is function-level + line-level questions; found = reported function is the buggy one; line = a true buggy line is inside the reported region.

## Per bug category (noise 0.0)

| category | bugs | infogain: found / line / mean Q | divide: found / line / mean Q | topdown: found / line / mean Q |
|---|---|---|---|---|
| crash | 8 | 8/8 / 8/8 / 5.6 | 8/8 / 8/8 / 5.9 | 8/8 / 8/8 / 7.1 |
| state | 6 | 6/6 / 3/6 / 9.7 | 6/6 / 3/6 / 8.8 | 6/6 / 3/6 / 9.0 |
| wrong-value | 20 | 20/20 / 18/20 / 7.0 | 20/20 / 18/20 / 9.2 | 20/20 / 18/20 / 10.2 |

## Tracing cost per tier (failing test call only)

| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |
|---|---|---|
| p01-dict-iteration | 0.05 | 3 → 1.5 ms (13/4); 6 → 1.8 ms (13/11); 9 → 1.9 ms (13/11); 15 → 2.2 ms (13/11); 30 → 2.0 ms (13/11); all → 1.9 ms (13/12) |
| p02-missing-return | 0.07 | 3 → 1.3 ms (3/1); 6 → 1.7 ms (3/2) |
| p03-case-validation | 0.06 | 3 → 1.3 ms (5/3); 6 → 1.5 ms (5/4) |
| p04-unpack-split | 0.06 | 3 → 1.3 ms (3/2) |
| p05-untrimmed-deps | 0.28 | 3 → 2.8 ms (2/0); 6 → 2.9 ms (2/1) |
| p06-empty-guard | 0.05 | 3 → 1.5 ms (5/3); 6 → 1.5 ms (5/4) |
| p07-zero-division | 0.05 | 3 → 1.5 ms (4/3) |
| p08-missed-cycle | 0.17 | 3 → 4.6 ms (15/7); 6 → 3.7 ms (15/10); 9 → 5.3 ms (15/14) |
| p09-weekend-boundary | 0.18 | 3 → 3.2 ms (8/7) |
| p10-loop-off-by-one | 0.17 | 3 → 3.2 ms (10/9) |
| p11-range-end | 0.19 | 3 → 3.3 ms (17/16) |
| p12-wrong-attribute | 0.25 | 3 → 2.4 ms (2/1) |
| p13-wrong-variable | 0.33 | 3 → 4.8 ms (59/9); 6 → 4.6 ms (59/15); 9 → 5.6 ms (59/39); 15 → 6.4 ms (59/58) |
| p14-wrong-method | 0.21 | 3 → 3.4 ms (135/7); 6 → 4.6 ms (135/18); 9 → 5.3 ms (135/48); 15 → 6.2 ms (135/90); 30 → 8.7 ms (135/133); all → 8.8 ms (135/134) |
| p15-swapped-arguments | 0.21 | 3 → 2.5 ms (125/3); 6 → 4.5 ms (125/18); 9 → 6.3 ms (125/44); 15 → 5.7 ms (125/81); 30 → 8.1 ms (125/123); all → 7.7 ms (125/124) |
| p16-partial-traversal | 0.19 | 3 → 4.5 ms (39/10); 6 → 6.6 ms (39/31); 9 → 6.4 ms (39/37); 15 → 6.8 ms (39/37); 30 → 6.0 ms (39/37); all → 6.9 ms (39/38) |
| p17-recursion-argument | 0.18 | 3 → 2.5 ms (48/5); 6 → 2.7 ms (48/11); 9 → 3.0 ms (48/27); 15 → 2.7 ms (48/46); 30 → 2.6 ms (48/46); all → 2.7 ms (48/47) |
| p18-base-case | 0.16 | 3 → 2.6 ms (10/2); 6 → 3.4 ms (10/8); 9 → 3.0 ms (10/8); 15 → 3.2 ms (10/8); 30 → 3.1 ms (10/8); all → 3.1 ms (10/9) |
| p19-wrong-default | 0.18 | 3 → 3.1 ms (11/2); 6 → 3.3 ms (11/8); 9 → 3.4 ms (11/9); 15 → 3.7 ms (11/9); 30 → 3.5 ms (11/9); all → 3.7 ms (11/10) |
| p20-limit-boundary | 0.18 | 3 → 3.3 ms (11/3); 6 → 3.6 ms (11/9); 9 → 3.9 ms (11/9); 15 → 4.1 ms (11/9); 30 → 4.6 ms (11/9); all → 4.0 ms (11/10) |
| p21-truncation | 0.21 | 3 → 3.2 ms (2/1) |
| p22-sort-direction | 0.16 | 3 → 2.6 ms (47/7); 6 → 2.4 ms (47/19); 9 → 2.7 ms (47/33); 15 → 2.5 ms (47/45); 30 → 2.5 ms (47/45); all → 2.6 ms (47/46) |
| p23-alignment | 0.28 | 3 → 3.8 ms (5/4) |
| p24-rounding-direction | 0.19 | 3 → 3.5 ms (64/7); 6 → 2.8 ms (64/15); 9 → 3.7 ms (64/31); 15 → 3.9 ms (64/62); 30 → 5.1 ms (64/62); all → 4.2 ms (64/63) |
| p25-boolean-logic | 0.21 | 3 → 3.5 ms (12/3); 6 → 3.7 ms (12/8); 9 → 5.4 ms (12/11) |
| p26-tag-prefix | 0.19 | 3 → 4.0 ms (5/2); 6 → 3.7 ms (5/4) |
| p27-module-constant | 0.17 | 3 → 2.9 ms (2/0); 6 → 2.9 ms (2/1) |
| p28-generator-numbering | 0.23 | 3 → 3.2 ms (16/6); 6 → 4.6 ms (16/11); 9 → 5.6 ms (16/15) |
| p29-accumulator | 0.16 | 3 → 3.4 ms (12/6); 6 → 3.0 ms (12/10); 9 → 5.1 ms (12/10); 15 → 3.7 ms (12/10); 30 → 3.1 ms (12/10); all → 3.7 ms (12/11) |
| p30-shallow-clone | 0.12 | 3 → 2.5 ms (13/3); 6 → 3.0 ms (13/11); 9 → 2.9 ms (13/11); 15 → 3.5 ms (13/11); 30 → 3.7 ms (13/11); all → 4.5 ms (13/12) |
| p31-mutable-default | 0.22 | 3 → 4.3 ms (12/9); 6 → 3.7 ms (12/10); 9 → 5.4 ms (12/10); 15 → 5.0 ms (12/10); 30 → 5.4 ms (12/10); all → 4.0 ms (12/11) |
| p32-load-bookkeeping | 0.18 | 3 → 3.3 ms (14/3); 6 → 4.0 ms (14/12); 9 → 4.3 ms (14/13) |
| p33-stale-cache | 0.20 | 3 → 2.3 ms (54/4); 6 → 2.7 ms (54/10); 9 → 3.1 ms (54/26); 15 → 3.4 ms (54/52); 30 → 4.0 ms (54/52); all → 3.9 ms (54/53) |
| p34-late-binding | 0.25 | 3 → 4.3 ms (15/3); 6 → 4.5 ms (15/13); 9 → 5.3 ms (15/13); 15 → 4.8 ms (15/13); 30 → 4.3 ms (15/13); all → 4.2 ms (15/14) |
