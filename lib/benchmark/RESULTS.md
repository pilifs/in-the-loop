# Benchmark results

Written by `lib/benchmark/run.py` on 2026-11-06T21:42:39+0000, as pipeline job `20261106-201041-benchmark-corpus-with-exclusive-jbmc-pha`, at commit `26227917d3b6`, on 28 × AMD RYZEN AI MAX+ 395 w/ Radeon 8060S (x86_64), with jvmcontract 0.1.0, JBMC 6.11.0 (cbmc-6.11.0) and openjdk version "25.0.5" 2026-10-20 LTS. Every run had a deadline of 120 s, loops unwound 16 times and arrays of up to 8 elements, on both engines. What the columns mean is in [README.md](README.md).

Every run of an engine that may call JBMC was made under each of JBMC's staging policies, `staged`, `full-range`, `tight`. The tables of the corpus are over `staged`, and [JBMC's staging policies](#jbmcs-staging-policies) compares the others with it.

SAT solvers: the own checker on CaDiCaL 1.9.5, bundled by the Rust crate cadical 0.1.16; JBMC on CaDiCaL 3.0.0, linked into JBMC (/usr/bin/jbmc), the version as its signature there reads; auto on CaDiCaL 1.9.5, bundled by the Rust crate cadical 0.1.16 and CaDiCaL 3.0.0, linked into JBMC (/usr/bin/jbmc), the version as its signature there reads. Their configuration is under `environment.sat` in `results.json`.

## Correctness and coverage

| group | engine | mode | cases | correct | of them assuming a gap | unsupported | false success | false alarm | total s | median s | max s | peak MB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 semantic conformance | native | strict | 93 | 82 | 0 | 11 | 0 | 0 | 3.6 | 0.04 | 0.08 | 39.1 |
| 1 semantic conformance | native | assume | 93 | 83 | 1 | 3 | 7 (7 naming a gap) | 0 | 3.6 | 0.04 | 0.1 | 39.6 |
| 1 semantic conformance | native | advised | 93 | 87 | 0 | 6 | 0 | 0 | 4.5 | 0.04 | 0.18 | 111.4 |
| 1 semantic conformance | jbmc | strict | 93 | 79 | 0 | 14 | 0 | 0 | 140.5 | 0.25 | 120.08 | 52.0 |
| 1 semantic conformance | jbmc | assume | 93 | 81 | 3 | 4 | 8 (8 naming a gap) | 0 | 140.4 | 0.25 | 120.08 | 52.4 |
| 1 semantic conformance | jbmc | advised | 93 | 84 | 0 | 9 | 0 | 0 | 141.5 | 0.25 | 120.05 | 111.2 |
| 1 semantic conformance | auto | strict | 93 | 85 | 0 | 8 | 0 | 0 | 4.6 | 0.04 | 0.26 | 42.7 |
| 1 semantic conformance | auto | assume | 93 | 83 | 1 | 1 | 9 (9 naming a gap) | 0 | 4.2 | 0.04 | 0.27 | 39.3 |
| 1 semantic conformance | auto | advised | 93 | 87 | 0 | 6 | 0 | 0 | 4.9 | 0.05 | 0.27 | 111.5 |
| 2 real regressions | native | strict | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.06 | 1.72 | 70.3 |
| 2 real regressions | native | assume | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.06 | 1.71 | 70.5 |
| 2 real regressions | native | advised | 13 | 13 | 0 | 0 | 0 | 0 | 2.9 | 0.06 | 1.73 | 74.8 |
| 2 real regressions | jbmc | strict | 13 | 12 | 0 | 1 | 0 | 0 | 197.7 | 0.29 | 120.09 | 1354.2 |
| 2 real regressions | jbmc | assume | 13 | 12 | 0 | 1 | 0 | 0 | 197.8 | 0.28 | 120.07 | 1354.3 |
| 2 real regressions | jbmc | advised | 13 | 12 | 0 | 1 | 0 | 0 | 199.0 | 0.35 | 120.07 | 1354.3 |
| 2 real regressions | auto | strict | 13 | 13 | 0 | 0 | 0 | 0 | 3.1 | 0.06 | 2.0 | 67.3 |
| 2 real regressions | auto | assume | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.06 | 1.75 | 69.7 |
| 2 real regressions | auto | advised | 13 | 13 | 0 | 0 | 0 | 0 | 3.0 | 0.07 | 1.74 | 75.8 |
| 3 held-out performance cases | native | strict | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.62 | 43.5 |
| 3 held-out performance cases | native | assume | 12 | 12 | 0 | 0 | 0 | 0 | 1.9 | 0.06 | 0.62 | 43.3 |
| 3 held-out performance cases | native | advised | 12 | 12 | 0 | 0 | 0 | 0 | 2.0 | 0.07 | 0.63 | 48.6 |
| 3 held-out performance cases | jbmc | strict | 12 | 9 | 0 | 3 | 0 | 0 | 273.1 | 2.17 | 120.08 | 3370.5 |
| 3 held-out performance cases | jbmc | assume | 12 | 9 | 0 | 3 | 0 | 0 | 273.0 | 2.15 | 120.06 | 3370.6 |
| 3 held-out performance cases | jbmc | advised | 12 | 9 | 0 | 3 | 0 | 0 | 274.3 | 2.44 | 120.09 | 3370.7 |
| 3 held-out performance cases | auto | strict | 12 | 12 | 0 | 0 | 0 | 0 | 1.9 | 0.07 | 0.67 | 44.9 |
| 3 held-out performance cases | auto | assume | 12 | 12 | 0 | 0 | 0 | 0 | 1.9 | 0.07 | 0.64 | 43.3 |
| 3 held-out performance cases | auto | advised | 12 | 12 | 0 | 0 | 0 | 0 | 2.0 | 0.07 | 0.64 | 48.5 |
| 4 recorded examples | native | strict | 2 | 2 | 0 | 0 | 0 | 0 | 6.0 | 2.99 | 4.64 | 77.4 |
| 4 recorded examples | jbmc | strict | 2 | 1 | 0 | 1 | 0 | 0 | 70.0 | 34.98 | 60.76 | 3410.0 |
| 4 recorded examples | auto | strict | 2 | 2 | 0 | 0 | 0 | 0 | 6.1 | 3.06 | 4.81 | 81.1 |

Why the unsupported cases had no verdict:

- group 1, native, strict: 8 gap, 3 refused
- group 1, native, assume: 3 refused
- group 1, native, advised: 4 needs contracts, 2 refused
- group 1, jbmc, strict: 11 gap, 2 witness not reproduced, 1 out of time
- group 1, jbmc, assume: 3 witness not reproduced, 1 out of time
- group 1, jbmc, advised: 5 gap, 2 witness not reproduced, 1 needs contracts, 1 out of time
- group 1, auto, strict: 8 gap
- group 1, auto, assume: 1 witness not reproduced
- group 1, auto, advised: 4 needs contracts, 2 gap
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
| array-bounds | native | 3 | 3 | 0 | 0 | 0.06 | 0.47 | 41.2 |
| array-bounds | jbmc | 3 | 3 | 0 | 0 | 0.43 | 18.25 | 370.2 |
| array-bounds | auto | 3 | 3 | 0 | 0 | 0.06 | 0.46 | 40.7 |
| array-mutation | native | 2 | 2 | 0 | 0 | 0.1 | 0.15 | 38.9 |
| array-mutation | jbmc | 2 | 1 | 1 | 0 | 3.58 | 6.64 | 3370.5 |
| array-mutation | auto | 2 | 2 | 0 | 0 | 0.1 | 0.15 | 39.4 |
| binary-search | native | 3 | 3 | 0 | 0 | 1.34 | 1.72 | 70.3 |
| binary-search | jbmc | 3 | 3 | 0 | 0 | 56.43 | 60.76 | 2059.7 |
| binary-search | auto | 3 | 3 | 0 | 0 | 1.31 | 2.0 | 67.3 |
| div-rem | native | 9 | 9 | 0 | 0 | 0.06 | 0.62 | 43.5 |
| div-rem | jbmc | 9 | 6 | 3 | 0 | 0.27 | 120.09 | 53.8 |
| div-rem | auto | 9 | 9 | 0 | 0 | 0.06 | 0.67 | 44.9 |
| records | native | 2 | 2 | 0 | 0 | 0.07 | 0.08 | 37.0 |
| records | jbmc | 2 | 2 | 0 | 0 | 0.32 | 0.35 | 54.4 |
| records | auto | 2 | 2 | 0 | 0 | 0.07 | 0.08 | 37.1 |
| scalar-arithmetic | native | 6 | 6 | 0 | 0 | 0.06 | 0.12 | 36.5 |
| scalar-arithmetic | jbmc | 6 | 6 | 0 | 0 | 0.27 | 0.29 | 53.4 |
| scalar-arithmetic | auto | 6 | 6 | 0 | 0 | 0.06 | 0.12 | 36.8 |
| semantics | native | 93 | 82 | 11 | 0 | 0.04 | 0.08 | 39.1 |
| semantics | jbmc | 93 | 79 | 14 | 0 | 0.25 | 120.08 | 52.0 |
| semantics | auto | 93 | 85 | 8 | 0 | 0.04 | 0.26 | 42.7 |
| utf8 | native | 2 | 2 | 0 | 0 | 2.48 | 4.64 | 77.4 |
| utf8 | jbmc | 2 | 1 | 1 | 0 | 0.77 | 9.2 | 3410.0 |
| utf8 | auto | 2 | 2 | 0 | 0 | 2.56 | 4.81 | 81.1 |

## Where the time goes, by workload, under strict

Each engine's seconds over every run of the workload, decided or not, as shares of the phases of `lib/src/phases.rs`: the checker's own (`loading` to `trace`, and `checker-other`, JBMC starting and printing), then the driver's (`gaps` and JBMC's preflight, `contracts`, `replay` and shrinking, the `jvm` witness run, the `harness`, the `setup` of the work directory with the JDK's classes and the models, and the rest of the process as `driver`). Step 5b of the sound-verdicts brief.

| workload | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| array-bounds | native | 3 | 0.57 | · | · | 4% | 5% | 64% | 0% | · | · | · | 0% | · | · | 4% | 22% | **solving** 64% | 45662 |
| array-bounds | jbmc | 3 | 19.08 | 0% | 0% | 1% | 3% | 91% | 0% | 3% | 1% | · | 0% | · | · | 0% | 1% | **solving** 91% | 762544 |
| array-bounds | auto | 2 | 0.5 | · | · | 5% | 4% | 71% | · | · | · | · | · | · | · | 3% | 17% | **solving** 71% | 45662 |
| array-mutation | native | 2 | 0.2 | · | · | 3% | 3% | 41% | · | · | · | · | · | · | · | 7% | 45% | **driver** 45% | 59707 |
| array-mutation | jbmc | 2 (1 undecided) | 10.22 | 0% | 0% | 2% | 30% | 53% | · | 13% | 1% | · | · | · | · | 0% | 1% | **solving** 53% | 17233885 |
| array-mutation | auto | 2 | 0.2 | · | · | 3% | 3% | 41% | · | · | · | · | · | · | · | 7% | 46% | **driver** 46% | 59707 |
| binary-search | native | 2 | 1.98 | · | · | 3% | 3% | 88% | · | · | · | · | · | · | · | 1% | 5% | **solving** 88% | 240144 |
| binary-search | jbmc | 2 | 61.53 | 0% | 0% | 1% | 3% | 95% | · | 1% | 0% | · | · | · | · | 0% | 0% | **solving** 95% | 3281450 |
| binary-search | auto | 2 | 2.25 | · | · | 3% | 3% | 88% | · | · | · | · | · | · | · | 1% | 5% | **solving** 88% | 240144 |
| div-rem | native | 9 | 1.05 | · | · | 2% | · | 53% | 0% | · | · | · | 0% | · | · | 6% | 38% | **solving** 53% | 55638 |
| div-rem | jbmc | 9 (3 undecided) | 376.98 | 0% | 0% | 0% | 0% | 99% | 0% | 0% | 0% | · | 0% | · | · | 0% | 0% | **solving** 99% | 49832 |
| div-rem | auto | 9 | 1.12 | · | · | 3% | · | 53% | 0% | · | · | · | 0% | · | · | 6% | 38% | **solving** 53% | 55638 |
| records | native | 2 | 0.14 | · | · | 1% | · | 1% | · | · | · | · | 10% | · | · | 10% | 78% | **driver** 78% | 7451 |
| records | jbmc | 2 | 0.64 | 10% | 4% | 6% | 2% | 10% | 0% | 23% | 19% | · | 0% | · | · | 2% | 22% | **checker-other** 23% | 13325 |
| records | auto | 2 | 0.14 | · | · | 1% | · | 1% | · | · | · | · | 10% | · | · | 10% | 78% | **driver** 78% | 7451 |
| scalar-arithmetic | native | 6 | 0.4 | · | · | 2% | · | 21% | · | · | · | · | 0% | · | · | 11% | 66% | **driver** 66% | 20540 |
| scalar-arithmetic | jbmc | 6 | 1.61 | 4% | 1% | 1% | 1% | 4% | 0% | 43% | 22% | · | 0% | · | · | 3% | 21% | **checker-other** 43% | 4221 |
| scalar-arithmetic | auto | 6 | 0.39 | · | · | 2% | · | 22% | · | · | · | · | 0% | · | · | 11% | 65% | **driver** 65% | 20540 |
| semantics | native | 93 (11 undecided) | 3.63 | · | · | 1% | · | 1% | 0% | · | · | · | 0% | · | · | 19% | 79% | **driver** 79% | 100555 |
| semantics | jbmc | 93 (14 undecided) | 140.55 | 2% | 0% | 0% | 0% | 85% | 0% | 5% | 4% | · | 0% | · | · | 0% | 3% | **solving** 85% | 49726 |
| semantics | auto | 93 (8 undecided) | 4.61 | 3% | 1% | 1% | · | 1% | 0% | 9% | 8% | · | 0% | · | · | 14% | 63% | **driver** 63% | 100555 |
| utf8 | native | 1 | 0.31 | · | · | · | 15% | 68% | · | · | · | · | · | · | · | 2% | 15% | **solving** 68% | 23224 |
| utf8 | jbmc | 1 | 0.77 | 0% | 0% | 7% | 5% | 68% | · | 4% | 8% | · | · | · | · | 1% | 6% | **solving** 68% | 173454 |
| utf8 | auto | 1 | 0.31 | · | · | · | 15% | 68% | · | · | · | · | · | · | · | 2% | 15% | **solving** 68% | 23224 |

### The recorded examples

| id | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| example/141 | native | 1 | 1.34 | · | · | 2% | 4% | 89% | · | · | · | · | · | · | · | 1% | 5% | **solving** 89% | 137013 |
| example/141 | jbmc | 1 | 60.76 | 0% | 0% | 0% | 4% | 95% | · | 0% | 0% | · | · | · | · | 0% | 0% | **solving** 95% | 4718689 |
| example/141 | auto | 1 | 1.31 | · | · | 2% | 4% | 90% | · | · | · | · | · | · | · | 1% | 4% | **solving** 90% | 137013 |
| example/142 | native | 1 | 4.64 | · | · | 1% | 2% | 96% | · | · | · | · | · | · | · | 0% | 1% | **solving** 96% | 161165 |
| example/142 | jbmc | 1 (1 undecided) | 9.2 | 0% | 0% | 6% | 65% | · | · | 27% | 1% | · | · | · | · | 0% | 1% | **encoding** 65% | – |
| example/142 | auto | 1 | 4.81 | · | · | 1% | 2% | 96% | · | · | · | · | · | · | · | 0% | 1% | **solving** 96% | 161165 |

Left out of these tables, because their phases add up to more than their time (beyond 1% and 5 ms): `real/checksum/broken-property` on auto (by 0.013 s).

## Group 1: semantic conformance, case by case

The JVM's answer is the conformance test's (`lib/tests/conformance.rs`), on the calls the corpus lists.

<details><summary>All 93 claims</summary>

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `conformance/capacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.18 s | – gap 0.3 s | ✗ₐ verified 0.26 s | ✓ violation 0.40 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.18 s |
| `conformance/builderCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.04 s | ✓ violation 0.14 s | – gap 0.3 s | ✗ₐ verified 0.26 s | ✓ violation 0.38 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.14 s |
| `conformance/mapCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.10 s | – gap 0.3 s | ✗ₐ verified 0.25 s | ✓ violation 0.34 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.10 s |
| `conformance/setCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.10 s | – gap 0.2 s | ✗ₐ verified 0.25 s | ✓ violation 0.34 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.10 s |
| `conformance/loadFactor/1` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | ✗ₐ verified 0.26 s | – needs contracts 0.1 s | – gap 0.3 s | ✗ₐ verified 0.27 s | – needs contracts 0.0 s |
| `conformance/nullMonitor/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | – gap 0.3 s | ✗ₐ verified 0.27 s | – gap 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/monitor/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – gap 0.3 s | ✓ₐ verified 0.26 s | – gap 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/firstByte/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.13 s | – gap 0.1 s | ✗ₐ verified 0.14 s | ✓ violation 0.28 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.11 s |
| `conformance/hiding/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/hiding/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/hidden/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/hidden/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.05 s |
| `conformance/sameLiteral/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/sameLiteral/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/otherLiteral/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/otherLiteral/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/sameClass/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/sameClass/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/concatenated/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – gap 0.3 s | ✓ₐ verified 0.26 s | – gap 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/concatenated/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ₐ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/boom/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.02 s | – needs contracts 0.0 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✗ₐ verified 0.03 s | – needs contracts 0.0 s |
| `conformance/inherited/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | – needs contracts 0.0 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✗ₐ verified 0.03 s | – needs contracts 0.0 s |
| `conformance/quiet/1` | verified | conformance test | – gap 0.0 s | ✓ₐ verified 0.04 s | – needs contracts 0.0 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ₐ verified 0.03 s | – needs contracts 0.0 s |
| `conformance/finallyWins/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/finallyWins/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.06 s |
| `conformance/caught/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/caught/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/nestedHandler/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/nestedHandler/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/element/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/element/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/cast/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/cast/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/throwNull/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/throwNull/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/rethrown/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/rethrown/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/aliasedLocals/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/aliasedLocals/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/aliasedObjects/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.30 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/aliasedObjects/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/twoArrays/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.17 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/writeThrough/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/length/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/lengthOrMinusOne/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/nullLocal/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/nullLocal/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/width/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/width/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/width/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/clamp/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/clamp/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/pairsEqual/1` | verified | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.0 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s |
| `conformance/pairsEqual/2` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.0 s | – gap 0.3 s | ✗ₐ verified 0.25 s | – gap 0.3 s | – gap 0.3 s | ✗ₐ verified 0.26 s | – gap 0.3 s |
| `conformance/sides/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/sides/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/code/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/code/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divide/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/divide/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.28 s | ✓ violation 0.27 s | ✓ violation 0.28 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divide/3` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.0 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `conformance/divide/4` | violation | conformance test | ✓ violation 0.08 s | ✓ violation 0.10 s | ✓ violation 0.09 s | ✓ violation 0.26 s | ✓ violation 0.19 s | ✓ violation 0.25 s | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `conformance/divideLong/1` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.05 s | ✓ violation 0.08 s | ✓ violation 0.29 s | ✓ violation 0.28 s | ✓ violation 0.35 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.07 s |
| `conformance/divideLong/2` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.33 s | ✓ verified 0.33 s | ✓ verified 0.34 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/remainder/1` | verified | conformance test | ✓ verified 0.05 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `conformance/remainder/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.23 s | ✓ violation 0.23 s | ✓ violation 0.23 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.06 s |
| `conformance/remainder/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/remainderLong/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/remainderLong/2` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s |
| `conformance/shiftLeft/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/shiftLeft/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.23 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.07 s |
| `conformance/shiftLeft/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.29 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/shiftLeftLong/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.27 s | ✓ verified 0.26 s | ✓ verified 0.30 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/shiftLeftLong/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s |
| `conformance/shiftLeftLong/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/shiftRight/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.27 s | ✓ verified 0.06 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/shiftRight/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s |
| `conformance/shiftUnsigned/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/shiftUnsigned/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/square/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.23 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `conformance/negate/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/toByte/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.23 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/toByte/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/toChar/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/toChar/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/toShort/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.04 s |
| `conformance/fromLong/1` | violation | conformance test | ✓ violation 0.07 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/nextChar/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.20 s | ✓ verified 0.20 s | ✓ verified 0.21 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/nextChar/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.15 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/absolute/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.27 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/increment/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/byteSum/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.20 s | ✓ verified 0.20 s | ✓ verified 0.21 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.03 s |
| `conformance/byteSum/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.23 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |

</details>

## Group 2: real regressions, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `real/midpoint/broken-property` | violation | refuted returns -1073741824 | ✓ violation 0.12 s | ✓ violation 0.12 s | ✓ violation 0.13 s | ✓ violation 0.26 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.12 s | ✓ violation 0.12 s | ✓ violation 0.12 s |
| `real/midpoint/fixed-property` | verified | held 40579 | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `real/midpoint/fix-confined` | verified | held 121136 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.29 s | ✓ verified 0.29 s | ✓ verified 0.35 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `real/midpoint/search-within-bound` | verified | held 200000 | ✓ verified 1.72 s | ✓ verified 1.71 s | ✓ verified 1.73 s | ✓ verified 56.43 s | ✓ verified 56.67 s | ✓ verified 56.74 s | ✓ verified 2.00 s | ✓ verified 1.75 s | ✓ verified 1.74 s |
| `real/bucket/broken-property` | violation | refuted returns -2 | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `real/bucket/fixed-property` | verified | held 122010 | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `real/bucket/fix-confined` | verified | held 127354 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.09 s |
| `real/oddity/broken-property` | violation | refuted returns false | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `real/oddity/fixed-property` | verified | held 200017 | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `real/oddity/fix-confined` | verified | held 127076 | ✓ verified 0.07 s | ✓ verified 0.07 s | ✓ verified 0.07 s | ✓ verified 0.29 s | ✓ verified 0.28 s | ✓ verified 0.36 s | ✓ verified 0.08 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `real/checksum/broken-property` | violation | refuted returns 0 | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.43 s | ✓ violation 0.42 s | ✓ violation 0.42 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s |
| `real/checksum/fixed-property` | verified | held 200000 | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.41 s | ✓ verified 0.41 s | ✓ verified 0.42 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `real/checksum/fix-confined` | verified | held 190209 | ✓ verified 0.47 s | ✓ verified 0.46 s | ✓ verified 0.46 s | ✓ verified 18.25 s | ✓ verified 18.15 s | ✓ verified 19.06 s | ✓ verified 0.46 s | ✓ verified 0.47 s | ✓ verified 0.53 s |

## Group 3: held-out performance cases, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `held/saturating` | verified | held 200289 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `held/average/bits` | verified | held 200289 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.06 s |
| `held/average/unsigned-shift` | violation | refuted before: returns -1; after: returns 2147483647 | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.23 s | ✓ violation 0.23 s | ✓ violation 0.31 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s |
| `held/floor-mod/wide-modulus` | violation | refuted before: returns -3; after: returns 2147483646 | ✓ violation 0.62 s | ✓ violation 0.62 s | ✓ violation 0.63 s | ✓ violation 15.44 s | ✓ violation 15.44 s | ✓ violation 15.49 s | ✓ violation 0.67 s | ✓ violation 0.64 s | ✓ violation 0.64 s |
| `held/floor-mod/jdk` | verified | held 122010 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s |
| `held/ceil-div` | verified | held 122010 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.08 s | ✓ verified 0.07 s | ✓ verified 0.07 s |
| `held/lower-bound` | verified | held 130860 | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.32 s | ✓ verified 5.10 s | ✓ verified 4.89 s | ✓ verified 5.12 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.28 s |
| `held/utf8-length` | verified | held 200000 | ✓ verified 0.31 s | ✓ verified 0.31 s | ✓ verified 0.32 s | ✓ verified 0.77 s | ✓ verified 0.77 s | ✓ verified 0.84 s | ✓ verified 0.31 s | ✓ verified 0.31 s | ✓ verified 0.33 s |
| `held/reverse` | verified | held 200000 | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.16 s | – out of memory 6.6 s | – out of memory 6.8 s | – out of memory 6.9 s | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.16 s |
| `held/prefix-sums` | verified | held 200000 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 3.58 s | ✓ verified 3.53 s | ✓ verified 4.05 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `held/overlap/meets` | verified | held 52777 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.29 s | ✓ verified 0.29 s | ✓ verified 0.35 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `held/overlap/length` | violation | refuted before: returns 0; after: returns 2147483647 | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.35 s | ✓ violation 0.34 s | ✓ violation 0.41 s | ✓ violation 0.08 s | ✓ violation 0.08 s | ✓ violation 0.08 s |

## Group 4: recorded examples, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `example/141` | verified | recorded example | ✓ verified 1.34 s |  |  | ✓ verified 60.76 s |  |  | ✓ verified 1.31 s |  |  |
| `example/142` | verified | recorded example | ✓ verified 4.64 s |  |  | – out of memory 9.2 s |  |  | ✓ verified 4.81 s |  |  |

## JBMC's staging policies

Step 2b of [`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md): every run of `jbmc`, and of `auto` where the own checker gave no verdict and JBMC's fallback ran, under each of the policies of `--jbmc-staging` (`lib/src/deadline.rs`): `staged` runs every interval stage that restricts the inputs before the full range, `full-range` the full range alone, `tight` the first restricting stage on a fortieth of the check, then the full range. Everything else is the same: the deadline, the bounds, the models and the evidence rules. Proofs (cases expected `verified`) and counterexamples (expected `violation`) are counted apart. A witness is measured as reported, after `lib/src/shrink.rs` shrank it in the interpreter: the elements of its arrays and its largest magnitude. *Changed* counts the runs whose class differs from the same case's under `staged`, *larger* the witnesses bigger than its, and *starved* the runs left without a verdict that gave the full range less than a second, or none.

