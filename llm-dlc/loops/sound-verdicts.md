# Brief: a verdict stays inside the Java the engines implement, and says what it assumed

**Approved by the user on 2026-11-05**, with the open questions settled as recorded [below](#open-questions). It runs
before the proof experiments `build-orchestration.md` defers. The JBMC patch queue that an earlier draft planned as its
last phase is a separate working draft, [`jbmc-patch-queue.md`](jbmc-patch-queue.md), which is not part of this loop.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh):
`llm-dlc/tools/feature-loop.sh llm-dlc/loops/sound-verdicts.md`, in the session and with the model set under
[Loop settings](#loop-settings). The loop runs until the session judges, by [Loop until](#loop-until), that the rest is
not worth another cycle.

**Session: `7cacdb56-4c74-4880-a06e-f98031283c0f`.** The session that wrote this brief. Later work on this brief resumes
it rather than starting a new one.

Two outside reviews read the repository at git commit `c4fa2f64` (2026-11-05):

- [`sound-verdicts-review-ecosystem.md`](sound-verdicts-review-ecosystem.md) compares jvmcontract with JBMC, KeY,
  OpenJML, JPF, SAW, ByteBack, VeriFast, Dafny and proof checkers. Its strengths are bytecode-level, bit-accurate
  regression verification and readable witnesses. Its main finding: **some Java behaviour the native engine doesn't
  implement is approximated rather than refused, so a false claim can come back `Verified`**. It names two
  reproducers, `new ArrayList<>(n)` with a negative `n`, and `synchronized (null)`.
- [`sound-verdicts-review-jbmc.md`](sound-verdicts-review-jbmc.md) looks at where investing in CBMC/JBMC would pay. It
  finds the shared CBMC engine is maintained, but Java-specific development is thin and the models are old. Its first
  priority is the same as the other review's: strict acceptance of Java semantics, then control over models and
  intrinsics. After that it lists encoding patches (one quotient/remainder pair, plain modular multiplication), array
  and path-reuse work, and adapter fixes that need no fork.

**Read both reviews in full before the first piece of work of every cycle.** They are the input, and this brief is the
plan for carrying them out.

Checked at HEAD (2026-11-05, 13 commits after `c4fa2f64`), so these are not hypotheses:
- In `lib/src/bmc/mod.rs` (around line 1568), an unresolved JDK constructor is skipped, a `void` JDK instance method
  does nothing, and a reference-returning one returns a fresh opaque object.
- `MonitorEnter` and `MonitorExit` pop their operand with no null check (around line 1625).
- Fields are keyed by name alone (`GetField`, around line 1513).
- Every equivalence and property run walks all three interval stages (`STAGES` in `equivalence.rs`).
- The JBMC adapter parses text, not `--json-ui`.

## The idea: gaps are named, and nothing is assumed silently

Implementing these semantics faithfully costs almost nothing at run time:
- Refusing an unmodelled call ends the path early.
- A monitor null check is one branch.
- Field resolution and literal identity are settled when the bytecode is decoded.
- An initializer is refused or assumed, never run.

What it costs is **coverage**: strictness refuses programs that are accepted today. The one expensive check is having
JBMC re-prove a native `Verified`, which takes 10-100x longer on the recorded examples. So the choice is not between
cheap and thorough. It is between three honest answers to a **gap**: a call or construct the engine doesn't implement
faithfully, each with a stable id.

| Mode | A gap is | The verdict reads |
|---|---|---|
| **strict** | refused by name | `Unverifiable: gap G (ArrayList.<init>(int))`, or an unconditional `Verified` |
| **assume** | today's approximation, recorded as a named assumption | `Verified, assuming 2 behaviours` |
| **advised** | sent to the agent driving the tool, which proposes a contract for it. The tool checks each contract: proved against the JDK's bytecode, tested against a real JVM, or else trusted | `Verified; 1 contract proved, 1 tested on 400 inputs, 0 trusted` |

Today's behaviour, an approximation hidden inside `Verified`, does not survive in any mode.

**The advised mode is the differentiating feature.** The library is not a checker written for people typing specs.
It hands an agent exactly the gaps it can't close, then checks what the agent proposes as hard as it can. The LLM is
whichever agent drives the tool, never an API the library calls, so the library holds no keys and incurs no costs.
Strict is the advised mode given no contracts.

The order: **gaps named and refused (Phase 1), results that state their assumptions as data (Phase 2), the advised mode
on top of both (Phase 3)**, then the JBMC adapter (Phase 4) and measurement (Phase 5). Patching JBMC itself is left to
[`jbmc-patch-queue.md`](jbmc-patch-queue.md), which Phase 5's measurements inform. Nothing here makes a verdict weaker.
A `Verified` that strict refuses is the fix working. Where that would move a recorded example, 1a's scan records it for
the user's decision ([open question 3](#open-questions)).

## How to work through it

The working rules of [`build-orchestration.md`](build-orchestration.md#how-to-work-through-it) apply here too: one step
per cycle, committed on its own; check each claim against the code first; proofs and model checks are queued, never run
inline; recorded results are evidence, not inputs to edit; nothing gets weaker; docs move with the behaviour; defer
what needs the user, explicitly. In addition:

- **A semantic reference outside the tool.** The interpreter and the engines share models, so their agreement proves
  nothing about the JVM. Every conformance case, and every contract test in Phase 3, runs on a real JVM (`java`, inline:
  these are milliseconds). A disagreement with the JVM is a bug in jvmcontract, whichever side of it the tool's verdict
  falls on.
- **A reproducer before a fix.** Each semantic gap gets a failing test (a false `Verified`, or a witness the JVM
  doesn't reproduce) in the commit that closes it. If source reading says a gap exists but the test can't show it,
  record that under Progress rather than fixing blind.
- **Refuse first, model second.** A construct the engine doesn't implement faithfully becomes a named gap. Modelling it
  properly, by hand in `lib/models` or by a Phase 3 contract, is a later, separate step, and only where an example needs
  it.
- **The recorded examples are not moved to strict yet** ([open question 3](#open-questions)). Strict is the library's
  default, but `build.py` runs an example in the mode its `approach.gaps` names. Until the user decides how the existing
  examples move, a recorded example without one runs in `assume`, so a rerun records its assumptions rather than
  changing its verdict. Don't re-run examples only to move them, and don't change an `expected` verdict for
  strictness. 1a's scan records what each example would hit. New examples (the conformance corpus, Phase 3's) name
  their mode.
- **No LLM call from the library or the loop's tooling.** In Phase 3 the advising agent is whoever drives the tool. The
  loop's tests use fixed contract files. A contract the loop's own session writes for an example is committed like any
  other authored file, and marked as written by an agent.
- **Tools and versions are part of the evidence.** Any JBMC or solver behaviour this brief relies on is recorded with
  the exact version (JBMC 6.11.0 today, CaDiCaL as JBMC bundles it).

## The plan

### Phase 1: gaps are named, and strict is the default

- **1a. Measure the coverage first.** A static scan of each recorded example's reachable bytecode (no proof, no solver)
  lists the gaps it would hit: unmodelled JDK constructors and methods, monitors, hidden fields, literal identity, and
  static initializers. Use the reach graph or the decoder the engine already has. It is recorded in the example's
  `notes` and summed in the commit message, so the coverage strictness costs is known before it lands, and the user can
  decide from it how the recorded examples move.

  *Acceptance: a gap count per recorded example, with each gap's call named.*
- **1b. The gap as data, and strict and assume modes.**
  - Every instruction and call path of `lib/src/bmc` is implemented, modelled (by a named model with a written
    contract), or a gap. The table lives in the engine's module docs and is tested.
  - A gap has a stable id from what it is: kind, owner, name, descriptor, and the JDK's version for a JDK call. It
    carries the claim context an agent would need.
  - `--gaps strict` (the default) refuses the first gap a path reaches, and reports every gap the run met.
    `--gaps assume` keeps today's approximation for each gap and records it as an assumption in the outcome.
  - `build.py` passes `--gaps` from `approach.gaps` (schema and docs with it), defaulting to `assume` for a recorded
    example, as above.
  - The opaque-JDK-call fallbacks become gaps. The only exception is an explicit allow-list of calls whose effect the
    engine reproduces exactly: `Object.<init>`, and calls already covered by `lib/models`.
  - `MonitorEnter` and `MonitorExit` null-check (NPE), then do nothing in a single-threaded run, which the table says is
    all they mean there.

  *Acceptance: both review reproducers, and a `void` JDK mutator on an argument array, give a named gap (or a correct
  violation) under strict, never `Verified`, on both the native engine and `--engine auto`. Under assume they give
  `Verified, assuming ...` naming the gap.*
- **1c. Identity and initialization.**
  - Fields are resolved by JVMS field lookup (declaring class and name), so field hiding is two fields.
  - A string or class literal has the identity the JVM gives it (one object per distinct literal), or reference
    comparison on it is a gap.
  - A method that reaches a class whose `<clinit>` the engine doesn't run hits a gap, whose assume form is "already
    initialized".

  *Acceptance: a field-hiding case, a literal-identity case and a throwing `<clinit>` case agree with the JVM.*
- **1d. A conformance corpus.** Small programs, each with a claim and the JVM's actual behaviour, run through the JVM,
  the interpreter, the native engine and JBMC. They start with 1b's and 1c's reproducers, then cover exceptions,
  aliasing, null array parameters, record constructors, and arithmetic edge cases (`MIN_VALUE / -1`, negative `%`,
  shifts by out-of-range counts). The cheap ones are integration tests. The ones that need JBMC are examples under a
  new defect tag (proposed: `false-success`), run through the pipeline.

  *Acceptance: under strict, no engine gives `Verified` for a claim the JVM refutes, on any corpus case.*
- **1e. A confirming mode for `--engine auto`** (see [open question 2](#open-questions)). Today it falls back to JBMC
  only on `Unverifiable`. With `--confirm`, a native `Verified` is checked by JBMC wherever JBMC supports the harness,
  and disagreement is reported as its own outcome, never as either verdict. This is the one expensive check, so it is
  opt-in.

### Phase 2: the result says exactly what was established

- **2a. The statement as data.** `Outcome` gains a structured account of ∀x ∈ D, A(x) ⇒ Obs(old, x) = Obs(new, x)
  (properties likewise):
  - the input domain D, with nullability and aliasing (fresh non-null arrays, the array bound, records built through
    their constructors);
  - the assumptions A: the scope and intended inputs, initialization, and **each gap assumed or contract relied on, with
    its evidence level**;
  - the observations Obs (result, exception category, which arrays are compared afterwards);
  - the unwinding and completeness, the model bundle's digest, and the solver (name, version, fallback taken);
  - the gap mode, and whether the result was confirmed.

  `build.py` records it in result format 2's evidence. The page states it in one paragraph.

  *Acceptance: two results that differ only in domain, observations, assumptions or model bundle read differently, and
  the page says how.*
- **2b. Vacuity as a status.** The result says one of: non-vacuity established, vacuous, or unknown. How a vacuous
  `Verified` exits is [open question 1](#open-questions). The record-constructor caveat, that equivalence holds on the
  common constructible domain while constructor compatibility is a separate obligation, is stated wherever it applies.

### Phase 3: the advised mode, where the agent closes the gaps the tool can't

This needs Phase 1's gaps and Phase 2's assumptions as data. It is the brief's new capability, so each step ends with a
recorded example.

- **3a. The gap protocol.** With `--gaps advised`, a run that meets gaps it has no accepted contract for stops before
  solving. It returns them as structured data (`--json`): each gap's id, the call and its descriptor, the claim's
  context, what a contract for it must state (result, exceptions, effects on the receiver and arguments, purity), and
  a contract template. The agent writes the contracts and runs again. Nothing waits on a person.
- **3b. A contract format.** It states, for one call:
  - preconditions;
  - the result, as an expression over the arguments;
  - the exceptions, and the arguments under which each is thrown;
  - the effects on the receiver and on argument arrays, or none.

  Reuse what exists where it fits: the property syntax of `prove` (JML-style `\result`, `\old`, throws clauses), the
  `.contract` files and `lib/models`, rather than inventing a new language. The native engine applies a contract at the
  call in place of the gap. A contract outside what the engine can apply is itself refused, with the reason.
- **3c. Checking a contract, strongest first.** Each contract gets an evidence level, recorded with it:
  - **proved:** checked against the JDK's own bytecode, by `prove` on the extracted JDK class, where the method is in
    the engine's fragment;
  - **tested:** run on a real JVM against the contract on the boundary values of its argument types and on random
    inputs (seeded and recorded), with the number of inputs and every counterexample kept. A contract the JVM refutes
    is rejected, and its counterexample goes back to the agent;
  - **trusted:** neither applies; it is recorded and named.

  The verdict counts the contracts at each level. *Acceptance: the agent-written contract "`new ArrayList<>(n)` doesn't
  throw" is rejected by the JVM test at `n = -1`. The corrected one ("throws `IllegalArgumentException` when
  `n < 0`") is tested, and the review's reproducer then gets its correct verdict.*
- **3d. Contracts are kept and reused.** An accepted contract is stored under the id of its gap, which names the JDK
  version and descriptor. It is committed in a contract library (proposed: `lib/models/contracts/`), and checked once
  rather than on every run; a JDK upgrade re-checks it. A policy option (`--max-trust`) makes a run with more trusted
  contracts than allowed fail, so CI can require zero.
- **3e. The agent's side.** The `verify-bytecode` skill in `plugins/jvmcontract` learns the loop: run, read the gaps,
  write contracts, run again, and report the evidence levels. The skill is the user-facing way in, so this step stays
  small. *Acceptance: an example (a new technique tag, proposed `advised-contracts`) whose proof closes only through
  agent-written contracts, one proved and one tested, with the page showing both levels.*

### Phase 4: the JBMC adapter, without a fork

- **4a. Stages only where they can change the domain.** `--java-assume-inputs-interval` doesn't constrain array
  contents, so a harness whose inputs are all arrays (or already fixed by the scope) runs one stage. Every check gets
  one deadline, with explicit budgets for the preliminary stages and for any fallback, in place of a full timeout per
  stage. *Acceptance: example 142's harness runs once, and no check runs past its deadline.*
- **4b. Structured output.** Read JBMC through `--json-ui`, keeping the text parser only until a differential test over
  every recorded JBMC example shows the two agree. Unsupported input, unwinding failure, timeout, memory exhaustion,
  solver failure and counterexample stay distinct.
- **4c. JBMC's own approximations are gaps too.** Detect reachable stubs (missing bodies JBMC fills with a
  nondeterministic or empty body) and the zero/null fallback for an unresolved `invokedynamic`, from its output or a
  `--show-goto-functions` preflight. They become gaps in the same three modes. JBMC can apply a Phase 3 contract only
  where the harness can express it (as an assumption around the call), and a contract it can't apply leaves the gap
  open. *Acceptance: 1b's reproducers give the same answer under JBMC in each mode.*

### Phase 5: measure before optimizing

- **5a. A benchmark corpus in three groups.**
  - Semantic conformance (Phase 1's corpus).
  - Real regressions with a known bad and a fixed version, and properties reviewed independently of the tool. CVE
    kernels are welcome where a fixed version exists.
  - Held-out performance cases that didn't motivate the optimizations.

  Report correctness, supported coverage (per gap mode), time and memory separately. An unsupported case is not a
  success.
- **5b. Per-phase measurements for both engines, on matched statements, models, bounds, solver and gap mode.** Measure
  class loading and lowering, symbolic execution, encoding, solving, trace extraction, contract checking, peak memory,
  and the formula's variables and clauses. JBMC reports some of this itself (`--verbosity` timings, program size,
  solver statistics). The native engine extends `bmc::Stats`. These are pipeline jobs.

  *Acceptance: for each workload class (scalar arithmetic, div/rem identities, binary search, UTF-8 encoding, bounded
  array mutation, records), a table says which phase dominates in each engine.* The JBMC review's patch candidates are
  ranked from that table, not from source reading, and the table goes into [`jbmc-patch-queue.md`](jbmc-patch-queue.md)
  as the evidence for deciding on it.

## Open questions

Settled by the user on 2026-11-05. A new question that comes up goes here, with a default the loop takes until the user
settles it.

1. **A vacuous `Verified`:** a distinct status in the result and on the page, with the exit code unchanged (0).
   Changing the exit code changes every caller, so that stays the user's decision.
2. **`--engine auto`:** a native success is confirmed by JBMC only on request (`--confirm`), and the result says
   whether a success was confirmed.
3. **The recorded examples:** the default gap mode is strict, but that doesn't mean every example is re-run in strict
   mode. How the existing examples move is decided later, from 1a's scan. Until then they run in `assume` when they
   run at all, and their `expected` verdicts stay as they are (see [How to work through it](#how-to-work-through-it)).
4. **A JBMC fork** is out of this loop: [`jbmc-patch-queue.md`](jbmc-patch-queue.md) is a working draft to refine
   over time, informed by Phase 5.
5. **Order:** this brief runs before the proof experiments `build-orchestration.md` defers. Profiles reuse 2a's
   statement, and a diagnosis of "gap" points at Phase 3.
6. **The default gap mode:** strict everywhere unless `--gaps` says otherwise. The skill passes `--gaps advised`, and
   `assume` is never the library's default (`build.py`'s interim default for recorded examples is question 3's).
7. **What CI accepts:** `--max-trust 0`, so trusted contracts fail and tested ones pass, with the evidence on the page.
   The user may tighten it to proved-only.

Decided by the user on 2026-11-06, after the loop's run (the numbers above are unchanged):

- **Question 3, the recorded examples:** decided once job `20261106-082917` (the JBMC gaps each recorded JBMC example
  reaches) is back, with its table in hand. Until then they stay in `assume`. The job is at priority 10.
- **Question 1, a vacuous `Verified`:** the exit code stays 0, the status is the signal.
- **Question 7, what CI accepts:** proved and tested (`--max-trust 0`) for now. The accepted evidence level is to become
  configurable, likely per project, especially as more runs use `assume`.
- **The benchmark's departures (5a):** the user reviews group 2's properties. Group 3 and the rest are accepted as
  recorded. A CVE kernel is future work, done well before any public claim rests on the corpus.
- **The landing page at terminalvalue.net:** no update needed; the item is dropped.
- **The JBMC fork (question 4):** ranked from job `20261106-102624`'s table when it is back; fork or not is decided
  from that ranking.
- **Leftovers:** the relative `--jbmc` path and the console report's statement and phases are fixed next. For
  `real/bucket/fix-confined` (the timeout) and `--confirm` with contracts, an analysis comes first, and the user
  decides from it whether to do them.

## Done when

| Phase | Criterion |
|---|---|
| 1 | Every construct is implemented, modelled or a named gap. Under strict, no engine, nor `--engine auto`, gives `Verified` for a claim the JVM refutes on any conformance case, and the coverage cost is measured per example |
| 2 | Every result states its domain, assumptions (gaps and contracts with their evidence), observations, bounds, models, solver, gap mode and vacuity status as data |
| 3 | An agent can close a gap with a contract the tool proves or tests, a wrong contract is rejected with a counterexample, accepted contracts are reused, and an example shows it end to end |
| 4 | JBMC runs only the stages that can change its domain, within one deadline, read as JSON, with its stubs as gaps |
| 5 | A per-phase table for both engines over the three-group corpus, on matched configurations |

The pipeline jobs submitted along the way are back with their expected verdicts, or their failures are explained under
Progress.

## Deferred: not in this loop

Kept as context, so the phases above leave room for them:

- **Independent checking at the SAT boundary.** CaDiCaL can emit DRAT/LRAT proofs, and `cake_lpr` or `drat-trim` can
  check them. It has to cover every UNSAT decision that pruned exploration, not just one final formula, and it doesn't
  help a wrongly encoded formula: it comes after Phase 1. Phase 2a's statement and format 2's bundle are where a
  certificate would attach, and a proved contract's proof would join it.
- **Compositional reasoning beyond JDK calls.** Phase 3's contracts are method summaries for calls the engine can't
  enter. The same protocol extends to proved summaries of application methods, checked loop invariants and frame
  conditions, where the agent proposes and the verifier establishes. That extension, and proof reuse with precise
  invalidation, come after this loop.
- **Patching JBMC.** The patch queue and the engine work beyond it (array representations, persistent path prefixes
  with incremental solving, a compiled-model cache behind a worker pool) are in [`jbmc-patch-queue.md`](jbmc-patch-queue.md).
- **Concurrency.** JPF territory, and outside the native engine's single-threaded model, which Phase 1 makes explicit.

## Progress

Each run counts only its own commits, so work done in earlier runs is listed here.

- **1a, the gap scan (2026-11-05).**
  - `jvmcontract gaps --classes DIR --target C#m [--json]` ([`lib/src/bmc/gaps.rs`](../../lib/src/bmc/gaps.rs)) walks
    what a proof's roots may reach, as the engine resolves calls. It lists each gap by a stable id: the kind and the
    member, plus `@jdk-<version>` for a call into the JDK, as in `jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25.0.4.1`.
    It also lists the JDK calls the engine reproduces exactly and relies on, and what the engine refuses outright.
  - The kinds: `jdk-constructor`, `jdk-void-method`, `jdk-reference-method`, `monitor`, `hidden-field`,
    `literal-identity`, `class-initializer`, `string-conversion`.
  - `bmc::models_jdk_static` lists the arms of `call_jdk_static`, so the scan and the engine agree on what is modelled.
  - `build.py --scan-gaps` scanned the 56 B9/B11 examples on the javac apps (both versions for B9) and left a
    `Gap scan (...)` note in each.
  - **Result: strict mode moves no recorded verdict.** 54 examples have no gap. 013 and 071 (Quorum's vote rule, proved
    by JBMC) each meet four enum class initializers and one literal compared by reference. The native engine already
    refuses both examples, since enum constants are static fields that aren't compile-time constants.
  - Not scanned:
    - Box Office B9 006–008 run on the Gradle verifier.
    - The real-world 105–109 have no classes in the repository.
    - B8, B10, B12 and D1 are not proofs over bytecode.
  - **For 1b, the allow-list must be wider than this brief says.** It needs `Record.<init>()` (14 examples) and the JDK
    exceptions' `()`, `(String)` and `(String, Throwable)` constructors (25 examples), on top of `Object.<init>` and
    `lib/models`. Without them, strict would refuse almost half the corpus. `gaps::exact_jdk_call` is that list.
  - `string-conversion` can only come from javac 9–18 bytecode. From JDK 19, javac calls `String.valueOf` before
    concatenating, and the engine refuses that call.
  - The scan doesn't walk the harness, or the property and relation expressions compiled into it.
  - Next: 1b, gaps as data in the engine, with `--gaps strict|assume`.
- **1b, gaps as data, strict and assume (2026-11-05).**
  - The engine meets four kinds as it runs, sharing `gaps::jdk_instance_call` with the scan, so the two agree:
    `jdk-constructor`, `jdk-void-method`, `jdk-reference-method` and `string-conversion`. Under `--gaps strict`, the
    library's default, the path ends at the gap (`End::Gap`). A run that met one is `Unverifiable` unless another
    path is a violation, and its reason lists every gap met, with sites. Under `--gaps assume` the old approximation
    stays and is named: `Outcome.gaps` records each gap with its id, call, sites, approximation and treatment, which
    reach `search.gaps` and `search.gap_mode` in `--json`, then `✓ ..., assuming N behaviours ...` with an
    `assumed:` line per gap.
  - Monitors are implemented, not gaps: NPE on null, otherwise nothing. The scan no longer reports them.
  - `--engine auto` doesn't fall back to JBMC once the own checker has refused a gap, since JBMC would approximate the
    same call without naming it (4c). That is how auto meets the acceptance.
  - The engine's module docs have a table: implemented, modelled, gap or refused. A unit test decodes every opcode and
    checks it has a row there, and that every gap kind has a row in `gaps.rs`.
  - Acceptance, in the integration test `a_gap_is_refused_by_name_under_strict_and_named_as_an_assumption_under_assume`:
    - `new ArrayList<>(n)`, and `Random.nextBytes` on an argument array, are refused by name under strict on native
      and on auto, and `Verified, assuming ...` under assume.
    - `synchronized (null)` is a violation in both modes, with an NPE that the interpreter replays.
    - A real JVM run in the test confirms what the verdicts should be: `IllegalArgumentException`, NPE, and an
      array changed.
    - A regression proof with a JDK constructor added gives the same answers.
  - `build.py` passes `--gaps` only where the own checker decides the verdict (engine `native` or `auto`): the
    example's `approach.gaps` (in the schema), or `RECORDED_GAP_MODE = "assume"`.
    - `result.search` keeps `gapMode` and `gaps`.
    - A verified label and page name the assumed gaps.
    - No recorded result has gaps (1a), so no page changed and no job was needed.
  - For 2a: the gap mode is an attempt option, not part of the claim, so a recorded claim doesn't go stale over it. 2a's
    statement should take it in.
  - Still approximated silently in both modes, as the table says: hidden fields, literal identity and class
    initializers. That is 1c.
  - Next: 1c, identity and initialization.
- **1c, identity and initialization (2026-11-05).**
  - Two of the three are now implemented, not gaps, so `hidden-field` and `literal-identity` are no longer gap kinds
    (like `monitor` in 1b).
    - **Fields:** `ClassPath::resolve_field` is the JVM's field lookup (JVMS §5.4.3.2), and `ClassPath::field_key`
      keeps a field a subclass declares again under `Declaring.name`, while the usual field keeps its plain name. The
      engine and the interpreter both key fields this way. **The interpreter had the same bug**, so it replayed the
      engine's wrong witness as confirmed. That is the brief's point about shared semantics, shown.
    - **Literals:** each path keeps one object per distinct string or class literal (`Path.literals`). A string
      concatenation stays a new object, as JLS §15.18.1 says (checked on JDK 25: `s + ""` is not `s`). The
      interpreter already interned literals.
  - **Class initializers** are a gap the engine meets. `gaps::initializers` lists the `<clinit>`s that a class's
    initialization runs, in the JVM's order (JVMS §5.5): the superclasses' first, then superinterfaces with a default
    method, then the class's own. The engine meets them at the first `new`, `getstatic` (of the declaring class) or
    `invokestatic` (of the declaring class) on a path. The scan uses the same function. Under assume the initializer
    "has run already, and threw nothing". A JDK class is taken to be initialized already.
  - **`--engine auto` now asks JBMC when every gap refused is a class initializer** (`GapKind::jbmc_implements`),
    since JBMC runs initializers. It still doesn't ask JBMC after a JDK-call gap.
  - Acceptance, in the integration test `identity_and_initialization_agree_with_the_jvm`, each claim checked
    against a real JVM run:
    - field hiding, both the subclass's field and the hidden one;
    - a string literal compared across two classes, two different literals, and a class literal;
    - a throwing `<clinit>`, a throwing superclass `<clinit>`, and a harmless one.
    - The old engine gave `Verified` for four claims the JVM refutes, checked on the parent commit's binary:
      `hiding` `result == 2`, `sameLiteral` `!result`, `sameClass` `!result`, and `boom` `result == n`, where the
      JVM throws `ExceptionInInitializerError`.
    - Now the first three are violations whose witnesses the interpreter replays. `boom` is refused by name under
      strict, `Verified, assuming ...` under assume, and a violation (`ExceptionInInitializerError`) from JBMC
      under auto.
    - A harmless initializer is refused under strict too. That is the coverage strictness costs.
  - The 56 examples were scanned again, in 41 s. Only 013 and 071 changed: the literal-identity gap left them, and
    they keep their four enum initializers. Strict mode still moves no recorded verdict, and no job was needed.
  - Not done: a `getstatic` of a `String` constant field is still refused (javac inlines those as `ldc`).
  - Next: 1d, the conformance corpus. It starts from 1b's and 1c's reproducers, then covers exceptions, aliasing,
    null array parameters, record constructors and arithmetic edge cases.
- **1d, the conformance corpus (2026-11-06).**
  - [`lib/tests/conformance.rs`](../../lib/tests/conformance.rs) holds 54 small methods
    ([`Conformance.java`](../../lib/tests/conformance/conformance/Conformance.java)) and 93 claims, 48 of them refuted
    on the JVM. The cases cover:
    - 1b's and 1c's reproducers;
    - JDK constructors given a negative capacity;
    - exceptions: `finally` over a return, nested handlers, bounds, casts, `throw null` and rethrowing;
    - aliasing, `null` arrays, record constructors (rejecting, normalizing, and `equals`), and dispatch;
    - arithmetic edge cases: `MIN_VALUE / -1` in both widths, negative remainders, shift counts of 32, 33, 64 and
      -1, narrowing, and overflow.
  - The JVM is the reference. A Java runner (`Runner.java`) runs each call, and each claim's generated harness, in a
    class loader of its own, so every line sees the classes uninitialized. Whether a claim is refuted is the JVM's
    answer on the harness, not the corpus author's: every refuted claim has an input the JVM confirms, and every
    engine witness is run on the JVM too.
  - Inline (11 s): the tool's own checker under strict and assume, and the interpreter against the JVM call by call.
    **No `Verified` under strict for a claim the JVM refutes, and no witness the JVM doesn't reproduce.** Under
    assume, a refuted claim is `Verified` only with its gap named. Every native verdict is recorded per claim. The
    refusals by name are a gap (the four capacity constructors, `Random`, three class initializers) or a construct
    outside the fragment (record `equals` through `invokedynamic`, `i2f`).
  - **The corpus found a bug in the interpreter, not the engine.** `new ArrayList<>(n)`, `new HashMap<>(n)`,
    `new HashSet<>(n)`, `HashMap(4, f)` and `new StringBuilder(n)` returned normally for a negative `n` (or a load
    factor of 0 or less) where the JVM throws. That is the shared-semantics hazard of [How to work through
    it](#how-to-work-through-it), and it would also have put a wrong behavioural contract (B8) on such a method. They
    now throw what the JVM does. The corpus failed on it before the fix.
  - **A `null` array, or one array passed as two parameters, is outside the domain, and the domain now says so.**
    Both engines give each array parameter a non-null array of its own (JBMC through
    `--java-assume-inputs-non-null`), and the domain line read `a: int[] of length ≤ 8`. It now reads
    `a: int[] of length ≤ 8, not null`, ending `; no two the same array` when there are two arrays or more
    (`harness::domain`). The corpus's three such cases check that a `Verified` states the restriction that leaves out
    the JVM's refuting input. Recorded pages keep the old text until they are re-run. Modelling `null` and aliased
    arrays would change every recorded array verdict, so 2a takes them as data instead.
  - JBMC and `--engine auto` run the same corpus in an ignored test, pipeline job
    `20261106-021741-conformance-corpus-under-jbmc-and-engine`. **This departs from the brief:** the JBMC cases aren't
    examples under a `false-success` tag. A corpus is a table of claims over one class, and examples would put one
    claim on each page. So the tag is not added.
  - Next: 1e, `--confirm` for `--engine auto`.
- **1e, `--confirm` for `--engine auto` (2026-11-06).**
  - With `--engine auto --confirm`, for property and regression proofs alike, JBMC proves again any statement the
    tool's own checker proved. It runs once over every input, on the same harness and class path: the interval stages
    only find small witnesses sooner. The option is opt-in, and the CLI refuses it under any other engine.
  - `search.confirmation` records the result, with a status of `confirmed`, `disagreed`, `no-verdict` or `not-asked`,
    plus the checker, its seconds and the reason. A line under `✓` says it in words (open question 2).
  - **A disagreement is neither verdict.** The result is `Unverifiable`, "the engines disagree", with the finding
    `engines-disagree`, rather than a fourth `Verdict`: every caller already treats `Unverifiable` as no verdict, and
    the status says why. JBMC's witness is the counterexample, and the interpreter's run of the harness on it is shown
    (`replay.reproduced`). The interpreter decides nothing, since it shares the own checker's models: the message asks
    for a JVM run.
  - **"Wherever JBMC supports the harness"** means wherever it would check what the own checker assumed. A proof
    under `--gaps assume` that assumed a JDK call is `not-asked`, because JBMC would approximate the same call without
    naming it (4c). A class initializer assumed to have run is checked, since JBMC runs it. A JBMC with no verdict
    leaves the proof standing as the own checker's alone, exit 0, and the result says so.
  - Verified inline by `confirm_reports_what_jbmc_made_of_a_proof_of_the_own_checker` in `tests/conformance.rs`. A
    script stands in for JBMC there, since JBMC is not run inline. It covers each status, both drivers, the one-run
    command line, the JSON and the CLI refusal.
  - The real JBMC confirms the whole corpus under strict and assume in the ignored test
    `the_corpus_agrees_with_the_jvm_under_auto_confirm`, pipeline job
    `20261106-024336-conformance-corpus-under-engine-auto-con`. It fails on a JBMC confirmation of a
    claim the JVM refutes, and on a disagreement over one it does not. Under assume, `boom` and `inherited` should be
    disagreements, with an `ExceptionInInitializerError` witness.
  - `build.py` doesn't pass `--confirm` (no `approach` field), and no recorded result changes. 2a should take the
    confirmation into the statement, next to the gap mode.
  - Seen, not fixed: a relative `--jbmc` path fails, because JBMC runs in the work directory.
  - Phase 1 is complete, apart from the two pipeline jobs.
  - Next: 2a, the statement as data.
- **2a, the statement as data (2026-11-06).**
  - Both drivers' outcomes carry `stated` ([`lib/src/statement.rs`](../../lib/src/statement.rs)) whenever a harness
    was built, whatever the verdict. It holds:
    - **D**: each parameter with its kind (`primitive`, `array`, or `record` with its components), whether `null`
      is among its values, an array's longest length, and whether two arrays may be one (`shared_arrays`).
    - **A**: each assumption with a kind and a `basis`. The basis is `stated` by the claim (`--unchanged-unless`,
      `--assume`); made by the `harness` (a record's constructor rejecting an input, or `--before-arguments`
      throwing, skips it); the checker's `engine` semantics; or a gap `assumed`, with its id. The own checker's
      engine assumption is that every JDK class is initialized already. JBMC's is that a JDK method outside the
      models and its six JDK classes is a stub: 4c makes those gaps. Phase 3's contracts get bases of their own.
    - **Obs**: what is compared of the result (equality, a record by components, an array by elements, or the
      `--results-agree-when` relation), of an exception (its class among the harness's 15, not its message or
      state), and which arrays after the call. For a property, the assertion and the throws clauses.
    - The unwinding bound, the array bound, and `complete` (true for a proof). The models: whether used, a
      `sha256:` digest over every model's name and class file (a SHA-256 written out in `lib/src/digest.rs`,
      since the build has no network), and the JDK's version. The checker with its SAT solver (the own checker's
      bundled `CaDiCaL 1.9.5`) and fallback. The gap mode, and the `--confirm` status.
  - Identical bytecode is a statement too, with checker `none` and no models or unwinding.
  - `build.py` records it as `result.stated`, in camelCase, which format 2 stores in `evidence`. A property keeps its
    own under `properties`. The schema has it as `$defs/statement`. A page states it in one paragraph, **What the
    verdict is about**, after the proof line, or one per property.
  - Acceptance, inline:
    - `the_statement_says_what_a_verdict_is_about` (conformance.rs) runs the own checker on pairs of claims that
      differ only in the domain (array bound 8 or 4), the observations, an assumption, or the models (on or off).
      Each pair's statements differ in that part alone.
    - `StatementTest` (test_build.py) renders pairs whose statements differ in the domain, observations,
      assumptions, models or confirmation, and checks that each paragraph says the difference in its sentence.
  - No recorded result has `stated` until it is re-run, so no page changed (`--render-only` of every example).
    Pipeline jobs `20261106-025930-example-144-b9-re-run-its-result-records` and `...-145-...` re-run the pair that
    differs only in the array bound (8, vacuous; 12, real), so two real pages show it.
  - Not done:
    - The console report doesn't print the statement; `--json` and the page do.
    - `search` keeps its own copies of the bounds and gap mode, so as not to break its readers.
    - JBMC's solver is recorded as asked (`cadical`), without the version JBMC bundles.
    - Vacuity stays where it was, for 2b.
  - Next: 2b, vacuity as a status.
- **2b, vacuity as a status (2026-11-06).**
  - A verified statement carries `stated.vacuity` ([`Vacuity`](../../lib/src/statement.rs)): a `status` of
    `non-vacuous`, `vacuous` or `unknown`, a `basis` saying how it is known, a sentence, and the probe's witness.
    - `harness`: nothing skips an input before the calls (no scope, record, `--before-arguments` or `--assume`), so
      every input in D reaches them.
    - `probe`: the existing probe (the harness with the calls replaced by a failure, run by the own checker). Its
      violation is now kept as evidence, `not vacuous: span(this=Range[lo=20, hi=20]) reaches the calls`. Its proof is
      `vacuous`, as before (`Outcome.vacuous` keeps the reason for its readers). No verdict is `unknown`, with a
      line `vacuity unknown: ...` in place of the old `note:`, which nothing read.
    - `identical`: identical bytecode agrees on every input, whatever the scope.
  - Only a `Verified` has a status: a violation's witness reaches the calls by being one. Exit code 0 throughout
    (open question 1).
  - **The record-constructor caveat** is stated wherever it applies: a line `constructors: ...` under `✓`, the
    `constructible` assumption (2a), and the page's paragraph. Identical bytecode drops it, since the constructors
    are among what is identical.
  - `build.py`: the statement's paragraph ends with the vacuity sentence, and a label gains `, non-vacuity unknown`
    (or `for k of n` properties). `expectation` is unchanged, so an unknown verdict is not called vacuous. Schema:
    `$defs/statement/vacuity`.
  - Acceptance, inline: `vacuity_is_a_status_of_a_verified_statement` (conformance.rs) gets each status from real
    runs. Unknown comes from JBMC (a stand-in script) proving a method of a record whose constructor meets a gap
    the own checker's probe refuses under strict. `VacuityTest` (test_build.py) covers the record, label and page.
  - No recorded result has a status until it is re-run, so no page changed. Job
    `20261106-031642-example-127-b9-re-run-its-statement-says` re-runs 127 (records, proved by JBMC), whose page
    should show the probe's witness and the caveat. The pending 2a re-runs of 144/145 will not show a status.
  - Phase 2 is complete.
  - Next: 3a, the gap protocol (`--gaps advised`).
- **3a, the gap protocol (2026-11-06).**
  - `--gaps advised` ([`lib/src/advice.rs`](../../lib/src/advice.rs)), for property and regression proofs alike. The
    driver builds its harness, then scans the harness and every method it may reach (`gaps::scan`, rooted at the
    harness's `check`), on the class path the engine is given. No solver runs. A gap with no contract stops the run:
    - The verdict is `Unverifiable`, with the finding `gaps-need-contracts`, and `search` is absent, since nothing
      was solved. `stated` has the checker `none` ("gap scan: nothing was solved") and the gap mode `advised`.
    - `advice` in `--json` holds the claim in words, the JDK's version, and each gap with its id, call, owner, name,
      descriptor, parameters, result type and sites, plus what `--gaps assume` would take it to do. It also holds
      `must_state`, the parts a contract must state per kind (result, exceptions, receiver, arguments, the static
      state an initializer sets, purity), each with a question, and the gap's template block. `outside` lists what
      the engine refuses whatever the contracts say.
    - The template file is `contracts.template` in the work directory, and the console prints it after a `gap` line
      per gap.
  - **The template is the draft of 3b's format.** It is a block per gap, headed by its id, using `prove`'s keys:
    `call:` (which names the parameters, since a JDK class file keeps no names, so `arg0`), `assume:`,
    `throws: X when c`, `assert:` (over the arguments, `this`, `result` and `\old`), `modifies:` and
    `written-by:`. 3b parses it and applies it.
  - **With no gap, advised is strict.** `GapMode::refuses()` is true for both, so a gap the scan missed is still
    refused. Advised needs `--engine native` or `auto` (an error under `jbmc`, whose stubs are 4c's).
  - **The scan reaches every gap, not only the first a path meets.** `firstByte` gets both `Random.<init>` and
    `nextBytes`, where strict ends the path at the first.
  - Acceptance, inline:
    - `advised_stops_before_solving_with_each_gap_and_what_its_contract_states` (integration.rs) covers native and
      auto, property and regression: no `bmc.log`, the ids, sites, parameters, obligations, template file, JSON
      and statement, and a gap-free claim decided as strict decides it.
    - The conformance corpus now runs under advised too. It asks for contracts on exactly the 9 claims strict
      refuses for a gap (the five capacity constructors, `Random`, the three initializers), and decides the other
      84 as strict does. The test fails if advised asks where strict decides, or solves after advising.
    - `AdviceTest` (test_build.py) covers the record, the template in the example's folder, the schema
      (`$defs/advice`), the label `Unverifiable: 1 gap needs a contract (--gaps advised)`, the page's paragraph and
      details, and a stale template being removed.
  - `build.py` passes `approach.gaps: "advised"` through (now in the schema's enum). It keeps `advice` with the
    template copied to `contracts.template` (`contracts-N.template` for property N of several).
  - **This departs from the brief: 3a has no recorded example of its own.** A "contracts needed" page would record
    the protocol's output, which the corpus and the integration test already pin, and no verdict about any code.
    The example that shows the protocol is 3c's: the review's reproducer in an app kernel, a buffer pre-sized by a
    sum that can overflow. Its page will show the advice first, then the verdict once a tested contract
    (`IllegalArgumentException` when the capacity is negative) closes the gap, and the wrong contract rejected
    with its counterexample. No page changed (`--render-only` of every example), and no job was needed.
  - Not done: the scan may name a gap on a path no input takes (none on the corpus). A static JDK method the
    engine does not model is still refused outright, not a gap, so the protocol does not reach it. 3b could make
    it a gap kind.
  - Next: 3b, the contract format, read with `--contracts FILE` and applied by the engine at the call.
- **3b, the contract format (2026-11-06).**
  - `--contracts FILE` under `--gaps advised` ([`lib/src/gap_contracts.rs`](../../lib/src/gap_contracts.rs)), for
    property and regression proofs, reads 3a's template once it is filled in: `kind: gap-contracts`, then a block per gap
    under its id, with these keys:
    - `call:` names the parameters;
    - `assume:` is the inputs the contract covers;
    - `throws: X when c` may be repeated, and the first clause that holds decides, as in a property;
    - `assert:` is what holds afterwards;
    - `modifies:` is `nothing`, `this`, or an array parameter;
    - `written-by:` says who wrote it.

    The conditions are `prove`'s expressions, as the brief asks, over the primitive parameters and arrays of them.
  - **The engine applies a contract by running bytecode.** Each accepted contract becomes a static method of a generated
    class, `GapContracts`, written as the harness is, which the engine calls in place of the JDK call:
    - a branch per throws clause, which throws;
    - `havoc` gives an array the contract modifies fresh elements;
    - the assertion becomes a condition, and `infeasible` ends a path it excludes;
    - outside `assume:`, `open` meets the gap at the call, and it is refused there;
    - a reference result is whichever object the contract names: `result == this`, `result == <parameter>`,
      `result == null`, or `\fresh(result)`;
    - an initializer whose contract throws nothing and modifies nothing is taken to have run.
  - **A contract the engine cannot apply is refused with the reason, and its gap stays open.** The reasons: a `TODO`
    left; a call that doesn't match the id; `this` or an object parameter in a condition; `result != null` alone,
    which doesn't say which object; an initializer that throws or sets state; `\old`; a string conversion; a
    contract for another JDK's version, or one that names none. The refusal is printed in a `note:` line and kept as
    `refused_contract` in the gap's advice. The advice also lists `closed` gaps, and its template covers only the
    gaps still open.
  - **The verdict says what it rests on.** For example: `✓ ..., relying on 1 contract for gaps of the tool's own
    checker, 1 trusted`, with a `contract:` line for each, giving what the contract states and who wrote it.
    - `search.gaps` records each gap with the treatment `contract` and the contract.
    - The statement gives it an assumption of kind `contract`, with basis `trusted`: nothing checks a contract
      until 3c.
    - Under auto, a run that applied a contract is not handed to JBMC, and `--confirm` doesn't ask JBMC either
      (`not-asked`), since JBMC cannot apply a contract.
    - The interpreter runs the JDK's real call. When it doesn't reproduce a witness found through a contract, the
      result is no verdict, and the contracts are named as the likely cause. (A native witness that doesn't
      reproduce is no longer called "JBMC's".)
  - Acceptance, inline:
    - `a_contract_closes_its_gap_and_the_verdict_rests_on_it` (integration.rs), on native and auto:
      - The review's `new ArrayList<>(n)`, with the contract that matches the JVM, is a violation on `capacity(n=-1)`.
        The interpreter reproduces it with the JVM's own message.
      - With a matching throws clause in the claim, it is Verified, relying on 1 trusted contract.
      - With a contract that throws nothing, it is Verified and names that contract. Trusted, a wrong contract gives
        a wrong verdict: this is 3c's case.
      - Outside `assume:`, the gap is refused at the call.
      - `Random.nextBytes` with `modifies: bytes` is a violation where the array is read back, and Verified on its
        length.
      - `StringBuilder.append` with `result == this` is Verified. With `\fresh(result)` the witness doesn't
        reproduce, so there is no verdict.
      - An initializer's contract is applied.
      - A `TODO` contract goes back to the agent with its reason, and the regression driver behaves the same way.
    - The conformance corpus has a fourth column, advised with contracts. An agent (this session) wrote the corpus's
      contracts from the JVM's behaviour on its calls. They decide 6 of the 9 claims strict refuses for a gap, as the
      JVM decides them: the four capacity constructors and `firstByte` are violations whose witnesses the JVM
      reproduces, and `quiet` is Verified. The contract for `boom` throws, so it is refused. `inherited` and
      `loadFactor` have none. The test fails on a Verified the JVM refutes.
    - `ContractsTest` (test_build.py) covers these: `approach.contracts`, which is in the schema, a file in the
      example's folder that the runner copies to `build/gap-contracts/` so the recorded path is the same on every
      machine; the search record and the schema's contract object; the label `, relying on 1 contract for gaps (1
      trusted)`; the page's paragraph; and the advice's refusal and closed gaps.
  - **This departs from the brief in two ways.**
    - No recorded example of its own. A page whose verdict rests on an unchecked contract shows only the format, so
      3c's example (an ArrayList pre-sized by an overflowing sum) shows both steps, with evidence levels. No page
      changed (`--render-only` of every example), and no job was needed.
    - "The result, as an expression over the arguments" applies to no gap yet. Every gap kind's result is void or
      an object, so `assert:` on a result only chooses which object it is. A JDK method with a primitive result, and
      a static JDK method the engine doesn't model, are still refused outright rather than treated as gaps. Making
      them gap kinds (with no assume form) is what would let a contract state a value; it is a candidate for 3c or 3d.
  - Not done:
    - `\old` in a contract.
    - Contracts for a string conversion.
    - JBMC applying contracts (4c).
    - An application subclass that inherits the JDK method a contract is about.
    - A trusted contract whose assertion constrains state the call does not change removes inputs, as any wrong
      contract can. 3c's test on the JVM is what catches it.
  - Next: 3c, checking each contract: proved against the JDK's bytecode, tested on a real JVM, or trusted.
- **3c, first part: contracts tested on a real JVM (2026-11-06).**
  - Each contract the engine can apply is tested before it is used
    ([`lib/src/contract_testing.rs`](../../lib/src/contract_testing.rs)). A generated class, `GapContractTests`, is
    run once by the `java` of the JDK the gap ids name, with a 128 MB heap. For each contract, it calls the JDK's own
    method:
    - on every combination of its parameters' boundary values (up to 512), then on 256 random inputs drawn with a
      recorded seed (SplitMix64, seed 1), arrays of up to four elements;
    - an instance method on an object built by its class's constructor of no arguments;
    - an initializer by loading its class (`Class.forName`).

    It checks the contract on each input with the bytecode the engine's method for it uses (`expr::emit`). Inside
    `assume:`, the first throws clause that holds before the call decides, and the JVM must throw exactly that class.
    Where none holds, it must return, with every array `modifies:` leaves out unchanged, the result the object named,
    and `assert:` holding.
  - **The levels.** `Evidence` is `tested` or `trusted`, ordered strongest first, and `ContractUse` carries `testing`
    (inputs, returned, thrown per clause, outside, exhausted, seed, JDK, receiver, counterexamples) or `untested` (why
    trusted). A contract the JVM refutes is refused, its gap stays open, and the advice for the gap carries the
    counterexamples, each an input with what the contract expected and what the JVM observed. That is how the
    counterexample goes back to the agent. A contract the JVM cannot test (a parameter of an object type, a receiver
    it cannot build, a non-public call, no JVM) is trusted, with the reason.
  - **The verdict counts them:** `relying on 2 contracts for gaps of the tool's own checker, 1 tested, 1 trusted`, and
    each `contract:` line says `tested on 128 inputs on JDK 25.0.4.1 (seed 1), 38 more running out of the test's
    memory, none refuting it`. The statement's basis is `tested` or `trusted`. `build.py` puts the levels in the label
    (`(1 tested, 1 trusted)`) and the page, and lists other refuting inputs under the advice. The schema has
    `testing`, `untested`, the advice's `counterexamples` and the basis `tested`.
  - **A `VirtualMachineError` on the JVM is counted apart, not as a counterexample.** `new ArrayList<>(n)` runs out of
    memory for most large positive `n`, and a proof is about a JVM with enough memory. This is a decision the brief
    does not make, so it is recorded here.
  - **A contract is now about arrays that are there.** The test makes no `null` arrays, and the expressions cannot
    say `a == null`, so at a `null` array parameter the engine meets the gap rather than applying the contract.
  - Acceptance, inline, in `a_contract_closes_its_gap_and_the_verdict_rests_on_it` (integration.rs), on native and
    auto:
    - "`new ArrayList<>(n)` doesn't throw" is refused: `a JVM refutes it: on capacity=-1 the JVM's call throws
      java.lang.IllegalArgumentException: Illegal Capacity: -1, where the contract says it returns normally (83 of 128
      inputs refute it, ...)`, with the counterexamples in the advice. The run stops with the gap open.
    - The corrected contract (`throws: IllegalArgumentException when capacity < 0`) is tested, both of its sides
      exercised. The review's reproducer is then the violation `capacity(n=-1)`, which the interpreter reproduces
      with the JVM's message.
    - The JVM also refutes these: a `modifies:` that leaves out the array `nextBytes` fills, an assertion it does not
      keep, and `\fresh(result)` for `append`, which 3b caught only as a witness that didn't reproduce. A contract for
      `append(String)` is trusted, with why.
    - On the conformance corpus every contract is tested and none is refuted; the test fails otherwise.
    - `ContractsTest` has two new tests (150 Python tests in all).
  - Re-rendering every page changed none, and no job was needed.
  - **This departs from the brief in two ways.**
    - `proved` is not done. The JDK calls that are gaps today (constructors, `void` and reference-returning instance
      methods) are almost never in the engine's fragment: `ArrayList(int)` needs a reference array, a JDK static field
      and an `invokedynamic` string concatenation for its message. A static JDK method such as `Arrays.fill(int[],
      int)` would be in the fragment, but the engine refuses a static JDK call outright rather than treating it as a
      gap.
    - **Still no recorded example**, the third step to defer it. A realistic kernel (an `ArrayList` pre-sized from a
      count, then filled) needs `list.add`, a JDK method with a primitive result, which the engine also refuses
      outright. Both refusals are what 3b's Progress called a candidate for 3c or 3d.
  - Not done:
    - A tested contract is re-tested on every run (about 0.3 s, all of a file's contracts in one JVM). The corpus's
      contracts column takes about 30 s of the conformance test's 52 s. 3d's library checks a contract once.
    - Receiver state is not observed, so `modifies: this` is not checked.
    - Object parameters get no values, so such contracts stay trusted.
  - Next: 3c's second part. Make a JDK method with a primitive result, and a static JDK method the engine doesn't
    model, gap kinds with no assume form, so a contract can state a value (`size()`, `add` returning `true`). Prove
    a contract against the JDK's bytecode where the method is in the fragment (`Arrays.fill`), giving `proved`
    above `tested`. Then the recorded example.
- **3c, second part: calls whose value the proof reads are gaps (2026-11-06).**
  - Two new gap kinds, both in the scan and the engine (`gaps::jdk_instance_call`, and `gaps::jdk_static_call`
    for the static case):
    - `jdk-primitive-method`: a JDK instance method returning an integer, a `char` or a `boolean`, such as
      `Random.nextInt(bound)`;
    - `jdk-static-method`: a static JDK method the engine does not model, such as `Integer.numberOfLeadingZeros`
      or `Arrays.fill`.

    The engine used to refuse both outright. What it still refuses is a JDK method with a floating-point parameter
    or result, or with an array result.
  - **Neither has an assume form** (`GapKind::assumable`). The engine could only make the value up, so `--gaps
    assume` refuses them as strict does, with treatment `refused`, and the reason says that only a contract closes
    them. A run under assume that met both kinds of gap names the assumed ones and refuses these.
  - **A contract states the value.** `assert:` reads `result` for a primitive result, as in `0 <= result && result
    < bound`; `throws:` and `assume:` cannot read it. The contract's method takes the value from a new intrinsic
    (`anyInt()` or `anyLong()`), narrows it to the result's type, and keeps only what `assert:` admits. A static
    call has no receiver.
  - **The JVM test covers both kinds.** It calls a static method by `invokestatic`, and stores a primitive result
    where `result` reads it. A refuted assertion says what the JVM returned: `on i=0 the JVM's call returns 32,
    where the contract says it returns with `assert: 0 <= result && result < 32` holding`.
  - **A witness through a contract that the interpreter cannot run is now no verdict.** For example,
    `new Random(7)` is not something the interpreter can run. A contract admits values the JDK's call may never
    return, so such a witness is one the contracts admit, not yet the JVM's. Both drivers apply this rule
    (`equivalence::unconfirmed_through_contracts`).
    - **This changes a 3b result:** `firstByte` with a `nextBytes` contract was a violation, and is now
      `Unverifiable`, since `Random(1)` writes one particular byte.
    - Running such a witness on a real JVM would settle it, and is not done yet.
  - **`--engine auto` now decides per gap whether to ask JBMC** (`Gap::jbmc_implements`, the `jbmc` field of
    `GapRecord`). Before, it decided per kind. It asks JBMC about a class initializer, as before, and now also about
    a call to a JDK class whose bytecode JBMC is given (`equivalence::JDK_CLASSES`: `Math`, `StrictMath`, `Integer`,
    `Long`, `Short`, `Byte`). That keeps today's fallback for, say, `Integer.numberOfLeadingZeros`. A gap in
    `java.util.Random` is still not handed to JBMC, since JBMC stubs that class.
  - **A bug fixed:** the JVM test ran `java` in its own directory with a relative class path. So a relative
    `--work` or `--classes` made every contract trusted ("could not find GapContractTests"). The paths are now
    absolute.
  - Acceptance, inline:
    - `a_gap_is_refused_by_name_under_strict_and_named_as_an_assumption_under_assume` covers `bits`, which calls
      `Integer.numberOfLeadingZeros`, under strict and assume. It also covers `roll` under assume on native and
      auto, where the `Random` constructor is assumed, `nextInt` is refused, and JBMC is not asked.
    - The scan test covers both kinds. `String.valueOf(Object)`, which javac 19+ emits for a concatenation, is now
      a gap.
    - `a_contract_closes_its_gap_and_the_verdict_rests_on_it` has three new cases:
      - `bits` is Verified on one tested contract. Its violation `bits(n=-1)` is reproduced by the interpreter,
        which runs `Integer`'s own bytecode. A bound the call does not keep is refuted at `i=0`.
      - `roll` is Verified on two tested contracts. A witness of `result < sides` through the contract is no
        verdict.
      - `0 < result` for `nextInt` is refuted at `bound=1`, where the JVM returns 0.
    - New unit tests in `gaps.rs`, `gap_contracts.rs` and `advice.rs`.
    - The conformance corpus is unchanged.
    - All Rust tests and the 151 Python tests pass.
  - **The 56 scanned examples were scanned again (41 s).** Four notes changed, all on JBMC examples, so no verdict
    moves:
    - 037 and 127 meet `Integer.numberOfLeadingZeros` and `Long.numberOfLeadingZeros`. Before, these were
      "refused in any mode".
    - 013 and 071 now also meet `List.of` and `List.copyOf`.

    The note says such a gap has no assume form (`build.py`'s `NO_ASSUME_FORM`). The other 52 notes differed only
    in the date and were left as they were. Re-rendering every page changed only those four. No job was needed.
  - Not done:
    - **`proved`** (the 3c part one deviation). `Integer.numberOfLeadingZeros(int)` is now a gap, and it is pure
      `int` arithmetic in the engine's fragment, so it is the natural first contract to prove against the JDK's
      own bytecode. It is also what 037's new version calls.
    - Running a witness that goes through a contract on a JVM.
    - Object parameters (`list.add(e)`) are still untested, so their contracts stay trusted.
  - Next: 3c's last part.
    - Add the `proved` level: prove a contract with `prove` against the extracted JDK method when the method is in
      the fragment (the `Integer` and `Long` bit operations, `Arrays.fill`), with `proved` ranked above `tested`.
    - Then the recorded example. 037's `tableSizeFor`, rewritten with `numberOfLeadingZeros`, is a candidate for a
      proved contract, and a `Random` or `ArrayList` call for a tested one.
- **3c, last part: contracts proved against the JDK's bytecode (2026-11-06).**
  - `proved` is the strongest evidence level, ranked above `tested` (`Evidence::Proved`, statement basis `proved`).
    It is implemented in [`lib/src/contract_proving.rs`](../../lib/src/contract_proving.rs).
  - **How a proof runs.** Before the JVM test, each contract for a static JDK method whose parameters are primitives
    is proved by the tool's own checker against the JDK's own bytecode. The proof is generated as a class,
    `GapContractProofs`, with one method per contract. That method calls the JDK method and checks the contract as
    the JVM test does:
    - inside `assume:`, the first throws clause that holds decides, and the class thrown must be exactly that one.
      The class is compared through a new engine intrinsic, `sameClass`;
    - otherwise the method returns, with `assert:` holding of its result.

    The method's class is copied from the JDK image into a directory on the class path, so the checker runs its
    bytecode rather than meeting the gap. The run is under `--gaps strict`, with loops unwound 16 times, 30 s per
    contract, and no contracts applied inside it.
  - **The JVM confirms what a proof refutes.** A proof's witness is added to the JVM's inputs, so only the JVM's run
    makes it a counterexample.
    - A witness the JVM does not reproduce is a disagreement with the JVM. The contract stays tested, and `unproved`
      says so.
    - With no JVM, a refuted contract is refused: it stays open, rather than being trusted.
  - **What a proved contract records.** It is proved only if the JVM refutes nothing either, so it is also tested.
    `proof` records the class, the JDK, the class file's `sha256:` digest, the checker, the unwinding, the paths and
    the seconds. The contract line reads `proved on every input against the bytecode of java.lang.Integer in JDK
    25.0.4.1 (sha256:...), by ... over 18 paths; tested on 166 inputs ...`. Every contract that is not proved says
    why in `unproved`.
  - **What a proof is about:** the JDK's bytecode, which HotSpot may run as an intrinsic with the same meaning, with
    the JDK's classes taken as initialized, as in every proof the own checker makes.
  - Acceptance, inline:
    - `a_contract_closes_its_gap_and_the_verdict_rests_on_it` (integration.rs):
      - `bits`'s contract for `Integer.numberOfLeadingZeros` is now proved, on native and auto: basis `proved`, with
        the `proof` record in the JSON.
      - **A contract that is wrong only at `i = 777777`**, which neither the boundary values nor the 256 random
        inputs reach, is found by the proof. The JVM then refutes it there: "on i=777777 the JVM's call returns 12".
        Before this step it was tested.
      - `roll`'s contracts (a constructor and an instance method) stay tested, each with its `unproved` reason.
    - The unit test `a_contract_is_proved_against_the_jdk_bytecode_with_the_exception_class_exact`
      (gap_contracts.rs):
      - `Integer.divideUnsigned` with `throws: ArithmeticException when b == 0` is proved.
      - With `RuntimeException` in that clause it is refuted at `b=0`, a superclass not being the class thrown.
      - `result != 7` for `numberOfLeadingZeros` is refuted on an `i` in [2^24, 2^25).
      - An instance method is unproved, with its reason.
    - `ContractsTest` (test_build.py) checks the label `(1 proved, 1 tested)`, the page's words and the schema
      (`proof`, `unproved`, `proved`). The conformance corpus is unchanged: its contracts are all for constructors,
      `Random` or initializers, so they stay tested. All Rust tests and the 152 Python tests pass.
  - Re-rendering every page changed none, and no job was needed.
  - **This departs from the brief in two ways.**
    - `Arrays.fill` is not proved. A proof covers arrays only up to its bound (8), while the call it is applied at
      may be given a longer array (the engine makes constant-size arrays of up to 65536 elements), so a contract
      over arrays stays tested. Making the contract apply only up to the proof's bound would close the gap for
      fewer calls, so it is left undone.
    - **Still no recorded example: the fifth step to defer it.** 3e's acceptance asks for exactly the example 3c
      needs: one proof that closes only through agent-written contracts, one proved and one tested, with the page
      showing both levels. One example, recorded once with both levels, serves both steps better than a 3c example
      now and a 3e example later.
  - Not done:
    - A proof is run again on every run (milliseconds for these, but up to 30 s each); 3d's library checks a
      contract once.
    - Instance methods and constructors are not proved.
    - A witness that goes through a contract is still not run on a JVM.
  - Next: the recorded example, before 3d. A property proof under `--gaps advised`, on an app kernel, whose
    contracts an agent writes:
    - one for `Integer.numberOfLeadingZeros`, proved (for example, a capacity rounded up to a power of two);
    - one for `new ArrayList<>(n)` or `Random.nextInt`, tested;
    - and a wrong one the JVM refutes, shown in the advice.

    It runs through the pipeline (`approach.gaps: advised`, `approach.contracts`), and its page shows both levels.
    Tag: `advised-contracts`. Then 3d (the contract library and `--max-trust`) and 3e (the skill's loop).
- **The recorded example of 3c and 3e: 147 and 148 (2026-11-06).**
  - **The kernel.** Crosscut gains `retry.Jitter#fullJitterMillis`, full jitter: `new Random(requestId * 31 +
    attempt).nextInt(ceiling)`, where the ceiling is the base shifted by the attempt, the shift stopped at
    `Integer.numberOfLeadingZeros(base) - 1`, then capped. The module's properties file gains: the result is in [0,
    cap), and an invalid policy throws `IllegalArgumentException`. It comes with four tests, which pass.
  - The proof reaches three gaps, and closes only through contracts: `jdk-static-method` for `numberOfLeadingZeros`,
    and `jdk-constructor` and `jdk-primitive-method` for `Random`. The contracts are in each example's
    `gaps.contracts`, written by this session (an agent) from the template and the JDK's documentation, and marked so.
  - **Two examples, both B11, both `--engine native --gaps advised`.**
    - **147, expected `unverifiable`:** the agent's first contract for `nextInt` leaves out the exception, which is
      true at this call site. The JVM refutes it at `bound=0` (84 of 166 inputs). It is refused, its gap stays open,
      and the run stops before solving, with the counterexamples in the advice. The other two contracts are
      accepted.
    - **148, expected `verified`:** the contract with `throws: IllegalArgumentException when bound <= 0` added.
      `relying on 3 contracts ..., 1 proved, 2 tested`. The `numberOfLeadingZeros` contract states where the highest
      one bit is, and is proved against `java.lang.Integer`'s bytecode (18 paths). The two `Random` contracts are
      tested.
  - Checked inline on the patched module with the library's own run (0.2 s each). The recorded results are pipeline
    jobs `20261106-053555-example-147-b11-advised-contracts-a-cont` and
    `20261106-053555-example-148-b11-advised-contracts-full-j`.
  - **A fix in `build.py`:** the contracts file was not part of the claim, so changing a contract left a recorded
    result current. `contracts_digest()` puts its SHA-256 among the claim's inputs under `--gaps advised`, and
    `claim_changes` reports `the contracts for the gaps changed`. No recorded result has contracts, so no claim
    moved. A new test, `test_changed_contracts_for_the_gaps_make_the_result_stale`, covers it (153 Python tests).
  - `--contracts`'s help now says contracts are proved too. `lib/README.md` points at the tag. New technique tag
    `advised-contracts`.
  - **This departs from the brief: two examples, not one.** A run with a refuted contract stops with the gap open, so
    one recorded run cannot show both the refutation and the proof. The pair is the protocol's two runs: refuted
    then corrected.
  - **What the examples found, recorded in 148's notes:**
    - **A weaker `numberOfLeadingZeros` contract** (`0 <= result && result <= 32`) is proved just as well, but the
      property does not follow from it. Its witness goes through the contracts, and the interpreter cannot run
      `new Random`, so the run gives no verdict.
    - **The off-by-one kernel** (no `- 1`) gives no verdict for the same reason. The witness is
      `fullJitterMillis(baseMillis=99492, capMillis=100000, attempt=100000, requestId=100000)`: a negative ceiling,
      and `nextInt` throws. A real defect is no verdict, because a witness through a contract is not run on a JVM.
      That is the most useful thing still missing from the advised mode.
  - Next: 3d, the contract library and `--max-trust`.
    - An accepted contract is stored under its gap's id in `lib/models/contracts/`, with its evidence, and checked
      once rather than on every run. A different JDK version is a different id, so an upgrade re-checks it.
    - `--max-trust N` fails a run that rests on more trusted contracts than N.
    - Then 3e, the skill's loop. Running a witness found through contracts on a JVM, so that 148's off-by-one
      becomes a violation, is a candidate after them.
- **3d, the contract library and `--max-trust` (2026-11-06).**
  - **The library** ([`lib/src/contract_library.rs`](../../lib/src/contract_library.rs),
    [`lib/models/contracts/`](../../lib/models/contracts/README.md)) is built into the binary, as the models are. It
    has two parts:
    - a `.contracts` file per JDK class, in the `--contracts` format, each block under its gap's id, which names
      the JDK it was written for;
    - `checked.json`, a `Record` of each check: the contract's digest (over the gap and the keys, so comments and
      the JDK named don't change it), the JDK, the jvmcontract, and the evidence with its proof and JVM test.
  - **What it holds.** Ten contracts, written by this session from the JDK's documentation:
    - proved: `Integer.numberOfLeadingZeros`, `Integer.numberOfTrailingZeros`, `Long.numberOfLeadingZeros`;
    - tested: the capacity constructors of `ArrayList`, `HashMap`, `HashSet` and `StringBuilder`, and
      `Random(long)`, `nextInt(int)` and `nextBytes(byte[])`.
  - **How a run uses it.** Under `--gaps advised`, the driver scans the harness first. A gap it reaches that the
    agent's `--contracts` has no contract for takes the library's.
    - The agent's contract comes first, even when refused, so a wrong one goes back to the agent rather than being
      replaced (147 is unchanged).
    - A library contract whose record holds (the same digest, the same JDK, and for a proof the same class file in
      the JDK image) is applied with the record's evidence. No proof or JVM test runs for it, and its `contract:`
      line ends `checked once, on JDK 25.0.4.1 by jvmcontract 0.1.0, and recorded in the contract library, not
      checked again by this run` (`recorded` in the JSON).
    - A contract with no record that holds, as after a JDK upgrade, is checked by the run, with a `note:`. One
      written for another JDK is checked under the run's id. That is how a JDK upgrade re-checks it.
    - `--no-contract-library` turns it off.
  - **`jvmcontract gap-contracts [--dir DIR] [--record] [--json]`** checks every contract of a library on this
    JDK, either the built-in one or a directory's. It exits 1 when a contract is refused or has no record that holds.
    `--record` writes `DIR/checked.json`, keeping the records of other JDKs for contracts still in the library. That
    is the "checked once": the records in the commit come from it.
  - **`--max-trust N`.** When more than N of the contracts for the gaps reached are trusted, each of them is
    refused before solving, and its gap goes back to the agent through the advice: `it is trusted: nothing has
    checked it, since ...; the proof would rest on 1 trusted contract, and --max-trust 0 allows none`. Refusing
    them, rather than failing the run in some other way, reuses the protocol, so the agent sees which contracts are
    trusted and why. `build.py` passes it from `approach.maxTrust`, which is in the schema. Like the gap mode, it is
    an attempt option, not part of the claim.
  - Acceptance, inline:
    - `the_contract_library_closes_gaps_on_its_records_and_max_trust_refuses_trusted_contracts` (integration.rs),
      on native and auto:
      - the review's `capacity`: a violation `capacity(n=-1)` with no contracts file, then Verified with the throws
        clause, with no `contract-tests` or `contract-proofs` directory;
      - `roll` on two library contracts, and `bits` proved;
      - the agent's refuted `nextInt` contract going back to the agent while the library closes the constructor;
      - `--max-trust 0` refusing the trusted `append(String)` contract with nothing solved, and `--max-trust 1`
        accepting it;
      - a regression proof on the library;
      - the library off;
      - `contract_library::check` and the CLI on the built-in library: nothing refused, and every record holds on
        JDK 25.0.4.1.
    - The conformance corpus has a fifth column, advised with the library alone. It decides the same five claims as
      the corpus's own contracts (the four capacity constructors are violations the JVM reproduces, and `firstByte`
      is no verdict), on records, with no JVM test. The test fails if a library contract is checked again. The
      protocol columns now pass `contract_library = false`, as do 3a–3c's integration tests.
    - Unit tests: the built-in `FILES` list is every file in the directory, each contract is in its class's file and
      names its JDK; a digest ignores comments and the JDK; a record fails on a changed contract, another JDK, or
      another class file; a library contract moves to an upgraded JDK's id with no record.
    - `ContractsTest` (test_build.py) covers the page's words for a library contract and the schema's `recorded`.
      `--max-trust` is in `proof_options`. 154 Python tests in all.
  - **The recorded example: 149**, 148's kernel with no contracts file, `approach.maxTrust: 0`. It is expected
    `verified`, `relying on 3 contracts ..., 1 proved, 2 tested`, all three the library's on their records. Checked
    inline on the patched module (0.08 s, against about 0.2 s for 148, which checks its contracts). The job is
    `20261106-061323-example-149-b11-contract-library-full-ji`.
  - Re-rendering every page changed none: no recorded result has contracts yet.
  - **3e's acceptance example already exists.** "An example whose proof closes only through agent-written contracts,
    one proved and one tested" is 148 (pending), so 3e is the skill alone.
  - Not done:
    - A run uses only the built-in library. `gap-contracts --dir` checks a project's own, but nothing applies it in
      a proof (no `--contract-library DIR`).
    - The library is part of the tool, like `lib/models`, so it is not among an example's claim inputs. A changed
      library contract changes a verdict without the claim going stale.
    - `--max-trust` is not in the statement, so the page doesn't say the policy a verdict was held to.
    - A record names `jvmcontract 0.1.0`, which a change to the checker or the JVM test does not bump. A record is
      not invalidated when the code that made it changes; `gap-contracts` in CI would catch a different result only
      as a refusal.
    - The upgrade path is unit-tested only. No other JDK is installed here.
  - Next: 3e, the skill's loop. The `verify-bytecode` skill passes `--gaps advised --max-trust 0`, reads the
    advice, writes contracts, runs again, reports the evidence levels, and offers a contract worth keeping to the
    library (`gap-contracts --record`). After it, the candidate: run a witness found through contracts on a JVM, so
    that 148's off-by-one becomes a violation.
- **3e, the agent's side: the skill's loop (2026-11-06).**
  - The `verify-bytecode` skill ([`SKILL.md`](../../plugins/jvmcontract/skills/verify-bytecode/SKILL.md)) runs
    every regression and property proof with `$GAPS`, which is `--engine auto --gaps advised --max-trust 0`
    (open questions 6 and 7).
  - **A new step, 4a, "Close the gaps with contracts".** A proof that ends `gaps-need-contracts` has decided
    nothing. The agent:
    - copies the template's blocks into one `$WORK/gaps.contracts` for the whole pull request (checked: a block for
      a gap that a proof does not reach is ignored);
    - fills each block in from the JDK's Javadoc, and `javap -c` when the Javadoc is silent. It states every
      exception of the call, not only the ones this call site reaches, and never writes a contract to make a proof
      pass;
    - runs again with `--contracts`. It corrects a contract the JVM refutes from the counterexamples, and never
      weakens the property;
    - stops after three rounds on one gap, or at once on a trusted contract under `--max-trust 0`, and reports the
      gap as open.
  - A violation that goes through contracts and that the tool could not replay is reported as unconfirmed.
  - **The report** ([`report-template.md`](../../plugins/jvmcontract/skills/verify-bytecode/report-template.md))
    gains a section, "Contracts for JDK calls". It gives each contract with its level (proved, tested or trusted),
    the contracts refuted on the way and how they were corrected, and the gaps left open. A table row shows
    `relying on 3 contracts for JDK calls: 1 proved, 2 tested`.
  - **Offering contracts to the library.** A contract the agent wrote that was proved or tested, and that the
    library lacks, goes into `$WORK/library/<class>.contracts`. It is checked with `gap-contracts --dir ... --record`,
    and the report offers it for `lib/models/contracts/` by a pull request, which the skill never opens itself.
  - [`reference.md`](../../plugins/jvmcontract/skills/verify-bytecode/reference.md) gains:
    - `--max-trust`, `--no-contract-library` and `gap-contracts`;
    - the library's contents, and the precedence of the agent's contracts;
    - that `prove --json` is a list.
  - The plugin README's step 4 describes the loop. JBMC is now needed only for what the own checker hands on. The
    plugin and marketplace versions go to 0.3.0.
  - **Checked by running the loop as the skill writes it**, on 148's kernel (`Jitter#fullJitterMillis`, compiled
    alone), with the skill's commands:
    - Under `$GAPS --no-contract-library` the run asks for three contracts, with nothing solved.
    - An agent's `nextInt` contract with no exception is refused at `bound=0` (84 of 166 inputs), and its gap goes
      back with the counterexamples in the advice.
    - Corrected, the proof is `relying on 3 contracts ..., 1 proved, 2 tested` (0.2 s).
    - With the library on and no file, it gives the same verdict on records.
    - A `BitSet(int)` contract offered in a project directory: `gap-contracts --dir` exits 1 with no record, 0
      after `--record`, and 0 again on its record.
    - With no JBMC, a floating-point proof under auto ends `jbmc is not installed`, as the preflight now says.
  - **A new test, [`lib/tests/skill.rs`](../../lib/tests/skill.rs).** Every `jvmcontract` command that the skill's
    files name in code, and every option on it, including `$GAPS` on both proof commands, must be one the CLI's
    `--help` lists. It checks 57 options. A misspelt `--max-trust` in `$GAPS`, or `--work`, fails it. All Rust tests
    pass.
  - 3e's acceptance example is 148 (pending job `20261106-053555-example-148-...`), as 3d recorded. No page changed,
    and no job was needed.
  - **Phase 3 meets its Done-when criterion**, once the 147–149 jobs come back:
    - an agent closes a gap with a contract the tool proves or tests;
    - a wrong contract is rejected with a counterexample;
    - accepted contracts are reused from the library;
    - 147–149 show it end to end.
  - Not done:
    - The skill cannot keep a project's own library across pull requests: there is still no `--contract-library DIR`.
    - The landing page at terminalvalue.net still describes the JBMC-only skill. Deploying it is the user's call.
  - Next: run a witness found through contracts on a JVM. An input the interpreter cannot replay (148's off-by-one,
    `nextInt` given a negative ceiling) would then become a violation when the JVM reproduces it, and stays no
    verdict when it doesn't. That is the advised mode's last open hole. Then Phase 4, starting with 4a's stages and
    deadline.
- **After 3e: a witness through contracts is run on a JVM (2026-11-06).**
  - **When it applies.** The own checker found a witness through a contract, and the interpreter cannot run it
    (for example `new Random(seed)`). Both drivers then run it on a real JVM, the JDK the gap ids name
    ([`lib/src/jvm_witness.rs`](../../lib/src/jvm_witness.rs)).
  - **How it runs.** A generated class, `WitnessRun`, calls the proved harness's `check` on the witness, with the
    JDK's real calls where the contracts stood. Then it calls the method alone on fresh copies of the arguments,
    to get the outcome to report. For a regression proof it calls each version alone, when both are static methods
    of the harness's parameters. The harness runs first, so it sees the classes uninitialized.
  - **The harness fails there.** The witness is a violation. Its proof line reads `run on a JVM (JDK 25.0.4.1)
    with the JDK's own calls where the contracts stood`, and `replay.by` is `jvm`. The witness is not shrunk,
    since the interpreter is the shrinker's oracle.
  - **The harness holds.** The witness is no verdict: `... does not reproduce on a JVM (JDK ...): the method
    returns 7 there and the property holds on it`. If no JVM can run it, the earlier reason stands, with why.
  - **148's off-by-one is now a violation** (checked inline, 0.2 s):
    `fullJitterMillis(baseMillis=99492, capMillis=100000, attempt=100000, requestId=100000)` throws
    `IllegalArgumentException("bound must be positive")` on the JVM. 148's weaker `numberOfLeadingZeros`
    contract stays no verdict, since the JVM returns 18 there and the property holds. 148's notes say both.
  - **Found on the way: under a range contract, a regression proof's witness is almost never real.** Each
    version's call takes its own value under a contract, so two calls the versions make alike can differ in the
    proof. Two identical `new Random(7).nextInt(sides)` give `roll(sides=20)` as a witness, and the JVM gives both
    16. The message says so.
    - A guard moved from `> 30` to `> 31` gave the spurious `shift=20`, not the real `shift=31`, so the JVM run
      reports no verdict.
    - The fix would treat a JDK call with a contract as one function in both versions, as shared callees do. For
      a receiver like `Random` that is only sound with its state taken into account, so it is left for later.
  - Acceptance, inline:
    - `a_witness_through_contracts_is_run_on_a_jvm` (integration.rs), on the library's contracts, on native and
      auto:
      - `jitter(shift=31)` is a violation with the JVM's exception;
      - `roll(sides=10)` (the property fails only where `nextInt(10)` is 2; Random(7) gives 6) is no verdict;
      - `firstByte` is a violation, leaving `out=[115]`;
      - a regression whose new version calls `nextInt(1 << shift)` is a violation, before `0` and after the
        exception, both versions run alone on the JVM;
      - two versions that call `nextInt` alike are no verdict, with the regression hint.
    - `a_contract_closes_its_gap_and_the_verdict_rests_on_it` changes with it: `firstByte` is a violation, and
      `roll-violated` has `replay.by` `jvm`.
    - **The conformance corpus's two contract columns now decide `firstByte` as a violation.** 3b–3d gave it no
      verdict. Its own JVM runner reproduces the witness, independently of the tool's.
    - All Rust tests and the 154 Python tests pass.
  - `build.py` and the schema already had `replay.by: "jvm"` (from the Box Office verifier). The schema's text now
    names this use. The skill reports such a witness as the code's, and one the JVM does not reproduce as open.
    No recorded result changes, since none ran under `--gaps advised` yet (147–149 are pending). No job was
    needed.
  - Not done:
    - The witness of a disagreement under `--confirm` (1e) is still left for a person to run on a JVM. The same
      runner could settle it.
    - A witness the JVM does not reproduce is not followed by a search for another one.
    - An instance-method or record regression's versions are not run alone, so their outcomes read
      `<not run alone on the JVM, ...>`.
  - Next: Phase 4, starting with 4a. Run JBMC's interval stages only where they can change the domain, and give
    every check one deadline. Acceptance: 142's harness runs once.
- **4a, stages only where they change the domain, and one deadline (2026-11-06).**
  - **Stages** ([`lib/src/deadline.rs`](../../lib/src/deadline.rs)). `stages_for` reads the parameters of the
    harness's entry method from its class file. It keeps a preliminary stage (`[0:20]`, `[-100000:100000]`) only
    where the stage's interval leaves out some value of a primitive parameter. `--java-assume-inputs-interval` does
    not bound array elements, so:
    - a harness over arrays alone runs once, as 142's `(char[] chars, byte[] out)` now does;
    - one over bytes, chars or shorts skips the second stage;
    - one over booleans alone runs once;
    - one with an `int`, a `long` or a floating-point input runs all three.

    Both drivers use it. `equivalence::STAGES` is now a re-export.
  - **One deadline per check.** The check is the own checker's run, JBMC's stages, JBMC's fallback under auto, the
    runs with shared callees and as written, and the vacuity probe. It gets `--timeout` once, as a `Deadline`, where
    each of those runs used to get all of it. The budgets:
    - each preliminary stage gets at most an eighth of the check (`STAGE_SHARE`);
    - the own checker under `--engine auto` gets all but a quarter, which is kept for JBMC's fallback
      (`FALLBACK_SHARE`);
    - under `native`, the own checker gets everything that is left, and so do JBMC's last stage and the probe.

    JBMC's rerun with its default solver, when the solver asked for is missing, now takes what is left of the run's
    budget, not a second one.
  - **A preliminary stage that runs out of its budget hands on to the next.** Before, the first stage to time out
    ended the check with no verdict, though only the last stage is the proof. Any other no-verdict still ends the
    search. `JbmcResult::out_of_time` tells the two apart. It reads the problem text, which 4b's structured outcome
    should replace.
  - **`--confirm` is a second check, by a second checker, with a deadline of its own.** The brief does not say
    either way. Giving it what was left would leave it nothing after most own-checker proofs.
  - **The result shows where the time went.** `search.deadline_seconds` holds the deadline. `search.runs` lists
    every run in order, each with:
    - the checker;
    - its purpose (`proof`, `fallback`, `shared`, `as-written` or `probe`);
    - its interval;
    - its budget and seconds;
    - how it ended (`verified`, `violation`, `no-verdict` or `out-of-time`).

    `build.py` keeps them as `search.deadlineSeconds` and `search.runs`, which are in the schema. The `--timeout`
    help, the README's step 4 and `search` text, and the skill's budget line say the deadline is per check.
  - Acceptance, inline:
    - `jbmc_runs_only_the_stages_that_change_the_domain_within_one_deadline` (conformance.rs) uses a stand-in JBMC
      that logs each run, and can hang on the interval stages or on every run. It checks:
      - `length(int[])` runs once, as a property and as a regression;
      - `byteSum(byte, byte)` runs `[0:20]`, then the proof;
      - `increment(int)` runs all three, with budgets of at most 75 s, 75 s and the rest of 600;
      - with the stages hanging, a 16 s check hands on twice and is verified in under 8 s (before, it ended with no
        verdict at 16 s);
      - with every run hanging, a 4 s check ends in under 6 s with three `out-of-time` runs whose budgets add up to
        4 s;
      - under auto, the own checker's budget is 75 of 100 s, and its probe is recorded.
    - Unit tests in `deadline.rs` cover the stage rule and the budgets. `DeadlineTest` (test_build.py) covers the
      record and the schema. All Rust tests and the 155 Python tests pass.
  - **142 on the real JBMC is a pipeline job**, `20261106-071536-example-142-s-regression-harness-under-j`. It
    compiles Mica before and after 142's patch and runs `equivalence --engine jbmc --timeout 300`. It checks for one
    JBMC run over every input that ends within the deadline. Its steps were dry-run here with a stand-in JBMC. 142's
    recorded result is the own checker's and does not change, and no page changed.
  - Not done:
    - A stage the scope fixes, such as `x == 3`, is still run. Only the parameter types decide.
    - The own checker's internal witness search ([`bmc::STAGES`](../../lib/src/bmc/mod.rs)) is within its single
      run, so it was left as it was.
    - The JVM witness run, shrinking, and contract proofs and tests keep their own limits (60 s, the interpreter's
      steps, 30 s per contract). Contract checking happens inside the deadline's time, since the check starts
      before the contracts are applied.
  - Next: 4b, reading JBMC through `--json-ui`, with the text parser kept until a differential test over the
    recorded JBMC examples shows the two agree. Unsupported input, unwinding failure, timeout, memory exhaustion,
    solver failure and counterexample stay distinct, which also replaces `out_of_time`'s text match.
- **4b, JBMC read through `--json-ui` (2026-11-06).**
  - **The format is CBMC 6.11.0's own**, read from its source (`report_util.cpp`, `json_goto_trace.cpp`,
    `json_expr.cpp`, `ui_message.cpp` at tag `cbmc-6.11.0`), since JBMC is not run inline to find it out. It is one
    JSON array holding:
    - the `program`;
    - messages (`messageType`, `messageText`);
    - a `result` with every property's `status`, and a `trace` for each failed one;
    - the overall `cProverStatus` (`success`, `failure`, `inconclusive` or `error`).

    There is no `** N of M failed` line in this mode. A run that is killed leaves the array unclosed.
  - **The reader** ([`jbmc::parse_json`](../../lib/src/jbmc.rs)) is now the default.
    - It reads the array element by element, up to the first that does not parse, so a cut-off run and text around
      the array (the solver note, the timeout line) do no harm.
    - A counterexample's inputs come from the trace's `input` steps, by slot.
    - An array's elements come from the `length`, `data` and element assignments before its input step, as in the
      text.
    - **A value is read from its bits** (`binary` with its width), not from how Java prints it. An integer is
      signed unless its type is `char` or `boolean` (JBMC writes `const long`). A float is IEEE 754 at width 32 or
      64.
    - Only `success`, with every property `SUCCESS` or `UNREACHABLE`, is a proof.
  - **How a run ended is data:** `Ending` on every result, and `search.runs[].ending`. The values are `verified`,
    `counterexample`, `unwinding-failure`, `other-failure`, `timeout`, `memory-exhausted`, `killed`,
    `solver-failure`, `unsupported-input` (a class path entry JBMC could not read, or an `ERROR` message before any
    result), `unavailable`, `unreadable`, and the own checker's `no-verdict`.
    - `out_of_time` reads the ending now, not the problem text.
    - The text parser gives the same endings, except that it cannot tell an error before any result from output it
      cannot read.
  - **The text parser is kept**, as `JVMCONTRACT_JBMC_READ=text`. `both` runs JBMC both ways and decides by the
    JSON. It writes what each reading made of the run (verdict, ending, property count, and the counterexample in
    one canonical form) to `<log>.differential.json`, and appends it to the file `JVMCONTRACT_JBMC_DIFFERENTIAL`
    names. Under `both` the second run gets a budget of its own, so it is a test mode.
  - Acceptance, inline:
    - **On the real JBMC 6.11.0.** The integration suite's JBMC cases (151 runs of the real JBMC, 107 `success`
      and 38 `failure`) now go through the JSON reader. Every witness among them is replayed by the interpreter,
      which checks the inputs read: longs, ints, `int[]`, records, and stages.
    - A new test, `the_json_and_the_text_reading_of_jbmc_agree`, runs the CLI under `both` on four claims (six
      runs): a proof, a counterexample over an `int[]` and an `int`, one over a `long`, and an unwinding failure.
      Every pair of readings agrees.
    - Unit tests in `jbmc.rs` cover every ending from fixtures in CBMC's shape: arrays of `byte` and `char` and a
      `null` one, a store after the input, `1.5f` and a double NaN from their bits, a cut-off array, a note before
      it, the class path warning and an error before any result. They also cover the canonical forms, and `both` on
      a stand-in that agrees and one that does not.
    - The conformance stand-ins answer in JSON when asked for it, in text otherwise. `DeadlineTest` checks
      `ending` in the record and the schema (156 Python tests). All Rust tests pass.
  - **The differential test over every recorded JBMC example is a pipeline job**:
    `20261106-073804-jbmc-read-through-json-ui-agrees-with-th`. It runs `build.py` on a copy of `examples/` over the
    41 B9/B11 examples JBMC proves on the javac apps, under `both`. It fails on any disagreement, and on any verdict
    that differs from its expected one. Its summary step was dry-run on the inline test's records. **The text parser
    goes once it passes.** The pending JBMC jobs (the corpus under JBMC and auto-confirm, 127, and 142 on JBMC) now
    run under the JSON reader too.
  - Re-rendering every page changed none. `lib/README.md` and the skill's `reference.md` say how JBMC is read.
  - Not done:
    - The console report and the page don't show the ending; `--json` and the result's `search.runs` do.
    - JBMC's solver version is still not recorded.
  - Seen for 4c: JBMC's JSON names each stub class in a message, `stub class symbol java::... already exists`. That
    could be the preflight's starting point.
  - Next: 4c. Make JBMC's own approximations gaps in the three modes: stubbed missing bodies, and the zero/null
    fallback for an unresolved `invokedynamic`. Acceptance: 1b's reproducers give the same answer under JBMC in each
    mode. After it, the text parser's removal once job `-073804` agrees, then Phase 5.
- **4c, first part: JBMC's own approximations are gaps under strict and assume (2026-11-06).**
  - **The preflight** ([`lib/src/jbmc_gaps.rs`](../../lib/src/jbmc_gaps.rs)). Before JBMC's stages, the tool runs
    JBMC with `--show-goto-functions` on the harness, with the proof's class path and options. This converts what
    the proof would and solves nothing: 40 ms on 1b's reproducers. It gets an eighth of the deadline, at most 60 s,
    and writes `jbmc-goto.txt`.
    - The goto program is JBMC's own account of what it runs, virtual dispatch included. The tool walks its call
      graph (`CALL` lines) from the harness's entry.
    - Every function reached is looked up on JBMC's class path. Read from CBMC 6.11.0's `lambda_synthesis.cpp` and
      `java_bytecode_parser.cpp`, and seen in its listings, JBMC approximates three things:
      - **A stub** for a method with no bytecode: a constructor constructs the object and nothing else, a `void`
        method does nothing, and any other method returns any value (`null` or a new object for an object).
        None throws or changes anything.
      - **The zero fallback** for an `invokedynamic` that it links to no class of its own making. JBMC never
        checks the bootstrap method's name: it accepts an entry of the metafactory's shape whose interface is on
        its class path with one abstract method. So string concatenation is `null` there, a record's
        `equals`/`hashCode`/`toString` are `false`/`0`/`null`, and so is a lambda for `java.util.function.Function`.
        A call site counts as linked when its `bytecode-index` has a `lambda_synthetic_class$` instruction.
      - **Monitors, which JBMC drops.** It models them only under `--java-threading`, so `synchronized (null)`
        throws nothing. The brief did not name this one.
  - **Kinds and ids.** A JDK stub keeps the own checker's kind and id
    (`jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-...`), so a gap reads the same whichever checker meets it.
    Three kinds are new, met by JBMC only: `missing-body` (a stub outside the JDK), `invokedynamic`
    (`invokedynamic:<bootstrap>:<site name><descriptor>`) and `monitor` (per method). Each `GapRecord` now has
    `checker: "jbmc"`, with JBMC's approximation in words.
  - **Not gaps:**
    - stubs JBMC reproduces exactly: `gaps::exact_jdk_call`, plus a JDK constructor whose bytecode only calls one
      such constructor, as `Number.<init>()` does;
    - stubs that only a JDK class's initializer reaches, such as `Class.getPrimitiveClass` from `Integer.<clinit>`.
      These fall under the statement's engine assumption for JBMC, now worded for them: JDK classes are initialized
      by their initializers as JBMC runs them, with its stubs inside.

    Without that second rule, every proof that touches `Integer` or `Math` would be refused.
  - **The modes** (`jbmc_gaps::hold`, in both drivers and in `--confirm`):
    - **Strict:** a JBMC proof that reaches a gap is no verdict: `JBMC proved it, but reaches N constructs it
      approximates ...`. So is one whose preflight could not be read. A counterexample stands only if the
      interpreter replays it, as before. The message for one that doesn't replay now names JBMC's stubs.
    - **Assume:** the verdict stands, `assuming N behaviours JBMC does not implement`, with an `assumed:` line per
      gap.
    - **Advised:** still refused under `--engine jbmc`, with a new reason: JBMC applies no contract.
    - **`--confirm`:** JBMC's proof is held to its gaps under the own checker's gap mode. Under strict, a
      confirmation that reaches a stub is `no-verdict`.

    `build.py` now passes `RECORDED_GAP_MODE` (assume) to the examples JBMC proves too, since the library's strict
    default now reaches them. It keeps `checker` in `search.gaps`, and the page says whose approximation was
    assumed (`assumed_lines`). The schema has the new kinds and `checker`.
  - Acceptance, inline, on the real JBMC 6.11.0: `jbmc_own_approximations_are_gaps_in_the_same_modes`
    (integration.rs). Each claim is first checked on a JVM.
    - `capacity` (`new ArrayList<>(n)`) and `firstByte` (`Random.nextBytes` on an argument array): JBMC alone proves
      both claims the JVM refutes. Under strict they are now refused by name, with the own checker's ids. Under
      assume they are `Verified, assuming ...`.
    - **`nullMonitor` (`synchronized (null)`): JBMC proves `result == 1`** where the JVM and the own checker throw
      NPE. It is now a `monitor` gap under strict, and `Verified` naming it under assume.
    - `concatIsNull` and `sameRecord` (a record's `equals`): JBMC proves `result` and `!result` on its zero value.
      Both are now refused as `invokedynamic` gaps.
    - `bits` (`Integer`'s own bytecode, whose initializer reaches a stub) is still `Verified`, with no gap.
    - A regression proof that adds `new ArrayList<>(n)`, under `--engine jbmc`, is refused under strict and
      verified under assume.
    - Unit tests in `jbmc_gaps.rs` cover the goto reader and the classification. The conformance stand-ins answer
      the preflight. All Rust tests pass (138 unit, 5 conformance, 59 integration, 1 skill), and so do the 157
      Python tests, one of them new (`test_a_jbmc_proof_names_the_stubs_it_assumed`).
    - All 58 existing integration tests, 151 runs of the real JBMC among them, pass unchanged under the new strict
      default: none of them reaches a JBMC gap with a `Verified`.
  - **This departs from the brief's acceptance in two ways.**
    - **"The same answer under JBMC in each mode" is not reachable for `synchronized (null)`.** The own checker
      gives the violation, while JBMC gives a named gap, because it drops the instruction. That is 1b's
      acceptance, "a named gap (or a correct violation) ... never `Verified`", not the same answer.
    - **Advised** gives the same answer only through the own checker: `--engine auto` runs the protocol, and
      `--engine jbmc --gaps advised` is refused. JBMC applying a contract is 4c's second part.
  - **The recorded examples: job `20261106-082917-jbmc-s-own-approximations-as-gaps-every`.** It runs `build.py` on a
    copy of the 41 JBMC examples under assume, where no verdict should move. It tabulates the JBMC gaps each
    reaches, and how many recorded proofs strict would refuse, as 1a did for the own checker. Their notes get the
    result when it is back.
  - Re-rendering every page changed none. `lib/README.md`, the `--gaps` help and the skill's `reference.md` describe
    JBMC's gaps.
  - Not done:
    - The preflight's time is not in `search.runs`. It is outside the proof's runs, though it is in the check's
      deadline.
    - A stub reached only on a path no input takes is still a gap, since the call graph is static.
    - `--java-threading` is not used, so monitors stay a gap.
  - Next: 4c's second part. JBMC applies a contract where the harness can express it: the call sites redirected
    to a generated class of contract methods over `org.cprover.CProver` (nondeterminism, assumptions), as shared
    callees are redirected (`lib/src/shared.rs`). That makes advised work under `--engine jbmc`, and a contract it
    cannot apply leaves the gap open. Then the text parser's removal once job `-073804` agrees, then Phase 5.

- **4c, second part: JBMC applies contracts (2026-11-06).**
  - `--gaps advised` now works under `--engine jbmc`, and in JBMC's turn under `auto`
    ([`lib/src/jbmc_contracts.rs`](../../lib/src/jbmc_contracts.rs)). Both drivers no longer refuse it.
  - **The protocol is the own checker's, on JBMC's gaps.** The gaps that JBMC's preflight finds in its goto program
    are the scan.
    - A JDK-call gap with no contract stops the run before anything is solved. It returns the advice, with
      `checker: "jbmc"`, the problem `the proof reaches 1 gap of JBMC with no contract`, and a template headed for
      JBMC.
    - The contracts are read and checked exactly as for the own checker: proved, tested on a JVM or trusted, the
      library's records, `--max-trust`. A JBMC gap of a JDK call has the own checker's id, so one contract serves
      both checkers.
    - No contract closes a `monitor`, `invokedynamic` or `missing-body` gap under JBMC. The advice lists these as
      "approximated by JBMC whatever the contracts", and the proof is refused as under strict.
  - **How JBMC applies a contract: it runs the same contract method as the own checker.**
    - In the harness and the application's class directories, every call site of a closed gap is rewritten into an
      `invokestatic` of the contract's method. `shared::redirect_calls` now takes any kind of call, and turns an
      `invokeinterface` into `invokestatic` plus two `nop`s, so no offset moves.
    - A constructor's call goes through `GapContractCalls.k<N>`, which takes the still-uninitialized receiver and
      drops it.
    - The intrinsics are a class over JBMC's `org.cprover.CProver`:
      - `anyInt`/`anyLong` call `nondetInt`/`nondetLong`;
      - `infeasible` is `assume(false)`;
      - `havoc` loops over the array's elements, giving each a nondet value;
      - `open` throws an `AssertionError`, which JBMC reports as a property of its own,
        `jvmcontract.GapIntrinsics.open`. A run in which it fails is no verdict: "an input outside the `assume:` of
        the contract for ... reaches its gap".
    - Checked first on JBMC 6.11.0, with no CProver class on the class path. An assertion in a helper is its own
      property. `CProver.assume` constrains values. The goto program shows the uninitialized object cast to
      `Object` and passed on.
    - **A second preflight runs on the rewritten class path.** Whatever JBMC still approximates there is held as
      under strict.
    - **Some call sites are not rewritten, and their gaps stay open:**
      - a call whose JDK method an application class overrides, since the JVM would dispatch to the override (it
        gets a note);
      - calls made from the JDK's own bytecode;
      - classes in jars.
    - An exception a contract throws that is not among the harness's 15 has its class and superclasses taken from
      the JDK image (`property::extract_exceptions`). JBMC matches handlers by class, so without this it would not
      know the class is a `Throwable`.
  - **What a result says.**
    - Each contract applied is a gap record with treatment `contract` and `checker: "jbmc"`.
    - The verdict reads `relying on 1 contract for gaps of JBMC, 1 tested`, with a note saying how many contracts
      were applied and how many classes rewritten.
    - A witness that goes through a contract is replayed by the interpreter, or run on a JVM, exactly as before. The
      messages name JBMC.
    - `build.py` puts JBMC's name on the page (the advice paragraph and the contracts paragraph). The schema has
      `advice.checker`.
  - **Acceptance, inline, on the real JBMC 6.11.0**: `jbmc_applies_the_contracts_for_its_gaps` (integration.rs).
    - No contract: the advice is returned, with nothing solved.
    - The review's `new ArrayList<>(n)`:
      - with the contract the JVM's behaviour has, it is the violation `capacity(n=-1)`, which the interpreter
        reproduces with the JVM's message;
      - with the exception declared, it is Verified, `1 tested`, with basis `tested` in the statement;
      - "doesn't throw" is refuted by the JVM at `n = -1` and goes back to the agent;
      - `assume: capacity >= 0` meets the gap at a negative `n`.
    - `Random`:
      - `firstByte` is a violation whose witness the JVM runs (`115, leaving out=[115...`);
      - `filled` is Verified on 2 tested contracts;
      - `roll` is Verified within `nextInt`'s range;
      - a property the range does not decide gives a witness that does not reproduce on the JVM, so no verdict.
    - `StringBuilder.append` with `result == this` is Verified.
    - A method that synchronizes around the call: the advice lists the monitor as approximated by JBMC, and with the
      contract the proof is refused for the monitor.
    - Under auto, the own checker refuses a `float` comparison after the call, and JBMC's turn proves it through the
      same contract.
    - A regression proof (`new ArrayList<>(n)` added) stops with the advice without a contract, and is the
      violation with one.
    - Two older tests that expected advised to be refused under JBMC now check its advice. All Rust tests pass, and
      so do the 158 Python tests, one of them new.
  - **1b's reproducers now give the own checker's answers under JBMC in each mode.** The exception is
    `synchronized (null)`, as part one recorded. JBMC drops monitors, so no contract closes that gap, and it stays a
    named gap.
  - No recorded example runs under JBMC with `--gaps advised`, so no page changed and no job was needed. The
    `--gaps` help, `lib/README.md`, the module docs and the skill's `reference.md` say JBMC applies contracts.
  - Not done:
    - **`--confirm` still does not ask JBMC** about a proof that rests on contracts (`not-asked`). JBMC could now
      apply the same contracts there.
    - A static JDK method that the own checker reproduces exactly but JBMC stubs is refused by the contract reader,
      with the own checker's reason. None is known on the recorded examples.
    - The preflights' time is still not in `search.runs`.
  - Phase 4 is done, apart from removing the text parser, which waits for job `-073804`.
  - Next: Phase 5a, the benchmark corpus in three groups. It assembles the conformance corpus, the real regressions
    with a known bad and fixed version, and held-out performance cases, and reports correctness, supported coverage
    per gap mode, time and memory separately for both engines. The text parser goes as soon as `-073804` agrees.

- **5a, the benchmark corpus (2026-11-06).**
  - [`lib/benchmark/`](../../lib/benchmark/README.md) has three groups, 118 cases:
    - **Group 1: the conformance corpus's 93 claims.** `conformance.json` is written by a new test in
      `conformance.rs`, `the_benchmark_takes_its_first_group_from_this_corpus`. The test fails when the file is not
      the corpus, so the two cannot drift (`JVMCONTRACT_BLESS=1` writes it).
    - **Group 2: four documented bugs, 13 cases.** Each bug has its broken and fixed version as source trees
      (`src/broken`, `src/fixed`):
      - JDK-5045582, the `binarySearch` midpoint;
      - FindBugs' `RV_ABSOLUTE_VALUE_OF_HASHCODE`;
      - Java Puzzlers' "Oddity";
      - CERT NUM00-J's overflowing range check.

      For each, the broken version's property is refuted, the fixed version's is proved, and a regression proof
      shows the fix changes only the inputs it was meant to. That is the ecosystem review's §6.3 sequence. The
      whole `binarySearch` before and after its fix is a case too: the two agree on every array of up to 8
      elements, since the overflow needs more than 2^30 of them. So it is expected `verified`, a real bug outside
      the domain.
    - **Group 3: 12 held-out regressions** (`src/v1`–`src/v3`), over the workloads 5b's table is over:
      - scalar arithmetic: saturating add, the floor mean;
      - div/rem: `floorMod` three ways, `ceilDiv`;
      - binary search: a scan to a lower-bound bisection;
      - UTF-8: an encoded length with an ASCII fast path;
      - array mutation: reverse, prefix sums;
      - records: interval overlap.

      Three are violations. One was found while writing them: `((a % n) + n) % n` overflows once `n` passes 2^30.
  - **The answers come from the JVM, not the tool.**
    - [`Reference.java`](../../lib/benchmark/Reference.java) writes out each claim of groups 2 and 3 in Java, apart
      from the harness generator and the expression language, and runs each version in a class loader of its own.
    - A `violation` case names a witness, and the JVM must refute the claim on it.
    - For a `verified` case, the JVM searches boundary values and 200,000 seeded inputs. That is evidence, not proof.
    - Every witness an engine reports is run on the JVM too: group 1's through the tool's harness and the
      conformance runner, groups 2 and 3's through `Reference.java`. One the JVM does not reproduce is a false
      alarm.
    - Inline, the JVM bears out all 25 answers.
  - **The runner, [`run.py`](../../lib/benchmark/run.py).**
    - It runs each case on `native` and `jbmc` under strict, assume and advised. Advised uses the library alone, with
      `--max-trust 0`, and no agent.
    - The configurations are matched: one harness, unwind 16, arrays of up to 8, the models on both, and a 120 s
      deadline.
    - A run is `correct`, `correct-assuming` (a gap named), `unsupported` (with the reason), `false-success`
      (`-assuming` when the verdict names the gap), or `false-alarm`.
    - It keeps wall and CPU seconds and the peak memory from `wait4`, which counts JBMC and the JVM. Checked: a
      300 MB grandchild reads as 308 MB.
    - It keeps the solver's figures: the own checker's paths, solver calls, variables and clauses, and JBMC's runs.
    - It writes `results.json` and `RESULTS.md`, and exits 1 on a false success, a false alarm, or an answer the JVM
      does not bear out.
    - `test_run.py` has 14 tests. Among them: `Reference.java` lists exactly the corpus's ids, every version names
      its class, and both engines get the same command but for `--engine`.
  - **Inline, the own checker alone over groups 2 and 3** (a 20 s deadline, not the job's 120 s):
    - 24 of 25 correct in each mode, none wrong; median 0.1 s, 3.0 s at most when it decides; 73 MB at most.
    - **A held-out finding:** `real/bucket/fix-confined`, `Math.abs(hash) % b` against `(hash & 0x7fffffff) % b`
      for a non-negative hash, runs out of time. It was over 100 s before it was stopped, under the default
      deadline. The two dividends are equal only under the scope, and the lazy division does not relate two
      remainders of different terms.
    - A smoke test of the runner on JBMC (five runs) found no surprise. For `capacity`, on both engines: strict
      unsupported for the gap, assume a false success naming it, and advised correct through the library.
  - **The full run is job `20261106-094317-benchmark-corpus-step-5a-both-engines-un`**: about 700 runs, both
    engines, three modes. It writes `lib/benchmark/RESULTS.md` and `results.json`.
  - Also fixed:
    - `lib/README.md` still said advised needs `--engine native` or `auto`, which 4c's second part made untrue.
    - The `--engine` help said the own checker has no arrays.
  - **This departs from the brief in three ways.**
    - No CVE kernel. The brief welcomes them, and none was added.
    - "Properties reviewed independently of the tool" is met by stating each from its published source and holding
      it to the JVM in `Reference.java`. No person reviewed them.
    - Group 3 is held out from the optimizations' development, not from their author: this session wrote both. It
      is recorded as first written, whatever an engine makes of it.
  - Not done:
    - `--engine auto` and `--confirm` are not in the matrix.
    - Each configuration runs once, so the times carry the machine's noise.
    - The per-phase split is 5b's.
  - Next: 5b, the per-phase measurements, on this corpus and on the recorded examples 5b names (binary search
    141, UTF-8 142).
    - The own checker extends `bmc::Stats` with its phases: decoding, symbolic execution, encoding, solving,
      extracting the witness, shrinking, and checking contracts. JBMC's `--verbosity` timings and its program and
      formula sizes are read from its log.
    - `run.py` carries both into the results.
    - A table per workload says which phase dominates on each engine, and goes into `jbmc-patch-queue.md`.
    - The text parser goes once `-073804` agrees.

- **5b, per-phase measurements (2026-11-06).**
  - **The phases** ([`lib/src/phases.rs`](../../lib/src/phases.rs)). Every checker run has a `Profile`, the same for
    both engines. Its seconds are split into `loading`, `lowering`, `symbolic`, `encoding`, `solving`, `trace` and
    `other`. Its `formula` gives JBMC's SSA steps and verification conditions, and the variables and clauses. It is
    recorded on each of `search.runs` as `phases` and `formula`.
    - **The own checker** extends `bmc::Stats` with `loading_seconds` (`ClassPath` times its loads),
      `decoding_seconds` (`Engine::code`), `encoding_seconds` (the `Blaster`'s word-level operations) and
      `witness_seconds` (`staged_input`, less its solving and encoding). Symbolic execution is what the others leave
      of the run.
    - **JBMC** runs under `--json-ui --timestamp monotonic`. Its `Runtime Symex`, `Convert SSA`, `Post-process` and
      `Solver` lines give the phases it times. The times of its messages give loading (to `Generating GOTO
      Program`), lowering (to `Starting Bounded Model Checking`) and the trace. Checked on JBMC 6.11.0 first: the
      flag adds a `timestamp` to every message. **A run cut off by its deadline or its memory gives the rest of its
      time to the phase it was in**, so a JBMC timeout says where its time went.
    - **The drivers time their own steps** (`search.phases`): setup (the JDK's classes and the models), harness,
      gaps (the advised scan and JBMC's preflights), contracts, replay and shrinking, the JVM witness run, and the
      rest. The timers sit in the called functions, so neither driver's control flow changed.
  - **A measurement found on the way: a clock read costs about 0.3 µs on this WSL2 ARM machine** (574 ns per timed
    region, measured). Timing each word-level operation cost as much as the encoding it measured: example 142 went
    from 7.14 to 7.38 s, against 0.24 s of encoding. The own checker now times one operation in 64, picked by a
    xorshift so the sample does not follow the order operations come in. It scales the sample up, after taking off
    the clock's own cost, which is measured when the `Blaster` is made. On 142, encoding reads 0.17–0.21 s and
    symbolic execution 0.06–0.08 s; solving is 95% either way. The other timers are cheap (1,885 solver calls on 142).
  - **The runner** ([`lib/benchmark/run.py`](../../lib/benchmark/run.py)).
    - Each run record gets `phases`: the checker runs' phases summed, JBMC's start and output as `checker-other`,
      the driver's steps, and `driver` for the rest of the process. It also gets the largest `formula`.
    - `RESULTS.md` gains **"Where the time goes, by workload, under strict"**: a row per workload and engine over
      every run, decided or not, with each phase's share, the dominant phase and the largest formula.
    - **Group 4, the recorded examples 5b names**: 141 (binary search) and 142 (UTF-8). Their claims are read from
      their `example.json`, their patches are applied to a copy of Mica, and they run under strict alone. Their
      expected answer is the recorded one, so neither the JVM's search nor the witness check covers them, and they
      have a table of their own.
    - `test_run.py` has 17 tests.
  - **Inline, the own checker over groups 2–4** (a 20 s deadline): correct on every case but
    `real/bucket/fix-confined`, out of time as in 5a. Solving dominates every workload whose runs take more than a
    fraction of a second: 96% for div-rem, 86% for binary search, 89% for 141 (2.0 s) and 92% for 142 (7.3 s). On
    the short cases, the driver's fixed cost of about 50–70 ms dominates.
  - **A JBMC smoke run of the four midpoint cases.** On the bounded `binarySearch` (`search-within-bound`), JBMC takes
    45 s, 94% of it solving 3.28 million clauses; the own checker takes 3.1 s, 88% solving 240,000 clauses. On the
    small cases, JBMC's start and output are about a fifth of a check, and its preflight another fifth. That run
    reached 1.4 GB inline, past CLAUDE.md's 1 GB for inline work; nothing else on JBMC was run inline.
  - **The table goes into [`jbmc-patch-queue.md`](jbmc-patch-queue.md)**, which gains a section "Evidence: where each
    engine's time goes". It maps each candidate patch to the phase it would shrink, and the workloads where that
    phase must dominate for the patch to pay. It also has the first inline figures. Those already point at the
    formula's size (the array-representation candidate) rather than arithmetic, for binary search.
  - **The full run is job `20261106-102624-benchmark-corpus-with-per-phase-measurem`**: the 5a run plus group 4,
    with the phases. It **supersedes `-094317`**, which runs the same cases at the 5a revision without them.
  - The schema has `phases` and `formula` on each run, and the native stats' new fields: `build.py` keeps them, and
    `DeadlineTest` checks it. 159 Python tests in all. All 140 recorded results still validate, and no page changed.
    `lib/README.md` describes the JSON. All Rust tests pass: 145 unit, 6 conformance, 60 integration, 1 skill.
  - **This departs from the brief in three ways.**
    - The own checker has no separate encoding pass: it builds the formula as it explores the paths and hands each
      clause to one incremental solver. So its `encoding` is the time inside the circuit builders, sampled, and its
      `symbolic` what the other phases leave.
    - Peak memory is per process (`wait4`), not per phase. Neither checker reports memory by phase.
    - **The ranking of the patch candidates waits for the job.** The table it writes is the evidence. This step
      leaves the mapping it will be read with, and the first figures.
  - Not done:
    - The console report doesn't print the phases; `--json` and the results do.
    - The driver's fixed cost of about 50 ms (reading the target and its class path, the statement, the report) is
      measured but not split further.
    - The `--confirm` run's phases are not in `search.runs`, since it is a second check.
  - Next: once job `-102624` is back, rank the patch candidates in `jbmc-patch-queue.md` from its table. Remove the
    text parser once `-073804` agrees. Those, with the pending jobs, are what is left of the brief; every phase's
    plan step is done.

## Loop settings

The session is fixed: further work on this brief resumes it.

- session: 7cacdb56-4c74-4880-a06e-f98031283c0f
- model: claude-opus-5-5
- effort: high

## Loop until

Go on while a cycle can still realize a substantial part of the reasonably attainable value of this brief. The user
prefers the loop to run as long as possible, so when in doubt, continue. Phase 1 fixes verdicts that can be wrong
today, and Phase 3 is the brief's new capability, so don't stop before both are done unless they are blocked on the
user. The JBMC patch queue is never a reason to go on. Stop when most of the rest has been realized: the
remaining steps are small or speculative next to what is done, or what is left needs the user's input (an open
question, network access, an external service) and has been recorded as deferred. Don't go on to polish, and don't
stop while a step of the plan that needs nothing from the user is still open.
