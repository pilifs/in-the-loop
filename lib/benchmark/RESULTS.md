# Benchmark results

Written by `lib/benchmark/run.py` on 2026-11-06T07:22:03-0500, on 8 × - (aarch64), with jvmcontract 0.1.0, JBMC 6.11.0 (cbmc-6.11.0) and openjdk version "25.0.4.1" 2026-08-18 LTS. Every run had a deadline of 120 s, loops unwound 16 times and arrays of up to 8 elements, on both engines. What the columns mean is in [README.md](README.md).

## Correctness and coverage

| group | engine | mode | cases | correct | of them assuming a gap | unsupported | false success | false alarm | total s | median s | max s | peak MB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 semantic conformance | native | strict | 93 | 82 | 0 | 11 | 0 | 0 | 6.6 | 0.07 | 0.17 | 37.6 |
| 1 semantic conformance | native | assume | 93 | 83 | 1 | 3 | 7 (7 naming a gap) | 0 | 6.3 | 0.06 | 0.17 | 37.6 |
| 1 semantic conformance | native | advised | 93 | 87 | 0 | 6 | 0 | 0 | 7.6 | 0.08 | 0.17 | 43.2 |
| 1 semantic conformance | jbmc | strict | 93 | 79 | 0 | 14 | 0 | 0 | 146.8 | 0.27 | 120.09 | 49.9 |
| 1 semantic conformance | jbmc | assume | 93 | 81 | 3 | 4 | 8 (8 naming a gap) | 0 | 147.3 | 0.27 | 120.06 | 50.0 |
| 1 semantic conformance | jbmc | advised | 93 | 84 | 0 | 9 | 0 | 0 | 148.4 | 0.28 | 120.09 | 44.6 |
| 2 real regressions | native | strict | 13 | 12 | 0 | 1 | 0 | 0 | 124.7 | 0.11 | 120.09 | 76.3 |
| 2 real regressions | native | assume | 13 | 12 | 0 | 1 | 0 | 0 | 124.8 | 0.09 | 120.1 | 70.5 |
| 2 real regressions | native | advised | 13 | 12 | 0 | 1 | 0 | 0 | 124.7 | 0.11 | 120.11 | 82.9 |
| 2 real regressions | jbmc | strict | 13 | 12 | 0 | 1 | 0 | 0 | 201.2 | 0.46 | 120.1 | 1386.8 |
| 2 real regressions | jbmc | assume | 13 | 12 | 0 | 1 | 0 | 0 | 202.1 | 0.51 | 120.1 | 1386.9 |
| 2 real regressions | jbmc | advised | 13 | 12 | 0 | 1 | 0 | 0 | 200.5 | 0.46 | 120.14 | 1386.9 |
| 3 held-out performance cases | native | strict | 12 | 12 | 0 | 0 | 0 | 0 | 2.9 | 0.16 | 0.82 | 42.8 |
| 3 held-out performance cases | native | assume | 12 | 12 | 0 | 0 | 0 | 0 | 2.7 | 0.1 | 0.79 | 42.5 |
| 3 held-out performance cases | native | advised | 12 | 12 | 0 | 0 | 0 | 0 | 2.9 | 0.14 | 0.8 | 46.9 |
| 3 held-out performance cases | jbmc | strict | 12 | 9 | 0 | 3 | 0 | 0 | 286.4 | 2.82 | 120.11 | 3367.8 |
| 3 held-out performance cases | jbmc | assume | 12 | 9 | 0 | 3 | 0 | 0 | 279.7 | 2.82 | 120.09 | 3367.8 |
| 3 held-out performance cases | jbmc | advised | 12 | 9 | 0 | 3 | 0 | 0 | 281.1 | 2.97 | 120.11 | 3367.9 |
| 4 recorded examples | native | strict | 2 | 2 | 0 | 0 | 0 | 0 | 9.4 | 4.69 | 7.19 | 82.1 |
| 4 recorded examples | jbmc | strict | 2 | 1 | 0 | 1 | 0 | 0 | 79.0 | 39.52 | 65.17 | 3407.7 |

