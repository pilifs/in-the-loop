# Feature loop: engine-priorities-native

Started 2026-11-06 19:15:03 UTC, no limit on cycles, session 63d80e44-36d9-4bcb-9e72-e31c6d9336ef, claude-opus-5-5 at high effort, after change nvvnwrnomzzkktuyypmzxlozsszrxrry.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-native.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'nvvnwrnomzzkktuyypmzxlozsszrxrry..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-native.md` at sha256 10aca92721bdef2af3746b2db6a77c91a3c12f53c8c9ac03daa3672d3870d530.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phase 5 is the core of this stream: don't stop before it is done unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

Session 63d80e44-36d9-4bcb-9e72-e31c6d9336ef was forked from session 3761db96-b870-47f7-aded-2ba264c165f4.

- cycle 1, 2026-11-06 19:20:37, `nzxrwvummoty`: Queue a Bitwuzla 0.8.2 build from source for the solver comparison (verification pending)
  - decided to continue: The loop should go on: this run has committed only Phase 1c, the Bitwuzla build job, which is queued. Phase 4b, the inline `jvmcontract gaps` scans of class initializers, needs nothing but my own work. Phase 5 and 6a–6b are still open too, and none of them waits on that job.
- cycle 2, 2026-11-06 19:38:44, `wnxlynrsoosq`: Count class initializers by shape: enums and their switch maps are all the apps have (Phase 4b)
  - decided to continue: The loop should go on. This run has committed 1c (the Bitwuzla build job) and 4b (the initializer count that fixes Phase 5's scope), and Phase 5, the stream's core, hasn't started. Its first step, static fields and class initialization in the own checker, needs nothing but my own work. Fixing `build.sh` after the failed Bitwuzla job and resubmitting it is also mine to do now.
- cycle 3, 2026-11-06 19:41:15, `mwxvlkzzxkts`: Link CaDiCaL static into the Bitwuzla build and queue it again (verification pending)
  - decided to continue: This run has made three commits: the first Bitwuzla build job, the Phase 4b count, and the fix to the build with the job queued again. Phase 5, the stream's core, hasn't started yet. Its first step needs only my own work: static fields and class initialization in our own checker, with the conformance tests for the three initializer cases (`boom`, `inherited`, `quiet`). Only the Bitwuzla job is waiting, and nothing is waiting on the user.
- cycle 4, 2026-11-06 20:12:04, `kumppqkzlvwn`: Run application class initializers in the own checker, as JVMS 5.5 does (Phase 5, step 1)
  - decided to continue: This run has made four commits: the Bitwuzla build and its fix, the 4b count, and class initializers in our own checker (Phase 5 step 1). Phase 5 isn't done. Its next step, the `Enum.<init>`, `List.of` and `List.copyOf` models with conformance cases checked on the JVM, needs only my own work. Recording the Bitwuzla job that passed is also mine to do, so nothing waits on a job or on the user yet.
- cycle 5, 2026-11-06 20:36:45, `knlrwnqukqwm`: Model Enum.<init>, List.of and List.copyOf for JBMC, checked on the JVM (Phase 5, step 2; verification pending)
  - decided to continue: The loop should go on. Phase 5 isn't done: the rerun of 071 and 013 is queued as job `-203501`, but its other remaining step, enums in the own checker (arrays of references for `$VALUES`, with the `Enum` model run there), needs only my own work. The brief also asks me to do Phase 6a and 6b while that job runs, and both need only my own work too, so nothing waits only on jobs or on the user.
- cycle 6, 2026-11-06 21:08:35, `wnktqxrtllpw`: Record the own checker's solver calls as replayable incremental CNF transcripts (Phase 6a)
  - decided to continue: The loop should go on: Phase 5, the core of this stream, isn't done. Job `-203501` (071 and 013 under strict) is still waiting in the queue, but enums in the own checker (`$VALUES` as an array of references, with the `Enum` model run there) need nothing but my own work. Phase 6b, the narrow solver interface, is also open and is meant to be done while Phase 5's job runs, so nothing left waits only on a job or on the user.
- cycle 7, 2026-11-06 21:27:30, `syntvmqpxlzs`: Put the own checker's SAT solver behind a narrow interface (Phase 6b)
  - decided to continue: Phase 5 isn't done yet. Its last step, enums in the own checker (`$VALUES` as an array of references, with the `Enum` model used there), needs nothing but my own work. Job `-203501` is still waiting in the queue, but that only holds up recording its result, not the enum step. Phase 6c can also be prepared without waiting, so the status stays `working` and the loop should go on.
- cycle 8, 2026-11-06 22:05:15, `ulstzomtvuxt`: Run enums in the own checker: arrays of references, Enum's model, switch maps (Phase 5, step 3)
  - decided to continue: My own work on Phase 5 is finished. What's left of it waits on job `-203501`, which has run but isn't collected yet. Phase 6c still has work that needs only me: putting Bitwuzla behind the solver interface, the word-level prototype for the five workloads, and the job's script. Not everything waits on jobs or on the user, so the status stays `working` and the loop goes on.
- cycle 9, 2026-11-06 22:27:46, `osspkxkzomwy`: Put Bitwuzla behind the own checker's solver interface, chosen by JVMCONTRACT_SOLVER (Phase 6c, step 1)
  - decided to continue: Phase 6c still has steps that need only my own work before its job can be submitted: making Bitwuzla's preprocessing selectable, the word-level prototype for the five workloads, and the job's script. Phase 5's own work is done, and recording job `-203501`'s result only waits for it to be collected, so not everything left waits on jobs or on the user.
- cycle 10, 2026-11-06 22:47:07, `wqskvlymolnr`: Make Bitwuzla's options selectable by name and queue the bit-blasted solver comparison (Phase 6c, step 2; verification pending)
  - decided to continue: The loop should go on. Phase 6c's second part, the word-level prototype for the five cases and its job script, needs nothing but my own work, and it can be done while job `-224616` runs. Phase 5's own work is done. Its unmet criterion, 071's two proofs under strict, needs a change in `jbmc_gaps.rs`, which is the JBMC stream's file, and it is recorded under Progress for the reconcile loop.
- cycle 11, 2026-11-06 23:08:01, `ulsqmxuqnylu`: Give Bitwuzla the own checker's word-level terms, and queue the word-level solver comparison (Phase 6c, part 2; verification pending)
  - decided to stop: Everything left in my phases now waits on jobs. Phase 6c's word-level prototype is committed with its job `20261106-230455`. Phase 6d, the written recommendation, needs that job and the bit-blasted one (`20261106-224616`), and Progress's status already names both. Phase 5's own work is done; its remaining criterion, 071's two proofs under strict, needs a fix in `jbmc_gaps.rs`. That file is the JBMC stream's, and the fix is recorded under Progress for the reconcile loop.

## Summary

# Feature loop summary: `engines-native` stream, 11 cycles

The run made 11 commits on Phases 1c, 4b, 5, 6a, 6b and 6c. Two of my phases are open: 6c's two comparison jobs haven't come back, and 6d (the written recommendation) waits on both. Progress ends with `Status: waiting on jobs 20261106-224616-… 20261106-230455-…`.

## Commits (oldest first)

| Change | What it adds | How it was verified |
|---|---|---|
| `nzxrwvum` Queue a Bitwuzla 0.8.2 build (1c) | `lib/solvers/bitwuzla/build.sh`: downloads a pinned release and checks its sha256, builds it with meson and ninja, installs it under `~/tools/bitwuzla/`, and writes `build.json` recording versions, the CaDiCaL it links, and smoke-test answers. | Tested inline against fake `git` and `curl`, with no network. The build itself ran as job `-192008`, which failed (next row). |
| `mwxvlkzz` Link CaDiCaL statically into the Bitwuzla build | Fixes the `-192008` failure: the installed binary couldn't load `libcadical.so`. Notes that Bitwuzla's CaDiCaL is 2.1.2, while the engine's is 1.9.5. | A meson configure-only run showed the intended static and shared targets. Job `-194049` then **passed**: Bitwuzla 0.8.2, commit `61bdc637`. |
| `wnxlynrs` Count class initializers by shape (4b) | `jvmcontract gaps` gives each `<clinit>` gap a shape, and `initializer_shapes.py` counts them. The apps have 49 initializers: 36 enums and 13 enum switch maps. Of the recorded examples, only 013 and 071 reach any. | A new integration test covers every shape; the unit, integration and skill suites pass. |
| `kumppqkz` Run class initializers in the own checker (5, step 1) | Static fields are kept as path state, and `<clinit>` runs as JVMS 5.5 says, with `ExceptionInInitializerError` and `NoClassDefFoundError`. The witness interpreter was fixed to match the JVM. | Checked on JDK 25.0.5. 8 new conformance cases (16 claims) agree with the JVM in every native mode. `boom`, `inherited` and `quiet` are now decided. |
| `knlrwnqu` Model `Enum.<init>`, `List.of` and `List.copyOf` for JBMC (5, step 2) | New models in `lib/models`, following OpenJDK 25's code. 11 interpreter disagreements with the JVM are fixed. | 11 new conformance cases (22 claims) checked on the JVM. A new test runs the models against the JDK's own classes, and a mutated model fails it. Job `-203501` **failed** (see below). |
| `wnktqxrt` Replayable solver transcripts (6a) | The own checker can record every clause and solver call as incremental CNF. `jvmcontract transcript FILE` replays one. Also fixes a race in `conformance.rs`. | Parser and replay unit tests, and an engine test. `held/lower-bound`'s 460-call transcript replays in 0.178 s, against 0.179 s recorded. |
| `syntvmqp` A narrow `Sat` interface (6b) | Separates the engine's scheduling (`Engine`), encoding (`Blaster`) and solving (`Sat`). No behaviour changes. | A test solver that logs every call gives the same outcome, clauses and calls. `held/lower-bound` writes the same transcripts, counted by clauses and calls. |
| `ulstzomt` Enums in the own checker (5, step 3) | Arrays of references (`anewarray`, `aaload`, `aastore`). The checker now runs the Enum model, so enum initializers, `$VALUES` and switch maps run. | 5 new cases, run on the JVM first. The own checker decides 4 of them, plus the existing `enumState` case; `valueOf` stays a gap. Class-initializer gaps fall to 0 over the apps (from 49) and over the examples. |
| `osspkxkz` Bitwuzla behind `Sat` (6c, step 1) | `JVMCONTRACT_SOLVER=bitwuzla` uses Bitwuzla 0.8.2 at run time, and refuses any other version. Results now name the solver they ran on. | Same verdicts on both solvers, and CaDiCaL's transcripts replay on Bitwuzla. 44 of the 46 engine tests pass on Bitwuzla; the two that fail pin CaDiCaL's models. One indicative replay: CaDiCaL 0.18 s, Bitwuzla 6.2 s by default and 1.06 s with preprocessing off. |
| `wqskvlym` Bitwuzla options by name, and the bit-blasted comparison queued (6c, step 2) | `bitwuzla:preprocess=0,…` style options, checked against the library's own ranges. `lib/solvers/compare.py` runs five workloads on three solver configurations. Also records job `-203501`'s result. | The script's 4 tests pass, and a trial on two workloads gives the expected verdicts with no replay contradiction. Job **`-224616` is pending**. |
| `ulsqmxuq` Word-level terms for Bitwuzla (6c, part 2) | A `Terms` interface. With `bitwuzla-words`, arithmetic, comparisons, shifts and `ite` go to Bitwuzla as bit-vector terms instead of bit-blasted circuits. `compare.py --words` runs the word-level comparison. | The blaster's int and long tests also run on the word-level solver, and its model values match the engine's own evaluation. 46 of 51 engine tests pass with it chosen; the 4 that fail by design pin lazy refinement or clauses. One indicative run: `reverse` 0.12 s against CaDiCaL's 0.18 s. Job **`-230455` is pending**. |

Throughout the run, the unit (up to 162), integration (64) and skill suites pass. Conformance fails only two known tests:
- **The 12 library-record claims:** the contracts were recorded on JDK 25.0.4.1 and this machine runs 25.0.5. Job `-203501`'s new record should fix this after the merge.
- **`lib/benchmark/conformance.json`:** it belongs to the JBMC stream and is now about 32 claims behind the corpus.

## Verification jobs

- **Waiting on you to run them:**
  - `20261106-224616-the-own-checker-on-cadical-and-on-bitwuz`: the bit-blasted comparison, about 1 h 30 min.
  - `20261106-230455-the-own-checker-on-cadical-and-on-bitwuz`: the word-level comparison, about 30 min.
- **Failed and already dealt with:**
  - `-192008`: the Bitwuzla build. Fixed and rerun as `-194049`, which passed.
  - `-203501`: 071 and 013 under strict. See below.
- **This workspace's `pipeline.py status` is stale.** It still lists `-192008`, `-194049` and `-203501` as pending, because their results were collected in another workspace. It shows the two Bitwuzla builds as "cannot run here" (they ask for 8 CPUs and 6–8 GiB); since both have already run, that doesn't matter.
- **The other stream's jobs in the queue:** `-192959`, `-194328`, `-201041`, `-203452` and `-204220`.

## `sync.py check` before pushing

- **0 warnings for you to judge.**
- **23 errors, none on this run's commits** (this session is `63d80e44`). All of them say a session "has no manifest" or "points at a log the manifest does not list".
  - They are on other sessions' changes, mostly the JBMC stream's `7b8a1d3b`, plus `0c61a765`, `2b3fe2be`, `b4d45e13`, `ae994066`, `62264445` and `e47f34c2`.
  - They will need fixing before a push succeeds, probably by pushing from the workspace that holds those sessions.

## Needs your decision or input

- **An upstream JBMC report (outward-facing, so not drafted or sent).**
  - **The problem:** JBMC 6.11.0 gives a false success under strict on the conformance case `declaring`. On a `getstatic` of a field declared in `Holder` but reached through `Sub`, it runs `Sub.<clinit>`; the JVM initializes `Holder` alone.
  - **Reproducer:** the case in `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`.
  - **Decide:** whether to report it.

## Left for the reconcile loop or the JBMC stream

- **Phase 5's last criterion is unmet: 071's properties 1 and 2 aren't verified under strict.** `jbmc_gaps.rs` refuses them over `Collection.isEmpty` and `toArray` stubs found in `ImmutableCollections.listCopy`, which no path of these proofs reaches. The fix is a gap check that follows paths rather than JBMC's call graph, in the JBMC stream's file.
- **`jbmc_gaps.rs` should also name a gap** for a static field reached through a class that isn't its declaring class (the `declaring` case).
- **Regenerate `lib/benchmark/conformance.json`** with `JVMCONTRACT_BLESS=1`.
- **Update 071's and 013's notes and pages** from job `-203501`'s outputs.

## Other things worth knowing

- **Corrections to the brief, given in the commit messages:**
  - Phase 5's text says the own checker refuses arrays of references. It no longer does, though `List.of` and `copyOf` stay JBMC-only.
  - Bitwuzla was built on x86_64, not ARM64; `build.json` records the architecture.
  - 6c's single job became two: bit-blasted and word-level.
- **Two flaky test failures,** each seen once and passing when run alone:
  - An integration test that runs JBMC, in the 6a cycle; its message wasn't kept.
  - `jbmc::tests::a_run_that_dies_gives_no_verdict_whatever_it_printed`, under `JVMCONTRACT_SOLVER=bitwuzla-words`.
- **The inline Bitwuzla timings are single runs and only indicative.** The two pending jobs measure them properly, and their results are the evidence 6d needs before any default changes.

Ended 2026-11-06 23:09:53 after 11 cycle(s): the session decided the work was done.
