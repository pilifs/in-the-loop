# Stream brief: cleanup, examples and tools

One of three streams of [`cleanup.md`](cleanup.md) that run in parallel, each in its own jj workspace on its own
branch. The others are [`cleanup-native.md`](cleanup-native.md) and [`cleanup-jbmc.md`](cleanup-jbmc.md). Once all
three are finished, the main brief's loop merges them ([Reconciling](cleanup.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh cleanup` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh cleanup-examples` from this stream's workspace (`jj workspace root --name cleanup-examples`).
The loop refuses any other.

**The main brief is the instruction.** Read [`cleanup.md`](cleanup.md) in full every cycle, and its inputs. Its
direction, starting point, working rules, deferrals and decisions all apply here. This file says which items are
yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section. Edit implementation
files according to the main brief's [ownership](cleanup.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/cleanup-integration.md`, if it exists. A failure in your
files on the latest combined commits is your next piece of work.

## Your items

In order. E1 to E4 don't depend on each other: when one waits on a job, go on with the next.

- **E1. VF-002, a patch that creates its subject.** `build.py` stops examples 147, 148 and 149 with "the patch does
  not change the subject file" (`examples/tools/build.py:3523`), because their patches create `Jitter.java`
  (`--- /dev/null`).
  - Reproducer first, in `examples/tools/test_build.py`: a patch that creates its subject is refused today.
  - Then take a created subject as having an empty before side, in `excerpts()` and wherever else the subject's old
    text is read.
  - Check that the examples' notes and pages still say what each proves.
  - **Closes when** the three jobs (`20261106-053555-example-147-…`, `20261106-053555-example-148-…`,
    `20261106-061323-example-149-…`), resubmitted after the fix, pass with each example's expected verdict.
  - Read their notes first. If one expects a verdict the current tool can't give for another reason, that example's
    failure is a new finding, recorded under Progress. It doesn't count against the fix.
  - **VF-016, with it**: the same check stops examples 160 and 161, for the opposite reason. Their subject,
    `RetryAfter#nanosUntilToken`, is a caller the patch doesn't change: the change is in its helper, `TokenBucket`.
    Take a subject the patch leaves alone when the change is in the subject's code closure, with the excerpts
    showing the changed file. Or have the examples name the helper's file. Choose by what the examples' pages need
    to show, and say why under Progress. Reproducer in `test_build.py`. **Closes when** jobs
    `20261107-053635-example-160-…` and `-161-…`, resubmitted after the fix, pass: 160 verified with `lastAfter`
    shared, 161 a violation with no helper shared.
  - **VF-017, beside it**: examples 150, 151 and 152 fail as `build.py` validates their result, because
    `examples/schema/result.schema.json` allows no `object` parameter kind (its `statement.domain.parameters` kind
    is `primitive`, `array` or `record`). Extend the schema to what jvmcontract writes for an object parameter, with
    a `test_build.py` case. **Closes when** jobs `20261107-064330-example-150-…`, `20261107-064331-example-151-…` and
    `-152-…`, resubmitted after the fix, pass: 150 verified; 151 a violation differing only in `result == throttle`;
    152 verified within the constructor-made domain.
- **E2. VF-014, H1's benchmark comparison, isolated.** The benchmark job of H1 (`20261107-041414`) was compared with
  a stale `lib/benchmark/results.json`, so 8 verdicts changed for reasons the job can't tell apart from H1. H1 is
  change `uyqkxsly`.
  - Make the comparison the entry offers as its alternative, H1 against its parent. A job runs at one commit, and
    `pipeline.py submit --revision REV` picks which. So:
    - two jobs, at `--revision` H1's parent and at H1 itself. Each runs step 1 of `20261107-041414` unchanged
      (`run.py --engines native --out lib/target/benchmark-native.json`), with that file as an `--output`;
    - once both are collected, a quick third job at your current commit. It applies `20261107-041414`'s step-2
      comparison script to the two collected outputs, in `verification/results/ID/outputs/`, in place of
      `lib/benchmark/results.json`. There is no comparison in `run.py` itself: the script is in that job's
      `result.json`.
  - Every verdict should be the same in both, and the formula sizes should differ only where references merge.
  - **Closes when** the third job passes. If verdicts do differ between the two, H1 changed them. That is a verdict
    for the entry, recorded under Progress with the runs, not a reason to change the comparison.
  - Then, as a separate job, record a fresh `results.json` at your current commit, so that later comparisons start
    from the current engine. Its outputs replace the file through `collect`. Never edit the file by hand.
