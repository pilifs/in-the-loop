# Fast-follow brief · Reconcile the Rust and Python architecture of `lib`

**21 November 2026 · `pilifs/in-the-loop` · Baseline [`cfe2dc91`][head]**

**Commission three changes before the next proving campaign.** Give Rust proof output one interpretation across its Python consumers. Bind preparation and checking to the same class bytes that the selected JVM loads. Extract the existing Python array-induction implementation into `lib` as a concrete test of how a research technique becomes a reusable library capability. The first two changes address observed disagreements. The third tests whether the architecture makes a successful research technique easier to reuse without forcing a language rewrite.

**Decision for research briefs.** A domain agent may change any layer needed to solve a hard problem. It may write a new proof method in Python, extend the Rust engine, use an independent solver, or leave an unsuccessful experiment beside an example. The durable commitment begins when another component interprets that work as evidence for a claim. At that point the consumer must be able to reconstruct what ran, on which bytes, at what scope, and why the result qualifies. Keep this brief to one implementation run. It is ready to hand to the watcher as a single brief.

## What exists today

| Responsibility | Current implementation | Direction |
|---|---|---|
| JVM analysis and checker execution | `lib/Cargo.toml` builds one Rust package, `jvmcontract`, with a library and CLI. `property` and `equivalence` produce typed outcomes. `statement` and `spec` describe assumptions, observations, bounds, models and evidence. `classfile`, `classpath`, `bmc`, the interpreter and the JBMC driver carry different parts of the execution. | Keep the single crate. Give shared proof-result types a library home when both proof modes need them. Keep distinct engines, replay and oracle implementations independently testable. [Crate][crate] · [Modules][modules] · [Statement][statement] · [Shared IR][spec] |
| Planning, orchestration and evidence qualification | The Python target route already has `TaskPlan`, `ProofRecipe`, `PreparedTarget`, execution history and receipt ingestion. `recipes.translate` already forwards a declared assumption. `qualification.py` compares what Rust reported with what the plan asked for. | Build on these stages. Rust reports the statement it actually checked. Python independently determines whether it answers the frozen claim, including an adapter’s correspondence and any replay. [Route][route] · [Recipe][recipe] · [Qualification][qual] · [Earlier implementation results][prior] |
| Benchmarks, tools and emerging proof capabilities | Of 111 tracked Python files under `lib/`, 97 are under `benchmark/`, nine under `tools/`, three under `tests/` and two under `solvers/`. Meanwhile, `examples/tools/targets/array_induction.py` translates bytecode into solver obligations. | Organize reusable software by the decision it owns. Benchmark scoring belongs with the benchmark. A proof technique used by multiple examples can belong in the library even when its implementation is Python. [Benchmark reader][bench] · [Array induction][induction] |

The earlier foundation work already produced direct and adapter recipes, version-aware decoding and recoverable attempts. This brief changes the consumers that bypass those mechanisms and the places where independently maintained representations disagree. Recheck the pinned findings at the implementation head, especially after the queued process brief lands. [Previous architecture work][prior]

## 1. Make proof output a library contract

**Observed disagreement.** I replayed the first established row of example 359’s `contents-fix` native-selector result through the existing ordinary decoder, selector classifier and benchmark classifier. The original row has `wire_version: 1`, and the complete native-selector route reports 2,865 admitted and checked cases. The table changes one input at a time in memory. The original row passes all three paths. [Archived case set][case359] · [Ordinary decoder][decode] · [Selector classifier][selector] · [Benchmark reader][bench]

| Input to the existing readers | Ordinary wire decoder | Native-selector row | Benchmark with expected `verified` |
|---|---|---|---|
| Original v1 row, exit 0 | Decodes one outcome | `established` | `correct` |
| Only `wire_version` changed to 999 | Refuses the unknown version | `established` | `correct` |
| Only `stated.bounds.complete` changed from Boolean `true` to string `"false"` | Decodes the envelope | `established` through Python truthiness | `correct` |
| Original row, process exit changed to 2 | Decodes the bytes independently of exit | `open` | `correct` |

**Implement the narrow shared contract.**

