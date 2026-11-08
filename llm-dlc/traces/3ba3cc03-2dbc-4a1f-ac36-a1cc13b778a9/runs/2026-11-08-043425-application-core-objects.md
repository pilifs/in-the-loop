# Feature loop: application-core-objects

Started 2026-11-08 04:34:25 UTC, no limit on cycles, session 3ba3cc03-2dbc-4a1f-ac36-a1cc13b778a9, claude-opus-5-5 at high effort, after change rqxxpmqtolylqxyzywktllvwonxstvoz.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/application-core-objects.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'rqxxpmqtolylqxyzywktllvwonxstvoz..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/application-core-objects.md` at sha256 111030cbe1572d4a901669751dfe7457eb45bd34c27f14a5595e238caae9da45.

After each commit the session decides whether to go on:

> Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with `waiting on jobs ID ...`. Stop with `done` when O1–O3 and your share of the combined acceptance pass, or each is deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Optional construction work must not delay the core or grow into a heap project. Anything new you find goes under Progress, for the main brief's for-review list.

## Commits

Session 3ba3cc03-2dbc-4a1f-ac36-a1cc13b778a9 was forked from session 3da21514-fe46-49d5-8200-08d3cf89ea17.

- cycle 1, 2026-11-08 04:52:02, `zuwkutwssrpl`: application-core objects O1: an ordinary receiver made by its constructor in the regression and property checks (verification pending)
  - decided to continue: The loop should go on: this run has one commit so far (`zuwkutws`), and it covers only O1's first part, the ordinary receiver. The rest is my own work and doesn't depend on another stream: - O1's other parts: constructor arguments that are bounded primitive arrays, choosing a constructor through a plan, and `--plan` support in the checks. - O2's construction DAG with its replay and negative controls. - O3's setup sequence on the throttle. The pending job (`20261108-045000-…`) and the cache finding I sent to the reuse stream block none of this.
- cycle 2, 2026-11-08 05:35:17, `rukolrmuswxn`: application-core objects O1 and O2: a constructor may take a bounded primitive array, kept apart between the versions, and a leaked defensive copy is refuted
  - decided to continue: The loop should go on: O2's core still has steps that need only my own work. Those are a plan's nullable and shared objects, rebuilt with the same identities on the JVM, and three of the five negative controls (two parameters that were one object becoming distinct, side effects in a constructor, a narrower new constructor under an anchored domain). After them come checking that a shrunk witness is still a legal construction, and registering every constructor and setup method for reuse. The contract's O3 failure waits on the coordinator's fixture fix and is recorded in Progress, but nothing else is blocked on another stream or a job.
- cycle 3, 2026-11-08 05:56:03, `xnwtzpszzxsv`: application-core objects O2: a plan's root may be null or one of other roots' objects, one node at two roots is one object, and two parameters that were one object becoming distinct is refuted
  - decided to continue: The loop should go on. O2 still has steps that need only my own work: two negative controls (side effects in a constructor, and a narrower new constructor under an anchored domain), a check that a shrunk witness is still a legal construction, and registering every constructor and setup method for proof reuse. The contract's O3 failure waits on the coordinator's fixture fix and is recorded in Progress, but it blocks nothing else, and no job is pending that other work depends on.
- cycle 4, 2026-11-08 05:58:42, `rzsloznpmsnz`: application-core objects: move this stream's lib/README.md paragraphs out of the spot every stream appends to
  - decided to continue: The loop should go on. This cycle only fixed the README merge conflict, and O2 still has steps that need only my own work: two negative controls (side effects in a constructor, and a narrower new constructor under an anchored domain), a check that a shrunk witness is still a legal construction, and registering the constructors and setup methods for proof reuse. The contract's O3 failure waits on the coordinator's fixture fix and is recorded in Progress, but it doesn't block those steps.
- cycle 5, 2026-11-08 06:13:01, `vnrtpxstskst`: application-core objects O2: a constructor or setup call that writes a static field is refused by name, the negative control of unsupported side effects in a constructor
  - decided to continue: The loop should go on. O2 still has steps that need only my own work: the last negative control (a narrower new constructor under an externally anchored domain), the check that a shrunk recipe is still a legal construction, and registering the constructors and setup methods for proof reuse. O3's contract failure waits on the coordinator's fix to the throttle fixture's allocation bound, which is recorded in Progress and doesn't block those steps.
- cycle 6, 2026-11-08 06:36:09, `qvzkzuzoswlt`: application-core objects O2: an input only one version's constructors accept is a difference, the negative control of a narrower new constructor under an anchored domain (verification pending)
  - decided to continue: The loop should go on. O2 still has steps that need only this stream's work: checking that a shrunk counterexample's construction recipe is still legal and still reproduces the same failure, and registering constructors and setup methods as claim roots. The values stream has also committed its String adapter, so O2's adapter step can begin. The two pending jobs and O3's fixture allocation bound, which waits on the coordinator, block none of these.
