# Feature loop: cleanup-examples

Started 2026-11-07 18:31:05 UTC, no limit on cycles, session b65d132b-4eb4-46fd-8556-f4cba3311ad1, claude-opus-5-5 at high effort, after change svoznurqyptvmyyrrmtnommqywmmpyoo.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/cleanup-examples.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'svoznurqyptvmyyrrmtnommqywmmpyoo..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/cleanup-examples.md` at sha256 9937654e4a839b19da3481369c642019b4a7f93e7d5bf5318795d59103393aea.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when every item is closed by its check or deferred by the timebox. Stop with `blocked: ...` when what is left needs the user and is recorded under Progress. Don't take on work beyond your items: anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-07 18:35:09, `xmsmzwoyoklp`: VF-014's comparison queued on the two isolated runs, and VF-002's 147 and 148 deferred by the timebox after a third defect in build.py's contract staging (verification pending)
  - decided to continue: The loop should go on, because E2 still has one step the stream can do by its own work. That step is to queue the job that records a fresh `lib/benchmark/results.json` at the current commit, which the brief makes a separate job from the comparison. Everything else is either closed (VF-016, VF-017, E3, E4), deferred by the timebox (VF-002's 147 and 148), or waiting on the comparison job `20261107-183328-…`.
- cycle 2, 2026-11-07 18:37:49, `yztkltwvnkmy`: VF-014's fresh lib/benchmark/results.json queued at the current engine, all three engines, after the isolated comparison (verification pending)
  - decided to stop: The loop should stop: everything left waits on jobs. E3, E4, VF-016 and VF-017 are closed, VF-002's 147 and 148 are deferred by the timebox (149 passed), and both of E2's remaining steps are queued: the comparison `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm`, and the fresh recording `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso`. Progress's last line already reads `waiting on jobs` with those two ids, so `run-streams.sh` can rerun the stream once they're collected.

## Summary

# Cleanup-examples stream: run summary (2 cycles)

## Commits this run

**`xmsmzwoy` (7315cda): VF-014's comparison queued; VF-002's 147 and 148 deferred by the timebox (verification pending)**
- **E2 (VF-014):** the two isolated benchmark runs, at H1's parent and at H1, both passed. This commit adds job `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm`, which compares the two runs. It reuses job `20261107-041414`'s step-2 comparison script unchanged, and checks each input file against the sha256 its run recorded. I tried it inline on the same files first (0.2 s): 557 runs, 24 new cases, 0 verdicts changed.
- **E1:** VF-016 passed: 160 is verified with `lastAfter` shared, and 161 is a violation with nothing shared. VF-002's 149 passed.
  - 147 and 148 failed in `stage_contracts` (`build.py:432`). Since `myrqmxqq`, `run()` gives each runner the attempt directory as its folder, so it looks for the example's `gaps.contracts` there.
  - That was VF-002's second failure in a row, so the timebox defers 147 and 148. The finding and the cost of another attempt are in the brief's Progress and in both examples' notes.
  - **Checked by:** `examples/index.json` was re-rendered, and `test_build.py`'s 189 tests pass.

**`yztkltwv` (c9995ae): a fresh `lib/benchmark/results.json` queued (verification pending)**
- VF-014 found the committed recording stale. It was written at `26227917`, before the own checker had class initializers and before H1's conformance cases existed.
- This commit adds job `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso`. It runs the same step as `20261106-201041`: all three engines (native, jbmc, auto) under every gap mode and staging policy. Its outputs are `results.json` and `RESULTS.md`, which `collect` will put in place of the committed ones.
- **Checked by:** `pipeline.py validate` passes, and the default workspace's copies of both files match this commit's sha256, so `collect` can apply them.

## Verification jobs

| Job | State |
|---|---|
| `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm` | **Passed, not yet collected.** Same result as the inline try: 557 runs, 24 new (the `swaps`, `swapsOrNull` and `swapsThenNull` conformance cases), 0 verdicts changed, 0 formulas grown, 0 paths or merges changed. This closes VF-014 once collected. |
| `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso` | **Pending** (2 CPU, 4.5 GiB, about 2 h). |

`submit` warned that no runner can take this job's 6G limit. That warning came from this workspace's base `pipeline.toml`. The runner in the default workspace allows 14G per job, so the job can run.

If this job exits 1 on JBMC or auto (a false success, a false alarm, or a JVM disagreement), that is a finding for the jbmc stream, not this one.

No job from this stream failed this run.

## `sync.py check`

**0 warnings to judge.** It does report **16 errors**, and none come from this run's commits:
- **14 "has no manifest" errors:** commits from other sessions (`2324d402`, `a8cc612f`, `ed84ffdf`, `367bd874`) whose manifests aren't in this workspace.
- **`syqpoxom`:** points at log `747e1075ca6b`, which its manifest doesn't list.
- **Planning session `2df7775c`:** its log `3f768f3bb246` is neither stored locally nor uploaded.

These should go away when the streams are merged. Check them again after that, before pushing.

## Needs your attention

- **Collect both jobs** with `/run-verification`. After that, Progress can record VF-014 as closed, note whether the fresh `results.json` was applied, and set the stream's status to `done`.
- **VF-002's 147 and 148:** these need your decision. A third attempt means fixing how `build.py` stages contracts so it finds `gaps.contracts` in the example's folder, not in the attempt directory. The brief's Progress has the cost estimate.
- **Integration merge conflict:** the integration check hit a conflict in the generated files and `llm-dlc/README.md`. I left it for the reconcile step.
- **Prompt points at the wrong brief:** this cycle's prompt named the default workspace's copy of `cleanup-examples.md`, whose Progress is older than this stream. I updated this workspace's copy. Point future runs at it, or bring it over when merging.

Ended 2026-11-07 18:39:15 after 2 cycle(s): the session decided the work was done.
