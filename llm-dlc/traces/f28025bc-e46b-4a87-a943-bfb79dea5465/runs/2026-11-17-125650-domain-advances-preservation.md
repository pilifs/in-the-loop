# Feature loop: domain-advances-preservation

Started 2026-11-17 12:56:50 UTC, no limit on cycles, session f28025bc-e46b-4a87-a943-bfb79dea5465, claude-opus-5-5 at high effort, after change lupovnmvlpnmukynpprxtssqkorzxvvl.

> Work on the brief in `llm-dlc/loops/domain-advances-preservation.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by naming what is yours: `sync.py commit --only PATH ... -m ...` takes those files and folders alone and leaves everything else uncommitted where it is. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'lupovnmvlpnmukynpprxtssqkorzxvvl..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message. Then read your inbox, `$(jj workspace root --name default)/llm-dlc/loop-summaries/domain-advances-preservation-inbox.md`, if it exists: each item under Open there is something the conductor needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did about it, and weigh it below your brief and the user's decisions, which come first, so an item that contradicts the brief is reported in Progress, by its id, not obeyed.

Brief `llm-dlc/loops/domain-advances-preservation.md` at sha256 42770bd1962837d98207bfd7a7c7f110157886ce15f40ad9e9f56f2addee2de2.

After each commit the session decides whether to go on:

> Steps 1 to 6 first, then 7 while a cycle can still realize a substantial part of it. Stop with `waiting on jobs ID ...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's. Keep the last line of Progress a status.

## Commits

- cycle 1, 2026-11-17 13:14:59, `trkpotroxpky`: The examples' router carries example 287's two new notes
  - decided to continue: This run has finished only step 1 of the brief's six (its two commits: the driver and first failure, then the router). The next piece, modelling warning-level logging so the check can reach the two sides' bcrypt, needs only me and doesn't wait on the queued job. Steps 2 to 6 come after it, so the status stays `working`.
- cycle 2, 2026-11-17 13:46:39, `zmvkptqzpvkx`: The pair of versions compares exceptions by class and starts each version as if it ran alone (verification pending)
  - decided to continue: This run has done step 1 and step 4: 287's first failure is reproduced, and the pair of versions now compares exceptions by class and starts each version from a fresh state. Steps 2, 3, 5 and 6 are left. The next piece needs only me and doesn't wait on the two queued jobs: modelling warning-level logging so 287's check can reach the two sides' bcrypt, then the boundary work of step 2. The status stays `working`.
- cycle 3, 2026-11-17 14:45:38, `unswkkxpxtvk`: The checker models a line logged at WARNING as spring-jcl logs it, so example 287's preservation reaches both sides' bcrypt
  - decided to continue: The loop should go on. Step 1 is now finished and step 4 is done: 287's check gets past every logging stop and fails where the brief predicted, at bcrypt's loops, which are identical in both releases. Step 2, finding the smallest way to relate the two sides there, is work I can do myself now, without waiting on any job or on the user, and steps 3, 5 and 6 follow from it.
- cycle 4, 2026-11-17 15:19:04, `wokytpkznxqx`: The pair of versions reads its scope on copies of its own and compares an exception by its class and the classes above it; 289 and 290 rerun (verification pending)
  - decided to continue: The loop should go on. Steps 1 and 4 are done, including both new holes the inbox reported in the comparison of the two versions. Steps 2, 3, 5 and 6 are still open, and step 2 is next: choosing how to relate the two sides at bcrypt's `crypt_raw` and `ekskey` loops, which are identical in both releases. That is work I can do now, without waiting on any job or on the user.
- cycle 5, 2026-11-17 16:25:21, `pswwplozumxo`: The preservation stream acknowledges inbox items I006 to I009 and takes the two soundness ones next
  - decided to continue: The loop should go on. Steps 2 and 3 are committed, but 287 is not decided yet. What comes next is work I can do now, without waiting on a job or on the user: - the two holes the inbox reported in my code (I006, I009); - making the rounds-loop search cheaper, so 287's job at bound 80 has a chance to finish; - then step 6, example 307. The two claim questions (I007, I008) are recorded for the user, and nothing waits on them.
