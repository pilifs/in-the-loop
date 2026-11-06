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
