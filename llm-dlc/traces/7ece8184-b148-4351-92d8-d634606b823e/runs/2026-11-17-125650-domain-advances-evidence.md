# Feature loop: domain-advances-evidence

Started 2026-11-17 12:56:50 UTC, no limit on cycles, session 7ece8184-b148-4351-92d8-d634606b823e, claude-opus-5-5 at high effort, after change lupovnmvlpnmukynpprxtssqkorzxvvl.

> Work on the brief in `llm-dlc/loops/domain-advances-evidence.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by naming what is yours: `sync.py commit --only PATH ... -m ...` takes those files and folders alone and leaves everything else uncommitted where it is. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'lupovnmvlpnmukynpprxtssqkorzxvvl..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message. Then read your inbox, `$(jj workspace root --name default)/llm-dlc/loop-summaries/domain-advances-evidence-inbox.md`, if it exists: each item under Open there is something the conductor needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did about it, and weigh it below your brief and the user's decisions, which come first, so an item that contradicts the brief is reported in Progress, by its id, not obeyed.

Brief `llm-dlc/loops/domain-advances-evidence.md` at sha256 4b6fdf081d0dae8f88c3d203e0ed5c72790b4f2b49739dc704f05eecda5ee980.

After each commit the session decides whether to go on:

> Steps 1 to 6 in order, 7 whenever it comes up. Stop with `waiting on jobs ID ...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's. Keep the last line of Progress a status.

## Commits

- cycle 1, 2026-11-17 13:11:33, `zlxkxlstvktr`: The evidence stream acknowledges inbox item I001
  - decided to continue: The loop should go on. Step 1 still waits on the foundation's two jobs, but the work after it doesn't depend on them: step 3 can queue the 286 and 287 `mutant-security` reruns with the new drivers now, and steps 4 to 6 (the vacuity control, binding observed initializers, and the Python proof-tier job) need only me. The brief's status line already says `working`, which still fits.
- cycle 2, 2026-11-17 13:28:34, `kynmlzxkpzpm`: Example 289's four answers beside the route are accepted from the job that recorded what it ran, with no limit
  - decided to continue: The loop should go on. Two cycles have finished step 2 and example 289's half of step 1, and the only thing still waiting on a job is the lemma half of step 1. The work that comes next needs only me: submitting the step 3 reruns of 286, 287 and 290 with the new drivers, then the vacuity control and the observed-initialization binding. The brief's status line already says `working`, which still fits.
- cycle 3, 2026-11-17 13:38:47, `mktymxvtmltt`: The trace check makes a note, not an error, of a shared commit another stream's session stamped, while that stream's manifest lists the log
  - decided to continue: The loop should go on. Step 3's reruns and the lemma job are queued, so step 3's records and step 1's lemma half wait on those jobs. Steps 4 to 6 need only me and don't depend on them: the vacuity control and `accept.py`'s refusal of a vacuous establishment, the observed-initialization binding, and queuing VF-030's proof-tier jobs. The brief's status line still rightly says `working`.
- cycle 4, 2026-11-17 13:47:11, `suuomluxkmpx`: Step 1's lemma half is done and example 290's four answers are accepted from the rerun that recorded what it ran
  - decided to continue: The loop should go on. Steps 1 and 2 are done, and step 3 now waits only on the 286, 287 and 288 reruns, which are still running. Step 4, the check that a preservation result doesn't pass vacuously, needs only me, and so do steps 5 and 6, so the status rightly stays `working`.
- cycle 5, 2026-11-17 14:04:12, `ymzlyksqouqq`: A preservation proof is non-vacuous only with a witness outside the allowed change, and accept.py asks the outcome to say so
  - decided to continue: The loop should go on. Step 4 is done. Step 3's remaining reruns and the new 289/290 preservation rerun wait on jobs and a merge. But step 5 (binding observed initializers, with I004) and step 6 (queuing VF-030's proof tier) need only me, so the status rightly stays `working`.
- cycle 6, 2026-11-17 14:12:24, `mzllzmkqlsyq`: Example 288's fixed-security is recorded beside the route from the rerun that recorded what it ran, and accept.py accepts it with no limit
  - decided to continue: The loop should go on. Step 3's 288 part is done. What's left of step 3 waits on the 286 and 287 jobs and on the 289/290 preservation rerun, but step 5 needs only me: merge the challenge stream's `mqkqvvmw` onto this line, then bind observed initializers and make I004's test pass. Step 6, queuing the VF-030 proof-tier jobs, also needs only me, so the status rightly stays `working`.
