# Feature loop: stub-reachability

Started 2026-11-08 01:38:19 UTC, no limit on cycles, session 807d6ed2-a98d-4f93-8dbb-28d70736eff7, claude-opus-5-5 at high effort, after change pktlkzsptxlsyuvtmtvuoosqozyqwpnu.

> Work on the brief in `llm-dlc/loops/stub-reachability.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'pktlkzsptxlsyuvtmtvuoosqozyqwpnu..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/stub-reachability.md` at sha256 1fc31a8d3c1845683538a4753b7b863950fd727473d55c34ab367b85cb10b697.

After each commit the session decides whether to go on:

> Stop with `done` once step 4's criterion is met. Stop with `blocked: ...` when step 2 finds no method that is both correct and cheap, or the user is needed. Set the status to `working` when the cleanup merge is committed, before starting. Don't take on other gaps or models.

## Commits

- cycle 1, 2026-11-08 01:41:03, `umwtoqpkokwr`: Stub reachability, step 4 done: the guard passed, and VF-015 is deferred by the timebox on an uncaught checked exception in the equivalence harness
  - decided to stop: The loop should stop with `done`, because step 4's criterion is met: the guard job passed, and VF-015 is deferred by the timebox after N3's second failure in a row, with the finding recorded. That was committed as `umwtoqpk`, and Progress ends `Status: done`. What's left, catching declared checked exceptions in the equivalence harness, is outside this brief, and the timebox rules out a third attempt in this loop.

## Summary

# Stub reachability run, 2026-11-08: the loop stopped with `done` after one cycle

## What this run committed

This run made one commit. `jj log -r 'pktlkzsp..@-'` lists only it, and `@` is empty.

### `umwtoqpk`: Stub reachability, step 4 done

**What it adds:** no code. It records the outcome of step 4's two jobs, which another session had collected in `pktlkzsp`:

- **Guard job** `20261108-011441-stub-reachability-step-4-no-stub-a-proof`: **passed.** Every check passed:
  - the gap preflight's unit tests;
  - the eight gap tests in `lib/tests/integration.rs`;
  - the conformance corpus under `--engine jbmc` and `auto`.

  So the probe at each call site (`jvmcontract.StubProbe.p<k>`, added in step 3) doesn't drop any stub that a proof actually enters.
- **VF-015's job** `20261108-011411-vf-015-example-109-revisited-hex-todigit`: **failed, but not on stubs.**
  - Step 3 now passes. That is the old `toDigit` under `--assume 'ch == 1632'` with `--gaps strict`, and it shows `String.format` as a stub the solver proves is never reached. This is what the brief set out to achieve.
  - The job then fails at step 5, the ASCII equivalence, with `EquivalenceHarness.check:(CI)V.1`.

**The cause, found by reading the job's JBMC traces:**
- That property is JBMC's "no uncaught exception" check.
- On a non-hex ASCII character, the old `toDigit` throws `DecoderException`, which is a checked exception.
- The equivalence harness only catches unchecked exceptions (`RuntimeException`) and `Error` (`harness::EXCEPTIONS` in `lib/src/harness/mod.rs`), so the exception escapes.
- Step 4's pass was meaningless: `test $? -eq 1` also accepted "cannot be verified".
- The throwing-initializer notes that were suspected when the result was collected are not the cause.

This is VF-015's second failure in a row, so the timebox defers it. The commit records the finding and what a further attempt would cost in three places:
- the brief's Progress, which now ends `Status: done`;
- a "Triaged 2026-11-08" bullet on VF-015 in `verification/findings.md` (the entry stays open);
- example 109's notes in its `example.json`.

**How it was verified:** nothing needed a new run, since the triage only read collected logs (`work-ascii` and `work-change` `jbmc.log`). The commit's check gave 0 errors and 0 warnings.

## Verification jobs

- **Pending or running:** none (`pending: 0`, `running: 0`, `finished, not collected: 0`).
- **Failed, from this brief:** `20261108-011411-vf-015-example-109-revisited-hex-todigit`, at step 5, as described above. It is deferred, not to be resubmitted as it stands.
- **Older failures:** `report` still shows 81 failed jobs out of 286, under "Needs attention". None of them comes from this run, and none was touched.

## Warnings from `sync.py check`

`check` reports 0 errors and 0 warnings across 64 sessions. Its 135 notes need no action, and there is nothing for you to judge before pushing.

## Decisions for you

1. **Whether to fix VF-015.** It is deferred by the timebox and outside this brief, so it needs your decision. A further attempt needs:
   - the equivalence harness to catch the method's declared `throws` classes (and then `java.lang.Exception`), so that the old and new versions throwing a checked exception count as an observable outcome rather than an uncaught one;
   - the job's step 4 to check that a change was actually found, instead of accepting any exit code 1;
   - then a resubmitted VF-015 job, from a new brief or work item.
2. **An outdated expectation in the brief.** Its plan expected VF-015's next failure to be the `StandardCharsets.UTF_8` replay (`lib/src/interp/natives.rs:373`), but that code path was never hit. I couldn't change it, because the loop only lets me edit Progress, so it is noted in the commit message instead. Correct or drop it if the brief will be reused.
3. **Pushing.** Nothing has been pushed. When you want to publish, run `python3 llm-dlc/tools/sync.py push --bookmark main` or `/publish`.

Ended 2026-11-08 01:42:15 after 1 cycle(s): the session decided the work was done.
