# Working draft: stock JBMC, a better-run adapter, and wider native coverage

**WORKING DRAFT. Not a loop brief yet: don't run it.** It has no Loop settings, and nothing here is approved until the
user settles the [open questions](#open-questions). It replaces the earlier "downstream JBMC patch queue" draft
(2026-11-06): the evidence below moved the work away from a fork. That draft is in the history if needed.

**Input:** [`engine-priorities-review.md`](engine-priorities-review.md), an outside review of the repository at `6cea609e`
that reads the raw benchmark results and the JBMC jobs' outputs. **Read it in full before starting work.** Its figures
were rechecked against `lib/benchmark/results.json` on 2026-11-06 (below). The fork candidates of the older
[`sound-verdicts-review-jbmc.md`](sound-verdicts-review-jbmc.md) are now [deferred](#deferred-a-jbmc-fork).

## Direction

- **Keep JBMC stock** (6.11.0): the fallback under `--engine auto` and the second checker under `--confirm`.
- **Ask it better questions.** Change which queries the adapter sends JBMC, not how JBMC solves them.
- **Measure correctly** before using a phase share to direct work.
- **Widen the own checker's semantics** where the evidence shows a JBMC-only win, starting with application class
  initializers.
- **Run solver experiments under control**: capture the incremental queries first, then compare backends.

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

## The plan

The order below is the review's. The user may change it ([open question 1](#open-questions)).

### Phase 1: measurements to trust

- **1a. Exclusive JBMC phases.**
  - Account for nested timers per solver call: `Post-process` sits inside `Solver`.
  - Handle a call cut off by the deadline or by memory on its own.
  - Check that the exclusive phase totals match the elapsed time, within a stated tolerance. A run that fails the check
    is flagged, never normalized to 100%.
  - Add fixtures captured from real JBMC 6.11.0 output, in `--json-ui --timestamp monotonic`: success, timeout and
    out of memory.
  - Queue a benchmark rerun as a job, and regenerate the "Where the time goes" table from it.
- **1b. Record the solver.** Record which SAT backend each engine used, with its version and configuration, in
  `results.json` and in each result's evidence: CaDiCaL's version for the own checker, and JBMC's solver and options.
- **1c. A reproducible gap inventory.** Queue a strict rerun of the 41 recorded JBMC examples that saves
  `examples/tools/gap_table.py --json`'s output with the job's results. It replaces `-082917`'s projection with a
  measured table, per obligation.

### Phase 2: which stages JBMC is asked to run

Compare three policies on the benchmark corpus and the recorded JBMC examples, as one pipeline job:
1. **Today's staged search.**
2. **Full range first.**
3. **One preliminary stage on a tight budget**, then the full range.

Keep the overall deadline, the bounds, the models and the evidence rules the same across the three.

Measure proofs and counterexamples separately, and how small each witness is. The stages exist to give small
witnesses. With full range first, a counterexample is shrunk afterwards by `lib/src/shrink.rs`, which already shrinks
any engine's witness through the interpreter. A shrunk witness is a local minimum, so compare its size with the staged
one's.

`--confirm` already runs the full range, so the change applies to ordinary JBMC checks and to the `auto` fallback. The
default changes only on the job's evidence, and **only JBMC's** (decided 2026-11-06). The own checker keeps searching
its stages per violating path. Those stages are cheap, and they keep its witnesses small.

### Phase 3: application class initializers, enums and immutable lists

- **Count first.** Find how often `class-initializer` gaps occur, and of what shape, in the recorded examples and in
  the apps (Mica, Crosscut, Quorum, Box Office), from `--gaps` scans run inline where they are cheap. The recorded
  results predate gap records, so today's count of zero means nothing. Choose the scope from the count, **leaning toward
  the semantics that occur most, where they're convenient** (decided 2026-11-06). The two choices are full JVMS §5.5
  semantics, or initializers that only assign constants first.
- **Then implement.** Run a class's `<clinit>` at its first `new`, `getstatic`, `putstatic` or `invokestatic` (JVMS
  §5.5), after its superclasses' and the relevant superinterfaces', which `gaps.rs` already lists. Model an
  `ExceptionInInitializerError` and the later `NoClassDefFoundError`.
- **Check** against the JVM in the conformance corpus. `boom`, `inherited` and `quiet` become correct on the own
  checker.
- **Model `Enum.<init>`, `List.of` and `List.copyOf` in `lib/models`** (decided 2026-11-06). They become bytecode on
  JBMC's class path and in the interpreter, so they stop being gaps rather than being covered by contracts. Follow the
  rules for adding a model in `lib/models/README.md`.
  - `Enum.<init>(String, int)` sets `name` and `ordinal`, exactly.
  - `List.of` and `List.copyOf` return a small immutable list. It throws `NullPointerException` on a `null` element and
    `UnsupportedOperationException` on any change. `copyOf` hands back the same instance for a list that is already
    immutable, since identity is observable.
  - Add conformance cases for each behaviour, checked against a real JVM.
  - **The check:** examples 071 and 013 rerun under strict. 071's first two property proofs, which strict turns into
    no verdict today, come back as proved with no gap. 013's violation still replays.
  - Every property proof over a Quorum kernel benefits, since they all return `Decision`, which calls these.
  - The own checker needs `Enum.<init>` for enum initializers anyway. Whether it uses these models in its own fragment
    (it refuses arrays of references, which `List.of`'s varargs creates) is part of the scope chosen after the count.
- **Then a coverage inventory.** Match own checker against JBMC over every recorded example to pick the next semantic
  extension, floating point (035) being the known candidate. The inventory comes before choosing.

### Phase 4: the witnesses that don't reproduce

Find the root cause for `caught/1` and `nestedHandler/1`: models, exception handling, translation of the harness, or
reading the trace. Keep the replay boundary as it is. Fix the cause if it's in this repository. If it's in JBMC, draft a
report for the user, never filed by an agent.

### Phase 5: solver infrastructure, then experiments

- **Capture the own checker's incremental queries** as replayable transcripts. Binary search takes 942 solver calls and
  example 141 takes 1,044, so a backend judged on one final CNF can mislead.
- **Put a narrow SAT interface** between the engine and CaDiCaL. It separates scheduling the queries, encoding them and
  solving them.
- **Then experiment, on architecture rather than percentages** (decided 2026-11-06). **Bitwuzla is the preferred
  backend.** It sits on CaDiCaL, which gives an easier path to try a major change: word-level bit-vector and array
  obligations handed to the solver instead of being bit-blasted by the engine. Fetching and building it on ARM64 is a
  pipeline job with network access.
  - A newer CaDiCaL (2.x against the bundled 1.9.5) and Z3 5.3.1 or cvc5 1.4.2 (installed) on exported transcripts are
    in scope only where a quick estimate shows more than an incremental gain. A small percentage is deferred.
  - Record both the fixed transcripts and the full checks.

## Deferred: a JBMC fork

No result makes a fork the best use of the time. These candidates are kept for reference only:
- strict Java mode in JBMC itself;
- model selection separated from string refinement (relevant only if JBMC's string reasoning is wanted back);
- one shared quotient/remainder encoding;
- same-width modular multiplication;
- array representations;
- persistent prefixes with incremental solving;
- a compiled-model cache;
- structural hashing.

Reconsider only if Phase 2 leaves JBMC's own solving as the cost on a workload that matters, and the own checker can't
take that workload.

## Deferred: verifying complex objects

Contracts under `--gaps advised` for calls with object parameters (`List.of`, `List.copyOf`, `Enum.<init>`) can only be
*trusted*: the contract language states conditions over primitive parameters alone, and the JVM test can't generate
objects. Such a contract can also be false in general (`List.of` throws on a `null` element, and a contract can't say
so). A proof that rests on one would look stronger than it is, so it isn't done here (decided 2026-11-06). Phase 3's
models cover the known cases. Other ways of verifying calls over complex objects, and the entities themselves, are to
be revisited in a later loop.

These upstream reports could still be drafted for the user, never filed by an agent:
- `forDigit` ignores its radix;
- `--incremental-loop` is not wired into JBMC's checker selection;
- trace output for nondeterministic strings is unbounded.

## Open questions

1. **Order.** Still open: it's reviewed last, before the brief is written.

Settled by the user on 2026-11-06:
2. **Staging default:** if full range first wins, only JBMC's default changes. The own checker keeps its staging.
3. **Class-initializer scope:** count first, then choose, leaning toward the semantics that occur most where they're
   convenient.
4. **Solver experiments:** Bitwuzla is preferred, for its path to a change of architecture on CaDiCaL. Other solver
   experiments only where the benefit is more than incremental: now is not the time for small percentages.
5. **The brief:** written once the order is agreed.

## Notes

- Nothing yet.
