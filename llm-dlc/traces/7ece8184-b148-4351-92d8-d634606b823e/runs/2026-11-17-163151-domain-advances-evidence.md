# Feature loop: domain-advances-evidence

Started 2026-11-17 16:31:51 UTC, no limit on cycles, session 7ece8184-b148-4351-92d8-d634606b823e, claude-opus-5-5 at high effort, after change mmnoqoprrzmrtqovvnqruywlxrzwkmpu.

> Work on the brief in `llm-dlc/loops/domain-advances-evidence.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by naming what is yours: `sync.py commit --only PATH ... -m ...` takes those files and folders alone and leaves everything else uncommitted where it is. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'mmnoqoprrzmrtqovvnqruywlxrzwkmpu..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message. Then read your inbox, `$(jj workspace root --name default)/llm-dlc/loop-summaries/domain-advances-evidence-inbox.md`, if it exists: each item under Open there is something the conductor needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did about it, and weigh it below your brief and the user's decisions, which come first, so an item that contradicts the brief is reported in Progress, by its id, not obeyed.

Brief `llm-dlc/loops/domain-advances-evidence.md` at sha256 4b6fdf081d0dae8f88c3d203e0ed5c72790b4f2b49739dc704f05eecda5ee980.

After each commit the session decides whether to go on:

> Steps 1 to 6 in order, 7 whenever it comes up. Stop with `waiting on jobs ID ...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's. Keep the last line of Progress a status.

## Commits

- cycle 1, 2026-11-17 16:39:53, `qxstltmqkoot`: test_accept.py's pipeline build step uses a path outside any home directory; the made-up one is proposed for the allow list
  - decided to continue: The loop should go on. This cycle closed I010, but I011 is still open and needs only this stream: the observed-initializer check still accepts three cases (a replaced lambda, an object another class holds, and a default locale changed during initialization) where a JVM gives a different result. I012 handed the 289/290 rerun to the preservation stream and left the freeze as your open question, so Progress says `working` and the next cycle has work it can finish on its own.
- cycle 2, 2026-11-17 17:06:28, `vqquvmnmmoqx`: An observed initializer is refused where it wrote into a value another class holds or changed the JDK's settings: every value of a class it initialized besides is compared in full
  - decided to stop: The loop should stop, because Progress now ends with `- Status: done` and none of what is left needs only this stream. I011 is committed (`vqquvmnm`), so the binding is in place and all the countermodels are refused, which meets the Done-when's third row; the first row waits on the preservation stream's rerun of 289's and 290's preservation (I012). 290's restated claim waits on your freeze, which the brief records as yours to give, and the allow-list proposal for `fa4e66dc` waits on your approval.

## Summary

## Run summary: domain-advances-evidence feature loop

The loop stopped with the brief's status at `done`. Nothing left for this stream can be done by it alone. The run made three commits, listed oldest first.

### 1. `wxpoysws`: `accept.py` refuses any job step that isn't a plain driver run
- **Why:** The challenge stream (inbox I010) found that the step check only read a step's words up to the task name and the first `--work`. Steps run under `bash -c`, so four kinds of job got through:
  - a shell suffix after the driver that rewrites the outcome;
  - an earlier step that replaces the driver or writes the outcome folder;
  - `--work` given twice, where the check read the first and the driver uses the last;
  - `--jvmcontract` pointing at another binary.
- **What changed:**
  - Every step must now be `python3 [-I] examples/NNN-.../proofs/prove.py TASK`, allowing only `--timeout`, one `--work` and the trial flags, all as plain words.
  - A job's `env` and a step's `cwd` are refused.
  - The result's steps must match the job file's, apart from the pipeline's own cargo build as step 0.
  - A later step that writes the same outcome folder is refused.
