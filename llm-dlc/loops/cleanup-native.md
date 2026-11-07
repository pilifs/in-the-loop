# Stream brief: cleanup, the own checker

One of three streams of [`cleanup.md`](cleanup.md) that run in parallel, each in its own jj workspace on its own
branch. The others are [`cleanup-jbmc.md`](cleanup-jbmc.md) and [`cleanup-examples.md`](cleanup-examples.md). Once
all three are finished, the main brief's loop merges them ([Reconciling](cleanup.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh cleanup` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh cleanup-native` from this stream's workspace (`jj workspace root --name cleanup-native`). The
loop refuses any other.

**The main brief is the instruction.** Read [`cleanup.md`](cleanup.md) in full every cycle, and its inputs. Its
direction, starting point, working rules, deferrals and decisions all apply here. This file says which items are
yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section. Edit implementation
files according to the main brief's [ownership](cleanup.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/cleanup-integration.md`, if it exists. A failure in your
files on the latest combined commits is your next piece of work.

## Your items

In order:

- **N1. VF-010, probe budgets that don't depend on the clock.** `Engine::probe` (`lib/src/bmc/mod.rs:1326`) gives a
  branch probe as long as all the solver calls so far took, at least a second. So which side of a branch stays
  undecided depends on how fast the machine is.
  - Reproducer first. The entry's own is 8 runs of `jvmcontract equivalence --target 'fixtures.Pricing#total'
    --engine native --timeout 40` on `lib/tests/integration.rs`'s fixture. At most 8 × 40 s, so it is a quick job,
    not inline. It shows the runs differing: 6 found the violation in about 4 s, and 2 ran out of time.
  - Then budget probes by solver work (conflicts, propagations or solver calls, whatever the solver behind
    `self.b` can limit), not by `Instant`.
  - Keep the design the doc comment states: an undecided side is decided after the decided paths, with all the time
    left. Only the budget's unit changes.
  - The overall deadline stays wall-clock. It is the user's `--timeout`.
  - Check that no recorded own-checker verdict changes:
    - the unit and integration tests inline;
    - the benchmark's own-checker runs at the fix and at its parent, compared, so that only this change is measured.
      Use the examples stream's pattern (its E2): two recording jobs with `submit --revision`, then a quick
      comparison job over their collected outputs. Don't compare with the committed `results.json`: VF-014 is
      about how stale it is.
  - **Closes when** the reproducer gives the same answer in 8 of 8 runs, and a job runs the integration tests with
    no failure. Submit both, naming VF-010.
- **N2. VF-011, unwinding counted per entry of a loop.** `Engine::jump` (`lib/src/bmc/mod.rs:1945`) counts back
  edges per path and `(class, method, target)`, and never resets the count when the loop is left.
  - Reproducer first. A nested loop whose inner loop runs fewer than `--unwind` times on each entry, but more in
    total, is left unwound today. The harness of example 052's property (a `\max` over `k` of a `\sum` over `i < k`)
    is one.
  - Then count per entry of a loop. The count of a loop starts again when the path enters it afresh, and is kept
    while it stays in the loop.
  - It must stay a bound. Every path still ends, and a path cut short still gives no verdict, never a proof:
    - unwinding assertions keep their meaning;
    - a loop that is left and re-entered by a back edge of an outer loop is bounded by the outer one's count.
  - **Closes when** a job runs 052 under strict on the own checker (`approach.engine` set to native in a copy, as
    the entry says) and it is established with no gap.
- **N3. VF-015, example 109's replay.** Job `20261103-010716-example-109-revisited-hex-todigit-s-regr` failed at its
  step 3. JBMC refuted the old `Hex#toDigit` on `ch == 1632`, but the interpreter could not replay the witness: it
  refuses `reads static field java.nio.charset.StandardCharsets.UTF_8` (`lib/src/interp/natives.rs:373`).
  - First resubmit the job unchanged at your current commit (`pipeline.py resubmit`). JDK models have shipped with
    jvmcontract since then, and the failure may be gone. Its step 1 clones Commons Codec, which needs the network.
  - If it fails the same way, make the interpreter read `StandardCharsets`' constants as the JVM has them (or the
    static finals of JDK classes it can initialize as the JVM would), with a reproducer in the interpreter's tests.
    Then resubmit. A witness the interpreter can't run stays "could not replay", never a pass.
  - **Closes when** the job, resubmitted at a fixing commit, passes. If it fails again for a reason outside replay
    (JBMC, the clone), that is the timebox's call. Name what failed under Progress.

**Not yours:**
- JBMC's side of any disagreement, `auto` and `--confirm` (the jbmc stream);
- `build.py` and the benchmark's recording (the examples stream).

