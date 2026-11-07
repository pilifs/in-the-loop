# Verification findings and decisions

What the verification runs turned up that needs a person: verdicts against a change, failures a submitter has to
fix, and decisions the managing agent took that change what the results mean. The agent running
[`/run-verification`](../.claude/skills/run-verification/SKILL.md) adds an entry whenever a run produces one, and
updates or closes entries when a later run settles them. Results themselves stay in [`results/`](results/); this
page is the short list of what is still open, and what was decided, so that nothing is lost between sessions.

Each entry has an id (`VF-NNN`, never reused), and these fields:

- **Status**: `open` (needs someone), `decided` (a decision was taken and is recorded here, nothing to do), or
  `closed` (settled: say by what, with the job or commit). Open entries come first, newest first; the rest follow.
- **Raised**: the date, the machine (`runner.host`), and the run's job ids and the commit they ran at.
- **Found**: what happened, with the evidence a reader needs without the logs.
- **Needs**: what would settle it, and who should act: the submitter, a brief's loop, or the user.
- **Tracked in**: where the work lives, if anywhere else (a brief's Progress, an example's notes).
- **Closes when**: the check that settles it, usually a job to rerun unchanged.

## Open

### VF-011: the own checker counts a loop's unwinding over the whole path, so example 052 is left to JBMC

- **Status**: open (deferred by the user on 2026-11-07, until after the foundations loop)
- **Raised**: 2026-11-07, from job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab485`, `vm-1`) and
  the coverage inventory `examples/coverage.md` (commit `unvpruot`). Not a job failure.
- **Found**: under `--gaps strict`, obligation `052#0` is established by JBMC (with unwinding assertions at 16) and
  unresolved on the own checker: "a loop was not fully unwound with --unwind 16 (PropertyHarness.check at pc 238)".
  As read, not yet reproduced: `Engine::jump` in `lib/src/bmc/mod.rs` counts back edges per path and per
  `(class, method, target)`, and never resets the count when the loop is left. The property's `\max` over `k` of a
  `\sum` over `i < k` is two nested loops in the harness (`harness/expr.rs` compiles each quantifier as a loop), so over
  an array of length 8 one path takes the inner back edge up to 36 times. The count is incomplete, not unsound: a
  path cut short gives no verdict.
- **Needs**: a reproducer first (a nested loop whose inner loop runs fewer than the bound each time but more in total),
  then counting per entry of a loop. Ranked second among the own checker's extensions in `examples/coverage.md`.
- **Tracked in**: `examples/coverage.md` (extension 2), `llm-dlc/loops/engine-priorities.md` (Next, item 9).
- **Closes when**: a job runs 052 under strict on the own checker (`approach.engine` set to native in a copy) and it is
  established with no gap.

### VF-010: the own checker's regression proof of `Pricing#total` sometimes runs out of time: its branch probes depend on wall-clock time

- **Status**: open (deferred by the user on 2026-11-07, until after the foundations loop)
- **Raised**: 2026-11-06 on cvm, inline, while triaging job `20261106-203452`; seen again in full inline suite runs on
  2026-11-06 and 2026-11-07 (commits `xrrxwxny`, `vrkpmtqv`, `pkuyvwwp`).
- **Found**: `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (`lib/tests/integration.rs`) fails now and then
  on the own checker's regression proof of `fixtures.Pricing#total` (the rounding refactor) and passes alone. Of 8
  identical runs of `jvmcontract equivalence --target 'fixtures.Pricing#total' --engine native --timeout 40`, 6 found
  the violation in about 4 s (13 solver calls, 2 of 2 divisions built in full) and 2 ran out of time at the 8th solver
  call (0 of 2 built). As read: the branch probes (`bmc/mod.rs`, `probe`) are given as long as the solver calls so far
  took, at least a second, so which side of a branch is left undecided, and with it the path order and the queries,
  depends on the machine's speed. One order leaves a query that doesn't finish.