- cycle 6, 2026-11-17 16:54:22, `lqkwokqqmsvx`: A logged record's getters may write its number fields and may not throw a Throwable, and the pair of versions tells apart two exception classes whose interfaces differ
  - decided to continue: The loop should go on: the reported soundness holes are fixed, and step 5 is work I can do now. Next I make the loop-invariant search in bcrypt's rounds cheaper, since the last probe ran out of time there. Then I queue 287's preservation job at bound 80. Steps 5 and 6 are still open, nothing waits on a job yet, and the two claim questions (I007, I008) need the user but block no step.
- cycle 7, 2026-11-17 18:10:24, `rmvpqswzxlyv`: The preservation stream acknowledges inbox items I010 and I011 and takes the tie's soundness hole next
  - decided to continue: The loop should go on: work that needs only me is left. That is I010 (the tie fingerprint's hole) and I011 (merge the default line, then rerun 289 and 290), and step 6 (307) needs no job result to start. Only 287's acceptance waits on job `20261117-180758-…`, so the status stays `working`. One thing to check at the start of the next cycle: `lib/src/bmc/loops.rs` changed on disk after my last commit, so I'll run `jj status` and see whose change it is before touching it.
- cycle 8, 2026-11-17 19:13:43, `kskmpmnymvoy`: Merge the default line and the challenge stream's tie countermodels; the code two versions are taken to share is closed against calls back through the JDK and takes in class initializers; 287 at bound 80, 289 and 290 rerun (verification pending)
  - decided to continue: The loop should go on. Step 6 (307: a driver, the slice artifacts, nullable password and salt, seven salts, bound 80, unwind 513) waits on no job and needs only me, and the outside review (I012) also puts it next. Only 287's decision and the 289/290 record wait on jobs `20261117-185613` and `20261117-185623`, so the status stays `working`.
- cycle 9, 2026-11-17 21:09:47, `uxyusvsvswus`: 307 has a driver on the route's slices, and the checker takes a call both versions share as one function of both: preservation verified and the mutant refuted in capped probes at the frozen bound (verification pending)
  - decided to continue: The loop should go on. Several pieces of work need only me: merging the default line, fixing 290's relative log path and rerunning it (I014), and the six reach countermodels (I019). After those comes testing the call rule against the specialist's fixtures and extending it to `crypt_raw` (I018), which is 287's third approach now that its job stopped at `BCrypt.key` again (I015). Only 307's verdicts wait on jobs, so the status stays `working`.
- cycle 10, 2026-11-17 21:31:39, `qopxypnnswvw`: The code two versions are taken to share resolves each field to the class that declares it and takes in the initializers the JVM runs; the observer's log path is absolute; 289 and 290 rerun (verification pending)
  - decided to continue: The loop should go on. The next piece needs only me: test the call rule against the `callee-countermodels` fixture on JDK 25 (I018), then extend it to `crypt_raw`. That is 287's third approach after its second job stopped at `BCrypt.key` (I015), and 287's "Done when" criterion can't be met or recorded without it. Only 307's verdicts and the 289/290 rerun wait on jobs, so the status stays `working`.
- cycle 11, 2026-11-17 23:14:21, `xuwlklyorpoy`: The checker takes bcrypt's crypt_raw as one function of both releases: a call on a receiver nothing reads after it, returning an array it makes; 287's preservation verifies in a capped probe at bound 80 (verification pending)
  - decided to continue: The loop should go on. Steps 1 to 6 now wait only on jobs: 287's `preservation` (`20261117-230459-…`), 307's two tasks (`20261117-210114-…`) and the 289/290 rerun (`20261117-213024-…`). Step 7, 288's preservation, needs only me, and the brief asks to take it while a cycle can still realize a substantial part of it. A profiling cycle on today's checker is such a part, and it may also show whether the extended call rule helps 288.
- cycle 12, 2026-11-17 23:33:25, `sqprlwkvwvso`: Merge the challenge stream's log, stand-in and supertype countermodels; a logged record's getter that can raise an Error, and a class whose header differs, are no longer taken as harmless or as the same code
  - decided to continue: The loop should go on: there is still work for me alone. 307's jobs have passed on the default line, so the next cycle can merge their results and accept both tasks through `accept.py`. Step 7, 288's preservation profiled first, also hasn't started. Only 287's acceptance waits on a job (`20261117-230459-…`), and the probes show this cycle's soundness fixes leave that verdict as it was.
- cycle 13, 2026-11-17 23:45:09, `qmsonuowwzwv`: Merge the default line's job results: 287's preservation established at bound 80 and accepted; 307's two tasks decided, refused by accept.py's entry check alone
  - decided to continue: Steps 1 to 6 are done: 287's preservation is decided and accepted, and 307's two tasks are decided, waiting only on the evidence stream's change to `accept.py`, which my work doesn't depend on. Step 7 hasn't started. Profiling 288's preservation in a capped probe and acting on what it shows is a substantial piece one cycle can still do.
- cycle 14, 2026-11-18 01:08:42, `mwvyxxyrvykt`: 288's preservation profiled: the binder's configuration and a last relational query hold the time, not the locale table; a call's record follows the objects a heap merge numbers again
  - decided to continue: Steps 1 to 6 are done, and step 7 is recorded as VF-031's next data point, as your decision D035 asks. Work that needs only this stream is still open from the inbox. I025 (merge the default line and accept 307's two tasks) completes the brief's 307 criterion. I023 is a soundness gap in this stream's shared-call rule, which the "make it sound" step makes this stream's to close.
