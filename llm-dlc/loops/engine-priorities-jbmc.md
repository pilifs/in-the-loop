# Stream brief: engine priorities, the JBMC side and the measurements

One of two streams of [`engine-priorities.md`](engine-priorities.md) that run in parallel, each in its own jj
workspace on its own branch. The other is [`engine-priorities-native.md`](engine-priorities-native.md). Once both have
stopped, a reconcile loop merges them; [Streams](engine-priorities.md#streams) in the main brief says how.

Started with the other stream by `llm-dlc/tools/run-streams.sh engines` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh engines-jbmc` from this stream's workspace (`jj workspace root --name jbmc`):
the loop refuses any other.

**The main brief is the instruction.** Read [`engine-priorities.md`](engine-priorities.md) in full every cycle, and its
input [`engine-priorities-review.md`](engine-priorities-review.md) too. Its direction, evidence, working rules,
deferrals and decisions all apply here. This file only says which part of its plan is yours, and keeps your Progress.
Don't edit the main brief, the other stream's brief, or anything outside this file's `## Progress` section.

## Your phases

In the main brief's order:

1. **1a** exclusive JBMC phases, with fixtures from real JBMC 6.11.0 output;
2. **1b** the SAT backend recorded for both engines. You define the shape in `results.json`'s environment and in each
   result's evidence. Record the own checker's CaDiCaL (version from the `cadical` crate) as it stands; the native
   stream adds Bitwuzla later in the same shape;
3. **2a–2c** the staging-policy option, the benchmark job, and JBMC's default decided from it;
4. **3** the two witnesses that don't reproduce;
5. **4a** the strict job on both engines over the 41 JBMC examples, with `gap_table.py --json`.

Not yours: 1c, 4b, 4c, 5 and 6. 4c needs both 4a and the native stream's 4b, so the reconcile loop does it.

## Boundaries

You own the JBMC adapter and the measurements: `lib/src/jbmc.rs`, `jbmc_gaps.rs`, `jbmc_contracts.rs`,
`phases.rs`, `deadline.rs`, `lib/benchmark/`, `examples/tools/gap_table.py`, and their tests and fixtures.

The native stream owns `lib/src/bmc/`, `lib/models/` and the solver interface. Don't change them. If your work needs
a change there, record it under Progress for the reconcile loop and work around it.

Some files both streams may touch: `lib/src/main.rs` and `lib.rs` (CLI options, module list), `lib/tests/conformance.rs`
and `lib/tests/conformance/`, `lib/src/interp/`, `witness.rs`, `shrink.rs`, `Cargo.toml`. In those, add rather than
rewrite: new options, new cases and new functions, not reorganizations. Name every change to one of them under
Progress, so the reconcile loop knows where to look.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Jobs.** Submit and commit jobs as usual. The runner works in the default workspace and also runs jobs committed
  here, at this commit (see `verification/README.md`). Results are collected there, not here: read them with
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" report` and `status`, and the files under
  that workspace's `verification/results/`. Record what you take from a result under Progress with the job id. Its
  outputs reach this branch only at the merge, so don't copy them in by hand.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by
  `run-streams.sh`, which runs this loop unattended: `- Status: working` while there is work you can do,
  `- Status: waiting on jobs ID ...` when everything left waits on those jobs (it runs the loop again once their results
  are collected), `- Status: done` when your phases are finished, or `- Status: blocked: ...` with what needs the user.
- **Another session is not your concern** beyond the loop's usual rule: the native stream works in its own directory
  and never touches this working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `3761db96`,
  compacted), so you share its context with the other stream. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- **1a, exclusive JBMC phases: done.**
  - `lib/src/phases.rs` reads JBMC's timers per solver call. `Runtime Solver` covers the whole call, so the
    `Runtime Post-process` inside it counts under `encoding` only. A call that printed neither that line nor CaDiCaL's
    `N variables, M clauses` never reached the SAT solver, so all of it is `encoding`.
  - `Phases::excess` flags a run whose named phases add up past its seconds by more than 1% plus 5 ms. The JSON
    carries the excess as `phases_excess` on `deadline::Run`; nothing is scaled. `lib/benchmark/run.py` records it per
    case as `phasesExcess` and leaves such runs out of the phase tables, naming them below.
  - Fixtures are real JBMC 6.11.0 runs on cvm (x86_64), in `lib/tests/fixtures/jbmc-phases/`: `held/prefix-sums`
    proved (Post-process 0.175 s inside Solver 2.955 s), the same cut off at 1.9 s, `held/reverse` out of memory at
    700 MiB, and two solver calls in one run.
  - The nesting shows in the message times. Job `20261106-192959` (network) was to check it against CBMC's source at
    `cbmc-6.11.0`. It failed on its own display grep, which matched nothing under `pipefail` before any check ran
    (finding VF-004). The runner resubmitted it from the default workspace as `20261106-194328`, which **passed**.
    In CBMC 6.11.0, `run_property_decider` (`bmc_util.cpp:393–400`) times `property_decider.solve()` as
    `Runtime Solver`. Inside that call, `prop_conv_solvert::dec_solve` runs `finish_eager_conversion()` and prints
    `Runtime Post-process` (`prop_conv_solver.cpp:449–461`), guarded by `post_processing_done`, so only a run's
    first call prints it. That is the nesting `phases.rs` assumes. The constraint from the goals is added before
    the Solver timer starts, so it lands in `Runtime decision procedure`, which `phases.rs` doesn't read.
  - Shared files changed (added to, nothing reorganized):
    - `lib/README.md`: one clause on `phases_excess` in `--json`'s description;
    - `lib/src/jbmc.rs`: `json_items` is `pub(crate)`, for the tests.
  - **For the reconcile loop:** on cvm, `conformance.rs`'s
    `the_corpus_agrees_with_the_jvm_on_the_tools_own_checker` fails with 12 disagreements. Not rerun at the base; the
    messages point away from this change.
    - The cause: the JDK is 25.0.5, but the contract library's records (`lib/models/contracts/`, the native stream's)
      were written for 25.0.4.1, so advised runs print "is not the library's, on its record".
    - It may also touch 2b's advised runs.
