# Benchmark results

Written by `lib/benchmark/run.py` on 2026-11-07T20:20:14+0000, as pipeline job `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso`, at commit `c9995ae17d82`, on 28 × AMD RYZEN AI MAX+ 395 w/ Radeon 8060S (x86_64), with jvmcontract 0.1.0, JBMC 6.11.0 (cbmc-6.11.0) and openjdk version "25.0.5" 2026-10-20 LTS. Every run had a deadline of 120 s, loops unwound 16 times and arrays of up to 8 elements, on both engines. What the columns mean is in [README.md](README.md).

Every run of an engine that may call JBMC was made under each of JBMC's staging policies, `staged`, `full-range`, `tight`. The tables of the corpus are over `staged`, and [JBMC's staging policies](#jbmcs-staging-policies) compares the others with it.

SAT solvers: the own checker on CaDiCaL 1.9.5, bundled by the Rust crate cadical 0.1.16; JBMC on CaDiCaL 3.0.0, linked into JBMC (/usr/bin/jbmc), the version as its signature there reads; auto on CaDiCaL 1.9.5, bundled by the Rust crate cadical 0.1.16 and CaDiCaL 3.0.0, linked into JBMC (/usr/bin/jbmc), the version as its signature there reads. Their configuration is under `environment.sat` in `results.json`.

## Correctness and coverage

| group | engine | mode | cases | correct | of them assuming a gap | unsupported | false success | false alarm | total s | median s | max s | peak MB |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 semantic conformance | native | strict | 160 | 130 | 0 | 30 | 0 | 0 | 5.7 | 0.03 | 0.06 | 40.8 |
| 1 semantic conformance | native | assume | 160 | 130 | 0 | 25 | 5 (5 naming a gap) | 0 | 5.7 | 0.03 | 0.06 | 40.7 |
| 1 semantic conformance | native | advised | 160 | 135 | 0 | 25 | 0 | 0 | 6.8 | 0.04 | 0.08 | 46.5 |
| 1 semantic conformance | jbmc | strict | 160 | 124 | 0 | 36 | 0 | 0 | 179.0 | 0.25 | 120.05 | 804.2 |
| 1 semantic conformance | jbmc | assume | 160 | 126 | 7 | 26 | 8 (8 naming a gap) | 0 | 179.2 | 0.25 | 120.09 | 804.1 |
| 1 semantic conformance | jbmc | advised | 160 | 125 | 0 | 35 | 0 | 0 | 172.2 | 0.24 | 120.09 | 804.1 |
| 1 semantic conformance | auto | strict | 160 | 133 | 0 | 27 | 0 | 0 | 8.6 | 0.04 | 0.49 | 46.9 |
| 1 semantic conformance | auto | assume | 160 | 133 | 1 | 20 | 7 (7 naming a gap) | 0 | 8.5 | 0.04 | 0.48 | 46.8 |
| 1 semantic conformance | auto | advised | 160 | 135 | 0 | 25 | 0 | 0 | 7.3 | 0.04 | 0.28 | 46.4 |
| 2 real regressions | native | strict | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.05 | 1.74 | 71.1 |
| 2 real regressions | native | assume | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.05 | 1.77 | 71.0 |
| 2 real regressions | native | advised | 13 | 13 | 0 | 0 | 0 | 0 | 2.9 | 0.06 | 1.75 | 77.9 |
| 2 real regressions | jbmc | strict | 13 | 12 | 0 | 1 | 0 | 0 | 194.0 | 0.28 | 120.06 | 1354.4 |
| 2 real regressions | jbmc | assume | 13 | 12 | 0 | 1 | 0 | 0 | 193.9 | 0.28 | 120.07 | 1354.4 |
| 2 real regressions | jbmc | advised | 13 | 12 | 0 | 1 | 0 | 0 | 194.0 | 0.35 | 120.08 | 1354.3 |
| 2 real regressions | auto | strict | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.05 | 1.74 | 71.4 |
| 2 real regressions | auto | assume | 13 | 13 | 0 | 0 | 0 | 0 | 2.8 | 0.06 | 1.73 | 70.7 |
| 2 real regressions | auto | advised | 13 | 13 | 0 | 0 | 0 | 0 | 2.9 | 0.06 | 1.75 | 77.0 |
| 3 held-out performance cases | native | strict | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.6 | 46.3 |
| 3 held-out performance cases | native | assume | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.07 | 0.6 | 44.6 |
| 3 held-out performance cases | native | advised | 12 | 12 | 0 | 0 | 0 | 0 | 1.9 | 0.07 | 0.61 | 49.6 |
| 3 held-out performance cases | jbmc | strict | 12 | 9 | 0 | 3 | 0 | 0 | 281.4 | 1.95 | 120.07 | 5413.7 |
| 3 held-out performance cases | jbmc | assume | 12 | 9 | 0 | 3 | 0 | 0 | 281.0 | 2.0 | 120.07 | 5413.6 |
| 3 held-out performance cases | jbmc | advised | 12 | 9 | 0 | 3 | 0 | 0 | 281.9 | 2.07 | 120.1 | 5413.9 |
| 3 held-out performance cases | auto | strict | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.61 | 47.0 |
| 3 held-out performance cases | auto | assume | 12 | 12 | 0 | 0 | 0 | 0 | 1.8 | 0.06 | 0.61 | 46.1 |
| 3 held-out performance cases | auto | advised | 12 | 12 | 0 | 0 | 0 | 0 | 1.9 | 0.07 | 0.62 | 49.8 |
| 4 recorded examples | native | strict | 2 | 2 | 0 | 0 | 0 | 0 | 6.0 | 2.98 | 4.67 | 81.1 |
| 4 recorded examples | jbmc | strict | 2 | 1 | 0 | 1 | 0 | 0 | 76.0 | 38.01 | 60.46 | 5545.8 |
| 4 recorded examples | auto | strict | 2 | 2 | 0 | 0 | 0 | 0 | 6.0 | 3.02 | 4.73 | 83.0 |

Why the unsupported cases had no verdict:

- group 1, native, strict: 27 gap, 3 refused
- group 1, native, assume: 22 gap, 3 refused
- group 1, native, advised: 23 needs contracts, 2 refused
- group 1, jbmc, strict: 19 gap, 9 refused, 7 witness not reproduced, 1 out of time
- group 1, jbmc, assume: 14 witness not reproduced, 11 refused, 1 out of time
- group 1, jbmc, advised: 13 needs contracts, 9 refused, 7 witness not reproduced, 5 gap, 1 out of time
- group 1, auto, strict: 26 gap, 1 refused
- group 1, auto, assume: 15 gap, 4 witness not reproduced, 1 refused
- group 1, auto, advised: 23 needs contracts, 2 gap
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
| array-bounds | native | 3 | 3 | 0 | 0 | 0.05 | 0.44 | 41.2 |
| array-bounds | jbmc | 3 | 3 | 0 | 0 | 0.41 | 15.06 | 370.0 |
| array-bounds | auto | 3 | 3 | 0 | 0 | 0.05 | 0.45 | 41.8 |
| array-mutation | native | 2 | 2 | 0 | 0 | 0.1 | 0.15 | 40.1 |
| array-mutation | jbmc | 2 | 1 | 1 | 0 | 3.18 | 15.96 | 5413.7 |
| array-mutation | auto | 2 | 2 | 0 | 0 | 0.1 | 0.15 | 40.7 |
| binary-search | native | 3 | 3 | 0 | 0 | 1.3 | 1.74 | 71.1 |
| binary-search | jbmc | 3 | 3 | 0 | 0 | 55.9 | 60.46 | 2059.8 |
| binary-search | auto | 3 | 3 | 0 | 0 | 1.3 | 1.74 | 71.4 |
| div-rem | native | 9 | 9 | 0 | 0 | 0.06 | 0.6 | 46.3 |
| div-rem | jbmc | 9 | 6 | 3 | 0 | 0.27 | 120.07 | 54.9 |
| div-rem | auto | 9 | 9 | 0 | 0 | 0.06 | 0.61 | 47.0 |
| records | native | 2 | 2 | 0 | 0 | 0.07 | 0.07 | 38.3 |
| records | jbmc | 2 | 2 | 0 | 0 | 0.31 | 0.34 | 55.5 |
| records | auto | 2 | 2 | 0 | 0 | 0.07 | 0.07 | 38.5 |
| scalar-arithmetic | native | 6 | 6 | 0 | 0 | 0.06 | 0.12 | 37.8 |
| scalar-arithmetic | jbmc | 6 | 6 | 0 | 0 | 0.28 | 0.29 | 54.8 |
| scalar-arithmetic | auto | 6 | 6 | 0 | 0 | 0.06 | 0.12 | 37.8 |
| semantics | native | 160 | 130 | 30 | 0 | 0.04 | 0.06 | 40.8 |
| semantics | jbmc | 160 | 124 | 36 | 0 | 0.23 | 120.05 | 804.2 |
| semantics | auto | 160 | 133 | 27 | 0 | 0.04 | 0.49 | 46.9 |
| utf8 | native | 2 | 2 | 0 | 0 | 2.5 | 4.67 | 81.1 |
| utf8 | jbmc | 2 | 1 | 1 | 0 | 0.72 | 15.57 | 5545.8 |
| utf8 | auto | 2 | 2 | 0 | 0 | 2.53 | 4.73 | 83.0 |

## Where the time goes, by workload, under strict

Each engine's seconds over every run of the workload, decided or not, as shares of the phases of `lib/src/phases.rs`: the checker's own (`loading` to `trace`, and `checker-other`, JBMC starting and printing), then the driver's (`gaps` and JBMC's preflight, `contracts`, `replay` and shrinking, the `jvm` witness run, the `harness`, the `setup` of the work directory with the JDK's classes and the models, and the rest of the process as `driver`). Step 5b of the sound-verdicts brief.

| workload | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| array-bounds | native | 3 | 0.52 | · | · | 4% | 5% | 68% | · | · | · | · | 0% | · | · | 4% | 19% | **solving** 68% | 45662 |
| array-bounds | jbmc | 3 | 15.88 | 0% | 0% | 1% | 3% | 90% | 0% | 3% | 1% | · | · | · | · | 0% | 1% | **solving** 90% | 762544 |
| array-bounds | auto | 3 | 0.54 | · | · | 4% | 5% | 67% | · | · | · | · | 0% | · | · | 4% | 20% | **solving** 67% | 45662 |
| array-mutation | native | 2 | 0.2 | · | · | 1% | 6% | 41% | · | · | · | · | · | · | · | 6% | 45% | **driver** 45% | 59707 |
| array-mutation | jbmc | 2 (1 undecided) | 19.14 | 0% | 0% | 1% | 15% | 74% | · | 8% | 1% | · | · | · | · | 0% | 1% | **solving** 74% | 17233885 |
| array-mutation | auto | 2 | 0.2 | · | · | 1% | 7% | 41% | · | · | · | · | · | · | · | 7% | 44% | **driver** 44% | 59707 |
| binary-search | native | 2 | 1.99 | · | · | 2% | 4% | 88% | · | · | · | · | · | · | · | 1% | 5% | **solving** 88% | 240144 |
| binary-search | jbmc | 2 | 60.44 | 0% | 0% | 1% | 3% | 95% | · | 0% | 0% | · | · | · | · | 0% | 0% | **solving** 95% | 3281450 |
| binary-search | auto | 2 | 2.0 | · | · | 2% | 4% | 88% | · | · | · | · | · | · | · | 1% | 5% | **solving** 88% | 240144 |
| div-rem | native | 9 | 1.02 | · | · | 0% | 2% | 53% | · | · | · | · | 0% | · | · | 6% | 38% | **solving** 53% | 55638 |
| div-rem | jbmc | 9 (3 undecided) | 376.91 | 0% | 0% | 0% | 0% | 99% | 0% | 0% | 0% | · | 0% | · | · | 0% | 0% | **solving** 99% | 49832 |
| div-rem | auto | 9 | 1.03 | · | · | 0% | 2% | 53% | · | · | · | · | 0% | · | · | 6% | 38% | **solving** 53% | 55638 |
| records | native | 2 | 0.13 | · | · | · | 1% | 1% | · | · | · | · | 10% | · | · | 10% | 79% | **driver** 79% | 7451 |
| records | jbmc | 2 | 0.62 | 11% | 4% | 6% | 2% | 11% | 0% | 24% | 20% | · | 0% | · | · | 2% | 21% | **checker-other** 24% | 13325 |
| records | auto | 2 | 0.13 | · | · | · | 1% | 1% | · | · | · | · | 10% | · | · | 10% | 79% | **driver** 79% | 7451 |
| scalar-arithmetic | native | 6 | 0.39 | · | · | · | 2% | 22% | · | · | · | · | 0% | · | · | 10% | 66% | **driver** 66% | 20540 |
| scalar-arithmetic | jbmc | 6 | 1.63 | 4% | 1% | 1% | 1% | 4% | 0% | 42% | 22% | · | 0% | · | · | 3% | 21% | **checker-other** 42% | 4221 |
| scalar-arithmetic | auto | 6 | 0.39 | · | · | · | 1% | 22% | · | · | · | · | 0% | · | · | 11% | 65% | **driver** 65% | 20540 |
| semantics | native | 160 (30 undecided) | 5.73 | · | · | 0% | 1% | 1% | · | · | · | · | 0% | · | · | 19% | 79% | **driver** 79% | 100555 |
| semantics | jbmc | 160 (36 undecided) | 179.01 | 3% | 1% | 1% | 2% | 77% | 0% | 6% | 7% | · | 0% | · | · | 1% | 4% | **solving** 77% | 2712459 |
| semantics | auto | 160 (27 undecided) | 8.6 | 4% | 1% | 3% | 1% | 1% | 1% | 8% | 13% | · | 0% | · | · | 13% | 56% | **driver** 56% | 100555 |
| utf8 | native | 1 | 0.33 | · | · | 6% | 10% | 66% | · | · | · | · | · | · | · | 2% | 15% | **solving** 66% | 23224 |
| utf8 | jbmc | 1 | 0.72 | 0% | 0% | 8% | 5% | 64% | · | 6% | 8% | · | · | · | · | 1% | 7% | **solving** 64% | 173454 |
| utf8 | auto | 1 | 0.32 | · | · | 6% | 11% | 68% | · | · | · | · | · | · | · | 2% | 13% | **solving** 68% | 23224 |

### The recorded examples

| id | engine | runs | s | loading | lowering | symbolic | encoding | solving | trace | checker-other | gaps | contracts | replay | jvm | harness | setup | driver | dominant | largest formula (clauses) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| example/141 | native | 1 | 1.3 | · | · | 2% | 3% | 89% | · | · | · | · | · | · | · | 0% | 5% | **solving** 89% | 137013 |
| example/141 | jbmc | 1 | 60.46 | 0% | 0% | 0% | 4% | 95% | · | 0% | 0% | · | · | · | · | 0% | 0% | **solving** 95% | 4718689 |
| example/141 | auto | 1 | 1.3 | · | · | 2% | 3% | 90% | · | · | · | · | · | · | · | 1% | 5% | **solving** 90% | 137013 |
| example/142 | native | 1 | 4.67 | · | · | 1% | 2% | 96% | · | · | · | · | · | · | · | 0% | 1% | **solving** 96% | 161165 |
| example/142 | jbmc | 1 (1 undecided) | 15.57 | 0% | 0% | 4% | 65% | · | · | 31% | 0% | · | · | · | · | 0% | 0% | **encoding** 65% | – |
| example/142 | auto | 1 | 4.73 | · | · | 1% | 1% | 96% | · | · | · | · | · | · | · | 0% | 1% | **solving** 96% | 161165 |

## Group 1: semantic conformance, case by case

The JVM's answer is the conformance test's (`lib/tests/conformance.rs`), on the calls the corpus lists.

<details><summary>All 160 claims</summary>

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `conformance/capacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s | – gap 0.3 s | ✗ₐ verified 0.29 s | ✓ violation 0.35 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s |
| `conformance/builderCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s | – gap 0.3 s | ✗ₐ verified 0.29 s | ✓ violation 0.33 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s |
| `conformance/mapCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s | – gap 0.3 s | ✗ₐ verified 0.29 s | ✓ violation 0.33 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s |
| `conformance/setCapacity/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.06 s | – gap 0.3 s | ✗ₐ verified 0.30 s | ✓ violation 0.34 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.05 s |
| `conformance/loadFactor/1` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | ✗ₐ verified 0.29 s | – needs contracts 0.1 s | – gap 0.3 s | ✗ₐ verified 0.31 s | – needs contracts 0.0 s |
| `conformance/nullMonitor/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | – gap 0.3 s | ✗ₐ verified 0.25 s | – gap 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/monitor/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – gap 0.3 s | ✓ₐ verified 0.25 s | – gap 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/firstByte/1` | violation | conformance test | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.08 s | – gap 0.2 s | ✗ₐ verified 0.19 s | ✓ violation 0.35 s | – gap 0.0 s | ✗ₐ verified 0.03 s | ✓ violation 0.10 s |
| `conformance/hiding/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/hiding/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/hidden/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/hidden/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/sameLiteral/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/sameLiteral/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/otherLiteral/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/otherLiteral/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/sameClass/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.27 s | ✓ verified 0.31 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/sameClass/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/concatenated/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – gap 0.3 s | ✓ₐ verified 0.25 s | – gap 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/concatenated/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ₐ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/boom/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/inherited/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/quiet/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/counter/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/counter/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.15 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/constructed/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/constructed/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/superFirst/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/superFirst/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/cycle/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/cycle/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/declaring/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/declaring/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/defaults/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/defaults/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/defaults/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/fatal/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.27 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/fatal/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/boomTwice/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/boomTwice/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumState/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.32 s | ✓ verified 0.32 s | ✓ verified 0.33 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/enumState/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumValues/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/enumValues/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumSwitch/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/enumSwitch/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumBodies/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.31 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/enumBodies/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumBroken/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/enumBroken/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/enumValueOf/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.2 s | – witness not reproduced 0.2 s | – needs contracts 0.1 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/enumValueOf/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.20 s | ✓ₐ violation 0.20 s | – needs contracts 0.1 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listSizes/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.2 s | – witness not reproduced 0.2 s | – needs contracts 0.2 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listSizes/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.20 s | ✓ₐ violation 0.21 s | – needs contracts 0.1 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listNull/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ verified 0.30 s | ✓ verified 0.30 s | ✓ verified 0.34 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listNull/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.20 s | ✓ violation 0.20 s | ✓ violation 0.21 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listChange/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.2 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listChange/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.28 s | ✓ₐ violation 0.27 s | – needs contracts 0.2 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listCopySame/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ verified 14.03 s | ✓ verified 14.10 s | ✓ verified 14.02 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listCopySame/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 2.59 s | ✓ violation 2.36 s | ✓ violation 2.36 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listCopyMutable/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 3.7 s | – refused 3.7 s | – needs contracts 0.3 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listCopyMutable/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 3.6 s | – refused 3.6 s | – needs contracts 0.3 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listGet/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listGet/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/listSearch/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.2 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.0 s |
| `conformance/listSearch/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.27 s | ✓ₐ violation 0.30 s | – needs contracts 0.2 s | ✓ violation 0.28 s | ✓ₐ violation 0.28 s | – needs contracts 0.0 s |
| `conformance/listEquals/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.2 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.0 s |
| `conformance/listEquals/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.2 s | – gap 0.3 s | – witness not reproduced 0.3 s | – needs contracts 0.0 s |
| `conformance/listIterate/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | – refused 0.4 s | – refused 0.4 s | – refused 0.5 s | – refused 0.4 s | – refused 0.4 s | – needs contracts 0.0 s |
| `conformance/listIterate/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.28 s | ✓ violation 0.27 s | ✓ violation 0.28 s | ✓ violation 0.31 s | ✓ violation 0.28 s | – needs contracts 0.0 s |
| `conformance/listOfArray/1` | verified | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ verified 0.48 s | ✓ verified 0.48 s | ✓ verified 0.49 s | ✓ verified 0.49 s | ✓ verified 0.48 s | – needs contracts 0.0 s |
| `conformance/listOfArray/2` | violation | conformance test | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.28 s | – gap 0.0 s | – gap 0.0 s | – needs contracts 0.0 s |
| `conformance/finallyWins/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/finallyWins/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/caught/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/caught/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/caught/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/caughtAsRuntime/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/caughtAsRuntime/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/nestedHandler/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.09 s |
| `conformance/nestedHandler/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/element/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/element/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.18 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/cast/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/cast/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/throwNull/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/throwNull/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/rethrown/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/rethrown/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/aliasedLocals/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/aliasedLocals/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/aliasedObjects/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/aliasedObjects/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/swaps/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/swaps/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/swapsOrNull/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/swapsOrNull/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/swapsOrNull/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/swapsThenNull/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.28 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/swapsThenNull/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/swapsThenNull/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/twoArrays/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.16 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/writeThrough/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/length/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/lengthOrMinusOne/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.15 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/nullLocal/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/nullLocal/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/width/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/width/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.28 s | ✓ violation 0.27 s | ✓ violation 0.28 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/width/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/clamp/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/clamp/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.23 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/pairsEqual/1` | verified | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.0 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s | – gap 0.2 s | – witness not reproduced 0.2 s | – gap 0.2 s |
| `conformance/pairsEqual/2` | violation | conformance test | – refused 0.0 s | – refused 0.0 s | – refused 0.0 s | – gap 0.3 s | ✗ₐ verified 0.25 s | – gap 0.3 s | – gap 0.3 s | ✗ₐ verified 0.27 s | – gap 0.3 s |
| `conformance/sides/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/sides/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.18 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/code/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/code/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divide/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.27 s | ✓ verified 0.29 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/divide/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divide/3` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – out of time 120.0 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/divide/4` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divideLong/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.27 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/divideLong/2` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/remainder/1` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.32 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `conformance/remainder/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s |
| `conformance/remainder/3` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/remainderLong/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/remainderLong/2` | violation | conformance test | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.06 s | ✓ violation 0.07 s | ✓ violation 0.07 s |
| `conformance/shiftLeft/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/shiftLeft/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/shiftLeft/3` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/shiftLeftLong/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/shiftLeftLong/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/shiftLeftLong/3` | verified | conformance test | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.27 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s |
| `conformance/shiftRight/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/shiftRight/2` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.07 s | ✓ violation 0.23 s | ✓ violation 0.23 s | ✓ violation 0.21 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `conformance/shiftRight/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/shiftUnsigned/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/shiftUnsigned/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/shiftUnsigned/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | – refused 0.3 s | – refused 0.3 s | – refused 0.3 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/square/1` | violation | conformance test | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.05 s |
| `conformance/negate/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.27 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/toByte/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/toByte/2` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/toChar/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/toChar/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/toShort/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/fromLong/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.26 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/nextChar/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.20 s | ✓ verified 0.20 s | ✓ verified 0.21 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/nextChar/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/absolute/1` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/increment/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.35 s | ✓ verified 0.28 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/byteSum/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.20 s | ✓ verified 0.20 s | ✓ verified 0.21 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.03 s |
| `conformance/byteSum/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.23 s | ✓ violation 0.22 s | ✓ violation 0.22 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/leadingZeros/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.30 s | ✓ verified 0.31 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/leadingZeros/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.04 s |
| `conformance/leadingZeros/3` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `conformance/leadingZerosLong/1` | verified | conformance test | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.41 s | ✓ verified 0.41 s | ✓ verified 0.41 s | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `conformance/leadingZerosLong/2` | violation | conformance test | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.16 s | ✓ violation 0.16 s | ✓ violation 0.17 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |

</details>

## Group 2: real regressions, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `real/midpoint/broken-property` | violation | refuted returns -1073741824 | ✓ violation 0.12 s | ✓ violation 0.12 s | ✓ violation 0.13 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.28 s | ✓ violation 0.12 s | ✓ violation 0.12 s | ✓ violation 0.13 s |
| `real/midpoint/fixed-property` | verified | held 40579 | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.27 s | ✓ verified 0.27 s | ✓ verified 0.28 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `real/midpoint/fix-confined` | verified | held 121136 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | ✓ verified 0.29 s | ✓ verified 0.29 s | ✓ verified 0.35 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `real/midpoint/search-within-bound` | verified | held 200000 | ✓ verified 1.74 s | ✓ verified 1.77 s | ✓ verified 1.75 s | ✓ verified 55.90 s | ✓ verified 55.89 s | ✓ verified 55.91 s | ✓ verified 1.74 s | ✓ verified 1.73 s | ✓ verified 1.75 s |
| `real/bucket/broken-property` | violation | refuted returns -2 | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.27 s | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s |
| `real/bucket/fixed-property` | verified | held 122010 | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.26 s | ✓ verified 0.04 s | ✓ verified 0.03 s | ✓ verified 0.04 s |
| `real/bucket/fix-confined` | verified | held 127354 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `real/oddity/broken-property` | violation | refuted returns false | ✓ violation 0.05 s | ✓ violation 0.04 s | ✓ violation 0.05 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.21 s | ✓ violation 0.04 s | ✓ violation 0.04 s | ✓ violation 0.05 s |
| `real/oddity/fixed-property` | verified | held 200017 | ✓ verified 0.03 s | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.27 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.05 s |
| `real/oddity/fix-confined` | verified | held 127076 | ✓ verified 0.07 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s |
| `real/checksum/broken-property` | violation | refuted returns 0 | ✓ violation 0.05 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.41 s | ✓ violation 0.43 s | ✓ violation 0.42 s | ✓ violation 0.05 s | ✓ violation 0.06 s | ✓ violation 0.06 s |
| `real/checksum/fixed-property` | verified | held 200000 | ✓ verified 0.03 s | ✓ verified 0.04 s | ✓ verified 0.04 s | ✓ verified 0.41 s | ✓ verified 0.41 s | ✓ verified 0.41 s | ✓ verified 0.04 s | ✓ verified 0.05 s | ✓ verified 0.04 s |
| `real/checksum/fix-confined` | verified | held 190209 | ✓ verified 0.44 s | ✓ verified 0.45 s | ✓ verified 0.46 s | ✓ verified 15.06 s | ✓ verified 14.96 s | ✓ verified 14.90 s | ✓ verified 0.45 s | ✓ verified 0.45 s | ✓ verified 0.45 s |

## Group 3: held-out performance cases, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `held/saturating` | verified | held 200289 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `held/average/bits` | verified | held 200289 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `held/average/unsigned-shift` | violation | refuted before: returns -1; after: returns 2147483647 | ✓ violation 0.06 s | ✓ violation 0.08 s | ✓ violation 0.06 s | ✓ violation 0.23 s | ✓ violation 0.23 s | ✓ violation 0.30 s | ✓ violation 0.06 s | ✓ violation 0.06 s | ✓ violation 0.06 s |
| `held/floor-mod/wide-modulus` | violation | refuted before: returns -3; after: returns 2147483646 | ✓ violation 0.60 s | ✓ violation 0.60 s | ✓ violation 0.61 s | ✓ violation 15.42 s | ✓ violation 15.39 s | ✓ violation 15.49 s | ✓ violation 0.61 s | ✓ violation 0.61 s | ✓ violation 0.62 s |
| `held/floor-mod/jdk` | verified | held 122010 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s |
| `held/ceil-div` | verified | held 122010 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.07 s |
| `held/lower-bound` | verified | held 130860 | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s | ✓ verified 4.55 s | ✓ verified 4.55 s | ✓ verified 4.62 s | ✓ verified 0.25 s | ✓ verified 0.25 s | ✓ verified 0.26 s |
| `held/utf8-length` | verified | held 200000 | ✓ verified 0.33 s | ✓ verified 0.33 s | ✓ verified 0.32 s | ✓ verified 0.72 s | ✓ verified 0.72 s | ✓ verified 0.79 s | ✓ verified 0.32 s | ✓ verified 0.32 s | ✓ verified 0.33 s |
| `held/reverse` | verified | held 200000 | ✓ verified 0.15 s | ✓ verified 0.14 s | ✓ verified 0.16 s | – out of memory 16.0 s | – out of memory 15.5 s | – out of memory 15.7 s | ✓ verified 0.15 s | ✓ verified 0.15 s | ✓ verified 0.16 s |
| `held/prefix-sums` | verified | held 200000 | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s | ✓ verified 3.18 s | ✓ verified 3.28 s | ✓ verified 3.34 s | ✓ verified 0.05 s | ✓ verified 0.05 s | ✓ verified 0.06 s |
| `held/overlap/meets` | verified | held 52777 | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.28 s | ✓ verified 0.28 s | ✓ verified 0.35 s | ✓ verified 0.06 s | ✓ verified 0.06 s | ✓ verified 0.06 s |
| `held/overlap/length` | violation | refuted before: returns 0; after: returns 2147483647 | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s | ✓ violation 0.34 s | ✓ violation 0.34 s | ✓ violation 0.41 s | ✓ violation 0.07 s | ✓ violation 0.07 s | ✓ violation 0.08 s |

## Group 4: recorded examples, case by case

| case | expected | the JVM | native strict | native assume | native advised | jbmc strict | jbmc assume | jbmc advised | auto strict | auto assume | auto advised |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `example/141` | verified | recorded example | ✓ verified 1.30 s |  |  | ✓ verified 60.46 s |  |  | ✓ verified 1.30 s |  |  |
| `example/142` | verified | recorded example | ✓ verified 4.67 s |  |  | – out of memory 15.6 s |  |  | ✓ verified 4.73 s |  |  |

## JBMC's staging policies

Step 2b of [`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md): every run of `jbmc`, and of `auto` where the own checker gave no verdict and JBMC's fallback ran, under each of the policies of `--jbmc-staging` (`lib/src/deadline.rs`): `staged` runs every interval stage that restricts the inputs before the full range, `full-range` the full range alone, `tight` the first restricting stage on a fortieth of the check, then the full range. Everything else is the same: the deadline, the bounds, the models and the evidence rules. Proofs (cases expected `verified`) and counterexamples (expected `violation`) are counted apart. A witness is measured as reported, after `lib/src/shrink.rs` shrank it in the interpreter: the elements of its arrays and its largest magnitude. *Changed* counts the runs whose class differs from the same case's under `staged`, *larger* the witnesses bigger than its, and *starved* the runs left without a verdict that gave the full range less than a second, or none.

