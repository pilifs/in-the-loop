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

### VF-008: the conformance corpus under JBMC and auto: JBMC says `Verified` on `declaring`, which the JVM refutes

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 6.
- **Found**: `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` (tests/conformance.rs:749) reports 1 disagreement out of
  73 cases: `declaring [assert result == n + 107]`, `--gaps strict` on JBMC says Verified ("2 properties proved over
  n: int in 0.2 s; loops unwound 16 times with unwinding assertions") and the JVM refutes it. This is the unsoundness
  VF-001 describes, now on a case the strict policy was meant to cover.
- **Needs**: the engine-priorities-jbmc loop (or whoever owns the JBMC staging policy) to find why strict lets this
  proof through (a model or exception path unmodelled?), and add the case to the brief's Progress.
- **Tracked in**: [`llm-dlc/loops/engine-priorities-jbmc.md`](../llm-dlc/loops/engine-priorities-jbmc.md); see also VF-001.
- **Closes when**: the same job, resubmitted unchanged at a fixing commit, has step 6 pass.

### VF-007: engine-priorities step 3: escaping exceptions: `auto --confirm` disagrees with the JVM on 12 claims, and an integration test times out

- **Status**: open
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

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-204220-the-41-recorded-jbmc-examples-under-stri` (at `61f5e48d1abf`).
- **Found**: steps 1 and 2 stop at "result.json: Additional properties are not allowed ('sat' was unexpected)" on
  example 013, in the result schema check of `build.py`'s attempt. Only 9 of the 41 examples reached the table (32 skipped as "not format 2"), so step 3's assertion `9 examples in the table, not 41` also fails. The same schema complaint ('newProblems' unexpected) is in older B12 results, so the result schema may lag the writer.
- **Needs**: the submitter (engine-priorities step 4a): add `sat` to the result schema (or stop writing it), check that the 41 examples carry format-2 results with gaps recorded, then resubmit.
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted, passes with 41 examples in the table.

### VF-005: example 071 under strict: the first two proofs are `unverifiable` on JDK 25.0.5 where the job expects `verified` with no gap

- **Status**: open
- **Raised**: 2026-11-06 on `vm-1`. Job `20261106-203501-examples-071-and-013-under-strict-with-t` (at `7457928f1864`), step 3 (steps 1, 2, 4 and 5 passed: 013 under strict, and the contract library recorded on this JDK).
- **Found**: the assertion that obligations 0 and 1 of example 071's result are `verified` with no gaps fails: they are
  `unverifiable` with gaps `jdk-reference-method:java.util.Collection.toArray()...@jdk-25.0.5` and
  `jdk-primitive-method:java.util.Collection.isEmpty()Z@jdk-25.0.5`. Step 2 ran the example's own build as expected,
  so the example stands and the expectation about the models (Enum and List) is what does not hold: the models were
  not enough on JDK 25.0.5, or the recorded library does not cover `Collection`. (The 41-example job saw 071#0 and 071#1 unresolved on `Enum.<init>`/`List.of`, a different gap set.)
- **Needs**: the submitter to say whether the `Collection` methods should be modelled or the expectation relaxed.
- **Tracked in**: [`llm-dlc/loops/engine-priorities.md`](../llm-dlc/loops/engine-priorities.md).
- **Closes when**: the job, resubmitted unchanged at a commit that fixes it, passes step 3.

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
