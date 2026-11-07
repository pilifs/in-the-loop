# Feature loop: engine-priorities-jbmc

Started 2026-11-06 22:29:52 UTC, no limit on cycles, session 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573, claude-opus-5-5 at high effort, after change xrrrwlrmqqputoknupzooswuqmtlrzyv.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'xrrrwlrmqqputoknupzooswuqmtlrzyv..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md` at sha256 4b2f54d4789ec8e4eab1b37b1dbe2d0b0463b1e82d9048d770cc0d8fab4f001f.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

- cycle 1, 2026-11-06 22:47:41, `pxqzmomtzsxy`: JBMC right-shifts by the whole distance: the preflight names an unmasked shift and refuses a JBMC proof through one
  - decided to continue: The loop should go on. This run has committed one step, the `unmasked-shift` guard, and all three jobs it was waiting on have been collected. Three steps remain that need only my own work: 2c, deciding JBMC's staging default from job `-201041`, which is a core Phase 2 step; triaging the Phase 3 job `-203452`; and fixing the result schema that rejects `stated.checker.sat`, then resubmitting 4a. None of them waits on a job or on the user, and Progress says `Status: working`.
- cycle 2, 2026-11-06 22:56:28, `wvkxpmzxuunt`: JBMC searches the full range alone by default, on benchmark job 20261106-201041's evidence
  - decided to continue: The loop should go on. This run has made two commits, the `unmasked-shift` guard and step 2c, so Phases 1 and 2, the core of this stream, are done. Two steps that need only my own work are still open: triaging the Phase 3 job `-203452` (the `Pricing#total` timeout and the 12 `auto --confirm` disagreements), and fixing the examples' result schema so it accepts `stated.checker.sat`, then resubmitting the 4a job. Neither waits on a job or on the user.
- cycle 3, 2026-11-06 23:14:38, `xzvyuwxptsny`: Under --confirm, a JBMC refutation through a named defect, whose witness does not reproduce, is no verdict; job 20261106-203452 triaged (verification pending)
  - decided to continue: The loop should go on. This run has three commits: the unmasked-shift guard, the `full-range` default (2c), and the `--confirm` fix that came out of triaging job `-203452`. Its rerun is queued as `-231317`. One step still needs only my own work: Phase 4a's job `-204220` failed because the examples' result schema doesn't allow the solver record (`stated.checker.sat`), so I need to fix the schema and resubmit the 41-example job. That doesn't wait on a job or on you.
- cycle 4, 2026-11-06 23:19:21, `tokyzslsyxoz`: The examples' result schema allows the statement's SAT solver record; 4a's job rerun (verification pending)
  - decided to stop: The loop should stop for now: everything left in this stream waits on two jobs. This run made four commits: the unmasked-shift guard, the `full-range` default from Phase 2c, the `--confirm` fix that came out of triaging job `-203452`, and the result-schema fix with Phase 4a's job resubmitted. That finishes Phases 1 and 2, and leaves Phases 3 and 4a needing only the results of jobs `20261106-231317` and `20261106-231837`. Progress already ends with `waiting on jobs 20261106-231317 20261106-231837`, so `run-streams.sh` will start the loop again once those results are collected.

## Summary

# engines-jbmc loop: summary of this run (4 cycles, 4 commits)

Everything this stream can do on its own is done. Phases 1 and 2 are finished. Phases 3 and 4a are waiting on one running job and one queued job. Status line: `waiting on jobs 20261106-231317 20261106-231837`.

## Commits

### 1. `pxqzmomt` (de817928): JBMC's unmasked right shift is now a named defect
- **What it adds:**
  - **The bug:** JBMC 6.11.0 masks the distance of left shifts but not of right shifts (`>>`, `>>>`, on int and long). A distance outside 0..31 (or 0..63 for long) therefore gives a different result from the JVM.
  - **Wrong answers it caused:**
    - it "proved" `x >> s == 0 || == -1` where `s == 33`, but on the JVM `4 >> 33 == 2`;
    - it "proved" `x >>> s == 0` where `s == 32`;
    - it reported a counterexample to `conformance/shiftRight/2` that doesn't reproduce.
  - **The guard:** `lib/src/jbmc_gaps.rs` gains a third defect, `unmasked-shift`. A JBMC proof through one is refused under every `--gaps` mode. Counterexamples are still replayed.
  - **Cost:** the rule is broad. One correct JBMC proof (`shiftRight/1`) is now refused, though `auto` still proves it with the own checker.
  - **Corpus:** gains `shiftRight/3` and `shiftUnsigned/3` (the two false proofs). `lib/benchmark/conformance.json` is regenerated (98 claims).
  - **Upstream:** a draft upstream bug report is in `lib/tests/fixtures/jbmc-defects/README.md`. It has not been filed.
- **How it was verified:**
  - The preflight fixture test covers 3 new defects and 3 neighbours, and fails with the detection turned off.
  - On the real JBMC both false proofs are now refused, and `auto` gives the violation.
  - Lib (157), integration (63), skill, `test_run.py` and `test_gap_table.py` pass.
  - Conformance fails only on its 12 known disagreements. These come from the contract records being from JDK 25.0.4.1 while the machine runs 25.0.5.