A model change in `lib/models/` is the jbmc stream's. If you need one, say so under Progress.

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

- **N1, step 1: the reproducer, before the fix.** New script `lib/tests/reproducers/vf-010.sh`: it compiles
  `integration.rs`'s Pricing fixture and its rounding refactor, runs the entry's `jvmcontract equivalence ...
  --engine native --timeout 40` N times, prints each run's exit and the own checker's numbers, and exits 0 only when
  every run finds the violation. Job `20261107-163057-vf-010-s-reproducer-before-the-fix-prici` runs it 8 times at
  this commit, expecting exit 1 (runs that differ). One debug run here found the violation in 2.7 s (13 solver calls,
  1 of 2 divisions built in full). Next: the fix. CaDiCaL's per-call `conflicts` limit (`cadical::Solver::set_limit`)
  can budget a probe by solver work; the deadline stays the terminate callback's wall-clock.
- **N1, step 2: the fix, and its checks queued.** `Engine::probe` now gives a probe as many conflicts as all the
  solver calls so far had, at least `PROBE_CONFLICTS` (10,000), through a new work limit on `Sat`
  (`set_work_limit`, `work`) and `Blaster`. `solve_until` counts the conflicts across its refinement calls. CaDiCaL's
  conflicts are counted as the clauses it learns (one per conflict of its search). The call is stopped through the
  terminate callback, which CaDiCaL polls on a count of its steps, so the stop is the same on every run. CaDiCaL's
  own `conflicts` limit also counts inprocessing conflicts, a different unit, so it isn't used. Bitwuzla has no such
  limit and keeps the old wall-clock budget. Transcripts record a probe's limit (`conflicts N` after `limit`), and
  replay gives it again.
  - The cause, measured: the probe that finds Pricing's violating side needs 5,167 conflicts, about 1.04 s here, just
    over the old 1 s floor. At a 2,000-conflict floor it is left undecided and the run times out at 40 s, so 10,000
    gives it twice that margin.
  - Verified inline:
    - 8 of 8 reproducer runs found the violation with identical numbers;
    - new tests: `a_conflict_limit_stops_a_call_at_the_same_work_every_time`, and the logged-solver test checks
      probe limits and their replay;
    - every lib suite passed, unit tests and `integration.rs` included.
  - Jobs:
    - `20261107-165544-vf-010-s-reproducer-at-the-fix-pricing-t` (expects exit 0) and
      `20261107-165544-vf-010-s-integration-tests-at-the-fix-li` close VF-010 when both pass;
    - `20261107-165544-vf-010-s-benchmark-at-the-fix-run-1-of-2` (at the fix: it carries no `--revision`, so it runs
      at the commit that adds it) and `20261107-165544-vf-010-s-benchmark-at-the-fix-s-parent-r` (`--revision`
      c307e721) record the own checker's benchmark runs to `lib/target/benchmark-native-vf010-{fix,parent}.json`.
  - Next for N1: once both benchmark runs are collected, a quick comparison job over their outputs. Every verdict
    should be the same.
  - Shared file: `lib/README.md`'s sentence on the probe budget now says conflicts, not seconds (a rewrite of one
    sentence, since the docs move with the behaviour).
  - **For review:**
    - One clock dependency is left: after the first violation, the search for a smaller witness shortens the
      deadline to the time taken so far, at least a second (`check`, `lib/src/bmc/mod.rs` ~957). That can change which
      witness is reported, but not the verdict, so it is outside VF-010.
    - Step 1's `sync.py commit` reported 4 errors that aren't this stream's:
      - session `2df7775c`'s log `3f768f3bb246` is neither stored nor uploaded here (it is only in the default
        workspace's `llm-dlc/traces/`);
      - other workspaces' commits `zykkyuuw` (jbmc stream) and `syqpoxom` (verification loop) have no manifest
        here.

      The foundations streams saw the same (`foundations-alignment.md`), and the merge should resolve them.
  - Next: N2's reproducer (VF-011), and N3's unchanged resubmission (VF-015).
  - Correction: step 2's `sync.py commit` reported 13 errors, not 4, all of the same kind (none from this session):
    session `2df7775c`'s log `3f768f3bb246`, and commits of the sibling streams and the verification loop with no
    manifest in this workspace (`uxvwumlz`, `lqozoovu`, `ulvlrqwu`, `pkuvkyln`, `muznwonp`, `wmuwlwkx`, `uytnkqst`,
    `vtkypktk`, `wurnsyot`, `zykkyuuw`, `syqpoxom`).