| engine | mode | kind | policy | correct | no verdict | wrong | total s | median s | changed | larger witnesses | shrunk | starved | no verdict, why |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| jbmc | strict | proofs | `staged` | 54 of 65 | 11 | 0 | 654.3 | 0.26 | 0 | · | · | 3 | 4 out of time, 3 gap, 2 witness not reproduced, 2 out of memory |
| jbmc | strict | proofs | `full-range` | 54 of 65 | 11 | 0 | 574.7 | 0.15 | 0 | · | · | 0 | 4 out of time, 3 gap, 2 witness not reproduced, 2 out of memory |
| jbmc | strict | proofs | `tight` | 54 of 65 | 11 | 0 | 587.8 | 0.2 | 0 | · | · | 3 | 4 out of time, 3 gap, 2 witness not reproduced, 2 out of memory |
| jbmc | strict | counterexamples | `staged` | 47 of 55 | 8 | 0 | 27.1 | 0.21 | 0 | 0 | 16 | 0 | 8 gap |
| jbmc | strict | counterexamples | `full-range` | 46 of 55 | 9 | 0 | 9.3 | 0.16 | 1 | 0 | 17 | 0 | 8 gap, 1 witness not reproduced |
| jbmc | strict | counterexamples | `tight` | 46 of 55 | 9 | 0 | 10.9 | 0.2 | 1 | 0 | 19 | 0 | 8 gap, 1 witness not reproduced |
| jbmc | assume | proofs | `staged` | 55 of 63 | 8 | 0 | 584.3 | 0.26 | 0 | · | · | 3 | 4 out of time, 3 witness not reproduced, 1 out of memory |
| jbmc | assume | proofs | `full-range` | 55 of 63 | 8 | 0 | 534.9 | 0.15 | 0 | · | · | 0 | 4 out of time, 3 witness not reproduced, 1 out of memory |
| jbmc | assume | proofs | `tight` | 55 of 63 | 8 | 0 | 545.6 | 0.2 | 0 | · | · | 3 | 4 out of time, 3 witness not reproduced, 1 out of memory |
| jbmc | assume | counterexamples | `staged` | 47 of 55 | 0 | 8 | 27.0 | 0.21 | 0 | 0 | 16 | 0 |  |
| jbmc | assume | counterexamples | `full-range` | 46 of 55 | 1 | 8 | 9.2 | 0.16 | 1 | 0 | 17 | 0 | 1 witness not reproduced |
| jbmc | assume | counterexamples | `tight` | 46 of 55 | 1 | 8 | 11.0 | 0.2 | 1 | 0 | 19 | 0 | 1 witness not reproduced |
| jbmc | advised | proofs | `staged` | 53 of 63 | 10 | 0 | 586.9 | 0.27 | 0 | · | · | 3 | 4 out of time, 3 gap, 2 witness not reproduced, 1 out of memory |
| jbmc | advised | proofs | `full-range` | 53 of 63 | 10 | 0 | 536.3 | 0.16 | 0 | · | · | 0 | 4 out of time, 3 gap, 2 witness not reproduced, 1 out of memory |
| jbmc | advised | proofs | `tight` | 53 of 63 | 10 | 0 | 546.1 | 0.21 | 0 | · | · | 3 | 4 out of time, 3 gap, 2 witness not reproduced, 1 out of memory |
| jbmc | advised | counterexamples | `staged` | 52 of 55 | 3 | 0 | 27.9 | 0.22 | 0 | 0 | 16 | 0 | 2 gap, 1 needs contracts |
| jbmc | advised | counterexamples | `full-range` | 51 of 55 | 4 | 0 | 10.3 | 0.16 | 1 | 0 | 21 | 0 | 2 gap, 1 needs contracts, 1 witness not reproduced |
| jbmc | advised | counterexamples | `tight` | 51 of 55 | 4 | 0 | 12.1 | 0.21 | 1 | 0 | 23 | 0 | 2 gap, 1 needs contracts, 1 witness not reproduced |
| auto | strict | proofs | `staged` | 1 of 2 | 1 | 0 | 0.4 | 0.21 | 0 | · | · | 1 | 1 gap |
| auto | strict | proofs | `full-range` | 1 of 2 | 1 | 0 | 0.3 | 0.16 | 0 | · | · | 0 | 1 gap |
| auto | strict | proofs | `tight` | 1 of 2 | 1 | 0 | 0.4 | 0.18 | 0 | · | · | 1 | 1 gap |
| auto | strict | counterexamples | `staged` | 2 of 4 | 2 | 0 | 0.8 | 0.21 | 0 | 0 | 0 | 0 | 2 gap |
| auto | strict | counterexamples | `full-range` | 2 of 4 | 2 | 0 | 0.6 | 0.16 | 0 | 0 | 0 | 0 | 2 gap |
| auto | strict | counterexamples | `tight` | 2 of 4 | 2 | 0 | 0.8 | 0.19 | 0 | 0 | 0 | 0 | 2 gap |
| auto | assume | proofs | `staged` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 1 | 1 witness not reproduced |
| auto | assume | proofs | `full-range` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 0 | 1 witness not reproduced |
| auto | assume | proofs | `tight` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 1 | 1 witness not reproduced |
| auto | assume | counterexamples | `staged` | 0 of 2 | 0 | 2 | 0.5 | 0.26 | 0 | 0 | 0 | 0 |  |
| auto | assume | counterexamples | `full-range` | 0 of 2 | 0 | 2 | 0.3 | 0.15 | 0 | 0 | 0 | 0 |  |
| auto | assume | counterexamples | `tight` | 0 of 2 | 0 | 2 | 0.4 | 0.21 | 0 | 0 | 0 | 0 |  |
| auto | advised | proofs | `staged` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 1 | 1 gap |
| auto | advised | proofs | `full-range` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 0 | 1 gap |
| auto | advised | proofs | `tight` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | · | · | 1 | 1 gap |
| auto | advised | counterexamples | `staged` | 0 of 1 | 1 | 0 | 0.3 | 0.27 | 0 | 0 | 0 | 0 | 1 gap |
| auto | advised | counterexamples | `full-range` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | 0 | 0 | 0 | 1 gap |
| auto | advised | counterexamples | `tight` | 0 of 1 | 1 | 0 | 0.2 | 0.21 | 0 | 0 | 0 | 0 | 1 gap |

