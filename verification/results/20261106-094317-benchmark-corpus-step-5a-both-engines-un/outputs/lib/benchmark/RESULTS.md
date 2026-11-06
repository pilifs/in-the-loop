# Benchmark results

Written by `lib/benchmark/run.py` on 2026-11-06T17:53:21+0000, on 28 × AMD RYZEN AI MAX+ 395 w/ Radeon 8060S (x86_64), with jvmcontract 0.1.0, JBMC 6.11.0 (cbmc-6.11.0) and openjdk version "25.0.5" 2026-10-20 LTS. Every run had a deadline of 120 s, loops unwound 16 times and arrays of up to 8 elements, on both engines. What the columns mean is in [README.md](README.md).

## Correctness and coverage

| group | engine | mode | cases | correct | of them assuming a gap | unsupported | false success | false alarm | total s | median s | max s | peak MB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 semantic conformance | native | strict | 93 | 82 | 0 | 11 | 0 | 0 | 4.2 | 0.04 | 0.07 | 39.6 |
| 1 semantic conformance | native | assume | 93 | 83 | 1 | 3 | 7 (7 naming a gap) | 0 | 4.3 | 0.04 | 0.07 | 39.5 |
| 1 semantic conformance | native | advised | 93 | 87 | 0 | 6 | 0 | 0 | 5.6 | 0.05 | 0.21 | 111.3 |
| 1 semantic conformance | jbmc | strict | 93 | 79 | 0 | 14 | 0 | 0 | 140.2 | 0.25 | 120.06 | 49.8 |
| 1 semantic conformance | jbmc | assume | 93 | 81 | 3 | 4 | 8 (8 naming a gap) | 0 | 140.4 | 0.25 | 120.06 | 51.8 |
| 1 semantic conformance | jbmc | advised | 93 | 84 | 0 | 9 | 0 | 0 | 141.7 | 0.25 | 120.07 | 111.4 |
| 2 real regressions | native | strict | 13 | 12 | 0 | 1 | 0 | 0 | 123.0 | 0.06 | 120.06 | 80.6 |
| 2 real regressions | native | assume | 13 | 12 | 0 | 1 | 0 | 0 | 123.0 | 0.06 | 120.07 | 88.4 |
| 2 real regressions | native | advised | 13 | 12 | 0 | 1 | 0 | 0 | 123.1 | 0.06 | 120.07 | 90.6 |
| 2 real regressions | jbmc | strict | 13 | 12 | 0 | 1 | 0 | 0 | 196.9 | 0.27 | 120.05 | 1354.4 |
| 2 real regressions | jbmc | assume | 13 | 12 | 0 | 1 | 0 | 0 | 197.5 | 0.27 | 120.08 | 1354.4 |
| 2 real regressions | jbmc | advised | 13 | 12 | 0 | 1 | 0 | 0 | 198.4 | 0.34 | 120.09 | 1354.3 |
| 3 held-out performance cases | native | strict | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.07 | 0.59 | 43.7 |
| 3 held-out performance cases | native | assume | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.59 | 45.9 |
| 3 held-out performance cases | native | advised | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.6 | 48.7 |
| 3 held-out performance cases | jbmc | strict | 12 | 9 | 0 | 3 | 0 | 0 | 273.9 | 1.94 | 120.06 | 3835.3 |
| 3 held-out performance cases | jbmc | assume | 12 | 9 | 0 | 3 | 0 | 0 | 274.0 | 1.96 | 120.1 | 3835.3 |
| 3 held-out performance cases | jbmc | advised | 12 | 9 | 0 | 3 | 0 | 0 | 274.6 | 2.03 | 120.09 | 3835.3 |

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

## By workload, under strict

| workload | engine | cases | correct | unsupported | wrong | median s (decided) | max s | peak MB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| array-bounds | native | 3 | 3 | 0 | 0 | 0.05 | 0.44 | 40.9 |
| array-bounds | jbmc | 3 | 3 | 0 | 0 | 0.41 | 14.38 | 370.0 |
| array-mutation | native | 2 | 2 | 0 | 0 | 0.1 | 0.15 | 39.4 |
| array-mutation | jbmc | 2 | 1 | 1 | 0 | 3.17 | 8.59 | 3835.3 |
| binary-search | native | 2 | 2 | 0 | 0 | 1.1 | 1.94 | 69.6 |
| binary-search | jbmc | 2 | 2 | 0 | 0 | 32.07 | 59.6 | 1354.4 |
| div-rem | native | 9 | 8 | 1 | 0 | 0.06 | 120.06 | 80.6 |
| div-rem | jbmc | 9 | 6 | 3 | 0 | 0.26 | 120.06 | 55.0 |
| records | native | 2 | 2 | 0 | 0 | 0.07 | 0.07 | 37.5 |
| records | jbmc | 2 | 2 | 0 | 0 | 0.3 | 0.33 | 38.0 |
| scalar-arithmetic | native | 6 | 6 | 0 | 0 | 0.06 | 0.12 | 36.9 |
| scalar-arithmetic | jbmc | 6 | 6 | 0 | 0 | 0.26 | 0.28 | 37.2 |
| semantics | native | 93 | 82 | 11 | 0 | 0.04 | 0.07 | 39.6 |
| semantics | jbmc | 93 | 79 | 14 | 0 | 0.22 | 120.06 | 49.8 |
| utf8 | native | 1 | 1 | 0 | 0 | 0.3 | 0.3 | 34.6 |
| utf8 | jbmc | 1 | 1 | 0 | 0 | 0.71 | 0.71 | 81.2 |

