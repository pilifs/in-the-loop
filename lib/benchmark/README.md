# The benchmark corpus

Steps 5a and 5b of [`llm-dlc/loops/sound-verdicts.md`](../../llm-dlc/loops/sound-verdicts.md): before an optimization
is chosen, measure both engines on a corpus that did not motivate the optimizations, keep correctness, coverage, time
and memory apart, and split each engine's time into its phases. An unsupported case is not a success, and a `Verified`
the JVM refutes outweighs any speed.

The corpus is in three groups, and a fourth for the phase measurements:

| Group | What | Cases | Where |
|---|---|---:|---|
| 1, semantic conformance | the conformance corpus of step 1d: small methods with claims about gaps, identity, initialization, exceptions, aliasing, `null` arrays, records and arithmetic edge cases | 98 claims | [`conformance.json`](conformance.json), written by `the_benchmark_takes_its_first_group_from_this_corpus` in [`../tests/conformance.rs`](../tests/conformance.rs) |
| 2, real regressions | four documented bugs, each with the broken and the fixed version (`src/broken`, `src/fixed`): the broken version's property refuted, the fixed version's proved, and a regression proof that the fix changes only the inputs it was meant to | 13 | [`corpus.json`](corpus.json) |
| 3, held-out performance cases | regressions written for the benchmark after the engines' optimizations (`src/v1` to `src/v3`), one or more per workload, kept as first written whatever an engine makes of them | 12 | [`corpus.json`](corpus.json) |
| 4, recorded examples | the reviews' case studies, examples 141 (a bisection rewritten half-open, `binary-search`) and 142 (an ASCII fast path for a modified UTF-8 encoder, `utf8`), their claims read from their `example.json` and their patches applied to Mica; under strict alone, since they reach no gap. Their expected answer is the recorded one, and they are not in the JVM's search | 2 | `RECORDED` in [`run.py`](run.py) |

Group 2's bugs, each cited in its source file and in `corpus.json`:

- **JDK-5045582**, `Arrays.binarySearch`'s midpoint `(low + high) / 2` overflowing (fixed in JDK 6 with `>>> 1`).
  Also the whole search, which the two versions do alike on every array of up to 8 elements: the overflow needs one
  of more than 2^30, so the bug is real and outside the proof's domain, and the expected answer is `verified`.
- **FindBugs' `RV_ABSOLUTE_VALUE_OF_HASHCODE`**: `Math.abs(hash) % buckets` is negative for `Integer.MIN_VALUE`.
- **Java Puzzlers, Puzzle 1**: `i % 2 == 1` is false for a negative odd `i`.
- **CERT NUM00-J**: a range check `off + len > b.length` that overflows and passes.

No CVE kernel yet: the brief welcomes them where a fixed version exists, and none was added in this step.

The workloads are the ones step 5b's per-phase table is over: `scalar-arithmetic`, `div-rem`, `binary-search`,
`utf8`, `array-mutation` and `records`, with `array-bounds` for the range check and `semantics` for group 1.

## The answers, from the JVM

Every case has an expected answer, `verified` or `violation`, and it does not come from the tool:

- **Group 1**: a claim is `violation` when one of the calls the corpus lists refutes it on a JVM, which the
  conformance test checks every time it runs; otherwise `verified`, as the corpus states it.
- **Groups 2 and 3**: [`Reference.java`](Reference.java) writes out each case's claim in Java, apart from the tool's
  harness generator and its expression language, and runs the versions in a class loader each. A `violation` case
  names an input, its `witness`, which the JVM must refute the claim on. For a `verified` case it searches for a
  refutation among boundary values (every combination, for int parameters) and 200,000 inputs drawn with a fixed seed,
  arrays of up to 8 elements. That is evidence, not a proof. Each case also says `why` it holds or fails.

Every violation an engine reports is run on the JVM too: group 1's through the harness the tool generated and the
conformance runner ([`../tests/conformance/Runner.java`](../tests/conformance/Runner.java)), as the conformance
test does; groups 2 and 3's through `Reference.java`. A witness the JVM does not reproduce is a false alarm, whatever
the tool's own replay said.

## What a run is

Each case runs on each engine (`native`, the tool's own checker; `jbmc`) under each gap mode (`strict`, `assume`,
`advised`). The configurations are matched: the tool generates one harness, which both engines check, with the same
unwinding (16), the same array bound (8), the tool's JDK models on both, the same deadline for the whole check (120 s
by default), and the same gap mode. Their solvers differ: CaDiCaL 1.9.5 bundled with the own checker, and the CaDiCaL
JBMC 6.11.0 bundles, which the tool asks for. Under `advised` no agent writes contracts: a run applies the contract
library's ([`../models/contracts/`](../models/contracts/README.md)) with `--max-trust 0`, and a gap the library does
not close stops it with the advice.

A run is one of:

