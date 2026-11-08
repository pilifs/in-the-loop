# Feature loop: stub-reachability

Started 2026-11-08 00:56:04 UTC, no limit on cycles, session 807d6ed2-a98d-4f93-8dbb-28d70736eff7, claude-opus-5-5 at high effort, after change qkrlyslvusqmnupntktnoqlxnruxrqoq.

> Work on the brief in `llm-dlc/loops/stub-reachability.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qkrlyslvusqmnupntktnoqlxnruxrqoq..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/stub-reachability.md` at sha256 1fc31a8d3c1845683538a4753b7b863950fd727473d55c34ab367b85cb10b697.

After each commit the session decides whether to go on:

> Stop with `done` once step 4's criterion is met. Stop with `blocked: ...` when step 2 finds no method that is both correct and cheap, or the user is needed. Set the status to `working` when the cleanup merge is committed, before starting. Don't take on other gaps or models.

## Commits

- cycle 1, 2026-11-08 00:57:50, `mwzqmlswqxyq`: Stub reachability, step 2: the probe at the call site is chosen, since JBMC 6.11 has no --cover
  - decided to continue: This run has made one commit (`mwzqmlsw`), which settled step 2: the probe at the call site is correct on both the case and the control, and cheaper than the proof, so the `blocked:` condition isn't met. Step 4's criterion is still far off: step 3 and VF-015's resubmitted job are both outstanding, and nothing needs the user. Step 3 is code and unit tests in `jbmc_gaps.rs` that can run inline without waiting on any job, so the next cycle has real work to do.
- cycle 2, 2026-11-08 01:12:27, `xlnrlwxsrswq`: Stub reachability, step 3: the gap preflight asks JBMC's solver, by a probe at each call site, whether a path reaches a stub its symbolic execution enters
  - decided to continue: This run has committed steps 2 and 3: the probe was chosen on the job's evidence, then built into the preflight, and its reproducer fails without the new step and passes with it. Step 4's criterion isn't met yet: VF-015's job still has to be resubmitted and pass, and the guard jobs still have to be submitted. Nothing is blocked or needs the user, since step 4 is just queuing those jobs, which the next cycle can do now.
- cycle 3, 2026-11-08 01:17:03, `wvztqlwrlulx`: Stub reachability, step 4: VF-015's job resubmitted and a guard job for the gap preflight's probe (verification pending)
  - decided to stop: I'd stop the loop here. This run has committed steps 2, 3 and 4, and step 4's criterion isn't met yet. But all that's left is waiting on the two queued jobs (`20261108-011411-…` and `20261108-011441-…`), which the verification agent runs and collects, so another cycle now would have nothing to do. Neither `done` nor `blocked:` applies; Progress ends with `Status: waiting on jobs` and both ids, and the brief says a single loop like this one is rerun by hand once their results are collected.

## Summary

# Stub reachability loop: summary of this run (3 cycles, 2026-11-08)

The loop is waiting on two verification jobs. Steps 2 and 3 of `llm-dlc/loops/stub-reachability.md` are done, and step 4's jobs are queued. Step 4's criterion, that VF-015's proof stands with no stub left out of the gaps wrongly, can only be decided once both jobs have run and been collected. Nothing in the run is blocked, and nothing needs credentials.

## Commits

### `mwzqmlsw`: Step 2, choosing how JBMC's solver decides whether a stub is reached
- **What it adds:** step 1's experiment job (`20261107-233000-…`) passed, and this commit records its results and the method chosen from them in Progress. No code changed.
  - `--cover location` doesn't work: JBMC 6.11 rejects the option as a usage error. The brief was wrong to say JBMC has it; the mention in a help line is CBMC's text. That correction is in the commit message, as the loop rules require.
  - A probe assertion placed at the stub's call site gave the right answer on both runs. It holds under `ch == 1632`, and it fails without that assumption. It took 92 ms, against 129 ms for the proof.
  - Progress also records the rules step 3 had to keep. A probe only counts when the run's unwinding assertions hold. A probe must not cut the path it sits on. A stub leaves the gaps only when every one of its call sites' probes holds.
- **Verified by:** reading the job's log and outputs.