- cycle 7, 2026-11-17 14:19:27, `wowqurkuylvp`: Example 286's three answers beside the route are accepted with no limit from the rerun that recorded what it ran
  - decided to continue: The loop should go on: step 3 is done for 286, 288 and 290, and what's left of it waits on 287's job and on the 289/290 preservation rerun after the lines meet. Step 5 needs only me: merge the challenge stream's `mqkqvvmw`, then bind observed initializers so that I004's test passes. Step 6, queuing the VF-030 proof-tier jobs, needs only me too, so the status stays `working`.
- cycle 8, 2026-11-17 14:49:17, `lzpqszyooynr`: An observed class initializer is bound to what it was observed on, and the run ends where it is not
  - decided to continue: I can do the next pieces myself: 287's rerun job is back, so its records and `accept.py 287` are ready to finish. After that come 290's restated preservation claim (I prepare it, you freeze it) and step 6's VF-030 jobs. Only the 289/290 preservation rerun waits on another stream, so no stop status applies yet.
- cycle 9, 2026-11-17 14:55:31, `krptozvmlptx`: Example 287's three answers beside the route are accepted with no limit from the rerun that recorded what it ran
  - decided to continue: The loop should go on: work that needs only me is still left. That is preparing 290's restated preservation claim (option B), with the freeze recorded as yours to give, and then step 6, queuing the VF-030 jobs and finding out why the Python proof tier counts 0 tests. The only waiting piece is the 289/290 preservation rerun, which needs the preservation stream's `zmvkptqz` on this line first, so no stop status applies yet.
- cycle 10, 2026-11-17 15:14:18, `nzsypymyqxtw`: Example 290's preservation claim restated to compare what the matchers are, prepared for the user to freeze
  - decided to continue: The loop should go on, because step 6 (VF-030) needs only me. It means queuing the Python and Rust proof-tier jobs and finding out why the estimate counts 0 Python proof tests. Step 5's own share is done: 290's restated claim waits on your freeze and a checker change. Step 3's last piece waits on the preservation stream's `zmvkptqz` reaching this line. Neither of those is a reason to stop while step 6 is undone.
- cycle 11, 2026-11-17 15:22:58, `nosxvuntumnm`: VF-030's Python half was empty and the default run covers it; the Rust proof tier is queued after the foundation's checker changes (verification pending)
  - decided to continue: The loop should go on, because one piece of work still needs only me. Inbox item I007 reports seven ways `accept.py` accepts an answer its evidence doesn't give; the fix is adding the challenge stream's tests and closing those holes. `accept.py` is this stream's own code, and the Done-when's first row depends on it being right. The rest waits on others: VF-030 on the Rust proof-tier job, 290's restated claim on your freeze, and the 289/290 rerun on `zmvkptqz` reaching this line. None of that is a reason to stop while I007 is open.
- cycle 12, 2026-11-17 15:33:07, `kqxwrwrxwkvm`: accept.py refuses or leaves unbound the seven answers the challenge stream's controls showed it accepting without evidence
  - decided to stop: The loop should stop, because none of what's left needs only me. With I007 done, the next piece is closing VF-030, and that waits on job `20261117-152112-the-rust-proof-tier-after-the-domain-adv`, which hasn't started. The other two pieces aren't mine to move: the 289/290 preservation rerun needs `zmvkptqz` merged onto this line, and 290's restated claim needs your freeze. The brief's status line already reads `waiting on jobs 20261117-152112-the-rust-proof-tier-after-the-domain-adv`.

## Summary

# Domain-advances evidence stream: summary of the run (12 cycles)

The run stopped while waiting on one verification job. Of the brief's steps, 1, 2 and 4 are done, and 3 and 5 are done as far as this stream can take them. Step 6 (VF-030) waits on its job. `accept.py` now accepts every answer of 286, 287, 288 and 290 beside the route with no limit. It also accepts 289's three security answers. It refuses 289's and 290's preservation until they are rerun on the vacuity fix.

## Commits, oldest first