- cycle 15, 2026-11-18 01:27:59, `vyzppnkuzxwz`: 287's accepted preservation is agreement on terminating runs, and the preservation stream takes the user's order for the rest of the run
  - decided to continue: Your D036 puts I023 next, and only this stream can do it: seven false proofs of this stream's shared-call rule must be refused or refuted, and `--no-shared-callees` must turn the rule off. After that comes another piece needing no one else: pointing 289's and 290's task records at job `20261117-213024` and accepting them on this line. 307's mutant waits on the evidence stream's harness fix, and that blocks nothing else.
- cycle 16, 2026-11-18 01:50:30, `puuwrruuyvpu`: The call taken as one function of both versions refuses what its outcome leaves out, and --no-shared-callees turns it off (I023)
  - decided to continue: The loop should go on. Next in your D036 order is pointing 289's and 290's preservation task records at job `20261117-213024` and running `accept.py` on both. That needs no new solver work and no one else, so it is a real step on the second "done when" criterion. After it, 288's close-out (recording its bound profile as VF-031's next data point) is also mine. Only 307's mutant waits on the evidence stream's harness fix.
- cycle 17, 2026-11-18 02:03:21, `wwoltylnpxtm`: 289's and 290's preservation answers rest on job 20261117-213024 and are accepted, by the user's D036
  - decided to continue: The loop should go on. `accept.py`'s fix for reading a pair's harness is now on the default line. So the next step in your D036 order is mine to do now: merge the default line, run the default tests and rerun `accept.py 307`, the last step for 307's mutant control. After that, I028's soundness fix in the one-function rule and 288's close-out also need only this stream, and no job or user decision is in the way.
- cycle 18, 2026-11-18 02:15:29, `srrlvkpwuqzn`: Merge the default line into the preservation line: 307's two answers are accepted, by the user's D036
  - decided to continue: The loop should go on. The brief's done criteria are now met: 287 is accepted, both of 307's answers are accepted, and the pairing countermodels pass with their limits stated. But I028 and I029 are two open soundness holes in this stream's own one-function rule. Fixing them is mine to do now, with no job or user decision in the way, and 288's close-out after them needs only this stream too.