Why the unsupported cases had no verdict:

- group 1, native, strict: 8 gap, 3 refused
- group 1, native, assume: 3 refused
- group 1, native, advised: 4 needs contracts, 2 refused
- group 1, jbmc, strict: 11 gap, 2 witness not reproduced, 1 out of time
- group 1, jbmc, assume: 3 witness not reproduced, 1 out of time
- group 1, jbmc, advised: 5 gap, 2 witness not reproduced, 1 needs contracts, 1 out of time
- group 2, native, strict: 1 out of time
- group 2, native, assume: 1 out of time
- group 2, native, advised: 1 out of time
- group 2, jbmc, strict: 1 out of time
- group 2, jbmc, assume: 1 out of time
- group 2, jbmc, advised: 1 out of time
- group 3, jbmc, strict: 2 out of time, 1 out of memory
- group 3, jbmc, assume: 2 out of time, 1 out of memory
- group 3, jbmc, advised: 2 out of time, 1 out of memory
- group 4, jbmc, strict: 1 out of memory

## By workload, under strict

| workload | engine | cases | correct | unsupported | wrong | median s (decided) | max s | peak MB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| array-bounds | native | 3 | 3 | 0 | 0 | 0.08 | 0.69 | 37.6 |
| array-bounds | jbmc | 3 | 3 | 0 | 0 | 0.46 | 18.46 | 368.3 |
| array-mutation | native | 2 | 2 | 0 | 0 | 0.21 | 0.21 | 37.2 |
| array-mutation | jbmc | 2 | 1 | 1 | 0 | 4.65 | 15.89 | 3367.8 |
| binary-search | native | 3 | 3 | 0 | 0 | 2.19 | 2.8 | 67.6 |
| binary-search | jbmc | 3 | 3 | 0 | 0 | 58.58 | 65.17 | 2066.2 |
| div-rem | native | 9 | 8 | 1 | 0 | 0.11 | 120.09 | 76.3 |
| div-rem | jbmc | 9 | 6 | 3 | 0 | 0.42 | 120.11 | 51.1 |
| records | native | 2 | 2 | 0 | 0 | 0.15 | 0.17 | 35.7 |
| records | jbmc | 2 | 2 | 0 | 0 | 0.55 | 0.56 | 36.0 |
| scalar-arithmetic | native | 6 | 6 | 0 | 0 | 0.09 | 0.26 | 35.1 |
| scalar-arithmetic | jbmc | 6 | 6 | 0 | 0 | 0.32 | 0.48 | 35.5 |
| semantics | native | 93 | 82 | 11 | 0 | 0.07 | 0.17 | 37.6 |
| semantics | jbmc | 93 | 79 | 14 | 0 | 0.27 | 120.09 | 49.9 |
| utf8 | native | 2 | 2 | 0 | 0 | 3.83 | 7.19 | 82.1 |
| utf8 | jbmc | 2 | 1 | 1 | 0 | 0.99 | 13.88 | 3407.7 |

## Where the time goes, by workload, under strict

Each engine's seconds over every run of the workload, decided or not, as shares of the phases of `lib/src/phases.rs`: the checker's own (`loading` to `trace`, and `checker-other`, JBMC starting and printing), then the driver's (`gaps` and JBMC's preflight, `contracts`, `replay` and shrinking, the `jvm` witness run, the `harness`, the `setup` of the work directory with the JDK's classes and the models, and the rest of the process as `driver`). Step 5b of the sound-verdicts brief.

