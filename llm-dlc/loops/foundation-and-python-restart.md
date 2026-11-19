# Java verification restart brief

**Run the foundation work first, then the Python architecture work.** Start at the last verified checkpoint on the implementation branch. Use example 105 for the read-only history inventory, Gradebook and the two-array fixture for claim and replay qualification, and Apache Commons Math GCD for the first upstream change. Part 2 uses those same inputs to refactor the direct proof route, then tests an adapter against ThreeTenBP’s date arithmetic.

**Starter inputs.** Extract the kit alongside the checkout. From its root, `sh gradebook/run.sh` and `java alias/AliasedArrays.java` run with a JDK. Its README gives the pinned upstream inputs and JVM commands for GCD and ThreeTenBP. [java-foundation-starter.zip](java-foundation-starter.zip)

**How the parts meet.** In Part 1, record the actual result or first blocker for each required claim through the existing route. Keep the JVM reference results, frozen claim keys, artifact identities and attempt records. If a known translation gap prevents a claim from earning a receipt, carry that open obligation into Part 2. After implementing the recipe, return to the same frozen case and apply the final acceptance check. Work can continue on independent claims while that one is open.

## Part 1 · Verification foundations

**First assignment.** Open the last verified checkpoint on the implementation branch. Inventory existing claim and attempt records for example 105. Then take the Gradebook fixture in the accompanying starter kit through the ordinary public route and compare each claim with its independent finite JVM oracle. Use the Apache Commons Math GCD change as the first new upstream packet. These three tasks isolate the history, observation and real-artifact requirements of the foundation plan.

This is a continuation brief. The private or unmerged state of the interrupted run is unknown. The repository examples below were inspected on `main` at `2fd3369f`. At handoff, list each relevant change as merged, present on the working branch, or still open. Keep successful partial work and retain any genuine incomplete attempt with its original identity. Keep the scope of each existing receipt attached to its original claim and subject.

### Foundation work packages

| Package | First example | What the agent should deliver |
|---|---|---|
| **A. Qualify the checker** | The shared-array fixture, an immutable calendar value, and a caught arithmetic exception | Use two predecessor branches yielding different array contents or freshly allocated objects. Recheck that joining paths preserves observable differences or explicitly refuses the claim. For environment binding, let a display formatter capture a named setting at class initialization. Compare two fresh JVMs whose settings differ. For exception qualification, distinguish exception class, selected message policy, an observed catch and an escaping exception. Start with the array join, then the environment and exception checks. |
| **B. Bind claims and preserve history** | 105 for existing evidence, Gradebook for controlled interruption | Group records by source claim, bound artifact and execution. Ensure a retry or sibling cannot overwrite earlier evidence. Display latest attempt next to currently eligible result, its qualifications, last completed stage and evidence links. Keep `restsOn` and `limits` in machine and human output. |
| **C. Share bounded inputs and observers** | Gradebook, then the original 71-input two-array problem | Exercise the public route from claim file through execution, replay and acceptance. Preserve shared vs equal-but-distinct roots. Check native across the stated finite domain. Exercise an explicitly defined overlapping profile on JBMC with a preserving and a distinguishing pair. Give a smaller supported profile a separate identity. |
| **D. Check transfer and cost** | 193 for ordered effects and a framework route, Apache GCD for a real change, then ThreeTenBP for a second library | Pin subject and checker inputs, compare the effective statement and replay, and capture first blocker, runtime and peak memory. Record operational budget and host/cache conditions for timing comparisons. Release the independent application streams when the corresponding gates pass. List unfinished obligations and their first blockers. |

### Work already in the repository