- **Verified:**
  - Seven new controls in `test_accept.py` (`StepsPastTheFix`). Six of them fail on the old `accept.py`; the seventh checks that honest job shapes are still accepted.
  - Run on examples 286 to 290, `accept.py` still accepts the same 13 answers. 289's and 290's preservation answers are still refused, as before.
  - `test_accept.py` passes all 45 tests, and `test_costs.py run --changed` passed 7 of 7. One unrelated flaky JBMC unit test passed on its second run.
  - The `test_costs.py` estimate, tag and lint steps all agree.

### 2. `qxstltmq`: made-up home path removed from a test fixture
- **Why:** The previous commit's test fixture used a made-up `/home/...` path. The trace check flags it as another user's home directory: finding `fa4e66dc`, a warning in this session's log.
- **What changed:** The fixture now uses `/opt/rust/bin/cargo`. The copies of the path already in the session log can't be edited, so I proposed the finding for the allow list.
- **Verified:** `test_accept.py` passes all 45 tests.

### 3. `vqquvmnm`: observed initializers refused when they write outside their own class or change JDK settings (I011)
- **Why:** The challenge stream's binding countermodels (I011) showed three proofs that a real JVM contradicts:
  - `bc.Boxed` writes into an object that another class holds;
  - `bc.Rehooked` swaps one of `Hooks`' lambdas for another;
  - `bc.Relocaled` sets the default locale.
- **What changed:**
  - **Values are described in full.** The observer (`ObservedInitializer.java`, new `Describe` and `Pool` classes) now fully describes every value that each class initialized alongside the observed one holds, both after the run and when that class is initialized alone:
    - an application object by all the fields its classes declare;
    - a lambda by the method it calls, read from its constant pool through new `--add-exports` flags, plus its captured values;
    - a JDK collection by its elements;
    - a float by its bits.
  - **Mismatches and undescribable values are refused.** `observe` in `lib/src/observed.rs` compares these descriptions and refuses any value it can't describe, saying why.
  - **JDK settings are checked after the run.** The observer re-reads the locale, the time zone and the system properties after initialization, and any change is refused.
  - **Output format:** it gains `on.changed`, plus `d` or `why` beside `u`.
  - **Copied fixtures:** the countermodel fixtures and their JVM test were copied unchanged from `klqnuoxw`.
- **Verified:**
  - The new test in `observed_countermodels.rs` and a new unit test pass. `run --changed` passed 28 of 28.
  - Example 290 still verifies. Capped probes of fixed-security and preservation passed with the same path counts as before (659 and 573). All values held by its nine alongside-initialized classes are described and match when each is initialized alone.
  - The result is recorded in:
    - 290's notes;
    - VF-033;
    - `lib/README.md`;
    - the module doc in `observed.rs`, which also lists what is still not compared.
- **Sent on:** an inbox item about the format change went to the state stream (I014).

### Verification jobs
- This run submitted no jobs. Nothing is pending or failed in this workspace.
- Four jobs are recorded on another head (`e6972eaa`), which this working copy isn't on. They come in with a merge and won't be rerun:
  - 286: protected-state tasks;
  - 287: preservation through the adapter;
  - 289 and 290: two preservation reruns.

### Warnings to judge before pushing
`sync.py check` reports 0 errors and 4 warnings, all from the same finding:
- **`fa4e66dc`:** the made-up `/home/someone` path appears 52 times across three logs of this session. It is a false positive and is already proposed for the allow list. You can approve it in your own terminal with `python3 llm-dlc/tools/sync.py allow approve`; nothing waits on it.

### Waiting on you or other streams
- **290's restated claim (D023):** you need to decide whether to freeze it.
- **Preservation rerun for 289 and 290 (I012):** this belongs to the preservation stream. Its results are probably among the jobs on `e6972eaa` and need that merge. The first done-when row waits on it.
- **The brief is out of date:** its "Where it stands" paragraph no longer matches the results. I couldn't fix it because I may only edit `## Progress`.

Ended 2026-11-17 17:07:56 after 2 cycle(s): the session decided to stop; the brief says done.