- **N3, step 1: the unchanged resubmission.** Job `20261107-165827-example-109-revisited-hex-todigit-s-regr`
  supersedes `20261103-010716-…` with its steps, expectations and budget unchanged. Only its title and description
  now name VF-015. It runs at this commit (no `--revision`). Its step 1 clones Commons Codec, so it needs the network.
  As read, the interpreter still refuses static fields it doesn't know (`lib/src/interp/natives.rs:373`), so if JBMC
  still refutes step 3's claim, its witness will fail to replay the same way, and the fix comes next.
  - Next: N2's reproducer (VF-011), while this job and N1's four are pending.
  - Correction: N1's step-2 entry above lists `pkuvkyln` (it read `pkuvkylu`, a typo).
- **N2, steps 1 and 2: the reproducer and the fix, with 052's job queued.** Unwinding is now counted per entry of a
  loop. Each frame keeps its own counts, by loop head. A back edge from `from` to `target` counts for `target`, and it
  starts again the count of every head after `target` and up to `from`, the loops nested in its body. So an inner
  loop gets `--unwind` iterations per iteration of the loop around it, and per call of its method, as JBMC's
  `--unwind` counts.
  - It stays a bound. On a path that never ends in a frame, the lowest head it keeps going back to is started again
    only by a back edge to a lower head, which the path takes finitely often. So that count passes `--unwind` and the
    path ends unwound, with no verdict. Calls are still at most 64 deep. A merge keeps the lower count per frame, as
    it did per path. This argument is in `Engine::jump`'s doc comment.
  - The reproducer is new unit tests in `lib/src/bmc/mod.rs`. Before the fix the first and third failed with "not
    fully unwound" (`Check.check at pc 15`, `Check.count at pc 3`), and after it they pass:
    - `an_inner_loop_is_unwound_per_entry_of_it`: 4 × 3 nested iterations under `--unwind 4`, and 052's shape
      (`\sum` over `i < k` inside a loop over `k < n`, `n` up to 5) proved under `--unwind 5`. An inner loop of 5
      iterations is still beyond `--unwind 4`;
    - `a_loop_entered_again_by_an_outer_back_edge_is_bounded_by_the_outer_count`: an outer loop of 5 iterations with a
      one-iteration inner loop is still unwound, and so are two overlapping loops, neither inside the other, whose
      back edges alternate. This guard passed before the fix too;
    - `a_loop_is_unwound_per_call_of_its_method`: four calls of a method whose loop runs 3 times.
  - Verified inline: every lib suite passed (unit 207, `integration.rs` 64, conformance, heap, observations,
    alignment and the rest).
  - Job `20261107-171502-vf-011-example-052-under-strict-on-the-o` is the entry's check, and closes VF-011 when it
    passes. It copies `examples/`, sets 052's `approach.engine` to native in the copy, runs `build.py 052`, and
    expects every obligation established, by the own checker, under strict, with no gap.
  - **For review:**
    - The own checker now explores nested and repeatedly called loops further before it stops, so some of its
      "not fully unwound" results may become verdicts, or timeouts. Both are sound outcomes. N1's benchmark jobs
      were submitted before this change, so they don't measure it.
    - `examples/coverage.md` (extension 2) still describes the count as per path. It is the examples stream's file.
  - Everything left waits on jobs: N1's comparison job needs both benchmark outputs, N2 needs 052's job, and N3 needs
    109's.
