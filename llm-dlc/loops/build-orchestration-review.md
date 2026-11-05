# Review: build.py as a runner of claims, attempts and evidence

The high-level input for the brief [`build-orchestration.md`](build-orchestration.md). It is
an outside review of [`examples/tools/build.py`](../../examples/tools/build.py), with
`verification/pipeline.py` and the library's interfaces, made with ChatGPT at commit
`4c279ba6` (jj `mzpzpssr`, 2026-11-04) and shared at
<https://chatgpt.com/s/t_6aec5e6dc0fc819181c19721e8936d4f>. Its links point at that commit.

It is kept as it was written, apart from the closing offer of follow-ups, so the brief can be
checked against it. It is not edited as the work goes on: what turned out differently goes in
the commit messages and in the brief's Progress section.

---

**Yes. I think `build.py` is now one of the highest-leverage places to work.** The library already exposes capabilities that the script could combine into much more useful workflows: checking a complete bug fix, reviewing a dependency upgrade, producing a reproducible regression test, and systematically trying different proof strategies.

My recommendation is to evolve it into **a runner that records exactly what was claimed, which attempts were made, and what evidence supports the result**. The existing example pages would become one presentation of those results.

I reviewed the exact commit you linked, `4c279ba6f3b46ecac8cf938903059ee993a36968`, including the relevant library interfaces and `verification/pipeline.py`. I also checked several failure cases using isolated Python functions with mocked subprocess results; I did not run builds or formal verification.

There are a few correctness fixes I would make first, followed by some substantial feature opportunities.

## 1. Make the reported result dependable

### A. A crashed verifier must not become “counterexample found”

This is the most urgent issue I found.

In `tool()`, only exit code `2` is treated as a tool failure. Several callers then classify the result as:

```python
verified if returncode == 0
else unverifiable if "cannot be verified" in output
else violation
```

Consequently, an unexpected exit—including a signal termination—can become a semantic violation. See [`tool()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L607) and [`run_tool_equivalence()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L713).

I reproduced this with a mocked process returning `-9`, empty stdout, and empty stderr:

| Input to the runner | Reported result |
|---|---|
| Verifier terminated by signal 9 | `violation` |
| No verifier output | `Violation: counterexample found` |
| No witness produced | Empty counterexample list |