**105 · Apache Commons Numbers integer powers.** The integrated packet has a refuted property before the fix, an established property afterward, a refuted unrestricted comparison, and an unresolved confined-change task. The latter records a strict-checker gap at a `StringBuilder` constructor. Two before-property attempts share a prepared claim ID and another in the same task directory has a different ID. A fresh agent should recover all three by navigating from the claim, without conflating them. Keep the older README’s account of a JBMC run and its timing labeled as historical. This makes a read-only first delivery possible before scheduling new work. [Receipts](https://github.com/pilifs/in-the-loop/tree/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/105-commons-numbers-223-pow-of-minus-two-to-the-31/receipts) · [Recorded gap](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/105-commons-numbers-223-pow-of-minus-two-to-the-31/records/refusals/confined-change.json)

**193 · Shop quote.** An order at one cent per unit and quantity 100 returns 90 cents on both versions. The old version records a quote event with total 90 and quantity 100. The new version records none. The checked-in example describes a JVM replay under recording stubs. Declare two independent obligations on the same pair, one for the returned amount and one for the ordered event trace and payload. Run quantities 99 and 100 with a positive total to distinguish an unchanged control from the differing case. Generate separate receipts for these claims. The existing joint result supplies a baseline. [Shop quote and recorded witness](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/193-a-bulk-order-s-quote-event-dropped-in-the-refactor-refuted-on-the-route-s-trace-of-sends/README.md)

### Runnable synthetic fixtures

#### Gradebook, a controlled three-revision history

The same Java method returns the previous mark and writes its replacement. A deliberate regression omits the final-slot write. A repair skips only redundant writes. The domain is all non-null arrays of lengths 1–3 with marks and replacements in `{0,1,2}` and any valid slot. The kit compiles the three implementations separately and compares each against an independently expressed per-cell rule. It uses no external dependencies.

| Observation | Baseline errors | Regression errors | Repair errors |
|---|---:|---:|---:|
| Return the previous mark, 306 inputs | 0 | 0 | 0 |
| Correct full poststate, 306 inputs | 0 | **78** | 0 |
| Correct poststate on interior slots, 189 inputs | 0 | 0 | 0 |
| All untargeted cells unchanged, 306 inputs | 0 | 0 | 0 |

On `[0], slot 0, replacement 1`, all three return zero. The regression leaves `[0]`. The other two leave `[1]`. The witness refutes the full-state claim. It is outside the domain of the interior-only claim. Give each obligation its own frozen identity and validate membership at replay. The synthetic history supports introduction (baseline → regression), repair (regression → repair), and preservation across a successful refactor (baseline → repair). No historical provenance needs to be inferred.

**Attempt-history drill.** Start the execution record before launching the checker. Complete the return-only claim. In a separate attempt for full poststate, inject an interruption after the checker emits a candidate and before witness qualification. From a fresh checkout, recover the candidate and stage, identify the missing replay, and retry with a new linked execution ID. Ingest a completion twice and launch two retries concurrently. Each real execution should appear once. Sibling evidence should retain its status. Record that the stop was injected. Separately retain a genuinely timed-out or slower comparable attempt if observed, with its budget, strategy, stage timings and baseline. A last-slot witness tested against the interior-only claim provides a distinct late *replay rejection*. Treat the reason as domain mismatch, even if the JVM shows a difference.

#### The two-root array case

The domain has two nullable array roots, lengths 0–2, and cell values in `{0,1}`. Include shared roots and distinct roots with equal contents. The reference writes the first cell through the left root when both arrays are present and nonempty, and the control skips the write. Both return zero. A fresh JVM enumeration in the kit produced **0 return differences, 3 right-root differences, and 21 combined-root differences over 71 inputs**. With a single shared `[0]`, the right root sees the write. With two separately allocated `[0]` arrays, it does not. Require the replay to preserve that distinction. Count the oracle cases independently of any single symbolic witness. This is the first fixture for testing heap construction, sharing and selected poststate.

**Optional exception control.** On divisors `{-1,0,1}`, let a small averaging routine attempt an integer division, catch `ArithmeticException`, set a visible handler marker and return a chosen fallback. Freeze separate claims for “no divide-by-zero event,” “no exception escapes,” and “the specified handler and fallback are observed on zero.” Expected results are refuted, established, and established, respectively, if the selected backend supports each observation. The marker covers this explicit handler. It supplies no general JVM event instrumentation.

### Upstream library cases

**1. Apache Commons Math MATH-238 · greatest common divisor.** Upstream fixed `MathUtils.gcd(int,int)` for large operands. The parent used multiplication to test whether either input was zero. In Java two nonzero integers can have an `int` product of zero after overflow. Pin parent `4564adbf19ebc6da19befcc7dbef310a00b4de13` and fix `dabf3a5beb9ab697d570154b9961078a8586c787`. Each complete upstream `MathUtils.java` compiled unchanged with JDK classes only. The kit includes the independent harness and checks the original source blobs before compiling them. [Apache fix and test](https://github.com/apache/commons-math/commit/dabf3a5beb9ab697d570154b9961078a8586c787) · [Apache release notes](https://commons.apache.org/proper/commons-math/changes-report.html)

| JVM calibration | Parent | Fix |
|---|---:|---:|
| Expected `gcd(2^i,2^j) = 2^min(i,j)` for all 441 exponent pairs from 0–20 | **45 mismatches** | **0** |
| Expected `gcd(0,n) = n` for all 256 values from 0–255 | 0 mismatches | 0 |
| `gcd(65536,65536)`, expected 65536 | 131072 | 65536 |
| Apache’s regression assertion, expected 98304 | 3440640 | 98304 |

Use the bounded power family for the correction claim and the zero-input family for preservation. Prepare both revisions once, record the actual byte identities, then qualify each outcome separately. A test set restricted to small operand *values* would miss precisely the change of interest. The parent/fix pair establishes a repair boundary. The commit that originally introduced the defect is unknown here.

**2. ThreeTenBP · complete hours across midnight.** Pin parent `fea38bd81e10d35ef8d991a4463733587e3ee7bc` and fix `f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88`. For a local interval from 23:30 to 00:15 the next day, the correct number of complete hours is zero. Use two consecutive dates and quarter-hour inputs. Compute expected hours from a single signed minute difference divided by 60, truncating toward zero. Keep separate obligations for agreement with the clock oracle, same-day preservation, and reversing endpoints. Reversal symmetry can hold on a consistently wrong answer. Freeze the dates, units and absence of time-zone conversion. [Upstream fix and tests](https://github.com/ThreeTen/threetenbp/commit/f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88) · [Method contract](https://www.threeten.org/threetenbp/apidocs/org/threeten/bp/LocalDateTime.html)

On OpenJDK 21.0.13 the pinned production sources were compiled and checked against their Git blob identities. The 192 quarter-hour timestamps gave **36,864 ordered pairs per revision**. The parent disagreed with the complete-hours oracle on **6,912** pairs, the fix on **zero**. Both versions had zero same-day discrepancies and zero violations of sign reversal. The 23:30 → 00:15 witness returned 1 then 0, and the reversed pair returned −1 then 0. For this historical source tree on JDK 21 the compiler needed `--add-exports java.base/sun.util.calendar=ALL-UNNAMED` for an unrelated chronology class. The tested method has no time-zone dependency.

**3. Apache Commons Lang · UTF-16 search as the next interface case.** Pin parent `2d2e68560fb001c7fa8f8d6f7475f3b800acd995` and fix `bdd674f7c64dbc2c8ff043ee995fcd9f6f59a13b`. Upstream fixed the end-origin search for a supplementary character on a non-String `CharSequence`. Freeze short sequences of up to three tokens drawn from `{a,b,U+2070E}` and test public `StringUtils.lastIndexOf` on a `StringBuilder`. Independently enumerate tokens and their UTF-16 offsets. Ask for last-match correctness, unchanged absent-character results, and ordinary single-code-unit preservation. Pin the runtime type because a plain `String` exercises a different implementation path. Source and upstream regression tests were inspected. This is a candidate after the first two upstream cases. [Upstream fix and tests](https://github.com/apache/commons-lang/commit/bdd674f7c64dbc2c8ff043ee995fcd9f6f59a13b) · [Apache release notes](https://commons.apache.org/proper/commons-lang/changes.html)

### Foundation evidence to carry into Part 2

1. A fresh agent can find the eligible result for each required claim, the latest attempt, the preceding slower or interrupted attempt, and what evidence is missing. An interrupted or rejected replay cannot replace an independently accepted sibling.
2. The public planning output names the admitted inputs, effective bounds and observation. The same information survives execution and acceptance. An in-domain counterexample is replayed on the selected artifact and observer. A valid witness for another claim is rejected.
3. The native and selected JBMC runs state their actual coverage. Retain any backend refusal on its own claim, with the first unsupported construct and last completed stage. A precise refusal is a successful diagnostic test and leaves its proof obligation open.
4. Show at least one preserving change and one real correction through the ordinary user entry. Count required claim/subject pairs independently of attempts. Compare cost only for a fixed obligation with matching artifacts and recorded operating conditions. If all synthetic cases pass but an upstream artifact fails, make that artifact the next engineering priority.

**Evidence boundary.** Repository outcomes above are checked-in records. New JVM enumerations are finite reference results. No new `jvmcontract` or JBMC jobs were run for this continuation brief. Historical bytes and a public repair can support a before/after conclusion. A generated mutant is recorded as constructed, and an adapter result is qualified by its admitted inputs and checked entry.

## Part 2 · Python architecture for proof runs

Keep Python for planning, preparation, controls and evidence qualification. Give the ordinary proof route one typed translation from a declared claim to the exact `jvmcontract` invocation. Start with Gradebook and Apache Commons Math for direct method calls. Add a second recipe for ThreeTenBP, where primitive clock ticks must first be converted into the objects expected by the upstream method.

**Starting point.** The architecture review describes `pilifs/in-the-loop` at `2fd3369f`. Inspect the working branch first. Reuse any translation, claim, attempt or replay support already present there. The foundation starter supplies finite JVM reference results for all three pilots. [java-foundation-starter.zip](java-foundation-starter.zip)

### Where the architecture works

| Boundary | What already works | What I would change |
|---|---|---|
| Example authoring | A task identifies a property or revision pair. The sidecar and claim file already express the method, inputs, observations, bounds and controls. | Keep the existing JSON authoring path. Give authors a way to see which parts the selected proof strategy can honor. |
| Proof lifecycle | The 74-line `route.py` coordinates planning, preparation, controls, verification and ingestion. Frozen Python types distinguish a task plan, prepared target, raw execution and receipt. | Extend that existing sequence with an explicit translation from the planned claim to an invocation. Preserve stage-specific refusals. |
| Rust checker | The binary exposes property-file execution and structured descriptions of assumptions, observations, bounds, models and vacuity. | Use those fields as evidence of what was checked. Add narrow output fields where Python otherwise has to infer scope. Keep JVM semantics in Rust. |
| Verification queue | Task submission reuses the proof planner. The queue owns a pinned checkout, resource limits, retries, logs and conflict-aware collection. It also runs other kinds of jobs. | Let the queue carry proof and attempt references. A retry gets an execution identity so the earlier attempt remains discoverable. |
| Evidence and reporting | Acceptance already checks details such as artifact identity, replay and provenance. | Move result decoding out of the CLI. Keep the decision to accept a claim independently checkable. |

[Proof route](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/route.py#L44) · [Workflow interfaces](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/interfaces.py#L45) · [Rust property-file interface](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/lib/src/main.rs#L973) · [Rust statement](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/lib/src/statement.rs#L29) · [Task submission](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/verification/pipeline.py#L1818) · [Queue collection](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/verification/pipeline.py#L1579)

### A claim can change without the invocation changing

At the reviewed snapshot, the planner included the equivalence claim’s input assumption in its frozen identity. The ordinary property-proof command emitted `--assume`. The ordinary equivalence command omitted it, although the Rust CLI could accept it. A planner probe with stand-ins for prepared artifacts produced three distinct claim keys and one identical command when varying the assumption and selected observations. That probe stopped at command construction. Published verdicts require their own evidence. [Claim planner](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/workflow.py#L209) · [Ordinary invocation](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/runtime.py#L1581) · [Rust equivalence interface](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/lib/src/main.rs#L491)

Recheck this on the working branch using the Gradebook baseline and regression. Keep the prepared bytes fixed across three claims and show the translation for each one in `--plan`.

| Claim on the same pair | Independent JVM calibration | What acceptance needs to check |
|---|---|---|
| Return the same previous mark on any admitted slot | Agreement on all 306 inputs | A final-array difference alone cannot refute this claim. |
| Leave the same final array on any admitted slot | Differences on 78 of 306 inputs | Replay the same starting array, slot and replacement on each revision, then compare the complete final arrays. |
| Leave the same final array on interior slots only | Agreement on all 189 admitted inputs | The last-slot witness is outside the claim. Require evidence that the checker enforced the interior assumption, or an explicit reason this route cannot check it. |

Use the concrete witness `scores=[0], slot=0, replacement=1`. Both versions return 0, and their final arrays differ. That input belongs only to the first two domains, and its array difference supports only the second refutation. Record why it was rejected for each other observation or domain. A single invocation can serve several claims when its effective domain and observations justify each conclusion separately. A proof over a larger domain can support a narrower property if the observations, assumptions and bounds permit it.

### What should become declarative

Introduce one small Python component that consumes the existing task plan and a selected **proof recipe**. The recipe describes how a verifier can check a claim. Its first implementation can be a typed Python function for direct-method verification. Give authors a new JSON field only when there is a real choice to express. An adapter recipe becomes justified by the second pilot.

| Concept | What belongs there | Example |
|---|---|---|
| **Claim** | What is asserted, about which revisions and method, over which domain and observations, with which semantic bounds. | On interior gradebook slots, the baseline and regression agree on the final array. |
| **Proof recipe** | Which method the checker actually enters, how it corresponds to the subject, how each side’s ordered classpath is built, how assumptions and observations are enforced, which models or lemmas are required, and what replay qualifies the result. | Direct verification of a method from pinned source slices, or verification through a named adapter with an explicit scope. |
| **Attempt policy** | Operational choices such as wall-clock budget, resource limit and retry. Attach the actual choices and measurements to each attempt. | Raising a timeout can retry the same obligation. Reducing the array bound changes the scope the attempt can establish. |
| **Evidence** | Checker-reported statement, actual byte identities, verdict, qualifications and replay where applicable. | A refutation is eligible when the replayed witness satisfies the claim’s precondition and differs on a declared observation. |

The recipe should implement each semantic field through an explicit argument, a pinned harness, or an independently verifiable checker default. For anything else, return the existing `Unsupported` type with the uncovered field. For example, the ordinary builder already refuses hashed model files it cannot supply. A named Rust model and a file with a digest are distinct inputs. Preserve that distinction. Classify engine, model and gap-handling changes by their effect on the checked statement and its qualifications before treating two attempts as comparable. [Ordinary invocation](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/runtime.py#L1581) · [Workflow interfaces](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/interfaces.py#L45)

Expose that mapping in the existing `--plan` output. Planning can immediately explain which inputs it will enforce and which need prepared artifacts. Preparation binds the actual bytes, entry point and ordered classpaths before starting the solver. Ingestion then reconciles the Rust statement, artifact identities and witness or independent controls with the frozen plan. An echoed plan digest proves which plan was requested. It supplies no independent evidence that the verifier enforced it. [Claim planner](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/workflow.py#L209) · [Rust statement](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/lib/src/statement.rs#L29) · [Receipt ingestion](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/workflow_ingest.py#L491)

### Direct-method pilot using Apache Commons Math

Use the existing `TaskPlan` to run `org.apache.commons.math.util.MathUtils.gcd(int,int)` on the pinned parent and fix. Prepare each revision once. Freeze the identities of the compiled class and ordered dependencies, the JDK and checker, the actual entry descriptor `(II)I`, and the bounds. For the zero-input preservation claim, admit `u=0` and `0≤v≤255`. For the correction claim, each operand ranges independently over the 21 permitted powers of two. The oracle computes the expected result from their exponents. A representation the route cannot express earns a typed refusal naming the unsupported field. [Apache GCD fix and regression test](https://github.com/apache/commons-math/commit/dabf3a5beb9ab697d570154b9961078a8586c787)

Before changing the runner, capture the existing route’s plan, arguments, raw result or refusal, and acceptance for each task, wherever available. Compare those records with the new recipe on the same artifacts and budget. The JVM reference for the power family is 45 mismatches before the fix and zero afterward. The zero-input family has none on either revision. Use the same byte identities for proof and replay. Label the compiled upstream class as the artifact. [Ordinary verification scope](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/runtime.py#L1674)

### Adapter pilot using ThreeTenBP

Define a small Java entry `long completeHours(int startTick, int endTick)`. Each tick ranges independently from 0 through 191 and denotes a quarter-hour from midnight on June 15, 2012. The adapter constructs two `org.threeten.bp.LocalDateTime` values and delegates once to the receiver’s `until(Temporal, TemporalUnit)` with `ChronoUnit.HOURS`. Include both endpoints, backward intervals and crossings of midnight. [ThreeTenBP fix and tests](https://github.com/ThreeTen/threetenbp/commit/f0b2eaf1856b7fb5fdf78de3cedc9781b6619b88)

The recipe records the adapter’s checked entry and byte digest, the upstream method and its bytes for each revision, both ordered classpaths, the tick-to-date mapping, and the observation of returned whole hours. Qualify two different relationships independently.

| Check | Acceptance criterion |
|---|---|
| **Does the adapter call the upstream method as declared?** | For each revision, compare the adapter result with an independently constructed direct JVM call for every one of the 36,864 ordered tick pairs. Both paths should return the same value even on the older revision when its answer is wrong. Changing the adapter to use minutes must fail this check. |
| **Does the upstream method satisfy the date contract on this grid?** | Compare with integer elapsed minutes divided by 60, truncating toward zero. The expected mismatch counts are 6,912 on the parent and zero on the fix. Both pass every same-day and sign-reversal check. Preserve per-claim outcomes. |

Only the direct-call exercises and finite clock oracle have previously been run. The adapter and its correspondence test are proposed implementation work. A qualified adapter result applies to these two dates, the quarter-hour grid and the hours unit. If object construction or dispatch is unsupported, retain the verified JVM evidence and record the checker’s first blocker. Keep independent oracles and specialized Java adapters writable in code. Add a declarative field when another real authoring choice requires it.

### Implementation order

| Step | Deliverable | Done when |
|---|---|---|
| **1. Fix claim translation** | Exercise Gradebook’s three claims. Audit the fields already supported by the property and equivalence routes. | `--plan` shows how each requested semantic field maps to a flag, pinned harness, verifiable checker default or specific refusal. The Gradebook evidence distinguishes an inadmissible input from a difference in an unobserved value. |
| **2. Introduce the direct recipe** | Route GCD through a typed invocation. Preserve the public CLI, existing JSON and readable receipt identities. | Old and new paths are compared on like inputs wherever a baseline exists. Differences are explained by the effective statement, prepared bytes or checker capability. |
| **3. Add the adapter recipe** | Run ThreeTenBP with the correspondence and correctness checks above. | A wrong-unit adapter is detected. A receipt names the actual entry and the domain over which its result transfers. A second instance of the same recipe can use data to supply artifacts and arguments. |
| **4. Extract result decoding** | Move shared Rust-result decoding and classification primitives out of `build.py`. Feed proof records into the existing queue and durable attempt history. | Old receipts remain readable. A timed-out attempt and its retry are separately discoverable. A batch with mixed outcomes retains the evidence and eligibility decision for each claim. |

The next structural cleanup belongs at the evidence boundary. Receipt ingestion currently imports `build.py` for classification functions. Some acceptance checks rely on a literal generated Java guard or a phrase in human-facing output. Introduce one version-aware decoder for the wire format. Replace textual signals individually when structured evidence and an independent behavioral check cover the same guarantee. A shared decoder can tell consumers what Rust reported. Eligibility for a particular claim still requires a separate decision. [Receipt ingestion](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/workflow_ingest.py#L491) · [Outcome classification](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/build.py#L672) · [Evidence acceptance](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/accept.py#L476)

### Handoff to the next agent

Keep the existing distinction between the source claim key and its binding to prepared artifacts. Link the recipe, actual invocation, operational budget and stage reached to the durable attempt. A retry on the same obligation should let an agent discover that preparation succeeded, the solver exhausted its budget, and a later approach changed strategy. A narrower semantic bound or adapter scope must remain visible. Historical results retain their original meaning. Several claims can share preparation or one invocation, while each claim keeps its own verdict and evidence links. Rust already supports multi-property runs, so the Python design can support such batching where the selected backend and claims are compatible. [Workflow interfaces](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/interfaces.py#L45) · [Claim planner](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/examples/tools/targets/workflow.py#L209) · [Rust property-file interface](https://github.com/pilifs/in-the-loop/blob/2fd3369fb9c884f6bdcbb6549426382d762b1c4f/lib/src/main.rs#L973)

Publish the three Gradebook plans and their per-claim dispositions, the direct GCD comparison, and the ThreeTenBP adapter correspondence report. Include one interrupted or unsuccessful execution and its surviving evidence. The acceptance review should be able to reconstruct what the checker actually ran and why each result is eligible for its stated claim.