1. Move ownership of versioned proof serialization from the private CLI wrapper into a small Rust library module beside the outcome types. Keep the CLI as a caller. Preserve the `prove --json` ordered array, the `equivalence --json` object, and each command’s existing process-exit semantics. Property and equivalence may keep different payloads. `lib/src/wire.rs` already means wire types in application contracts and should retain that meaning. If common types such as `equivalence::Search` or `Replay` move, retain the existing public Rust paths with re-exports. [CLI producer][emit] · [Equivalence outcome][regression] · [Property outcome][property]
2. Put one small importable Python reader for this contract under `lib/`. A module at `lib/python/jvmcontract_io.py` is a sufficient initial shape. Factor the usable parts out of `examples/tools/checker_output.py` and keep existing script/import entry points. Separate three questions in code. **Can these bytes be decoded? Did the process complete consistently with the requested command? Does this evidence qualify for this claim?** The first two have shared rules. The third belongs to the consumer and its independent checks. A benchmark can score a valid engine answer differently from a proof campaign.
3. Switch ordinary ingestion, live native selectors, archived selector validation, and `lib/benchmark/run.py` to the shared reader. The solver comparison also consumes the benchmark reader. A single-property benchmark must require its one expected outcome. For the Rust CLI, both a violation and an unverifiable outcome map to exit 1, and a multi-property run returns the maximum exit across its rows. A valid refutation can score correct at exit 1. A verified sibling in that batch keeps its own result. Exit 2 denotes a tool failure. Preserve the order of all rows. Validate the actual types of fields used to justify a decision. Treat missing legacy information as unknown where a claim requires it. Keep raw output, version and reason available for diagnosis. Timeouts, tool errors, contradictory exits and unsupported versions cannot receive a newly decisive classification. Preserve the published scoring categories for valid historical inputs. [Archived selector checks][selector-read] · [Solver comparison][solver] · [Receipt ingestion][ingest]
4. Remove **one demonstrated dependency on English text** as a Rust-to-Python round trip. Rust’s proof cache can apply a changed helper by summary or retain its body. The current Python regex recognizes the earlier shared-helper/stays-as-written messages and omits those two paths. Emit a typed helper decision for new outcomes, including callee identity, action, applicable proof/summary key and reason. Preserve the distinction between a helper proved equal and a conditional summary applied at particular calls. Render the human note from the decision. Keep the old reader for records that predate the field and preserve the meaning of `sharedHelpers`. [Rust decisions][helpers] · [Python projection][helper-reader] · [Reuse control][reuse-test]

**Acceptance.** Run the table as a fixture through the actual entry points. The future version has an explicit unsupported outcome everywhere. A string cannot satisfy a required Boolean. A failing process with a decisive-looking payload earns no benchmark credit. Keep untagged v0, current v1, genuinely mixed multi-property results, cache hits without a fresh search, vacuity/unknown, assumed gaps and interrupted attempts distinguishable. Verify the unmodified 359 route still qualifies all 2,865 cases. Change only the human wording in a new-format helper record and get identical structured results. Keep historical artifacts immutable. [Existing version tests][recipes-test] · [Existing helper expectations][helpers-test]

## 2. Bind the proof to the class that ran

**Observed disagreement on a running JVM.** I built a disposable multi-release JAR containing two valid implementations of `fixture.Gate.marker()I`. The base method returns 1 and the Java 17 overlay returns 17. The two JARs below differ only in how the manifest spells the value of `Multi-Release`. On OpenJDK 21.0.13 I checked both the class resource digest using the repository’s `LoadedClasses.java` and the return value from an ordinary JVM call. Hashes below are the first 12 hex digits of SHA-256. [Preparation][prep] · [Python entry selection][jar] · [JVM probe][loaded] · [Existing folded-manifest test][jar-test]

| Manifest value | Python preparation digest | Python effective-entry digest for Java 21 | JVM-loaded digest | JVM return |
|---|---|---|---|---:|
| `Multi-Release: true` on one line | `3bf6db2ffa75` (base) | `fad6975e4aec` (overlay) | `fad6975e4aec` | 17 |
| Same value folded as `tr\r\n ue` | `3bf6db2ffa75` (base) | `fad6975e4aec` (overlay) | `3bf6db2ffa75` | 1 |

The native launch path already compares effective bytes with the prepared binding and can refuse a disagreement. Keep that protection. The Rust resolver also unfolds manifest continuations in source. The probe above exercised Python and the installed JVM. The implementing agent should run the equivalent Rust path under the project’s pinned JDK. The observed folded behavior is specific to the tested runtime until checked elsewhere. This fixture uses the ordinary application classloader and an actual method call as a cross-check. Keep that scope explicit when a custom loader or bytecode transformation is involved. [Native launch guard][guard] · [Rust resolver][cp] · [Rust refusal test][cp-test]

**Refactor around a selected class binding.** Explain once which exact bytes the checker will inspect for a binary class name on an ordered classpath and a bound runtime. Return the selected provider and JAR entry, class digest, feature/JDK identity, and the method name and descriptor requested. Retain physical JAR inventory as a separate operation for provenance. A scan that deliberately lists every ZIP entry and a request for the loaded method have different meanings.

Use `lib/src/classpath.rs` and `lib/src/classfile/` for the tool’s selection and inspection. Start with one internal, batched read operation for the classes needed by a prepared revision. Reuse an existing entry point if it can supply these facts. Wire preparation, method/parameter lookup and the native launch guard through the same binding, including subject and adapter where applicable. Python continues to acquire artifacts, select the toolchain and invoke the independent JVM probe. Keep planning and historical receipt inspection usable without a Rust build. A process per class or per selector is too costly.

