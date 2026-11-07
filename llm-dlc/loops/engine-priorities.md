# Brief: stock JBMC asked better questions, honest measurements, and wider native coverage

**Approved by the user on 2026-11-06**, with the decisions recorded [below](#decisions). It replaces the "downstream JBMC patch queue" draft, since the evidence below moved the work away from a fork.
That draft is in the history if needed.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). Its plan is worked in [two streams run in
parallel](#streams), each a loop of its own with a short brief that names its phases. This brief is the instruction for
both. Its own loop, `llm-dlc/tools/feature-loop.sh engines` in the default workspace, reconciles them once both have
stopped, and then does what is left. It runs in a fresh session of its own, set under [Loop settings](#loop-settings),
with no memory of the planning or of the streams: [Streams](#streams) says where all of it is. It runs until the
session judges, by [Loop until](#loop-until), that the rest is not worth another cycle.

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

## Streams

The plan's phases are split by the line between the two engines, so the streams touch different code:

| Loop | Brief | jj workspace | Phases |
|---|---|---|---|
| `engines-jbmc` | [`engine-priorities-jbmc.md`](engine-priorities-jbmc.md) | `jbmc` | 1a, 1b, 2, 3, 4a: the JBMC adapter and the measurements |
| `engines-native` | [`engine-priorities-native.md`](engine-priorities-native.md) | `native` | 1c, 4b, 5, 6: the own checker, its models and the solver |
| `engines` | this brief | `default` | the merge, then 4c, the examples' notes from jobs, the docs, and what the streams left |

Each stream commits on its own branch, the `@-` line of its workspace, and nothing is merged until both have stopped.
The verification runner, in the default workspace, also runs the jobs committed in the streams' workspaces, at their
own commits, and collects their results there. The stream briefs say which files each owns and how the shared ones are
changed. The phase order above still holds within each stream.

**Running it all** (the user, from the default workspace, in tmux): `llm-dlc/tools/run-streams.sh engines`. It runs
the streams, then this brief's own loop, unattended, and the user is needed only once that loop is finished.
- The first time, it compacts the planning session (`3761db96`, the conversation that planned the streams; the
  stream briefs' `- fork:`), and adds the
  workspaces next to the repo, `../REPO-jbmc` and `../REPO-native` (on cvm, `~/code/in-the-loop-jbmc` and `-native`), from
  the latest commit.
- Each stream's session starts as a fork of that compacted conversation (`- fork:` in its Loop settings), so both
  begin with the same context.
- It starts `verification-loop.sh` (unless one already runs), which runs, collects and commits the loops' jobs.
- Every brief, this one included, ends its Progress with `- Status: working`, `waiting on jobs ID ...`, `done` or
  `blocked: ...`. When a loop stops, the script reads it. Waiting on jobs, it waits until their results are collected
  here and runs the loop again. Done or blocked, the loop is finished. A loop that stops twice in a row without a
  status that says why counts as blocked.
- Once both streams are finished, it runs this brief's own loop here, `feature-loop.sh engines`, in a fresh session,
  then stops the verification loop.
- Everything prints to the one terminal, each line prefixed with its loop, and Ctrl-C stops all of it. Running the
  script again continues where it stopped; a loop whose status is done or blocked isn't run again.

The runner's budget is the machine's memory less the loops' caps (3.5 GB each).

**How the streams ran, and where their work is.** The reconcile session starts fresh: it didn't see the planning
conversation or the streams, and nothing of theirs is in its context. It all is in files:

| What | Where |
|---|---|
| The planning | Session `3761db96-b870-47f7-aded-2ba264c165f4`. It planned this brief, the split and the tools, and was compacted once before the streams forked from it. Its published summary is `llm-dlc/traces/3761db96-b870-47f7-aded-2ba264c165f4/summary.md`. |
| How they ran | `llm-dlc/tools/run-streams.sh engines`, from this (default) workspace on cvm (the ssh host `cvm`, repo at `~/code/in-the-loop`). Each stream was `feature-loop.sh engines-STREAM` in its own workspace, `jj workspace root --name STREAM` (`../in-the-loop-jbmc`, `-native` on cvm), in the systemd scope `feature-loop-engine-priorities-STREAM.scope`, with the session in its brief's Loop settings, forked from the planning session. Each committed on its own branch, the `@-` line of its workspace, and never pushed or merged. |
| Their commits | `jj log -r '::jbmc@- ~ ::default@-'`, and the same for `native`. The later paragraphs of each message say what changed and how it was verified. |
| Their Progress | Each stream brief as its branch left it: `jj file show -r jbmc@- llm-dlc/loops/engine-priorities-jbmc.md` (the copy in this workspace is from before the streams started). It names the shared files each changed and what it deferred. |
| Their run records | `$(jj workspace root --name STREAM)/llm-dlc/loop-summaries/*-engine-priorities-STREAM.md`, one per run: each commit as it landed, how the run ended (no commit, interrupted, or decided to stop), and the session's own summary with jobs pending, warnings and deferred items. Gitignored and only there, so read them before step 7. |
| Their conversations | After step 2, `llm-dlc/traces/SESSION/summary.md` on each branch, the published summary. The raw transcripts, under `~/.claude/projects/` in the directory named after the workspace's path, are not to be printed (CLAUDE.md): use the summaries. |
| Their logs | `llm-dlc/traces/SESSION/logs/` in each workspace (step 3). |
| Their jobs | Committed on their branches under `verification/jobs/`, run by the runner here and collected here under `verification/results/`. `python3 verification/pipeline.py status` lists them with every workspace's, and `report` reads the results. |

**Reconciling** is this loop's first piece of work. `run-streams.sh` starts this loop once both streams are finished:
each one's status says `done`, or `blocked` on something for the user. A blocked stream is merged with what it
committed, and what it needs goes on the list for the user. Started by hand while a stream still runs, a cycle of this
loop does nothing and makes no commit, which stops the loop. In order:

1. **Check the streams have stopped.** `systemctl --user is-active feature-loop-engine-priorities-jbmc.scope` and
   `feature-loop-engine-priorities-native.scope` must both say inactive.
2. **Record their last turns.** In each stream's workspace (`jj workspace root --name jbmc`, then `native`), run
   `jj st` from that directory first. If it shows changes outside `llm-dlc/traces/`, `llm-dlc/index.json` and
   `llm-dlc/README.md`, a cycle was interrupted there: don't commit them yourself. Say so, and leave the stream to be
   continued (`run-streams.sh engines STREAM`) or to the user. Otherwise run
   `python3 llm-dlc/tools/sync.py commit -m "Record session traces" -m "..."` from that directory. This puts the
   conversation after the stream's last commit on its branch.
3. **Copy their logs here.** Logs are not in git. Copy each file under the stream workspace's
   `llm-dlc/traces/*/logs/` that isn't here yet into the same path in this workspace (`cp -n`). A push uploads them
   from here.
4. **Merge.** `jj new @- jbmc@- native@-`. Do this only while this working copy holds no other session's files; if it
   does, wait for that session to commit them (the runner commits each collection) rather than moving them.
   - The trace files that every commit regenerates may conflict: `llm-dlc/index.json`, `llm-dlc/traces/README.md`,
     `llm-dlc/traces/metrics.json`, and the session table in `llm-dlc/README.md`. Take either side: the commit rewrites
     them from the manifests, which don't conflict.
   - Resolve code and docs using the streams' Progress notes on the shared files.
   - Where a result the runner collected for a stream's job conflicts with that stream's own edits, the stream's code
     wins and the result stands as recorded.
   - After the merge, the Rust suite and the Python suites must pass, as on each branch.
5. **Commit the merge** with `sync.py commit`. Its check must report 0 errors.
6. **Fold the streams' Progress into this brief's,** a line per phase with its commits and job ids. Read each
   stream's run records in its workspace's `llm-dlc/loop-summaries/` for what they deferred.
7. **Forget the workspaces:** `jj workspace forget jbmc native`. Their directories stay for the user to delete; each
   holds a build of about 3 GB.

After the merge, this loop takes 4c, updates 071's and 013's `notes` from the Phase 5 job, regenerates what the merged
jobs feed (`lib/benchmark/RESULTS.md`), and fits Bitwuzla's version into 1b's record. Then it finishes whatever the
streams left that needs no input from the user, and lists for the user the decisions that do.

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

The streams `engines-jbmc` and `engines-native` worked the plan in parallel ([Streams](#streams)) and both stopped
with `done` on 2026-11-07. Each phase's detail, with the shared files each stream changed, is in its stream brief as
its branch left it (`jj file show -r lukovtll llm-dlc/loops/engine-priorities-jbmc.md`, and `ulsslrtx` for
`-native`), and in the commits named below (change ids).

- **1a, exclusive JBMC phases: done** (`snprkxtx`, `tvquoumw`). `phases.rs` counts `Runtime Post-process` once, inside
  `Runtime Solver`; a run whose phases pass its seconds by more than 1% plus 5 ms is flagged `phases_excess`, never
  scaled. Fixtures from real JBMC 6.11.0 (proved, cut off, out of memory, two calls). The nesting was checked against
  CBMC's source at `cbmc-6.11.0` by job `20261106-194328` (passed; its first run `-192959` failed on its own grep).
- **1b, the SAT solver recorded: done** (`olttywtt`). `stated.checker.sat` in every result: CaDiCaL 1.9.5 for the own
  checker, JBMC's `--sat-solver cadical` (3.0.0, read from its executable) with its standing options. `results.json`
  lists them in `environment.sat`.
- **1c, the Bitwuzla build: done** (`nzxrwvum`, `mwxvlkzz`). Job `20261106-194049` passed (its first run `-192008`
  failed on a shared CaDiCaL subproject): Bitwuzla 0.8.2, commit `61bdc637`, linking CaDiCaL 2.1.2 static, recorded in
  `lib/solvers/bitwuzla/build.json`. Built on x86_64, not the ARM64 the plan names.
- **2a, the staging policy: done** (`uykqwxvr`). `--jbmc-staging staged|full-range|tight`.
- **2b, the benchmark job: done** (`xtkwolst`). Job `20261106-201041` passed; its `results.json` and `RESULTS.md` are
  collected, "Where the time goes" over corrected phases.
- **2c, JBMC's default: `full-range`** (`wvkxpmzx`), from job `-201041`. Under strict JBMC's proofs were the same 54 of
  65 under each policy, 575 s against `staged`'s 654 s; binary search 26 s against 56 s, 141 31 s against 61 s;
  counterexamples 9 s against 27 s; no shrunk witness larger. The one case that changed class is a JBMC defect (3).
- **3, the witnesses that don't reproduce: done** (`svvrpymr`, `pxqzmomt`, `xzvyuwxp`). Two JBMC 6.11.0 defects, and
  a third found by 2b: `return-past-handler` (an exception computed into a `return` escapes its handler),
  `stubbed-handler` (JBMC's JDK stubs have no superclass, so `catch (RuntimeException e)` misses), and
  `unmasked-shift` (`>>`, `>>>` don't mask the distance). Each gave a **false proof under strict** on `--engine jbmc`.
  The preflight (`jbmc_gaps.rs`, `Defect`) now refuses a JBMC proof through one under every mode, and `--confirm` takes
  a refutation through one whose witness doesn't reproduce for no verdict. Jobs `20261106-203452` (failed, triaged)
  and `-231317` (passed). Two upstream reports are drafted in `lib/tests/fixtures/jbmc-defects/README.md`, not filed.
- **4a, the strict job on both engines: done** (`xrrrwlrm`, `tokyzsls`, `xyplqrtn`, `pmoympwn`). Job `20261107-000039`
  passed (`-204220`, `-231837` failed on the result schema, fixed). Of 43 obligations: both engines decide 35 and
  agree on all; only JBMC decides 5 (`013#0`, `035#0`, `052#0`, `071#2`, `127#0`); neither decides 3 (`037#0`,
  `071#0`, `#1`). `037#0`'s recorded proof is refused by the unmasked-shift guard though correct (checked on all 2^32
  ints). The tables are in that job's outputs, `lib/target/jobs/4a-coverage/`.
- **4b, initializers counted: done** (`wnxlynrs`). Apps: 49 initializers, 36 enums and 13 `$SwitchMap`s, none
  `throws`, `constants` or `other`. Recorded examples: only 013 and 071, through four Quorum enums. Benchmark: `Boom`,
  `Base` throw, `Quiet` is constants. Scope chosen: full JVMS §5.5.
- **5: mostly done** (`kumppqkz`, `knlrwnqu`, `ulstzomt`).
  - Class initializers run in the own checker as JVMS §5.5 orders them; `boom`, `inherited`, `quiet` are correct on
    it, with 8 more cases. Enums run too (arrays of references, `Enum`'s model, switch maps): over the apps the 49
    `class-initializer` gaps are 0.
  - `Enum.<init>`, `List.of`, `List.copyOf` are models on JBMC's class path, checked on the JVM by 11 cases and by
    running them relocated against the JDK's classes.
  - **Open: 071's two proofs don't stand under strict.** Job `20261106-203501` (failed): the models are used, but
    JBMC's preflight walks the call graph, not paths, and reaches `Collection.isEmpty` and `toArray` stubs in
    `ImmutableCollections.listCopy` that no path takes. The fix is a path-aware check in `jbmc_gaps.rs`.
  - **Found by that job: a false success of JBMC under strict,** `declaring`: JBMC runs `Sub.<clinit>` on a
    `getstatic Sub.value` declared in `Holder`, where the JVM initializes `Holder` alone. `auto` decides it right.
  - That job also recorded the contract library on JDK 25.0.5 (its step passed). Its `checked.json` is applied by
    hand, since a failed job's outputs aren't: the file was still the job's source (`368d584b…`), the contracts
    unchanged since its commit `7457928f`, and it adds the 10 records of 25.0.5 to those of 25.0.4.1. The 12
    conformance claims that failed on the library's records now pass (the whole conformance test, on JDK 25.0.5).
    The library's integration test named 25.0.4.1 as the one JDK with records; it now reads them from `checked.json`.
    In the full suite `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` failed once on `Pricing#total`'s
    refutation and passed alone: the wall-clock branch probes of item 8.
- **6a–6d: done** (`wnktqxrt`, `syntvmqp`, `osspkxkz`, `wqskvlym`, `ulsqmxuq`, `tpytwvmv`). Transcripts
  (`JVMCONTRACT_TRANSCRIPTS`, `jvmcontract transcript`), the `Sat` trait, Bitwuzla behind it on clauses and on
  word-level terms. Jobs `20261106-224616` and `-230455` passed: on clauses Bitwuzla is 2–43× slower; on terms with
  `preprocess=0` at most 1.93× faster, and no case moves to decided. `lib/solvers/README.md` recommends against a
  migration now.
- **Reconcile, steps 1–5: merged** (`pkyqqotr`). The stream traces recorded on their branches, logs copied, the three
  lines merged. `lib/README.md`'s conflict keeps both streams' paragraphs. Fixed at the merge: a conformance test
  that pinned a corpus line, and `lib/benchmark/conformance.json` regenerated (146 claims). Rust unit 174,
  integration 64, skill pass; conformance fails only the 12 known library-record claims. `test_build.py` (35
  `KeyError: 'verdict'`, on both branches before) and `test_performance.py` (one failure, in files the merge doesn't
  touch) fail as before the merge.
- **Reconcile, steps 6–7: done.** This fold, and `jj workspace forget jbmc native`. The directories
  `../in-the-loop-jbmc` (0.5 GB) and `../in-the-loop-native` (2.2 GB) stay for the user to delete, with the streams'
  run records in their `llm-dlc/loop-summaries/`.
- **Next, in order:**
  1. ~~take `checked.json` from job `-203501`~~ (done);
  2. the `declaring` gap in `jbmc_gaps.rs`, with a conformance claim, and a report drafted for the user;
  3. a path-aware stub check in `jbmc_gaps.rs` so 071's two proofs can stand, then a job rerunning 071 and 013;
  4. 4c, the coverage inventory from 4a's tables and 4b;
  5. the examples' notes: 071 and 013 from `-203501` (and the rerun), 037 from `-000039`;
  6. Bitwuzla's version in 1b's record (`statement::native_sat()` from the configured solver);
  7. `test_build.py`'s and `test_performance.py`'s failures;
  8. smaller ones the streams noted: the own checker's branch probes depend on wall-clock time (`Pricing#total` timing
     out in 2 of 8 runs), the sampled encoding flagging short runs `phasesExcess`, the conformance job for the native
     stream's step 3 cases under JBMC, `auto` and `--confirm`.
- **For the user:** the 7 allow-list proposals (mangled C++ symbols in session `7b8a1d3b`'s logs); the two drafted
  upstream reports, and a third once `declaring`'s is drafted; a push. CaDiCaL 2.x on its own, to separate it from
  Bitwuzla's word-level gain, is below the brief's bar and not queued.
- Status: working

## Loop settings

- session: c2bd9df4-5f20-4312-95a4-3eb88a60e0cd
- model: claude-opus-5-5
- effort: high

## Loop until

The reconcile comes first; don't stop before the merge is committed unless a stream is still running or the merge
needs the user. Keep the last line of Progress a status, as the stream briefs describe: `working`,
`waiting on jobs ID ...` (stop then: `run-streams.sh` runs this loop again once they are back), `done` when the brief
is finished, or `blocked: ...` with what needs the user. Your last cycle's commit sets `done` or `blocked`, and the
Progress above it is what the user reads first. After it, go on while a cycle can still realize a substantial part of the reasonably attainable value
of this brief. The user
prefers the loop to run as long as possible, so when in doubt, continue. Phases 1, 2 and 5 are the brief's core: don't
stop before they're done unless they are blocked on the user or on a job. Stop when most of the rest has been
realized: the remaining steps are small or speculative next to what is done, or what is left needs the user's input (a
decision, network access) and has been recorded as deferred. Don't go on to polish, and don't stop while a step that
needs nothing from the user is still open.
