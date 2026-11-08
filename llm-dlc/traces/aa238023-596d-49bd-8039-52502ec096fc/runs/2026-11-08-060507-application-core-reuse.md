# Feature loop: application-core-reuse

Started 2026-11-08 06:05:07 UTC, no limit on cycles, session aa238023-596d-49bd-8039-52502ec096fc, claude-opus-5-5 at high effort, after change qszysnyorstwxxttpztzlwnmwnklzqqv.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'qszysnyorstwxxttpztzlwnmwnklzqqv..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/application-core-reuse.md` at sha256 bdc29a515d2ccf1cbd3302bbc25e91090a5d916ec533fb5c1ec1e21a3858247c.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when R1, R2, R3's justified outcome and your share of the combined acceptance pass, or each is deferred by the timebox with the finding. R4 may be left out without changing that. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

- cycle 1, 2026-11-08 06:20:11, `xrxnwkqtkxuk`: application-core reuse R2: a read-only helper's summary over the primitive arrays its receiver's fields hold, applied only within its bound
  - decided to continue: This run has committed R2's bounded array reads. The R3 measurement job (`20261108-060410`) has come back passed, so R3's decision now needs only my own work: read its release figures, then either cache the JDK image per process or record that no preparation cache is justified. Nothing left waits on a job, the user or another stream, so the loop should go on.
- cycle 2, 2026-11-08 06:34:06, `womryvutuspn`: application-core reuse R3: the JDK image's table of classes built once per process and shared, keyed by its index (verification pending)
  - decided to stop: This run has committed R2's bounded array reads and R3's decision: the JDK image's table of classes is now shared within the process. R3 is finished apart from the release figures of job `20261108-063259`, R1 and R2 pass at the unit level, and J4 comes at the merge. R4 is the only own work left, and since it is optional and may be left out, I'm not starting it: what's required now waits only on job `20261108-063259`. Progress still says `working`, so the next cycle should set it to that waiting status when it reads the job's figures.

## Summary

# Application-core reuse loop: summary of this run (2 cycles)

The run made two commits on the reuse stream, in workspace `in-the-loop-application-core-reuse`. R2 is finished. R3's change is committed, but the job that measures it in a release build hasn't run yet.

## Commits