- cycle 7, 2026-11-08 06:51:46, `ozwozwkorymn`: application-core objects O2: a shrunk witness is the same failure as the one found, replayed before it is accepted (verification pending)
  - decided to continue: The loop should go on: one O2 step still needs only this stream's work. That step is listing every constructor and setup method a check uses as a claim root, from the construction plan and harness layout, so that reuse's cache can key on them. Only wiring that list into the cache in `proof_cache.rs`, which is reuse's file, has to wait for that stream. The pending jobs, the String adapter (which waits for the merge) and O3's fixture allocation bound (which waits on the coordinator) block nothing else.
- cycle 8, 2026-11-08 07:20:14, `urlkszxtksrm`: application-core objects O2: every constructor and setup method that makes a check's inputs is listed as a claim root, for the reuse stream's key
  - decided to continue: The loop should go on, because one step still needs only this stream's work. A replay that couldn't run one version must stop being counted as reproduced in `witness::differences`. That code is this stream's replay plumbing, and it comes with a reproducer first. The rest waits on others but blocks nothing else: two pending jobs (`20261108-063512-…`, `20261108-064305-…`), reuse wiring `construction_roots` into its cache key, the String adapter until the merge, and O3's fixture allocation bound for the coordinator.
- cycle 9, 2026-11-08 07:23:07, `nkqoklwqvpnt`: application-core objects O2: the record test of lib/tests/integration.rs asserts the two construction regions that compare admission, closing VF-022 when its job passes (verification pending)
  - decided to continue: The loop should go on. A step still needs only this stream's work: `witness::differences` must stop counting a replay that couldn't run one version as reproduced. That code is this stream's replay plumbing, and the step starts with a reproducer. What else is left waits on others but doesn't block that step: job `20261108-072230-…` (VF-022's rerun), reuse wiring `construction_roots` into its cache key, the String adapter until the merge, and the coordinator's call on O3's fixture allocation bound.
- cycle 10, 2026-11-08 07:42:05, `nqpqroqpsysx`: application-core objects O2: a replay that cannot run one version reproduces nothing, and its witness is run on a JVM (verification pending)
  - decided to stop: Every required step left now waits on someone else. Two jobs are pending: `20261108-072230-…` for VF-022 and `20261108-074116-…` for this cycle's replay fix. O2's String adapter waits for the merge, O3's allocation bound waits on the coordinator, and rooting setup calls in the cache key is the reuse stream's; all are recorded under Progress. The only work left that is mine alone is optional (array fields in property expressions), and the brief says not to let that grow into a heap project, so the next state is `waiting on jobs 20261108-072230-… 20261108-074116-…`, with those blockers named.

## Summary

# Application-core objects stream: summary of this run (10 cycles, 11 commits)

The stream is not pushed. One job is still running, the merge is blocked only by conflicts in generated files, and the decisions listed below are with you, the coordinator or the reuse stream. "Inline" below means native-engine tests run in the session without JBMC; the JBMC runs went to queued jobs.

## Commits, oldest first

1. **`zuwkutws` — O1: a receiver can be any ordinary class, made by its constructor.** Before, `equivalence` and `prove` refused an instance method unless its class was a record of primitive components. Now the receiver is built like an object parameter. Its fields are compared after the call, and it counts as a root for identity checks.
   - **Verified:** inline, by the contract's O1 and five new tests. Job `20261108-045000-…` **passed**: integration tests plus shop examples 190–196, all as expected.
   - **Found:** an unsound cache hit in reuse's `proof_cache.rs`. A build that changes only an inner object's constructor reuses another build's proof. The reproducer is the ignored test `an_inner_objects_constructor_is_part_of_the_cached_claim`.
2. **`skvmtlxn` — O1/O3: plans and setup sequences.**
   - A construction plan can choose which constructor to use.
   - A setup sequence of one or two calls is checked and replayed as one whole history. When setup throws in one version only, that counts as a difference.
   - **Verified:** inline, by four new tests.
   - **Found:** the frozen throttle claims set an allocation bound of 0, but `allows` and `take` allocate the exception they throw. O3 in `tests/application_core.rs` fails on this (see "Needs your attention").
3. **`rukolrmu` — O1/O2: constructors may take bounded primitive arrays.** Each version gets its own copy of the array. A constructor that keeps the caller's array where the previous version copied it is now refuted.
   - **Verified:** inline, by three new tests; the witnesses were also run on a JVM.
4. **`xnwtzpsz` — O2: aliasing in plans.**
   - A plan's root may be null, or may be the same object as another root's.
   - One node used at two roots is always one object.
   - The negative control: a rewrite that is only correct when two parameters are distinct objects is refuted.
   - **Verified:** inline, by unit tests and four integration tests; the witnesses were also run on a JVM.
5. **`rzsloznp` — README only.** This stream's `lib/README.md` paragraphs moved, unchanged, to a spot no other stream appends to. This removed one source of merge conflict.
6. **`vnrtpxst` — O2: constructors or setup calls that write a static field are refused by name.** Before, a verdict over such a constructor silently covered only the first object made.
   - **Verified:** inline, by a new test. No job was needed.
7. **`qvzkzuzo` — O2: an input that only one version's constructors accept is now a difference.** Before, it was skipped, so a narrower new constructor could pass as verified.
   - **Verified:** inline.
   - Job `20261108-063512-…` **failed** on one stale test assertion, which became VF-022. Its 20 example steps (126–196) all gave their expected verdicts.
8. **`ozwozwko` — O2: a shrunk witness must reproduce the same failure.** Before, shrinking could turn one difference into a different one. A shrunk witness is now replayed before it is accepted.
   - **Verified:** inline.
   - Job `20261108-064305-…` **failed** on the same stale assertion. Its other 64 tests passed.
9. **`urlkszxt` — O2: every constructor and setup method that makes a check's inputs is listed as a claim root** (`Layout::construction_roots`), for the reuse stream's cache key.
   - **Verified:** inline. This includes a test showing that a guard is needed until reuse's key uses these roots.
10. **`nkqoklwq` — fixes VF-022.** The record test now expects the new statement text, with one construction region per version.
    - Job `20261108-072230-…` **passed**, 65 of 65, and **VF-022 is closed**. That run also covers the code from commits 7 and 8.
11. **`nqpqroqp` — O2: a replay that cannot run one version is no longer counted as a reproduction.** This is the Phase 0 finding on VF-015 step 4: an unknown outcome had been counted as a difference. Such witnesses now go to a JVM. The result is a violation if the JVM shows a failure, and unverifiable otherwise.
    - **Verified:** inline, by a reproducer that failed before the fix, a new unit test, 230 lib tests and the other suites.
    - Job `20261108-074116-…` is **still running**.

## Verification jobs

| Job | State |
|---|---|
| `20261108-045000-…-o1-lib-tests-in` | passed |
| `20261108-063512-…-o2-the-regressi` | failed: stale assertion, VF-022, now closed |
| `20261108-064305-…-o2-a-shrunk-wit` | failed: same cause, VF-022 |
| `20261108-072230-…-o2-lib-tests-in` | passed, closes VF-022 |
| `20261108-074116-…-o2-a-replay-tha` | **running** (integration tests 65/65, plus a stricter VF-015 step 4 on example 109). It does not close VF-015. |

## `sync.py check`

- **0 warnings** for you to judge.
- 22 `ERROR`s, all "session … has no manifest", from other sessions: 9ef76667, b8c9cad1, 73918f92, aa238023, 34b4ec0b, 201f326a, e9fd9c4f and others. None is from this stream's session (3ba3cc03), so they are left to their owners. There were 21 last cycle; the extra one is another session's.

## Needs your attention

- **O3's allocation bound (yours or the coordinator's decision).** `expected.json` expects O3 to be verified or refuted. With the frozen bound of 0 it is unresolved, so `application_core` fails on O3 (13 of 14 pass) until someone either corrects the fixture or decides otherwise. I left the allocation gate unchanged.
- **VF-015 step 5:** you deferred it, and it stays open.
- **Reuse stream requests** (their files, not mine):
  - Fix the unsound inner-constructor cache hit. Its reproducer is the ignored test.
  - Use `construction_roots` in the regression key. Until then, claims with setup calls stay uncached.
  - Read the plan in the property key and in `spec::cache::key`.
- **Merge:**
  - The 07:36 integration check conflicts only in generated files: `llm-dlc/README.md`, `index.json`, `traces/README.md` and `traces/metrics.json`.
  - After merging:
    - un-ignore the inner-constructor test;
    - drop the uncached guard for setup claims;
    - remove the old "either version rejects" sentence and update the Limits line in `lib/README.md`.
- **Waiting on the values stream:** O2's String adapter needs values' `nlkuyptr` merged first.
- **Progress status:** the brief's Progress still ends `- Status: working`. The loop stopped before committing `waiting on jobs …`, so the next run should update it.
- **Flaky test:** a timing test in values' `bmc/bits.rs` failed once under load and passed 3 of 3 when run alone. It is recorded under Progress.
- **Not done (optional):** array fields in property expressions (`this.data`), deferred so it wouldn't grow into a heap project.

Ended 2026-11-08 07:44:52 after 10 cycle(s): the session decided the work was done.
