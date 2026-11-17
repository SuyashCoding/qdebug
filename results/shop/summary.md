# qdebug evaluation: shop (tuned policy)

5 seeded bugs x 3 strategies x noise 0.0, 0.1, 0.2 (10 seeds per noise level > 0; noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate ε = 0.1. Questions are function-level oracle answers; line questions are zoom-mode answers.

## Per-strategy comparison

| strategy | noise | runs | function found | func. questions | line questions | true line in region | region size | tiers used | final tier % | monitored / total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| infogain | 0.0 | 5 | 100% | 5.4 | 4.2 | 100% | 1.0 | 4.0 | 53 | 34 / 35 |
| divide | 0.0 | 5 | 100% | 5.2 | 4.2 | 100% | 1.0 | 3.0 | 34 | 20 / 35 |
| topdown | 0.0 | 5 | 100% | 11.0 | 4.2 | 100% | 1.0 | 5.2 | 82 | 34 / 35 |
| infogain | 0.1 | 50 | 80% | 7.1 | 5.2 | 56% | 1.0 | 4.0 | 54 | 34 / 35 |
| divide | 0.1 | 50 | 80% | 5.2 | 4.0 | 44% | 1.0 | 3.0 | 33 | 19 / 35 |
| topdown | 0.1 | 50 | 60% | 7.8 | 3.4 | 30% | 1.0 | 5.2 | 82 | 34 / 35 |
| infogain | 0.2 | 50 | 60% | 9.6 | 3.9 | 28% | 1.0 | 4.4 | 63 | 34 / 35 |
| divide | 0.2 | 50 | 54% | 5.9 | 3.6 | 26% | 1.0 | 3.4 | 40 | 20 / 35 |
| topdown | 0.2 | 50 | 36% | 6.5 | 2.4 | 20% | 1.0 | 5.2 | 82 | 34 / 35 |

## Per-bug results (noise 0.0)

| bug | buggy function | SBFL function rank | SBFL line rank | infogain: Q / found / line / tier | divide: Q / found / line / tier | topdown: Q / found / line / tier |
|---|---|---|---|---|---|---|
| bug_01 | `quantity_discount_rate` | 3 | 9 | 1+3 / ✓ / ✓ / 10% | 2+3 / ✓ / ✓ / 10% | 2+3 / ✓ / ✓ / 10% |
| bug_02 | `cheapest_units` | 2 | 12 | 5+4 / ✓ / ✓ / 100% | 1+4 / ✓ / ✓ / 5% | 20+4 / ✓ / ✓ / 100% |
| bug_03 | `zone_for` | 1 | 1 | 1+3 / ✓ / ✓ / 5% | 1+3 / ✓ / ✓ / 5% | 2+3 / ✓ / ✓ / 100% |
| bug_04 | `build_invoice` | 7 | 49 | 12+8 / ✓ / ✓ / 100% | 17+8 / ✓ / ✓ / 100% | 21+8 / ✓ / ✓ / 100% |
| bug_05 | `Cart.total_weight` | 4 | 62 | 8+3 / ✓ / ✓ / 50% | 5+3 / ✓ / ✓ / 50% | 10+3 / ✓ / ✓ / 100% |

Q is function-level + line-level questions; found = reported function is the buggy one; line = a true buggy line is inside the reported region.

## Per bug category (noise 0.0)

| category | bugs | infogain: found / line / mean Q | divide: found / line / mean Q | topdown: found / line / mean Q |
|---|---|---|---|---|
| state | 1 | 1/1 / 1/1 / 9.0 | 1/1 / 1/1 / 5.0 | 1/1 / 1/1 / 24.0 |
| wrong-value | 4 | 4/4 / 4/4 / 9.8 | 4/4 / 4/4 / 10.5 | 4/4 / 4/4 / 13.0 |

## Robustness per bug (function found rate under noise)

| bug | infogain @ 0.1 | divide @ 0.1 | topdown @ 0.1 | infogain @ 0.2 | divide @ 0.2 | topdown @ 0.2 |
|---|---|---|---|---|---|---|
| bug_01 | 100% | 90% | 90% | 80% | 40% | 40% |
| bug_02 | 60% | 100% | 30% | 60% | 70% | 10% |
| bug_03 | 100% | 100% | 100% | 100% | 100% | 100% |
| bug_04 | 70% | 40% | 20% | 30% | 20% | 10% |
| bug_05 | 70% | 70% | 60% | 30% | 40% | 20% |

## Tracing cost per tier (failing test call only)

| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |
|---|---|---|
| bug_01 | 0.18 | 2 → 2.2 ms (4/1); 4 → 3.8 ms (4/3) |
| bug_02 | 0.21 | 2 → 2.7 ms (73/2); 4 → 2.9 ms (73/4); 6 → 3.3 ms (73/8); 10 → 3.7 ms (73/12); 20 → 5.2 ms (73/45); all → 6.1 ms (73/72) |
| bug_03 | 0.35 | 2 → 2.9 ms (3/1); 4 → 3.7 ms (3/1); 6 → 3.5 ms (3/1); 10 → 3.5 ms (3/1); 20 → 2.3 ms (3/1); all → 2.8 ms (3/2) |
| bug_04 | 0.20 | 2 → 2.2 ms (59/2); 4 → 2.7 ms (59/4); 6 → 2.9 ms (59/7); 10 → 2.6 ms (59/11); 20 → 3.0 ms (59/37); all → 4.4 ms (59/58) |
| bug_05 | 0.21 | 2 → 2.2 ms (37/2); 4 → 2.8 ms (37/4); 6 → 3.6 ms (37/6); 10 → 2.6 ms (37/10); 20 → 3.0 ms (37/34); all → 2.7 ms (37/36) |