- **1b, the SAT solver recorded: done.**
  - Each result's evidence names its SAT solver: `stated.checker.sat`, with `solver`, `version`, `source` and
    `configuration` (`Sat` in `lib/src/statement.rs`).
  - The own checker's is CaDiCaL 1.9.5, from the signature of the `cadical` crate it is bundled by (0.1.16, read
    from `Cargo.lock`). It runs with CaDiCaL's default options, incrementally (one solver per run, queries under
    assumptions), with the deadline through its terminate callback.
  - JBMC's is the solver asked for (`--sat-solver cadical`), with the configuration of the options every run passes
    (`jbmc::standing_options`, which the command line uses too). The version is read from the CaDiCaL signature in the
    executable, without running it: `cadical-3.0.0` in JBMC 6.11.0's.
    - An executable without CaDiCaL is recorded with JBMC's default, which the adapter's "unknown solver" retry falls
      back to.
    - A script standing in for JBMC gets no version.
  - `lib/benchmark/run.py` keeps each run's `sat` and lists each engine's solvers once in `environment.sat`.
    `RESULTS.md` names them under its first line; job `-102624`'s page renders as before.
  - **For the native stream and the reconcile loop:** Bitwuzla fits the same `Sat`. `statement::native_sat()` builds the
    own checker's record next to `bmc::solver_signature()` (unchanged); once the solver interface (6b) exists, it should
    supply the solver's name, version and configuration.
  - Changed outside this stream's files, added to:
    - `lib/src/statement.rs`: `Sat`, `native_sat`, and `Checker.sat`. `checker()` takes a closure for JBMC's record,
      called only when JBMC gave the verdict;
    - `lib/src/equivalence.rs` and `property.rs`: the one call of `checker()` each;
    - `lib/README.md`: `sat` in `--json`'s description.
  - **For the reconcile loop:**
    - `examples/tools/test_build.py` has 35 errors on this branch, `KeyError: 'verdict'` in `build.py` reading
      committed example results. None of its inputs changed here.
    - The commit check's 4 errors, after 1a, were in other workspaces' commits: the default workspace's verification
      results and the native stream's Bitwuzla job, both sessions without a manifest here. They should clear at the
      merge.