- cycle 19, 2026-11-18 03:19:42, `nwylyxloopst`: Merge the challenge stream's record and allocation countermodels and close I028 and I029 in the one-function rule
  - decided to continue: The loop should go on for one more cycle. The done criteria are met, and I028 and I029 are now closed and verified. But Progress still says `working`, and D036's last point is mine alone: record 288's profile as VF-031's next data point and set the status to `done`. That needs no job and no decision from you.

## Summary

# Domain-advances run, preservation loop: summary after 19 cycles

## The short version

- **The brief's done criteria are met.** 287's and 307's preservation answers are accepted, with exception classes compared exactly. 289's and 290's answers are accepted from job `20261117-213024`. The pairing countermodels pass, with their limits written down.
- **The brief's status line still reads `- Status: working`, not `done`.** The loop stopped before cycle 20. That cycle would have recorded 288's profile as VF-031's next data point and set the status to `done`; it needs no job and no decision from you.
- **Nothing is pushed.** The working copy is empty, on top of `nwylyxlo` (38cedfd8). No verification jobs are pending or running; all 460 have been collected.
- **The last full default test run passed (54/54).** It ran on cycle 19's tree, d3687f052630.
- The revset covers **177 revisions**. It includes the evidence, challenge and state streams and the watcher's commits that merged into this line, not only mine, so they are grouped by stream below.

## 1. The preservation stream (this loop)

The pair check runs the old and new versions side by side and proves they agree. This stream made it sound on the real examples and decided 287, 307, 289 and 290.

| Change | What it adds | How it was verified |
|---|---|---|
| `oqsnoyom`, `trkpotro` | 287's preservation reaches the checker; it stops at `java.util.logging` WARNING, not at bcrypt. | Probe, and the example validated. |
| `kwyxmlns`, `zmvkptqz` | Merges the shared driver and the pairing countermodels. The pair now compares exceptions by class, and each version starts as if it ran alone. | Pairing countermodels refuted; job queued. |
| `unswkkxp` | A line logged at WARNING is modelled as spring-jcl logs it, so 287 reaches both versions' bcrypt. | Tests and a probe. |
| `wokytpkz`, `owrsowqm` | The pair reads its scope on its own copies and compares an exception by its class and superclasses. Two runs of one loop go on from one state. | Challenge countermodels refuted; 289 and 290 rerun as a job. |
| `lqkwokqq`, `lmyvttyt` | A logged record's getters may write number fields and may not throw. Exception classes whose interfaces differ are told apart. | The challenge stream's countermodels, now refuted. |
| `lxvttwmp`, `kskmpmny`, `qopxypnn` | The second run of a loop takes over the first's summary. The shared code is closed against calls back through the JDK, takes in class initializers, and resolves each field to the class that declares it. The observer's log path is made absolute. | Tie and reach countermodels refuted; jobs for 287 at bound 80 and for 289/290. |
| `uxyusvsv`, `xuwlklyo` | 307 has a driver on the route's slices. A call both versions share is taken as **one function of both** (for bcrypt, `crypt_raw`). | Capped probes at the frozen bound: 307 verified and its mutant refuted; 287 verified at bound 80. |
| `qmsonuow`, `vyzppnku` | 287's preservation is established at bound 80 and accepted, as agreement on runs that terminate. | Job result, accepted through `accept.py`. |
| `mwvyxxyr` | Profiles 288's preservation: the time goes to the binder's configuration and a last relational query, not to the locale table. | Probes at bounds 3 to 6. |
| `puuwrruu` (I023) | The one-function rule refuses what a call's outcome leaves out. `--no-shared-callees` turns the rule off. | Tests, plus probes on the seven examples. |
| `wwoltyln` | 289's and 290's preservation answers rest on job `20261117-213024` and are accepted, by your D036. | Job passed; accepted through `accept.py`. |
| `srrlvkpw`, `lxosnzun` | Merge the default line in: 307's two answers are accepted (D036). | Default run after the merge. |
| `nwylyxlo` (I028, I029) | Merges the challenge stream's record and allocation countermodels. A call's record now keeps the cells its array result held when the call returned. Its outcome bits are keyed by the call. Calls that keep what a loop makes are refused: reference arrays, the application's own objects, and String joins and appends. | The `stale` countermodel is refuted only with the fix in, and `swapped` is now refuted too. `kept` is undecided. Each refusal is shown necessary for its own countermodels, and each countermodel differs on a JVM. Probes: 287 and 307 verified, 307's mutant refuted, 289 and 290 verified. `--changed` tests and the default run pass. |

