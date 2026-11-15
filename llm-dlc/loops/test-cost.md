# Brief: test cost: cheap by default, expensive once

**Status of the brief**: drafted 2026-11-15 from the user's request and a measurement of the loops' time; the
[decisions](#decisions) settled by the user the same day. **Revised the same day** after the user stopped the first run
as it began a measuring job: nothing is re-run to measure. Tiers come from past runs and from what a test spawns, and
the loop is cut to the tags, the lint and the guidance, so the stream conductor can follow soon. The proxies, the
retiering of the slow files and the reuse of passed results are [deferred](#deferred-not-in-this-loop).

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), run alone in the default workspace after example-targets
(done 2026-11-15) and before the stream conductor's steps 4–6:
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/test-cost.md`.

Every test gets a cost tier, the tests run by default are cheap, and an expensive test runs as a queued job, once for the
inputs it checks. Agents are steered away from running expensive tests and from writing them where a cheaper test shows
the same thing. Where an expensive test is needed, a cheap proxy beside it gives an indicative result while iterating.
This loop lays the ground for that: every test tagged with its tier, a lint that keeps the tags honest, and the
guidance. Making the default run cheap, by moving the slow files' JBMC tests to the proof tier behind proxies, is the
next loop's.

**Inputs.** Read these in full before the first piece of work of every cycle:
- [Where it starts from](#where-it-starts-from), below: the measurement this brief rests on.
- [`lib/README.md`'s Tests section](../../lib/README.md#tests): what the Rust tests need and what is already ignored.
- [`verification/README.md`](../../verification/README.md): what is queued and how, and its table of estimates.
- [`brief-template.md`](brief-template.md#standing-rules): the standing rule on what runs inline, which this brief
  changes.

## Direction

- **Every test declares its cost.** Three tiers, by what a test runs and what it costs on this machine (thresholds in
  [decision 1](#decisions)). In this loop the cost comes from past runs and from what the test spawns, never from a new
  measuring run ([decision 9](#decisions)):
  - **unit**: in process, with no subprocess and nothing outside the repo. The default for a new test.
  - **tool**: spawns `javac`, `java`, the `jvmcontract` binary or a stand-in script; seconds. Runs inline.
  - **proof**: spawns JBMC, TLC or a solver on more than a toy, or goes over the tool tier's time or memory. Never runs
    in a plain `cargo test` or a Python test run. It runs as a pipeline job, with one narrow inline exception
    ([decision 4](#decisions)).

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

  A test that spawns JBMC or TLC without a proof tag is caught by a lint in the default run. (A test over its tier's
  threshold is caught once the measuring tool of step 2 runs, in a later loop.)
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
- **The suites:** 25 test files in `lib/tests/` with 384 `#[test]`s, and 258 unit tests in `lib/src/`. Python has 28
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
- **No measuring runs** ([decision 9](#decisions)). Don't run the whole suite, the ignored tests, the proof tier or the
  measuring tool to find out what a test costs, inline or as a job. Take its cost from what already exists:
  - the timings in past sessions' redacted logs (`tool_time.py` reads them: "test result … finished in Xs" per binary);
  - past pipeline results in `verification/results/` (step durations and their `cargo test` logs; heap's ignored tests
    took 2 to 25 minutes each there, and conformance's about 23);
  - what the test calls: the JBMC or TLC helpers make it proof tier, `javac`, `java`, the binary or a stand-in script
    tool tier, nothing outside the process unit tier.

  Where these disagree or say nothing, estimate, and say so in the inventory. Inline, run only the tests you changed,
  and the default run once before committing, as now.
- **Nothing runs less than it does today.** This loop doesn't add `#[ignore]` to a test that runs by default now, or skip
  one in a default Python run. A test the inventory puts in the proof tier that runs by default today stays as it is,
  and is listed for retiering in the next loop (step 3). So no change of this loop needs a job.
- **One mechanism, or a group of test files, per cycle.** Tagging a file means adding the tier helper to its tool-tier
  tests and rewriting its `#[ignore]` reasons, in one commit with the inventory regenerated.
- **Verification mode: none needed.** This loop queues no jobs. If a piece of work turns out to need one, record it as
  deferred, with why, and go on.

## The plan

### Phase 1: the tools and the inventory

1. **The time analysis as a tool:** `llm-dlc/tools/tool_time.py`. Done (`spvkptmn`).
2. **The measuring tool, written but not run:** the stopped run left `lib/tools/test_costs.py`,
   `lib/tools/install-nextest.sh` (cargo-nextest 0.9.151 is installed) and `lib/.config/nextest.toml` uncommitted in the
   working copy. Finish them as a tool a later loop queues as a job:
   - its `measure` is never run in this loop. Test its parsing (JUnit, the process samples, the inventory it writes) on
     made-up inputs, at the unit tier, and its process watching on a made-up command of a second or less.
   - nothing points outside the repo: the nextest wrapper runs the tool's `watch` from `lib/tools/`, not a script under
     `/tmp`. A profile that is only for measuring stays out of the default run.
   - `lib/README.md` says how to queue it later, with the estimate from past jobs (about 3 hours).
3. **The inventory, from past runs and estimates:** `lib/tests/costs.json`, and the same for Python, generated by a
   command (an `estimate` subcommand of `test_costs.py`, say) from the sources in
   [How to work through it](#how-to-work-through-it), never by hand. Each test gets:
   - its tier;
   - its cost, with its source: a past job's id, a session's log (by sha256, per binary where per-test isn't known), or
     `estimated` with the reason;
   - for a test whose tier is proof but runs by default today, `retier: pending`. That list is the next loop's work.

   A later `measure` run replaces the estimates in the same file.

### Phase 2: the tags and the lint

4. **Rust tiers** ([decision 2](#decisions)):
   - The proof tier is `#[ignore = "cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST"]`. The twelve existing ignore reasons
     are rewritten to that form. One with no proxy yet says `proxy: none yet`, and is listed in the inventory.
   - The tool tier is skipped under `JVMCONTRACT_TEST_TIER=unit`, through a helper each tool-tier test calls first. The
     tests with `retier: pending` call it too, so the unit-only run is quick. Without the variable, nothing changes.
5. **Python tiers** ([decision 7](#decisions)): one `@cost("tool" | "proof")` decorator in a shared helper, with the tool
   tier skipped under `TEST_COST=unit`. Every Python test the inventory puts above the unit tier is tagged. A Python
   test that would be proof tier but runs by default today is tagged `pending` and still runs by default.
6. **One way to run each tier**, documented in `lib/README.md`: the default run, the unit-only run, and the proof tier
   as a job (the `pipeline.py submit` command for it, written down, not run).
7. **The lint, in the default run:** a unit-tier test, like `tests/skill.rs`, checks:
   - every `#[ignore]` reason starts with `cost:`;
   - every proof-tier tag names a proxy that exists, or says `proxy: none yet` for a test the inventory lists;
   - no test outside the proof tier calls the JBMC or TLC helpers directly, except the inventory's `retier: pending`
     tests;
   - every test the inventory names exists, and every test is in it.

   Python gets the same checks.

### Phase 3: guidance

8. **The guidance**:
   - **CLAUDE.md** gets a short Tests section: the tiers; that the default run is what you run inline; the proof tier
     as a job, with [decision 4](#decisions)'s one inline exception, stated as narrowly; write the cheapest test that
     shows the behaviour, and give a new proof-tier test a tag, a reason and a proxy. Adding a test to the
     `retier: pending` or `proxy: none yet` lists is for a person to decide.
   - **`brief-template.md`'s standing rule** names the tiers instead of "conformance cases on a real `java`".
   - **`verification/README.md`**: "the slow tests" become the proof tier, and the `retier: pending` tests until they
     move.
   - **`lib/README.md`'s Tests section.**
9. **For-review list** in Progress:
   - the tests whose tier is an estimate with no past timing behind it;
   - the size of the `retier: pending` and `proxy: none yet` lists, by file;
   - anything the tagging found that the next loop should know.

## Done when

| Phase | Criterion |
|---|---|
| 1 | `tool_time.py` is committed. `test_costs.py` and the installer are committed, tested on made-up inputs, and never run to measure. Every Rust and Python test has a tier in the generated inventory, with the source of its cost. |
| 2 | Every ignored test carries a `cost:` tag. Every tool-tier and `retier: pending` test calls the tier helper. The lint is in the default run and passes. Each tier has one documented way to run. No test runs less by default than before. |
| 3 | CLAUDE.md, the brief template, the verification README and `lib/README.md` describe the tiers. The for-review list is in Progress. |

## Deferred: not in this loop

- **To the next test-cost loop**, by the user's decision on 2026-11-15 ([decision 9](#decisions)), after the stream
  conductor:
  - running the measuring tool as a job, replacing the estimates;
  - the proxies: the record and replay stand-in for JBMC and TLC;
  - retiering the `retier: pending` tests, starting with the five slow files, each with its proof tier queued, and
    the default `cargo test` (debug, warm) within 60 seconds;
  - reusing a passed result while its inputs are unchanged, and the JBMC answer cache ([decision 5](#decisions));
  - the integration scripts running the default tier and queuing the proof tier;
  - a measured comparison with [Where it starts from](#where-it-starts-from), using `tool_time.py`.
- **Making JBMC, TLC or the native engine faster:** the engines' own loops do that.
- **Changing what a test checks:** tests are tagged and moved, not redesigned.
- **CI outside this machine.**
- **`examples/tools/build.py` runs:** already queued.

## Decisions

Settled by the user on 2026-11-15:

1. **Tiers and thresholds:**
   - **unit**: no subprocess, under 1s.
   - **tool**: under 10s and 1 GB.
   - **proof**: JBMC, TLC, or over the tool tier's limits.

   Benchmarks stay queued as they are.
2. **The Rust mechanism:**
   - The proof tier is `#[ignore = "cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST"]`. It works with plain `cargo test`
     and with nextest, and needs no feature flags.
   - The tool tier is skipped under `JVMCONTRACT_TEST_TIER=unit`, through a helper the test calls first.

   Not Cargo features, which recompile per tier, and not one file per tier.
3. **cargo-nextest is installed** from its prebuilt release binary on github.com (an allowed host), hash-pinned.
4. **Where the proof tier runs:**
   - As pipeline jobs, once per finished change, for the tests whose inputs it touched.
   - **One inline exception**: an agent may run a single proof-tier test inline, once, when its change targets that test
     directly and the inventory measures it under a minute.
   - Anything else proof-tier is queued. CLAUDE.md's rule on queuing proofs gets this exception, stated as narrowly.
5. **The JBMC answer cache is allowed, and labelled.**
   - Exact keys only, and every reused answer names its source run.
   - Proxies and tool-tier runs may reuse any hit. A job that claims a verdict reuses only a hit from a pipeline result
     with the identical key, and says so; otherwise it runs JBMC fresh.
6. **Proxies:**
   - Required for every new proof-tier test.
   - Existing proof-tier tests get one in Phase 4 if they are in the five slow files (`conformance.rs`,
     `observations.rs`, `integration.rs`, `alignment.rs`, `application_core.rs`). The others are listed for later.
7. **Python: tagged now, Rust first.**
   - The same tiers and decorator, with the lint covering Python.
   - Proxies and retiering go to Rust. A Python file gets one only where the measurement shows it is worth it.
   - The case for including Python: its tests took 3.3h in the measurement, 1.1h direct and 2.2h inside example-targets'
     integration checks, which run nothing else. That is about 27% of that loop's active time.
8. **Launch:**
   - Alone, in the default workspace, after example-targets is done.
   - Model `claude-opus-5-5` at high effort, 12G.
   - Not beside conductor steps 4–6, which also edit the brief template and the integration check `run-streams.sh`
     runs; one after the other, in either order.
   - The user chose this loop first (2026-11-15). The conductor's steps 1–3 stay unmerged in the jj workspace
     `stream-conductor` (`../in-the-loop-stream-conductor`): not this loop's to merge, edit or rebase.
9. **No measuring run, and a shorter loop** (the user, 2026-11-15, after stopping the first run as it began the
   measuring job, estimated at about 3 hours of jobs):
   - Tiers come from past runs and from what a test spawns, never from re-running tests or jobs. The measuring tool is
     written, and run in a later loop.
   - This loop does the tags, the lint and the guidance. The proxies, the retiering and the reuse of results
     (Phases 3 and 4 of the first draft) go to the next test-cost loop, after the stream conductor. Decision 5, and
     decision 6's part on existing tests, apply there.

## Progress

- 2026-11-15, drafted from the user's request ("we should not be running expensive tests where we can avoid it, and
  frankly probably not more than once in many cases … they should also be discouraged from writing expensive tests when
  unnecessary, or at minimum, provide the option to run proxy tests that are much cheaper") and the measurement above.
- 2026-11-15, the user settled the eight decisions: as proposed, except decision 4, which allows one narrow inline
  exception. For decision 7, the user asked first for the case for including Python.
- 2026-11-15, example-targets done and pushed. The user chose to run this loop before the conductor's steps 4–6. The
  brief moved from the side workspace `test-cost-plan` onto main, and its count of Python test files was brought up to
  date (28). Next: Phase 1 step 1, `tool_time.py`.
- 2026-11-15, Phase 1 step 1 done: `llm-dlc/tools/tool_time.py` (tested by `test_tool_time.py`, unit tier, on made-up
  logs). It finds loop sessions from the briefs' `- session:` lines and the loop summaries, reads their redacted logs
  (`--fetch` downloads published ones not stored here, checked against their sha256, into `~/.cache/llm-traces/logs`),
  and reports blocked time by category, by loop, and by cargo test binary, with full-suite, debug and release spreads.
  The measurement's set is `--fetch --exclude sync-performance --exclude test-cost --session
  360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb=early-feature-loop` (26 sessions found, not 27). It reproduces the
  measurement's compile/test split exactly (936 timed runs, compiling 0.9h, tests 8.2h) and the slow files' ranking,
  but its stated definitions give other totals: active 116h, tools 47.8h, cargo test 20.8h plus 3.6h waiting on it in
  the background, proofs inline 4.7h. Its full-suite debug runs (no target, filter or `--ignored`) are 91 calls, 14% of
  cargo test time, median 11s, p90 579s; all debug runs are 788 calls, 44%, median 8s, p90 82s. The brief's "542 runs,
  48%, median 17s, p90 136s" came from scripts not kept and isn't reproduced; Phase 5 compares against this tool's
  numbers. Next: Phase 1 step 2, install cargo-nextest and queue the per-test cost job.
- 2026-11-15, the user stopped the run in cycle 2, as it was about to queue the measuring job, and revised the brief
  ([decision 9](#decisions)): no measuring run, with tiers taken from past runs and estimates, and the loop cut to the
  tags, the lint and the guidance. Cycle 2 had installed cargo-nextest 0.9.151 and left `lib/tools/test_costs.py`,
  `lib/tools/install-nextest.sh` and `lib/.config/nextest.toml` uncommitted. Next: Phase 1 step 2 as revised, finishing
  those files without running `measure`.
- Status: working

## Loop settings

- session: 72d38e75-aae0-402e-9b8a-881beec53824
- model: claude-opus-5-5
- effort: high
- memory: 12G

## Loop until

Phases 1 to 3, in order. Keep the last line of Progress a status: `working`, `done`, or `blocked: ...` with what needs
the user. Stop with `done` once every criterion of [Done when](#done-when) holds, or with the remaining items recorded
as deferrals with their reasons. Never run the measuring tool, the whole suite with its ignored tests, or a job to
find out what a test costs: if a tier can't be estimated, say so in the inventory and go on. Items deferred by the
timebox count as recorded deferrals, never as a reason to keep going.