### `xlnrlwxs`: Step 3, the gap preflight asks JBMC's solver whether a stub is reached
- **What it adds:**
  - **The bug:** JBMC's symbolic execution keeps a branch even when only the solver can rule it out. So the preflight in `lib/src/jbmc_gaps.rs` counted a stub as entered when an `--assume` made it unreachable. That is VF-015's case: the `String.format` stub on `toDigit`'s exception path.
  - **The probe:** the preflight now makes one more JBMC run for the stubs symbolic execution still enters, with the same bounds and solver. Each call site of those stubs is rewritten to call a `jvmcontract.StubProbe` method. That method fails its own assertion on a nondeterministic branch and otherwise makes the original call, so no path is cut. The rewrite uses a new `shared::redirect_calls_at`.
  - **When a stub leaves the gaps:** only when all of its probes hold and every unwinding assertion holds. The stub stays a gap if the run times out, gives no verdict or can't be read, or if any call site can't be probed.
  - **Where it's recorded and documented:** the result is in `Found::solved` and `Preflight::probes`, and the note says why the stub was left out. The module doc and `lib/README.md`'s gap section describe the change.
- **Verified inline:**
  - **Unit tests** on step 2's recorded probe output. VF-015's case reads as unreached. These cases still count the stub as a gap: the control, a missing probe, one failing probe of two, a failing unwinding assertion, no verdict, and a timeout.
  - **Placement tests:** two stubs called in a row, a call site whose instruction calls a different method, and a call site with no bytecode index.
  - **A live JBMC reproducer** that takes milliseconds: `a_stub_behind_a_condition_only_the_solver_decides_is_no_gap`. It fails with the old behaviour and passes with the new.
  - The unit suite passes (215 tests), and every target compiles.
  - The integration and conformance gap tests run JBMC proofs, so they were left to step 4's guard job instead of being run inline.

### `wvztqlwr`: Step 4, two jobs queued (verification pending)
- **What it adds:**
  - `20261108-011411-vf-015-example-109-revisited-hex-todigit` reruns VF-015's job with its steps unchanged. Under `--gaps strict` it should now prove `Hex#toDigit --assume 'ch == 1632'` with no JBMC gap. If it passes, VF-015 is closed. This is the cleanup native stream's N3, its second and last attempt under the timebox. `pipeline.py resubmit` keeps the old title, so I edited the title and description in the job file afterwards. The steps were not touched.
  - `20261108-011441-stub-reachability-step-4-no-stub-a-proof` checks that the probe doesn't wrongly drop a stub a proof really does enter. It runs:
    - the `jbmc_gaps` unit tests, including the live ones;
    - eight gap tests from `lib/tests/integration.rs` (I checked the name filters inline with `--list`);
    - the conformance corpus under `--engine jbmc` and `auto`.
- **Verified:** `pipeline.py validate` reported 0 problems, and the commit reported 0 errors and 0 warnings.

## Verification jobs

| Job | State |
|---|---|
| `20261108-011411-vf-015-example-109-revisited-hex-todigit` | **running**, started 2026-11-08 01:17 UTC |
| `20261108-011441-stub-reachability-step-4-no-stub-a-proof` | **pending**: 2 CPUs, 3 GiB, about 40 minutes |

None has failed. All 284 other jobs are collected.

What happens next depends on the results, as Progress records:
- **Both pass:** close VF-015, and the loop ends with `done`.
- **VF-015's step 4 fails on `StandardCharsets.UTF_8`:** fixing that in the interpreter is the next item.
- **The guard job fails:** fix the probe.

## Before pushing
- `sync.py check` shows **0 errors and 0 warnings** across 63 sessions. Its 134 notes need no action.
- The three commits haven't been pushed. When you want to publish them, run `python3 llm-dlc/tools/sync.py push --bookmark main` or `/publish`.

## Needs your input
- **Your decisions:** none. Nothing was deferred for credentials or a decision.
- **One brief claim was wrong:** the brief says JBMC has `--cover`, and it doesn't. I couldn't fix that, because the loop rules only let me edit Progress, so the correction is in `mwzqmlsw`'s message instead. You may want to fix the brief's text.
- **When the jobs finish:** after `/run-verification` collects them, rerun the stub-reachability loop by hand to read the results and act on them.

Ended 2026-11-08 01:18:18 after 3 cycle(s): the session decided the work was done.