Cases whose class differs between the policies, jbmc under strict: `conformance/shiftRight/2`.

Cases whose class differs between the policies, jbmc under assume: `conformance/shiftRight/2`.

Cases whose class differs between the policies, jbmc under advised: `conformance/shiftRight/2`.

<details><summary>Proofs, jbmc under strict, 65 cases: each case, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/monitor/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/hiding/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/hidden/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.21 s |
| `conformance/sameLiteral/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/otherLiteral/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/sameClass/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/concatenated/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/quiet/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/finallyWins/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/caught/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/nestedHandler/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/element/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/cast/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/throwNull/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/rethrown/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/aliasedLocals/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/aliasedObjects/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/twoArrays/1` | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.15 s |
| `conformance/writeThrough/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/length/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/lengthOrMinusOne/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/nullLocal/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/width/1` | ✓ verified 0.26 s | ✓ verified 0.19 s | ✓ verified 0.20 s |
| `conformance/clamp/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/pairsEqual/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |
| `conformance/sides/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.21 s |
| `conformance/code/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/divide/1` | ✓ verified 0.26 s | ✓ verified 0.17 s | ✓ verified 0.21 s |
| `conformance/divide/3` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.0 s |
| `conformance/divideLong/2` | ✓ verified 0.33 s | ✓ verified 0.20 s | ✓ verified 0.22 s |
| `conformance/remainder/1` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/remainder/3` | ✓ verified 0.27 s | ✓ verified 0.16 s | ✓ verified 0.21 s |
| `conformance/remainderLong/1` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/shiftLeft/1` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/shiftLeft/3` | ✓ verified 0.26 s | ✓ verified 0.16 s | ✓ verified 0.21 s |
| `conformance/shiftLeftLong/1` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/shiftLeftLong/3` | ✓ verified 0.26 s | ✓ verified 0.17 s | ✓ verified 0.21 s |
| `conformance/shiftRight/1` | ✓ verified 0.26 s | ✓ verified 0.16 s | ✓ verified 0.21 s |
| `conformance/shiftUnsigned/2` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/toByte/2` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/toChar/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/toShort/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/nextChar/1` | ✓ verified 0.20 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/increment/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/byteSum/1` | ✓ verified 0.20 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `real/midpoint/fixed-property` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `real/midpoint/fix-confined` | ✓ verified 0.29 s | ✓ verified 0.17 s | ✓ verified 0.24 s |
| `real/midpoint/search-within-bound` | ✓ verified 56.43 s | ✓ verified 26.24 s | ✓ verified 29.52 s |
| `real/bucket/fixed-property` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `real/bucket/fix-confined` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `real/oddity/fixed-property` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `real/oddity/fix-confined` | ✓ verified 0.29 s | ✓ verified 0.18 s | ✓ verified 0.23 s |
| `real/checksum/fixed-property` | ✓ verified 0.41 s | ✓ verified 0.21 s | ✓ verified 0.31 s |
| `real/checksum/fix-confined` | ✓ verified 18.25 s | ✓ verified 7.01 s | ✓ verified 9.69 s |
| `held/saturating` | ✓ verified 0.28 s | ✓ verified 0.17 s | ✓ verified 0.22 s |
| `held/average/bits` | ✓ verified 0.28 s | ✓ verified 0.17 s | ✓ verified 0.22 s |
| `held/floor-mod/jdk` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/ceil-div` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/lower-bound` | ✓ verified 5.10 s | ✓ verified 1.78 s | ✓ verified 3.45 s |
| `held/utf8-length` | ✓ verified 0.77 s | ✓ verified 0.83 s | ✓ verified 0.77 s |
| `held/reverse` | – out of memory 6.6 s | – out of memory 7.0 s | – out of memory 6.8 s |
| `held/prefix-sums` | ✓ verified 3.58 s | ✓ verified 3.53 s | ✓ verified 3.48 s |
| `held/overlap/meets` | ✓ verified 0.29 s | ✓ verified 0.18 s | ✓ verified 0.23 s |
| `example/141` | ✓ verified 60.76 s | ✓ verified 30.58 s | ✓ verified 33.61 s |
| `example/142` | – out of memory 9.2 s | – out of memory 9.2 s | – out of memory 9.5 s |

</details>

<details><summary>Counterexamples, jbmc under strict, 55 cases: each case, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/capacity/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/builderCapacity/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/mapCapacity/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/setCapacity/1` | – gap 0.2 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/loadFactor/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/nullMonitor/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/firstByte/1` | – gap 0.1 s | – gap 0.1 s | – gap 0.1 s |
| `conformance/hiding/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/hidden/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) |
| `conformance/sameLiteral/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/otherLiteral/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/sameClass/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/concatenated/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/boom/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/inherited/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/finallyWins/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) |
| `conformance/caught/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/nestedHandler/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/element/2` | ✓ violation 0.17 s, `[];0` (max 0; found 7 el., max 15) | ✓ violation 0.16 s, `[];0` (max 0; found 7 el., max 2147483647) | ✓ violation 0.16 s, `[];0` (max 0; found 7 el., max 15) |
| `conformance/cast/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `1` (max 1; found max 2147483647) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/throwNull/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/rethrown/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1; found max 2147483648) | ✓ violation 0.21 s, `-1` (max 1; found max 2147483648) |
| `conformance/aliasedLocals/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/aliasedObjects/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/nullLocal/2` | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/width/2` | ✓ violation 0.26 s, `-1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.16 s, `-1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.21 s, `-1;2147483647` (max 2147483647; found max 2147483647) |
| `conformance/width/3` | ✓ violation 0.16 s, `1;0` (max 1) | ✓ violation 0.16 s, `1;0` (max 1) | ✓ violation 0.16 s, `1;0` (max 1) |
| `conformance/clamp/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.21 s, `-1` (max 1) |
| `conformance/pairsEqual/2` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/sides/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/code/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.24 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/divide/2` | ✓ violation 0.28 s, `-2147483648;-1` (max 2147483648) | ✓ violation 0.16 s, `-2147483648;-1` (max 2147483648) | ✓ violation 0.21 s, `-2147483648;-1` (max 2147483648) |
| `conformance/divide/4` | ✓ violation 0.26 s, `0;0` (max 0; found max 15) | ✓ violation 0.24 s, `0;0` (max 0; found max 1) | ✓ violation 0.18 s, `0;0` (max 0; found max 15) |
| `conformance/divideLong/1` | ✓ violation 0.29 s, `-9223372036854775808;-1` (max 9223372036854775808) | ✓ violation 0.17 s, `-9223372036854775808;-1` (max 9223372036854775808) | ✓ violation 0.22 s, `-9223372036854775808;-1` (max 9223372036854775808) |
| `conformance/remainder/2` | ✓ violation 0.23 s, `-1;2` (max 2; found max 65535) | ✓ violation 0.17 s, `-1;2` (max 2; found max 2147483647) | ✓ violation 0.23 s, `-1;2` (max 2; found max 2147483647) |
| `conformance/remainderLong/2` | ✓ violation 0.22 s, `-1;50` (max 2; found max 65535) | ✓ violation 0.17 s, `-1;50` (max 2; found max 9223372036854775807) | ✓ violation 0.22 s, `-1;50` (max 2; found max 9223372036854775807) |
| `conformance/shiftLeft/2` | ✓ violation 0.21 s, `-1;32` (max 32) | ✓ violation 0.16 s, `-1;32` (max 32) | ✓ violation 0.21 s, `-1;32` (max 32) |
| `conformance/shiftLeftLong/2` | ✓ violation 0.22 s, `-1;64` (max 64) | ✓ violation 0.16 s, `-1;64` (max 64) | ✓ violation 0.21 s, `-1;64` (max 64) |
| `conformance/shiftRight/2` | ✓ violation 0.22 s, `-1;33` (max 33) | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/shiftUnsigned/1` | ✓ violation 0.21 s, `-1;32` (max 32) | ✓ violation 0.16 s, `-1;32` (max 32; found max 2147483648) | ✓ violation 0.21 s, `-1;32` (max 32; found max 2147483648) |
| `conformance/square/1` | ✓ violation 0.21 s, `46341` (max 46341; found max 65535) | ✓ violation 0.16 s, `-46341` (max 46341; found max 1073741823) | ✓ violation 0.21 s, `-46341` (max 46341; found max 1073741823) |
| `conformance/negate/1` | ✓ violation 0.28 s, `-2147483648` (max 2147483648) | ✓ violation 0.16 s, `-2147483648` (max 2147483648) | ✓ violation 0.21 s, `-2147483648` (max 2147483648) |
| `conformance/toByte/1` | ✓ violation 0.22 s, `128` (max 128) | ✓ violation 0.17 s, `128` (max 128) | ✓ violation 0.21 s, `128` (max 128) |
| `conformance/toChar/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.21 s, `-1` (max 1) |
| `conformance/fromLong/1` | ✓ violation 0.26 s, `2147483648` (max 2147483648; found max 4611686018427387904) | ✓ violation 0.16 s, `2147483648` (max 2147483648; found max 4611686018427387904) | ✓ violation 0.21 s, `2147483648` (max 2147483648; found max 4611686018427387904) |
| `conformance/nextChar/2` | ✓ violation 0.16 s, `65535` (max 65535) | ✓ violation 0.16 s, `65535` (max 65535) | ✓ violation 0.16 s, `65535` (max 65535) |
| `conformance/absolute/1` | ✓ violation 0.27 s, `-2147483648` (max 2147483648) | ✓ violation 0.16 s, `-2147483648` (max 2147483648) | ✓ violation 0.21 s, `-2147483648` (max 2147483648) |
| `conformance/byteSum/2` | ✓ violation 0.23 s, `0;-1` (max 1; found max 128) | ✓ violation 0.16 s, `0;-1` (max 1; found max 128) | ✓ violation 0.21 s, `0;-1` (max 1; found max 128) |
| `real/midpoint/broken-property` | ✓ violation 0.26 s, `1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.16 s, `1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.21 s, `1;2147483647` (max 2147483647; found max 2147483647) |
| `real/bucket/broken-property` | ✓ violation 0.27 s, `-2147483648;3` (max 2147483648; found max 2147483648) | ✓ violation 0.16 s, `-2147483648;3` (max 2147483648; found max 2147483648) | ✓ violation 0.21 s, `-2147483648;3` (max 2147483648; found max 2147483648) |
| `real/oddity/broken-property` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1; found max 2147483647) | ✓ violation 0.22 s, `-1` (max 1; found max 2147483647) |
| `real/checksum/broken-property` | ✓ violation 0.43 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) | ✓ violation 0.21 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) | ✓ violation 0.32 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) |
| `held/average/unsigned-shift` | ✓ violation 0.23 s, `0;-1` (max 1; found max 1) | ✓ violation 0.18 s, `0;-1` (max 1; found max 2147483648) | ✓ violation 0.23 s, `0;-1` (max 1; found max 2147483648) |
| `held/floor-mod/wide-modulus` | ✓ violation 15.44 s, `637534207;1509949441` (max 1509949441; found max 1509949441) | ✓ violation 0.34 s, `637534207;1509949441` (max 1509949441; found max 1509949441) | ✓ violation 0.39 s, `637534207;1509949441` (max 1509949441; found max 1509949441) |
| `held/overlap/length` | ✓ violation 0.35 s, `-1;2147483647;-1;2147483647` (max 2147483647) | ✓ violation 0.18 s, `-1;2147483647;-1;2147483647` (max 2147483647) | ✓ violation 0.23 s, `-1;2147483647;-1;2147483647` (max 2147483647) |

</details>

<details><summary>Proofs, auto under strict, 2 cases: each case where JBMC's fallback ran, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/quiet/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/pairsEqual/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |

</details>

<details><summary>Counterexamples, auto under strict, 4 cases: each case where JBMC's fallback ran, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/loadFactor/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/boom/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) |
| `conformance/inherited/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) |
| `conformance/pairsEqual/2` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |

</details>

## The JVM against the corpus

Every expected answer of groups 2 and 3 is borne out on the JVM.

Every witness an engine reported reproduces on the JVM.