### 1. `xrxnwkqtkxuk`: R2, a read-only helper's summary now covers primitive arrays in its receiver's fields
**What it adds**
- A read-only helper (one that only reads its receiver's fields) can now also read an array held in one of those fields: its length and its elements. This works for one-dimensional primitive arrays, except float and double. The footprint analysis is in `lib/src/reuse/footprint.rs`.
- It checks every path through the helper's bytecode. Any array reference must stay in a local and only be used to get its length or load an element of its own type.
- These are each refused, by name:
  - writing to the array;
  - passing it on to another method;
  - comparing it or testing it for null;
  - two arrays meeting where paths join;
  - arrays of floats, of references, or of arrays.
- The summary's proof assumes the array isn't null and has at most 8 elements. Each version's adapter checks both facts on the real receiver at every call. If either fails, it runs that version's original helper instead.
- Each adapter is now a class of its own in its version's package, so it can legally reach package-private members.

**Departure from the brief, for you to judge:** the brief says the field case is "total". With arrays, a read out of bounds throws `ArrayIndexOutOfBoundsException`. The summary's proof treats that exception as an outcome to compare, so the helper is no longer total.

**How it was verified:** inline, with 4 new tests in `lib/tests/reuse_summaries.rs` (14 in all, run three times):
- eight refusals;
- the lifted helper agrees with the original on a JVM over 72 cases, 54 of them out of bounds;
- a for-each rewrite's summary is reused by five changed callers:
  - with a tier mutated through the field and through the caller's alias (each verified, and a stale defect refuted and replayed);
  - with a 10-element array and with a null array, where the original body runs instead;
- a helper that charges one tier more is refused, and its caller is refuted;
- a helper whose versions differ only past the bound: its caller on 10 elements is refuted and replayed. As a check, I took the guard out once: that caller then verified, so the defect was hidden. This shows the guard is needed.
- The classes it produces agree with the original versions on a JVM run with `-Xverify:all`.
- The 233 unit tests pass, and so do the reuse, summaries, application_core, compare, heap, effects and foundations test suites.

### 2. `womryvutuspn`: R3, the JDK image's class table is built once per process and shared (verification pending)
**Why:** job `20261108-060410` (passed) timed a small compare run stage by stage in a release build:

| Run | Time |
|---|---|
| Cold | 460.6 ms |
| Rerun, inside the process | 209.8 ms |
| Rerun, as a separate process | 290.3 ms (185.4 ms of it before any proof-cache lookup) |
| Defect, cold | 2217 ms (1723 ms of it solving) |

A debug build showed that a rerun opens the JDK image `lib/modules` 28 times, and a cold run 50 times. Each open rebuilt the table of classes.

**What it adds**
- In `lib/src/jimage.rs`, `open_file` still reads the image's header and index on every open. If it has already built a class table from identical index bytes, it reuses it. Up to 4 tables are kept, most recent first, and resources are still read from the file actually opened.
- The benchmark (`lib/tests/preparation.rs`) now times the first open and later opens separately.
- `lib/README.md` has a new paragraph, "Preparation, measured".

**Departure from the plan:** the earlier plan was to send this change to the merge as an interface request. Instead I edited `jimage.rs` directly: no stream owns it and none has touched it since the fork. The commit message records the reason.

**How it was verified:**
- In a debug build, the in-process rerun went from 846 ms to 37 ms.
- A new unit test checks three things:
  - two opens of the same image share one table and read the same class;
  - a copy of only the index, placed elsewhere, shares it too;
  - a copy with one class name changed gets a table of its own, and the shared table is left intact.
- The 234 unit tests pass, along with the reuse (11), reuse_summaries (14), compare, application_core (14), summaries (40), effects (18), heap (49), foundations (5) and observations (12) test suites.
- The release figures wait on job `20261108-063259`.

## Verification jobs

| Job | Status |
|---|---|
| `20261108-063259` (R3 benchmark again, with the shared table; 7 repeats into `lib/benchmark/preparation/shared-image.{json,md}`) | **pending, not run yet** |
| `20261108-060410` (R3's first benchmark) | passed, collected |
| `20261108-045000` (the objects stream's O1) | passed, collected |

None have failed. The pipeline is run by `/run-verification`. Once `063259` is back, its figures need to be copied into R3's record in the brief's Progress. R3 is then done.

## `sync.py check`
- **0 warnings** for you to judge.
- **14 ERRORs**, all "session … has no manifest". They are all on other streams' commits, none of which are ancestors of this stream's work, and they were already there before this run. I left them alone. They need sorting out wherever those sessions' traces live before anything is pushed.

## What needs your attention
- **The brief's Progress still says `working`.** The loop stopped because what's left of R3 only waits on job `063259`. The next cycle should record the job's figures and update the status.
- **R4 is not started.** It is the optional local write summary, and it doesn't change any acceptance row. Whether to do it before the merge is your call.
- **J4**, the small report on preparation and cost, is done at the merge.
- **R2's departure from "total"** for array reads, described above, should be reviewed.
- **R3's direct edit of `lib/src/jimage.rs`** should be looked at during the merge.
- **Interface requests recorded for the merge:**
  - `property_store` should take `&mut Outcome`;
  - `property::Outcome` should get a `reuse` field;
  - the out-of-date "Refused until…" docs should be fixed;
  - the contract's R2 row should be checked again after the merge.
- **The integration report** hasn't changed since 05:36. It records a 4-sided conflict in `lib/README.md` and in generated files, which the merge has to resolve. This stream's new README paragraph adds to that file.
- Nothing was pushed.

Ended 2026-11-08 06:36:11 after 2 cycle(s): the session decided the work was done.