This also affects the benchmark’s success criterion. `matchesExpected` compares the verdict and vacuity flag, so an example expecting a violation can pass because the verifier died. Separately, `write_evidence()` creates an empty SARIF report when the expected report is missing. Together, these can make missing evidence look like a completed negative result. See [expectation matching](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L225) and [`write_evidence()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1447).

**I would represent three separate questions:**

| Question | Example answers |
|---|---|
| Did the execution complete correctly? | Completed, timed out, killed, invalid output, tool error |
| What happened to the claim? | Established, refuted, unresolved |
| Did this match the benchmark’s expectation? | Yes, no, not evaluable |

For an expected violation, require a completed semantic result identifying the failing obligation and its appropriate evidence. That evidence might be a witness, a contract difference, or a model trace, depending on the approach.

This distinction is also essential for a developer-facing CI check: a benchmark that successfully demonstrates a bug and a change that satisfies its requirements are different outcomes.

### B. Always connect the patched bytecode to the model being checked

There is a gap in both D1 paths.

`run_tool_tlc()` regenerates contracts only when `behaviourChangeIntended` is true. It then generates TLA+ from the contract files. The library’s `tla` command reads the supplied contract and emits a module; it does not verify that the contract still describes the patched classes. The legacy Box Office path follows the same conditional pattern. See [`run_tool_tlc()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1314), the [`tla` implementation](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/main.rs#L555), and [`run_tlc()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L443).

The problematic case is precise:

1. A patch changes a decision kernel.
2. Existing tests still pass.
3. `behaviourChangeIntended` is false.
4. TLC checks the operator generated from the old contract.

The model can pass while the new implementation’s decision table never reaches it. The changed-row coverage check will also see identical before/after contracts.

**The intended-change flag should control whether a difference is acceptable. It should not control whether the model corresponds to the candidate implementation.**

I would make these explicit obligations:

- Establish the connection between candidate bytecode and the contract used to generate each operator.
- Compare the candidate contract with the approved baseline and report unauthorized differences.
- Check the model using operators corresponding to the candidate implementation.

You could reuse an existing contract after verifying it against the candidate classes, or derive a fresh candidate contract and retain the difference. Either way, save evidence of that connection and its domain.

This closes a specific gap in the chain. The relationship between handwritten protocol logic and the application remains a separate modeling assumption.

**Qualification:** I did not find a checked-in D1 example that demonstrates this mismatch. This is a confirmed orchestration gap with a clear trigger, rather than evidence that the existing recorded corpus is invalid.

### C. Consume the structured results the library already provides

This looks like an unusually good return on a small change.

The library already supports:

- `equivalence --json`, returning an `Outcome`.
- `prove --json`, returning **all** property outcomes.
- `tlc --json`, which the script already uses.

The equivalence and property runners nevertheless reconstruct results from human-readable text. See the [equivalence JSON output](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/main.rs#L440), [property JSON output](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/main.rs#L498), and [current property parsing](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L751).

That causes more than fragile parsing. A method can have several properties, but the script selects one assertion, one witness, one proof description, and any vacuity line using separate regex searches. Their ownership can become unclear.

There is also a concrete artifact mismatch: the library puts multiple property runs in `property-1`, `property-2`, and so on, while `finish_symbolic()` looks for one harness directly beneath `work/harness`. The recorded result for example 071 has `statement: null`; its target has three property declarations. See [property work directories](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/main.rs#L470), [`finish_symbolic()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L693), and [example 071’s result](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/071-vote-rule-that-compares-log-length-before-term-grants-a-vote-it-must-refuse/result.json#L34).

**Preserve one result per obligation**, including its assertion, assumptions, harness, witness, proof description, and vacuity. Compute a headline above that list:

- Any refuted required obligation makes the change fail.
- Unresolved obligations remain visible even when another obligation fails.
- The change satisfies its checks only when every required obligation is established under the required scope.

The JSON structures already contain much of this information. `verify` and `update` would need additional structured interfaces; I would not pretend their current text output has the same guarantees.

### D. Distinguish missing coverage from zero coverage

The symbolic vacuity reporting is valuable. The TLC coverage logic needs a stronger representation of missing information.

Currently, a verified run with absent coverage is treated as having an empty set of covered operators. If decision rows changed, this can produce `vacuous: true`. I reproduced that behavior using the isolated `tlc_coverage()` function. See [`tlc_coverage()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1262).

Use an explicit status:

```text
coverageStatus: complete | partial | unavailable
```

Conclude that changed rows were unvisited only when the coverage evidence supports that conclusion. Also preserve each configuration’s termination reason: the current renderer can describe an unfinished configuration as having “stopped at the counterexample,” even when it was unverifiable. See [`coverage_lines()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L2008).

This is particularly important for AI-driven experimentation. Missing evidence should give the agent a diagnostic task, not a misleading semantic explanation.

## 2. Introduce a frozen run plan and a durable evidence format

This is the architectural change I would organize the rest around.

### Separate the claim from attempts to prove it

The current example result is predominantly a flat summary. I would introduce these concepts underneath the existing example format:

| Object | What it records |
|---|---|
| **Claim** | Exact before/after artifacts, target method, assumptions, allowed changes, result relation, observations, input domain, and model dependencies |
| **Attempt** | Claim ID, selected engine, effective options, resource budget, execution status, duration, and diagnostic outputs |
| **Conclusion** | What is established, refuted, or unresolved, with references to supporting attempts |
| **Evidence bundle** | Harnesses, witnesses, model/configuration files, logs, reports, and artifact hashes |

The distinction between claim and attempt matters enormously.

Changing a timeout or SAT solver can be another attempt at the same claim. Restricting inputs or reducing the maximum array length changes the claim. An unwind limit needs an explicit completeness interpretation: a successful bounded exploration supports the full claim only when the backend establishes the required completeness conditions.

For the AI workflow, this yields a simple rule:

> An agent can try another strategy against a fixed claim. Changing the claim creates a separately identified proposal.

That makes “we proved more things” measurable. Otherwise, an agent can appear to make progress by narrowing assumptions until a statement becomes easy or vacuous.

### Make one planning function serve both `build.py` and the pipeline

You already have substantial execution infrastructure. `verification/pipeline.py` handles committed-source exports, scheduling, resource reservations, tool caching, run provenance, and output collection. The script should produce detailed claim evidence within that infrastructure. See the pipeline’s [resource planning and tool cache](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/verification/pipeline.py#L672) and [run records](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/verification/pipeline.py#L720).

There is already a concrete reason to share a plan:

- The pipeline requests JBMC for every B9/B11 example, including examples selecting the native engine.
- Box Office examples request Gradle but omit `jvmcontract`, even though B12 uses it.

That can reject a native job unnecessarily or bypass the pipeline’s verifier prebuild and build-memory reservation. See [`example_job_parts()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/verification/pipeline.py#L1305), [`engine_flag()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L745), and [`run_boundaries()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L283).

A pure planning function should resolve:

- Project/build adapter.
- Targets and claims.
- Required and optional tools.
- Engine and effective options.
- Model configurations.
- Expected outputs and retention policy.

Both execution and submission would consume it. Move scratch-directory creation into an execution context so importing the planner has no execution side effects.

### Bind reports to the inputs that produced them

`--render-only` combines an existing `result.json` with the current example metadata. The renderer also reads current authored material, without verifying that it matches the run. `main()` writes the result before validating it, and schema validation is silently optional when `jsonschema` is unavailable. See [`main()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L77) and [`validate()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L164).

I would:

1. Freeze the resolved claim and input fingerprints before execution.
2. Write each attempt into its own directory.
3. Validate the complete result and artifact manifest.
4. Publish the completed bundle together.
5. Render from the saved snapshot, showing whether it still matches current inputs.

Include the actual before/after bytecode and dependency fingerprints, relevant model identities, effective proof settings, and the pipeline job/source identifiers. The pipeline already supplies `VERIFY_JOB_ID`, `VERIFY_SOURCE_COMMIT`, and `VERIFY_WORKDIR`; use them to link the records. See [`step_env()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/verification/pipeline.py#L835).

There is also a small but worthwhile editorial correction: “Why the verdict is right” currently prints the author’s expected explanation even if the observed result differs. Label authored expectations separately from observed evidence. See [that rendering block](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1678).

## 3. Build the developer features around that foundation

### Feature 1: “Check this bug fix”

**This would be my first developer-facing feature.**

The runner already passes `intendedInputs`, previous method/argument mappings, and result relations to equivalence checking. The missing step is combining several obligations into one change review. See [`run_tool_equivalence()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L713).

For an illustrative request such as “treat the exact expiration deadline as expired,” generate a reviewable plan:

| Obligation | Meaning |
|---|---|
| Preserve surrounding behavior | Outside the declared boundary case, old and new behavior agree |
| Establish the fix | At the boundary, the new implementation reports expiration |
| Preserve relevant policies | Applicable boundary/capability requirements continue to hold |

This uses B9, B11, and relevant contract checks together.

`--unchanged-unless` alone establishes preservation outside an allowed change region. It does not establish that the behavior inside that region is correct. The combined workflow answers both questions.

The existing `behaviourChangeIntended` flag is too coarse to carry this intent. In several paths it causes contracts to be regenerated before verification. That is useful for authoring a candidate contract, but a developer-facing gate also needs an independently specified requirement or reviewed allowed difference. The B12 path’s extra check for newly introduced problem lines is already a useful example of an additional policy. See [`run_tool_contracts()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L657) and [`run_boundaries()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L283).

For an ordinary Java developer, the interface can be:

> “Here is the behavior you meant to change. Here is what should stay the same. Here is what we established, and here are the remaining gaps.”

The formal specification can remain inspectable underneath.

### Feature 2: Turn findings into a JVM replay and a JUnit test

There is an important accuracy issue and a feature opportunity here.

The Rust equivalence implementation replays witnesses in your bytecode interpreter. The README renderer nevertheless says the finding was replayed “on the JVM against both versions.” See the [equivalence implementation’s description](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/equivalence.rs#L5) and [`findings_equivalence()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1776).

First, make the wording derive from recorded replay metadata.

Then add an actual JVM replay stage:

1. Preserve the witness arguments, target descriptors, mappings, and artifact identities.
2. Execute the old and new artifacts in isolated JVM processes.
3. Record returns, exceptions, and supported observable mutations.
4. Evaluate the same relation used by the claim.
5. Export a JUnit regression test and a reproduction command.

Start with supported primitives, strings, and arrays. More complicated object graphs can follow as the representation becomes reliable.

The JSON outcomes already expose argument values and shrinking information, though the values are currently strings; retain those and add enough type information for unambiguous reconstruction. See the [`Counterexample` structure](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/equivalence.rs#L136).

**The result becomes something a developer can run, debug, and commit.** Independent JVM replay also gives useful evidence about a witness’s correspondence to actual execution. It confirms that execution; it does not establish the universal claim.

### Feature 3: Make real projects runnable inputs

At this commit, `app_of()` recognizes four bundled applications, and `main()` explicitly skips real-world examples. I confirmed that selecting example 108 prints the skip message and returns exit code zero. An unknown ID also returns zero without running an example. See [`app_of()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L153) and [selection handling](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L94).

The immediate fix is strict argument parsing and explicit “unsupported/not executed” outcomes for requested runs.

The larger feature is a project adapter that produces:

- Before and after classpaths.
- Target methods and source locations.
- Build and test commands, when needed.
- Claims and model dependencies.

**I would start with two already-built class/JAR sets and explicit targets.** Maven and Gradle import can then provide those inputs automatically.

That gives you a practical route to:

- Checking a real pull request.
- Comparing dependency versions.
- Reproducing a historical regression.
- Turning a Jackson example into an executable recipe.

The numbered examples can continue to use the same mechanism. A Jackson experiment should be expressible through a manifest, without adding another application-specific branch to the script.

### Feature 4: Run disciplined AI proof experiments

This is the runner improvement most directly connected to your original question about frontier models making difficult verification feasible.

Give the agent a controlled loop:

1. Resolve and freeze the claim.
2. Run an initial supported strategy.
3. Receive a structured diagnosis: counterexample, unsupported operation, resource limit, incomplete exploration, or other failure.
4. Propose another strategy or additional proof obligations.
5. Check those obligations and record their dependency on the original claim.
6. Report the original claim as established only when the required checks support it.

The library already exposes engine selection, timeouts, SAT solver selection, string refinement, and shared-callee controls. The script exposes only part of that surface. See the [equivalence option wiring](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/main.rs#L417).

I would expose these as named experiment profiles, with effective settings saved for every attempt. For example:

| Diagnosis | Useful next experiment |
|---|---|
| Resource limit | Retry with a different supported solver or budget |
| Unnecessary exploration of unchanged dependencies | Compare supported shared-callee settings |
| Difficult arithmetic | Propose a decomposition into checked arithmetic obligations |
| Unsupported library behavior | Identify the exact missing model or summary |
| Vacuous claim | Diagnose the assumptions and propose a separately reviewed claim |
| Several independent properties | Preserve completed outcomes and focus on unresolved ones |

There is an important boundary: **the runner can coordinate a lemma or summary workflow; the backend must support checking and using it soundly.** An AI-written explanation or an unchecked replacement model cannot close the original claim.

For the Jackson division example, the useful outcome would be a repeatable experiment: the exact artifacts and numeric assumptions, direct-checker attempts, a proposed arithmetic decomposition, machine-checked obligations where supported, and the remaining Java-semantics requirements. That would let you measure whether better models are reducing intervention or closing previously unresolved claims.

Track progress by fixed claim, including time, compute, interventions, and reasons for failure. A narrower theorem should appear as a different result.

## 4. Preserve work and make expensive runs easier to understand

Several execution changes would support all four features.

### Stream stage output and retain the inner workspace

Most subprocesses use `capture_output=True`. The outer pipeline can stream `build.py` output, but it cannot recover child output that remains buffered inside Python. Meanwhile, the per-example temporary directory is deleted on exit, and symbolic runs copy only selected artifacts out. See [`run()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L179), [`tool()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L607), and [`finish_symbolic()`](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L693).

Use a common command wrapper that writes stdout/stderr to per-stage files and emits compact progress events. Put attempt directories under the pipeline work directory when present.

Preserve the generated harness, exact inputs, relevant tool outputs, and partial logs. Retain certificates when a backend actually supplies them; distinguish those from an ordinary solver result record.

### Save each completed configuration immediately

`run_tool_tlc()` runs all configurations before writing the combined output. If a later invocation errors, earlier results may exist only in memory. See [the configuration loop](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L1328).

Checkpoint each result independently. Resume only when its complete input fingerprint matches.

The same approach can later support independent properties and decomposition obligations. This would be particularly helpful for AI agents: they can build on completed evidence instead of restarting a whole experiment after one failed stage.

### Cache subject builds across jobs

`BEFORE_CLASSES` is process-local. The pipeline’s one-example jobs therefore do not share it. Also, `tool_before_classes()` invokes `tool_compile()`, which compiles tests even though only production classes are returned. See [the compilation helpers](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/examples/tools/build.py#L577).

Split production and test compilation, then consider a content-addressed baseline build cache keyed by the relevant sources, dependencies, compiler identity, and options.

Keep proof reuse stricter: unchanged method text alone is insufficient when callees, models, or assumptions change. The library already has dependency-aware unchanged-code and shared-callee handling; expose that evidence through the runner. See [the equivalence implementation](https://github.com/pilifs/in-the-loop/blob/4c279ba6f3b46ecac8cf938903059ee993a36968/lib/src/equivalence.rs#L18).

Stage timings will tell you whether compilation reuse matters for a particular workload. For difficult arithmetic, proof strategy may dominate.

## 5. The implementation sequence I would choose

I would deliver this incrementally:

| Order | Change | Acceptance criterion |
|---|---|---|
| **1** | Structured B9/B11 outcomes and explicit execution status | A killed process, malformed output, or missing result can never count as an expected semantic violation; every property retains its evidence |
| **2** | D1 correspondence checks and reliable coverage status | Every generated operator has a recorded connection to candidate bytecode; missing coverage remains unknown |
| **3** | Shared planning function and validated evidence bundles | Pipeline requirements match the selected backend; reports identify exact inputs and cannot silently mix attempts |
| **4** | External-artifact adapter, combined change checks, JVM replay | A real before/after Java change produces preservation results, intended-behavior results, and reproducible findings |
| **5** | Checkpointed experiment profiles and AI orchestration | Several strategies can pursue a fixed claim, with resumable evidence and measurable progress |

For the early changes, use small runner-focused regression fixtures: terminated processes, malformed JSON, multiple properties with mixed outcomes, missing coverage, stale input fingerprints, and unknown selections. They directly test the orchestration risks without needing an expensive proof run for every case.

**The feature I would aim to put in a Java developer’s hands first is “check this fix and give me a regression test for any unintended difference.”** Structured results, combined obligations, and actual JVM replay would get you substantially closer using capabilities that are already present in the library. The same foundation would then make the more ambitious AI-assisted Jackson experiments easier to run, compare, and trust.
