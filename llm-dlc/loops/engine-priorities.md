# Brief: stock JBMC asked better questions, honest measurements, and wider native coverage

**For the user's final review (2026-11-06). Not approved yet: don't run it.** Once approved, this line becomes the date of
approval. It replaces the "downstream JBMC patch queue" draft, since the evidence below moved the work away from a fork.
That draft is in the history if needed.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh):
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/engine-priorities.md`, in the session and with the model set under
[Loop settings](#loop-settings). The loop runs until the session judges, by [Loop until](#loop-until), that the rest is
not worth another cycle.

**Input:** [`engine-priorities-review.md`](engine-priorities-review.md), an outside review of the repository at `6cea609e`
that reads the raw benchmark results and the JBMC jobs' outputs. **Read it in full before the first piece of work of
every cycle.** Its figures were rechecked against `lib/benchmark/results.json` on 2026-11-06 (below). The fork
candidates of the older [`sound-verdicts-review-jbmc.md`](sound-verdicts-review-jbmc.md) are
[deferred](#deferred-not-in-this-loop). This brief follows [`sound-verdicts.md`](sound-verdicts.md), whose loop is
finished.

## Direction

- **Keep JBMC stock** (6.11.0): the fallback under `--engine auto` and the second checker under `--confirm`. No patches.
- **Ask it better questions.** Change which queries the adapter sends JBMC, not how JBMC solves them.
- **Measure correctly** before using a phase share to direct work.
- **Widen the own checker's semantics** where the evidence shows a JBMC-only win, starting with application class
  initializers. Model the JDK calls that keep sound proofs from standing, rather than trusting contracts for them.
- **Try solvers for a change of architecture, not for percentages.** Capture the incremental queries first, then put
  Bitwuzla against the bundled CaDiCaL.

Every rule the sound-verdicts loop set still holds: strict by default, gaps named, every witness replayed before it is
reported, and a result that says what it established.

## The evidence

Benchmark job `20261106-102624`, 712 runs at `b2e3b9c5`. That commit predates the own checker's functional-consistency
lemma, so `real/bucket/fix-confined` is still out of time there. The figures stand as recorded: don't replace them with
later runs.

**Engines compared case by case** (recounted from `results.json`):

| Mode | Cases | Both correct | Own checker alone | JBMC alone | Neither |
|---|---:|---:|---:|---:|---:|
| strict | 120 | 98 | 10 | 3 | 9 |
| advised | 118 | 102 | 9 | 3 | 4 |

The own checker was faster on every case both decided correctly: 98 of 98 under strict, 102 of 102 under advised.
These are single runs on this corpus.

**Formula sizes** where JBMC's is far larger (clauses):

| Case | Own checker | JBMC | Ratio | Times |
|---|---:|---:|---:|---|
| bounded binary search | 240,144 | 3,281,450 | 13.7× | 2.8 s vs 58.6 s |
| example 141 | 137,013 | 4,718,689 | 34.4× | 2.2 s vs 65.2 s |
| prefix sums | 5,637 | 959,836 | 170× | 0.20 s vs 4.65 s |
| reverse | 59,707 | 17,233,885 | 289× | 0.21 s vs out of memory |

**JBMC's interval stages cost a lot.** Stages are `[0:20]`, then `[-100000:100000]`, then the full range. All three keep
the same array and loop bounds.

| Case | JBMC total | `[0:20]` | `[-100000:100000]` | full range |
|---|---:|---|---|---|
| binary search | 58.6 s | 15.1 s, timeout | 15.1 s, timeout | 28.1 s, verified |
| example 141 | 65.2 s | 15.2 s, timeout | 15.2 s, timeout | 34.6 s, verified |
| checksum fix-confined | 18.5 s | 5.7 s, verified | 6.1 s, verified | 6.5 s, verified |
| lower bound | 7.2 s | 2.3 s, verified | 2.2 s, verified | 2.5 s, verified |
| floor-mod, wide modulus | 15.5 s | 0.05 s, verified | 15.0 s, timeout | 0.25 s, counterexample |
| floor-mod, JDK | 120.1 s | 0.05 s, verified | 15.0 s, timeout | 104.9 s, timeout |

`deadline.rs` already drops a stage that restricts nothing. What is still open is whether a stage that does restrict
the inputs is worth running. These are durations observed inside the staged run, not predictions for a full-range-first
run. Even without the earlier stages, JBMC's last run alone is about 10× the own checker's whole check on binary search
and 16× on example 141.

**The JBMC phase table overcounts.** CBMC 6.11.0 reports `Runtime Post-process` from inside the call that
`Runtime Solver` times (`run_property_decider` → `prop_conv_solvert::dec_solve` → `finish_eager_conversion`).
`lib/src/phases.rs` adds the first to `encoding` and the second to `solving`, so the time is counted twice. On
`held/reverse` the phases add up to 22.0 s against 15.9 s of wall time. The table in `lib/benchmark/RESULTS.md` shows
40% encoding and 87% solving for JBMC on `array-mutation`.
- Wall times, outcomes and clause counts are not affected.
- The claim "82–99% solving on both engines" is withdrawn until this is fixed.
- The own checker's shares are unaffected: binary search 89.6% solving, 141 87.5%, 142 94.2%.

**Coverage.**
- **Class initializers.** All three cases only JBMC wins, under both modes, are application `<clinit>`s:
  `conformance/boom/1`, `inherited/1` and `quiet/1`. The own checker refuses them as `class-initializer` gaps.
  A different solver won't close this gap: the semantics are missing.
- **Floating point.** Example 035 (NaN compared with `equals`) is a JBMC violation that the own checker refuses for its
  floating-point arithmetic. JBMC's value goes beyond the three benchmark wins.
- **Witnesses that don't reproduce.** On `conformance/caught/1` and `nestedHandler/1`, JBMC's counterexample doesn't
  reproduce in the interpreter. The tool answers unverifiable instead of reporting a false alarm. The cause is not known:
  models, exception handling, translation, or reading the trace.
- **Example 071.** Its first two property proofs reach JBMC stubs for `Enum.<init>`, `List.of` and `List.copyOf` (013 reaches the same three).
  Strict turns them into no verdict, while the example's violation label stands. That was projected from job
  `-082917`'s recorded gaps, not from a strict rerun.

**Job `-082917`'s gap table is not reproducible from what was published.** Its build log is committed, but the
per-obligation table was rebuilt by hand and is not.

**Solver identity is not recorded.** `results.json`'s `environment` names JBMC and jvmcontract, not the SAT backend or
its configuration.

## How to work through it

The working rules of [`build-orchestration.md`](build-orchestration.md#how-to-work-through-it) apply:
- one step per cycle, committed on its own;
- check each claim against the code first;
- proofs, model checks and benchmark runs are queued, never run inline;
- recorded results are evidence, not inputs to edit;
- nothing gets weaker;
- docs move with the behaviour;
- defer what needs the user, explicitly.

In addition:
- **The JVM is the semantic reference.** Every new conformance case and model is checked on a real `java`, inline:
  these are milliseconds. A disagreement with the JVM is a bug in jvmcontract, whichever side the verdict falls on.
- **A reproducer before a fix.** A phase overcount gets a fixture that shows it. A witness mismatch gets a failing
  test. A new model gets a conformance case the old behaviour fails.
- **Recorded figures stand.** Job `-102624`'s numbers are not rewritten with later runs. A new measurement is a new job,
  and the table says which job and commit each figure comes from.
- **Defaults change only on a job's evidence.** Phase 2's staging policy and anything Phase 6 suggests are decided
  from queued runs, recorded under Progress with the job id.
- **Tools and versions are part of the evidence.** JBMC 6.11.0, CaDiCaL 1.9.5 as bundled by the `cadical` crate, and
  Bitwuzla once built, each with exact version and configuration (Phase 1b makes this automatic).
- **Nothing outward-facing.** Upstream reports to CBMC/JBMC are drafted for the user, never filed. A network fetch is
  done only inside a pipeline job that says so in its description. If the pipeline has no network, record it as
  needing the user and go on with what doesn't.

## The plan

The order was proposed in review with the user. Phases 2 and 4 are queued work, so carry on with the next phase that
doesn't wait on a job while one runs.

### Phase 1: measurements to trust

- **1a. Exclusive JBMC phases.**
  - Account for nested timers per solver call: CBMC 6.11.0 reports `Runtime Post-process` from inside the call that
    `Runtime Solver` times. Check this against CBMC's source at the 6.11.0 tag before relying on it.
  - Handle a call cut off by the deadline or by memory on its own.
  - Check that the exclusive phase totals match the elapsed time, within a stated tolerance. A run that fails the check
    is flagged, never normalized to 100%.
  - Add fixtures captured from real JBMC 6.11.0 output, in `--json-ui --timestamp monotonic`: success, timeout and
    out of memory. Capturing them is short inline work. Choose cases that finish in seconds.
- **1b. Record the solver.** Record which SAT backend each engine used, with its version and configuration, in
  `results.json`'s environment and in each result's evidence: CaDiCaL's version for the own checker, and JBMC's solver
  and options.
- **1c. Queue the Bitwuzla build** (for Phase 6) as soon as Phase 1 is committed, since it's long. It's a pipeline job
  that fetches a pinned Bitwuzla release and builds it on ARM64. It records the version, the source digest and the
  CaDiCaL it links. Estimate CPUs, memory and duration before submitting.

### Phase 2: which stages JBMC is asked to run

- **2a. A staging policy option** for JBMC checks:
  1. **today's staged search**;
  2. **full range first**;
  3. **one preliminary stage on a tight budget**, then the full range.

  The overall deadline, the bounds, the models and the evidence rules are the same under all three. Unit-test the
  policies on short cases. The full range keeps the same array and loop bounds as the stages.
- **2b. One benchmark job** reruns the whole corpus (groups 1–4) with Phase 1's exclusive phases, and runs the JBMC
  cases under all three policies. Running them together saves a 40-minute rerun. The job's table reports each policy's
  time and verdict per case, proofs and counterexamples apart, and each witness's size after `lib/src/shrink.rs`.
  `shrink.rs` already shrinks any engine's witness through the interpreter to a local minimum. The "Where the time
  goes" table in `lib/benchmark/RESULTS.md` is regenerated from it.
- **2c. Decide from the job.** If a policy is faster without giving worse verdicts or materially larger witnesses, it
  becomes **JBMC's** default, for ordinary checks and for the `auto` fallback. `--confirm` already runs the full range.
  The own checker keeps searching its stages per violating path (decided 2026-11-06): those stages are cheap, and they
  keep its witnesses small.

### Phase 3: the witnesses that don't reproduce

On `conformance/caught/1` and `nestedHandler/1`, JBMC's counterexample (`n=0`) doesn't reproduce in the interpreter,
and the tool answers unverifiable. Find the root cause: the models, exception handling, the harness's translation, or
reading the trace. Keep the replay boundary as it is. Fix the cause with a test if it's in this repository. If it's in
JBMC, draft a report for the user. This is small, inline work: do it while Phase 2's job runs.

### Phase 4: what each engine covers

- **4a. One job over the 41 recorded JBMC examples**, under strict, on both engines.
  - It saves `examples/tools/gap_table.py --json` with its results. That replaces job `-082917`'s projection with a
    measured table, per obligation.
  - Recorded verdicts don't change: a difference from `expected` is reported, not recorded over.
- **4b. Class initializers counted.** Run `jvmcontract gaps` scans (static, inline) over the recorded examples and the
  apps (Mica, Crosscut, Quorum, Box Office). Count `class-initializer` gaps by shape:
  - enums;
  - initializers that assign only constants or literal tables;
  - initializers that throw;
  - initializers that read or write other statics.
- **4c. A coverage inventory** from 4a and 4b: per example, which engine decides, and what stops the other. It ranks
  the next semantic extensions. Floating point (example 035) is the known candidate after Phase 5.

### Phase 5: application class initializers, enums and immutable lists

- **Class initializers in the own checker.** Choose the scope from 4b's count, leaning toward the shapes that occur
  most where they're convenient (decided 2026-11-06). The two choices are full JVMS §5.5 semantics, or initializers
  that only assign constants first.
  - Full semantics run a class's `<clinit>` at its first `new`, `getstatic`, `putstatic` or `invokestatic`, after its
    superclasses' and the relevant superinterfaces', which `bmc/gaps.rs` already orders. It throws
    `ExceptionInInitializerError`, then `NoClassDefFoundError` on a later use.
  - Whatever stays out of scope remains a named gap.
  - The conformance cases `boom`, `inherited` and `quiet` become correct on the own checker, or the Progress note says
    which stay gaps and why.
- **Models for `Enum.<init>`, `List.of` and `List.copyOf` in `lib/models`** (decided 2026-11-06). They become bytecode
  on JBMC's class path and in the interpreter, so they stop being gaps rather than being covered by contracts. Follow
  the rules for adding a model in `lib/models/README.md`.
  - `Enum.<init>(String, int)` sets `name` and `ordinal`, exactly.
  - `List.of` and `List.copyOf` return a small immutable list. It throws `NullPointerException` on a `null` element and
    `UnsupportedOperationException` on any change. `copyOf` hands back the same instance for a list that is already
    immutable, since identity is observable.
  - Add conformance cases for each behaviour, checked against a real JVM.
  - Every property proof over a Quorum kernel benefits, since they all return `Decision`, which calls these.
  - Whether the own checker uses these models in its fragment is part of the scope chosen from 4b. It refuses arrays
    of references, which `List.of`'s varargs creates.
- **The check is a queued job:** examples 071 and 013 rerun under strict.
  - 071's first two property proofs, no verdict under strict today, come back proved with no gap.
  - 071's third property and 013 still give violations whose witnesses replay.
  - The two examples' `notes` are updated from the job.

### Phase 6: Bitwuzla, as evidence for a change of architecture

Bitwuzla is preferred over Z3 and cvc5 (decided 2026-11-06): it sits on CaDiCaL, which makes it the easier path to a
major change. The change would hand word-level bit-vector and array obligations to the solver, instead of the engine
bit-blasting them.

- **6a. Capture the own checker's incremental queries** as replayable transcripts. Binary search makes 942 solver
  calls and example 141 makes 1,044, so a backend judged on one final CNF can mislead.
- **6b. A narrow solver interface** between the engine and CaDiCaL. It separates scheduling the queries, encoding them
  and solving them, and nothing changes behind it: every test passes and the recorded verdicts stand.
- **6c. The comparison, as a job.**
  - Run the transcripts and full checks on CaDiCaL as today.
  - Run the same checks through Bitwuzla with the engine's bit-blasted clauses (SAT only), to separate the solver from
    the encoding.
  - Then run Bitwuzla on word-level terms for the workloads where the formula's size dominates: binary search, 141,
    142, reverse and prefix sums. Building word-level terms from the engine is prototype work, scoped to those
    workloads.
- **6d. A recommendation, not a migration.** The result is a written case for or against moving the engine to
  word-level solving, with the job's table. A migration would be its own brief.
- A newer CaDiCaL (2.x) or Z3 5.3.1 and cvc5 1.4.2 (installed) are tried only where a quick estimate shows more than
  an incremental gain (decided 2026-11-06). Now is not the time for small percentages.

## Done when

| Phase | Criterion |
|---|---|
| 1 | JBMC's phases are exclusive and add up to the elapsed time within the stated tolerance on the fixtures, and every result names its SAT backend and configuration |
| 2 | One job measures the three staging policies over the corpus with corrected phases, and JBMC's default follows its evidence |
| 3 | The cause of the two witnesses that don't reproduce is known, and fixed or drafted as a report |
| 4 | A measured per-obligation gap table and a native/JBMC coverage inventory over the recorded JBMC examples, and class initializers counted by shape |
| 5 | Class initializers run in the own checker to the chosen scope, the three models are in place and checked on the JVM, and 071's two property proofs stand under strict |
| 6 | Transcripts and a solver interface exist, and a job's table compares CaDiCaL with Bitwuzla, bit-blasted and word-level, with a written recommendation |

The pipeline jobs submitted along the way are back with their expected verdicts, or their failures are explained under
Progress.

## Deferred: not in this loop

- **A JBMC fork.** No result makes it the best use of the time. The candidates are kept for reference only:
  - strict Java mode in JBMC itself;
  - model selection separated from string refinement (relevant only if JBMC's string reasoning is wanted back);
  - one shared quotient/remainder encoding;
  - same-width modular multiplication;
  - array representations;
  - persistent prefixes with incremental solving;
  - a compiled-model cache;
  - structural hashing.

  Reconsider only if Phase 2 leaves JBMC's own solving as the cost on a workload that matters, and the own checker
  can't take that workload. These upstream reports could still be drafted for the user, never filed by an agent:
  - `forDigit` ignores its radix;
  - `--incremental-loop` is not wired into JBMC's checker selection;
  - trace output for nondeterministic strings is unbounded.
- **Verifying complex objects.**
  - Contracts under `--gaps advised` for calls with object parameters (`List.of`, `List.copyOf`, `Enum.<init>`) can
    only be *trusted*: the contract language states conditions over primitive parameters alone, and the JVM test can't
    generate objects.
  - Such a contract can also be false in general (`List.of` throws on a `null` element, and a contract can't say so).
    A proof that rests on one would look stronger than it is.
  - So they aren't used (decided 2026-11-06). Phase 5's models cover the known cases. Other ways of verifying calls
    over complex objects, and the objects themselves, are to be revisited in a later loop.
- **Migrating the engine to word-level solving.** Phase 6 only makes the case for or against it.
- **Configurable accepted evidence per project** (proved, tested or trusted for CI), and **a CVE kernel** for the
  benchmark before any public claims. Both were recorded in the sound-verdicts loop.

## Decisions

Settled by the user on 2026-11-06:
1. **Order:** as in [the plan](#the-plan): measurements; staging; the witnesses that don't reproduce; coverage;
   initializers and models; Bitwuzla.
2. **Staging default:** if a policy wins, only JBMC's default changes. The own checker keeps its staging.
3. **Class-initializer scope:** count first, then choose, leaning toward the semantics that occur most where they're
   convenient.
4. **Example 071:** models for `Enum.<init>`, `List.of` and `List.copyOf`, folded into Phase 5. No trusted contracts.
5. **Solvers:** Bitwuzla is preferred, for its path to a change of architecture on CaDiCaL. Other solver experiments
   only where the benefit is more than incremental.

## Progress

- Nothing yet.

## Loop settings

- session: 3761db96-b870-47f7-aded-2ba264c165f4
- model: claude-opus-5-5
- effort: high

## Loop until

Go on while a cycle can still realize a substantial part of the reasonably attainable value of this brief. The user
prefers the loop to run as long as possible, so when in doubt, continue. Phases 1, 2 and 5 are the brief's core: don't
stop before they're done unless they are blocked on the user or on a job. Stop when most of the rest has been
realized: the remaining steps are small or speculative next to what is done, or what is left needs the user's input (a
decision, network access) and has been recorded as deferred. Don't go on to polish, and don't stop while a step that
needs nothing from the user is still open.