Also: `pswwploz` and `rmvpqswz` acknowledge inbox items. Every inbox item, I001 to I029, is acknowledged in Progress.

**Limits written down:**
- No countermodel was found for the merge of an opaque String result: the timebox ran out after two shapes.
- The challenge stream's `callee-countermodels/check.py --rule-landed` expects `same`, `copied` and `parsed` to be verified. These are now refused, because `new Hash()` and `append` fall under I029's refusals. That loses precision, not soundness.

## 2. The challenge stream (countermodels)

About 25 commits. Each adds false proofs, or answers wrongly accepted, that the checker or `accept.py` let through, each shown wrong on a JVM. They cover:
- loop invariants and checked summaries (`smnuqrou`, `uktunxxo`);
- the pair of versions (`ada891f4`, `roqtqlpm`, `pklttqzw`, `vtwrpxps`, `wuotsmsr`);
- ties and the identical-bytecode shortcut (`qnlomnmx`, `tqmpowvx`, `zmpzxkqn`);
- write sets and effect contracts (`synvlnls`, `qmtxwupn`, `ukukylmu`, `uqrzluvx`);
- the models on request under assumed gaps (`lqyqxwqv`);
- observed initializers and their bindings (`mqkqvvmw`, `klqnuoxw`, `plqpmmop`);
- stand-ins and logged records (`mnwtrnrp`);
- the acceptance check (`zwrpkwnl`, `xnqlyxnw`).

Each was handed to the stream that owns the rule, which fixed it.

Three commits found wrong implementations that the frozen claims accept:
- `lqvlvwsm`: one each for 287, 307 and 286's protected state.
- `yqwmukvo`: two wrong 6.1.14 binders satisfy 288's decided answer and the state stream's binding check.
- `rqtklpxv`: two wrong 5.6.4 matchers satisfy 289's security and preservation claims.

## 3. The state stream (286 and effect contracts)

About 27 commits (`kztoupry` … `kmytvuop`):
- A write set, `prove --writes`, and effect contracts that stand in for calls, each tightened against the challenge stream's countermodels.
- Stand-ins sampled against a library method on a JVM (`prove --stand-in`).
- Models on request: ArrayDeque, HashSet, LinkedHashSet, StringJoiner and PropertyChangeEvent.
- 286's protected-state claim is refuted on 5.3.18 and accepted (`txzyyurs`). The refutation was later re-accepted from a clean job, `20261118-011232` (`zwnwruqs`).
- 288's binding under its locales: kept on 6.1.14, refuted on 6.1.13 under tr-TR (`ownxunnx`).

Verification was by probes, jobs, and the challenge stream's countermodels refused or refuted (`vulpuymq`).

## 4. The evidence stream (`accept.py` and drivers)

- Every example's driver records what it ran (`rkxyyqwn`).
- `accept.py`:
  - refuses steps that are not a plain driver run (`wxpoysws`, `kqxwrwrx`);
  - requires a non-vacuity witness (`ymzlyksq`);
  - reads a pair task's harness and refuses a `--work` outside the step's folder (`mxslxvzk`, I015 first half);
  - takes an overload named by its descriptor (`utzknmuo`).
