# Feature loop: engine-priorities-jbmc

Started 2026-11-06 19:15:03 UTC, no limit on cycles, session 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573, claude-opus-5-5 at high effort, after change nvvnwrnomzzkktuyypmzxlozsszrxrry.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'nvvnwrnomzzkktuyypmzxlozsszrxrry..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md` at sha256 4b2f54d4789ec8e4eab1b37b1dbe2d0b0463b1e82d9048d770cc0d8fab4f001f.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

Session 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573 was forked from session 3761db96-b870-47f7-aded-2ba264c165f4.

- cycle 1, 2026-11-06 19:30:49, `snprkxtxpqkt`: JBMC's phases are exclusive: post-processing counted once, overcounts flagged (verification pending)
  - decided to continue: The loop should go on: this run has committed only Phase 1a. Phase 1b (recording the SAT backend in `results.json` and in each result's evidence) and Phase 2a (the JBMC staging-policy option) still need nothing but my own work. Phases 1 and 2 are this stream's core, and nothing left waits on a job yet. The CBMC source-check job is a confirmation that nothing depends on.
- cycle 2, 2026-11-06 19:47:48, `xzrpqnvrlvpm`: Propose this session's mangled C++ symbol names for the allow list; note the resubmitted CBMC source job
  - decided to continue: The loop should go on. Phase 1 is now committed: 1a's exclusive phases, then 1b's SAT record together with the allow-list proposals. Phase 2a, the staging-policy option for JBMC checks with its unit tests, needs nothing but my own work. Phase 2 is core to this stream, so stopping before it would go against the brief. Nothing left waits only on a job: the resubmitted CBMC source check `-194328` gates nothing.
- cycle 3, 2026-11-06 20:02:32, `tvquoumwxvrq`: Record that CBMC 6.11.0's source nests Runtime Post-process inside Runtime Solver, as phases.rs assumes
  - decided to continue: The loop should go on. This run has committed 1a, 1b and 2a, and the CBMC source check that 1a relied on has passed. Phase 2 is core to this stream and isn't finished: 2b needs nothing but my own work. That means changing `lib/benchmark/run.py` to run the JBMC cases once per policy and report each policy's time, verdict and witness size, then queuing the job. Phase 3 is inline work too, to do while that job runs.
- cycle 4, 2026-11-06 20:11:19, `xtkwolstzuyt`: The benchmark runs JBMC under each staging policy and compares them, proofs and counterexamples apart (verification pending)
  - decided to continue: The loop should go on. This run has committed 1a, 1b and 2a, and 2b is now queued as job `20261106-201041`, so only 2c waits on a job. Phase 3 needs nothing but my own work: finding why JBMC's witnesses on `conformance/caught/1` and `nestedHandler/1` don't reproduce, which the brief schedules for while the job runs. 4a's strict job over the 41 examples can also be written and submitted without waiting on anything.
- cycle 5, 2026-11-06 20:36:15, `svvrpymrpslx`: JBMC lets a runtime exception past its handler in two shapes: the preflight names them and refuses a JBMC proof through one (verification pending)
  - decided to continue: The loop should go on. Phase 3 is committed: the cause is found and guarded, and the upstream report is drafted. Its JBMC tests run in job `-203452`, and 2c waits on job `-201041`. But 4a's job, a strict run on both engines over the 41 recorded JBMC examples that saves `gap_table.py --json`, needs only my own work to write and submit. It will also show how many recorded JBMC proofs the new guard refuses.
- cycle 6, 2026-11-06 20:43:24, `xrrrwlrmqqpu`: The 41 recorded JBMC examples run under strict on both engines, tabulated per obligation (verification pending)
  - decided to stop: The loop should stop. Every step of my phases that needs only my own work is done and committed: 1a, 1b, 2a, 2b's job, Phase 3's cause, check and draft report, and 4a's job. What is left waits on jobs: 2c needs the staging benchmark `20261106-201041`, Phase 3's JBMC tests are in `20261106-203452`, and 4a's table comes from `20261106-204220`. Progress already ends with `Status: waiting on jobs 20261106-201041 20261106-203452 20261106-204220`, so the loop is run again once their results are collected.

## Summary

# engines-jbmc loop: summary of this run

The run made eight commits in workspace `jbmc`, against `llm-dlc/loops/engine-priorities.md`. Phases 1a, 1b, 2a and 3 are done, and the 2b and 4a jobs are submitted. Everything left (2c, the Phase 3 job, the 4a report) waits on queued jobs. The working copy is clean, and nothing was pushed.

## Commits

| Change | What it adds | How it was verified |
|---|---|---|
| `snprkxtx` **Phase 1a**: JBMC's phases no longer double-count | `lib/src/phases.rs` now counts JBMC's post-processing once, as encoding, instead of also inside "Runtime Solver". Before, phases could add up to more than the run: 22.0 s of phases in a 15.9 s run. `Phases::excess` flags any run whose phases still exceed its time, and the benchmark leaves those runs out of "Where the time goes". The recorded `RESULTS.md` stands, with a note that its JBMC shares overcount. | Fixtures of real JBMC 6.11.0 output in `lib/tests/fixtures/jbmc-phases/`. Lib 150, integration 63 and skill tests pass; `test_run.py` 19 pass. |
| `olttywtt` **Phase 1b**: every result names its SAT solver | Results now record the solver, its version and its configuration on both engines. The own checker uses CaDiCaL 1.9.5 (cadical crate 0.1.16). JBMC uses CaDiCaL 3.0.0, read from the JBMC executable without running it. The benchmark lists the solvers in `environment.sat`. | New unit tests, and 3 new benchmark tests (22 pass). A real run prints the record; the recorded job `-102624` renders as before. |
| `xzrpqnvr` Allow-list proposals | Reading `/usr/bin/jbmc`'s strings in 1b put seven mangled C++ symbol names in this session's log. They are proposed for the allow list as false positives. The commit also records that job `-192959` failed on its own grep and was resubmitted as `-194328`. | — |
| `uykqwxvr` **Phase 2a**: `--jbmc-staging` | A new option on `equivalence` and `prove` with three policies: `staged` (the default until 2c decides), `full-range` and `tight`. The own checker's stages and `--confirm` don't follow the option. The policy is recorded as `search.staging`. | Unit tests in `deadline.rs`, plus an end-to-end test against a stand-in JBMC. Changing `equivalence` to ignore the option makes that test fail. Lib 155 and integration 63 pass. |
| `tvquoumw` Phase 1a confirmed from CBMC's source | Records that job `20261106-194328` passed: in CBMC 6.11.0's source, "Runtime Post-process" is timed inside "Runtime Solver", as `phases.rs` now assumes. | Pipeline job, passed. |
| `xtkwolst` **Phase 2b**: benchmark runs every staging policy *(verification pending)* | `lib/benchmark/run.py --jbmc-staging` runs each JBMC case once per policy. Auto's fallback is rerun under the other policies only where it actually ran. Each run records its witness size. `RESULTS.md` gets a section comparing the policies, with proofs and counterexamples kept apart. | `test_run.py` 26 pass (5 new). The old results render to the committed page byte for byte. The full measurement is job `-201041`. |
| `svvrpymr` **Phase 3**: JBMC lets runtime exceptions past their handlers *(verification pending)* | JBMC's counterexamples to `caught/1` and `nestedHandler/1` didn't reproduce on the JVM. Running JBMC on those cases and variants of them found two causes. (1) A JBMC defect: when a method returns an expression from inside a `try`, JBMC places that expression's check after the handler's range ends. (2) This repository's JDK stub classes have no superclass, so `catch (RuntimeException)` misses its subclasses. Both causes also produced **false proofs under strict**. The preflight in `jbmc_gaps.rs` now detects both shapes, and a JBMC proof that reaches one is refused under every `--gaps` mode. Three new corpus cases were added. | A unit test over 8 shapes, which fails with detection disabled. End to end on the real JBMC, both false proofs are now refused. Lib 157 and the other conformance tests pass. Integration tests and conformance under `jbmc`/`auto`/`--confirm` are in job `-203452`. |
| `xrrrwlrm` **Phase 4a**: the 41 recorded JBMC examples under strict on both engines *(verification pending)* | Job `-204220` runs `build.py` on scratch copies of the 41 examples, once with `--engine jbmc` and once with `native`, then compares the two. `examples/` itself is not modified. `gap_table.py` rows now show engine, checker, expectation, the problem and whether the refusal is a JBMC defect. A new `--compare A B` lists obligations whose status differs. | `test_gap_table.py` passes, with a new test. A plan-only check gives `--engine native --gaps strict` for all 41, keeping `--unwind 32` on the four Crosscut B9s. |

## Verification jobs

None failed. One is running and three are pending:

- **Running:** `20261106-201041`, the benchmark under the three staging policies (2b). It decides 2c.
- **Pending:** `20261106-203452`, the Phase 3 integration tests and conformance under `jbmc`, `auto` and `auto --confirm`.
- **Pending:** `20261106-204220`, the 41 examples on both engines (4a).
- **Pending, not this stream's:** `20261106-203501`, the native stream's job for examples 071/013 and the JDK 25.0.5 contract library.

The run-verification agent needs to run and collect these; the loop picks up 2c, the Phase 3 triage and the 4a report once their results are in.

## `sync.py check`: what you need to judge before pushing

- **8 warnings, all for you to judge:**
  - 7 allow-list proposals wait on `python3 llm-dlc/tools/sync.py allow approve` in your terminal. They are the mangled MiniSat/CaDiCaL C++ symbol names, flagged as long tokens.
  - The same symbols show up as `long-token ×14` warnings in this session's seven logs. Approving the proposals clears those too.
- **16 errors, none in this branch:**
  - They are on changes from other workspaces' sessions (`63d80e44`, `2b3fe2be`, `b4d45e13`, `62264445`, `e47f34c2`). Examples are the native stream's Phase 5 models (`knlrwnqu`), its Phase 4b (`wnxlynrs`), and the runner's Bitwuzla/CBMC result commits.
  - Most read "session … has no manifest". `wtvowsos` also points at two logs its manifest doesn't list.
  - I checked: none of these changes is an ancestor of `@` here. They should clear when those sessions sync or merge, but do look at them before a push.

## Needs your input

- **Upstream JBMC report:** a report on cause 1 (the check placed after the handler) is drafted in `lib/tests/fixtures/jbmc-defects/README.md`. Filing it with CBMC/JBMC is your call; nothing was sent.
- **Cause 2 fix:** the stub classes need models of the JDK exception hierarchy. That belongs in `lib/models/`, which is the native stream's, so it is recorded for the reconcile loop.

## Also worth knowing

- **Conformance on cvm:** `the_corpus_agrees_with_the_jvm_on_the_tools_own_checker` fails with 12 disagreements. The contract library's records are from JDK 25.0.4.1, and cvm runs 25.0.5. This predates the run; job `-203501` (native stream) re-records on 25.0.5.
- **`test_build.py`:** `examples/tools/test_build.py` has 35 pre-existing errors: the tests read committed results in the format-2 layout as if they were the old format. Real `build.py` runs aren't affected. Noted for the reconcile loop.
- **For 2c:** under `--engine auto`, a staged JBMC fallback whose two preliminary stages time out leaves the full range no time. Job `-201041` measures this.
- **Out-of-date brief:** in 2b, the brief asks only for the JBMC cases under all three policies. The job also measures auto's fallback under each, because 2c's default covers the fallback too. This is noted in the 2b commit message.

Ended 2026-11-06 20:44:52 after 6 cycle(s): the session decided the work was done.