| workload | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| array-bounds | native | 3 | 0.83 | · | · | 6% | 6% | 63% | 0% | · | · | · | 0% | · | · | 5% | 20% | **solving** 63% | 45662 |
| array-bounds | jbmc | 3 | 19.36 | 0% | 0% | 2% | 4% | 92% | 0% | 1% | 1% | · | 0% | · | · | 0% | 0% | **solving** 92% | 762544 |
| array-mutation | native | 2 | 0.41 | · | · | 3% | 5% | 27% | · | · | · | · | · | · | · | 9% | 56% | **driver** 56% | 59707 |
| array-mutation | jbmc | 2 (1 undecided) | 20.54 | 0% | 0% | 2% | 40% | 87% | · | · | 1% | · | · | · | · | 0% | · | **solving** 87% | 17233885 |
| binary-search | native | 2 | 3.2 | · | · | 3% | 3% | 87% | · | · | · | · | · | · | · | 1% | 6% | **solving** 87% | 240144 |
| binary-search | jbmc | 2 | 65.79 | 0% | 0% | 1% | 4% | 95% | 0% | 0% | 0% | · | · | · | · | 0% | 0% | **solving** 95% | 3281450 |
| div-rem | native | 9 (1 undecided) | 121.66 | 0% | · | 0% | · | 99% | 0% | · | · | · | 0% | · | 0% | 0% | 1% | **solving** 99% | 55638 |
| div-rem | jbmc | 9 (3 undecided) | 377.75 | 0% | 0% | 0% | 0% | 99% | 0% | 0% | 0% | · | 0% | · | · | 0% | 0% | **solving** 99% | 49832 |
| records | native | 2 | 0.29 | 1% | · | 1% | · | 1% | 0% | · | · | · | 9% | · | · | 15% | 72% | **driver** 72% | 7451 |
| records | jbmc | 2 | 1.09 | 16% | 4% | 6% | 2% | 10% | 1% | 23% | 16% | · | 0% | · | · | 3% | 19% | **checker-other** 23% | 13325 |
| scalar-arithmetic | native | 6 | 0.79 | 0% | · | 3% | · | 19% | · | · | · | · | 0% | · | · | 17% | 61% | **driver** 61% | 20540 |
| scalar-arithmetic | jbmc | 6 | 2.06 | 6% | 2% | 2% | 2% | 7% | 0% | 26% | 23% | · | 0% | · | · | 5% | 26% | **checker-other** 26% | 4914 |
| semantics | native | 93 (11 undecided) | 6.6 | 0% | · | 2% | · | 1% | 0% | · | · | · | 0% | · | · | 25% | 72% | **driver** 72% | 100555 |
| semantics | jbmc | 93 (14 undecided) | 146.79 | 4% | 1% | 0% | 0% | 82% | 0% | 4% | 5% | · | 0% | · | 0% | 1% | 3% | **solving** 82% | 49726 |
| utf8 | native | 1 | 0.47 | · | · | · | 24% | 59% | · | · | · | · | · | · | · | 3% | 14% | **solving** 59% | 23224 |
| utf8 | jbmc | 1 | 0.99 | 1% | 0% | 8% | 5% | 72% | · | 1% | 7% | · | · | · | · | 1% | 6% | **solving** 72% | 173454 |

### The recorded examples

| id | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| example/141 | native | 1 | 2.19 | · | · | 2% | 4% | 88% | · | · | · | · | · | · | · | 1% | 6% | **solving** 88% | 137013 |
| example/141 | jbmc | 1 | 65.17 | 0% | 0% | 1% | 6% | 94% | 0% | 0% | 0% | · | · | · | · | 0% | · | **solving** 94% | 4718689 |
| example/142 | native | 1 | 7.19 | 0% | · | 1% | 3% | 94% | · | · | · | · | · | · | · | 0% | 2% | **solving** 94% | 161165 |
| example/142 | jbmc | 1 (1 undecided) | 13.88 | 0% | 0% | 6% | 1% | 62% | · | 29% | 1% | · | · | · | · | 0% | 1% | **solving** 62% | – |

## Group 1: semantic conformance, case by case

The JVM's answer is the conformance test's (`lib/tests/conformance.rs`), on the calls the corpus lists.