**`rkxyyqwn`: every driver records what it ran (step 2)**
- **What it adds:**
  - `examples/tools/beside_route.py` replaces the code that each of the drivers for examples 286 to 290 had its own copy of.
  - Each driver now records the claim, the bound, the JARs, the adapter, the verifier binary and the driver itself in `evidence.json`.
  - A run ends if its mutant's JAR is not the one the mutant replay ran.
  - `--max-array-length` or `--unwind` marks the run as a trial.
- **Finding:** the drivers of 286, 287 and 288 built their mutant with a different recipe than the route's, so their mutant JAR was never the bytes the replay ran. The shared module reproduces each example's replay JAR exactly.
- **Verified by:** the new `test_beside_route.py` (unit and tool tiers), `run --changed`, and `validate_example.py` for 286 to 290. No proofs were run.

**`yypzyxmw`, `mqkqvvmw`: the challenge stream's countermodels, merged into this line by `tswurxzv`**
- **What they add:**
  - Five false proofs of agreement between a pair of versions. These were handed to the preservation stream.
  - Five countermodels of observed initializers and class files. Three went to this stream; the class-path reader now refuses the other two (`ClassPath::refused`).
- **Verified by:** the challenge stream's own tests. After the merge, `validate_example.py` 289 and 290 and `run --changed` passed.

**`zlxkxlst`: acknowledges inbox item I001**
- I001 is the `test_brief_run.py` hang or leak inside a stream. Nothing changed.

**`vsttntoz`: reruns of 286, 287, 288 and 290 at the frozen bound (verification pending)**
- It queued four jobs, one per example, using the new drivers. All four have since passed and are used by the commits below.

**`kynmlzxk`: all four of 289's answers accepted with no limit**
- **What it adds:**
  - The results of job `20261117-122454-example-289-…`, taken unchanged from the collector.
  - A fix to the artifacts check: a constructed mutant's JARs are now looked up under its base revision.
- **Verified by:** `test_accept.py` (29 tests, including a control that fails without the fix), `validate_example.py 289` and `run --changed`.

**`mktymxvt`: `sync.py check` downgrades a shared commit stamped by another stream's session to a note**
- **Why:** the preservation stream merged `rkxyyqwn` and restamped it. After that, every commit on this line failed with "has no manifest".
- **What it adds:** that case is now a note, unless the commit's own tree holds that session's manifest. Then a merge lost it, and it stays an error.
- **Verified by:** two new controls in `test_workspaces.py` (14 tests pass), and `check` reporting 0 errors.

**`suuomlux`: step 1's lemma half done; 290's four answers accepted with no limit**
- **The lemma job passed:** `simpleMatch` is still proved by induction under the tightened lemma checks, and 286's and 288's fixed-security still verify. No earlier result rested on the hole.
- **290:** its rerun job passed with the same verdicts and path counts as before.
- **Verified by:** `accept.py 290`, `validate_example.py` 286, 288 and 290, and `run --changed`.

**`ymzlyksq`: vacuity control (step 4)**
- **The hole:** a proof about a pair of versions counted as non-vacuous even when every assumed input lay inside the allowed change. Replacing 289's `--unchanged-unless` with `true` still gave a non-vacuous proof.
- **What it adds:**
  - A second check for a verified pair with an allowed change, which records `vacuity.outside`.
  - `accept.py` refuses an outcome that doesn't show a witness outside the change.
- **Effect:** 289's and 290's preservation answers are now refused until they are rerun.
- **Verified by:** a new tool-tier test in `lib/tests/pairing.rs` (it fails without the fix), three cases in `test_accept.py`, capped probes, `estimate`, `tag` and `lint`, and `validate_example.py` 289 and 290.

**`mzllzmkq`: 288's fixed-security recorded beside the route and accepted with no limit (13 checks)**
- 288's refutations and preservation stay undecided (VF-031).
- **Also:** answers inbox item I006. `Slot` and `Object` are unchanged; `Observed` gains a record of what the observation was taken on.
- **Verified by:** `validate_example.py 288`, `build.py --index-only` and `run --changed`.

**`wowqurku`: 286's three answers accepted with no limit**
- 286's mutant-security had been refused before this.
- **Verified by:** `accept.py 286`, `validate_example.py 286` and `run --changed`.

