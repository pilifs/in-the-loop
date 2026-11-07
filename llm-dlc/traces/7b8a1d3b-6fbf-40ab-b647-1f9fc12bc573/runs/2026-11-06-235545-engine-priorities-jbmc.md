# Feature loop: engine-priorities-jbmc

Started 2026-11-06 23:55:45 UTC, no limit on cycles, session 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573, claude-opus-5-5 at high effort, after change tokyzslsyxozmzkvstvvztuvmxxzwkxq.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'tokyzslsyxozmzkvstvvztuvmxxzwkxq..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/engine-priorities-jbmc.md` at sha256 4b2f54d4789ec8e4eab1b37b1dbe2d0b0463b1e82d9048d770cc0d8fab4f001f.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to `waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.

## Commits

- cycle 1, 2026-11-07 00:01:50, `xyplqrtnqlom`: The examples' result schema allows a run's phasesExcess; 3's rerun passed, 4a's JBMC table measured, its own-checker step rerun (verification pending)
  - decided to stop: Phases 1, 2 and 3 are done. This run's commit (`xyplqrtn`) recorded the passing rerun of Phase 3's job, measured JBMC's half of Phase 4a, and fixed the schema error that stopped the own checker's half. The only thing left in my phases is reading job `20261107-000039`, which reruns that half. None of the remaining work is mine alone, and Progress already ends with `- Status: waiting on jobs 20261107-000039`, so the loop starts again once that job is collected.

## Summary

# Run summary: `engines-jbmc` feature loop (1 cycle)

This run made one commit. My phases (1, 2 and 3) are finished. Phase 4a has JBMC's half measured, and its own-checker half is waiting on one running job. The stream's status line says `waiting on jobs 20261107-000039`.

## Commit

### `xyplqrtn` (98bab485): the result schema now accepts `phasesExcess`; Phase 3's rerun passed; 4a's JBMC table measured *(verification pending)*

- **Phase 3 is done.** The rerun job `20261106-231317` passed in 33 m 53 s, with a peak of 1.3 GiB:
  - 63 integration tests passed.
  - The corpus ran under `jbmc` and `auto`: 98 claims, 196 runs.
  - Under `auto --confirm`, the 12 disagreements from `-203452` no longer appear.
  - Each of the three JBMC 6.11.0 defects in `lib/src/jbmc_gaps.rs` now has its cause known and a guard with tests. Two of them have upstream reports drafted for you (details under "Needs your input").
- **4a, JBMC's table:** job `20261106-231837` checked the 41 recorded JBMC examples under strict mode. JBMC refuted 27 obligations, proved 13 and left 3 without a verdict (43 in all).
  - `071#0` and `#1` get no verdict, at the `Enum.<init>`, `List.of` and `List.copyOf` stubs. Job `-082917` predicted this.
  - **`037#0` is the one result that differs from its expected verdict.** It is a JBMC proof, refused by the `unmasked-shift` guard at `-1 >>> Integer.numberOfLeadingZeros(cap - 1)`, where the shift distance is 32 when `cap == 1`.
    - I checked it inline on the JVM over all 2³² ints. The recorded proof is correct: JBMC computes that shift wrongly, but here the wrong value gives the same result.
    - So the refusal comes from the guard being broader than it needs to be. This is noted for 037's notes and for the reconcile loop's 4c.
- **Fix:** the own-checker step of `-231837` stopped at example 018. `build.py` refused the result because the result schema did not allow `phasesExcess` on `search.runs[]`. That field is Phase 1a's flag for a run whose named phases add up to more than its total time.
  - `examples/schema/result.schema.json` now allows `phasesExcess` as a positive number.
  - The underlying cause is in the own checker: the encoding time in `lib/src/bmc/bits.rs` is sampled (`ENCODING_SAMPLE`), so short runs can come out over their total. I recorded this for the native stream, which owns that code.
- **How it was verified:**
  - I reproduced 018 inline. The run took 0.18 s; encoding (0.019 s) plus solving (0.174 s) comes to 0.013 s over that, beyond the tolerance.
  - I added the real run record to the 14 committed results that have runs, and they pass `build.py`'s whole `check_result` chain.
  - Negative and string values are refused (42 of 42 cases behaved as expected), and the schema from the previous commit refuses the real record.
  - `test_build.py` still has the same 35 errors it had before this change, and `test_gap_table.py` passes.
- **Job submitted:** `20261107-000039` reruns all three steps of `-231837` at this commit, so the own checker's table and the comparison between engines come from the same code.

## Verification jobs

| Job | State | Notes |
|---|---|---|
| `20261107-000039`: the 41 JBMC examples under strict on both engines (4a rerun) | **running** since 2026-11-07 00:02 UTC | The only thing this stream is still waiting on. |
| `20261106-231837`: the first version of that job | **failed** at the own-checker step (018) | Fixed in `xyplqrtn` and replaced by `-000039`. Its JBMC table is recorded. |
| `20261106-231317`: Phase 3 rerun | passed | — |

`report` lists 48 failed jobs in total. Apart from `-231837`, none of them are this stream's (for example, `20261103-002843`, a Mica examples rerun where a patch no longer applies to example 036).

## `sync.py check`: warnings for you to judge before pushing

- **7 proposed allow-list entries** are waiting for you: run `python3 llm-dlc/tools/sync.py allow approve` in your terminal.
- **12 of this session's logs** (`7b8a1d3b…`) each warn `long-token ×14`. They look like mangled C++ symbols (`_ZZ…`, 45–107 characters), probably from JBMC/CBMC output. Please confirm they are harmless before they are published. `sync.py review show ID` shows each one, masked.
- **27 errors**, all "session has no manifest" or "points at log … that the manifest does not list". They come from other workspaces' changes (for example `xqmmzyrtzxqr` and `wtvowsostpzw`), none of which are ancestors of this branch, so this stream did not cause them. They still need clearing before a push.

## Needs your input

- **Two upstream JBMC reports are drafted and not filed**, because filing is outward-facing. Both are in `lib/tests/fixtures/jbmc-defects/README.md`: one for cause 1 (`return-past-handler`) and one for cause 3 (`unmasked-shift`). It's your call whether and when to file them.
- **Nothing else is blocked on you.** No credentials or other decisions are pending.

## Handed to other loops

- **Native stream:** the own checker's sampled encoding time can flag short runs with `phasesExcess`. That code is in `lib/src/bmc/`, which this stream doesn't touch.
- **Reconcile loop (4c):**
  - JBMC's table from `-231837`, and the own checker's table once `-000039` is collected; the tables go to 4c as they stand.
  - 037 is counted as decided by neither engine under strict, because the `unmasked-shift` guard refuses a proof that is in fact correct.

## Next

When `-000039` is collected, the next loop run records the own checker's table over the 41 and the comparison under 4a. It then sets the stream's status to `done`.

Ended 2026-11-07 00:03:24 after 1 cycle(s): the session decided the work was done.