- **Needs**: probe budgets that don't depend on wall-clock time (a count of conflicts or of solver calls, say), with
  the 8-run reproducer above showing every run alike.
- **Tracked in**: `llm-dlc/loops/engine-priorities-jbmc.md` (step 3's notes), `llm-dlc/loops/engine-priorities.md` (Next,
  item 8).
- **Closes when**: the reproducer gives the same answer in 8 of 8 runs, and a job runs the integration tests with no
  failure.

### VF-009: `auto --confirm` disagrees with the JVM on `boomTwice` and `enumBroken`: JBMC's refutation at `n=0` is spurious, the own checker is right

- **Status**: open
- **Raised**: 2026-11-07 on `vm-1`. Job `20261107-010728-jbmc-s-extra-initializers-named-and-refu` (at `254f1d7a4893`), step 2 (steps 1 and 3 passed: the corpus under JBMC and auto, and the draft report's example).
- **Found**: `the_corpus_agrees_with_the_jvm_under_auto_confirm` (tests/conformance.rs:792) has 8 disagreements, all on
  `boomTwice [assert result == 2]` and `enumBroken [assert result == 12]`, under `--gaps Strict` and `Assume`: Auto
  reports a violation at `n=0` that the JVM does not reproduce (the interpreter gives 2 and 12, the harness holds), and
  `--confirm` says the engines disagree: the own checker proves the property on every input and JBMC 6.11.0 refutes it
  on `n=0`. The same shape as VF-007 (closed by job `20261106-231317`) but on methods that run an exception handler
  twice and an enum initializer; the job's change (extra initializers named and refused in the preflight) did not
  cover them. Step 3's JBMC output ("1 of 13 failed") is the expected violation of that example.
- **Needs**: the engine-priorities-jbmc loop: why JBMC refutes `boomTwice(n=0)` and `enumBroken(n=0)` (a class
  initializer JBMC runs that the JVM does not? the `--throw-runtime-exceptions` path?), and refuse or model it.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md). Deferred by
  the user on 2026-11-07, untriaged, until after the foundations loop; a candidate for the draft brief
  [`llm-dlc/loops/jbmc-upstream.md`](../llm-dlc/loops/jbmc-upstream.md) if JBMC's handling of a throwing initializer
  turns out to be the cause. Both methods are cases the engines-native stream added in Phase 5, step 3 (`ulstzomt`):
  the rest of that stream's cases agree with the JVM under JBMC and `auto` (jobs `20261107-012013`, `20261107-022319`),
  so this finding is all that is left of the engine-priorities brief's "conformance job for the native stream's step 3
  cases" (Next, item 8).
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 2 pass.