| Class | Meaning |
|---|---|
| `correct` | the expected verdict, assuming nothing |
| `correct-assuming` | the expected verdict, under `assume`, naming a gap it assumed |
| `unsupported` | no verdict, with the reason: a gap refused, contracts needed, out of time or memory, engines disagreeing, a witness that did not reproduce, or a construct the engine refuses |
| `false-success` | `Verified` for a claim the JVM refutes; `false-success-assuming` when the verdict names the gap it assumed, which is what `assume` promises and no more |
| `false-alarm` | a violation of a claim the JVM bears out, or one whose witness the JVM does not reproduce |

For each run the runner keeps the wall-clock and CPU seconds, the peak resident memory of `jvmcontract` and of every
process it waited for (JBMC, the JVM it tests contracts on), read from `wait4`, and what the solver side reports (the
own checker's paths, solver calls, variables and clauses; JBMC's runs, each with its stage, seconds and ending).

Each run also keeps the SAT solver its verdict was solved on, as the result's evidence names it (`sat`, from the
JSON's `stated.checker.sat`, [`../src/statement.rs`](../src/statement.rs)): the `solver`, its `version`, its `source`
and its `configuration`. For the own checker that is the solver `JVMCONTRACT_SOLVER` chooses, as it records itself
(`Sat::record` in [`../src/bmc/sat.rs`](../src/bmc/sat.rs)): by default CaDiCaL as the Rust crate `cadical` bundles it,
the version from CaDiCaL's signature and the crate's from `Cargo.lock`, run incrementally with its default options;
under `bitwuzla` or `bitwuzla-words`, Bitwuzla as [`../solvers/bitwuzla/`](../solvers/bitwuzla/README.md) describes
its record. For JBMC it
is the solver the adapter asks for, `--sat-solver cadical`, with the version of the CaDiCaL linked into the JBMC
executable, read from CaDiCaL's signature there (`cadical-3.0.0` in JBMC 6.11.0's), and the options every JBMC run
passes; a JBMC that holds no CaDiCaL is recorded with its default solver, which the runs then fall back to.
`results.json`'s `environment.sat` lists each engine's solvers once, and `RESULTS.md` names them under its first line.
Job `20261106-102624`'s results predate this ([`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md) step
1b) and name none.

## Where the time goes (step 5b)

Each checker run reports its seconds in the same phases for both engines ([`../src/phases.rs`](../src/phases.rs)),
and the size of the formula it solved:

| Phase | The own checker | JBMC 6.11.0 |
|---|---|---|
| `loading` | reading and parsing class files | its first message to `Generating GOTO Program` |
| `lowering` | decoding methods | the GOTO program and its passes, to `Starting Bounded Model Checking` |
| `symbolic` | exploring the paths, gates evaluated in path models included | `Runtime Symex` and `Runtime Postprocess Equation` |
| `encoding` | building circuits, as the paths are explored; one operation in 64 is timed, since a clock read costs about 0.3 µs on WSL2 | `Runtime Convert SSA` and `Runtime Post-process` |
| `solving` | CaDiCaL's calls | `Runtime Solver`, less the `Runtime Post-process` timed inside it |
| `trace` | reading the witness out of a model | `Building error trace` to the next message |
| `checker-other` | nothing | the rest of the run: starting, printing |