On ordinary jars, match existing identities and outputs. For multi-release or shadowed classes, obtain a matching runtime observation or return a typed refusal with both digests and their origins. A successful Rust/Python agreement on the wrong class would still be wrong. Preserve duplicate-class policy, JDK shadowing rules, launcher overrides and missing-member refusals. Test both manifest spellings, an ordinary jar, reversed classpath order, an unbound release, an overloaded or missing descriptor, and at least one existing non-synthetic target. A previously refused case may become eligible only with new evidence bound to the bytes actually loaded. [Rust class bytes][cp] · [Preparation and origin checks][prep] · [Parameter lookup and extraction][params]

## 3. Promote one proven Python technique into `lib`

**Choose array induction.** The current module parses pinned `javap` output, propagates Java arithmetic and heap state, constructs SMT obligations, calls Z3, acquires example artifacts, and publishes results. Its disassembly helper is also imported by schedule and monitor experiments. The proof method already has three concrete consumers. This is enough evidence to extract it. [Implementation][induction] · [Route][route] · [Existing Rust loop summaries][loops]

| Existing workload | Behavior the extraction must preserve |
|---|---|
| 336 · Guava first array match | `first-any-length` is established for its declared domain of already-allocated, non-null arrays. Preserve the nonempty-domain and termination obligations. [Recorded run][r336] |
| 337 · JDK range fill and aliasing | `fill-any-length` and `caller-any-length` are established. `caller-extra-any-length` stays unresolved because its caller-frame obligation expected `unsat` and obtained `sat`. This is the most important negative control. [Unresolved caller][r337] |
| 346 · Guava long-array holdout | The established first-match claim uses 64-bit elements and 32-bit indices. A shared implementation must preserve the distinction without an example-ID switch. [Recorded holdout][r346] |

Move the reusable instruction/obligation logic and solver-result handling under `lib/` in Python first. Keep example discovery, revision choice, artifact preparation and receipt publication in the current adapter. Make it possible to invoke the extracted core on a bound method plus its declared rule without a numbered example directory. Keep existing imports for the other disassembly clients while migrating them. The Rust bytecode decoder is a candidate to replace textual parsing for the specific instructions this technique consumes. Compare its decoded operands, branch targets and exception handling against the pinned disassembly before switching. That substitution can wait if the extraction already gives the next domain a usable API. [Rust decoder][bytecode] · [Current adapter and records][induct-adapter]

Record the rule implementation used for new results. Today `rulesSha256` is the digest of a single Python file. After extraction, a hash of the wrapper alone would miss a changed proof rule. Bind new records to the actual semantic implementation and preserve the meaning of historical digests. The organic benchmark also fingerprints and exports a fixed set of paths. Include the new Python modules in the input set and export for new baselines. Select the historical inventory/hash algorithm for old pins, so exporting an old revision still works. Change only the extracted module and verify the new fingerprint changes. Run a frozen checkout with no ambient project packages and prove it loads the pinned reader and rules. [Baseline fingerprint and export][frozen]

Compare named obligations, expected/observed answers, domain widths, class hashes, and the negative control before calling the move complete. Preserve archived evidence and independent JVM observations. The existing SMT files and recorded solver answers support these specific induction results. They do not certify a general Java-to-SMT translation. [Current provenance][induct-adapter]

## How much architecture should a research agent follow?

Give the agent end-to-end ownership of the question. Use the following decisions when reviewing work for reuse. An agent should be able to complete a promising experiment without opening an architecture discussion first.

| When this happens | What the agent should do |
|---|---|
| One difficult case needs an unfamiliar representation or solver routine | Implement the smallest experiment where it is easiest to work. Record the original claim, approach, observation and first blocker in the existing attempt. A bespoke script or a cross-layer edit is a valid result. |
| A technique works only on a narrower method, domain or adapter | Keep the narrower result under its own claim and retain the original attempt. Record the correspondence check that would make transfer possible. |
| Two readers disagree on a fact that can change accepted evidence | Fix the shared boundary immediately, even for the first case. Add the smallest counterexample that would have caught the disagreement. The two probes in this brief qualify. |
| A second domain needs the same semantic operation, or the same defect recurs | Extract the smallest demonstrated common part. Use one prior caller and the new caller as transfer tests. Independent models and JVM oracles remain independent where their disagreement can reveal a mistake. |
| An abstraction needs example-ID branches or repeated exceptions to express the original research | Shrink it or leave the experiment local. Revisit when there is a concrete second use or measured cost. File length, language choice and resemblance are weak reasons to move code. |

