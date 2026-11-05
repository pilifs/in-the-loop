# Brief: build.py as a runner of claims, attempts and evidence

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh):
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/build-orchestration.md`, in the session and with
the model set under [Loop settings](#loop-settings). The loop runs until the session judges,
by [Loop until](#loop-until), that the rest is not worth another cycle.

**Session: `cc65240f-1df0-42e0-81ce-41a80fa61028`.** The session that wrote this brief. Later work on
this brief resumes it (`claude --resume cc65240f-1df0-42e0-81ce-41a80fa61028`, or the loop,
which reads it from [Loop settings](#loop-settings)) rather than starting a new one.

[`examples/tools/build.py`](../../examples/tools/build.py) runs every example: it builds the
before and after versions, calls jvmcontract, JBMC or TLC, and writes `result.json` and the
example's page. An outside review of it at `4c279ba6` (2026-11-04),
[`build-orchestration-review.md`](build-orchestration-review.md), found that its reported
results can't always be trusted. A verifier that crashed is counted as a counterexample. A D1
model can check the old contract against new bytecode. Missing coverage is read as no
coverage. Several properties collapse into one statement. The review also proposes an
architecture to fix this: a frozen claim, attempts against it, conclusions, and an evidence
bundle. On top of that it proposes four developer-facing features. **Read the review in full
before the first piece of work of every cycle.** It is the input, and this brief is the plan
for carrying it out.

**This brief is about the right data structures, interfaces and evaluations for deep formal
proof work.** The review's developer features (its section 3, this plan's Phase 4) are
[deferred](#deferred-phase-4-developer-features) by the user's decision and are not to be
worked on. They would add considerations that are useful to developers but not novel, and
make the proof experiments this project exists for harder to run. They will be revisited
later, separately from the proof work. What this brief builds should make them easy to add
then: a JUnit test or a JVM replay should be a new presentation of evidence the format
already holds, not a change to it. Where a step has to choose, it chooses what serves the
proof work.

**Phase 5, the proof experiments, is [deferred](#deferred-phase-5-proof-experiments) too.**
It will probably come before the developer features, but only after the structural work of
Phases 1–3 is done and has been designed and planned further. This loop covers Phases 1–3:
results that can be trusted, models tied to the code they check, and one plan with durable
evidence. That structure should leave room for Phase 5 without building any of it.

## How to work through it

- **One step of [the plan](#the-plan) per cycle**, in order, committed on its own. A step
  that is too big for one cycle is split. Commit the first half with the rest named under
  Progress. Don't skip ahead. Later steps build on the result format the earlier ones settle.
- **Check each claim against the code first.** The review read `4c279ba6`. `build.py`,
  `pipeline.py` and `lib/` have changed since and will keep changing, because other sessions
  work in this repository. A finding that no longer holds goes in the commit message, not
  in the code. Spot checks on 2026-11-05 at `68af56c2` found the cited line numbers in
  `build.py` still exact. The exit-code classification, the missing `--json` on equivalence
  and `prove`, and the "replayed it on the JVM" wording (line 1801) were all still present.
- **Test the runner without running proofs.** Add `examples/tools/test_build.py`, which
  doesn't exist yet. Use `unittest` and mocked `subprocess` results, in the style of
  `verification/test_pipeline.py`. The fixtures the review names come first: a process
  killed by a signal, empty output, malformed JSON, several properties with mixed outcomes,
  missing TLC coverage, stale input fingerprints, an unknown example id and a real-world
  example. Every step adds the fixtures for what it changes. These tests and `cargo test`
  in `lib/` run inline.
- **Proofs and model checks are queued, never run inline** (CLAUDE.md,
  [`verification/README.md`](../../verification/README.md)). When a step changes what
  examples record, run `build.py --render-only` inline to check the pages still render.
  Then submit pipeline jobs for a representative set of the affected examples: one per
  approach (B9 JBMC, B9 native, B11, B12, D1) and every example the step names. The commit
  summary line ends `(verification pending)` and the job ids go in a paragraph. Don't wait
  for the results. Read them with `python3 verification/pipeline.py report` at the start of
  later cycles. A regression they show comes before the next step.
- **Recorded results are evidence, not inputs to edit.** Never change a verdict, statement or
  coverage in a committed `result.json` by hand. A format change keeps old results readable:
  the renderer and schema accept the old shape until the pipeline has re-produced them.
  Results are rewritten only by `build.py` runs, and those run through the pipeline.
- **Nothing gets weaker.** Each step must keep or tighten every check `build.py` makes:
  the expected-verdict match, vacuity, the B12 `!`-line check, existing tests and the
  coverage of changed rows. If an example that passed now fails because the runner
  stopped counting a crash or missing evidence as a result, the fix is working. Record it
  under Progress with what it needs. Don't loosen the check.
- **The pipeline is another agent's.** Changes to
  [`verification/pipeline.py`](../../verification/pipeline.py) keep `test_pipeline.py`
  passing and its job format readable. Jobs already queued must still run. The pipeline
  itself is run by `/run-verification`, not by this loop.
- **Library changes are in scope** where a step needs them, for example a structured
  output for `verify` and `update`, typed witness values or a replay entry point. They go in
  `lib/` with tests. The interpreter and JBMC results committed for existing examples must
  not change.
- **Docs move with the behaviour.** A new result field, option or command is described in
  the same commit in [`examples/README.md`](../../examples/README.md), in
  [`examples/approaches.md`](../../examples/approaches.md), or in the schema's own
  descriptions. What one example teaches goes in that example's `notes`.
- **New examples follow the router** ([`examples/README.md`](../../examples/README.md)): one
  numbered folder each, tagged from `tags.json`. Look for a close existing one with
  `examples/tools/find.py` first.
- **Defer what needs the user, explicitly.** Some things are not done and not guessed at:
  network access to fetch dependencies (Maven Central, Gradle plugins), calls to an LLM API
  or any paid service, a change to what is published, and a decision only the user can make
  (see [Open questions](#open-questions)). Do the parts that don't need it, behind a switch
  that is off where it must be. End the commit message with a **Deferred for the user**
  paragraph: what is needed, why, and what it would unlock. Don't stop the loop over it
  while other work remains.

## Keep the loop running

The loop should run for as many cycles as there is useful work. Only three things stop it:
a cycle that ends without a commit, a decision reply without a clear last line, and an edit
to this brief outside [Progress](#progress). The review file is input too. Leave it as it is.

- **End every cycle with a commit.** If the planned step is blocked, commit the largest part
  that isn't: the tests, the fixtures, the groundwork behind a switch that is off. Record the
  rest under **Deferred for the user**. Never end a cycle with only a question.
- **Don't pause for minor questions.** When the brief and CLAUDE.md leave a choice open, take
  the conservative option, the one that reports less as established. Say in the commit
  message what you chose and why, and go on.
- **A denied command is information, not a stop.** Don't retry it unchanged. Work out what it
  would have done that it shouldn't, change the approach, and carry on.
- **Long commands go in the background**: the full `cargo test`, a `--render-only` over all
  examples, `test_pipeline.py`. Wait for them rather than letting a tool timeout end the turn.
- **Findings in your own log are not a stop.** Build made-up test values at run time so the
  transcript holds none. If one gets in anyway, propose it with
  `sync.py allow propose ID --reason ...` and go on.
- **Check `jj st` at the start of a cycle.** Another session may have left files uncommitted.
  Commit only your own (see the memory on concurrent sessions).
- **Keep [Progress](#progress) current, and leave the rest of the brief alone.** Update
  Progress in the commit that does the work: what changed, which examples' results moved,
  the job ids, and what comes next. An edit anywhere else stops the loop, so corrections to
  the rest go in the commit message.
- **In the decision turn,** end with exactly `LOOP: continue` or `LOOP: stop`, on its own last
  line. When in doubt, continue.

## Progress

Each run counts only its own commits, so work done in earlier runs is listed here.

- Nothing yet. The next step is [1a](#phase-1-results-that-can-be-trusted).

## Open questions

These are the user's to settle. Until they do, the loop takes the default given and says so
in the commit that relies on it.

1. **Result format.** Is the claim/attempt/conclusion/evidence format a new
   `result.schema.json` version that replaces the flat result, or a block added next to it?
   *Default: added next to it.* The flat fields stay and are computed from the new block, so
   every existing page and tool keeps working. Retiring them is the user's decision.

## The plan

The review's own order (its section 5) is kept, with each phase cut into steps of about one
cycle. Each step names its **acceptance criterion**: the step is done when that holds and is
tested. Phases 4 and 5 are deferred ([5](#deferred-phase-5-proof-experiments),
[4](#deferred-phase-4-developer-features)), so the plan ends with Phase 3. The numbers stay
the review's so the two can be read side by side.

### Phase 1: results that can be trusted

- **1a. Execution status, separate from the verdict.** Every place that turns a process into
  a verdict, `tool()` and the `returncode == 0 / "cannot be verified" / else violation`
  pattern at least at build.py:256, 321 and 396, first decides how the execution went:
  `completed`, `timed-out`, `killed`, `invalid-output` or `tool-error`. Only a completed run
  has a verdict (`established`, `refuted` or `unresolved`, or the existing labels mapped
  onto them). The expectation match records `yes`, `no` or `not-evaluable`, and an expected
  violation needs a completed refutation plus its evidence. `write_evidence()` stops making
  an empty SARIF file when the report is missing. Fixtures: signal 9 with empty output, a
  timeout, an exit code nothing knows. *Acceptance: a killed process, malformed output or a
  missing result can never count as an expected violation.*
- **1b. Strict selection.** Unknown example ids exit non-zero. A requested real-world
  example (105–109), or one whose app `app_of()` doesn't know, is recorded as
  `not-executed` with the reason, not skipped silently with exit 0. Check what the pipeline
  expects from a skipped example before changing the exit code.
  *Acceptance: no requested run ends with exit 0 without having run.*
- **1c. Equivalence from `--json`.** `run_tool_equivalence()` reads the library's `Outcome`
  instead of parsing text. That covers the statement, witness, shrinking, vacuity, stage and
  the summary line's numbers. The replay wording on the page comes from recorded replay
  metadata. Today the witness is replayed in jvmcontract's bytecode interpreter, so the page
  says so, not "on the JVM". Submit jobs for a B9 JBMC example, a B9 native one and a vacuous
  one (144). *Acceptance: the B9/B11 results for those examples are unchanged, apart from
  the wording and fields this step adds.*
- **1d. One result per property, from `prove --json`.** Property proofs keep every
  property's outcome, with its assertion, assumptions, harness (`property-N`), witness,
  proof description and vacuity. A headline is computed over them. Any refuted required
  obligation fails the change, unresolved ones stay visible, and the change passes only
  when all are established. Example 071 (three properties, `statement: null` today) is the
  test case. *Acceptance: 071 records three outcomes, and a mixed fixture gives the right
  headline.*

### Phase 2: the model checks what was built

- **2a. Candidate contracts for D1.** `run_tool_tlc()` (build.py:1314) and the Box Office
  `run_tlc()` (443) always connect the operators they check to the patched bytecode. They
  either derive the candidate contract from the patched classes or verify the committed
  contract against them, and record which. `behaviourChangeIntended` then decides only
  whether a difference from the baseline is allowed, not whether the model is regenerated.
  Unauthorized differences are reported. No checked-in example shows the gap (the review
  says so). Add a fixture that does, and if it's cheap, a D1 example where an unintended
  kernel change passes today's runner. Submit jobs for one D1 example per model (2PC, Raft
  election, Raft replication, circuit breaker).
  *Acceptance: every generated operator has a recorded connection to candidate bytecode.*
- **2b. Coverage that knows what it doesn't know, and checkpoints.** `tlc_coverage()`
  records `coverageStatus: complete | partial | unavailable`, and only `complete` coverage
  can make a verdict vacuous. Each configuration keeps its termination reason, and
  `coverage_lines()` stops saying "stopped at the counterexample" for an unfinished run.
  Each configuration's result is written as soon as it completes and is reused only when
  its full input fingerprint matches (review section 4). *Acceptance: missing coverage stays
  unknown, and an error in a later configuration keeps the earlier ones.*

### Phase 3: one plan, durable evidence

- **3a. A pure planning function.** `plan(example)` resolves, without side effects, the
  app/build adapter, targets and claims, required and optional tools, engine and effective
  options, model configurations, and expected outputs. Scratch directories move into an
  execution context. `build.py` executes plans, and `pipeline.py`'s `example_job_parts()`
  takes its tool and resource needs from the same plan. That fixes native-engine jobs that
  ask for JBMC, and Box Office (B12) jobs that leave out jvmcontract and its build memory.
  *Acceptance: the pipeline's requirements match the selected backend, and test_pipeline
  covers both cases.*
- **3b. Claim, attempt, conclusion, evidence bundle.** The format in the review's section 2,
  under [open question 1](#open-questions). The claim is frozen before execution, with input
  fingerprints (before/after bytecode, dependencies, models, effective settings) and the
  pipeline's `VERIFY_JOB_ID`, `VERIFY_SOURCE_COMMIT` and `VERIFY_WORKDIR`. Each attempt is
  written to its own directory. The whole result and its artifact manifest are validated
  before anything is written, and a missing `jsonschema` is an error, not a silent skip.
  The bundle is published at once. Changing the timeout, solver or engine is a new attempt.
  Changing the inputs, the array bound or the assumptions is a new claim with its own id.
  An unwind limit records whether the backend showed the exploration complete. A witness is
  kept with typed values (a library change: `Counterexample` values are strings today),
  target descriptors, argument mappings and artifact identities, enough to rebuild the call
  without the text. That is what would later make a JVM replay or a JUnit test a mere
  rendering.
  *Acceptance: a report names its exact inputs and can't mix attempts from different runs.*
- **3c. Render from the saved snapshot.** `--render-only` renders from the bundle and shows
  whether it still matches the current inputs. "Why the verdict is right" separates the
  author's expected explanation from the observed evidence. *Acceptance: a stale fixture is
  shown as stale, and a result that disagrees with its expectation doesn't print the
  expectation as the reason.*
- **3d. Stage logs, kept workspaces, split compilation.** One command wrapper writes each
  stage's stdout and stderr to files and prints short progress lines, so the pipeline can
  stream them. Attempt directories go under `VERIFY_WORKDIR` when it's set, and keep the
  harness, inputs, tool output and partial logs. Production and test compilation are split,
  so `tool_before_classes()` doesn't compile tests. Measure first, then decide on a
  content-addressed baseline build cache across jobs. Add it only if the timings show it
  matters, and never reuse a proof on unchanged method text alone.
  *Acceptance: an interrupted job leaves its stage logs and workspace behind.*

## Done when

The review's acceptance criteria hold for Phases 1–3 (4 and 5 are deferred):

| Phase | Criterion |
|---|---|
| 1 | A killed process, malformed output or a missing result can never count as an expected semantic violation, and every property keeps its own evidence |
| 2 | Every generated operator has a recorded connection to candidate bytecode, and missing coverage stays unknown |
| 3 | Pipeline requirements match the selected backend, and reports name exact inputs and can't silently mix attempts |

The pipeline jobs submitted along the way are back with their expected verdicts, or their
failures are explained under Progress.

## Deferred: Phase 5, proof experiments

**Not to be worked on in this loop**, by the user's decision (2026-11-05). It is likely the
next thing after this brief, ahead of the developer features, but it gets its own design and
planning first, informed by what Phases 1–3 settle. It is kept here as context, so Phases 1–3
leave room for it: a claim with a stable id, attempts with their effective settings, a claim
narrowed into a new one rather than replaced, and execution status and failure reasons as
data, not text. A cycle that finds itself building toward profiles, diagnosis or resumption
stops at that structure and notes the rest in its commit message. Step 2b's per-configuration
checkpoints are a correctness fix for TLC runs and stay in scope.

- **5a. Experiment profiles.** Named profiles over the library options the runner doesn't
  expose yet: engine, timeouts, SAT solver, string refinement, shared callees. Every attempt
  saves its effective settings and links to its fixed claim. A profile can't change a claim.
  *Acceptance: several profiles against one claim give several attempts under one claim id.*
- **5b. Diagnosis, resumption and the agent loop.** Each unfinished attempt gets a
  structured diagnosis from the outcomes: counterexample, unsupported operation, resource
  limit, incomplete exploration, vacuous claim, or other. The runner proposes next attempts
  from the review's table. A narrower claim is a separate proposal with its own id, never a
  silent replacement. Completed obligations are reused by fingerprint. Progress is reported
  per fixed claim: time, compute, interventions, reasons for failure. The model-driven part is
  open then: whether the runner diagnoses and offers next attempts for an agent session to
  pick among (the earlier default), or does more. *Acceptance: a resumed experiment continues
  from completed evidence, and the claim's report keeps the narrowed claims separate.*

## Deferred: Phase 4, developer features

**Not to be worked on in this loop**, by the user's decision (2026-11-05). These are the
review's section 3 features. They are kept here as context, so the format of Phases 1–3
leaves room for them, and so the next brief can start from them. A cycle that finds itself
needing one of them stops at the data structure or interface the feature would use, and
notes the rest in its commit message. Step 1c's correction of the page wording about where a
witness was replayed is a correctness fix, not this feature, and stays in scope.

- **4a. "Check this bug fix."** One change review combines obligations. *Preserve*: outside
  the declared boundary, old and new agree (B9 with `--unchanged-unless`). *Establish*:
  inside it, the new behaviour is the intended one (a B11 property, or an explicit
  expected-result relation). *Policies*: the boundary or contract checks that apply keep
  holding (B12 `!` lines, contract rows). The allowed change is declared on its own in the
  example, not inferred from `behaviourChangeIntended`. The runner prints a reviewable plan
  of the obligations before it runs them, and a report after: what was meant to change,
  what must stay the same, what was established, and what gaps remain. Add an example
  pair, such as the review's "an exact expiry deadline counts as expired" on Crosscut's
  expiry kernel (see 122/123), one where the fix holds and one where it leaks past its
  boundary. *Acceptance: one run reports preservation, the intended behaviour and policies
  as separate obligations, with one headline.*
- **4b. Replay on the JVM, and a JUnit test.** Keep the witness arguments with their types
  (a library change: `Counterexample` values are strings today), target descriptors,
  argument mappings and artifact identities. Run the old and new versions in separate JVM
  processes, record returns, exceptions and supported mutations, and evaluate the claim's
  own relation. Write a JUnit regression test and a reproduction command into the bundle
  (open then: commit it next to the example, or keep it in the bundle only?). Start with primitives, strings and arrays. A JVM
  replay is a quick check, not a proof, and can run inline in tests. *Acceptance: a B9
  violation's witness is reproduced on the JVM and exported as a test that fails on the
  after-version.*
- **4c. External artifacts as inputs.** An adapter takes two class/JAR sets and explicit
  targets from a manifest. It produces classpaths, target methods with their source
  locations, and claims, without a branch in `build.py` for each app. The four bundled apps
  move onto it. A real-world example (105–109) becomes runnable where its built artifacts
  are on disk (open then: whether dependencies may be downloaded). *Acceptance: a before/after pair of JARs
  gives preservation and intended-behaviour results and reproducible findings.*

## Loop settings

The session is fixed: further work on this brief resumes it.

- session: cc65240f-1df0-42e0-81ce-41a80fa61028
- model: claude-opus-5-5
- effort: high

## Loop until

Go on while a cycle can still realize a substantial part of the reasonably attainable value of
this brief. The user prefers the loop to run as long as possible, so when in doubt, continue.
Phases 1 and 2 fix results that can be wrong today, so don't stop before they are done unless
they are blocked on the user. The plan ends with Phase 3, so the deferred phases are never a
reason to go on. Stop when most of the rest has been realized: the remaining
steps are small or speculative next to what is done, or what is left needs the user's input
(an open question, network access, an external service) and has been recorded as deferred.
Don't go on to polish, and don't stop while a step of the plan that needs nothing from the
user is still open.
