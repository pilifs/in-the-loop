# Working draft: a downstream JBMC patch queue

**WORKING DRAFT. Not a loop brief yet: don't run it.** It is for the user to refine and weigh over time. It has no
Loop settings on purpose, and nothing here is approved. It was split out of [`sound-verdicts.md`](sound-verdicts.md)
on 2026-11-05, where it had been the last phase. That brief's Phase 5 measurements are the evidence this one waits for.

The input is [`sound-verdicts-review-jbmc.md`](sound-verdicts-review-jbmc.md), an outside review of CBMC/JBMC at
commit `8e018d0c0ef67`, read against this repository at `c4fa2f64`.

## The question

Should the project maintain a small downstream branch of JBMC, and if so, with which patches?

The review's view:
- The shared CBMC engine is actively maintained (6.11.0, August 2026). Taking it over would be a large commitment.
- Java-specific development is thin: five commits to `jbmc/src` in a year. The Java models bundle is pinned to an
  October 2022 revision with known defects.
- So the strongest case is control over **Java semantics and models**, then a few **focused encoding patches**, with
  the branch kept close to upstream.

What [`sound-verdicts.md`](sound-verdicts.md) already does without a fork:
- JBMC's own approximations (reachable stubs, the zero/null `invokedynamic` fallback) become gaps (its Phase 4c).
- Redundant interval stages, the per-check deadline and `--json-ui` are adapter work (Phase 4a, 4b).
- The models the project relies on are already its own (`lib/models`).

A fork has to earn its keep beyond all that.

## Candidate patches, in the review's order

Each would be measured on `sound-verdicts.md`'s Phase 5 corpus before and after, and dropped if it doesn't pay.

1. **Strict Java mode.** JBMC itself refuses reachable missing bodies, unapproved stubs and unsupported bootstrap
   methods, instead of the adapter detecting them from output. It makes Phase 4c's gaps native to JBMC.
2. **Model selection separated from string refinement.** Today `--refine-strings` also swaps in JBMC's Character
   replacements, which is why the project runs `--no-refine-strings`. `forDigit` ignores its radix, for example.
   Separating them would let string reasoning back in with the project's own models.
3. **One shared quotient/remainder encoding.** `a / b` and `a % b` each build a full divider today. Cache the pair by
   (dividend, divisor, width, signedness). It has to keep Java's zero-divisor exception and `MIN_VALUE / -1`. The
   review's best first performance candidate.
4. **Same-width modular multiplication without sign circuitry.** The low w bits of a product are the same signed and
   unsigned. Keep the overflow, widened, fixed-point and floating-point paths as they are.

Larger engine work, only with strong evidence from the measurements:
- array representations chosen by read/write counts, with lazy consistency constraints;
- persistent symbolic prefixes with incremental solving across paths;
- a compiled-model cache behind a worker pool;
- structural hashing of Boolean gates.

## What it would take

- **Network access** to fetch CBMC at a pinned commit, and an **ARM64 build from source** as a pipeline job. The build
  is long and heavy: estimate it before the first job.
- **A patch queue in the repository** (proposed: `lib/jbmc/patches/`), applied to the pinned commit. The resulting
  JBMC is recorded by version and patch-set digest in every attempt.
- **A standing commitment.** Each upstream release means rebasing the queue and re-running the conformance and
  benchmark corpora.
- **Upstream reports** (the `forDigit` radix bug, `--incremental-loop` not wired into JBMC's checker selection,
  unbounded trace output for nondeterministic strings) are outward-facing. They would be drafted for the user, never
  filed by an agent.

## Open questions for the user

1. Is a fork worth it at all, given `sound-verdicts.md`'s adapter work and the native engine's growing fragment? The
   Phase 5 table is meant to answer this.
2. If yes: which patches first? The review suggests strict mode and model selection for correctness, and
   quotient/remainder for performance.
3. Contribute patches upstream, keep them downstream, or both?
4. Where does the CBMC build run, and how is it cached across jobs?

## Evidence: where each engine's time goes

`sound-verdicts.md`'s step 5b measures it. Each checker run is split into the same phases for both engines
(`lib/src/phases.rs`): `loading`, `lowering`, `symbolic`, `encoding`, `solving`, `trace`, and JBMC's start and output
(`checker-other`). Each run also gets its formula's size: JBMC's SSA steps, and the variables and clauses. JBMC's
times are its own `Runtime` lines plus the times of its messages (`--timestamp monotonic`). A run cut off by its
deadline or its memory gives the rest of its time to the phase it was in.

