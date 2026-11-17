# qdebug evaluation: planner (tuned policy)

34 seeded bugs x 1 strategies x noise 0.0 (10 seeds per noise level > 0; noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate ε = 0.1. Questions are function-level oracle answers; line questions are zoom-mode answers.

## Per-strategy comparison

| strategy | noise | runs | function found | func. questions | line questions | true line in region | region size | tiers used | final tier % | monitored / total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| infogain | 0.0 | 34 | 100% | 3.4 | 3.5 | 85% | 1.0 | 1.9 | 14 | 12 / 23 |

## Per-bug results (noise 0.0)

| bug | buggy function | SBFL function rank | SBFL line rank | infogain: Q / found / line / tier |
|---|---|---|---|---|
| p01-dict-iteration | `Plan.drop_done` | 1 | 2 | 2+4 / ✓ / ✓ / 5% |
| p02-missing-return | `parse_duration` | 4 | 1 | 2+4 / ✓ / ✓ / 10% |
| p03-case-validation | `parse_line` | 2 | 4 | 4+5 / ✓ / ✓ / 10% |
| p04-unpack-split | `split_fields` | 2 | 3 | 1+2 / ✓ / ✓ / 5% |
| p05-untrimmed-deps | `parse_deps` | 4 | 29 | 1+3 / ✓ / ✓ / 10% |
| p06-empty-guard | `busiest` | 1 | 2 | 2+3 / ✓ / ✓ / 5% |
| p07-zero-division | `progress` | 1 | 2 | 1+3 / ✓ / ✓ / 5% |
| p08-missed-cycle | `find_cycle.<locals>.follow` | 2 | 8 | 3+4 / ✓ / ✓ / 10% |
| p09-weekend-boundary | `is_workday` | 1 | 1 | 2+1 / ✓ / ✓ / 5% |
| p10-loop-off-by-one | `add_workdays` | 1 | 3 | 5+6 / ✓ / ✓ / 5% |
| p11-range-end | `workdays_between` | 1 | 1 | 9+1 / ✓ / ✓ / 5% |
| p12-wrong-attribute | `earliest_start` | 1 | 1 | 1+4 / ✓ / ✓ / 5% |
| p13-wrong-variable | `build_schedule` | 1 | 2 | 1+6 / ✓ / ✓ / 5% |
| p14-wrong-method | `critical_path` | 1 | 7 | 1+5 / ✓ / ✓ / 5% |
| p15-swapped-arguments | `slack` | 1 | 3 | 5+4 / ✓ / ✓ / 50% |
| p16-partial-traversal | `order.<locals>.place` | 1 | 7 | 4+3 / ✓ / ✓ / 10% |
| p17-recursion-argument | `_collect_dependents` | 1 | 4 | 4+4 / ✓ / ✓ / 15% |
| p18-base-case | `depth` | 1 | 4 | 2+4 / ✓ / ✓ / 10% |
| p19-wrong-default | `load_by_owner` | 1 | 2 | 3+5 / ✓ / ✓ / 10% |
| p20-limit-boundary | `overloaded` | 1 | 1 | 2+2 / ✓ / ✓ / 5% |
| p21-truncation | `format_percent` | 1 | 1 | 1+1 / ✓ / ✓ / 5% |
| p22-sort-direction | `top_priorities` | 1 | 1 | 7+2 / ✓ / ✓ / 5% |
| p23-alignment | `summary_line` | 1 | 3 | 4+6 / ✓ / ✓ / 5% |
| p24-rounding-direction | `Estimator.buffer` | 1 | 1 | 3+2 / ✓ / ✓ / 15% |
| p25-boolean-logic | `Estimator.risk` | 1 | 3 | 3+3 / ✓ / ✓ / 10% |
| p26-tag-prefix | `parse_line` | 2 | 6 | 4+7 / ✓ / ✓ / 10% |
| p27-module-constant | `parse_duration` | 4 | - | 1+3 / ✓ / ✗ / 10% |
| p28-generator-numbering | `iter_lines` | None | 9 | 6+4 / ✓ / ✗ / 10% |
| p29-accumulator | `Plan.complete` | 1 | 5 | 3+4 / ✓ / ✓ / 5% |
| p30-shallow-clone | `Plan.clone` | 1 | 2 | 12+0 / ✓ / ✗ / 100% |
| p31-mutable-default | `owners_of` | 1 | - | 10+0 / ✓ / ✗ / 100% |
| p32-load-bookkeeping | `rebalance` | 1 | 3 | 4+5 / ✓ / ✓ / 10% |
| p33-stale-cache | `Estimator.effort` | 1 | 1 | 1+4 / ✓ / ✓ / 5% |
| p34-late-binding | `owner_views` | 2 | 7 | 3+6 / ✓ / ✗ / 10% |

Q is function-level + line-level questions; found = reported function is the buggy one; line = a true buggy line is inside the reported region.

## Per bug category (noise 0.0)

| category | bugs | infogain: found / line / mean Q |
|---|---|---|
| crash | 8 | 8/8 / 8/8 / 5.5 |
| state | 6 | 6/6 / 3/6 / 8.7 |
| wrong-value | 20 | 20/20 / 18/20 / 7.0 |

## Tracing cost per tier (failing test call only)

| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |
|---|---|---|
| p01-dict-iteration | 0.09 | 3 → 5.3 ms (13/4) |
| p02-missing-return | 0.13 | 3 → 4.8 ms (3/1); 6 → 3.6 ms (3/2) |
| p03-case-validation | 0.06 | 3 → 2.7 ms (5/3); 6 → 1.9 ms (5/4) |
| p04-unpack-split | 0.07 | 3 → 4.0 ms (3/2) |
| p05-untrimmed-deps | 0.21 | 3 → 4.2 ms (2/0); 6 → 12.7 ms (2/1) |
| p06-empty-guard | 0.10 | 3 → 2.3 ms (5/3) |
| p07-zero-division | 1.77 | 3 → 1.9 ms (4/3) |
| p08-missed-cycle | 0.20 | 3 → 5.3 ms (15/7); 6 → 5.3 ms (15/10) |
| p09-weekend-boundary | 0.19 | 3 → 3.8 ms (8/7) |
| p10-loop-off-by-one | 0.20 | 3 → 7.7 ms (10/9) |
| p11-range-end | 0.20 | 3 → 8.8 ms (17/16) |
| p12-wrong-attribute | 0.28 | 3 → 5.1 ms (2/1) |
| p13-wrong-variable | 0.44 | 3 → 6.9 ms (59/9) |
| p14-wrong-method | 0.31 | 3 → 4.1 ms (135/7) |
| p15-swapped-arguments | 0.30 | 3 → 7.9 ms (125/3); 6 → 9.4 ms (125/18); 9 → 18.9 ms (125/44); 15 → 11.9 ms (125/81); 30 → 16.5 ms (125/123) |
| p16-partial-traversal | 0.23 | 3 → 7.1 ms (39/10); 6 → 8.4 ms (39/31) |
| p17-recursion-argument | 0.39 | 3 → 6.4 ms (48/5); 6 → 3.3 ms (48/11); 9 → 3.3 ms (48/27) |
| p18-base-case | 0.20 | 3 → 4.4 ms (10/2); 6 → 4.8 ms (10/8) |
| p19-wrong-default | 0.31 | 3 → 6.3 ms (11/2); 6 → 6.9 ms (11/8) |
| p20-limit-boundary | 0.23 | 3 → 4.1 ms (11/3) |
| p21-truncation | 0.24 | 3 → 3.8 ms (2/1) |
| p22-sort-direction | 0.26 | 3 → 4.0 ms (47/7) |
| p23-alignment | 0.35 | 3 → 5.8 ms (5/4) |
| p24-rounding-direction | 0.27 | 3 → 4.5 ms (64/7); 6 → 4.0 ms (64/15); 9 → 4.0 ms (64/31) |
| p25-boolean-logic | 0.40 | 3 → 5.1 ms (12/3); 6 → 6.0 ms (12/8) |
| p26-tag-prefix | 0.21 | 3 → 4.6 ms (5/2); 6 → 7.0 ms (5/4) |
| p27-module-constant | 0.41 | 3 → 3.2 ms (2/0); 6 → 6.7 ms (2/1) |
| p28-generator-numbering | 0.30 | 3 → 4.9 ms (16/6); 6 → 4.8 ms (16/11) |
| p29-accumulator | 0.19 | 3 → 4.9 ms (12/6) |
| p30-shallow-clone | 0.18 | 3 → 2.8 ms (13/3); 6 → 4.1 ms (13/11); 9 → 4.2 ms (13/11); 15 → 3.7 ms (13/11); 30 → 3.6 ms (13/11); all → 3.4 ms (13/12) |
| p31-mutable-default | 0.23 | 3 → 5.4 ms (12/9); 6 → 6.8 ms (12/10); 9 → 5.9 ms (12/10); 15 → 5.9 ms (12/10); 30 → 6.8 ms (12/10); all → 5.1 ms (12/11) |
| p32-load-bookkeeping | 0.23 | 3 → 5.5 ms (14/3); 6 → 4.9 ms (14/12) |
| p33-stale-cache | 0.22 | 3 → 10.1 ms (54/4) |
| p34-late-binding | 0.30 | 3 → 5.8 ms (15/3); 6 → 11.0 ms (15/13) |
