# Feature loop: engine-priorities-jbmc

Started 2026-11-07 00:08:24 UTC, no limit on cycles, session 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573, claude-opus-5-5 at high effort, after change xyplqrtnqlomslkusuutuvxxxzqkxntm.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'xyplqrtnqlomslkusuutuvxxxzqkxntm..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md` at sha256 4b2f54d4789ec8e4eab1b37b1dbe2d0b0463b1e82d9048d770cc0d8fab4f001f.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

- cycle 1, 2026-11-07 00:10:29, `pmoympwnmukq`: 4a's job 20261107-000039 passed: both engines' strict tables over the 41 JBMC examples, and their comparison; the stream's phases are done
  - decided to stop: All of this stream's phases (1a, 1b, 2a–2c, 3 and 4a) are finished. This run's commit `pmoympwn` recorded job `20261107-000039`'s two tables and their comparison, and Progress now ends with `- Status: done`. What remains belongs to others: 4b–6, the examples' notes and the merge go to the native stream and the reconcile loop, and the two drafted JBMC bug reports wait on you to file them.

## Summary

# Engines JBMC loop: run summary (1 cycle)

This stream is finished: all its phases (1a, 1b, 2a–2c, 3 and 4a) are done, and its Progress section ends with `- Status: done`.

## Commit this run

**`pmoympwn` (3d1a40db): 4a's job `20261107-000039` passed; the stream's phases are done**

- **What it adds:** a Progress entry in `llm-dlc/loops/engine-priorities-jbmc.md` recording the 4a job. That job ran the 41 recorded B9/B11 JBMC examples on each engine in strict mode and compared the two tables. It took 4 m 22 s and peaked at 1.1 GiB.
  - **JBMC's table:** 27 refuted, 13 established, 3 unresolved. This is the same as the earlier run `-231837`.
    - `071#0` and `#1` hit stubs.
    - The unmasked-shift guard refused `037#0`. The proof itself is correct.
  - **The own checker's table:** 24 refuted, 11 established, 8 unresolved.
    - `013#0` and `071#0`–`#2` stop at the `TermOrder.<clinit>` class initializer.
    - `037#0` stops at `Integer.numberOfLeadingZeros`, and `127#0` at `Long.numberOfLeadingZeros`.
    - `035#0` has a float parameter, which is outside the fragment.
    - `052#0` has a loop that `--unwind 16` doesn't fully unroll.
  - **The comparison:** 5 of the 43 obligations differ.
    - Both engines decide 35, and they agree on every one.
    - JBMC alone decides 5, the own checker alone none, and neither decides 3.
  - Example 018 reports a `phasesExcess` of 0.010. The result schema has allowed that field since `xyplqrtn`.
  - The entry includes a note for 4c. No shared file changed.
- **How it was verified:**
  - All three steps of the job passed: JBMC 184 s, own checker 78 s, comparison 0.2 s.
  - I extracted the outputs from the result's `changes.diff`, and their sha256s match the recorded outputs. They are also in the default workspace's `lib/target/jobs/4a-coverage/`.
  - Both `gap_table.py --compare` and a separate count over the two JSON tables confirmed the 5 differences and the split above.

## Verification jobs

- **Pending, running or uncollected:** none. The queue is empty and all 200 jobs are collected.
- **This run's job** `20261107-000039` passed.
- **Failures:** `pipeline.py report` lists 48 failed jobs, but they come from earlier work. The first is the Mica rerun `20261103-002843`, where a patch didn't apply. None was submitted in this run.

## `sync.py check`: 28 errors, 14 warnings

**Errors (28).** All are "session … has no manifest" or "points at log … that the manifest does not list".
- One more than last time: `lxlxyvstqozv`, the verification runner's collection commit.
- I checked each erroring change against `::@`, and none is in this branch. They belong to other sessions or workspaces, so I didn't touch them. They still need fixing before anything from those branches is pushed.

**Warnings for you to judge before pushing (14):**
1. **7 allow-list proposals** are waiting for your decision. Approve them in your own terminal with `python3 llm-dlc/tools/sync.py allow approve`.
2. **13 of this session's logs (`7b8a1d3b-…`) are flagged for long tokens.** Each has 14 long-token hits, all mangled C++ symbols starting `_ZZ…` (45–107 characters) from tool output. They look harmless, but they need your decision: propose them for the allow list, or review them with `/review-findings`.

## Waiting on you

- **Two upstream JBMC bug reports** are drafted in `lib/tests/fixtures/jbmc-defects/README.md`, one for each of two defects in `jbmc_gaps.rs`. They stay drafts until you decide whether to file them.
- **A push** only happens when you ask, after you've judged the warnings above.

## Owned by other loops

- **The reconcile loop:** 4c (it takes the two tables as they stand), the examples' notes (including 037's, described in Progress) and the merge.
- **The native stream:** 4b, 5 and 6. This includes the own checker's gaps that 4a measured: class initializers, `numberOfLeadingZeros` and floats.

Ended 2026-11-07 00:11:40 after 1 cycle(s): the session decided the work was done.