### 2. `wvkxpmzx` (11039262): JBMC now searches the full range by default (Phase 2c)
- **What it adds:**
  - **The evidence:** benchmark job `20261106-201041` compared JBMC's three staging policies.
    - Under strict, all three proved the same 54 of 65 claims. Total time was 654 s for staged, 575 s for full-range and 588 s for tight.
    - The hard proofs took about half the time without stages.
    - Counterexamples took 9 s instead of 27 s, and none of the shrunk witnesses was larger.
  - **The change:** `full-range` is now the default for `--jbmc-staging`, `Options::new` and `lib/benchmark/run.py`. The own checker keeps its stages.
  - **Docs:** the READMEs record the job's figures.
- **How it was verified:**
  - Lib, integration and skill tests pass.
  - Three integration tests now assert the full range, with the same witnesses as before.
  - Conformance fails only on the 12 known JDK disagreements.

### 3. `xzvyuwxp` (14607996): a `--confirm` fix, from triaging job `20261106-203452` (verification pending)
- **What it adds:**
  - **The problem:** the job had 12 disagreements under `--confirm`. In each, the own checker proved the claim and JBMC refuted it through a known defect (`return-past-handler` or `stubbed-handler`), with a witness that doesn't reproduce.
  - **The fix:** such a refutation is now "no verdict", and the own checker's proof stands, unconfirmed, with the defect named. A witness that does reproduce is still a disagreement.
  - **Correction to Progress:** the job's integration-step failure wasn't JBMC. It was the own checker timing out on `fixtures.Pricing#total`; see "Other things for your attention" below.
- **How it was verified:**
  - On the real JBMC, `caught`, `caughtAsRuntime` and `nestedHandler` are now "verified, not confirmed", naming the defect.
  - A new stand-in-JBMC test fails with the fix turned off.
  - Lib (157) and conformance pass, apart from the 12 known JDK disagreements.
- **Rerun:** as job `20261106-231317`.

### 4. `tokyzsls` (835d5f28): the result schema allows the SAT solver record (verification pending)
- **What it adds:**
  - **The problem:** Phase 4a's job `20261106-204220` failed at its first example. `examples/schema/result.schema.json` rejected Phase 1b's `stated.checker.sat` field.
  - **The fix:** the schema now allows exactly that shape: `solver`, `version` (or null), `source` and `configuration`.
- **How it was verified:**
  - Real `sat` records from both engines, spliced into the 14 committed results that carry a statement, pass `build.py`'s full validation. A record with an extra field is rejected.
  - Three real statements validate against `$defs/statement`.
  - `test_build.py` has the same 35 pre-existing errors (`KeyError: 'verdict'`) before and after the change.
- **Rerun:** as job `20261106-231837`.

## Verification jobs
| Job | State | What it checks |
|---|---|---|
| `20261106-231317` | **running** since 23:14 UTC | The rerun of `-203452`: the corpus under JBMC, `auto` and `--confirm`, plus the integration tests. It also measures the unmasked-shift guard and the full-range default. |
| `20261106-231837` | **pending** (2 CPU, 2 GiB, about 25 min) | The rerun of 4a: the 41 recorded JBMC examples under strict on both engines, tabulated per obligation. |

Nothing is failed and uncollected. The jobs this run collected and acted on were `-201041` (passed), `-203452` (failed, triaged in commit 3) and `-204220` (failed, fixed in commit 4).

## `sync.py check` warnings to judge before pushing
- **7 allow-list proposals** are waiting for your approval (`python3 llm-dlc/tools/sync.py allow approve`). None were added by this run.
- **11 logs from this session** (`7b8a1d3b…`) each have **14 long-token findings**. They look like mangled C++ symbols (`_ZZ…`, 45–107 characters) from JBMC/CBMC output. Check them with `sync.py review show` and decide whether to allow them.
- **25 errors**, all in other workspaces' changes: none of the 18 change ids is in this workspace's history. Most are "session … has no manifest". `wtvowsostpzw` ("Record verification results: Bitwuzla build fails its smoke test (VF-003)") also points at two logs its manifest doesn't list. These belong to the sessions that made those changes, but `check` will report them until those changes are fixed.

## Deferred: needs your decision
- **The upstream JBMC bug report** (unmasked right shift) is drafted in `lib/tests/fixtures/jbmc-defects/README.md`, with a reproducer checked on JBMC and the JVM. Filing it is outward-facing, so it waits for you to decide whether and where.

## Other things for your attention
- **The own checker is timing-dependent** (this is `lib/src/bmc/`, the native stream's area, so I didn't touch it). Its branch probes are budgeted by wall-clock time, so its path order depends on timing. On cvm, 2 of 8 identical runs of the `fixtures.Pricing#total` regression proof hit the 40 s limit, where the others took 4 s. A reproducer is in Progress for the native stream and the reconcile loop.
- **Shared files changed** (also named in Progress):
  - `lib/tests/conformance.rs`
  - `lib/src/equivalence.rs`
  - `lib/src/property.rs`
  - `lib/README.md`
  - `lib/benchmark/README.md`
  - `lib/benchmark/run.py`
  - `examples/schema/result.schema.json`
- **When the two jobs come back:** their results go under Phases 3 and 4a. 4a's tables go to the reconcile loop's Phase 4c as they stand.

`@` is empty. Nothing was pushed.

Ended 2026-11-06 23:20:44 after 4 cycle(s): the session decided the work was done.