## Group 1: semantic conformance, case by case

The JVM's answer is the conformance test's (`lib/tests/conformance.rs`), on the calls the corpus lists.

<details><summary>All 93 claims</summary>

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `conformance/capacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | ✓ violation 0.20 s | – gap 0.3 s | ✗ₐ verified 0.25 s | ✓ violation 0.45 s |
| `conformance/builderCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | ✓ violation 0.21 s | – gap 0.3 s | ✗ₐ verified 0.25 s | ✓ violation 0.44 s |
| `conformance/mapCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.12 s | – gap 0.3 s | ✗ₐ verified 0.26 s | ✓ violation 0.34 s |
| `conformance/setCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | ✓ violation 0.11 s | – gap 0.3 s | ✗ₐ verified 0.25 s | ✓ violation 0.34 s |
| `conformance/loadFactor/1` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – needs contracts 0.0 s | – gap 0.2 s | ✗ₐ verified 0.25 s | – needs contracts 0.1 s |
| `conformance/nullMonitor/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.07 s | – gap 0.3 s | ✗ₐ verified 0.26 s | – gap 0.3 s |
| `conformance/monitor/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | – gap 0.2 s | ✓ₐ verified 0.26 s | – gap 0.3 s |
| `conformance/firstByte/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | ✓ violation 0.15 s | – gap 0.1 s | ✗ₐ verified 0.14 s | ✓ violation 0.39 s |
| `conformance/hiding/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/hiding/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.22 s | ✓ violation 0.18 s |
| `conformance/hidden/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/hidden/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.07 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.17 s |
| `conformance/sameLiteral/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.26 s |
| `conformance/sameLiteral/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/otherLiteral/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/otherLiteral/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/sameClass/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/sameClass/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.18 s |
| `conformance/concatenated/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.05 s | – gap 0.3 s | ✓ₐ verified 0.25 s | – gap 0.3 s |
| `conformance/concatenated/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ₐ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/boom/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | – needs contracts 0.0 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/inherited/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | – needs contracts 0.0 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/quiet/1` | verified | conformance test | – gap 0.0 s | ✓ₐ verified 0.03 s | – needs contracts 0.0 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s |
| `conformance/finallyWins/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s |
| `conformance/finallyWins/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/caught/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/caught/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/nestedHandler/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/nestedHandler/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.07 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s |
| `conformance/element/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.29 s | ✓ verified 0.32 s | ✓ verified 0.33 s |
| `conformance/element/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.18 s |
| `conformance/cast/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.27 s |
| `conformance/cast/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/throwNull/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.26 s |
| `conformance/throwNull/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/rethrown/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/rethrown/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.24 s |
| `conformance/aliasedLocals/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.27 s |
| `conformance/aliasedLocals/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/aliasedObjects/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/aliasedObjects/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/twoArrays/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.06 s | ✓ verified 0.17 s | ✓ verified 0.15 s | ✓ verified 0.16 s |
| `conformance/writeThrough/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.15 s | ✓ verified 0.14 s | ✓ verified 0.15 s |
| `conformance/length/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s |
| `conformance/lengthOrMinusOne/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s |
| `conformance/nullLocal/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.26 s |
| `conformance/nullLocal/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/width/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.31 s | ✓ verified 0.26 s |
| `conformance/width/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.34 s |
| `conformance/width/3` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.19 s | ✓ violation 0.19 s |
| `conformance/clamp/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.28 s |
| `conformance/clamp/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.23 s |
| `conformance/pairsEqual/1` | verified | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.1 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s |
| `conformance/pairsEqual/2` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.1 s | – gap 0.3 s | ✗ₐ verified 0.25 s | – gap 0.3 s |
| `conformance/sides/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.27 s |
| `conformance/sides/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.17 s |
| `conformance/code/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/code/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.18 s |
| `conformance/divide/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.28 s |
| `conformance/divide/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.28 s |
| `conformance/divide/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `conformance/divide/4` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.15 s | ✓ violation 0.16 s |
| `conformance/divideLong/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s |
| `conformance/divideLong/2` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.26 s |
| `conformance/remainder/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/remainder/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.20 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/remainder/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/remainderLong/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.27 s |
| `conformance/remainderLong/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/shiftLeft/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/shiftLeft/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/shiftLeft/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/shiftLeftLong/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/shiftLeftLong/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/shiftLeftLong/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s |
| `conformance/shiftRight/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/shiftRight/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/shiftUnsigned/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/shiftUnsigned/2` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `conformance/square/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/negate/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s |
| `conformance/toByte/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/toByte/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.24 s | ✓ verified 0.25 s | ✓ verified 0.25 s |
| `conformance/toChar/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.24 s | ✓ verified 0.24 s | ✓ verified 0.25 s |
| `conformance/toChar/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.20 s | ✓ violation 0.21 s | ✓ violation 0.21 s |
| `conformance/toShort/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `conformance/fromLong/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.27 s | ✓ violation 0.26 s | ✓ violation 0.28 s |
| `conformance/nextChar/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.20 s | ✓ verified 0.20 s | ✓ verified 0.20 s |
| `conformance/nextChar/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.15 s | ✓ violation 0.15 s | ✓ violation 0.16 s |
| `conformance/absolute/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.26 s |
| `conformance/increment/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.26 s |
| `conformance/byteSum/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.19 s | ✓ verified 0.19 s | ✓ verified 0.20 s |
| `conformance/byteSum/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s |