JBMC's times come from its own `Runtime` lines and from the times of its messages (`--timestamp monotonic`), read
per solver call: `Runtime Solver` times the whole call, post-processing included, so that is counted under
`encoding` alone, and a call that ran out of memory before CaDiCaL started is all `encoding`. A run cut off by its
deadline or its memory gives the rest of its time to the phase it was in, so a timeout says where it was spent.
The phases are exclusive: a checker run's named phases may add up past its seconds by 1% and 5 ms at most (rounding,
and two clocks), and a run past that carries `phases_excess` instead of being scaled to fit. Real JBMC 6.11.0 runs in
[`../tests/fixtures/jbmc-phases/`](../tests/fixtures/jbmc-phases/README.md) show each case. Around the runs, the driver's steps are timed too: `gaps` (the gap scan under advised, JBMC's preflight of
its goto program), `contracts`, `replay` (the interpreter, shrinking), `jvm` (a witness run on a JVM), `harness`,
`setup` (the JDK's classes and the models written to the work directory), and `driver`, the rest of the process.

`RESULTS.md` has a table per workload and engine, under strict, over every run, decided or not: the share of each
phase, the phase that dominates, and the largest formula. Group 4 has a table of its own, since one of its runs
outweighs a whole workload of the corpus. A run whose phases add up past its time (`phasesExcess`: a checker run's
`phases_excess`, or the run's phases past the process's seconds by more than the same tolerance) is left out of
these tables and named under them. The JBMC shares in the current `RESULTS.md`, job `20261106-102624`'s, overcount:
they were recorded before [`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md) step 1a, when
`Runtime Post-process` was counted in both `encoding` and `solving`. They stand as recorded until the next benchmark
job regenerates the page.

## JBMC's staging policies (step 2b)

A JBMC check searches interval stages before the full range (`[0:20]`, then `[-100000:100000]`, then every input),
and `--jbmc-staging` picks which of them run ([`../src/deadline.rs`](../src/deadline.rs), step 2a of
[`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md)): `staged` all of them, `full-range` the full
range alone, `tight` the first restricting stage on a fortieth of the check and then the full range. The runner's
`--jbmc-staging` takes a list of them, and makes every run of an engine that may call JBMC once per policy: `jbmc`,
and `auto` (the own checker, then JBMC's fallback on what it leaves without a verdict). An `auto` run whose own
checker decided under the first policy is not made again, since JBMC never ran. Each such run records its `staging`,
and `auto`'s whether it fell back to JBMC (`fallback`).

The tables of the corpus, the phase tables among them, are over the first policy. "JBMC's staging policies" in
`RESULTS.md` compares the others with it, per engine and mode, with the proofs (cases expected `verified`) and the
counterexamples (expected `violation`) apart: how many each decides correctly, leaves without a verdict, or gets
wrong, their seconds, how many runs change class from the first policy's, how many witnesses are larger than its,
and how many runs left without a verdict gave the full range under a second or none (*starved*: under `auto`, two
`staged` stages out of time can take the whole fallback). Its case-by-case tables, under strict, give each policy's
verdict and time and each witness.

**The default, from job `20261106-201041` (step 2c): `full-range`.** That job ran the corpus under all three. Under
strict, JBMC's proofs were the same 54 of 65 under each policy, in 654 s under `staged`, 575 s under `full-range` and
588 s under `tight` (medians 0.26, 0.15 and 0.20 s); the hard ones took half the time without the stages (the bounded
binary search 26 s against 56 s, example 141 31 s against 61 s, checksum's fix-confined 7 s against 18 s). Its
counterexamples took 9 s against 27 s, and no shrunk witness was larger, though the witnesses found over every input
were (up to `Long.MAX_VALUE`) and took more interpreter runs to shrink (190 on `remainderLong/2`, where `staged` took
49), still in less time. No run under `full-range` was starved; under `staged` and `tight`, three were, all without a
verdict for other reasons. The one case whose class changed,
`conformance/shiftRight/2` (a violation under `staged`, witness not reproduced under the others, in every mode), is
JBMC's unmasked right shift, a defect `staged`'s witness happened to miss
([`../tests/fixtures/jbmc-defects/README.md`](../tests/fixtures/jbmc-defects/README.md)). Under `auto` the policies
gave the same verdicts. So `full-range` became the default of `--jbmc-staging` for ordinary checks and `auto`'s
fallback, and of the runner's own `--jbmc-staging`; the own checker keeps its stages.

A witness is measured as reported, after [`../src/shrink.rs`](../src/shrink.rs) shrank it in the interpreter
(`witnessSize`), and, when shrinking changed it, as the engine found it (`foundSize`, with `shrinkRuns`): the elements
of its arrays and the largest magnitude among its values. A larger witness is one with more elements or a larger
value.

## Running it

```bash
python3 lib/benchmark/run.py --engines native --groups 2,3,4        # under a minute: the own checker only
python3 lib/benchmark/run.py --out lib/benchmark/results.json --table lib/benchmark/RESULTS.md   # both engines: a pipeline job
python3 lib/benchmark/run.py --engines native,jbmc,auto --jbmc-staging staged,full-range,tight \
    --out lib/benchmark/results.json --table lib/benchmark/RESULTS.md                          # step 2b's job
python3 lib/benchmark/run.py --render lib/benchmark/results.json    # the tables again from a results file
python3 -m unittest lib/benchmark/test_run.py                       # the runner's tests; no proof runs
```

It compiles the version trees and the conformance class into `lib/target/benchmark`, asks the JVM for the answers,
runs every case, checks the witnesses, and writes the results and the tables. It exits 1 on a false success or a
false alarm, or when the JVM does not bear out an expected answer. A JBMC run is a proof, so the full run is a
pipeline job (see [`verification/README.md`](../../verification/README.md)); [`RESULTS.md`](RESULTS.md) and
[`results.json`](results.json) are what the last one wrote. Run as one, the results name the job and the commit it ran
at (`environment.job` and `commit`, from the pipeline's `VERIFY_JOB_ID` and `VERIFY_SOURCE_COMMIT`), and so does the
page's first line.

## Adding a case

Add the version's source under `src/`, a case to `corpus.json` with its source, `why` and, for a violation, a
witness, and the same id with its claim to `Reference.java`. `test_run.py` fails when the two lists differ, or when a
case names a class its versions do not have. A held-out case is one written after the optimizations it might favour:
write it, record it, and do not change it to suit an engine. Group 1 grows with the conformance corpus: add the case
there and run its test with `JVMCONTRACT_BLESS=1`.
