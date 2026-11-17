# Feature loop: domain-advances-evidence

Started 2026-11-17 16:05:44 UTC, no limit on cycles, session 7ece8184-b148-4351-92d8-d634606b823e, claude-opus-5-5 at high effort, after change kqxwrwrxwkvmutrkvpklpuqsnmpumkop.

> Work on the brief in `llm-dlc/loops/domain-advances-evidence.md`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run `jj status` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its `## Progress` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by naming what is yours: `sync.py commit --only PATH ... -m ...` takes those files and folders alone and leaves everything else uncommitted where it is. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its `## Progress` section if it has one (it carries over from earlier runs of this loop) and by the commits since (`jj log -r 'kqxwrwrxwkvmutrkvpklpuqsnmpumkop..@-'` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its `## Progress` section; if it has one, update it in the same commit with what this piece did and what comes next, and if it ends with a `- Status:` line, keep that line current there too: `working` while a piece of work that needs only you is left, otherwise the status the brief's `## Loop until` gives for stopping (`waiting on jobs ID ...` with the job ids, `done`, or `blocked: ...` with what needs the user or another stream). If the rest of the brief is wrong or out of date, say so in the commit message. Then read your inbox, `$(jj workspace root --name default)/llm-dlc/loop-summaries/domain-advances-evidence-inbox.md`, if it exists: each item under Open there is something the conductor needs you to act on, so acknowledge each by its id in this cycle's Progress update with what you did about it, and weigh it below your brief and the user's decisions, which come first, so an item that contradicts the brief is reported in Progress, by its id, not obeyed.

Brief `llm-dlc/loops/domain-advances-evidence.md` at sha256 4b6fdf081d0dae8f88c3d203e0ed5c72790b4f2b49739dc704f05eecda5ee980.

After each commit the session decides whether to go on:

> Steps 1 to 6 in order, 7 whenever it comes up. Stop with `waiting on jobs ID ...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked: ...` when the next step is the user's. Keep the last line of Progress a status.

## Commits

- cycle 1, 2026-11-17 16:08:52, `nsnxmlmtukmt`: VF-030 is closed: the Rust proof tier passed whole after the foundation's checker changes and the evidence line's
  - decided to continue: The loop should go on. This cycle closed VF-030, and the last line of Progress is `working`, because two new inbox items need only me. One is I008: the observation binding misses writes to a superclass or superinterface, properties read through `Properties.get`, the time zone and environment variables. The other is I009: keep the state stream's naming of a lambda's class, which touches the same file. The other open items, the 289/290 preservation rerun and 290's claim freeze, wait on a merge or on you, but I008 with I009 can be done now.
- cycle 2, 2026-11-17 16:29:18, `mmnoqoprrzmr`: An observation is bound to its supertypes' state, to a property read through the Properties map, to the time zone and to the environment; the state stream's lambda naming is kept
  - decided to stop: The loop should stop. This run has closed VF-030 and done I008 and I009, so the inbox is empty and the observation binding covers all five of the challenge stream's countermodels. Two things are left, and neither can be done from this stream: the 289/290 preservation rerun needs `zmvkptqz` merged onto this line, and 290's restated preservation claim needs your freeze. Progress already ends with that `blocked:` status.

## Summary

# Loop summary: the domain-advances evidence stream

This run made two commits, both on this workspace's line. Neither is pushed, and nothing was pushed.

## Commits

### `nsnxmlmt` (d8d5208d): VF-030 is closed
- **What it adds:**
  - The result of job `20261117-152112-the-rust-proof-tier-after-the-domain-adv`, taken unchanged from the collector's commit `xnlsuqmu`.
  - A note in `verification/findings.md` closing VF-030.
  - The job ran the whole Rust proof tier (`cargo test --release -- --ignored`) on top of the foundation's checker changes and this line's checks on version pairs and observations. That is all 19 tests `costs.json` marks ignored, including VF-018's three heap tests and conformance's two.
  - All 19 passed in 42 min, at a peak of 4.2 GiB. The estimate was 55 min and 8 GiB.
  - The Python half of VF-030 has no tests, because no Python test is tagged proof tier. So nothing is left open.
  - The brief's Progress records this as cycle 13. It acknowledges inbox items I008 and I009.
- **How it was verified:**
  - I checked the job's log against the ignored rows in `costs.json` and confirmed that none was left out.
  - `test_costs.py run --changed` passed 4/4.

### `mmnoqopr` (de6efd3d): the observation is bound to more of the state it read
This covers inbox items I008 and I009.
- **What it adds:**
  - **Supertypes are compared.** `--observed-initializer` now compares the state a class left in its supertypes with what each would be if initialized alone. Before, it skipped them.
  - **Properties read through the map are recorded.** A system property read through `Properties.get`, `getOrDefault` or `containsKey` is now recorded and bound, as `getProperty` was.
  - **Reading all the properties is refused.** Code that reads the system properties as a whole (`keySet`, `entrySet`, `forEach`, `store`, …) is refused with the name of the class that did it.
  - **The time zone is bound.** The observation now records the default time zone. The stated assumption now ends "… and default time zone X".
  - **Reading the environment is refused.** A class whose bytecode calls `System.getenv` or `ProcessBuilder.environment` is refused. The check covers the observed class and every class it initialized.
  - **Two kinds of read are still not seen,** and the module doc says so: the environment read by reflection, and properties read through `equals` or `hashCode`.
  - **The state stream's `Dump.nameOf` is kept (I009).** I took their `ObservedInitializer.java` whole, then extended it. Their test fixture `Hooked.java` and its `claims.rs` lines came with it.
  - **Tests:**
    - A new tool-tier test, `an_observation_is_bound_to_its_writes_outside_the_class_and_to_every_setting_it_read`, runs the challenge stream's five `ob` countermodels, copied from `lqvlvwsm`:
      - Derived is refused.
      - Filled is refused.
      - Bypassed is accepted, and the property it read is named.
      - Zoned is accepted, and its time zone is named.
      - Environ is refused.
    - There is also a new unit test for the whole-properties refusal.
  - **Docs and notes:** `lib/README.md`, the notes of example 290 and VF-033's audit bullet are updated.
- **How it was verified:**
  - Capped probes on example 290 still prove fixed-security (659 paths) and preservation (573 paths).
  - In those probes, HttpServlet now lists GenericServlet, which is the same as when initialized alone. The observations state en-US and Etc/UTC, and show no environment or whole-properties reads.
  - `validate_example.py 290` passed.
  - `test_costs.py run --changed` passed 28/28.
  - `estimate`, `tag` and `lint` agree.
  - The commit check reported 0 errors.
  - I told the state stream about these changes through its inbox, as item `domain-advances-state-I012`.

## Verification jobs
- **Pending, running or failed:** none.
- **Recorded on another head (`1b4984f2`, the collector's line, not merged here):** four jobs.
  - Example 286's protected-state tasks.
  - Example 287's preservation claim.
  - Two runs of preservation on 289/290 from the preservation stream, both of which passed (about 1 min each, `holds×2`).

  None of them is this stream's. They come in when that line is merged.

## Warnings from `sync.py check`
None: 0 errors and 0 warnings across 138 sessions, plus 642 notes that need no action.

## Deferred work that needs you
- **Freezing 290's restated preservation claim.** It was prepared in `9f7f73cf` and compares what the matchers are. It needs your decision to freeze it.
- **Rerunning preservation on 289/290 on this line.** This needs `zmvkptqz` (64660b09: exceptions compared by class, each version started fresh) merged onto this line. That merge belongs to the watcher or the preservation stream, not to this stream. The preservation stream's own runs passed on its line, but the rerun with this line's widened binding has not been done.

## Other things that need your attention
- **Merge conflicts to expect.** I copied the state stream's files rather than merging them. So when the state line is merged, expect conflicts in `ObservedInitializer.java`, `lib/src/observed.rs` and `lib/README.md`. Take this line's versions (`mmnoqopr`): they already contain the state line's `nameOf` change.
- **The brief is out of date in two places**, as the commit messages say:
  - the "Where it stands" paragraph;
  - step 6, which mentions a Python proof tier that has no tests.
- **Progress ends blocked:** `Status: blocked: …` on the two items above.

Ended 2026-11-17 16:30:57 after 2 cycle(s): the session decided to stop; the brief says blocked: the 289/290 preservation rerun needs zmvkptqz merged onto this line (the watcher's or the.
