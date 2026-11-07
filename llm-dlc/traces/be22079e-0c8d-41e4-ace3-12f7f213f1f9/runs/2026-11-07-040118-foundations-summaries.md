# Feature loop: foundations-summaries

Started 2026-11-07 04:01:19 UTC, no limit on cycles, session be22079e-0c8d-41e4-ace3-12f7f213f1f9, claude-opus-5-5 at high effort, after change rvxkytqyxunzzwnpplmomsnpxursnolr.

> Work on the brief in `~/code/in-the-loop/llm-dlc/loops/foundations-summaries.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of `.claude/skills/run-verification/SKILL.md` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'rvxkytqyxunzzwnpplmomsnpxursnolr..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message.

Brief `~/code/in-the-loop/llm-dlc/loops/foundations-summaries.md` at sha256 425f040ea8c7d9a7eaf863d7c830dbf00f40c70f2384e3e14d262ce7fd3ec6ed.

After each commit the session decides whether to go on:

> Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

## Commits

Session be22079e-0c8d-41e4-ace3-12f7f213f1f9 was forked from session ae994066-d1ea-4620-b03e-176a07061175.

- cycle 1, 2026-11-07 04:10:54, `xuxuymrrrqsq`: Summaries S1: code closure digests per target, naming the parts a change touches; shared.rs's shape now resolves dynamic constants
  - decided to continue: The loop should go on. This run has finished only S1, and the rest of the core still needs only my own work and no decision from the user: S2's proof cache and invalidation tests, S3's impact report and S4's shared helpers proved equivalent. The one open `check` error comes from another stream's commit and clears at the merge, so it is no reason to stop.
- cycle 2, 2026-11-07 04:21:04, `spkzmqwzmuom`: Summaries S2a: the claim key and the local proof cache, with adversarial invalidation tests
  - decided to continue: The loop should go on. This run has committed S1 (code closure digests) and S2a (the claim key, the cache and its invalidation tests), so the core is only partly done. S2b, the cache's hook in `equivalence.rs` with `--cache`, is next, and S3 and S4 come after it. All three need nothing but my own work, and no item has been deferred by the timebox or needs the user.
- cycle 3, 2026-11-07 04:38:52, `wwxvkxkmywxp`: Summaries Progress: name the other streams' commits that sync.py check reports without a manifest
  - decided to continue: The loop should go on: S1 and both halves of S2 are done, but S3 (the impact report) and S4 (narrow shared helpers, with examples 160–169) are still left in my core. Both need nothing but my own work. Nothing is blocked or deferred by the timebox, and the 6 check errors belong to other streams and clear at the merge.
- cycle 4, 2026-11-07 04:55:11, `krmrutopmwkm`: Summaries Progress: name the 15 errors sync.py check reports after S3, none from this branch's work
  - decided to continue: The loop should go on. This run has committed S1, S2a, S2b and S3, but S4 is still left in my core: one shared stub for helpers proved equivalent, with a check at each call site, acyclic proof dependencies, and examples 160 and 161. It needs nothing but my own work. Nothing is blocked or deferred by the timebox, and the 15 check errors come from other workspaces' commits, are recorded under Progress, and clear at the merge.
- cycle 5, 2026-11-07 05:17:53, `wmzzzzzsyvyo`: Summaries Progress: name the 18 errors sync.py check reports after S4a, none from this branch's work
  - decided to continue: The loop should go on. This run has committed S1 through S3 and now S4a, which makes the integration contract's three summaries checks pass. What is left of my core is S4b: examples 160 and 161, with `build.py` passing `--cache` to an example that asks for it. It needs only my own work, and its proof runs go to a verification job, which is no reason to stop. S5 and S6 follow, nothing is blocked or deferred, and the 18 check errors all come from other streams' sessions and clear at the merge.
- cycle 6, 2026-11-07 05:52:19, `onmlxvvmsmsx`: Summaries Progress: two more errors in sync.py check, behind other streams' new commits
  - decided to continue: The loop should go on. This run has committed S1 through S4, so the core is done. Examples 160 and 161 only wait on their two jobs, which are for review, and a job is never a reason to stop. S5 (refinement per callee) and S6 (the economics job) are still my phases and need nothing but my own work, so stopping now would leave work undone, not avoid polish.
- cycle 7, 2026-11-07 06:21:12, `upvnlnwqrzzx`: Summaries Progress: name the 27 errors sync.py check reports after S5, none from this branch's work
  - decided to continue: The loop should go on. This run has committed the core (S1–S4) and now S5. S6, the economics job, is still one of my phases and needs nothing but my own work: build its change runs on top of `build.py`'s cache option, then submit it as a long job for review. Nothing left needs the user, and nothing has been deferred by the timebox.
- cycle 8, 2026-11-07 06:46:33, `kkqoyoqrtrrv`: Summaries S6: the proof cache's economics on the recorded examples, cold, warm and after four kinds of change (verification pending)
  - decided to stop: The loop should stop. All of this stream's phases, S1 through S6, are committed, and the Status is `done`. This branch passes its integration-contract checks, and its three jobs (S4b's two and S6's economics job) are listed under Progress for review. What remains is a cache for JBMC claims and a cache for `prove`, which is later-brief work and not a step in this stream's phases, so going on would be polish.

## Summary

# Foundations loop, summaries stream: what this run committed

All six phases (S1–S6) are committed in the jj workspace `in-the-loop-summaries`, and the brief's Status is `done`. All test suites pass: unit 183, conformance 9, foundations 3, summaries 40, skill 1, integration 64, `test_build.py` 168, `test_economics.py` 11. Three verification jobs from this stream haven't run yet, and `sync.py check` reports 30 errors, all from other streams' sessions. Nothing was pushed or merged.

## Commits

| Change | What it adds | How it was verified |
|---|---|---|
| `xuxuymrrrqsq` **S1** | Adds `lib/src/closure.rs`, which computes a digest for each part of the code a target's proof reads: methods, every class a call may dispatch to, classes, Spring files. `Closure::changes` names the parts that differ between two builds. **Bug fixed:** `shared.rs`'s body fingerprint didn't look into a `case Color.GREEN` in a pattern switch, so GREEN and BLUE looked equal. A regression check could have reported "nothing to prove" for a changed body. | 11 new tests in `summaries.rs`, one of which reproduced the bug before the fix. Unit, integration and foundations tests pass. |
| `spkzmqwzmuom` **S2a** | Adds the claim key (SHA-256 of the canonical claim) and the local proof cache (`spec/cache.rs`). A claim field the key doesn't know makes the claim uncacheable, rather than being left out of the key. The cache stores only verified results, and refutations that carry a witness. | 11 tests: changing any field of a claim changes its key, and each item on the brief's invalidation list is covered. Mutating the code shows the tests can fail. The integration contract's "summaries keys" and "summaries cache" checks pass. |
| `tumpnkkqksyp` **S2b** | Adds `equivalence --cache DIR` under `--engine native`. A hit returns the stored result without running the checker. Before a stored refutation is reused, its witness is replayed on the current code. JBMC and auto runs are never cached, since JBMC's identity isn't in the key. | 5 tests: exact hit, a miss for each setting that can change a verdict, a tampered witness, and a null array read back correctly (this test found that bug, now fixed). |
| `nplsyutxqysn` **S3** | Adds `jvmcontract impact --before --after`, which reports each claim as invalidated (naming the parts that changed), unchanged, or unresolved. | `examples/tools/impact_check.py` ran on all 59 B9/B11 examples of Crosscut, Quorum and Mica, judged against facts read directly from the class files: all pass. Two deliberately broken versions of `impact.rs` fail the check. 4 new tests. |
| `ztyymskoqxpy` **S4a** | A changed pure integer helper can now be proved equivalent on its own and then treated as one function in both versions of its callers. The caller's statement records an assumption of kind `callee`, basis `proved`. **Also found:** under `--engine native`, no callee had ever actually been shared. | 5 tests: helper reuse, a wrong helper, a mutually recursive helper. The integration contract's "summaries reuse" check passes. |
| `stvkozlttvzr` **S4b** *(verification pending)* | Adds examples 160 and 161 on Crosscut: a correct and a wrong rewrite of `TokenBucket.lastAfter`. Adds `build.py`'s `approach.cache` option and `expected.sharedHelpers`. **Fixes an S4a bug:** two cold runs on the same code gave the caller different keys. | Inline: 160's helper proof took 0.19 s; 161 is refuted with a counterexample that replays. 7 new `test_build.py` tests and 1 new summaries test (which failed before the fix). |
| `tqzzvqrotvqw` **S5** | Under JBMC, when a counterexample turns out to be spurious, only the shared callees it depends on are computed as written again, instead of all of them. | 3 tests, including two shared callees where only one is the cause. With that logic disabled, the two-callee test fails. **Flaky:** one integration test timed out under load; it passed alone in 9.9 s and in the next full run. |
| `kkqoyoqrtrrv` **S6** *(verification pending)* | Adds `examples/tools/economics.py` and 8 change patches (an unrelated edit, a helper rewrite, a representation change and a regression, for each of Crosscut and Mica). It measures cold and warm runs and what each change costs. The proof cache now notes how long computing the key and the lookup took. **Also fixes the brief:** S5's commit had pasted a duplicate Progress section into it. | `--plan` built all 90 trees inline (125 claims, 250 checks). `impact` confirmed what each change reaches, and both helper rewrites' proofs hold. 11 tests against a fake `jvmcontract`, including cases that are meant to fail. |

The other 7 commits only update Progress, mostly to list the `sync.py check` errors that come from other streams.

## Verification jobs not yet run

None has run yet, and none has failed. This stream's three:
- `20261107-053635-example-160-a-changed-refill-helper-prov` (quick): expected verified, with `lastAfter` shared.
- `20261107-053635-example-161-a-refill-helper-aligned-to-t` (quick): expected violation, with no helper shared.
- `20261107-064135-the-proof-cache-s-economics-on-the-recor` (long, ~30 min): expected to exit 0 with every expectation met.

Three other streams' jobs are also queued: alignment A3, H1 symbolic references and H2 nullable parameters. Run them with `/run-verification`.

## `sync.py check`

**0 warnings** for you to judge. There are 30 errors, all from other streams' sessions (heap, alignment, observations), none from this branch:
- **25 errors:** another stream's session has no manifest. Its manifest is on that stream's branch.
- **5 errors:** a commit points at log `1f2230c9f137`, which its manifest doesn't list.

These should clear when the branches are merged. If they don't, they need fixing before a push.

## Needs your attention

- **Merge conflicts.** The 06:01 integration check found conflicts with other streams in `lib/README.md`, `lib/src/equivalence.rs` and the generated `llm-dlc/` files. Its tests didn't run. The reconcile loop is responsible for resolving them.
- **Two things for a later brief, if you want them:**
  - **JBMC claims:** the cache serves only 17 of the 61 recorded B9/B11 examples on the javac apps. JBMC claims could be cached once JBMC's own identity is part of the key.
  - **`prove`:** `prove` (B11) has no cache hook yet.
- **Out of date in the main brief:** its "Where it starts from" still says refinement is all-or-nothing, which S5 changed. That text isn't this stream's to edit.
- Nothing was deferred for lack of credentials or a decision.

Ended 2026-11-07 06:48:17 after 8 cycle(s): the session decided the work was done.
