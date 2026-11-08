# Feature loop: application-core-reuse

Started 2026-11-08 11:52:01 UTC, no limit on cycles, session aa238023-596d-49bd-8039-52502ec096fc, claude-opus-5-5 at high effort, after change uxqrooysuqkqumvqylkszvpzoqqkzlwz.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'uxqrooysuqkqumvqylkszvpzoqqkzlwz..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md` at sha256 bdc29a515d2ccf1cbd3302bbc25e91090a5d916ec533fb5c1ec1e21a3858247c.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when R1, R2, R3's justified outcome and your share of the combined acceptance pass, or each is deferred by the timebox with the finding. R4 may be left out without changing that. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-08 11:55:01, `tvrqpuswknzk`: application-core reuse J4: the cost report's figures with all five cases, read from job 20261108-114325; the stream is done
  - decided to stop: This run's one commit, `tvrqpusw`, read the J4 job's release figures into Progress. It closed the last step this stream could do on its own: R1, R2, R3's justified cache, J3 and J4's five-case report all pass. R4 is left out, as the brief allows. The stream's brief already ends with `- Status: done`. What remains belongs to the main loop at the merge: J4's rerun on the merged revision, the R2 contract row reaching `fee`'s summary, and the interface requests in other owners' files.
  - the stop left the brief's status working, or uncommitted; session aa238023-596d-49bd-8039-52502ec096fc needs attention

## Summary

# Feature-loop run summary: application-core reuse stream (1 cycle)

## What this run committed

**`tvrqpusw` (dbb48a1d): application-core reuse J4: the cost report's figures with all five cases, read from job 20261108-114325; the stream is done**

- **Brief, stream copy** (`llm-dlc/loops/application-core-reuse.md`): a new Progress entry records the results of J4's job `20261108-114325`.
  - The job passed at `283aa75d` on vm-1 in 3m37s, peaking at 1.7 GiB. The runner committed its results in the default workspace as `tvwtmzkx`.
  - Median times for the six cost-benchmark scenarios:

    | Scenario | Reused / proved | In process | As a process | Solving | With javac |
    |---|---|---|---|---|---|
    | Cold | 0 / 5 | 71.5 ms | 127.0 ms | 50.0 ms | 546 ms |
    | Unchanged rerun | 5 / 0 | 9.5 ms | 62.5 ms | 0 | 481 ms |
    | Unrelated edit | 5 / 0 | 8.9 ms | 64.4 ms | 0 | 461 ms |
    | Safe helper rewrite | 1 / 4 | 79.2 ms | 138.7 ms | 59.0 ms | 534 ms |
    | Defect, cold | 0 / 5 | 1450.7 ms | 1687.6 ms | 1364.0 ms | 2085 ms |
    | Defect, rerun | 5 / 0 | 31.7 ms | 83.7 ms | 0 | 482 ms |

  - The JDK image's table of classes costs 8.63 ms to build and 0.07 ms once shared. Hashing the binary costs 37.7 ms.
  - The entry separates the three kinds of reuse:
    - `total` is proved again because the new `discount` proof's key is part of its claim;
    - `discount` itself is proved twice;
    - the route is proved again because its effect proof contains the helper's body.
  - javac takes 74–87% of each scenario's time, except the defect's cold run.
  - The stream is marked `- Status: done`. R1, R2, R3, J3 and J4 are finished; R4 is left out, as the brief allows.
- **`lib/README.md`**: two new sentences say what the last two cases show:
  - an unrelated edit is 5 exact hits (64 ms, against the unchanged rerun's 63 ms);
  - a safe helper rewrite proves 4 of 5 methods again (139 ms, against cold's 127 ms);
  - "Helper evidence is reused by key, not made cheaper to obtain." The paragraph links to `tests/fixtures/preparation/README.md`.
- **How it was verified:** every figure was read from J4's committed result and reports, and the percentages were recomputed. This commit adds no code, so it ran no tests and submitted no job.

## Verification jobs

- **None of this stream's jobs is pending or failed.** In the default workspace, where the runner works, the queue is empty: 0 pending, 0 running, 0 finished but not collected.
- **This workspace's own `pipeline.py status` lists 12 jobs as pending.** They aren't: the runner collected their results in the default workspace, and those results reach this branch only at the merge. The 12 are:
  - this stream's three R3 and J4 jobs (`060410`, `063259`, `114325`), all passed and read into Progress;
  - jobs from the objects and values streams;
  - the VF-023 probes.
- **J4 should run again on the merged revision**, because its figures were measured on this branch alone.

## `sync.py check`

- **0 warnings** need your judgement.
- **51 "has no manifest" ERRORs.** They come from older sessions in other workspaces, such as the runner's. None is from this session and none is an ancestor of this branch's `@`. I left them alone.

## Needs your attention

1. **The brief has two copies, and they disagree.**
   - This stream's copy says `done`. The copy in the default workspace, which this already-running `feature-loop.sh` reads, still says `working`.
   - I didn't edit the default copy. That would mean committing in the workspace where the runner and the main loop commit, and the merge would then have to reconcile two contradictory Progress sections.
   - `feature-loop.sh` will probably exit 1 with "needs attention". You can ignore that: `run-streams.sh` reads the stream's copy, finds `done`, and counts the stream finished. Loops started after `unwrvwqw` read the stream's own copy, so this won't recur.
2. **Left for the main loop at the merge** (recorded in Progress):
   - Recheck the R2 contract row in `lib/tests/application_core.rs` (`quotes.QuoteService#fee`). For now it accepts a refusal from either the objects or the reuse stream, because the objects stream's `construction::receiver` work isn't merged yet.
   - Rerun J4.
   - Three interface changes the stream asked for:
     - `property_store` should take `&mut Outcome`;
     - `property::Outcome` should get a `reuse` field;
     - the stale "Refused until…" docs in `main.rs` and `property::run` should be removed.
3. **Two items in Progress for review:**
   - Effect proofs don't use the helpers' proof results, so rewriting a helper re-proves every route that calls it.
   - R4 was left out on purpose.

Nothing was pushed.

Stopped 2026-11-08 11:57:37 after 1 cycle(s): the session decided to stop, but the brief's status still says working; session aa238023-596d-49bd-8039-52502ec096fc needs attention.
