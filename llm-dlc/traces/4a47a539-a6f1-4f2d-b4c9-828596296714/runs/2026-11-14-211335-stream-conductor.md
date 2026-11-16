# Feature loop: stream-conductor

Started 2026-11-14 21:13:36 UTC, no limit on cycles, session 4a47a539-a6f1-4f2d-b4c9-828596296714, claude-opus-5-5 at high effort, after change rrmtvtxmkrkxwnwtoktmnmqnmvnusnlp.

> Work on the brief in `llm-dlc/loops/stream-conductor.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'rrmtvtxmkrkxwnwtoktmnmqnmvnusnlp..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `llm-dlc/loops/stream-conductor.md` at sha256 067ec146ac8f3032a87980d06a7190f739a4bd5ecee9bb490a00601c3a65ef13.

After each commit the session decides whether to go on:

> Steps 1–3 of the plan, one commit each with its tests, in order. Keep the last line of Progress a status: `working`, or `blocked: ...` with what needs the user. Once step 3 is committed, record in Progress what step 4 needs from the merge and stop with `blocked: steps 1–3 done; step 4 waits for example-targets to be done and this branch merged`. Never start step 4 in this run. A decision the brief leaves open is yours to propose and take, recorded in Progress; stop `blocked:` only for one the brief says belongs to the user.

## Commits

Session 4a47a539-a6f1-4f2d-b4c9-828596296714 was forked from session d34058d5-39ed-426b-a9ff-d538463f39cc.

- cycle 1, 2026-11-14 21:26:59, `rsmpqlswuvvn`: sync.py check: a shared change stamped in another workspace is a note while that workspace's manifest lists its log
  - decided to continue: This run has committed step 1, the decision record (`ltmykkvx`), plus a separate fix to `check` (`rsmpqlsw`). Steps 2 (inboxes) and 3 (the rolling integration line) are still to do. Both need only me: they're tested on made-up repos, and the brief settles every decision in them or leaves it to me. Nothing is blocked, the status stays `working`, and the stop condition applies only once step 3 is committed.
- cycle 2, 2026-11-14 21:35:26, `zkyqxvtxvrmv`: stream-conductor step 2: inboxes, llm-dlc/tools/inbox.py, and the sentence feature-loop.sh adds to every brief's instruction
  - decided to continue: This run has committed steps 1 and 2 (`ltmykkvx` and `zkyqxvtx`), plus a separate fix to `check` (`rsmpqlsw`). Step 3, the rolling integration line, is still to do. It needs only me: it is tested on made-up repos, and the brief leaves nothing in it to the user. The status stays `working`, and the stop condition applies only once step 3 is committed.
- cycle 3, 2026-11-14 21:48:48, `znxmmrnvzonq`: stream-conductor step 3: the rolling integration line, llm-dlc/tools/integration.py, in place of run-streams.sh's integrate_once
  - decided to stop: Steps 1–3 are each committed with their tests: `ltmykkvx`, `zkyqxvtx` and `znxmmrnv`, plus the separate fix to `check`, `rsmpqlsw`. Progress now records what step 4 needs from the merge. Its last line is already `blocked: steps 1–3 done; step 4 waits for example-targets to be done and this branch merged`, which is exactly where the Loop until says this run stops. Step 4 must never start in this run, so nothing is left for this loop to do.

## Summary

# Stream-conductor run: steps 1–3 done, stopped before step 4

The run made four commits in the jj workspace `stream-conductor`, beside example-targets. Steps 1–3 of `llm-dlc/loops/stream-conductor.md` are done, each with its tests. The run then stopped as its Loop until required. Progress ends with `blocked: steps 1–3 done; step 4 waits for example-targets to be done and this branch merged`.

Nothing was pushed or merged, and the default workspace (`../in-the-loop`) was not touched.

## Commits

### `ltmykkvx`: step 1, the decision record
- **What it adds:**
  - `llm-dlc/decisions/schema.json`, which defines one JSON line per change of state.
  - `llm-dlc/tools/decisions.py`, which writes and reads it:
    - the conductor's `record` and `depend`;
    - your `review accept/overturn` and `answer`, which take an id or a range;
    - `list`, `show` and `counts`.
  - Every write is checked against the whole record. A write that would leave a problem is refused, and nothing is written.
  - `sync.py` renders the view (`llm-dlc/decisions/NAME.md`) with its other generated files. `check` validates each record against the schema and against Design 3's rules about what the conductor may decide alone.
- **Decisions taken as the brief proposed:**
  - A decision nobody has reviewed is flagged again once three commits or any job build on it.
  - `decisions.py` is its own tool.
  - Every line also gets a `kind` and an `at`, so your review lines never rewrite the conductor's lines.
- **Verified:** `test_decisions.py` (15 tests) and 2 new tests in `test_workspaces.py`. All 210 tool tests passed.

### `rsmpqlsw`: a fix to `sync.py check`
- **Why:** step 1's commit reported 8 false errors on example-targets commits this branch shares. The example-targets session in the default workspace had re-stamped them, and only that workspace's manifest lists the new log.
- **What changed:** such a trailer is now a note when another workspace's working copy holds a manifest that lists the log. Otherwise it is still an error.
- **Verified:** 2 new tests in `test_workspaces.py` on real jj workspaces. All 212 tool tests passed, and `check` reported 0 errors.

### `zkyqxvtx`: step 2, inboxes
- **What it adds:**
  - `llm-dlc/tools/inbox.py`. Each stream gets `llm-dlc/loop-summaries/NAME-STREAM-inbox.md` in the default workspace (gitignored).
  - `feature-loop.sh` now adds a sentence to every brief's cycle instruction. It tells the stream to:
    - read its inbox;
    - acknowledge each item by id in its Progress update;
    - follow the brief first, then your decisions, then the conductor, and report a contradiction rather than obey it.
  - `send` accepts only six kinds of item: `failure`, `interface`, `answer`, `queued`, `unblocked`, `overturned`. Each must say what the stream is to do and where it comes from.
  - `collect` counts only acknowledgements that are committed.
- **Verified:** `test_inbox.py` (8 tests), including two streams in a temporary jj repo. All 220 tool tests passed.

### `znxmmrnv`: step 3, the rolling integration line
- **What it adds:**
  - `llm-dlc/tools/integration.py` replaces `integrate_once` in `run-streams.sh`.
  - Each check merges every stream's latest commit onto the newest passing merge. It settles generated files with `sync.py regenerate` and runs the brief's script, still inside the 6 GB scope.
  - **On a pass:** the merge is committed on the line, without the script's output files, and never pushed.
  - **On a failure or conflict:** the merge stays uncommitted and is pinned to streams by the files involved.
    - One stream gets a `failure` item in its inbox.
    - Two or more get an open decision and a `queued` item each.
    - The next pass closes those questions as settled and sends each side an `unblocked` item.
    - The same failure seen twice sends nothing new.
- **Verified:** `test_integration.py` (5 tests) on a made-up jj repo with two stream workspaces. They cover:
  - six rounds: a pass, a two-stream failure, the same failure again, a pass that settles it, a textual conflict, and a one-stream failure;
  - finding which streams a failure belongs to;
  - the `run-streams.sh` wiring.

  All 225 tool tests passed.

## Verification jobs
- This run submitted none, and none was needed.
- Five jobs are pending in the shared queue, all from **example-targets** Phase 5 (gates A3 and A4 for examples 285, 286, 287 and 306). They are that loop's, not this one's.
- Nothing has failed or is waiting to be collected.

## `sync.py check`
0 errors and 0 warnings for you to judge. The 260 notes need no action.

## What needs you
1. **The merge.** Step 4 can start only once example-targets is done and this branch is merged into the main line. Merging is yours to do. After `jj new`, run `sync.py regenerate`. Then:
   - Merge this branch's changes to `run-streams.sh`, `feature-loop.sh`, `sync.py`, `llm-dlc/README.md` and the brief template with whatever example-targets changed in them.
   - Run the tool tests on the merged tree.
2. **Recorded in Progress for step 4** (no action needed from you now):
   - `integration.py` and `inbox.py` write the decision record in the default workspace without committing it. Until step 4's conductor commits it, a run's merge loop must.
   - Nothing yet does the conductor's three jobs: `inbox.py collect`, taking the open integration questions, and sending interface requests.
   - The line's commits stay visible as heads after a run. The final merge should start from `integration.py line BRIEF`, or abandon them. Otherwise `prune_workspaces.py` won't delete the `NAME-integration` workspace. Step 4 or 5 is to settle this.
3. **Not yet run for real.** The integration line, inboxes and decision record have only been tested on made-up repos. Their first real run is step 6's.

Ended 2026-11-14 21:50:35 after 3 cycle(s): the session decided to stop; the brief says blocked: steps 1–3 done; step 4 waits for example-targets to be done and this branch merged.
