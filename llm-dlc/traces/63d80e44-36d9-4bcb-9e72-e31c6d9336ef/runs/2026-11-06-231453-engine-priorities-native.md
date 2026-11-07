# Feature loop: engine-priorities-native

Started 2026-11-06 23:14:53 UTC, no limit on cycles, session 63d80e44-36d9-4bcb-9e72-e31c6d9336ef, claude-opus-5-5 at high effort, after change ulsqmxuqnyluwvxmwoxrxorunsvrvvul.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-native.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'ulsqmxuqnyluwvxmwoxrxorunsvrvvul..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-native.md` at sha256 10aca92721bdef2af3746b2db6a77c91a3c12f53c8c9ac03daa3672d3870d530.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phase 5 is the core of this stream: don't stop before it is done unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

- cycle 1, 2026-11-06 23:19:41, `tpytwvmvtzwp`: Recommend against moving the own checker to word-level solving, from the two solver comparisons (Phase 6d)
  - decided to stop: The loop should stop: all my phases are finished. This cycle's commit (`tpytwvmv`) wrote 6d, the recommendation, from the two comparison jobs, both of which passed, and set the status to `done`. The one open Phase 5 criterion (071's two proofs standing under strict) needs a fix in `jbmc_gaps.rs`. That file belongs to the JBMC stream, so the fix is recorded under Progress for the reconcile loop rather than being work I can do here.

## Summary

# Feature loop report: the `engines-native` stream, one cycle

This run made one commit, and it finishes the stream. The brief's status (`llm-dlc/loops/engine-priorities-native.md`) is now `done`. The one item still open, Phase 5's last criterion, needs a change in the JBMC stream's files, so it is left for the reconcile loop.

## The commit

### `tpytwvmv` (git `3aa194f`): recommend against moving the own checker to word-level solving (Phase 6d)

**What it adds:**
- **`lib/solvers/README.md` (new): the Phase 6 answer.** It recommends keeping CaDiCaL 1.9.5 and the engine's own bit-blasting as the default, and keeping `bitwuzla-words` as an opt-in prototype. No default changes. The figures come from the two comparison jobs, `20261106-224616` (bit-blasted) and `20261106-230455` (word-level), which both passed:
  - **Same clauses, different solver:** Bitwuzla is slower on every workload. It is 2–43× slower with its defaults and 1.7–14× slower with `preprocess=0`.
  - **Word-level terms with `preprocess=0`:** the gain is at most 1.93×, on binary search. Reverse is 1.66× faster and 142 is 1.31× faster; 141 and prefix sums are level.
  - **Word-level terms with Bitwuzla's defaults:** 141 and 142 are slower than CaDiCaL.
  - **What the tool can decide:** nothing changes. No case moved from undecided to decided.
  - **Cost of a migration:** it would lose the clause transcripts and the bundled solver, and the array theory is still unbuilt.
  - **Other contents:** a section on what evidence would change the recommendation (nonlinear arithmetic or long arrays, measured with `compare.py --words`), two tables of results, and the limits of the evidence.
- **`lib/solvers/compare.py`:** the job tables recorded the commit as `at ?`, because the runner's exported tree has no git. It now uses `VERIFY_SOURCE_COMMIT` when that is set and falls back to `git rev-parse HEAD`. The tables already recorded stay as they are.
- **`lib/solvers/test_compare.py`:** a new test for that fallback.
- **`lib/README.md` (a shared file):** one added sentence pointing at `solvers/README.md`.
- **`lib/solvers/bitwuzla/README.md`:** a pointer line to the new page.
- **The brief's Progress section:** the 6c results, the 6d entry, where each phase stands, and the list of items for the reconcile loop.

**How it was verified:**
- Every figure in the README was checked against the two jobs' outputs in `lib/solvers/comparison/`. Several figures in my first draft were wrong and were corrected before the commit.
- All 5 tests in `test_compare.py` pass.

## Verification jobs

- **This stream:** nothing is pending and nothing failed. Both comparison jobs passed: `-224616` in 22m41s and `-230455` in 3m51s.
- **Other streams' jobs:** results are collected in the default workspace, `~/code/in-the-loop`. Two JBMC-stream jobs are still in flight:
  - `20261106-231317` (JBMC's defects under `--confirm`) is **running**.
  - `20261106-231837` (the 41 recorded JBMC examples under strict) is **pending**.
- `pipeline.py status` in this workspace still lists those two and ten others as pending, because their results were collected in the default workspace, not here. They aren't really outstanding.
- The 47 failed jobs in `report` are all from earlier runs (2026-11-03 and before). None is from this run.

## `sync.py check`

- **0 warnings to judge.**
- **25 errors, none on this run's commit.** All of them come from other sessions' commits:
  - 24 errors are "session … has no manifest".
  - Change `wtvowsostpzw` has two errors of the form "points at a log the manifest does not list". The same change also accounts for one of the missing-manifest errors.
- Most of the errors are on the JBMC stream's changes (session `7b8a1d3b`). They should clear when those sessions commit through `sync.py`, or at the push, which records outstanding traces. If any are still there after that, they need looking at before you push.

## Left for the reconcile loop, or for you

- **Phase 5's last criterion is open:** 071's two proofs don't yet stand under strict. The fix is a path-aware gap check in `lib/src/jbmc_gaps.rs`, which belongs to the JBMC stream, so I didn't change it.
- **The `declaring` gap needs your decision.** Progress suggests drafting an upstream report about it for you to review. Nothing outward-facing has been sent.
- **Other files that need reconciling:**
  - `conformance.json`;
  - the notes for examples 071 and 013;
  - Bitwuzla's version in step 1b's record.
- **An open question in the comparison:** part of the word-level gain may come from Bitwuzla's newer CaDiCaL (2.1.2 against the engine's 1.9.5). A small job that builds a standalone CaDiCaL 2.x and replays the transcripts would separate the two. The brief doesn't call for it at a gain below 2×, so it wasn't queued.
- **Nothing is pushed.** Push when you're ready with `python3 llm-dlc/tools/sync.py push --bookmark main` or `/publish`.

Ended 2026-11-06 23:21:11 after 1 cycle(s): the session decided the work was done.