| engine | mode | kind | policy | correct | no verdict | wrong | total s | median s | changed | larger witnesses | shrunk | starved | no verdict, why |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| jbmc | strict | proofs | `staged` | 71 of 96 | 25 | 0 | 690.1 | 0.26 | 0 | · | · | 14 | 9 gap, 7 witness not reproduced, 4 out of time, 3 refused, 2 out of memory |
| jbmc | strict | proofs | `full-range` | 71 of 96 | 25 | 0 | 600.5 | 0.15 | 0 | · | · | 0 | 9 gap, 7 witness not reproduced, 4 out of time, 3 refused, 2 out of memory |
| jbmc | strict | proofs | `tight` | 71 of 96 | 25 | 0 | 620.9 | 0.2 | 0 | · | · | 13 | 8 gap, 7 witness not reproduced, 5 out of time, 3 refused, 2 out of memory |
| jbmc | strict | counterexamples | `staged` | 75 of 91 | 16 | 0 | 40.3 | 0.21 | 0 | 0 | 23 | 2 | 10 gap, 6 refused |
| jbmc | strict | counterexamples | `full-range` | 74 of 91 | 17 | 0 | 21.7 | 0.16 | 1 | 0 | 24 | 0 | 10 gap, 6 refused, 1 witness not reproduced |
| jbmc | strict | counterexamples | `tight` | 74 of 91 | 17 | 0 | 26.8 | 0.2 | 1 | 0 | 26 | 1 | 9 gap, 6 refused, 1 out of time, 1 witness not reproduced |
| jbmc | assume | proofs | `staged` | 72 of 94 | 22 | 0 | 614.0 | 0.26 | 0 | · | · | 14 | 13 witness not reproduced, 4 refused, 4 out of time, 1 out of memory |
| jbmc | assume | proofs | `full-range` | 72 of 94 | 22 | 0 | 554.5 | 0.15 | 0 | · | · | 0 | 13 witness not reproduced, 4 refused, 4 out of time, 1 out of memory |
| jbmc | assume | proofs | `tight` | 72 of 94 | 22 | 0 | 572.2 | 0.2 | 0 | · | · | 13 | 13 witness not reproduced, 5 out of time, 3 refused, 1 out of memory |
| jbmc | assume | counterexamples | `staged` | 75 of 91 | 8 | 8 | 40.1 | 0.21 | 0 | 0 | 23 | 2 | 7 refused, 1 witness not reproduced |
| jbmc | assume | counterexamples | `full-range` | 74 of 91 | 9 | 8 | 21.5 | 0.16 | 1 | 0 | 24 | 0 | 7 refused, 2 witness not reproduced |
| jbmc | assume | counterexamples | `tight` | 74 of 91 | 9 | 8 | 26.8 | 0.2 | 1 | 0 | 26 | 1 | 6 refused, 2 witness not reproduced, 1 out of time |
| jbmc | advised | proofs | `staged` | 70 of 94 | 24 | 0 | 611.2 | 0.26 | 0 | · | · | 8 | 7 witness not reproduced, 6 needs contracts, 4 out of time, 3 gap, 3 refused, 1 out of memory |
| jbmc | advised | proofs | `full-range` | 70 of 94 | 24 | 0 | 552.3 | 0.16 | 0 | · | · | 0 | 7 witness not reproduced, 6 needs contracts, 4 out of time, 3 gap, 3 refused, 1 out of memory |
| jbmc | advised | proofs | `tight` | 70 of 94 | 24 | 0 | 566.4 | 0.21 | 0 | · | · | 8 | 7 witness not reproduced, 6 needs contracts, 4 out of time, 3 gap, 3 refused, 1 out of memory |
| jbmc | advised | counterexamples | `staged` | 76 of 91 | 15 | 0 | 36.9 | 0.17 | 0 | 0 | 21 | 0 | 7 needs contracts, 6 refused, 2 gap |
| jbmc | advised | counterexamples | `full-range` | 75 of 91 | 16 | 0 | 18.5 | 0.16 | 1 | 0 | 26 | 0 | 7 needs contracts, 6 refused, 2 gap, 1 witness not reproduced |
| jbmc | advised | counterexamples | `tight` | 75 of 91 | 16 | 0 | 20.8 | 0.17 | 1 | 0 | 28 | 0 | 7 needs contracts, 6 refused, 2 gap, 1 witness not reproduced |
| auto | strict | proofs | `staged` | 1 of 5 | 4 | 0 | 1.7 | 0.32 | 0 | · | · | 3 | 3 gap, 1 refused |
| auto | strict | proofs | `full-range` | 1 of 5 | 4 | 0 | 1.3 | 0.27 | 0 | · | · | 0 | 3 gap, 1 refused |
| auto | strict | proofs | `tight` | 1 of 5 | 4 | 0 | 1.4 | 0.3 | 0 | · | · | 3 | 3 gap, 1 refused |
| auto | strict | counterexamples | `staged` | 2 of 5 | 3 | 0 | 1.5 | 0.3 | 0 | 0 | 1 | 1 | 3 gap |
| auto | strict | counterexamples | `full-range` | 2 of 5 | 3 | 0 | 1.2 | 0.28 | 0 | 0 | 1 | 0 | 3 gap |
| auto | strict | counterexamples | `tight` | 2 of 5 | 3 | 0 | 1.3 | 0.28 | 0 | 0 | 1 | 1 | 3 gap |
| auto | assume | proofs | `staged` | 1 of 5 | 4 | 0 | 1.6 | 0.3 | 0 | · | · | 3 | 3 witness not reproduced, 1 refused |
| auto | assume | proofs | `full-range` | 1 of 5 | 4 | 0 | 1.3 | 0.27 | 0 | · | · | 0 | 3 witness not reproduced, 1 refused |
| auto | assume | proofs | `tight` | 1 of 5 | 4 | 0 | 1.5 | 0.3 | 0 | · | · | 3 | 3 witness not reproduced, 1 refused |
| auto | assume | counterexamples | `staged` | 2 of 5 | 1 | 2 | 1.4 | 0.28 | 0 | 0 | 1 | 1 | 1 witness not reproduced |
| auto | assume | counterexamples | `full-range` | 2 of 5 | 1 | 2 | 1.2 | 0.28 | 0 | 0 | 1 | 0 | 1 witness not reproduced |
| auto | assume | counterexamples | `tight` | 2 of 5 | 1 | 2 | 1.3 | 0.28 | 0 | 0 | 1 | 1 | 1 witness not reproduced |
| auto | advised | proofs | `staged` | 0 of 1 | 1 | 0 | 0.2 | 0.18 | 0 | · | · | 1 | 1 gap |
| auto | advised | proofs | `full-range` | 0 of 1 | 1 | 0 | 0.2 | 0.18 | 0 | · | · | 0 | 1 gap |
| auto | advised | proofs | `tight` | 0 of 1 | 1 | 0 | 0.2 | 0.18 | 0 | · | · | 1 | 1 gap |
| auto | advised | counterexamples | `staged` | 0 of 1 | 1 | 0 | 0.3 | 0.28 | 0 | 0 | 0 | 0 | 1 gap |
| auto | advised | counterexamples | `full-range` | 0 of 1 | 1 | 0 | 0.2 | 0.16 | 0 | 0 | 0 | 0 | 1 gap |
| auto | advised | counterexamples | `tight` | 0 of 1 | 1 | 0 | 0.2 | 0.21 | 0 | 0 | 0 | 0 | 1 gap |

