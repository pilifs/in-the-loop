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

- Nothing yet.
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