<details><summary>All 93 claims</summary>

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `conformance/capacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.05 s | ✓ violation 0.09 s | – gap 0.3 s | ✗ₐ verified 0.28 s | ✓ violation 0.33 s |
| `conformance/builderCapacity/1` | violation | conformance test | – gap 0.1 s | ✗ₐ verified 0.05 s | ✓ violation 0.09 s | – gap 0.3 s | ✗ₐ verified 0.27 s | ✓ violation 0.33 s |
| `conformance/mapCapacity/1` | violation | conformance test | – gap 0.1 s | ✗ₐ verified 0.04 s | ✓ violation 0.10 s | – gap 0.3 s | ✗ₐ verified 0.26 s | ✓ violation 0.32 s |
| `conformance/setCapacity/1` | violation | conformance test | – gap 0.1 s | ✗ₐ verified 0.06 s | ✓ violation 0.09 s | – gap 0.3 s | ✗ₐ verified 0.26 s | ✓ violation 0.38 s |
| `conformance/loadFactor/1` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | ✗ₐ verified 0.27 s | – needs contracts 0.1 s |
| `conformance/nullMonitor/1` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.10 s | – gap 0.3 s | ✗ₐ verified 0.28 s | – gap 0.3 s |
| `conformance/monitor/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.06 s | – gap 0.3 s | ✓ₐ verified 0.27 s | – gap 0.3 s |
| `conformance/firstByte/1` | violation | conformance test | – gap 0.1 s | ✗ₐ verified 0.05 s | ✓ violation 0.12 s | – gap 0.2 s | ✗ₐ verified 0.16 s | ✓ violation 0.34 s |
| `conformance/hiding/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.28 s |
| `conformance/hiding/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.18 s | ✓ violation 0.19 s |
| `conformance/hidden/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.28 s |
| `conformance/hidden/2` | violation | conformance test | ✓ violation 0.09 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.18 s | ✓ violation 0.17 s | ✓ violation 0.19 s |
| `conformance/sameLiteral/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.29 s |
| `conformance/sameLiteral/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.17 s | ✓ violation 0.17 s | ✓ violation 0.18 s |
| `conformance/otherLiteral/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.26 s |
| `conformance/otherLiteral/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.18 s | ✓ violation 0.19 s |
| `conformance/sameClass/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.28 s |
| `conformance/sameClass/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.06 s | ✓ violation 0.08 s | ✓ violation 0.19 s | ✓ violation 0.18 s | ✓ violation 0.20 s |
| `conformance/concatenated/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.07 s | – gap 0.3 s | ✓ₐ verified 0.27 s | – gap 0.3 s |
| `conformance/concatenated/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.17 s | ✓ₐ violation 0.18 s | ✓ violation 0.19 s |
| `conformance/boom/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.05 s | – needs contracts 0.1 s | ✓ violation 0.18 s | ✓ violation 0.24 s | ✓ violation 0.19 s |
| `conformance/inherited/1` | violation | conformance test | – gap 0.1 s | ✗ₐ verified 0.05 s | – needs contracts 0.1 s | ✓ violation 0.18 s | ✓ violation 0.17 s | ✓ violation 0.18 s |
| `conformance/quiet/1` | verified | conformance test | – gap 0.1 s | ✓ₐ verified 0.05 s | – needs contracts 0.0 s | ✓ verified 0.27 s | ✓ verified 0.28 s | ✓ verified 0.29 s |
| `conformance/finallyWins/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.07 s | ✓ verified 0.33 s | ✓ verified 0.26 s | ✓ verified 0.28 s |
| `conformance/finallyWins/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.10 s | ✓ violation 0.19 s | ✓ violation 0.18 s | ✓ violation 0.20 s |
| `conformance/caught/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/caught/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.18 s | ✓ violation 0.18 s | ✓ violation 0.19 s |
| `conformance/nestedHandler/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.05 s | ✓ verified 0.06 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/nestedHandler/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.09 s | ✓ violation 0.18 s | ✓ violation 0.19 s | ✓ violation 0.19 s |
| `conformance/element/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.37 s | ✓ verified 0.31 s | ✓ verified 0.42 s |
| `conformance/element/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.19 s | ✓ violation 0.17 s | ✓ violation 0.18 s |
| `conformance/cast/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.28 s |
| `conformance/cast/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.18 s | ✓ violation 0.18 s | ✓ violation 0.20 s |
| `conformance/throwNull/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.28 s | ✓ verified 0.27 s |
| `conformance/throwNull/2` | violation | conformance test | ✓ violation 0.08 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.19 s | ✓ violation 0.17 s | ✓ violation 0.18 s |
| `conformance/rethrown/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.28 s |
| `conformance/rethrown/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.23 s | ✓ violation 0.24 s | ✓ violation 0.24 s |
| `conformance/aliasedLocals/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.28 s |
| `conformance/aliasedLocals/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.18 s | ✓ violation 0.19 s | ✓ violation 0.20 s |
| `conformance/aliasedObjects/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.28 s |
| `conformance/aliasedObjects/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.06 s | ✓ violation 0.09 s | ✓ violation 0.18 s | ✓ violation 0.18 s | ✓ violation 0.18 s |
| `conformance/twoArrays/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.08 s | ✓ verified 0.17 s | ✓ verified 0.16 s | ✓ verified 0.17 s |
| `conformance/writeThrough/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/length/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.15 s | ✓ verified 0.16 s | ✓ verified 0.16 s |
| `conformance/lengthOrMinusOne/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.16 s | ✓ verified 0.15 s | ✓ verified 0.17 s |
| `conformance/nullLocal/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.28 s |
| `conformance/nullLocal/2` | violation | conformance test | ✓ violation 0.09 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.19 s | ✓ violation 0.19 s | ✓ violation 0.20 s |
| `conformance/width/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.33 s | ✓ verified 0.36 s | ✓ verified 0.39 s |
| `conformance/width/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.09 s | ✓ violation 0.29 s | ✓ violation 0.29 s | ✓ violation 0.30 s |
| `conformance/width/3` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.08 s | ✓ violation 0.19 s | ✓ violation 0.17 s | ✓ violation 0.19 s |
| `conformance/clamp/1` | verified | conformance test | ✓ verified 0.07 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.27 s |
| `conformance/clamp/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.23 s | ✓ violation 0.24 s | ✓ violation 0.23 s |
| `conformance/pairsEqual/1` | verified | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.1 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s |
| `conformance/pairsEqual/2` | violation | conformance test | – refused 0.0 s | – refused 0.1 s | – refused 0.1 s | – gap 0.3 s | ✗ₐ verified 0.28 s | – gap 0.3 s |
| `conformance/sides/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.33 s |
| `conformance/sides/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.18 s | ✓ violation 0.19 s |
| `conformance/code/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.29 s |
| `conformance/code/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.18 s | ✓ violation 0.19 s | ✓ violation 0.18 s |
| `conformance/divide/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.08 s | ✓ verified 0.28 s | ✓ verified 0.32 s | ✓ verified 0.28 s |
| `conformance/divide/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.30 s | ✓ violation 0.30 s | ✓ violation 0.29 s |
| `conformance/divide/3` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `conformance/divide/4` | violation | conformance test | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.12 s | ✓ violation 0.27 s | ✓ violation 0.28 s | ✓ violation 0.24 s |
| `conformance/divideLong/1` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.10 s | ✓ violation 0.53 s | ✓ violation 0.52 s | ✓ violation 0.60 s |
| `conformance/divideLong/2` | verified | conformance test | ✓ verified 0.16 s | ✓ verified 0.08 s | ✓ verified 0.10 s | ✓ verified 0.52 s | ✓ verified 0.54 s | ✓ verified 0.53 s |
| `conformance/remainder/1` | verified | conformance test | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.11 s | ✓ verified 0.65 s | ✓ verified 0.56 s | ✓ verified 0.68 s |
| `conformance/remainder/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.09 s | ✓ violation 0.11 s | ✓ violation 0.31 s | ✓ violation 0.30 s | ✓ violation 0.35 s |
| `conformance/remainder/3` | verified | conformance test | ✓ verified 0.07 s | ✓ verified 0.07 s | ✓ verified 0.06 s | ✓ verified 0.38 s | ✓ verified 0.56 s | ✓ verified 0.41 s |
| `conformance/remainderLong/1` | verified | conformance test | ✓ verified 0.14 s | ✓ verified 0.09 s | ✓ verified 0.10 s | ✓ verified 0.63 s | ✓ verified 0.53 s | ✓ verified 0.38 s |
| `conformance/remainderLong/2` | violation | conformance test | ✓ violation 0.13 s | ✓ violation 0.12 s | ✓ violation 0.13 s | ✓ violation 0.33 s | ✓ violation 0.43 s | ✓ violation 0.48 s |
| `conformance/shiftLeft/1` | verified | conformance test | ✓ verified 0.09 s | ✓ verified 0.07 s | ✓ verified 0.10 s | ✓ verified 0.62 s | ✓ verified 0.46 s | ✓ verified 0.47 s |
| `conformance/shiftLeft/2` | violation | conformance test | ✓ violation 0.09 s | ✓ violation 0.15 s | ✓ violation 0.12 s | ✓ violation 0.26 s | ✓ violation 0.33 s | ✓ violation 0.25 s |
| `conformance/shiftLeft/3` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.07 s | ✓ verified 0.11 s | ✓ verified 0.52 s | ✓ verified 0.41 s | ✓ verified 0.59 s |
| `conformance/shiftLeftLong/1` | verified | conformance test | ✓ verified 0.10 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.49 s | ✓ verified 0.40 s | ✓ verified 0.49 s |
| `conformance/shiftLeftLong/2` | violation | conformance test | ✓ violation 0.10 s | ✓ violation 0.11 s | ✓ violation 0.08 s | ✓ violation 0.50 s | ✓ violation 0.33 s | ✓ violation 0.39 s |
| `conformance/shiftLeftLong/3` | verified | conformance test | ✓ verified 0.10 s | ✓ verified 0.10 s | ✓ verified 0.09 s | ✓ verified 0.39 s | ✓ verified 0.50 s | ✓ verified 0.66 s |
| `conformance/shiftRight/1` | verified | conformance test | ✓ verified 0.08 s | ✓ verified 0.05 s | ✓ verified 0.10 s | ✓ verified 0.38 s | ✓ verified 0.44 s | ✓ verified 0.35 s |
| `conformance/shiftRight/2` | violation | conformance test | ✓ violation 0.12 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.43 s | ✓ violation 0.32 s | ✓ violation 0.36 s |
| `conformance/shiftUnsigned/1` | violation | conformance test | ✓ violation 0.17 s | ✓ violation 0.17 s | ✓ violation 0.10 s | ✓ violation 0.25 s | ✓ violation 0.41 s | ✓ violation 0.38 s |
| `conformance/shiftUnsigned/2` | verified | conformance test | ✓ verified 0.08 s | ✓ verified 0.06 s | ✓ verified 0.09 s | ✓ verified 0.43 s | ✓ verified 0.63 s | ✓ verified 0.51 s |
| `conformance/square/1` | violation | conformance test | ✓ violation 0.09 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.25 s | ✓ violation 0.37 s | ✓ violation 0.36 s |
| `conformance/negate/1` | violation | conformance test | ✓ violation 0.11 s | ✓ violation 0.12 s | ✓ violation 0.08 s | ✓ violation 0.41 s | ✓ violation 0.55 s | ✓ violation 0.46 s |
| `conformance/toByte/1` | violation | conformance test | ✓ violation 0.10 s | ✓ violation 0.10 s | ✓ violation 0.09 s | ✓ violation 0.35 s | ✓ violation 0.43 s | ✓ violation 0.34 s |
| `conformance/toByte/2` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.47 s | ✓ verified 0.31 s | ✓ verified 0.47 s |
| `conformance/toChar/1` | verified | conformance test | ✓ verified 0.09 s | ✓ verified 0.09 s | ✓ verified 0.10 s | ✓ verified 0.39 s | ✓ verified 0.35 s | ✓ verified 0.28 s |
| `conformance/toChar/2` | violation | conformance test | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.45 s | ✓ violation 0.39 s | ✓ violation 0.56 s |
| `conformance/toShort/1` | verified | conformance test | ✓ verified 0.10 s | ✓ verified 0.05 s | ✓ verified 0.15 s | ✓ verified 0.33 s | ✓ verified 0.46 s | ✓ verified 0.34 s |
| `conformance/fromLong/1` | violation | conformance test | ✓ violation 0.09 s | ✓ violation 0.08 s | ✓ violation 0.17 s | ✓ violation 0.44 s | ✓ violation 0.44 s | ✓ violation 0.43 s |
| `conformance/nextChar/1` | verified | conformance test | ✓ verified 0.11 s | ✓ verified 0.09 s | ✓ verified 0.08 s | ✓ verified 0.23 s | ✓ verified 0.28 s | ✓ verified 0.24 s |
| `conformance/nextChar/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.18 s | ✓ violation 0.20 s | ✓ violation 0.33 s |
| `conformance/absolute/1` | violation | conformance test | ✓ violation 0.10 s | ✓ violation 0.10 s | ✓ violation 0.16 s | ✓ violation 0.49 s | ✓ violation 0.46 s | ✓ violation 0.57 s |
| `conformance/increment/1` | verified | conformance test | ✓ verified 0.09 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.43 s | ✓ verified 0.44 s | ✓ verified 0.51 s |
| `conformance/byteSum/1` | verified | conformance test | ✓ verified 0.08 s | ✓ verified 0.08 s | ✓ verified 0.11 s | ✓ verified 0.35 s | ✓ verified 0.49 s | ✓ verified 0.31 s |
| `conformance/byteSum/2` | violation | conformance test | ✓ violation 0.08 s | ✓ violation 0.06 s | ✓ violation 0.10 s | ✓ violation 0.26 s | ✓ violation 0.38 s | ✓ violation 0.37 s |

