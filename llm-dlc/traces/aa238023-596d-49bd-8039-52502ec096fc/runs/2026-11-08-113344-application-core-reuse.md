# Feature loop: application-core-reuse

Started 2026-11-08 11:33:44 UTC, no limit on cycles, session aa238023-596d-49bd-8039-52502ec096fc, claude-opus-5-5 at high effort, after change ropyotpkxzltrtswvnwnuqxmnmrnlrpu.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'ropyotpkxzltrtswvnwnuqxmnmrnlrpu..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md` at sha256 bdc29a515d2ccf1cbd3302bbc25e91090a5d916ec533fb5c1ec1e21a3858247c.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when R1, R2, R3's justified outcome and your share of the combined acceptance pass, or each is deferred by the timebox with the finding. R4 may be left out without changing that. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-08 11:36:05, `pswrtoxppxsn`: application-core reuse R3 done: the shared JDK image table's release figures, read from job 20261108-063259
  - decided to continue: This run has committed R3's release figures (`pswrtoxppxsn`), which finishes R3; R1 and R2 already pass at the unit level. A step that needs only this stream is still left: the benchmark lacks the contract's unrelated edit and safe helper rewrite, which J4's report needs to show reuse of helper evidence separately from exact cache hits. So the status stays `working` and the next cycle takes that step.
- cycle 2, 2026-11-08 11:44:26, `uxqrooysuqkq`: application-core reuse J4: the cost benchmark gets an unrelated edit and a safe helper rewrite, the contract's last two cases (verification pending)
  - decided to stop: This run has made two commits. The first recorded R3's release figures, which finishes R3; the second added J4's two missing benchmark cases (an unrelated edit and a safe helper rewrite) and queued their release run as job `20261108-114325-application-core-reuse-j4-the-small-comp`. Nothing is left that needs only my work: R1 and R2 pass at the unit level, J4 itself runs at the merge, and the optional R4 is left out because the contract's R2 check can't pass until the merge. Everything left waits on that job, and the brief's status already reads `waiting on jobs 20261108-114325-application-core-reuse-j4-the-small-comp`.
  - the stop left the brief's status working, or uncommitted; session aa238023-596d-49bd-8039-52502ec096fc needs attention

## Summary

# Application-core reuse stream: summary of this run (2 cycles)

This run worked only in the `application-core-reuse` workspace. It made two commits (plus the empty working copy `tvrqpusw`), pushed nothing and merged nothing.

## Commits

### `pswrtoxp` (1ca78c29): R3 done, with the release figures for the shared JDK image table
- **What it adds:**
  - Job `20261108-063259` passed at 3841df5e (3m22s, peak 1.7 GiB). Its figures are now in R3's Progress entry in the brief and in the preparation paragraph of `lib/README.md`, replacing the "pending" note.
  - Medians of 7 runs, before and after sharing the table, in process:
    - unchanged rerun: 209.8 → 8.6 ms (as a separate process: 290.3 → 66.1 ms);
    - cold run: 460.6 → 65.6 ms;
    - defect cold run: 2217 → 1576 ms;
    - defect rerun: 265.3 → 31.9 ms.
  - Opening the image costs 7.89 ms when it builds the table and 0.06 ms when it shares one.
  - javac still takes about 0.4 s per build, more than a whole rerun. The cache saves preparation time, not the time to prove a change.
- **How it was verified:** I read both R3 jobs' reports in full (`060410` before the change, `063259` after). All four scenarios reached the same verdicts, both in process and as a separate process. The README edit is prose only.
- **Gap found:** the benchmark was missing two of the acceptance contract's cases, the unrelated edit and the safe helper rewrite. The next commit adds them.

### `uxqrooys` (283aa75d): J4, the cost benchmark gets the contract's last two cases (verification pending)
- **What it adds:**
  - `lib/tests/preparation.rs` gets two overlays on `after`, in a new folder `lib/tests/fixtures/preparation/` with a README:
    - `unrelated-edit` adds a class that nothing reaches;
    - `helper-rewrite` rewrites `Pricing.discount`.
  - Both start from a copy of the proof cache that a cold run of `after` leaves.
  - For each subject, the report now says whether it was an exact hit, was proved, or went unchecked, and which helper proofs it was proved on.
  - New assertions:
    - both edits keep `after`'s verdicts;
    - the unrelated edit misses nothing and proves nothing again;
    - in the helper rewrite, `total` is proved again on a new proof of `discount`, while `withQuantity` is an exact hit.
  - No library code changed.
- **How it was verified:** a debug smoke run inline (1 repeat, 58 s) passed.
  - Unrelated edit: 5 exact hits.
  - Helper rewrite: 1 exact hit and 4 proofs (the route, `discount` as a subject and as `total`'s helper, and `total`).
  - The route is proved again because the closure of its effect proof contains the helper's body.
- **Release figures:** these come from job `20261108-114325`, which writes `lib/benchmark/preparation/j4.{json,md}`.

## Verification jobs
- **Running:** `20261108-114325-application-core-reuse-j4-the-small-comp`. It is running in the default workspace (since 11:45 UTC, about 15 minutes estimated). Its figures still need to be read into Progress.
- **Already collected:** the two R3 jobs, `060410` and `063259`.
  - Their results are committed in the default workspace, and both passed.
  - This workspace's `pipeline.py status` still lists them as pending, only because the results reach this branch at the merge.
- **Failed:** none of this stream's jobs failed. The 82 failed jobs in `report` are older jobs from other work.

## `sync.py check`
- **0 warnings** for you to judge.
- **49 ERRORs, all "session … has no manifest".**
  - All are on other streams' commits: none comes from this session, and none is an ancestor of this branch.
  - I left them alone, but they need fixing before any push that includes those commits.

## Work deferred, or waiting on you or the merge
- **J4 itself** runs at the merge, as the brief plans.
- **R4 (optional) is left out for now.** The contract's R2 row depends on the objects stream's `construction::receiver`, so R2 needs rechecking after the merge before R4 makes sense.
- **Interface requests for whoever merges** (other owners' code, which this stream doesn't edit):
  - `property_store` should take `&mut Outcome`;
  - `property::Outcome` should get a `reuse` field;
  - the "Refused until…" doc comments in `main.rs` and `property::run` are out of date.

## Also needs your attention
- **Two copies of the brief with different status lines.**
  - This stream's copy (`in-the-loop-application-core-reuse/llm-dlc/loops/application-core-reuse.md`) ends with `- Status: waiting on jobs 20261108-114325-application-core-reuse-j4-the-small-comp`.
  - The default workspace's copy, which the loop prompts point at, still says `working` and has none of this stream's Progress.
  - Fix: merge this stream's `@-`, or point the loop driver at this workspace's copy.

Stopped 2026-11-08 11:47:01 after 2 cycle(s): the session decided to stop, but the brief's status still says working; session aa238023-596d-49bd-8039-52502ec096fc needs attention.