### VF-002: examples 147, 148 and 149 never reach a proof

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-053555-example-147-b11-advised-contracts-a-cont`,
  `20261106-053555-example-148-b11-advised-contracts-full-j` (at `ef5d434c48db`) and
  `20261106-061323-example-149-b11-contract-library-full-ji` (at `8ea88f97e447`).
- **Found**: each fails within a second with "the patch does not change the subject file
  examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/retry/Jitter.java". The patches create that file
  (`--- /dev/null`), and `build.py`'s `excerpts()` requires the subject to exist before the patch. Deterministic: it
  fails the same on any machine, at the jobs' commits and still on 2026-11-06.
- **Needs**: either `excerpts()` accepts a subject the patch creates (an empty before side), or the examples' patches
  stop creating it. For whoever owns the advised-contracts examples (Phase 3 of the sound-verdicts brief).
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), and the notes of examples 147, 148 and 149.
- **Closes when**: the three jobs, resubmitted after the fix, pass with each example's expected verdict.

### VF-001: JBMC verdicts the JVM contradicts, passed through by `--engine auto`

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Jobs `20261106-021741-conformance-corpus-under-jbmc-and-engine` and
  `20261106-024336-conformance-corpus-under-engine-auto-con`, both at `470be6c5ff8b`, JBMC 6.11.0.
- **Found**: the conformance corpus (54 methods, 93 claims, the JVM as reference) disagrees with JBMC in both
  directions:
  - **JBMC proves seven claims the JVM refutes**, under `--gaps strict`: `capacity`, `builderCapacity`,
    `mapCapacity`, `setCapacity` and `loadFactor` (JDK constructors that throw on a negative capacity or a load
    factor of 0 or less; JBMC's library models, pinned to 2022, return normally), `nullMonitor`
    (`synchronized ((Object) null)` throws `NullPointerException` on the JVM), `firstByte` (`Random.nextBytes`) and
    `pairsEqual` (a record's `equals` through `invokedynamic`).
  - **JBMC reports violations the JVM does not reproduce** on `caught(n=0)` and `nestedHandler(n=0)`, which catch the
    `ArithmeticException` of an integer division by zero. The tool's own checker proves both and the JVM agrees.
    Either JBMC's semantics or a flag jvmcontract does not pass (such as `--throw-runtime-exceptions`).
  - **`--engine auto` takes JBMC's wrong `Verified`** for `loadFactor` and `pairsEqual`, where the own checker has no
    verdict, under strict and under assume. This part is jvmcontract's, not JBMC's.
- **Needs**: Phase 1 of the sound-verdicts brief is not done, though the brief read as if it were. Its criterion is
  that no engine, nor `--engine auto`, gives `Verified` under strict for a claim the JVM refutes. Closing it means
  treating JBMC's verdicts on JDK calls its models stand in for as gaps under strict, making `synchronized (null)`
  and division by zero behave as on the JVM under JBMC (or refusing them), and not letting auto take a JBMC
  `Verified` unchecked. For the sound-verdicts loop, or a loop of its own; the user is deciding how to take it on.
- **Tracked in**: [`llm-dlc/loops/sound-verdicts.md`](../llm-dlc/loops/sound-verdicts.md#progress) (the entry of
  2026-11-06 on `vm-1`), with every disagreement; the logs in each job's `results/ID/logs/`.
- **Closes when**: both jobs, resubmitted unchanged after the fix, pass.

## Decided and closed

### VF-012: the own checker raises a false alarm on `conformance/leadingZerosLong/2`, so the benchmark step exits 1 and the encoding-timing check never ran

- **Status**: closed by job `20261107-033320-the-own-checker-s-encoding-timed-whole-p` (at `dc03b87fb961`, `vm-1`, 2026-11-07): both steps passed, so no false alarm and the timing comparison ran and passed
- **Raised**: 2026-11-07 on `vm-1` (run with `--memory 7G --workers 3`). Job
  `20261107-032249-the-own-checker-s-encoding-timed-whole-p` at `58b89dd9ce1c`.
- **Found**: step 1 (`lib/benchmark/run.py --engines native`) ran all 533 own-checker runs in 143 s and exited 1,
  because three runs are classed `false-alarm`: `conformance/leadingZerosLong/2` under strict, assume and advised. The
  own checker reports `violation` with witness `48` in 0.04 s (610 variables, 2114 clauses), and the JVM replay says
  `witnessOnTheJvm: holds`, i.e. the witness is spurious. The case is not in the committed `lib/benchmark/results.json`
  (new since that run, probably from the numberOfLeadingZeros change), so this is not a regression of the encoding
  timing. Step 2 (no run flagged `phasesExcess`; median seconds ratio against job `20261106-201041` at most 1.10) was
  skipped. Read from the saved JSON in the work directory: 0 of 533 runs carry `phasesExcess`, which is promising but
  is not the check the job names, and the ratio was not computed. No other reference disagreement.
- **Needs**: whoever owns the `Long.numberOfLeadingZeros` modelling in the own checker (the engine-priorities loop)
  fixes the encoding behind case `leadingZerosLong/2` or marks the case as expected-unsupported; then the job is
  resubmitted unchanged (`pipeline.py resubmit 20261107-032249-the-own-checker-s-encoding-timed-whole-p`).
- **Update 2026-11-07 (cause found, fixed in the benchmark runner)**: the own checker's witness is right, and the JVM
  replay misread it. Run inline, `jvmcontract prove ... 'conformance.Conformance#leadingZerosLong' --assert
  'result < 64' --engine native --gaps strict` reports `leadingZerosLong(arg0=0)`, outcome 64, which the JVM bears out.
  The tool writes a `long` input as a decimal string (`"0"`), and `lib/benchmark/run.py`'s `token()` took any
  one-character string for a `char` and passed its code unit: `ord('0')`, 48, where `numberOfLeadingZeros(48)` is 58.
  Every single-digit `long`, `float` or `double` witness, alone or in an array, was misread that way. This case is the
  first in the corpus whose witness is one. `witness_arguments` now reads an input as a `char` only if its declared
  type is one. `test_a_long_or_a_double_witness_of_one_digit_is_its_value_not_a_char` failed before the fix
  (`48;[48,-2,55];53`) and passes after it. Step 2's check run by hand on the job's saved
  `lib/target/benchmark-native.json`: 0 of 533 runs flagged, median ratio 0.963 (quartiles 0.871 to 1.006) over the 29
  runs of 0.1 s or more, 31.5 s against 32.0 s over the 356 paired runs. Resubmitted unchanged.
- **Tracked in**: the job's `logs/1-benchmark-own-checker-only.log`.
- **Closes when**: the resubmitted job passes (no false alarm, no `phasesExcess`, median ratio at most 1.10).
- **Result**: 533 own-checker runs, 0 flagged `phasesExcess` (reference job: 1 of 356); median seconds ratio 0.974 over 29 runs of 0.1 s or more (quartiles 0.872 to 1.002).

### VF-008: the conformance corpus under JBMC and auto: JBMC says `Verified` on `declaring`, which the JVM refutes

- **Status**: closed by job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, 2026-11-07, `vm-1`): step 5 ran `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` and it passed (646 s). Not the same job resubmitted, but the same test.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 6.
- **Found**: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` (tests/conformance.rs:749) reports 1 disagreement out of
  73 cases: `declaring [assert result == n + 107]`, `--gaps strict` on JBMC says Verified ("2 properties proved over
  n: int in 0.2 s; loops unwound 16 times with unwinding assertions") and the JVM refutes it. This is the unsoundness
  VF-001 describes, now on a case the strict policy was meant to cover.
- **Needs**: the engine-priorities-jbmc loop (or whoever owns the JBMC staging policy) to find why strict lets this
  proof through (a model or exception path unmodelled?), and add the case to the brief's Progress.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md); see also VF-001.
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 6 pass.

### VF-005: example 071 under strict: the first two proofs are `unverifiable` on JDK 25.0.5 where the job expects `verified` with no gap

- **Status**: closed by job `20261107-024759-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `854a0d8f756e`, 2026-11-07, `vm-1`): step 3, `071: the first two proofs stand with no gap`, passed, with obligations 0 and 1 verified and no gaps (the `Collection` stubs reached by JBMC's call graph and never entered), after the preflight's index fix (`xmslpytz`). Not the same job resubmitted, but the same assertion.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 3 (steps 1, 2, 4 and 5 passed: 013 under strict, and the contract library recorded on this JDK).
- **Found**: the assertion that obligations 0 and 1 of example 071's result are `verified` with no gaps fails: they are
  `unverifiable` with gaps `jdk-reference-method:java.util.Collection.toArray()...@jdk-25.0.5` and
  `jdk-primitive-method:java.util.Collection.isEmpty()Z@jdk-25.0.5`. Step 2 ran the example's own build as expected,
  so the example stands and the expectation about the models (Enum and List) is what does not hold: the models were
  not enough on JDK 25.0.5, or the recorded library does not cover `Collection`. (The 41-example job saw 071#0 and 071#1 unresolved on `Enum.<init>`/`List.of`, a different gap set.)
- **Update 2026-11-07**: job `20261107-012013-jbmc-s-stubs-on-no-path-are-no-gaps-exam` (at `8b45798e6417`, `vm-1`) step 3 fails
  in a new way: the stubs on no path are now named as "no gaps" in the output (`note: JBMC's call graph reaches 2 stubs
  ... never enters ... no gaps: Collection.isEmpty(), Collection.toArray()`), but obligations 0 and 1 are still
  `unverifiable` with an empty gap list, where the job expects `verified`. Steps 2 (071 build), 4 (013 under strict) and 5 (corpus) passed.
  So the gap is gone and the verdict is not: something else in the strict path still withholds the proof.
- **Needs**: the submitter to say whether the `Collection` methods should be modelled or the expectation relaxed, and
  why an obligation with no gaps is `unverifiable` (see the verifier-output.txt of the job's 071 output).
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted unchanged at a commit that fixes it, passes step 3.

### VF-007: engine-priorities step 3: escaping exceptions: `auto --confirm` disagrees with the JVM on 12 claims, and an integration test times out

- **Status**: closed by job `20261106-231317-jbmc-s-defects-under-confirm-the-unmaske` (at `14607996bdca`, 2026-11-06, `vm-1`): the same three commands as `20261106-203452`, all three steps passed (33m53s, peak 1.3 GiB). The `Pricing#total` timeout did not recur.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203452-jbmc-s-escaping-exceptions-named-and-ref` (at `ffb68ef59525`), steps 1 and 3. Step 2 (corpus under JBMC and auto) passed.
- **Found**: step 3 (`the_corpus_agrees_with_the_jvm_under_auto_confirm`, tests/conformance.rs:689) has 12
  disagreements, all on methods that catch an exception (`caught`, `caughtAsRuntime`, `nestedHandler`, with `n=0`):
  Auto under `--gaps Strict` and `Assume` reports a violation the JVM does not reproduce (the harness holds), and
  `--confirm` says the engines disagree: the tool's own checker proves `n != 0 || result == -1` and JBMC refutes it on
  `n=0`, while the interpreter gives -1. So JBMC's counterexample is spurious on caught exceptions (not the checker).
  Step 1: integration test `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` (tests/integration.rs:1431) got
  Unverifiable ("the solver did not finish within the time limit") for `fixtures.Pricing#total`, expected Violation;
  62 other tests passed (703 s). That one may be a time limit on a 2 CPU job rather than a logic fault: not rerun to tell.
- **Needs**: the engine-priorities-jbmc loop: fix the handling of caught exceptions in the JBMC path, and decide whether
  the `Pricing#total` test needs a larger solver limit or a fixed expectation.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md).