- **2a, the staging policy: done.**
  - `--jbmc-staging` on `equivalence` and `prove` picks which of JBMC's interval stages run (`deadline::Staging`):
    - `staged`: today's search, and still the default;
    - `full-range`: the full range alone, its counterexample shrunk in the interpreter;
    - `tight`: the first stage that leaves out an input, on at most `TIGHT_SHARE` (a fortieth of the check, 3 s of
      120 s, where a staged stage may take 15 s), then the full range.
  - Under every policy, the deadline, bounds, models, preflights, gap rules and stop rule are the same: only the full
    range proves, a preliminary stage out of its budget hands on, and a violation stops the search. A stage that
    bounds nothing is still dropped. The own checker's stages and `--confirm`'s single run don't follow the policy.
  - A result records the policy as `search.staging` when JBMC gave the verdict.
  - Tests:
    - unit tests in `deadline.rs` for each policy's stages and budgets;
    - `jbmcs_staging_policy_picks_the_stages_it_runs_and_their_budgets` in `conformance.rs`, against a stand-in
      JBMC that answers stage by stage. It covers the stages each policy runs on both kinds of check, their
      budgets, a slow `[0:20]` handing on, and a violation found in the wide stage and in the full range, both
      shrunk to the same 99. It fails if `equivalence` ignores the option (checked by mutation).
  - **For 2c** (structure, not yet a measurement): under `--engine auto`, the fallback starts with a quarter of the
    check left. Under `staged`, two preliminary stages that time out take an eighth each, so the full range gets
    nothing. The 2b job should show whether this happens in the corpus.
  - Shared files changed, added to:
    - `lib/src/main.rs`: the `--jbmc-staging` option on both commands;
    - `lib/src/equivalence.rs` and `property.rs`: `Options.jbmc_staging`, the policy's stages and budgets in the
      staged loop, and `Search.staging`;
    - `lib/src/statement.rs`: `staging: None` in a test's `Search`;
    - `lib/tests/conformance.rs`: the helper `staged_jbmc` and the test above;
    - `lib/README.md`: the option and `search.staging`.
- **2b, the benchmark job: submitted, `20261106-201041` (pending).**
  - `lib/benchmark/run.py --jbmc-staging staged,full-range,tight` makes every run of `jbmc` once per policy, and of
    `auto` once under the first, then again under the others only where its own checker gave no verdict and JBMC's
    fallback ran. That gives 2c the `auto` fallback's evidence too, and the 2a note's question (a `staged`
    fallback whose full range got under a second) is counted as *starved*.
  - Each run records its `staging`, `auto`'s `fallback`, and its witness's size as reported (`witnessSize`, after
    `shrink.rs`) and as found (`foundSize`, `shrinkRuns`): array elements and largest magnitude.
  - The corpus's tables, "Where the time goes" among them, are over the first policy. A new section, "JBMC's staging
    policies", compares the others with it per engine and mode, proofs and counterexamples apart: correct, no
    verdict, wrong, seconds, class changes, larger witnesses, shrunk, starved. Under strict, case-by-case tables give
    each policy's verdict, time and witness.
  - The results name the job and its commit (`VERIFY_JOB_ID`, `VERIFY_SOURCE_COMMIT`), and so does the page's first
    line, as the brief asks of new figures.
  - Verified: `test_run.py` passes (26 tests, 5 new: the option passed through, witness sizes, `auto`'s skip rule
    through `run()`, the tables over the first policy and the comparison, the empty section). Job `-102624`'s
    `results.json` renders to the committed `RESULTS.md` byte for byte. A smoke run of group 2 under strict, own
    checker and `auto`, with a stub for JBMC, ran each `auto` case once (none fell back).
  - The job runs `native,jbmc,auto` under all three modes, about 2.5 h estimated. Advised runs may stop on the
    JDK 25.0.5 against the contract records' 25.0.4.1 (1a's note).
  - No shared file changed.