Keep a short map in the existing `lib/README.md` naming the owners of class selection, proof serialization, semantic proof methods, receipt qualification and benchmark scoring. Link to one working control for each. Update it when responsibility moves. No standing per-PR architecture approval is needed. Preserve the distinctions among the source claim key, prepared binding, execution/attempt ID, Rust proof-cache key and archived evidence reference. Each answers a different recovery or reuse question. Equating them just because several are digests would break retries or cache validity. [Source plan][workflow] · [Executions][executions] · [Proof cache][cache] · [Historical result formats][formats]

## Execution order and exit

1. **Baseline on the integrated head.** Reproduce the two disagreements and inventory callers of the affected operations. Capture a compact before/after table for the valid records and negative controls above. If the queued plumbing has moved evidence, use its supported resolver. The same test should work on an equivalent legacy working tree. Keep the plumbing brief’s ownership of storage, publication, branches and test scheduling.
2. **Land the wire contract and its consumers first.** It has the smallest decisive regression and removes inconsistent acceptance immediately. The class-binding work can proceed independently. Land the minimal Rust library changes through the normal CLI and preserve existing imports. Run targeted tests per change and route expensive solver replays through the repository’s existing verification workflow.
3. **Extract array induction against frozen examples.** Give one engineer freedom to work across both languages and the example adapter. First establish parity on original bytes, then remove duplicated production paths covered by those controls. Retain a truly independent oracle. If a proposed replacement decoder cannot represent an instruction, keep the validated path and record the blocker rather than narrowing the claim.
4. **Return to proving.** Deliver the two reproducers, their corrected outcomes, one real consumer of the extracted induction core outside its defining module, unchanged or explicitly explained historical readings, and the short ownership map. Show the number of new subprocesses per proof and the time to read 359’s archived selectors on the same machine before and after. Use a batched query so launch count stays independent of selector count. Finish once these checks pass. A Cargo workspace split, universal backend interface, complete Python-to-Rust port, new proof kernel, wider folder reshuffle or external UX redesign can each be reconsidered when a proving brief demonstrates a need.

**Evidence boundary.** The design review inspected the pinned source, ran the ordinary wire-version and multi-release-selection tests, replayed the selector and benchmark classifiers on an archived row and in-memory variants, and ran the two-JAR control on OpenJDK 21.0.13. The induction baselines are existing checked-in results. Fresh Rust, native solver, JBMC and Z3 runs belong to implementation acceptance.

[head]: https://github.com/pilifs/in-the-loop/commit/cfe2dc91681e38cb7ff17f5d39edb421e23334ba
[crate]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/Cargo.toml
[modules]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/lib.rs
[statement]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/statement.rs#L28
[spec]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/spec/mod.rs
[route]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/route.py
[recipe]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/recipes.py#L110
[qual]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/qualification.py#L149
[prior]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/llm-dlc/loops/foundation-and-python-results.md
[bench]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/benchmark/run.py#L181
[induction]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/array_induction.py
[case359]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/359-eclipse-boolean-list-insertion/records/native-selectors/fix/20261121T110735Z-f1bc304b/tasks/contents-fix/result.json
[decode]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/checker_output.py#L88
[selector]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/native_selectors.py#L201
[selector-read]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/native_selectors.py#L448
[emit]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/main.rs#L883
[regression]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/equivalence.rs#L327
[property]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/property.rs#L225
[solver]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/solvers/compare.py#L120
[ingest]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/workflow_ingest.py#L516
[helpers]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/proof_cache.rs#L813
[helper-reader]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/build.py#L1714
[reuse-test]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/tests/reuse_summaries.rs#L296
[recipes-test]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/test_recipes.py#L236
[helpers-test]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/test_build.py#L2402
[prep]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/runtime.py#L665
[jar]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/runtime_jar.py#L46
[loaded]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/java/LoadedClasses.java
[jar-test]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/test_runtime.py#L223
[guard]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/runtime.py#L1880
[cp]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/classpath.rs#L27
[cp-test]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/tests/observed_countermodels.rs#L230
[params]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/runtime.py#L1720
[loops]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/bmc/loops.rs
[r336]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/336-guava-first-array-match/records/array-induction/first-any-length/a7cc9c9463e12cdc4445/result.json
[r337]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/337-jdk-range-fill-alias/records/array-induction/caller-extra-any-length/a46b7d1d8170df9c6224/result.json
[r346]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/346-guava-long-array-holdout/records/array-induction/first-any-length/30437c63909c329614e6/result.json
[bytecode]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/classfile/bytecode.rs#L212
[induct-adapter]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/array_induction.py#L477
[workflow]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/workflow.py
[executions]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/targets/executions.py#L65
[cache]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/src/proof_cache.rs
[formats]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/examples/tools/result_format.py
[frozen]: https://github.com/pilifs/in-the-loop/blob/cfe2dc91681e38cb7ff17f5d39edb421e23334ba/lib/benchmark/organic-java/run.py#L27
