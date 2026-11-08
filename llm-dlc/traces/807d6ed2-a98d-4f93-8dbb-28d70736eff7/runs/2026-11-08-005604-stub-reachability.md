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
