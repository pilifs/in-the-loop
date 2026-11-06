# The own checker's solver: the comparison, and whether to move to word-level solving

Phase 6 of [`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md) asked whether the own checker should stop
bit-blasting and hand word-level bit-vector and array obligations to a solver. The question was about a change of
architecture, not small percentages. This page is Phase 6d's answer. It is a recommendation, not a migration: a
migration would need a brief of its own.

- [`bitwuzla/`](bitwuzla/README.md) builds Bitwuzla 0.8.2 and describes the binding (`JVMCONTRACT_SOLVER=bitwuzla`,
  `bitwuzla-words`).
- [`compare.py`](compare.py) runs the comparison as a pipeline job. Its tests are `test_compare.py`.
- `comparison/` holds the jobs' outputs: `bit-blasted.json` and `.md`, and `word-level.json` and `.md`.

## Recommendation: don't move the engine to word-level solving now

**Keep CaDiCaL 1.9.5 and the engine's own bit-blasting as the default. Keep `bitwuzla-words` as an opt-in
prototype, so a later workload can be measured with one job.** No default changes.

The reasons, from the two jobs below:

1. **Bitwuzla is not the better solver for the engine's own clauses.**
   - Given exactly the engine's clauses, Bitwuzla is slower on every workload:
     - 2 to 43 times slower with its defaults;
     - 1.7 to 14 times slower with `preprocess=0`.
   - The replays of CaDiCaL's own calls are no better. On those calls Bitwuzla gives no contradicting answer, but
     between 1 and 7 calls per replay of binary search and 142 run out of the time limit CaDiCaL was given.
   - So any gain has to come from the encoding, not from swapping the SAT backend.
2. **Word-level terms gain at most 1.9 times, and only with Bitwuzla's preprocessing off.**
   - With `preprocess=0`, the whole check is faster than CaDiCaL on three workloads and level on two:
     - binary search: 1.9 times faster;
     - reverse: 1.7 times faster;
     - 142: 1.3 times faster;
     - 141 and prefix sums: level.
   - With Bitwuzla's defaults, 141 and 142 are slower than CaDiCaL: 1.5 and 2.1 times slower.
   - A gain that depends on turning a default off, and goes away on two of five workloads otherwise, is a tuning
     result. It is not an architectural one.
3. **None of this changes what the tool can decide.**
   - Every solver verified all five workloads, with the same paths and merges. No case moved from undecided to
     decided.
   - The own checker already takes 0.05 to 4.7 s on these workloads. Benchmark job `-102624` had JBMC at 58.6 s and
     65.2 s on binary search and 141, and out of memory on reverse.
   - These five workloads were chosen because the formula's size dominates them, which is where word-level terms
     should help most. There, the formula given to the solver shrinks 44 to 380 times, from 5,637 to 240,144 clauses
     down to 25 to 3,633 word-level operations, and the time falls by less than half.
4. **A migration would cost more than it gains.**
   - **The transcripts would go.** These are 6a's replayable record of every query. A word-level check has no clauses
     to record, so they would need a term format of their own.
   - **The solver would no longer be bundled.** Today the `cadical` crate is compiled in. Bitwuzla is a C library
     loaded at run time, at a pinned version.
   - **It would be a second encoding to keep equal to the JVM.** The prototype's operations are tested against the
     engine's own evaluation, but a migration would make them the semantics.
   - **The array theory isn't built.** It is what would make the change architectural, and it is a change to the
     engine's state, not only to its encoding. It is unmeasured.

### What would change this

Measure again, with `compare.py --words` as it stands, on a workload of either kind:

- **A slow or undecided check where solving dominates.** For example, nonlinear arithmetic, where the engine's lazy
  multiplication and division refine many times, or arrays longer than the bounded cells (`maxArrayLength`) reach.
- **One where the gain grows with the bound.** The prototype hands multiplication and division to Bitwuzla whole, so
  these are its strongest cases. Neither kind is among the benchmark's workloads today.

If such a workload shows a gain of an order of magnitude, the next step is a prototype of the array theory measured
on it. A migration would follow only from that, in a brief of its own.

## The evidence

| Job | Commit | What it measured |
|---|---|---|
| [`20261106-224616`](../../verification/jobs/20261106-224616-the-own-checker-on-cadical-and-on-bitwuz.json) | `09739e6d` | Bit-blasted: full checks, and CaDiCaL's transcripts replayed (passed, 22m41s) |
| [`20261106-230455`](../../verification/jobs/20261106-230455-the-own-checker-on-cadical-and-on-bitwuz.json) | `bbb3062e` | Word-level: full checks (passed, 3m51s) |

Both ran on the same machine:

- **Machine:** vm-1 (`claude-vm`), x86_64, AMD Ryzen AI Max+ 395, 28 CPUs, a shared runner.
- **Software:** OpenJDK 25.0.5 and jvmcontract 0.1.0.
- **Solvers:**
  - CaDiCaL 1.9.5, bundled by the `cadical` crate.
  - Bitwuzla 0.8.2, built by job `-194049`: library sha256 `eac09e6d6f892ae0…`, `sat-solver cadical` (its CaDiCaL
    2.1.2), `produce-models`, and otherwise its defaults or `preprocess=0`.
- **Settings:** each case under strict, unwind 16, arrays up to 8, three runs of each.

Seconds are medians of the whole check, process start to exit.

The CaDiCaL column comes from the word-level job. The bit-blasted job's own CaDiCaL runs were 1.747, 1.436, 4.888,
0.152 and 0.061 s, within 10% of it apart from prefix sums' 10 ms. Each slowdown above is measured against its own
job's CaDiCaL.

| Case | CaDiCaL | Bitwuzla, clauses | Bitwuzla, clauses, `preprocess=0` | Bitwuzla, terms | Bitwuzla, terms, `preprocess=0` | Best terms against CaDiCaL |
|---|---:|---:|---:|---:|---:|---:|
| binary search (`real/midpoint/search-within-bound`) | 1.736 | 27.658 | 25.230 | 1.469 | 0.900 | 1.93× faster |
| `example/141` | 1.316 | 61.600 | 7.373 | 2.037 | 1.279 | 1.03× |
| `example/142` | 4.696 | 41.236 | 18.482 | 10.086 | 3.594 | 1.31× faster |
| `held/reverse` | 0.153 | 3.855 | 1.503 | 0.112 | 0.092 | 1.66× faster |
| `held/prefix-sums` | 0.051 | 0.122 | 0.101 | 0.061 | 0.051 | 1.00× |

The size of what each solver is given, from the same checks:

| Case | Calls, CaDiCaL / terms | Clauses (CaDiCaL) | Word-level operations (terms) | Variables, CaDiCaL / terms | Peak MB, CaDiCaL / terms, `preprocess=0` |
|---|---:|---:|---:|---:|---:|
| binary search | 942 / 937 | 240,144 | 626 | 69,486 / 11,580 | 70 / 68 |
| `example/141` | 1,044 / 1,124 | 137,013 | 694 | 39,635 / 11,400 | 58 / 77 |
| `example/142` | 1,885 / 1,891–1,894 | 161,165 | 3,633 | 43,974 / 33,718 | 82 / 89 |
| `held/reverse` | 115 / 125 | 59,707 | 331 | 16,780 / 7,223 | 39 / 44 |
| `held/prefix-sums` | 18 / 19 | 5,637 | 25 | 1,933 / 531 | 31 / 35 |

- **Solving is still almost all of the time.** CaDiCaL's checks spend 0 to 96% of their time inside solver calls,
  and above 85% on the three large ones.
- **The encoding was already cheap.** It is under 0.1 s in every check on CaDiCaL and on terms. Bit-blasted
  Bitwuzla builds its terms while the clauses are added, and takes up to 0.46 s.
- **The prototype makes slightly more calls.** It folds less than the circuits do, so a few probes that the circuits
  settle as constants become calls.

## Limits of the evidence

- **One machine, three runs each, on a shared runner.** Most ranges are within 10%. The widest are bit-blasted
  Bitwuzla's on binary search: 25.0 to 34.5 s, and 21.0 to 67.0 s with `preprocess=0`.
- **Two solver versions are mixed up in the word-level gain.** Bitwuzla runs CaDiCaL 2.1.2, and the engine runs 1.9.5,
  so part of the word-level gain may be the newer CaDiCaL. No standalone CaDiCaL 2.x is installed to separate the two.
  - Replaying the transcripts on one would settle it, as a small job that fetches and builds it.
  - The brief tries a newer CaDiCaL only where a quick estimate shows more than an incremental gain, and the whole
    word-level gain is below 2×. So this is not done here.
- **The prototype leaves things out.** It has no array theory, and its terms are built from the engine's bits. That
  is the run of one term's bits read back as the term, not a word-level engine.
  - A design built for terms from the start might do better.
  - The measurement bounds what handing these workloads' operations to Bitwuzla gains. It does not bound every
    word-level design.
- **The workloads are the benchmark's.** They are integer and array code, not nonlinear arithmetic or long arrays.
