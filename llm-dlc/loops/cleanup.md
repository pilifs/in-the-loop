# Brief: clean up the open findings

**Drafted and its [decisions](#decisions) settled with the user on 2026-11-07.** It starts after the
[launch prerequisites](#launch-prerequisites).

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). It works through the findings the verification runs
and the last loops left open, in [three streams run in parallel](#streams), each a loop of its own with a short brief
that names its items. This brief is the instruction for all three. Its own loop, `llm-dlc/tools/feature-loop.sh
cleanup` in the default workspace, merges them once all are finished, then does the work that needs the merge.

**Inputs.** Read both in full before the first piece of work of every cycle:
- [`verification/findings.md`](../../verification/findings.md), the open entries. Each says what was found, what
  would settle it, and the check that closes it. Read it from the default workspace
  (`$(jj workspace root --name default)/verification/findings.md`): the verification loop keeps it there while the
  streams run.
- This brief's [Where it starts from](#where-it-starts-from), which recounts each entry against the code.

## Direction

- **Close findings, don't add features.** Each item is an open entry in `verification/findings.md`, or a failure or
  leftover named [below](#where-it-starts-from). An item is finished when the check its entry names passes. "Fixed,
  job pending" is not finished.
- **The entry's own check closes it.** Resubmit the job an entry names unchanged
  (`pipeline.py resubmit ID`), or run the check it describes. Don't write an easier one. If the check itself turns
  out to be wrong (a step that can't pass for a reason outside the item), say so under Progress and defer it to the
  user. Don't rewrite the check.
- **Whoever runs the verification closes the entry.** `findings.md` is kept by the `/run-verification` agent in the
  default workspace: it closes an entry when the job that closes it passes. A stream never edits `findings.md`.
  Instead, it names the entry in the closing job's title and description ("closes VF-NNN when it passes"), and
  records the job under its Progress.
- **External work stays deferred** ([decision 1](#decisions)). This covers JBMC patches, reports filed upstream and a
  JBMC fork. Where an item turns out to be JBMC's bug, jvmcontract refuses or names the case. The evidence goes into
  the draft brief [`jbmc-upstream.md`](jbmc-upstream.md) as a candidate report, for the user to select later.
- **Soundness first.** The rules of [`sound-verdicts.md`](sound-verdicts.md) and
  [`engine-priorities.md`](engine-priorities.md) still hold:
  - the JVM is the semantic reference;
  - only JBMC's `VERIFICATION SUCCESSFUL` is a proof;
  - an engine that can't decide gives no verdict, never a wrong one.

  A fix that trades a missing verdict for a wrong one is not a fix.

## Where it starts from

Recounted at `main`'s `tqwpwkvz` (commit `34e1d87b`, 2026-11-07), after the foundations loop. Every entry here is
still open there. "As read" means the entry's claim about the code was checked against it but not reproduced.

| Item | Entry | What is open | Stream |
|---|---|---|---|
| Wall-clock probe budgets | VF-010 | `Engine::probe` (`lib/src/bmc/mod.rs:1326`) gives a branch probe `max(self.b.solving, 1 s)` of wall-clock time. So which side of a branch stays undecided, and with it the path order, depends on the machine. `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` fails on `Pricing#total` in about 2 of 8 runs. | [native](cleanup-native.md) |
| Unwinding counted per path | VF-011 | `Engine::jump` (`lib/src/bmc/mod.rs:1945`) counts back edges per path and `(class, method, target)`, and never resets the count when a loop is left. So a nested quantifier's inner loop runs out of `--unwind` across iterations of the outer one, and example 052 is left to JBMC. | native |
| Example 109's replay | VF-015 | Job `20261103-010716-example-109-revisited-hex-todigit-s-regr` failed at step 3: the old `toDigit`'s witness `ch == 1632` could not be replayed. The interpreter refuses `reads static field java.nio.charset.StandardCharsets.UTF_8` (`lib/src/interp/natives.rs:373`). It was never rerun or tracked. | native |
| JBMC's spurious refutation under `--confirm` | VF-009 | `boomTwice` and `enumBroken` at `n=0`: JBMC 6.11.0 refutes and the JVM doesn't. Both run a class initializer that throws. Untriaged. | [jbmc](cleanup-jbmc.md) |
| A missing harness under `--confirm` | VF-019 | H2's six nullable and may-alias claims give "no engine wrote a harness" under `auto --confirm` (job `20261107-043420`, 12 of its 20 disagreements; the other 8 are VF-009's). The job expected them refused, by name. | jbmc |
| JBMC's timeouts on H5's object proofs | VF-018 | Four H5 tests under `--engine jbmc`: JBMC doesn't finish within 600 s where the own checker proves the claim (jobs `-080218`, `-083358`, `-092158`, `-115201`). The other four H5 jobs passed. | jbmc |
| JBMC verdicts the JVM contradicts | VF-001 | Probably reduced to VF-009, which still has to be shown. `the_corpus_agrees_with_the_jvm_under_jbmc_and_auto` passed in jobs `20261107-010728` (step 1) and `20261107-024759`, so the seven false `Verified`s under strict and `auto`'s pass-through look handled by the engine-priorities loop. The entry's first job runs every ignored conformance test, `--confirm`'s included, so both jobs pass only once VF-009 is fixed. | jbmc |
| A patch that creates its subject | VF-002 | Examples 147, 148 and 149 stop before any proof. Their patches create `Jitter.java` (`--- /dev/null`), and `build.py` refuses that: "the patch does not change the subject file" (`examples/tools/build.py:3523`). | [examples](cleanup-examples.md) |
| A subject the patch doesn't change | VF-016 | Examples 160 and 161 stop on the same check as VF-002, for the opposite reason. Their subject is the caller `RetryAfter`, and the patch changes only its helper `TokenBucket` (jobs `20261107-053635-…160…` and `…161…`). | examples |
| No `object` kind in the result schema | VF-017 | Examples 150–152 fail validation: `'object' is not one of ['primitive', 'array', 'record']`. The enum is in `examples/schema/result.schema.json`'s `statement.domain.parameters`, and it is still so at `main` (jobs `20261107-064330/1-…`). | examples |
| H1's benchmark comparison | VF-014 | Job `20261107-041414` compared against a stale `lib/benchmark/results.json`. Eight verdicts changed on `boom/1`, `inherited/1` and `quiet/1`, most likely through class initializers gained since. The job doesn't isolate H1. | examples |
| Run records unpublished | VF-013 | `llm-dlc/loop-summaries/` is gitignored (`.gitignore:47`), and six of its records hold unredacted local paths. The approach is chosen in the entry: `sync.py` publishes a redacted copy beside each session's trace. | examples |
| Foundations leftovers | none | Recorded in [`foundations.md`](foundations.md#progress)'s last item:<br>• the golden domain's `allocations: 0` is not checked;<br>• the integration contract checks `discount` under the kernel claim, whose input `q` it doesn't have;<br>• a reused proof names its source run by the rewritten copies' temporary paths. | examples |
| The merge's examples | none | The streams' jobs for examples 150–152, 160–161 and 170–172 ran at the streams' own commits. The foundations merge changed `equivalence.rs`, and nothing has run them on the combined code. | this brief, after the merge |

**The 2026-11-07 afternoon run** of the 28 jobs the foundations loop left pending was collected and triaged by
the planning session. 18 passed:
- 170–172 and 190–196 with their expected verdicts;
- S6's proof-cache economics;
- Crosscut's nine examples;
- the alignment scoring, resubmitted as `20261107-155804-…` because one of its outputs had gone stale;
- five of heap's JBMC jobs.

The 10 failures are VF-016 to VF-019 above, and VF-009 again. Each is assigned here by the files its fix touches.

**Not items.** These failed jobs are settled elsewhere:
- 52 failed results in all. Each is either tracked by an entry above or closed, or superseded by a later pass of the
  same example or check.
- The failed `-073804` and `-082917` were triaged in [`engine-priorities-review.md`](engine-priorities-review.md):
  - `-073804`'s reading agreed, and its five examples passed in `-123940`;
  - `-082917`'s examples all gave their expected outcomes, and only its table script failed.
- The 2026-11-03 Mica rerun's example 036 passed in `20261105-022629`.
- The flaky `bmc::bits::tests::the_encoding_estimate_does_not_count_a_large_circuit_many_times_over` stays a known
  flake ([decision 3](#decisions)): rerun it once before treating a failure as a regression.

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, the [timebox](brief-template.md#the-timebox) included:
- one step per cycle, committed on its own;
- check each claim against the code first, this brief's and the entries' included;
- proofs, model checks and benchmark runs are queued, never run inline;
- recorded results are evidence, not inputs to edit;
- nothing gets weaker;
- docs move with the behaviour;
- defer what needs the user, explicitly;
- **a reproducer before a fix**, committed with the fix, failing before it and passing after.

In addition:
- **Verification runs with the pipeline** ([decision 5](#decisions)). `run-streams.sh` starts `verification-loop.sh`
  in the default workspace, and it runs the jobs every workspace commits.
  - Submit each check as a job, its expected result in the description, and the entry it closes in the title (see
    [Direction](#direction)). Commit it with the change: `(verification pending)` on the summary line, the job id in
    a paragraph.
  - Go on with any item that doesn't depend on the job.
  - When everything left waits on jobs, end Progress with `- Status: waiting on jobs ID ...`. `run-streams.sh`
    reruns the loop once their results are collected. Read them with `python3 "$(jj workspace root --name
    default)/verification/pipeline.py" report ID ...`.
  - A result that passed lets the item's entry be closed. A result that failed counts toward the timebox.
- **The timebox**, as the [template](brief-template.md#the-timebox) says:
  - Two failures in a row on one item end it in this loop. A failure is a job that came back failed, timed out or
    ran out of memory, or an inline attempt that failed. A resubmission with a bigger budget counts as an attempt.
  - Log it under Progress as *deferred by the timebox*, with both jobs, the finding, and what a further attempt
    would try and cost.
  - Then go on. There is no third attempt.
- **Items are independent.** No item in one stream waits on another stream. Within a stream, the item order is the
  order given, apart from where a stream brief says an item waits on another.

## Launch prerequisites

The planning session is `2df7775c-45a1-40a7-924b-75602d8ad256`, the conversation that drafted this brief in the
default workspace. The streams fork from it.

1. **The afternoon run collected and triaged** (done), with its results committed. Its new entries, VF-016 to
   VF-019, and example 109's old failure, VF-015, are in `findings.md` and assigned
   [above](#where-it-starts-from).
2. **The names**:
   - `cleanup` and `cleanup-STREAM` in `feature-loop.sh`;
   - `cleanup` with its three streams in `run-streams.sh`;
   - the integration check `llm-dlc/tools/cleanup-integration.sh`.
3. **This brief and its three stream briefs committed** (done) on the default line, with the session ids in their
   Loop settings.
4. **Push** (done, at the user's request).
5. **Close the planning session**. The user then runs `FEATURE_LOOP_MEMORY_MAX=4G CARGO_BUILD_JOBS=8 llm-dlc/tools/run-streams.sh cleanup` from the default
   workspace, in a tmux pane with a long history. It compacts the planning session once, before the forks.

## Streams

| Loop | Brief | jj workspace | Items | Owns |
|---|---|---|---|---|
| `cleanup-native` | [`cleanup-native.md`](cleanup-native.md) | `cleanup-native` | VF-010, VF-011, VF-015 | `lib/src/bmc/`, `lib/src/interp/`, `harness/`, `witness.rs`, `jvm_witness.rs`, `shrink.rs`, `lib/tests/integration.rs`'s own-checker tests |
| `cleanup-jbmc` | [`cleanup-jbmc.md`](cleanup-jbmc.md) | `cleanup-jbmc` | VF-009, VF-019, VF-001, VF-018 | `jbmc.rs`, `jbmc_gaps.rs`, `jbmc_contracts.rs`, `models.rs`, `lib/models/`, `lib/tests/conformance.rs` and its fixtures, `auto` and `--confirm`'s code in `property.rs` and `equivalence.rs`, `jbmc-upstream.md` |
| `cleanup-examples` | [`cleanup-examples.md`](cleanup-examples.md) | `cleanup-examples` | VF-002, VF-016, VF-017, VF-014, VF-013, the foundations leftovers | `examples/` (tools and examples), `lib/benchmark/`, `llm-dlc/tools/sync.py` and its tests and docs, `effects.rs`, `compare.rs`, `spec/heap.rs`, `lib/tests/foundations*`, `compare.rs`'s and `effects.rs`'s tests |
| `cleanup` | this brief | `default` | | the merge, the reruns at the merge, the publishing of the run records |

**Workspace names** are the brief's own, `cleanup-STREAM`, at `../in-the-loop-cleanup-STREAM`. jj workspace names
are repository-wide, and earlier runs left `native`, `jbmc`, `examples`, `integration` and the foundations streams'
directories behind (forgotten in jj, still on disk, the user's to delete). `run-streams.sh` stops before compacting
anything if a workspace's directory is already taken.

**Shared files.** Any stream may touch these by adding rather than rewriting: new options, variants, cases, tests and
functions, with no reorganization. Name each change under the stream's Progress. They are `lib/src/main.rs`,
`lib.rs`, `statement.rs`, `equivalence.rs` and `property.rs` (outside the jbmc stream's part), `Cargo.toml`,
`lib/README.md`, `examples/tags.json` and `examples/README.md`. `verification/findings.md` is no stream's: see
[Direction](#direction).

**Example numbers** (from 197, the next free one):
- native 200–209;
- jbmc 210–219;
- examples 220–229;
- this brief 197–199.

A cleanup adds an example only when a fix needs one as its reproducer.

**Memory** ([decision 7](#decisions)). Each stream's scope is capped at 4 GB (`- memory: 4G`, and
`FEATURE_LOOP_MEMORY_MAX=4G` in `~/.profile`, which overrides a brief's), and the integration check runs in a 3.5 GB
scope. Together that is 15.5 GB of the machine's 46. The `/run-verification` agent leaves the runner the machine's
memory less those caps and about 2.5 GB for the OS: about 28 GB, `--memory 28G` with up to 10 workers. Every pending
job asks for 3 GB or less, and VF-018's longer run may ask for more. `pipeline.local.toml`'s own default is 36 GB,
for when one 4 GB loop runs alone.

A stream's first build is a clean one, in its new workspace. Measured on 2026-11-07, a clean `cargo test --no-run`
of `lib/` peaked at 3.1 GiB, page cache included, with cargo's default of 28 parallel jobs. With the session's own
memory, that is close to the 4 GB cap. So the streams run with `CARGO_BUILD_JOBS=8`, set on the command below and
inherited by every session and its commands. Don't raise it in a stream.

**Running it all**, by the user, from the default workspace in tmux: `FEATURE_LOOP_MEMORY_MAX=4G CARGO_BUILD_JOBS=8
llm-dlc/tools/run-streams.sh cleanup`. The memory setting is spelled out because a shell started before
`~/.profile` changed still has the old 8G, which would override the briefs' `- memory: 4G`. It does
four things:
- compacts the planning session once;
- adds the three workspaces from the latest commit;
- starts `verification-loop.sh`;
- runs the streams side by side with the integration check, then this brief's own loop.

A stream that ends `waiting on jobs ID ...` is rerun once those results are collected, up to `RUN_STREAMS_JOB_WAIT`
(12 hours by default).

### The integration check

`run-streams.sh` merges the three streams' current `@-` in its `cleanup-integration` workspace
(`../in-the-loop-cleanup-integration`) whenever one moves, at most
hourly, and runs [`cleanup-integration.sh`](../tools/cleanup-integration.sh) on the merge. That script runs the unit
and integration-contract tests and the Python suites the streams touch, compiling and unit-level only. The report
goes to `llm-dlc/loop-summaries/cleanup-integration.md` in the default workspace. Each stream reads it at the start of
every cycle, and a failure in its own files is its next piece of work. A merge conflict is reported with the files in
conflict.

### Reconciling

This follows [`foundations.md`](foundations.md#streams)'s steps, for three streams:
1. Check all three are finished (status `done` or `blocked`, not only an inactive scope), and that
   `feature-loop-cleanup-integration.scope` is inactive too.
2. Wait for the verification loop to commit anything it left uncommitted in this working copy. Don't move or commit
   its files.
3. Record each stream's last turns, and copy their logs.
4. Merge with `jj new @- cleanup-native@- cleanup-jbmc@- cleanup-examples@-`, and commit.
5. Fold their Progress here, with every item the timebox deferred first.
6. Forget the workspaces `cleanup-native`, `cleanup-jbmc`, `cleanup-examples` and `cleanup-integration`. Their
   directories are the user's to delete.

## The plan

### Phases 1–3: the streams

Each stream brief lists its items in order. All three run at once.

### Phase 4: after the merge (this brief's own loop)

1. **Reconcile** ([above](#reconciling)).
2. **The run records published.** The first `sync.py commit` after VF-013's change publishes each record in
   `llm-dlc/loop-summaries/`, redacted, under its session's trace. These include the streams' own records, copied in
   at step 3 of the reconcile. Check that `check` reports 0 errors on them. A finding in a record is handled as for a
   log, and never by editing the record.
3. **The examples rerun at the merge.** This is one job, or one per app. It runs `build.py` on examples 150–152,
   160–161, 170–172 and 190–196 at the merge commit, each to give its recorded expected verdict. 150–152 and
   160–161 can run there only once VF-017's and VF-016's fixes are merged. Supersede any of
   the streams' pending jobs for those examples that ran at a stream's commit. Also include a job running
   `lib/tests/integration.rs` unchanged, if the native stream's VF-010 job ran before the merge.
4. **The for-review list.** In this brief's Progress, list each entry the streams worked on: closed (by which job),
   or still open with the job that would close it and why it hasn't. Name every job still pending.

## Done when

| Phase | Criterion |
|---|---|
| 1, native | VF-010, VF-011 and VF-015 closed by their checks, or deferred by the timebox with the finding |
| 2, jbmc | VF-009 and VF-019 closed, or VF-009's cause recorded and refused in jvmcontract with a candidate report in `jbmc-upstream.md`; VF-001's two jobs resubmitted unchanged and passed, or what is left of it named; VF-018 closed by the longer limit, or deferred to the user after one failed attempt |
| 3, examples | VF-002, VF-016, VF-017, VF-014 and VF-013 closed by their checks; the three foundations leftovers fixed with tests |
| 4 | the merge committed with the integration check passing on it; the run records published with `check` at 0 errors; the merge's examples rerun at the merge commit with their expected verdicts |

## Deferred: not in this loop

- **External work** ([decision 1](#decisions)): JBMC patches, upstream reports (drafted in `jbmc-upstream.md`, never
  filed by an agent), and a JBMC fork.
- **The flaky encoding-estimate test** ([decision 3](#decisions)): it stays known.
- **New capabilities.** The foundations streams' named gaps are next work, not findings: correspondences over
  expressions, floating point, collections, cycles, polymorphism, JBMC's identity in the cache key, and `prove`'s
  cache hook.
- **Complex-object contracts**, as [`engine-priorities.md`](engine-priorities.md#deferred-not-in-this-loop) deferred
  them.

## Decisions

Settled by the user on 2026-11-07:
1. External work stays deferred: JBMC patches, filed reports and a fork. A JBMC bug found here becomes a candidate
   report in `jbmc-upstream.md`.
2. VF-010 is in the loop: probe budgets that don't depend on wall-clock time.
3. The encoding-estimate test's flakiness stays a known flake, not an item.
4. VF-013 is in the loop, with the approach its entry records (a redacted copy beside each session's trace).
5. Three streams (native, jbmc, examples), run with the verification pipeline, not separate, so that entries can be
   closed in the loop. They fork this planning session.
6. VF-018: first rerun the four tests with a longer limit (1800 s), expectations unchanged. If that fails, defer it
   to the user, with no second attempt and no change to the harness or the expectations.
7. Each stream's scope is capped at 4 GB, which is also this machine's default for any loop now
   (`FEATURE_LOOP_MEMORY_MAX=4G` in `~/.profile`). The verification runner gets the rest.

## Progress

- Drafted 2026-11-07 by the planning session. A first launch stopped before any stream started: the workspace
  `integration`'s directory was left over from the foundations run. `run-streams.sh` now names workspaces after the
  brief (`cleanup-STREAM`, `cleanup-integration`), and checks every directory before compacting anything. The afternoon run was triaged into VF-015 to VF-019, and launch
  prerequisites 1 to 3 are done.
- **Phase 4, step 1: reconciled** (2026-11-07). All three streams had stopped: native `blocked`, jbmc `blocked`,
  examples `done`, and `feature-loop-cleanup-integration.scope` was inactive. Each stream's last turns were recorded
  on its branch (`trqroxpz`, `xqvqmyrq`, `xnmyynvx`), their logs and run records copied here, and the three branches
  merged with the default line. The workspaces `cleanup-native`, `cleanup-jbmc`, `cleanup-examples` and
  `cleanup-integration` are forgotten; their directories are the user's to delete. Each stream's own Progress, in
  full, is in its brief (`cleanup-native.md`, `cleanup-jbmc.md`, `cleanup-examples.md`), as its branch left it.
  - **Deferred by the timebox:**
    - **VF-002's examples 147 and 148** (examples stream). After `excerpts()`'s fix, `20261107-163046-…`/`-163047-…`
      failed at "apply the patch" (fixed by rebasing the patches' `Tests.java` hunk), then
      `20261107-165152-example-147-…`/`-148-…` failed in `stage_contracts` (`examples/tools/build.py:432`) with
      `FileNotFoundError` for `gaps.contracts`. The finding: since `myrqmxqq` (2026-11-05), `run()` hands each runner
      the attempt directory, and `stage_contracts` and `contracts_digest` read the example's `approach.contracts`
      file from it. A further attempt passes the example's folder to both, with a `test_build.py` reproducer, and
      resubmits the two jobs, about 2 minutes each. 149 passed (`20261107-165152-example-149-…`).
  - **Deferred to the user, not by the timebox:**
    - **VF-018** (jbmc stream, by decision 6). At 1800 s, `20261107-164356-vf-018-prices-prices-total-s-computed-in`
      passed. `-164356-vf-018-objects-kernel-price-s-output-rel`, `-164356-vf-018-lines-lines-reprice-s-equations-t`
      and `-164356-vf-018-orders-orders-reprice-s-equations` each timed out on their first JBMC run. What is left to
      prove in all three is two 64-bit products of symbolic operands being equal, which the own checker proves in
      under 0.1 s. Options, in `cleanup-jbmc.md`: a longer limit again, another solver or `--refine-arithmetic`, or
      leaving these four confirmations to the own checker.
    - **VF-001** (jbmc stream). Its check can't pass as written: in `20261107-172721-conformance-corpus-under-jbmc-and-engine`
      both ignored conformance tests pass (2 passed, 0 failed), but the step exits 1, because its `tee
      target/conformance-jbmc.log` opens before cargo makes `lib/target/` in the fresh work directory. The original
      jobs' logs open with the same error. The user can take that test result as the check, or have both jobs
      resubmitted with only `mkdir -p target &&` added. The sibling `-172721-…-under-engine-auto-con` was stopped by
      VF-021's scope-name collision (since fixed).
    - **VF-015** (native stream's N3). `20261107-165827-example-109-…` failed at step 3: JBMC now proves the old
      `toDigit`, but strict refuses the proof, which reaches JBMC's stub of `String.format`. The user has since chosen
      [`stub-reachability.md`](stub-reachability.md) (`rmvlorrs`) over a `String.format` model, and that brief closes
      VF-015 after this merge.
  - **native** (`ruvmympl` … `wpxntpty`): VF-010 closed by `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t`
    and `-165544-vf-010-s-integration-tests-at-the-fix-li`: probes budgeted in solver conflicts, not seconds. Its
    benchmark comparison `20261107-184603-…` gave 557 runs, 0 verdicts changed, and closed VF-021. VF-011 passed by
    `20261107-171502-vf-011-example-052-under-strict-on-the-o` (052 established by the own checker under strict):
    unwinding counted per entry of a loop.
  - **jbmc** (`zykkyuuw` … `wuxrynko`): VF-009 closed by `20261107-172721-jbmc-s-extra-initializers-named-and-refu`:
    JBMC hands a throwing class initializer's exception to its caller unwrapped, and the preflight names it as the
    defect kind `throwing-initializer`. Cause 5 is drafted in [`jbmc-upstream.md`](jbmc-upstream.md). VF-019 closed by
    `20261107-172721-nullable-and-one-array-parameters-in-pro`: `--confirm`'s refusal of a widened domain is named.
    `20261107-171442-…` measured the new guard: it refuses none of the 41 recorded JBMC examples' obligations.
  - **examples** (`wurnsyot` … `swopzxzu`): VF-016 closed by `20261107-165152-example-160-…` and
    `-165153-example-161-…`. VF-017 closed by `20261107-164043-example-150/151/152-…`. VF-014 closed by
    `20261107-183328-vf-014-h1-isolated-run-3-of-3-the-benchm` (H1 changed no verdict), and the fresh
    `lib/benchmark/results.json` (`20261107-183709-…`, 2829 runs) is applied. VF-013 is done by `sync.py`'s
    tests (`test_runs.py`): each run record is published redacted under its session's trace. The three foundations
    leftovers are fixed with tests: the allocation bound is checked, a claim naming an input its subject doesn't take
    is refused, and a reused proof names the builds its run was given.
  - **The merge.** Only generated trace files conflicted, and `llm-dlc/README.md`: the default line's
    application-core sentences and the examples stream's run-record paragraph are both kept. Other files that two
    lines changed (`lib/src/equivalence.rs`, `lib/tests/heap.rs`, `lib/README.md`, `examples/index.json`) merged
    cleanly with independent edits. `build.py --index-only` marks 149's page current, now that its job has passed.
- **Phase 4, step 2: the run records published** (2026-11-07). The merge's `sync.py commit` (`lpvnwkuz`) published
  all 18 records in `llm-dlc/loop-summaries/`, the streams' own included. Each is under its session's trace
  (`llm-dlc/traces/<session>/runs/`, 8 sessions), linked from that session's `summary.md`, and none holds a `/home/`
  path. `sync.py check` gives 0 errors and 0 warnings. Its one note on the records is that this loop's own record
  (`2026-11-07-212943-cleanup.md`) has grown since and is republished by the next sync. That meets VF-013's "Closes
  when", which is for the verification agent to record in `findings.md`. The two integration reports there
  (`cleanup-integration.md`, `foundations-integration.md`) are not run records and are left unpublished.
  - Next: step 3's job at the merge commit (examples 150–152, 160–161, 170–172 and 190–196, plus
    `lib/tests/integration.rs`, since VF-010's integration job ran before the merge).
- **Phase 4, step 3: the merge's examples queued** (2026-11-07). One job per app, each running every example's
  `build.py` step even if one fails, plus `lib/tests/integration.rs` as it is:
  - `20261107-215001-cleanup-merge-crosscut-s-examples-150-15`: 150 verified, 151 violation, 152 verified,
    160 verified, 161 violation;
  - `20261107-215001-cleanup-merge-deliveries-examples-170-17`: 170 verified, 171 and 172 violation;
  - `20261107-215001-cleanup-merge-shop-s-examples-190-196-re`: 190 and 195 verified, 191–194 violation,
    196 unverifiable;
  - `20261107-215001-cleanup-merge-lib-tests-integration-rs-a`: every non-ignored test passes.

  They run at the commit that queues them, whose code is the merge's (`lpvnwkuz`): the commits since change only
  generated trace files and this Progress. No job was pending for these examples, so none is superseded.
  - Next: read the four results, then step 4's for-review list.
- Status: waiting on jobs 20261107-215001-cleanup-merge-crosscut-s-examples-150-15 20261107-215001-cleanup-merge-deliveries-examples-170-17 20261107-215001-cleanup-merge-shop-s-examples-190-196-re 20261107-215001-cleanup-merge-lib-tests-integration-rs-a

## Loop settings

- session: 2d24d762-29a6-4514-a681-485fd10f1c7e
- model: claude-opus-5-5
- effort: high
- integration: llm-dlc/tools/cleanup-integration.sh
- new-window: no

## Loop until

The reconcile comes first. Don't stop before the merge is committed unless a stream is unfinished or the merge needs
the user. Then Phase 4. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`, `done`, or
`blocked: ...` with what needs the user. Stop with `done` once Phase 4's criterion is met and the for-review list
names every entry's state. Don't take on items beyond the ones this brief names: a new finding goes into the
for-review list. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't
go on to polish.