**The table** is `lib/benchmark/RESULTS.md`, section "Where the time goes, by workload, under strict". It covers the
benchmark corpus and examples 141 and 142, under one configuration: one harness, unwind 16, arrays of up to 8, a
120 s deadline, the models on, and CaDiCaL on both. It comes from pipeline job
`20261106-102624-benchmark-corpus-with-per-phase-measurem` (passed, collected 2026-11-06), at commit `b2e3b9c5`: before
the own checker's functional-consistency lemma, so `real/bucket/fix-confined` is out of time on both engines there.

**Which phase each candidate would shrink**, so the table can rank them:

| Candidate | Phase it acts on in JBMC | Workloads where that phase must dominate for it to pay |
|---|---|---|
| 3. shared quotient/remainder | `encoding` (Convert SSA), then `solving` through fewer clauses | `div-rem` |
| 4. modular multiplication | `encoding`, `solving` | `scalar-arithmetic`, `div-rem` |
| array representations | `encoding` and `solving` (the formula's size) | `binary-search`, `utf8`, `array-mutation` |
| persistent prefixes, incremental solving | `symbolic`, and `solving` repeated across stages | branch-heavy cases; the interval stages run JBMC up to three times |
| compiled-model cache, worker pool | `loading`, `lowering`, `checker-other`, and the preflight (`gaps`) | every short check |
| structural hashing of gates | `encoding`, the formula's size | any |
| 1. strict mode, 2. model selection | none: these are about correctness, and do not show in the table | |

**First figures, inline, before the job** (one machine, one run each, not the table):
- `real/midpoint/search-within-bound`, the whole bounded `binarySearch` before and after its fix, arrays of up to 8:
  - JBMC: 45 s and 1.4 GB, 94% of it solving a formula of 3.28 million clauses;
  - the own checker: 3.1 s, 88% solving, 240,000 clauses.

  Here the formula's size dominates, which is the array-representation candidate's case, not the arithmetic one's.
- Small cases (`real/midpoint`'s three others): JBMC takes about 0.1 s per run. JBMC's start and output are a fifth
  of a check, its goto preflight another fifth, and the interval stages run it up to three times.
- Example 142 on the own checker: 7.3 s, 95% solving.

**What the table says (job `-102624`), and the ranking it gives.**
- Correctness: 0 false successes under strict and advised on either engine, 0 false alarms, every expected answer and
  witness borne out on the JVM. Under assume, the false successes (7 own checker, 8 JBMC) all name their gap.
- JBMC gives no verdict where the own checker decides in under a second: `held/floor-mod/jdk` and `held/ceil-div`
  out of time (own checker 0.16 s, 0.10 s), `held/reverse` out of memory at 17 million clauses (0.21 s), example 142
  out of memory (7.2 s). Where both decide, JBMC's formula is 10 to 35 times larger: `search-within-bound` 3.3 million
  clauses and 59 s against 240,000 and 2.8 s; example 141 4.7 million and 65 s against 137,000 and 2.2 s.
- Solving dominates every workload whose runs take more than a second, on both engines (82–99%). On short checks
  JBMC's start and output and its preflight are about half its time; the own checker's driver about 50 ms.

Ranked by that evidence:
1. **Array representations** would pay most: `binary-search`, `utf8` and `array-mutation` lose by the formula's
   size. It is the larger engine work the queue asks strong evidence for, and the own checker already wins there by
   20 to 30 times.
2. **Shared quotient/remainder (3)** would help where `/` and `%` share operands (`floor-mod`), not where equal
   values are written differently (`fix-confined`, which the own checker closed with a congruence lemma).
3. **Compiled-model cache, worker pool** pays only on checks that take under a second already.
4. **Modular multiplication (4), structural hashing, persistent prefixes**: no workload in the table where their
   phase stands out.

**Recommendation (for the user's decision, open question 1):** no fork for performance. The patches the table
favours are engine-scale work where the own checker already decides, so JBMC stays stock, as the fallback under
`--engine auto` and the second checker under `--confirm`. A fork stays worth reconsidering only for the correctness
patches (1, strict mode; 2, model selection), if JBMC's string reasoning is wanted back.

## Notes

- Nothing yet.