**`lzpqszyo`: an observed class initializer is bound to what it was observed on (step 5, VF-033's audit half, I004)**
- **What it records:** the class file's hash, the class path, the JDK, the locale, the properties read, and the classes initialized alongside with their static state.
- **What `observed.rs` now ends the run on:**
  - a different class path, or a different class file from the one the tool reads;
  - the review's cross-class countermodel;
  - a Turkish, Azeri or Lithuanian locale.
- **Verified by:**
  - the I004 test in `observed_countermodels.rs` and four unit tests;
  - capped probes of 290, which verify again with the same path counts;
  - a default run after the merge, which passed.

**`krptozvm`: 287's three answers accepted with no limit**
- Its rerun job passed in 44m48s.
- **Verified by:** `accept.py 287`, `validate_example.py 287` and `run --changed`.

**`nzsypymy`: 290's preservation claim restated to compare the matchers themselves (VF-033, the option B you chose), ready for you to freeze**
- **What it adds:** a new adapter, `MatcherDescriptionAdapter#describe`, and `claims/lone-dispatcher-matchers-preserved.json`. The old claim and adapter are unchanged.
- **JVM check:** the new adapter agrees on all 28 probes that use the DispatcherServlet alone. On 132 of the other 140 it differs, where the fix changes behaviour by design.
- **Probes:**
  - At bound 1 the checker stops at a gap: `StringBuilder.append(Object)`.
  - At the frozen bound it reached the 4 GiB cap.
  - So the proof needs that gap closed first, and then one job.

**`nosxvunt`: VF-030 (verification pending)**
- It queued the whole Rust proof tier: job `20261117-152112-…`, about 55 minutes, 4 CPUs, 8 GiB.
- VF-030's Python half asks for nothing: no Python test is tagged proof tier, and the default run covers every Python test.

**`kqxwrwrx`: `accept.py` closes the seven holes the challenge stream's controls found (I007)**
- **What changed:**
  - Entry names are matched whole, not as substrings.
  - A step must be exactly `python3 [-I] <folder>/proofs/prove.py TASK`.
  - The driver's hash must match the driver at the job's source commit.
  - The domain uses the claim's bound alone.
  - A witness may be null only for a nullable parameter.
  - When the claim has an assumption, a refutation needs the harness source that checks it.
  - An equivalence task with no allowed change is refused if the pair it ran with has an allowed change (`meantToChange`).
- **Verified by:**
  - 8 new tests, which fail against the old `accept.py` with 11 failures;
  - 38 tests passing in `test_accept.py`;
  - 286 to 290 still accepting the same 13 answers, and still refusing 289's and 290's preservation;
  - `lint` and `run --changed` (7 of 7).

## Verification jobs

- **Pending:** `20261117-152112-the-rust-proof-tier-after-the-domain-adv`. It has not started. VF-030 closes when it passes.
- **Failed:** none.
- **Recorded on another line (`e02fc12bea4c`), not merged here:** four jobs from other streams. One is `20261117-151521-examples-289-and-290-preservation-once-m`, the preservation stream's rerun. Those results reach this line only when it is merged.

## `sync.py check`

0 errors, 0 warnings, 642 notes. Nothing needs your judgement before a push.

## What needs you

1. **Freeze 290's restated claim (VF-033).** This means recording its hash in a claims ledger, pointing the preservation task at the new file and listing the adapter source. Before the proof job is worth running, the `StringBuilder.append(Object)` gap in `MvcRequestMatcher.toString` has to be closed.
2. **Merge the preservation line (`zmvkptqz`, and `e02fc12bea4c` with its results) onto this line.** Until then, 289's and 290's preservation answers stay refused for lack of `vacuity.outside`, and their rerun can't be done here.
3. **Before a push:** no passing default run covers the head yet. The last one was at tree `bc1caa8a8827`, before `kqxwrwrx`. `sync.py push` will therefore run the default run inline.

## Other things to know

- **The brief is out of date:**
  - The "Where it stands" paragraph is stale. Every driver now records `evidence.json`, and the accepted answers are the ones listed above.
  - Step 6 asks for a Python proof tier that doesn't exist.
- **A flaky test:** `llm-dlc/tools/test_brief_run.py` (inbox I001) fails inside a stream because it inherits `RUN_STREAMS_WATCHER`. It passes with that unset. It cost about 49 s of reruns in cycle 12, and `run --changed` needed it unset or rerun in several cycles.
- **Example 288:** its two refutations and its preservation are still undecided at the frozen bound (VF-031).

Ended 2026-11-17 15:34:43 after 12 cycle(s): the session decided to stop; the brief says waiting on jobs 20261117-152112-the-rust-proof-tier-after-the-domain-adv.
