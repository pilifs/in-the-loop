# Stream brief: engine priorities, the JBMC side and the measurements

One of two streams of [`engine-priorities.md`](engine-priorities.md) that run in parallel, each in its own jj
workspace on its own branch. The other is [`engine-priorities-native.md`](engine-priorities-native.md). Once both have
stopped, a reconcile loop merges them; [Streams](engine-priorities.md#streams) in the main brief says how.

Started with the other stream by `llm-dlc/tools/run-streams.sh engines` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh engines-jbmc` from this stream's workspace (`jj workspace root --name jbmc`):
the loop refuses any other.

**The main brief is the instruction.** Read [`engine-priorities.md`](engine-priorities.md) in full every cycle, and its
input [`engine-priorities-review.md`](engine-priorities-review.md) too. Its direction, evidence, working rules,
deferrals and decisions all apply here. This file only says which part of its plan is yours, and keeps your Progress.
Don't edit the main brief, the other stream's brief, or anything outside this file's `## Progress` section.

## Your phases

In the main brief's order:

1. **1a** exclusive JBMC phases, with fixtures from real JBMC 6.11.0 output;
2. **1b** the SAT backend recorded for both engines. You define the shape in `results.json`'s environment and in each
   result's evidence. Record the own checker's CaDiCaL (version from the `cadical` crate) as it stands; the native
   stream adds Bitwuzla later in the same shape;
3. **2a–2c** the staging-policy option, the benchmark job, and JBMC's default decided from it;
4. **3** the two witnesses that don't reproduce;
5. **4a** the strict job on both engines over the 41 JBMC examples, with `gap_table.py --json`.

Not yours: 1c, 4b, 4c, 5 and 6. 4c needs both 4a and the native stream's 4b, so the reconcile loop does it.

## Boundaries

You own the JBMC adapter and the measurements: `lib/src/jbmc.rs`, `jbmc_gaps.rs`, `jbmc_contracts.rs`,
`phases.rs`, `deadline.rs`, `lib/benchmark/`, `examples/tools/gap_table.py`, and their tests and fixtures.

The native stream owns `lib/src/bmc/`, `lib/models/` and the solver interface. Don't change them. If your work needs
a change there, record it under Progress for the reconcile loop and work around it.

Some files both streams may touch: `lib/src/main.rs` and `lib.rs` (CLI options, module list), `lib/tests/conformance.rs`
and `lib/tests/conformance/`, `lib/src/interp/`, `witness.rs`, `shrink.rs`, `Cargo.toml`. In those, add rather than
rewrite: new options, new cases and new functions, not reorganizations. Name every change to one of them under
Progress, so the reconcile loop knows where to look.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Jobs.** Submit and commit jobs as usual. The runner works in the default workspace and also runs jobs committed
  here, at this commit (see `verification/README.md`). Results are collected there, not here: read them with
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" report` and `status`, and the files under
  that workspace's `verification/results/`. Record what you take from a result under Progress with the job id. Its
  outputs reach this branch only at the merge, so don't copy them in by hand.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by
  `run-streams.sh`, which runs this loop unattended: `- Status: working` while there is work you can do,
  `- Status: waiting on jobs ID ...` when everything left waits on those jobs (it runs the loop again once their results
  are collected), `- Status: done` when your phases are finished, or `- Status: blocked: ...` with what needs the user.
- **Another session is not your concern** beyond the loop's usual rule: the native stream works in its own directory
  and never touches this working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `3761db96`,
  compacted), so you share its context with the other stream. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- **1a, exclusive JBMC phases: done.**
  - `lib/src/phases.rs` reads JBMC's timers per solver call. `Runtime Solver` covers the whole call, so the
    `Runtime Post-process` inside it counts under `encoding` only. A call that printed neither that line nor CaDiCaL's
    `N variables, M clauses` never reached the SAT solver, so all of it is `encoding`.
  - `Phases::excess` flags a run whose named phases add up past its seconds by more than 1% plus 5 ms. The JSON
    carries the excess as `phases_excess` on `deadline::Run`; nothing is scaled. `lib/benchmark/run.py` records it per
    case as `phasesExcess` and leaves such runs out of the phase tables, naming them below.
  - Fixtures are real JBMC 6.11.0 runs on cvm (x86_64), in `lib/tests/fixtures/jbmc-phases/`: `held/prefix-sums`
    proved (Post-process 0.175 s inside Solver 2.955 s), the same cut off at 1.9 s, `held/reverse` out of memory at
    700 MiB, and two solver calls in one run.
  - The nesting shows in the message times. Job `20261106-192959` (network) checks it against CBMC's source at
    `cbmc-6.11.0`. Nothing waits on it.
  - Shared files changed (added to, nothing reorganized):
    - `lib/README.md`: one clause on `phases_excess` in `--json`'s description;
    - `lib/src/jbmc.rs`: `json_items` is `pub(crate)`, for the tests.
  - **For the reconcile loop:** on cvm, `conformance.rs`'s
    `the_corpus_agrees_with_the_jvm_on_the_tools_own_checker` fails with 12 disagreements. Not rerun at the base; the
    messages point away from this change.
    - The cause: the JDK is 25.0.5, but the contract library's records (`lib/models/contracts/`, the native stream's)
      were written for 25.0.4.1, so advised runs print "is not the library's, on its record".
    - It may also touch 2b's advised runs.
- **Next:** 1b, the SAT backend in `results.json`'s environment and in each result's evidence.
- Status: working

## Loop settings

- session: 7b8a1d3b-6fbf-40ab-b647-1f9fc12bc573
- model: claude-opus-5-5
- effort: high
- workspace: jbmc
- fork: 3761db96-b870-47f7-aded-2ba264c165f4

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Phases 1 and 2 are the core of this
stream: don't stop before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop: you are run again once their results are collected. Stop with `done` when your
phases are finished, or with `blocked: ...` when what is left needs the user's input and is recorded under Progress
as deferred. Don't go on to polish, and don't start work that belongs to the other stream or the reconcile loop.
