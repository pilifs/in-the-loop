# Stream brief: cleanup, JBMC's verdicts

One of three streams of [`cleanup.md`](cleanup.md) that run in parallel, each in its own jj workspace on its own
branch. The others are [`cleanup-native.md`](cleanup-native.md) and [`cleanup-examples.md`](cleanup-examples.md).
Once all three are finished, the main brief's loop merges them ([Reconciling](cleanup.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh cleanup` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh cleanup-jbmc` from this stream's workspace (`jj workspace root --name cleanup-jbmc`). The loop
refuses any other.

**The main brief is the instruction.** Read [`cleanup.md`](cleanup.md) in full every cycle, and its inputs. Its
direction, starting point, working rules, deferrals and decisions all apply here. This file says which items are
yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section, and
[`jbmc-upstream.md`](jbmc-upstream.md)'s candidate reports. Edit implementation files according to the main brief's
[ownership](cleanup.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/cleanup-integration.md`, if it exists. A failure in your
files on the latest combined commits is your next piece of work.

## Your items

In order:

- **J1. VF-009, JBMC's refutations of `boomTwice` and `enumBroken` at `n=0`.**
  - The facts, from job `20261107-010728` (at `254f1d7a`):
    - `the_corpus_agrees_with_the_jvm_under_auto_confirm` (`lib/tests/conformance.rs`) has 8 disagreements, all on
      these two methods, under `--gaps Strict` and `Assume`.
    - JBMC 6.11.0 refutes at `n=0`. The JVM and the own checker hold.
    - Both methods run a class initializer that throws. The JVM wraps the throw in `ExceptionInInitializerError`,
      and then raises `NoClassDefFoundError` on the class's next use.
  - **Triage first, as quick jobs** (JBMC never runs inline), each small and at `--priority 10`:
    - JBMC on the two methods alone, with and without `--throw-runtime-exceptions` and the flags the adapter passes;
    - each class initializer on its own;
    - the JVM's behaviour, on a real `java`, inline.

    Find which of these it is: JBMC's semantics of a failed initializer, a flag jvmcontract passes or doesn't, or
    the adapter's reading of the trace.
  - **Then fix it in jvmcontract**:
    - If it is the adapter or a flag, correct it.
    - If it is JBMC's semantics, the preflight (`jbmc_gaps.rs`) names such initializers as a gap, refused under
      strict as the extra initializers of `-010728` are. Add a candidate report to `jbmc-upstream.md`, with the
      evidence: the job, the class, and what the JVM does. Never file it.

    Add a conformance case if the two methods don't already pin the cause.
  - **VF-019, in the same test.** Since `-010728` ran, H2 added six nullable and may-alias claims to the corpus:
    `twoArrays` with `may alias a,b`, and `length` and `lengthOrMinusOne` with `nullable a`. Under `auto --confirm`
    each gives "no engine wrote a harness", under strict and assume alike (job
    `20261107-043420-nullable-and-one-array-parameters-in-pro`, 12 of its 20 disagreements). JBMC can't take such
    an input, so `--confirm` should refuse with a named reason. Make it do so, and have the test read a named
    refusal as no verdict. An unnamed missing harness stays a failure: nothing gets weaker.
  - **Closes when** job `20261107-010728-jbmc-s-extra-initializers-named-and-refu`, resubmitted unchanged at the
    fixing commit, has step 2 pass (VF-009), and job `20261107-043420-…`, resubmitted unchanged, passes (VF-019).
    Name both entries in the resubmissions.
- **J2. VF-001, what is left of it.**
  - Recheck each of its parts against the current code and the passing runs of
    `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto`, in `-010728` (step 1) and `-024759`:
    - the seven `Verified`s under strict that the JVM refutes;
    - `caught` and `nestedHandler` at `n=0`;
    - `auto` taking JBMC's `Verified` for `loadFactor` and `pairsEqual`.
  - Say under Progress which commit fixed each part, or that it is still open. Fix any part still open, with a
    conformance case.
  - **Closes when** both of its jobs, `20261106-021741-conformance-corpus-under-jbmc-and-engine` and
    `20261106-024336-conformance-corpus-under-engine-auto-con`, resubmitted unchanged, pass. The first runs every
    ignored conformance test, `--confirm`'s included, so submit both after J1's fix. They run about 20 minutes each.
    If a part is JBMC's and can only be refused, the refusal is the fix (strict gives no verdict). The jobs pass
    once the JVM never contradicts a verdict.

- **J3. VF-018, JBMC's timeouts on H5's object proofs.** Four of the heap stream's H5 tests under `--engine jbmc`
  fail on their first JBMC run with "JBMC did not finish within 600 s". The own checker proves each claim:
  - `Kernel#price` (`lib/tests/heap.rs:986`, job `20261107-080218-…`);
  - `Prices#total` (`:1172`, `-083358-…`);
  - `Lines#reprice` (`:1472`, `-092158-…`);
  - `Orders#reprice` (`:1685`, `-115201-…`).

  The other four H5 jobs, over the same harness machinery, passed in 2 to 6 minutes.
  - **First, more time** ([decision 6](cleanup.md#decisions)). The 600 s is the tests' own time limit for each run,
    `timeout_seconds: 600`, the default of `equivalence::Options::new` (`lib/src/equivalence.rs:157`) and
    `property::Options` (`property.rs:123`), which `related_on` (`lib/tests/heap.rs:710`) and `property_on` keep. It
    is not a limit of JBMC's own.
    - Let the ignored JBMC tests take their limit from an environment variable, with 600 s still the default.
      This is an addition to `heap.rs` (a shared file for this purpose): name it under Progress.
    - Submit the four tests as one job, or four, with the variable set to 1800 s, and the job's duration and timeout
      sized for it.
    - The expectations stay unchanged: each claim `Verified` under JBMC and under `auto --confirm`.
  - **If that fails, defer it to the user.** One failed attempt is enough here, by the user's decision; don't
    wait for a second. Record under Progress, as *deferred to the user*: the job, how long JBMC ran, and a short
    look at the harness JBMC was given (its size, its unwinding, how the correspondence's equations reach it). Don't
    change the harness or the tests' expectations in this loop.
  - **Closes when** the job with the longer limit passes.

**Not yours:**
- the own checker's engine and the interpreter (the native stream);
- `build.py`, the examples and `sync.py` (the examples stream).

A change to `lib/models/` says under Progress which recorded JBMC results it may change.

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
  both jobs, the finding and what a further attempt would cost. Triage jobs that run as designed don't count: a
  JBMC run that shows the disagreement is evidence, not a failure.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by `run-streams.sh`:
  - `working` while there is work you can do;
  - `waiting on jobs ID ...` when everything left waits on them;
  - `done` when every item is closed or deferred by the timebox;
  - `blocked: ...` with what needs the user.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `2df7775c`,
  compacted). What it settled is in the briefs. Where your memory of it and a brief differ, the brief wins.

## Progress

- **J1, VF-009: triage queued** (2026-11-07). The JVM's side is checked inline on the new fixture
  `lib/tests/fixtures/jbmc-defects/F.java`, one void method per part of a failed initializer's semantics (JVMS §5.5
  steps 5, 11 and 12): `wrapped`, `erroneous`, `once`, `error`, `enumWrapped`, and copies of `boomTwice(0)` and
  `enumBroken(0)`. Every assertion holds on JDK 25.0.5 (`all hold, runs 4`). The hypothesis, from the goto listings
  in `jbmc_gaps.rs`'s tests (`clinit_already_run := true` before the `<clinit>` call): JBMC neither wraps the
  initializer's exception in `ExceptionInInitializerError` nor marks the class erroneous. Job
  `20261107-163056-vf-009-triage-a-class-initializer-that-t` (priority 10) runs the fixture on stock JBMC with no
  flags, `--throw-runtime-exceptions`, and the adapter's flags, and the corpus's two methods through `jvmcontract
  prove` under `jbmc` and `auto --confirm`, keeping JBMC's traces. Next: VF-019, which doesn't wait on it.
- **J1, VF-019: fixed, its job waits on VF-009's fix** (2026-11-07). Read in the code: `--confirm` (and `--engine
  jbmc`) already refused the six claims with a reason in words (`property.rs`, "the domain … lets an array parameter
  be null or one array with another, which only the tool's own checker takes"), but before writing the harness, so
  the confirm test found no harness for them under any of its runs. It then also failed them as "the corpus says it
  is refuted, the JVM does not": 6 more failures in `-043420` beside the 12 the entry counts. Now the refusal is
  named: `property::Outcome::refused`, `Some(WIDENED_DOMAIN)` (`"widened-domain"`, in `--json` too), None for every
  other refusal and every run a checker made. In `conformance()`, a claim with no harness whose every run is
  `Unverifiable` and refused by name has no verdict and isn't judged against the JVM there (the test under JBMC and
  auto, whose plain `auto` runs write its harness, judges it). Any other missing harness is still a failure.
  Reproducer: `a_domain_jbmc_is_not_given_is_refused_by_name` (not ignored, no JBMC run) checks the six claims under
  `auto --confirm` strict and assume and `--engine jbmc`, and that plain `auto` decides them as the corpus records.
  It fails with `refused` left None (checked inline), and the conformance suite's 10 tests pass. Shared files, by
  adding: `lib/README.md` (one clause naming the refusal), and `Outcome`'s new field in `property.rs`. The closing
  resubmission of `20261107-043420-…` waits on VF-009's fix, since the same test carries VF-009's 8 disagreements.
- **J3, VF-018: the longer limit queued** (2026-11-07). The four failed jobs each ran 21 to 23 minutes (peak
  1.2 GiB): two JBMC runs of 600 s, the claim's under `--engine jbmc` and again under `auto --confirm` (whose own
  checker's `Verified` stood), and about 2 minutes for the rest. The JBMC tests in `lib/tests/heap.rs` now take each
  run's limit from `JVMCONTRACT_HEAP_TIME_LIMIT`, in seconds. It is 600 s when unset, and a value that isn't a
  positive number stops the test. Only the runs on an engine other than the own checker read it, since
  `timeout_seconds` is also the own checker's deadline. This is in `related_on` and `property_on`, so the tests
  that aren't ignored are unchanged. Shared file, by adding: `heap.rs`, the constant `TIME_LIMIT_VARIABLE`, the
  functions `time_limit` and `time_limit_from`, the two assignments, and the test
  `the_jbmc_tests_take_their_time_limit_from_the_environment`, which doesn't compile without them. heap's 47
  non-ignored tests pass. The four tests run unchanged with the variable at 1800, one job each (2 CPUs, 4 GiB,
  about 70 min, a timeout of 100 min): `20261107-164356-vf-018-objects-kernel-price-s-output-rel`,
  `-164356-vf-018-prices-prices-total-s-computed-in`, `-164356-vf-018-lines-lines-reprice-s-equations-t` and
  `-164356-vf-018-orders-orders-reprice-s-equations`. If any fails, VF-018 is deferred to the user, with no second
  attempt. Next: J2's recheck, then VF-009 once its triage is back.
- Not this stream's: `sync.py commit`'s check in this workspace reports 4 errors, none on this branch's own commits.
  They are the planning session's base commit `oqqwvmqy`, whose log `3f768f3bb246` is stored only in the default
  workspace, and other workspaces' commits (`ruvmymplmmoo`, native; `syqpoxomnynk`, the verification loop) whose
  manifests are there. The foundations streams saw the same, and it resolved at the merge.
- Status: working

## Loop settings

- session: a8cc612f-0606-4d4c-af9c-ef4ccb4bfee3
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: cleanup-jbmc
- fork: 2df7775c-45a1-40a7-924b-75602d8ad256

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when every item is closed by its check or deferred by the timebox. Stop
with `blocked: ...` when what is left needs the user and is recorded under Progress. Don't take on work beyond your
items: anything new you find goes under Progress, for the main brief's for-review list.
