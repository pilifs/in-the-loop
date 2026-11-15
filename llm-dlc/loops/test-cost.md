# Brief: test cost: cheap by default, expensive once

**Status of the brief**: drafted 2026-11-15 from the user's request and a measurement of the loops' time; the
[decisions](#decisions) are proposed, for the user to settle before launch.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run alone in the default workspace once example-targets
is done: `llm-dlc/tools/feature-loop.sh llm-dlc/loops/test-cost.md`.

Every test gets a cost tier, the tests run by default are cheap, and an expensive test runs as a queued job, once for the
inputs it checks. Agents are steered away from running expensive tests and from writing them where a cheaper test shows
the same thing. Where an expensive test is needed, a cheap proxy beside it gives an indicative result while iterating.

**Inputs.** Read these in full before the first piece of work of every cycle:
- [Where it starts from](#where-it-starts-from), below: the measurement this brief rests on.
- [`lib/README.md`'s Tests section](../../lib/README.md#tests): what the Rust tests need and what is already ignored.
- [`verification/README.md`](../../verification/README.md): what is queued and how, and its table of estimates.
- [`brief-template.md`](brief-template.md#standing-rules): the standing rule on what runs inline, which this brief
  changes.

## Direction

- **Every test declares its cost.** Three tiers, by what a test runs and what it measures on this machine (thresholds in
  [decision 1](#decisions)):
  - **unit**: in process, with no subprocess and nothing outside the repo. The default for a new test.
  - **tool**: spawns `javac`, `java`, the `jvmcontract` binary or a stand-in script; seconds. Runs inline.
  - **proof**: spawns JBMC, TLC or a solver on more than a toy, or goes over the tool tier's time or memory. Never runs
    in a plain `cargo test` or a Python test run. It runs as a pipeline job.

  Benchmarks stay as they are: queued (`preparation.rs:249`, `lib/benchmark/run.py`).
- **The default run is cheap.** `cargo test` in `lib/` and each Python suite run only the unit and tool tiers, within a
  stated budget ([Done when](#done-when)). While iterating, run the tests of what you changed. Run the whole default
  run once before committing.
- **An expensive test runs once for its inputs.** A later change makes an earlier run worthless, so running the proof
  tier while iterating is waste. It runs:
  - as a job committed with the change (`(verification pending)`), once the change is finished;
  - only for the tests whose inputs that change touched.

  A test whose inputs have not changed since a job passed it is not run again; the job's result stands for it.
- **A proof-tier test has a cheap proxy.** The proxy is a tool-tier or unit-tier test that checks the same behaviour as
  far as it can without the expensive tool. Ways to do that:
  - replay that tool's recorded output (the stand-in scripts at `lib/tests/values.rs:1253`, `lib/src/jbmc.rs:970` and
    `lib/tests/conformance.rs:22` already do this);
  - use a smaller bound;
  - check the generated harness or goto program instead of solving it.

  A proxy's pass is reported as indicative, never as verified. A proxy whose recording no longer matches its input says
  so, and points at the proof-tier test.
- **Write the cheapest test that shows the behaviour.** A new proof-tier test carries three things:
  - its tier and a cost estimate, in its tag;
  - the reason a cheaper test cannot show the same thing;
  - its proxy.

  A test that spawns JBMC or TLC without a proof tag, or that measures over its tier's threshold, is caught: by a lint
  in the default run, and by the measuring job.
- **Nothing gets weaker.** Tiers change when a check runs, not whether it runs:
  - a test moved to the proof tier is run by a job in the commit that moves it;
  - a verdict still needs the real tool (only JBMC's `VERIFICATION SUCCESSFUL` is a proof);
  - no test is deleted or relaxed to make it cheaper.

  Making a test cheaper keeps it equivalent: the same inputs and claims, through a smaller harness or a recorded
  answer.

## Where it starts from

Measured on 2026-11-15 from the redacted logs of 27 sessions in 9 jvmcontract loops, 2026-10-31 to 11-14 (early feature
loop, build-orchestration, sound-verdicts, engine-priorities, foundations, cleanup, stub-reachability, application-core,
example-targets). Each batch of parallel tool calls is counted once, as the time the agent was blocked:

- **Active agent time 112h**: the model 56h, waiting on tools 45.5h.
- **What the 45.5h of tools went to:**

  | Category | Hours | Notes |
  |---|---|---|
  | cargo test | 17.8 | |
  | Waiting on cargo runs started in the background | 5.7 | |
  | cargo build/check | 2.9 | |
  | Proofs inline | 7.0 | 4.3 of it before the pipeline existed |
  | Integration checks inline | 2.6 | 2.2 of it example-targets |
  | Python tests | 1.1 | |
  | `build.py` | 0.8 | |
  | `sync.py` | 1.6 | |
  | Other | 3.4 | |

  Cargo is 58% of tool time and about a quarter of all active time. By loop, cargo test plus waiting on it took 45% of
  application-core's active time and 35% of foundations' and engine-priorities'.
- **Running tests, not compiling.** In the 939 runs whose output kept cargo's timings, compiling took 0.9h and running
  the tests 8.2h. Full-suite debug runs were 542 calls and 48% of cargo test time: median 17s, but one in ten took over
  2 minutes.
- **A few files are most of it.** In the timings captured, each of these calls JBMC, `javac` or the binary end to end,
  in only 10 to 14 tests:

  | File | Mean per run | Share of captured test time |
  |---|---|---|
  | `lib/tests/conformance.rs` | 63s | 35% |
  | `observations.rs` | 139s | 20% |
  | `integration.rs` | 21s | 10% |
  | `alignment.rs` | 45s | 7% |
  | `application_core.rs` | 42s | 7% |

  `cargo test` runs its test binaries one after another, so these add up even on 30 vCPUs. cargo-nextest is not
  installed.
- **Verification jobs cost elapsed time, not agent time.** Median from submit to collected:

  | Loop | Median |
  |---|---|
  | foundations | 9h (8.4h of it in the queue, with no runner) |
  | cleanup | 1.6h |
  | engine-priorities, application-core, example-targets | 0.3h or less, with the verification loop beside the streams |

What exists already:
- **The suites:** 25 test files in `lib/tests/` with 384 `#[test]`s, and 258 unit tests in `lib/src/`. Python has 24
  `test_*.py` files across `examples/tools/` (and `targets/`), `llm-dlc/tools/`, `verification/`, `lib/benchmark/` and
  `lib/solvers/`.
- **Twelve ignored tests** with a reason, of which eleven say they "run JBMC …: a pipeline job" and one is a benchmark.
  They are in `heap.rs` (9), `conformance.rs` (2) and `preparation.rs` (1).
- **What runs regardless:** most JBMC calls in `integration.rs` (about 100 mentions) and the other slow files are not
  ignored, and run in every `cargo test`.
- **`JVMCONTRACT_SKIP_MISSING_TOOLS=1`** skips tests whose tool is missing. It is not a cost switch.
- **Undefined terms:** `verification/README.md` already says to keep "`cargo test` without the slow tests" inline, but
  nothing says which tests are slow. Its table estimates "`cargo test --release` in `lib/` with JBMC and TLC" at 2 CPUs,
  2G and 5 to 10 minutes.
- **The standing rule** in `brief-template.md` runs "compiling, unit tests and conformance cases on a real `java`"
  inline. The conformance cases are the costliest file.

## How to work through it

The [standing rules](brief-template.md#standing-rules), the [timebox](brief-template.md#the-timebox) included, with these
of its own:
- **Measure with jobs, not inline.** The full suite with the proof tier is a pipeline job, and so is any run over a
  minute. Inline, run only what you changed, at the unit and tool tiers. Follow this brief from its first cycle.
- **One file or one mechanism per cycle.** Retiering a test file is one step: tag its tests, give each proof-tier test
  a proxy, and queue the job that runs its proof tier. All in one commit.
- **A proxy is reviewed against its proof.** Before relying on a proxy, check that it fails where the proof fails: break
  the code it covers, or run the proof's recorded failing case, in a unit test or in the job.
- **Equivalence when making a test cheaper.** Say in the commit what the cheaper test still checks and what moved to the
  proof tier. A test made cheaper by checking less is a weakening, so don't do it.
- **Verification mode: with the pipeline.** A loop whose remaining work waits on jobs stops with
  `- Status: waiting on jobs ID ...`.

## The plan

### Phase 1: measure and classify

1. **The time analysis as a tool:** `llm-dlc/tools/tool_time.py`, which reads the redacted logs and reports blocked time
   by category, by loop and by test binary, as [Where it starts from](#where-it-starts-from) does. Parallel calls are
   counted once, and calls over two hours are left out. It is tested on made-up logs, and is used again in Phase 5.
2. **Per-test cost, as a job:** the whole Rust suite with the ignored tests, and each Python suite (`unittest
   --durations`). It records each test's time and the tools it spawns. With nextest ([decision 3](#decisions)) the
   times come from its JUnit output; without it, from a timed run per test binary.
3. **The inventory:** a generated `lib/tests/costs.json` (and one per Python suite, or one shared file), with each test's
   measured time and the tier it measures into. It is written by the job's outputs, never by hand, and shows which tests
   are mis-tiered today.

### Phase 2: the mechanism

4. **Rust tiers** ([decision 2](#decisions)):
   - The proof tier is `#[ignore = "cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST"]`. A plain `cargo test` skips it,
     `-- --ignored` runs it, and nextest selects it.
   - The tool tier is skipped under `JVMCONTRACT_TEST_TIER=unit`, through a helper each tool-tier test calls first, so
     a quick unit-only run exists.
   - The twelve existing ignore reasons are rewritten to the new form.
5. **Python tiers:** one `@cost("tool" | "proof")` decorator in a shared helper. The proof tier is skipped unless
   `TEST_COST=proof`, and the tool tier is skipped under `TEST_COST=unit`.
6. **One way to run each tier**, documented in `lib/README.md` and in CLAUDE.md: the default run, the unit-only run, and
   the proof tier as a job. The job is a `pipeline.py submit` recipe (or a `--tests proof` option) that runs the given
   proof-tier tests at the commit.
7. **The lint, in the default run:** a unit-tier test, like `tests/skill.rs`, checks three things:
   - every `#[ignore]` reason starts with `cost:`;
   - every proof-tier tag names a proxy that exists;
   - no test outside the proof tier calls the JBMC or TLC helpers directly.

   Python gets the same check. The measuring job of step 2 also flags a test over its tier's threshold, as an
   `attention` in its result.

### Phase 3: once for its inputs

8. **Reusing a passed result:** before running a proof-tier test, the job looks for a passing result of it at an
   earlier commit C. If none of the test's inputs changed since C, it skips the test and reports "passed at C, inputs
   unchanged". The inputs are the test file, its fixtures, `lib/src/`, `lib/Cargo.lock`, and the version of the tool it
   spawns. They are coarse at first; finer only if measurement shows the coarse set reruns too much. This builds on
   `verification/results/`, with no new store.
9. **The JBMC answer cache**, only as [decision 5](#decisions) settles. It is keyed exactly by class bytes, harness,
   options and JBMC version, and every reused answer says which run it came from.

### Phase 4: proxies, and retiering the slow files

10. **A record and replay stand-in for JBMC and TLC.** It builds on the existing stand-in scripts:
    - a proof-tier job can record each run's answer, keyed by a hash of its inputs, into fixtures that `collect` applies;
    - a proxy replays the recording;
    - a missing or stale key gives "no recording for this input: run TEST", never a pass.
11. **The five slow files, one per cycle:** `conformance.rs`, `observations.rs`, `alignment.rs`, `application_core.rs`,
    then `integration.rs`, which may take two cycles. For each, its tests are split into proof-tier tests and proxies, and
    its proof tier is queued in the same commit.
12. **The rest of the inventory:** every test the measuring job puts over its tier. Then the measuring job runs again,
    showing the default run inside its budget.

### Phase 5: guidance, and the next run measured

13. **The guidance**:
    - **CLAUDE.md** gets a short Tests section: which tier to run when, and that the proof tier is a job. Also: write the
      cheapest test that shows the behaviour, and give a proof-tier test a tag, a reason and a proxy.
    - **`brief-template.md`'s standing rule** names the tiers instead of "conformance cases on a real `java`".
    - **`verification/README.md`**: "the slow tests" become the proof tier, and its estimate row is updated.
    - **`lib/README.md`'s Tests section.**
    - **The integration scripts** (`*-integration.sh`) run the default tier and the proxies, and queue the proof tier.
14. **For-review list** in Progress:
    - tests whose proxy is weaker than its proof in a way worth knowing;
    - tests left over their tier, with why;
    - the default run's time before and after.

    `tool_time.py` is run on the next loop's logs once it exists, and its numbers are compared with the ones above.

## Done when

| Phase | Criterion |
|---|---|
| 1 | Every Rust and Python test has a measured time and a tier in the inventory, from a job. |
| 2 | Every ignored test carries a `cost:` tag. The lint is in the default run and passes. Each tier has one documented way to run. |
| 3 | A proof-tier job skips tests whose inputs haven't changed since a passing job, and says so in its result. |
| 4 | Each of the five slow files has its proof tier queued and proxies inline. The default `cargo test` (debug, warm) takes at most 60 seconds on this VM, against today's median full run of 17s and its p90 of 136s. The proof tier passes as a job. |
| 5 | CLAUDE.md, the brief template, the verification README and `lib/README.md` describe the tiers. The integration scripts use them. The for-review list is in Progress. |

## Deferred: not in this loop

- **Making JBMC, TLC or the native engine faster:** the engines' own loops do that.
- **Changing what a test checks:** this loop moves and proxies checks, and doesn't redesign them.
- **CI outside this machine.**
- **`examples/tools/build.py` runs:** already queued.

## Decisions

Proposed on 2026-11-15, for the user to settle:

1. **Tiers and thresholds:**
   - **unit**: no subprocess, under 1s.
   - **tool**: under 10s and 1 GB.
   - **proof**: JBMC, TLC, or over the tool tier's limits.

   Benchmarks stay queued as they are.
2. **The Rust mechanism:**
   - The proof tier is `#[ignore = "cost:proof: …"]`. It works with plain `cargo test` and with nextest, and needs no
     feature flags.
   - The tool tier is skipped under `JVMCONTRACT_TEST_TIER=unit`.

   The alternative, Cargo features per tier, recompiles the crate for each tier and is easy to forget.
3. **cargo-nextest:** install it (its prebuilt binary from github.com, hash-pinned, or `cargo install` from crates.io).
   It gives per-test times, runs tests in parallel across test files, and selects tests by name and binary.
   Recommended. Without it, step 2 measures per binary and the default run stays sequential across files.
4. **Where the proof tier runs:** only as pipeline jobs, never inline, and once per finished change, for the tests whose
   inputs it touched. The only exception would be the agent's own proxy failing in a way it cannot read; then it queues
   the one proof test with `--priority 10` rather than running it.
5. **The JBMC answer cache:**
   - Recommended: allowed for proxies and tool-tier runs, keyed exactly.
   - A job that claims a verdict runs JBMC fresh, unless the reused answer comes from a pipeline result with the
     identical key, and says so.
   - Alternative: no cache, with step 8 alone.
6. **Proxies:**
   - Required for every new proof-tier test.
   - Existing proof-tier tests get one in Phase 4 if they are in the five slow files. The others are listed for later.
7. **Python is in scope**, with the same tiers.
8. **Launch:** alone, in the default workspace, after example-targets is done. Model `claude-opus-5-5` at high effort,
   12G. Not beside conductor steps 4–6, which also edit the brief template and the
   integration check `run-streams.sh` runs; one after the other, in either order.

## Progress

- 2026-11-15, drafted from the user's request ("we should not be running expensive tests where we can avoid it, and
  frankly probably not more than once in many cases … they should also be discouraged from writing expensive tests when
  unnecessary, or at minimum, provide the option to run proxy tests that are much cheaper") and the measurement above.
- Status: draft: decisions to settle; launch after example-targets is done

## Loop settings

- session: 72d38e75-aae0-402e-9b8a-881beec53824
- model: claude-opus-5-5
- effort: high
- memory: 12G

## Loop until

Phases 1 to 4 first, in order, then Phase 5. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`
with the job ids, `done`, or `blocked: ...` with what needs the user. Stop with `done` once every criterion of
[Done when](#done-when) holds, or with the remaining items recorded as deferrals with their reasons. A test whose proof
tier fails twice is deferred by the timebox, never made cheaper to pass. Items deferred by the timebox count as recorded
deferrals, never as a reason to keep going.