- Observation binding was tightened (`lzpqszyo`, `mmnoqopr`, `vqquvmnm`).
- Answers beside the route were accepted with no limit from reruns: 289, 290, 286, 287, and 288's fixed-security.
- VF-030 was closed: the Rust proof tier passed whole (`nsnxmlmt`).

## 5. Watcher and run commits

The rest record job results ("Record verification results"), stream merges, inbox messages, your answers (D023: `npqmxyrx`, `povqtmtx`), and the findings VF-037 to VF-043.

## Verification jobs

- **Pending or running:** none. 460 collected; the report shows 125 failed in total, almost all from before this run.
- **Failed during this run** (all since superseded):
  - `20261117-180758` and `20261117-185613`: 287 at bound 80 could not be verified at `BCrypt.key`'s loop. Superseded by the one-function rule; 287 was then established and accepted.
  - `20261117-181750`: 286 protected state failed on a relative `-Xlog` path. Fixed and rerun; accepted from `20261118-011232`.
  - `20261117-185623`: 290 failed on the same relative `-Xlog` path. Rerun as `20261117-213024`, passed and accepted.

## Warnings to judge before pushing

`sync.py check` reports 0 errors, 59 warnings and 1244 notes (the notes need no action).

1. **4 allowlist proposals** await your `python3 llm-dlc/tools/sync.py allow approve`. Among them are 307's public bcrypt test vectors and `test_accept.py`'s made-up path.
2. **55 `long-token` warnings (`If6…fW`, 53 chars)** in session `6c5c7798` and in this session `f28025bc`. This is 307's public bcrypt test vector, already proposed for the allow list (`ywlkutrx`).
3. **`other-home-dir` in session `7ece8184`:** three logs (×12, ×4, ×15) and the run file `runs/2026-11-17-163151-domain-advances-evidence.md` (×1). Look with `sync.py review show`. Nobody has judged these yet.

## Needs your decision

- **Claims that let wrong implementations through.** Replacing any claim file is your decision:
  - **288:** two wrong 6.1.14 binders satisfy its answer (`yqwmukvo`).
  - **289:** two wrong matchers satisfy its claims (`rqtklpxv`). Inbox I026, about 289's probes, was not taken up.
  - **287:** a check-only guard satisfies its claims (`lqvlvwsm`, VF-039). You deferred a claim on `encode` to after the run.
  - **307:**
    - a wrong implementation satisfies its claims (`lqvlvwsm`);
    - its frozen claim cites a specification `getBytes(String)` does not have (VF-038). You deferred the restatement and I008.
  - **286:** a wrong implementation satisfies its protected-state claim (`lqvlvwsm`). It binds one value (VF-040); the two-value claim is to be added after the run. A corrected formalization is proposed as a new claim file (`kmytvuop`).
  - **290:** a restated preservation claim is prepared for you to freeze (`nzsypymy`). By D023 the frozen one stays for this run.
- **288's preservation is still open.** Bounds 3 and 4 verify in 13 s and 42 s. Bounds 5 and 6 are undecided after 150 s. The full bound runs out at about 5,400 s (VF-031: 1h32m). The time goes to `canonicalPropertyName` configuring the binder (about 72 of 136 s) and to the final relational `agree` query (15.9 s at bound 4). Ending it at that wall, and setting the brief's status to `done`, is the one step left from D036.
- **The outside review of acceptance (VF-041 to VF-043)** and **I015's second half** for `accept.py`: open with their owners.
- **VF-037:** `run-streams.sh` cannot restart a single stream.
- **/tmp:** its per-user quota filled up during cycle 19, and Bash output was lost. I deleted only my own scratch files. Clearing the rest is your decision.
- **Pushing:** when you choose, run `python3 llm-dlc/tools/sync.py push --bookmark main` or `/publish`.

Ended 2026-11-18 03:22:38 after 19 cycle(s).