- **Closes when**: the same job, resubmitted unchanged, passes all three steps.

### VF-006: engine-priorities step 4a: the 41-example gap-table job fails on a schema error, so no table exists

- **Status**: closed by job `20261107-000039-the-41-recorded-jbmc-examples-under-stri` (at `98bab48570e6`, 2026-11-07, `vm-1`): all three steps passed (4m22s, peak 1.1 GiB); 41 examples, 43 obligations in the table on both engines. 5 of 43 obligations differ in status between jbmc and native (013#0, 035#0, 052#0, 071#2, 127#0), as the brief wanted listed; 6 native obligations have no verdict at a gap (013#0, 037#0, 071#0, 071#1, 071#2, 127#0), and 037#0 is refused at a JBMC defect. Those are results for step 4a, not failures of the job.
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-204220-the-41-recorded-jbmc-examples-under-stri` (at `61f5e48d1abf`).
- **Found**: steps 1 and 2 stop at "result.json: Additional properties are not allowed ('sat' was unexpected)" on
  example 013, in the result schema check of `build.py`'s attempt. Only 9 of the 41 examples reached the table (32 skipped as "not format 2"), so step 3's assertion `9 examples in the table, not 41` also fails. The same schema complaint ('newProblems' unexpected) is in older B12 results, so the result schema may lag the writer.
- **Update 2026-11-06**: rerun `20261106-231837-the-41-recorded-jbmc-examples-under-stri` (at `835d5f28cbfd`, `vm-1`) fails again in a new way: step 2 (own checker) exits 1 at "result.json: Additional properties are not allowed ('phasesExcess' was unexpected)" on a `jvmcontract prove` attempt (attempt 018), so `sat` is fixed but the schema still lags the writer on another field. Steps 1 passed. Only 12 of 41 examples reach the table (29 skipped as "not format 2"), so step 3 again fails with `12 examples in the table, not 41`. Example 013 differs from its expected verdict (013#0 unresolved on `TermOrder.<clinit>`); 071#0 and 071#1 are unresolved on `Enum.<init>`, `List.copyOf`, `List.of` (see VF-005).
- **Needs**: the submitter (engine-priorities step 4a): add `sat` and `phasesExcess` to the result schema (or stop writing them; check every field the writer emits against it), check that the 41 examples carry format-2 results with gaps recorded, then resubmit.
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted, passes with 41 examples in the table.

### VF-004: the CBMC 6.11.0 source-reading job's grep for `run_property_decider` matches nothing

- **Status**: closed (job `20261106-194328-cbmc-6-11-0-s-source-times-runtime-post`, passed 2026-11-06 at `3feadaf0f7a2`: the corrected grep matched and all three checks found their strings)
- **Raised**: 2026-11-06 on `vm-1` (run with `--memory 8G --workers 2`). Job
  `20261106-192959-cbmc-6-11-0-s-source-times-runtime-post` at `b4c0164b852f`.
- **Found**: both files download (sha256 in the log) and step 1 prints the `== bmc_util.cpp: run_property_decider`
  header, then exits 1 after 0.4 s with no further output. Under `set -euo pipefail` the next command,
  `grep -n -A45 "^decision_proceduret::resultt run_property_decider" bmc_util.cpp`, matched nothing: that return type
  and line layout is not how 6.11.0 declares the function (likely a different return type or the name on its own line
  after the type). So the job never reached the `Runtime Solver` / `Runtime Post-process` / `finish_eager_conversion`
  checks. This is a defect in the job's step, not a finding about CBMC. I did not edit the step.
- **Needs**: the submitter resubmits with a pattern that matches (for instance `grep -n -B2 -A45 "run_property_decider("`),
  or drops the `-n -A` display and keeps the three `grep -q` checks.
- **Tracked in**: the job's `logs/1-fetch-and-show-cbmc-6-11-0-s-s.log`.
- **Closes when**: the corrected job passes.

### VF-003: Bitwuzla 0.8.2 builds but the installed binary cannot load `libcadical.so`

- **Status**: closed (job `20261106-194049-bitwuzla-0-8-2-built-from-source-cadical`, passed 2026-11-06 at `66dd857b6891`: CaDiCaL linked static, `bitwuzla --version` 0.8.2, three smoke queries gave the expected sat/unsat, C API through pkg-config works)
- **Raised**: 2026-11-06 on this 24-CPU host (run with `--memory 8G --workers 2`). Job
  `20261106-192008-bitwuzla-0-8-2-built-from-source-for-the` at `3853fcc7e8b7`.
- **Found**: `lib/solvers/bitwuzla/build.sh 0.8.2` downloads, compiles (217 targets, 24 s, peak 1.9 GiB) and installs into
  `~/tools/bitwuzla/bitwuzla-0.8.2`, then its check exits 127: `bitwuzla: error while loading shared libraries:
  libcadical.so: cannot open shared object file`. The shared-library build links CaDiCaL as a shared subproject, but
  no `libcadical.so` exists anywhere under `~/tools/bitwuzla`: meson did not install it (or no rpath points at it).
  Deterministic; not a resource problem. The partial install is left in place.
- **Needs**: whoever owns the solver comparison fixes `build.sh`: install CaDiCaL's library into the prefix with an
  rpath, or build CaDiCaL static, and check with `ldd` before the version smoke test.
- **Tracked in**: the job's `logs/1-build-bitwuzla-0-8-2.log`.
- **Closes when**: the job, resubmitted after the fix, passes.

None yet.
