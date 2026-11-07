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
- Status: working

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
