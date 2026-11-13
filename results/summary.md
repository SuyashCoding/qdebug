# qdebug evaluation summary

5 seeded bugs x 4 strategies x noise 0.0, 0.1, 0.2 (10 seeds per noise level > 0; noise 0 is deterministic and run once). GroundTruthOracle, assumed error rate ε = 0.1. Questions are function-level oracle answers; line questions are zoom-mode answers.

## Per-strategy comparison

| strategy | noise | runs | function found | func. questions | line questions | true line in region | region size | tiers used | final tier % | monitored / total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| infogain | 0.0 | 5 | 100% | 6.8 | 3.8 | 100% | 1.0 | 4.2 | 37 | 26 / 35 |
| infogain-full | 0.0 | 5 | 100% | 13.6 | 3.8 | 100% | 1.0 | 4.6 | 52 | 30 / 35 |
| topdown | 0.0 | 5 | 100% | 11.8 | 3.8 | 100% | 1.0 | 5.2 | 60 | 34 / 35 |
| divide | 0.0 | 5 | 100% | 5.4 | 3.8 | 100% | 1.0 | 2.8 | 24 | 16 / 35 |
| infogain | 0.1 | 50 | 78% | 7.3 | 4.5 | 44% | 1.0 | 4.2 | 38 | 26 / 35 |
| infogain-full | 0.1 | 50 | 78% | 14.5 | 4.6 | 54% | 1.0 | 4.7 | 51 | 30 / 35 |
| topdown | 0.1 | 50 | 52% | 11.0 | 4.7 | 42% | 1.0 | 5.2 | 58 | 33 / 35 |
| divide | 0.1 | 50 | 82% | 4.9 | 4.3 | 46% | 1.0 | 2.8 | 23 | 15 / 35 |
| infogain | 0.2 | 50 | 54% | 8.1 | 4.4 | 26% | 1.0 | 4.5 | 42 | 28 / 35 |
| infogain-full | 0.2 | 50 | 62% | 14.9 | 4.3 | 32% | 1.0 | 4.8 | 53 | 31 / 35 |
| topdown | 0.2 | 50 | 28% | 8.4 | 3.8 | 18% | 1.0 | 5.2 | 59 | 33 / 35 |
| divide | 0.2 | 50 | 52% | 6.5 | 4.6 | 30% | 1.0 | 3.4 | 31 | 19 / 35 |

## Per-bug results (noise 0)

| bug | buggy function | SBFL function rank | SBFL line rank | infogain: Q / found / line / tier | infogain-full: Q / found / line / tier | topdown: Q / found / line / tier | divide: Q / found / line / tier |
|---|---|---|---|---|---|---|---|
| bug_01 | `quantity_discount_rate` | 3 | 9 | 2+2 / ✓ / ✓ / 25% | 6+2 / ✓ / ✓ / 50% | 6+2 / ✓ / ✓ / 50% | 2+2 / ✓ / ✓ / 10% |
| bug_02 | `cheapest_units` | 2 | 12 | 3+4 / ✓ / ✓ / 50% | 18+4 / ✓ / ✓ / 100% | 17+4 / ✓ / ✓ / 100% | 1+4 / ✓ / ✓ / 5% |
| bug_03 | `zone_for` | 1 | 1 | 2+3 / ✓ / ✓ / 10% | 3+3 / ✓ / ✓ / 10% | 9+3 / ✓ / ✓ / 50% | 2+3 / ✓ / ✓ / 5% |
| bug_04 | `build_invoice` | 7 | 49 | 21+7 / ✓ / ✓ / 50% | 25+7 / ✓ / ✓ / 50% | 19+7 / ✓ / ✓ / 50% | 17+7 / ✓ / ✓ / 50% |
| bug_05 | `Cart.total_weight` | 4 | 62 | 6+3 / ✓ / ✓ / 50% | 16+3 / ✓ / ✓ / 50% | 8+3 / ✓ / ✓ / 50% | 5+3 / ✓ / ✓ / 50% |

Q is function-level + line-level questions; found = reported function is the buggy one; line = a true buggy line is inside the reported region.

## Robustness per bug (function found rate under noise)

| bug | infogain @ 0.1 | infogain-full @ 0.1 | topdown @ 0.1 | divide @ 0.1 | infogain @ 0.2 | infogain-full @ 0.2 | topdown @ 0.2 | divide @ 0.2 |
|---|---|---|---|---|---|---|---|---|
| bug_01 | 90% | 80% | 40% | 90% | 50% | 60% | 30% | 40% |
| bug_02 | 80% | 80% | 60% | 100% | 50% | 40% | 20% | 70% |
| bug_03 | 100% | 100% | 50% | 90% | 80% | 90% | 40% | 80% |
| bug_04 | 60% | 60% | 60% | 50% | 50% | 50% | 20% | 30% |
| bug_05 | 60% | 70% | 50% | 80% | 40% | 70% | 30% | 40% |

## Tracing cost per tier (failing test call only)

| bug | untraced ms | tier runs: monitored functions → traced ms (calls / monitored calls) |
|---|---|---|
| bug_01 | 0.19 | 2 → 3.9 ms (24/2); 4 → 3.1 ms (24/6); 6 → 3.9 ms (24/8); 10 → 3.6 ms (24/12); 20 → 3.8 ms (24/23) |
| bug_02 | 0.18 | 2 → 3.6 ms (58/2); 4 → 3.8 ms (58/4); 6 → 5.2 ms (58/8); 10 → 4.3 ms (58/12); 20 → 4.8 ms (58/45); all → 7.7 ms (58/57) |
| bug_03 | 0.19 | 2 → 3.8 ms (23/4); 4 → 3.9 ms (23/6); 6 → 3.7 ms (23/8); 10 → 4.0 ms (23/12); 20 → 4.7 ms (23/22) |
| bug_04 | 0.19 | 2 → 3.6 ms (45/2); 4 → 3.8 ms (45/4); 6 → 4.2 ms (45/7); 10 → 4.3 ms (45/11); 20 → 5.0 ms (45/44) |
| bug_05 | 0.18 | 2 → 4.4 ms (23/2); 4 → 4.3 ms (23/4); 6 → 3.8 ms (23/6); 10 → 4.1 ms (23/10); 20 → 4.3 ms (23/22) |