- **E3. VF-013, the loops' run records published.** Follow the entry's chosen approach (its **Needs**) step by step:
  - a reproducer first, with made-up paths and a made-up session, showing a record published unredacted or not at
    all;
  - `sync.py` reads the session id from a record's header and redacts the record with the transcripts' `Redactor`;
  - it writes the copy to `llm-dlc/traces/<session>/runs/<record>.md`, linked from that session's `summary.md`
    (start, end, cycles, how it ended);
  - `check` scans the copies, and a finding in one is an error as for a log;
  - a record still being written (no `Ended` line) is held back until it ends, or republished as it grows, as the
    entry leaves open. Choose one, and say why under Progress.

  The redaction rules don't change, so no stamp is needed. `traces-readme-template.md` and `llm-dlc/README.md` say
  where the runs are. Test redaction with made-up values only (CLAUDE.md).
  - Don't publish the real records from this workspace: its `llm-dlc/loop-summaries/` is this workspace's own. The
    main brief's loop publishes them after the merge ([Phase 4](cleanup.md#phase-4-after-the-merge-this-briefs-own-loop),
    step 2).
  - **Closes when** `sync.py`'s tests cover it. The rest of the entry's check (every record published, with `check`
    at 0 errors) is the main brief's, after the merge.
- **E4. The foundations leftovers**, from [`foundations.md`](foundations.md#progress)'s last item. Each gets a test
  that fails before the fix:
  - the golden domain's `allocations: 0` (`lib/tests/fixtures/foundations/golden/`) is checked against the domain
    the run states;
  - the integration contract checks `discount` under a claim of its own, not the kernel claim whose input `q` it
    doesn't have (`lib/tests/foundations.rs`);
  - a reused proof names the run it came from by the builds it was given, not the rewritten copies' temporary paths
    (`effects.rs`, `compare.rs`).

  These are inline: compiling and unit tests.

**Not yours:**
- the own checker and the interpreter (the native stream);
- JBMC's adapter, `auto`, `--confirm` and the conformance corpus (the jbmc stream).

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line, and the main brief's loop merges it.
- **Jobs, with the pipeline**, as the main brief's [rule](cleanup.md#how-to-work-through-it) says:
  - Submit each check as a job, named for the entry it closes, and commit it with the change.
  - Go on with any item that doesn't depend on it.
  - When all that is left waits on jobs, end with `- Status: waiting on jobs ID ...`, and you will be run again once
    they are collected. Read results with `python3 "$(jj workspace root --name default)/verification/pipeline.py"
    report ID`.
  - Never edit `verification/findings.md`.
- **The timebox**: two failures in a row on one item end it in this loop. Log it as *deferred by the timebox*, with
  both jobs, the finding and what a further attempt would cost.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by `run-streams.sh`:
  - `working` while there is work you can do;
  - `waiting on jobs ID ...` when everything left waits on them;
  - `done` when every item is closed or deferred by the timebox;
  - `blocked: ...` with what needs the user.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `2df7775c`,
  compacted). What it settled is in the briefs. Where your memory of it and a brief differ, the brief wins.

## Progress

- **E1, VF-002 and VF-016: fixed, jobs pending.** `excerpts()` in `examples/tools/build.py`:
  - takes a subject the patch creates (`--- /dev/null`) with an empty before side at line 1, and the page says
    "Before: none, the patch creates `Jitter.java`";
  - takes a subject the patch leaves alone when the patch changes exactly one Java file of the subject's source tree
    whose class the subject's source names. Both sides are then that file's hunks (`TokenBucket.java` for 160 and
    161), and the page says the patch changes a helper the subject calls. Otherwise it is refused as before, with
    the reason.
  - **Why the unchanged subject, not the helper's file in the examples:** the subject file is also the page's
    verified-unit link, the claim's `file` and the SARIF location. All three should be `RetryAfter`, the method
    proved. Naming `TokenBucket.java` would point `nanosUntilToken` at the wrong file. The pages also need to show
    the helper's change, which this does.
  - Reproducers in `test_build.py`'s `ExcerptsTest`: the 5 examples' own patches and made-up ones. They failed
    before the fix (5 errors) and pass after it.
  - Jobs, resubmitted unchanged, with the entry each closes added to its title and description:
    `20261107-163046-example-147-…`, `20261107-163047-example-148-…`, `20261107-163049-example-149-…` (VF-002),
    `20261107-163050-example-160-…`, `20261107-163051-example-161-…` (VF-016).