</details>

## Group 2: real regressions, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `real/midpoint/broken-property` | violation | refuted returns -1073741824 | ✓ violation 0.26 s | ✓ violation 0.17 s | ✓ violation 0.18 s | ✓ violation 0.35 s | ✓ violation 0.46 s | ✓ violation 0.46 s |
| `real/midpoint/fixed-property` | verified | held 40579 | ✓ verified 0.06 s | ✓ verified 0.05 s | ✓ verified 0.07 s | ✓ verified 0.39 s | ✓ verified 0.33 s | ✓ verified 0.40 s |
| `real/midpoint/fix-confined` | verified | held 35564 | ✓ verified 0.20 s | ✓ verified 0.13 s | ✓ verified 0.14 s | ✓ verified 0.48 s | ✓ verified 0.51 s | ✓ verified 0.43 s |
| `real/midpoint/search-within-bound` | verified | held 200000 | ✓ verified 2.80 s | ✓ verified 3.08 s | ✓ verified 2.85 s | ✓ verified 58.58 s | ✓ verified 59.73 s | ✓ verified 58.68 s |
| `real/bucket/broken-property` | violation | refuted returns -2 | ✓ violation 0.15 s | ✓ violation 0.09 s | ✓ violation 0.11 s | ✓ violation 0.38 s | ✓ violation 0.52 s | ✓ violation 0.50 s |
| `real/bucket/fixed-property` | verified | held 122010 | ✓ verified 0.07 s | ✓ verified 0.07 s | ✓ verified 0.08 s | ✓ verified 0.46 s | ✓ verified 0.41 s | ✓ verified 0.30 s |
| `real/bucket/fix-confined` | verified | held 127354 | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `real/oddity/broken-property` | violation | refuted returns false | ✓ violation 0.09 s | ✓ violation 0.08 s | ✓ violation 0.09 s | ✓ violation 0.30 s | ✓ violation 0.32 s | ✓ violation 0.30 s |
| `real/oddity/fixed-property` | verified | held 200017 | ✓ verified 0.06 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.35 s | ✓ verified 0.42 s | ✓ verified 0.32 s |
| `real/oddity/fix-confined` | verified | held 127076 | ✓ verified 0.11 s | ✓ verified 0.11 s | ✓ verified 0.20 s | ✓ verified 0.47 s | ✓ verified 0.42 s | ✓ verified 0.42 s |
| `real/checksum/broken-property` | violation | refuted returns 0 | ✓ violation 0.08 s | ✓ violation 0.09 s | ✓ violation 0.10 s | ✓ violation 0.44 s | ✓ violation 0.55 s | ✓ violation 0.46 s |
| `real/checksum/fixed-property` | verified | held 200000 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.46 s | ✓ verified 0.57 s | ✓ verified 0.48 s |
| `real/checksum/fix-confined` | verified | held 190209 | ✓ verified 0.69 s | ✓ verified 0.72 s | ✓ verified 0.66 s | ✓ verified 18.46 s | ✓ verified 17.75 s | ✓ verified 17.59 s |