- **The seven jobs' results, read, and N1's benchmark pair resubmitted.** All ran on `vm-1` and were collected in
  `rzmrlklw` (default line).
  - **N1 (VF-010): its closing checks passed.** `-165544-…-reproducer-at-the-fix…` found the violation in 8 of 8
    runs with the same numbers, and `-165544-…-integration-tests-at-the-fix…` had 64 passed, 0 failed. The
    verification agent closed VF-010 with them. Its caveat: the reproducer before the fix (`-163057-…`) did not
    reproduce on `vm-1` either (8 of 8 alike, so that job is recorded as failed). `vm-1` shows the fix stable, not the
    cure of `cvm`'s timeouts.
  - **N1's benchmark pair was stopped by the runner, not by the benchmark** (VF-021, raised by the verification
    agent). The runner names a step's systemd scope `vjob-<id[:40]>-<step>` (`verification/pipeline.py`, `Step` and
    its callers). Both ids begin `20261107-165544-vf-010-s-benchmark-at-th`, so the two steps had one unit name:
    - the parent job's step, starting at 17:52:42, stopped "a leftover of the same name", which was the fix job's
      running step (SIGTERM after 2m19s);
    - the fix job's cleanup then stopped the parent's new step (SIGTERM after 0.2 s).

    Both are resubmitted with their revisions pinned: `20261107-183538-vf-010-s-benchmark-at-the-fix-run-1-of-2`
    (`--revision f606b0d8`, the fix) and `20261107-183544-vf-010-s-benchmark-at-the-fix-s-parent-r`
    (`--revision c307e721`, its parent). Their ids differ within 40 characters. Steps and outputs are unchanged, and
    the descriptions name VF-021. This is N1's second attempt at the comparison: one more failure ends it by the
    timebox.
  - Next for N1: once both are collected, the quick comparison job over
    `lib/target/benchmark-native-vf010-{fix,parent}.json`, which closes VF-021 with them.
  - **N2 (VF-011): its closing check passed.** `-171502-…` gave "052#0: established, engine native, gaps [], modes
    ['strict']". VF-011 closes when the verification agent records it. N2 is done here.
  - **N3 (VF-015): the resubmission failed at step 3, for a reason outside replay.** JBMC now proves the old `toDigit`
    for `ch == 1632`, the Character.digit model at work, so there is no witness to replay. The step passes no `--gaps`,
    so strict applies, and jvmcontract refuses the proof. It reaches JBMC's stub of
    `String.format(String, Object[])` (`jdk-static-method:…@jdk-25.0.5`), which returns null or any object. That is on
    `toDigit`'s exception path. Steps 4 and 5 were skipped. Counted as N3's first failure.
    - No commit of this stream can make the job pass:
      - a model of `String.format` is in `lib/models/`, the jbmc stream's;
      - giving the step `--gaps assume` or advised changes the check, which is the user's call.
    - So N3 waits on one of those, recorded here for the main brief's for-review list.
    - As read, `get_static_jdk` (`lib/src/interp/natives.rs:373`) still refuses `StandardCharsets`' fields. Hex's
      `DEFAULT_CHARSET` reads `StandardCharsets.UTF_8`, so step 4's replay may meet it once step 3 passes. The brief
      asks for that fix only if the replay fails the same way, so it is not done here.
  - **For review:**
    - The unit-name collision is the runner's (`verification/pipeline.py`, not this stream's). It also stopped the jbmc
      stream's `20261107-172721-conformance-corpus-under-engine-auto-con` (SIGTERM at 17:55:32, when
      `…-conformance-corpus-under-jbmc-and-engine` started), whose first 40 characters are the same. Any two jobs
      submitted in the same second with titles alike in their first 24 characters can collide.
    - Making the unit name unique, by the full id or a hash of it, is a one-line fix for whoever keeps the pipeline.
- **N1, step 3: the benchmark pair passed, and its comparison queued.** Both resubmitted jobs passed on `vm-1`
  (`-183538-…-run-1-of-2` at f606b0d8 and `-183544-…-s-parent-r` at c307e721, 3m11s each, with no unit-name
  collision this time). Their outputs were applied to the runner's `lib/target/` (gitignored).
  - Job `20261107-184603-vf-010-s-benchmark-compared-the-own-chec` is the comparison. It finds each output by the
    sha256 its run recorded, in the runner's `lib/target/` or under `verification/results/ID/outputs/`, and compares
    every own-checker run by (case, mode), as the examples stream's VF-014 comparison does. It exits 1 if a verdict
    differs or a case is in one run only, and 2 if an output is missing or not the recorded one. It closes VF-021
    when it passes.
  - Tried here on the same files: 557 own-checker runs, none new or gone, 0 verdicts changed, 0 formulas grown past
    10%, 0 paths or merges changed. So on the benchmark, the conflict budget decides the same sides as the old
    wall-clock one did on `vm-1`. The step was also run in a mock runner tree, where it gave exit 0, and exit 2 with
    the outputs removed.
  - The unit-name collision listed for review above is fixed in the runner, by the verification agent: a scope is
    now named by the first 30 characters of the id and a hash of the whole id (`scope_id`, per VF-021 in
    `findings.md`).
  - The integration check's latest report (18:28) is a conflict in generated trace files (`llm-dlc/README.md`,
    `index.json`, `traces/README.md`, `traces/metrics.json`), not in this stream's files.
  - Left: N1 waits on this job. N2 is done. N3 waits on a `String.format` model (the jbmc stream's) or the user's
    decision on step 3's gap mode, as recorded above.
- Status: waiting on jobs 20261107-184603-vf-010-s-benchmark-compared-the-own-chec

## Loop settings

- session: 2324d402-3f17-421a-8a85-5b6846d2c728
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: cleanup-native
- fork: 2df7775c-45a1-40a7-924b-75602d8ad256

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when every item is closed by its check or deferred by the timebox. Stop
with `blocked: ...` when what is left needs the user and is recorded under Progress. Don't take on work beyond your
items: anything new you find goes under Progress, for the main brief's for-review list.
