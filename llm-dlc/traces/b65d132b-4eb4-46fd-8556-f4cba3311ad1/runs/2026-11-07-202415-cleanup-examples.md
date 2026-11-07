# Feature loop: cleanup-examples

Started 2026-11-07 20:24:15 UTC, no limit on cycles, session b65d132b-4eb4-46fd-8556-f4cba3311ad1, claude-opus-5-5 at high effort, after change yztkltwvnkmytxxsvltrqkzmoquxvzls.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/cleanup-examples.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'yztkltwvnkmytxxsvltrqkzmoquxvzls..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/cleanup-examples.md` at sha256 9937654e4a839b19da3481369c642019b4a7f93e7d5bf5318795d59103393aea.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when every item is closed by its check or deferred by the timebox. Stop with `blocked: ...` when what is left needs the user and is recorded under Progress. Don't take on work beyond your items: anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-07 20:25:36, `swopzxzurvsv`: VF-014 closed by the isolated comparison, and the fresh lib/benchmark/results.json applied on the default line: the examples stream is done
  - decided to stop: Every item is now either closed by its check or stopped by the two-failure limit. VF-014 closed when the isolated comparison passed, and the new benchmark recording was applied on the default line. VF-016, VF-017, VF-013, the foundations leftovers and VF-002's 149 were already closed, and VF-002's 147 and 148 were stopped by the limit. This run's one commit, `swopzxzu`, recorded that and set Progress to `Status: done`. No step is left that needs only this stream's own work, so by the loop-until rule the loop stops with `done`.

## Summary

# Cleanup-examples stream: run summary

This run made one commit, and the stream's status is now **done**. Every item is either closed by its check or was stopped after two failures in a row.

## Commit

**`swopzxzu`: VF-014 is closed and the new `lib/benchmark/results.json` is applied on the default line.**

It records the results of the two VF-014 jobs the previous run queued. Both passed, and both were collected in the default workspace's change `lmxwvplz`.

- **`20261107-183328` (the isolated comparison):** it compared H1's runs, each made with H1's own checker, against runs of H1's parent.
  - 557 runs, of which 24 are new: the swaps cases H1 added.
  - 0 verdicts changed, 0 formulas grew, and 0 paths or merges changed.
  - So H1 changed no verdict. The 8 changed verdicts that `20261107-041414` reported came from the old, out-of-date recording.
- **`20261107-183709` (the new recording):** it recorded native, jbmc and auto under every mode and staging policy, in 1h37m.
  - There was no false success and no false alarm.
  - `collect` applied `results.json` and `RESULTS.md`. The new file has 2829 runs; the old one had 1802.

I verified this by reading both jobs' reports with `pipeline.py report` and by counting the runs in the applied `results.json`. The commit only edits the brief's Progress, which now ends with `Status: done`.

## Verification jobs

None are pending or running, and none are finished but not collected. All 273 jobs are collected.

## `sync.py check`

It reports **0 warnings** to judge, so nothing needs your decision before a push.

It does report **22 errors**, and none of them come from this stream's commits:

- **20 errors:** commits from other sessions have no manifest in this workspace. The sessions are `2324d402`, `ed84ffdf`, `3da21514`, `a8cc612f` and `367bd874`, in commits such as `wpxntpty`, `lmxwvplz`, `sxqsorny` and `kmmoyzny`.
- **`syqpoxom` points at log `747e1075ca6b`**, which its manifest doesn't list.
- **Session `2df7775c` (the planning session):** its log `3f768f3bb246` is neither stored locally nor uploaded.

I expect these to clear when the streams are merged. If they are still there after the reconcile, look at them before pushing.

## Deferred: VF-002's examples 147 and 148

Both were stopped after two failures in a row, and nothing about them needs a credential or a decision from you.

- **The defect:** `stage_contracts` and `contracts_digest` read the example's `gaps.contracts` from the attempt directory instead of from the example's own folder (`examples/tools/build.py:432` and `:692`). This is the third defect found in `build.py`'s contract staging.
- **Suggested next attempt:**
  - Pass the example's folder to both functions.
  - Add a test in `test_build.py` that reproduces the bug.
  - Resubmit the two jobs, which take about 2 minutes each.

## Other things to note

- **Next full benchmark recording:** the new recording peaked at 6.0 GiB, which was its whole memory limit. The next full recording should get 6G of budget with an 8G limit.
- **The two workspaces hold different `results.json` files:** the new one is on the default line and the old one is still in this workspace. This branch doesn't touch the file, so the merge should take the new one without a conflict.
- **The prompt names the wrong copy of the brief:** the cycle prompt again pointed at the default workspace's `llm-dlc/loops/cleanup-examples.md`. That copy's Progress is empty and predates this stream; this workspace's copy is the one that was updated. The prompt may need fixing for later runs.
- **The integration check's merge conflict** is left for the reconcile in the main brief's loop.

Ended 2026-11-07 20:26:44 after 1 cycle(s): the session decided the work was done.