Cases whose class differs between the policies, jbmc under strict: `conformance/shiftRight/2`.

Cases whose class differs between the policies, jbmc under assume: `conformance/shiftRight/2`.

Cases whose class differs between the policies, jbmc under advised: `conformance/shiftRight/2`.

<details><summary>Proofs, jbmc under strict, 96 cases: each case, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/monitor/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/hiding/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/hidden/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/sameLiteral/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/otherLiteral/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/sameClass/1` | ✓ verified 0.27 s | ✓ verified 0.18 s | ✓ verified 0.24 s |
| `conformance/concatenated/1` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/quiet/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/counter/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/constructed/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/superFirst/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/cycle/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/declaring/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/defaults/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/fatal/1` | ✓ verified 0.27 s | ✓ verified 0.17 s | ✓ verified 0.21 s |
| `conformance/boomTwice/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/enumState/1` | ✓ verified 0.32 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/enumValues/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/enumSwitch/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/enumBodies/1` | ✓ verified 0.26 s | ✓ verified 0.20 s | ✓ verified 0.21 s |
| `conformance/enumBroken/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/enumValueOf/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |
| `conformance/listSizes/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |
| `conformance/listNull/1` | ✓ verified 0.30 s | ✓ verified 0.20 s | ✓ verified 0.25 s |
| `conformance/listChange/1` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listCopySame/1` | ✓ verified 14.03 s | ✓ verified 4.89 s | ✓ verified 7.93 s |
| `conformance/listCopyMutable/1` | – gap 3.7 s, full range starved | – gap 3.7 s | – out of time 6.7 s |
| `conformance/listGet/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/listSearch/1` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listEquals/1` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listIterate/1` | – refused 0.4 s | – refused 0.3 s | – refused 0.4 s |
| `conformance/listOfArray/1` | ✓ verified 0.48 s | ✓ verified 0.26 s | ✓ verified 0.38 s |
| `conformance/finallyWins/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/caught/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/caughtAsRuntime/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/nestedHandler/1` | – witness not reproduced 0.2 s, full range starved | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s, full range starved |
| `conformance/element/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/cast/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/throwNull/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.23 s |
| `conformance/rethrown/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/aliasedLocals/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/aliasedObjects/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.19 s |
| `conformance/swaps/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/swapsOrNull/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/swapsOrNull/2` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/swapsThenNull/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/twoArrays/1` | ✓ verified 0.15 s | ✓ verified 0.17 s | ✓ verified 0.15 s |
| `conformance/writeThrough/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/length/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/lengthOrMinusOne/1` | ✓ verified 0.14 s | ✓ verified 0.14 s | ✓ verified 0.14 s |
| `conformance/nullLocal/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/width/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/clamp/1` | ✓ verified 0.26 s | ✓ verified 0.14 s | ✓ verified 0.21 s |
| `conformance/pairsEqual/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |
| `conformance/sides/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/code/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/divide/1` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/divide/3` | – out of time 120.0 s | – out of time 120.1 s | – out of time 120.0 s |
| `conformance/divideLong/2` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/remainder/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/remainder/3` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/remainderLong/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/shiftLeft/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/shiftLeft/3` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/shiftLeftLong/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/shiftLeftLong/3` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/shiftRight/1` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/shiftUnsigned/2` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/toByte/2` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/toChar/1` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `conformance/toShort/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `conformance/nextChar/1` | ✓ verified 0.20 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/increment/1` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/byteSum/1` | ✓ verified 0.20 s | ✓ verified 0.14 s | ✓ verified 0.21 s |
| `conformance/leadingZeros/1` | ✓ verified 0.25 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `conformance/leadingZerosLong/1` | ✓ verified 0.41 s | ✓ verified 0.20 s | ✓ verified 0.31 s |
| `real/midpoint/fixed-property` | ✓ verified 0.27 s | ✓ verified 0.15 s | ✓ verified 0.21 s |
| `real/midpoint/fix-confined` | ✓ verified 0.29 s | ✓ verified 0.17 s | ✓ verified 0.24 s |
| `real/midpoint/search-within-bound` | ✓ verified 55.90 s | ✓ verified 26.09 s | ✓ verified 29.13 s |
| `real/bucket/fixed-property` | ✓ verified 0.26 s | ✓ verified 0.15 s | ✓ verified 0.20 s |
| `real/bucket/fix-confined` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `real/oddity/fixed-property` | ✓ verified 0.25 s | ✓ verified 0.14 s | ✓ verified 0.20 s |
| `real/oddity/fix-confined` | ✓ verified 0.28 s | ✓ verified 0.18 s | ✓ verified 0.22 s |
| `real/checksum/fixed-property` | ✓ verified 0.41 s | ✓ verified 0.19 s | ✓ verified 0.29 s |
| `real/checksum/fix-confined` | ✓ verified 15.06 s | ✓ verified 5.54 s | ✓ verified 8.55 s |
| `held/saturating` | ✓ verified 0.28 s | ✓ verified 0.17 s | ✓ verified 0.23 s |
| `held/average/bits` | ✓ verified 0.28 s | ✓ verified 0.17 s | ✓ verified 0.23 s |
| `held/floor-mod/jdk` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/ceil-div` | – out of time 120.1 s | – out of time 120.1 s | – out of time 120.1 s |
| `held/lower-bound` | ✓ verified 4.55 s | ✓ verified 1.74 s | ✓ verified 3.19 s |
| `held/utf8-length` | ✓ verified 0.72 s | ✓ verified 0.72 s | ✓ verified 0.72 s |
| `held/reverse` | – out of memory 16.0 s | – out of memory 15.5 s | – out of memory 15.5 s |
| `held/prefix-sums` | ✓ verified 3.18 s | ✓ verified 3.33 s | ✓ verified 3.28 s |
| `held/overlap/meets` | ✓ verified 0.28 s | ✓ verified 0.18 s | ✓ verified 0.23 s |
| `example/141` | ✓ verified 60.46 s | ✓ verified 29.75 s | ✓ verified 33.11 s |
| `example/142` | – out of memory 15.6 s | – out of memory 15.5 s | – out of memory 15.3 s |