</details>

## Group 2: real regressions, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `real/midpoint/broken-property` | violation | refuted returns -1073741824 | ✓ violation 0.12 s | ✓ violation 0.13 s | ✓ violation 0.14 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s |
| `real/midpoint/fixed-property` | verified | held 40579 | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s |
| `real/midpoint/fix-confined` | verified | held 35564 | ✓ verified 0.07 s | ✓ verified 0.07 s | ✓ verified 0.08 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.34 s |
| `real/midpoint/search-within-bound` | verified | held 200000 | ✓ verified 1.94 s | ✓ verified 1.95 s | ✓ verified 1.92 s | ✓ verified 59.60 s | ✓ verified 60.19 s | ✓ verified 60.76 s |
| `real/bucket/broken-property` | violation | refuted returns -2 | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.27 s | ✓ violation 0.26 s | ✓ violation 0.27 s |
| `real/bucket/fixed-property` | verified | held 122010 | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `real/bucket/fix-confined` | verified | held 127354 | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.0 s | – out of time 120.1 s | – out of time 120.1 s |
| `real/oddity/broken-property` | violation | refuted returns false | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.20 s | ✓ violation 0.20 s | ✓ violation 0.20 s |
| `real/oddity/fixed-property` | verified | held 200017 | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.24 s | ✓ verified 0.24 s | ✓ verified 0.24 s |
| `real/oddity/fix-confined` | verified | held 127076 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.34 s |
| `real/checksum/broken-property` | violation | refuted returns 0 | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.41 s | ✓ violation 0.41 s | ✓ violation 0.42 s |
| `real/checksum/fixed-property` | verified | held 200000 | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.40 s | ✓ verified 0.40 s | ✓ verified 0.41 s |
| `real/checksum/fix-confined` | verified | held 190209 | ✓ verified 0.44 s | ✓ verified 0.42 s | ✓ verified 0.44 s | ✓ verified 14.38 s | ✓ verified 14.42 s | ✓ verified 14.53 s |

## Group 3: held-out performance cases, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised |
|---|---|---|---|---|---|---|---|---|
| `held/saturating` | verified | held 200289 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.34 s |
| `held/average/bits` | verified | held 200289 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.33 s |
| `held/average/unsigned-shift` | violation | refuted before: returns -1; after: returns 2147483647 | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.28 s |
| `held/floor-mod/wide-modulus` | violation | refuted before: returns -3; after: returns 2147483646 | ✓ violation 0.59 s | ✓ violation 0.59 s | ✓ violation 0.60 s | ✓ violation 15.41 s | ✓ violation 15.41 s | ✓ violation 15.45 s |
| `held/floor-mod/jdk` | verified | held 122010 | ✓ verified 0.07 s | ✓ verified 0.06 s | ✓ verified 0.06 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/ceil-div` | verified | held 122010 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | – out of time 120.0 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/lower-bound` | verified | held 130860 | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 4.54 s | ✓ verified 4.59 s | ✓ verified 4.55 s |
| `held/utf8-length` | verified | held 200000 | ✓ verified 0.30 s | ✓ verified 0.30 s | ✓ verified 0.32 s | ✓ verified 0.71 s | ✓ verified 0.71 s | ✓ verified 0.78 s |
| `held/reverse` | verified | held 200000 | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.15 s | – out of memory 8.6 s | – out of memory 8.6 s | – out of memory 8.6 s |
| `held/prefix-sums` | verified | held 200000 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 3.17 s | ✓ verified 3.22 s | ✓ verified 3.28 s |
| `held/overlap/meets` | verified | held 52777 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.34 s |
| `held/overlap/length` | violation | refuted before: returns 0; after: returns 2147483647 | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.33 s | ✓ violation 0.33 s | ✓ violation 0.40 s |

## The JVM against the corpus

Every expected answer of groups 2 and 3 is borne out on the JVM.

Every witness an engine reported reproduces on the JVM.