- **3, the witnesses that don't reproduce: cause found, guarded, report drafted; job `20261106-203452` (pending).**
  - **The cause:** not the models, the trace reading, or the harness. JBMC 6.11.0 lets a runtime exception past the
    handler that catches it on the JVM, so the exception escapes the method. There are two shapes, found by running
    JBMC (in milliseconds) on the cases and on variants of them (`lib/tests/fixtures/jbmc-defects/README.md`):
    - **`return-past-handler`, a JBMC defect.** In `try { return 10 / n; } catch (ArithmeticException e)`, javac ends
      the handler's range before `ireturn`. JBMC keeps `10 / n` on its operand stack and emits it at the `ireturn`,
      with the check `--throw-runtime-exceptions` adds, after the `pop_catch` it placed at the range's end
      (`--show-symbol-table`). The same happens for `irem`, `ldiv`, `lrem`, an array element, a field and
      `arraylength`. A value stored first, passed to a call, compared, or under `finally` is caught.
      `caught/1` is this shape.
    - **`stubbed-handler`, this repository's class path.** JBMC's stub of a JDK class has no superclass, so
      `catch (RuntimeException e)` misses an `ArithmeticException` or an `IllegalArgumentException`. With the real
      classes on the class path it catches them, but the real `Throwable` brings a native `fillInStackTrace`.
      `nestedHandler/1` has both shapes.
  - **Worse than an unverifiable witness:** both shapes gave false proofs under strict with `--engine jbmc`.
    `prove caught --assert 'result == 10 / n' --throws 'java.lang.ArithmeticException when n == 0'` was ✓, but
    `caught(0)` returns -1 on the JVM. The same claim was proved on a `catch (RuntimeException e)` too. The own checker
    gives a violation on both.
  - **The guard:** JBMC's preflight (`lib/src/jbmc_gaps.rs`, `Defect`, `Found.defects`) finds both shapes in the
    bytecode of the functions JBMC reaches.
    - `return-past-handler` is a handler whose range ends at a value `return`, with an instruction computing that value
      that may throw what the handler catches.
    - `stubbed-handler` is a handler of a class JBMC has no class file of, where an exception the program may raise
      extends it on the JVM but not in JBMC. The exceptions counted are those the instructions instrument, and the
      throwables the reached code instantiates. It is broad: `catch (RuntimeException e)` next to any field access
      or virtual call counts, since the null check's exception would escape.
    - A JBMC proof that reaches a defect is no verdict under every `--gaps` mode, assume included, since no statement
      could assume it. A counterexample is still replayed (the replay boundary is unchanged). When it doesn't
      reproduce, `prove`'s message names the defect instead of guessing at a missing method; the notes list it as
      `jbmc defect:`.
  - **Tests:** `the_preflight_names_where_jbmc_raises_an_exception_past_its_handler` covers 8 shapes from
    `p/D.java`: 4 defects and 4 neighbours JBMC runs as the JVM does. It fails with the detection disabled.
    `a_proof_through_a_defect_is_refused_under_every_mode_and_a_counterexample_is_left_to_the_replay` covers `hold`.
    End to end on the real JBMC:
    - both false proofs are now refused, under assume too;
    - `caught/1` and `nestedHandler/1` are unverifiable, naming the defect;
    - `exactCatch` is a violation, as before.
  - **Corpus:** `conformance/caught/3` and `caughtAsRuntime/1`, `/2` were added, and `lib/benchmark/conformance.json`
    regenerated. On the JVM and the own checker they agree; the inline test still fails only on the 12 known
    disagreements, from the JDK version against the contract records.
  - **Job `20261106-203452`** runs what needs JBMC: the integration tests, and the ignored conformance tests under
    `jbmc` and `auto` (strict) and `auto --confirm` (strict and assume).
  - **Upstream:** a report for cause 1 is drafted in the fixture's README, for the user. It is not filed.
  - **Shared files changed:**
    - `lib/src/property.rs`: the unreproduced-witness message takes the preflight's defect first (one call);
    - `lib/tests/conformance.rs`: three claims;
    - `lib/tests/conformance/conformance/Conformance.java`: `caughtAsRuntime`, appended;
    - `lib/README.md`: a paragraph on defects.
    - `equivalence.rs`'s unreproduced message is unchanged; its notes name the defect.
  - **For the reconcile loop and the native stream:**
    - The fix for cause 2 is models of the JDK exception classes with their superclasses, and constructors that keep
      the message, in `lib/models` (not this stream's). Once they are on JBMC's class path, the `stubbed-handler` rule
      no longer fires for those classes.
    - A `GapKind` for defects in `bmc/gaps.rs` could replace the separate `Defect` type, if gaps and defects should
      read alike in `--json`; today a defect shows only in the problem and the notes.
    - 4a's job will run with this guard: a recorded JBMC proof refused for a defect is a difference to report.
- **4a, the strict job on both engines: submitted, `20261106-204220` (pending).**
  - The job runs `build.py` on the 41 recorded B9/B11 JBMC examples (Quorum, Crosscut, Mica), the same filter as
    job `-082917`, in two scratch copies of `examples/`:
    - as recorded (`--engine jbmc`, `--gaps strict`);
    - with only `approach.engine` set to `native` in the copy.
    It saves `gap_table.py --json` for each engine, every result's `result.json`, both build logs, and
    `gap_table.py --compare` between the two tables. Nothing recorded is written. A verdict that differs from its
    expected one is reported in the table's summary, not counted as a failure (`build.py`'s exit 1). The job fails
    only if `build.py` stops early, a result is missing, or a run isn't the engine and gap mode named.
  - `examples/tools/gap_table.py`:
    - each row now names its `engine`, `checker`, the example's `expectation`, and, for an obligation with no verdict,
      its `problem` and `jbmcDefect`: whether it is a JBMC proof refused at a construct JBMC runs otherwise than the
      JVM (3's guard, which records the defect only in the problem);
    - the summary counts the obligations left with no verdict at a gap (under strict a refused proof is already
      `unresolved`, so "strict would refuse" only counts assume runs), those refused at a defect, and the examples
      that differ from their expected verdict;
    - `--compare A.json B.json` lists the obligations whose status differs between two tables. It is 4c's input.
    - A new test in `test_gap_table.py` covers the fields and `--compare`; both tests pass. On the committed results,
      `071#0` and `#1` show as no verdict at the three JDK stubs, as recorded.
  - Inline checks: the example filter gives the 41, and in a scratch copy with the engine rewritten, `build.py --plan`
    gives `--engine native --gaps strict` for all 41 (`--unwind 32` kept on the four Crosscut B9s).
  - No shared file changed.
- **Next:** read the three jobs once collected. From `-201041`, decide 2c (JBMC's default staging, for ordinary checks
  and the `auto` fallback). From `-203452`, triage 3's JBMC tests. From `-204220`, report 4a's table and every
  difference from an expected verdict.
- Status: waiting on jobs 20261106-201041 20261106-203452 20261106-204220

## Loop settings

- session: 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573
- model: claude-opus-5-5
- effort: high
- workspace: jbmc
- fork: 3761db96-b870-47f7-aded-2ba264c165f4

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this
stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your
phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress
as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.