</details>

<details><summary>Counterexamples, jbmc under strict, 91 cases: each case, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/capacity/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/builderCapacity/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/mapCapacity/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/setCapacity/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.3 s |
| `conformance/loadFactor/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/nullMonitor/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/firstByte/1` | – gap 0.2 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/hiding/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/hidden/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/sameLiteral/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/otherLiteral/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/sameClass/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/concatenated/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/boom/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/inherited/1` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/counter/2` | ✓ violation 0.15 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/constructed/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/superFirst/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/cycle/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/declaring/2` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/defaults/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/defaults/3` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/fatal/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/boomTwice/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/enumState/2` | ✓ violation 0.16 s, `2` (max 2; found max 16) | ✓ violation 0.16 s, `-1` (max 1; found max 2147483648) | ✓ violation 0.16 s, `2` (max 2; found max 16) |
| `conformance/enumValues/2` | ✓ violation 0.16 s, `2` (max 2) | ✓ violation 0.16 s, `2` (max 2) | ✓ violation 0.16 s, `2` (max 2) |
| `conformance/enumSwitch/2` | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) |
| `conformance/enumBodies/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.21 s, `-1` (max 1) |
| `conformance/enumBroken/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/enumValueOf/2` | ✓ violation 0.20 s, `0` (max 0; found max 16) | ✓ violation 0.21 s, `0` (max 0; found max 2147483648) | ✓ violation 0.20 s, `0` (max 0; found max 16) |
| `conformance/listSizes/2` | ✓ violation 0.20 s, `0` (max 0) | ✓ violation 0.20 s, `0` (max 0) | ✓ violation 0.20 s, `0` (max 0) |
| `conformance/listNull/2` | ✓ violation 0.20 s, `0` (max 0) | ✓ violation 0.20 s, `0` (max 0) | ✓ violation 0.20 s, `0` (max 0) |
| `conformance/listChange/2` | ✓ violation 0.28 s, `1` (max 1; found max 11) | ✓ violation 0.27 s, `1` (max 1; found max 1342177281) | ✓ violation 0.27 s, `1` (max 1; found max 11) |
| `conformance/listCopySame/2` | ✓ violation 2.59 s, `0` (max 0; found max 16) | ✓ violation 2.53 s, `0` (max 0; found max 2147483648) | ✓ violation 2.43 s, `0` (max 0; found max 16) |
| `conformance/listCopyMutable/2` | – gap 3.6 s, full range starved | – gap 3.6 s | – out of time 6.7 s |
| `conformance/listGet/2` | ✓ violation 0.16 s, `1` (max 1; found max 8) | ✓ violation 0.16 s, `1` (max 1; found max 15) | ✓ violation 0.16 s, `1` (max 1; found max 8) |
| `conformance/listSearch/2` | ✓ violation 0.27 s, `0` (max 0) | ✓ violation 0.29 s, `0` (max 0) | ✓ violation 0.27 s, `0` (max 0) |
| `conformance/listEquals/2` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listIterate/2` | ✓ violation 0.28 s, `1` (max 1; found max 16) | ✓ violation 0.27 s, `1` (max 1; found max 1073741824) | ✓ violation 0.27 s, `1` (max 1; found max 16) |
| `conformance/listOfArray/2` | ✓ violation 0.27 s, `9` (max 9) | ✓ violation 0.27 s, `9` (max 9) | ✓ violation 0.27 s, `9` (max 9) |
| `conformance/finallyWins/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/caught/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/caught/3` | – refused 0.3 s | – refused 0.2 s | – refused 0.3 s |
| `conformance/caughtAsRuntime/2` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/nestedHandler/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/element/2` | ✓ violation 0.16 s, `[];0` (max 0; found 7 el., max 15) | ✓ violation 0.16 s, `[];0` (max 0; found 7 el., max 2147483647) | ✓ violation 0.16 s, `[];0` (max 0; found 7 el., max 15) |
| `conformance/cast/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `1` (max 1; found max 2147483647) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/throwNull/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/rethrown/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1; found max 2147483648) | ✓ violation 0.21 s, `-1` (max 1; found max 2147483648) |
| `conformance/aliasedLocals/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/aliasedObjects/2` | ✓ violation 0.16 s, `1` (max 1; found max 16) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.16 s, `1` (max 1; found max 16) |
| `conformance/swaps/2` | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) |
| `conformance/swapsOrNull/3` | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) |
| `conformance/swapsThenNull/2` | ✓ violation 0.16 s, `14` (max 14) | ✓ violation 0.16 s, `-2` (max 2) | ✓ violation 0.16 s, `14` (max 14) |
| `conformance/swapsThenNull/3` | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) | ✓ violation 0.16 s, `1` (max 1) |
| `conformance/nullLocal/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/width/2` | ✓ violation 0.28 s, `-1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.16 s, `-1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.21 s, `-1;2147483647` (max 2147483647; found max 2147483647) |
| `conformance/width/3` | ✓ violation 0.16 s, `1;0` (max 1) | ✓ violation 0.16 s, `1;0` (max 1) | ✓ violation 0.16 s, `1;0` (max 1) |
| `conformance/clamp/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.21 s, `-1` (max 1) |
| `conformance/pairsEqual/2` | – gap 0.3 s | – gap 0.1 s | – gap 0.2 s |
| `conformance/sides/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.17 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/code/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/divide/2` | ✓ violation 0.28 s, `-2147483648;-1` (max 2147483648) | ✓ violation 0.16 s, `-2147483648;-1` (max 2147483648) | ✓ violation 0.22 s, `-2147483648;-1` (max 2147483648) |
| `conformance/divide/4` | ✓ violation 0.16 s, `0;0` (max 0; found max 15) | ✓ violation 0.16 s, `0;0` (max 0; found max 1) | ✓ violation 0.16 s, `0;0` (max 0; found max 15) |
| `conformance/divideLong/1` | ✓ violation 0.27 s, `-9223372036854775808;-1` (max 9223372036854775808) | ✓ violation 0.16 s, `-9223372036854775808;-1` (max 9223372036854775808) | ✓ violation 0.21 s, `-9223372036854775808;-1` (max 9223372036854775808) |
| `conformance/remainder/2` | ✓ violation 0.21 s, `-1;2` (max 2; found max 65535) | ✓ violation 0.16 s, `-1;2` (max 2; found max 2147483647) | ✓ violation 0.21 s, `-1;2` (max 2; found max 2147483647) |
| `conformance/remainderLong/2` | ✓ violation 0.21 s, `-1;2` (max 2; found max 65535) | ✓ violation 0.16 s, `-1;2` (max 2; found max 9223372036854775807) | ✓ violation 0.21 s, `-1;2` (max 2; found max 9223372036854775807) |
| `conformance/shiftLeft/2` | ✓ violation 0.21 s, `-1;32` (max 32) | ✓ violation 0.16 s, `-1;32` (max 32) | ✓ violation 0.21 s, `-1;32` (max 32) |
| `conformance/shiftLeftLong/2` | ✓ violation 0.21 s, `-1;64` (max 64) | ✓ violation 0.16 s, `-1;64` (max 64) | ✓ violation 0.21 s, `-1;64` (max 64) |
| `conformance/shiftRight/2` | ✓ violation 0.23 s, `-1;33` (max 33) | – witness not reproduced 0.2 s | – witness not reproduced 0.2 s |
| `conformance/shiftRight/3` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/shiftUnsigned/1` | ✓ violation 0.21 s, `-1;32` (max 32) | ✓ violation 0.16 s, `-1;32` (max 32; found max 2147483648) | ✓ violation 0.21 s, `-1;32` (max 32; found max 2147483648) |
| `conformance/shiftUnsigned/3` | – refused 0.3 s | – refused 0.1 s | – refused 0.2 s |
| `conformance/square/1` | ✓ violation 0.21 s, `46341` (max 46341; found max 65535) | ✓ violation 0.16 s, `-46341` (max 46341; found max 1073741823) | ✓ violation 0.21 s, `-46341` (max 46341; found max 1073741823) |
| `conformance/negate/1` | ✓ violation 0.27 s, `-2147483648` (max 2147483648) | ✓ violation 0.16 s, `-2147483648` (max 2147483648) | ✓ violation 0.21 s, `-2147483648` (max 2147483648) |
| `conformance/toByte/1` | ✓ violation 0.21 s, `128` (max 128) | ✓ violation 0.16 s, `128` (max 128) | ✓ violation 0.22 s, `128` (max 128) |
| `conformance/toChar/2` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1) | ✓ violation 0.21 s, `-1` (max 1) |
| `conformance/fromLong/1` | ✓ violation 0.26 s, `2147483648` (max 2147483648; found max 4611686018427387904) | ✓ violation 0.16 s, `2147483648` (max 2147483648; found max 4611686018427387904) | ✓ violation 0.21 s, `2147483648` (max 2147483648; found max 4611686018427387904) |
| `conformance/nextChar/2` | ✓ violation 0.16 s, `65535` (max 65535) | ✓ violation 0.16 s, `65535` (max 65535) | ✓ violation 0.16 s, `65535` (max 65535) |
| `conformance/absolute/1` | ✓ violation 0.27 s, `-2147483648` (max 2147483648) | ✓ violation 0.16 s, `-2147483648` (max 2147483648) | ✓ violation 0.21 s, `-2147483648` (max 2147483648) |
| `conformance/byteSum/2` | ✓ violation 0.23 s, `0;-1` (max 1; found max 128) | ✓ violation 0.17 s, `0;-1` (max 1; found max 128) | ✓ violation 0.21 s, `0;-1` (max 1; found max 128) |
| `conformance/leadingZeros/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `conformance/leadingZeros/3` | ✓ violation 0.16 s, `1` (max 1; found max 2) | ✓ violation 0.16 s, `1` (max 1; found max 2) | ✓ violation 0.16 s, `1` (max 1; found max 2) |
| `conformance/leadingZerosLong/2` | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) | ✓ violation 0.16 s, `0` (max 0) |
| `real/midpoint/broken-property` | ✓ violation 0.28 s, `1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.16 s, `1;2147483647` (max 2147483647; found max 2147483647) | ✓ violation 0.21 s, `1;2147483647` (max 2147483647; found max 2147483647) |
| `real/bucket/broken-property` | ✓ violation 0.27 s, `-2147483648;3` (max 2147483648; found max 2147483648) | ✓ violation 0.16 s, `-2147483648;3` (max 2147483648; found max 2147483648) | ✓ violation 0.21 s, `-2147483648;3` (max 2147483648; found max 2147483648) |
| `real/oddity/broken-property` | ✓ violation 0.21 s, `-1` (max 1) | ✓ violation 0.16 s, `-1` (max 1; found max 2147483647) | ✓ violation 0.21 s, `-1` (max 1; found max 2147483647) |
| `real/checksum/broken-property` | ✓ violation 0.41 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) | ✓ violation 0.21 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) | ✓ violation 0.32 s, `[];4;2147483644` (max 2147483644; found 6 el., max 2147483644) |
| `held/average/unsigned-shift` | ✓ violation 0.23 s, `0;-1` (max 1; found max 1) | ✓ violation 0.18 s, `0;-1` (max 1; found max 2147483648) | ✓ violation 0.23 s, `0;-1` (max 1; found max 2147483648) |
| `held/floor-mod/wide-modulus` | ✓ violation 15.42 s, `637534207;1509949441` (max 1509949441; found max 1509949441) | ✓ violation 0.34 s, `637534207;1509949441` (max 1509949441; found max 1509949441) | ✓ violation 0.39 s, `637534207;1509949441` (max 1509949441; found max 1509949441) |
| `held/overlap/length` | ✓ violation 0.34 s, `-1;2147483647;-1;2147483647` (max 2147483647) | ✓ violation 0.18 s, `-1;2147483647;-1;2147483647` (max 2147483647) | ✓ violation 0.23 s, `-1;2147483647;-1;2147483647` (max 2147483647) |

</details>

<details><summary>Proofs, auto under strict, 5 cases: each case where JBMC's fallback ran, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/listSearch/1` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listEquals/1` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listIterate/1` | – refused 0.4 s | – refused 0.3 s | – refused 0.3 s |
| `conformance/listOfArray/1` | ✓ verified 0.49 s | ✓ verified 0.27 s | ✓ verified 0.38 s |
| `conformance/pairsEqual/1` | – gap 0.2 s, full range starved | – gap 0.2 s | – gap 0.2 s, full range starved |

</details>

<details><summary>Counterexamples, auto under strict, 5 cases: each case where JBMC's fallback ran, per policy</summary>

| case | `staged` | `full-range` | `tight` |
|---|---|---|---|
| `conformance/loadFactor/1` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |
| `conformance/listSearch/2` | ✓ violation 0.28 s, `0` (max 0) | ✓ violation 0.28 s, `0` (max 0) | ✓ violation 0.28 s, `0` (max 0) |
| `conformance/listEquals/2` | – gap 0.3 s, full range starved | – gap 0.3 s | – gap 0.3 s, full range starved |
| `conformance/listIterate/2` | ✓ violation 0.31 s, `1` (max 1; found max 16) | ✓ violation 0.28 s, `1` (max 1; found max 1073741824) | ✓ violation 0.28 s, `1` (max 1; found max 16) |
| `conformance/pairsEqual/2` | – gap 0.3 s | – gap 0.2 s | – gap 0.2 s |

</details>

## The JVM against the corpus

Every expected answer of groups 2 and 3 is borne out on the JVM.

Every witness an engine reported reproduces on the JVM.