## Group 3: held-out performance cases, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `held/saturating` | verified | held 200289 | ✓ verified 0.08 s | ✓ verified 0.07 s | ✓ verified 0.09 s | ✓ verified 0.30 s | ✓ verified 0.31 s | ✓ verified 0.40 s |
| `held/average/bits` | verified | held 200289 | ✓ verified 0.08 s | ✓ verified 0.09 s | ✓ verified 0.09 s | ✓ verified 0.30 s | ✓ verified 0.31 s | ✓ verified 0.38 s |
| `held/average/unsigned-shift` | violation | refuted before: returns -1; after: returns 2147483647 | ✓ violation 0.10 s | ✓ violation 0.10 s | ✓ violation 0.11 s | ✓ violation 0.25 s | ✓ violation 0.26 s | ✓ violation 0.34 s |
| `held/floor-mod/wide-modulus` | violation | refuted before: returns -3; after: returns 2147483646 | ✓ violation 0.82 s | ✓ violation 0.79 s | ✓ violation 0.80 s | ✓ violation 15.50 s | ✓ violation 15.48 s | ✓ violation 15.63 s |
| `held/floor-mod/jdk` | verified | held 122010 | ✓ verified 0.16 s | ✓ verified 0.10 s | ✓ verified 0.14 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/ceil-div` | verified | held 122010 | ✓ verified 0.10 s | ✓ verified 0.10 s | ✓ verified 0.10 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/lower-bound` | verified | held 130860 | ✓ verified 0.40 s | ✓ verified 0.41 s | ✓ verified 0.40 s | ✓ verified 7.21 s | ✓ verified 6.65 s | ✓ verified 6.68 s |
| `held/utf8-length` | verified | held 200000 | ✓ verified 0.47 s | ✓ verified 0.48 s | ✓ verified 0.48 s | ✓ verified 0.99 s | ✓ verified 1.05 s | ✓ verified 1.13 s |
| `held/reverse` | verified | held 200000 | ✓ verified 0.21 s | ✓ verified 0.22 s | ✓ verified 0.23 s | – out of memory 15.9 s | – out of memory 9.8 s | – out of memory 10.2 s |
| `held/prefix-sums` | verified | held 200000 | ✓ verified 0.20 s | ✓ verified 0.09 s | ✓ verified 0.16 s | ✓ verified 4.65 s | ✓ verified 4.59 s | ✓ verified 4.81 s |
| `held/overlap/meets` | verified | held 52777 | ✓ verified 0.17 s | ✓ verified 0.10 s | ✓ verified 0.13 s | ✓ verified 0.56 s | ✓ verified 0.61 s | ✓ verified 0.69 s |
| `held/overlap/length` | violation | refuted before: returns 0; after: returns 2147483647 | ✓ violation 0.12 s | ✓ violation 0.14 s | ✓ violation 0.14 s | ✓ violation 0.53 s | ✓ violation 0.54 s | ✓ violation 0.63 s |

## Group 4: recorded examples, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `example/141` | verified | recorded example | ✓ verified 2.19 s |  |  | ✓ verified 65.17 s |  |  |
| `example/142` | verified | recorded example | ✓ verified 7.19 s |  |  | – out of memory 13.9 s |  |  |

## The JVM against the corpus

Every expected answer of groups 2 and 3 is borne out on the JVM.

Every witness an engine reported reproduces on the JVM.