- **New finding, for review:** the jobs of 148 and 149 expect "1 proved, 2 tested". Since engine-priorities item 9,
  `Integer.numberOfLeadingZeros` is no gap (the examples' last notes), so the current tool can give only the two
  tested contracts. The verdict they expect, verified, is unaffected, and `build.py` checks only the verdict. The
  examples' titles and summaries still name three contracts.
- **The integration check's failure, fixed** (its report of 16:26, at `eeb1fa29`): `test_build.py`'s
  `ReplayWordingTest` held that only boxoffice pages say a witness was "replayed on the JVM". That predates
  `jvmcontract effects`, which does replay its witness on a JVM (`effects.rs:577`), so the pages of 171, 172 and
  191–194 failed it, correctly worded, with `replay.by: "jvm"` in each result. The test, renamed
  `test_no_recorded_example_is_said_to_be_replayed_where_its_result_does_not_say`, now checks each recorded B9
  violation's page against its own result's replay record (`replayed_where`), and that at least one is on the JVM.
  No page or result changed. All 185 tests pass.
- `--render-only` marks the pages of 170–172 stale, since the Crosscut and deliveries sources changed after their
  runs. They're not re-rendered here: Phase 4 reruns them at the merge.
- `sync.py commit`'s check reports errors that aren't this branch's: other streams' commits (`zykkyuuw`, `ruvmympl`,
  `syqpoxom`) have no manifest in this workspace, and the planning session's log `3f768f3bb246` is only in the
  default workspace's gitignored `llm-dlc/traces/*/logs/`, since `oqqwvmqy` isn't pushed. Left alone: the merge and
  its push settle them.
- **E1, VF-017: fixed, jobs pending.** `examples/schema/result.schema.json`'s statement was behind
  `lib/src/statement.rs` in more than the `kind` enum. An object parameter's statement also carries `inputObjects`
  (the input objects each version is made of) and, where choices may be one object, `mayAlias` in the domain, and
  `objects` and `identities` (step H3's `result == throttle`) in the observations. All four were refused by
  `additionalProperties: false`. The job reported only the first error. The schema now has `object` and the four
  fields, and its stale "never today" descriptions say what the code does.
  - The page's statement paragraph (`statement_paragraph`) now says that each object is made by its constructor,
    which fields are compared after the call, and which identity relations are compared within each version.
    Without that, 151's page wouldn't name the observation that refutes it.
  - Reproducers in `test_build.py`'s `StatementTest`: an object domain in 151's shape, recorded through
    `run_tool_equivalence`, validates, and so does a variant with a nullable, may-alias object. Malformed
    `kind`, `inputObjects` and `mayAlias` are refused, and the page names the object, fields and identities. Both
    tests failed before the fix and pass after it, with all 187 tests.
  - The statement's `spec` field isn't in the schema either, but nothing sets it yet (`statement.rs:52`), so it's
    left alone.
  - Jobs, resubmitted unchanged, with VF-017 and each one's expected verdict added to the title and description:
    `20261107-164043-example-150-…`, `20261107-164043-example-151-…` and `20261107-164043-example-152-…`.
- **E2, VF-014: the two runs queued.** `20261107-041414`'s step 1, unchanged, with its two files as outputs:
  - `20261107-164450-vf-014-h1-isolated-run-1-of-2-…` at H1's parent (`rvxkytqy`, `b927e5df`);
  - `20261107-164450-vf-014-h1-isolated-run-2-of-2-…` at H1 (`uyqkxsly`, `ddbb54ba`). That is the same tree as
    `73c514ad`, where `20261107-041414` ran.
  - H1's parent has no swaps conformance cases (H1 added them to `lib/benchmark/conformance.json`). So the third
    job's comparison lists them as new, and fails only on a changed verdict, as the script does.
  - **Where the outputs land:** `lib/target/` is gitignored (`target/`), and so is
    `verification/results/ID/outputs/lib/target/`. The default workspace already has a
    `lib/target/benchmark-native.json` (03:37), so `collect` keeps each passing job's file under `outputs/` as a
    conflict, not applied. The third job runs in a checkout without those files. It has to read them from the
    runner's repository, which is four directories above `$VERIFY_WORKDIR`, or carry them in.
- **Check errors that aren't this branch's:** `uytnkqst` (the jbmc stream's commit) has no manifest here either, as
  for `zykkyuuw`, `ruvmympl` and `syqpoxom` above.
- Next: E3, VF-013's reproducer and `sync.py`'s publishing of the run records. E2's third job follows once its two
  runs are collected.
- Status: working

## Loop settings

- session: b65d132b-4eb4-46fd-8556-f4cba3311ad1
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: cleanup-examples
- fork: 2df7775c-45a1-40a7-924b-75602d8ad256

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when every item is closed by its check or deferred by the timebox. Stop
with `blocked: ...` when what is left needs the user and is recorded under Progress. Don't take on work beyond your
items: anything new you find goes under Progress, for the main brief's for-review list.
