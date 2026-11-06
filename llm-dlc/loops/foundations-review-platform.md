# Input: structural opportunities for the own checker relative to JBMC

An outside review (ChatGPT) of the repository at `7031d33`, shared at
<https://chatgpt.com/s/t_6aee3b4a30288191a791ba7eb47704bf> and extracted from that page's embedded data on
2026-11-06. It is background for [`foundations.md`](foundations.md): its sections 4 (objects across the whole proof
boundary) and 7 (stateful shared summaries) bear most on that brief. Much of its sections 2–3 is the work of
[`engine-priorities.md`](engine-priorities.md). The text is as shared, apart from this header; `genui{...}` markers are
the chat's citation markup.

---

**Yes. I would frame this as turning the native checker into a self-sufficient Java verification platform.** The existing native engine is already the strongest starting point: it owns enough Java semantics to outperform JBMC substantially on your measured integer and array workloads. The next investment should expand the range of claims that this engine can express, execute, solve, and validate.

The largest architectural opportunity is **a shared representation of Java objects and state, connected to input generation, observations, contracts, and witness replay**. Alongside that, a typed representation of proof obligations would let you retain the successful SAT backend while adding Bitwuzla where different encodings or additional theories are useful.

I reviewed the repository at [`7031d33`](https://github.com/pilifs/in-the-loop/tree/7031d336e750e3094a33b3dd6eb00c6c2900a33d). The approved [`engine-priorities.md`](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/llm-dlc/loops/engine-priorities.md) already covers the immediate measurements, initializer work, Enum/List models, and Bitwuzla experiments. I treat those as planned work. The recommendations below extend that direction into a replacement strategy, without assuming anything about the additional capabilities you will share.

## 1. Where I would invest, ranked

There are two useful rankings here: **what removes JBMC use soonest**, and **what creates the most future capability**. Migration and a connected group of missing Java features lead the first ranking. Objects, state, and typed solver terms lead the second.

| Priority | Investment | Expected return | Relative effort |
|---|---|---|---|
| **1** | Move already eligible workloads onto the native engine, including legacy callers and defaults | Fastest reduction in actual JBMC dependence | Low to medium |
| **2** | Complete a native execution bundle: static state, selected class initialization, reference arrays, and model constructors/instance methods | Closes demonstrated gaps and makes Enum/List work useful to the native engine | Medium to high |
| **3** | Build a common bounded object domain: symbolic references, aliasing, heap observations, construction, and replay | Largest expansion in the kinds of Java methods and contracts you can verify | High |
| **4** | Introduce typed terms and integrate Bitwuzla behind the existing execution semantics | Enables different encodings and floating point; makes the solver a replaceable component | Medium to high |
| **5** | Add bounded strings and the common library semantics needed by target applications | Broadens applicability to ordinary application and library code | Medium to high, depending on scope |
| **6** | Extend relational checking and summaries to stateful code | Makes larger before/after checks tractable without repeatedly expanding unchanged behavior | High, with substantial reuse from earlier work |

This is an investment ranking, not a requirement to finish each row before starting the next. In particular, the object representation and typed-term design should be coordinated, while delivering small, usable capabilities throughout.

### Why the evidence supports this direction

In the recorded benchmark, the native engine was faster on all 98 strict cases that both engines decided correctly. The three strict cases decided only by JBMC were application class-initialization cases. Floating point, demonstrated separately by example 035, is another concrete native coverage gap. These are useful distinctions: some remaining dependence comes from missing Java semantics, while the native engine already has a strong encoding for its existing fragment. [Recorded benchmark and interpretation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/llm-dlc/loops/engine-priorities.md)

That argues for preserving the native engine’s compact primitive arrays, lazy arithmetic, sharing, and refinement machinery. A new platform should retain those optimizations as one effective way to lower Java operations into solver obligations. The current implementation already contains valuable infrastructure in [`bmc/bits.rs`](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/bmc/bits.rs), rather than merely delegating everything to CaDiCaL.

## 2. First remove dependency that no longer buys capability

Before adding substantial semantics, distinguish **“this workload uses JBMC”** from **“this workload requires JBMC.”**

There is still operational coupling in the repository:

- Relevant CLI commands default to JBMC.
- The example build machinery defaults B9/B11 checks to JBMC unless configured otherwise.
- Box Office’s existing Java verification route is specifically tied to JBMC.
- Native results are still converted into a `JbmcResult` representation internally.

Those are separate from the native engine’s actual verification capabilities. [CLI defaults](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/main.rs), [example orchestration](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/examples/tools/build.py), [native result conversion](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/bmc/mod.rs)

The already planned inventory of 41 recorded JBMC examples should therefore produce a **migration table**, as well as a gap table. For each obligation, distinguish:

1. The native engine can represent the claim.
2. It obtains the required result under the same domain, observations, bounds, and gap policy.
3. The application actually selects it.
4. The workload passes in an environment where JBMC is absent.

The fourth step is particularly valuable. An `auto` fallback can make a system appear independent while retaining a hard dependency in ordinary operation.

I would graduate workloads in groups, change their routing from measured evidence, and maintain a test configuration without JBMC installed. JBMC can remain useful as an optional comparison engine during development.

A common result type is also a sensible cleanup: the core should produce a verification result with engine provenance, and the JBMC adapter should translate its output into that type. This is modest architectural work, but it puts the dependency at the edge of the platform.

## 3. The first capability bundle should be complete native execution of enums and small immutable lists

The immediate semantic work has a useful, concrete shape. Static fields, class initialization, reference arrays, and executable library models reinforce one another.

### A model file alone does not currently remove the dependency

The native engine’s model execution policy is asymmetric:

- For a static method, it can execute a model’s bytecode body.
- For constructors and instance/interface calls, the corresponding execution path accepts application bytecode, then falls back to classified JDK handling. Model method bodies do not receive the same general treatment.

Consequently, adding an `Enum` constructor or a `List` implementation can improve JBMC and the concrete interpreter while leaving the native engine blocked. A static factory might become executable, only to encounter an unsupported constructor, reference array, or instance method inside it. [Native invocation handling](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/bmc/mod.rs), [model execution documentation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/models/README.md)

For dependency removal, I would define the deliverable as **“native checking of the relevant Quorum obligations”**, with the necessary features included:

- Static-field state and the selected class-initialization semantics.
- Reference-array allocation, reads, and writes.
- Execution of model constructors and instance/interface methods.
- The required Enum and immutable-list behavior.
- Relevant exceptional behavior and observable identity behavior.
- Conformance against the JVM.
- Strict native results for the targeted obligations.

This gives the work a coherent finish line.

### Why this bundle comes before arbitrary object graphs

You can implement much of this while retaining the current representation of known allocated objects. An enum instance or a small list allocated by a model is substantially easier than an arbitrary symbolic object supplied as an input.

That makes this a useful intermediate stage: it broadens the engine without requiring the entire future heap architecture at once.

The initializer census in the approved plan remains the right way to choose the first scope. If constant tables and enums dominate, start there. If initialization failure is included, its subsequent-use behavior must be represented too; JVM initialization has persistent state, including failure state. genui{"citation":{"ref":"turn9779953view1"}}

For the replacement roadmap, I would strengthen the existing acceptance criteria: examples 013 and 071 should eventually obtain their expected results **through the native engine**, with the same claims and strict policy. The current brief explicitly leaves native use of these models conditional, so that additional exit criterion matters. [Approved model and initializer scope](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/llm-dlc/loops/engine-priorities.md)

## 4. The largest architectural investment: objects across the whole proof boundary

The native checker already supports objects allocated during execution, fields, application calls, exceptions, and dispatch on known receiver classes. “Add object support” would therefore be an inaccurate description of the work.

The important extension is **from known objects to bounded symbolic object states**, and from primitive observations to meaningful observations of those states.

### Where the current boundary lies

References are currently represented as a known object index or null: `Val::R(Option<usize>)`. Reference values merge when they agree, and heap merging requires compatible shapes. That works well when execution determines which object a reference denotes. It does not directly represent a symbolic choice among several objects in a merged state. [Native values, objects, and merging](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/bmc/mod.rs)

The surrounding verification interface is similarly restricted:

| Dimension | Current boundary | Useful extension |
|---|---|---|
| Inputs | Primitives, fresh non-null primitive arrays, records flattened into primitive components | Nullable references, aliases, richer records, bounded object graphs |
| State | Known allocated objects and fields | Symbolic reference choices and state updates through those choices |
| Observations | Return values, exception categories, primitive input-array contents | Selected reachable fields, reference relationships, declared static effects |
| Properties | Scalar expressions and supported array/flattened-record expressions | Object paths, object predicates, state snapshots, effect conditions |
| Witnesses | Construction and replay for the supported primitive domain | Java construction recipes preserving object identity and aliasing |

These are documented boundaries in the [statement schema](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/statement.rs), [harness generation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/harness/mod.rs), [property expressions](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/harness/expr.rs), and [JVM witness support](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/jvm_witness.rs).

The current claims are explicitly scoped to their supported domains. Expanding these domains is a capability increase, not a correction to every existing proof.

### Build one domain description that several components can use

I would invest in a common description of:

- Allowed object types and object-count bounds.
- Nullability and permitted aliasing.
- Fields and array elements that belong to the input state.
- Constructors or factories used to create admissible inputs.
- State that the claim observes.
- The relationship between the initial states of the two program versions.

The symbolic executor, harness generator, contract tester, witness reconstructor, shrinker, and JVM replay machinery should all consume that description.

Otherwise, these components will develop subtly different ideas of an input. For example, the solver might find a counterexample where two parameters refer to the same object, while the replay code creates two separate objects. That witness would describe a different execution.

Constructor constraints also matter. Arbitrarily assigning fields does not necessarily produce a state an application can construct. A practical first implementation can support constructor- or factory-generated states, with that restriction stated in the domain. Broader graph generation can follow when needed.

### Before/after object checking needs correspondence, not equal internal IDs

The old and new implementations need corresponding initial states, with the same relevant values and alias relationships.

After execution, they may allocate different numbers of internal objects and still be equivalent. Conversely, two returned objects can have equal field values while differing in an observable alias relationship.

The comparison should therefore be defined over declared observations:

- Which reachable values agree?
- Does a returned reference still refer to the corresponding input object?
- Were selected input objects mutated equivalently?
- Were relevant static effects equivalent?
- Did the same category of exceptional outcome occur?

Requiring equality of internal heap indices would be meaningless across separate executions. Requiring complete equality of all internal allocations would unnecessarily reject valid transformations.

### Stage the implementation deliberately

I would build this in increasing order of complexity:

1. **Known objects and reference arrays**, sufficient for the initial model bundle.
2. **Nullability and aliasing for bounded inputs**, starting with simple types and richer immutable records.
3. **Mutable object graphs with explicit observed fields and footprints.**
4. **Cycles and broader polymorphism**, when real workloads justify them.

Preserve the cheap representation for known references. A symbolic reference can use a finite choice of object identities without forcing every ordinary reference operation through the most general machinery.

Likewise, avoid committing immediately to one universal heap encoding. Small explicit arrays of fields may outperform SMT arrays at the bounds you commonly use. Larger or more symbolic workloads may benefit from `select`/`store` terms. The representation should have room for both, with measurements deciding where each is used.

**This investment has unusually broad returns:** it improves native coverage, object contracts, model verification, counterexample quality, and ordinary application-method eligibility together.

## 5. Replatform the solver boundary around typed terms

The second major foundation is separating Java execution semantics from the representation consumed by a particular solver.

Today, the native engine’s `Bits` representation and Boolean DAG are closely connected to its bit-level encoding. That is an effective implementation for the current fragment, but a narrow SAT interface alone does not preserve the higher-level structure needed for a meaningful SMT comparison. [Current encoding machinery](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/bmc/bits.rs)

I would aim for two distinct representations:

**Java state and execution semantics**

This layer handles values, references, fields, arrays, dispatch, exceptions, initialization, and bounds.

**Typed symbolic terms**

This layer retains operations on booleans, fixed-width integers, floating-point values, references, and arrays long enough for different backends to lower them appropriately.

The current SAT backend can continue to bit-blast those terms, including its existing lazy operations and lemmas. Bitwuzla can receive suitable operations as bit-vector, array, or floating-point expressions.

This does not require replacing the entire engine in one change. Introduce typed operations around selected workloads, preserve the existing lowering, and expand only when the abstraction earns its place.

### Why Bitwuzla is a useful second architecture

Bitwuzla supports bit-vectors, floating point, arrays, uninterpreted functions, and combinations of these theories. Those capabilities align with several concrete gaps and encoding questions in this repository. genui{"citation":{"ref":"turn2345171view0"}}

I would fund two complementary backends:

- **The existing SAT path**, preserving the demonstrated performance on integral and small-array workloads.
- **Bitwuzla**, for word and array representations, and as the basis for floating-point support.

The approved transcript capture is important because the checker makes many incremental queries. The comparison must preserve that interaction pattern; the final formula alone is not the whole workload. [Planned solver experiment](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/llm-dlc/loops/engine-priorities.md)

Initially, select a backend for a complete obligation. Combining independently solved fragments inside one proof introduces additional composition requirements and should follow a demonstrated need.

Additional solvers become attractive when they provide a specific capability or solve a substantial recurring failure class. A growing list of interchangeable SAT engines would have a weaker connection to the dependency-removal goal.

### Floating point is a concrete capability milestone

Example 035 gives floating-point work an immediate acceptance case. It is also relatively separable from arbitrary mutable object graphs. [Example 035](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/examples/035-nan-compared-with-equals-turns-fcmpl-into-fcmpg/README.md)

However, integrating SMT floating point does not complete Java floating-point semantics automatically:

- Java comparison instructions have specified NaN behavior.
- Floating-point-to-integer conversions require Java’s handling of NaN and out-of-range values.
- Java `frem`/`drem` do not have the same definition as IEEE remainder, so a direct translation to SMT `fp.rem` is insufficient.
- SMT conversion operations can be unspecified in cases where Java requires a particular result. genui{"citation":{"refs":["turn2345171view1","turn2146648view1"]}}

I would start with bytecode arithmetic, comparisons, and conversions. Broader `Math` methods should be separate model work.

The capability also needs an observation and replay policy. The current real-JVM witness route accepts integral and boolean scalar/array types, so floating-point support must extend that route alongside symbolic execution. [JVM witness implementation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/jvm_witness.rs)

That produces a complete feature: a floating-point claim can be expressed, checked, and—when false—demonstrated on the JVM.

## 6. Own the library semantics that your workloads actually need

A general symbolic bytecode executor still encounters the semantics of library methods. This is where targeted ownership can expand coverage while keeping formulas manageable.

The repository already has a useful foundation: Java models compiled into bytecode, model-aware classpath resolution, and a contract library with several proved primitive contracts. Preserve and extend that machinery. [Model architecture](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/models/README.md), [contract library](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/models/contracts/README.md)

I would support two routes:

- **Executable model bodies** for behavior small enough to expand efficiently.
- **Semantic summaries** for behavior that can be justified and reused without expansion.

Both should describe their supported domain and observable behavior. Object summaries will additionally need effects and frame conditions: what they read, what they can change, and what they leave unchanged.

The current contract prover restricts its general proof route to static primitive signatures. Extending that meaningfully depends on the object-domain and observation work described above. [Contract proving boundary](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/contract_proving.rs)

### Strings are likely to be the next broad capability multiplier

After the initial enum/list bundle, bounded strings are a strong candidate for application-facing coverage:

- String-valued record fields and method parameters.
- Equality and prefix/suffix conditions.
- Parsing and validation.
- Concatenation and substring transformations.
- Collections of immutable values.

Their priority relative to floating point should follow the upcoming workload inventory. For parser, configuration, and security-related methods, strings may unlock much more code.

The representation should preserve Java’s UTF-16 code units, including sequences that cannot be represented faithfully by a conventional Unicode scalar-value string. Java indexing operates in code units, and supplementary characters occupy two positions. genui{"citation":{"ref":"turn2345171view2"}}

A bounded string can initially be modeled as a length and sequence of 16-bit values. That fits naturally with existing array reasoning. It can later acquire specialized encodings or summaries where justified.

The richer concrete interpreter is useful implementation material, but independent JVM conformance should remain the semantic reference. Sharing code between the symbolic engine and interpreter can reduce maintenance; it also reduces their independence as checks on one another.

### Use real library investigations to choose the next models

The archived investigations provide useful acceptance workloads:

- **Commons Codec Hex decoding** exercises character classification and supporting library semantics.
- **Jackson’s division-by-1000 transformation** is a useful test of arithmetic representation.
- **Commons Numbers power operations** exercise arithmetic and bounded iteration.

These are candidates for testing the architecture against real code, not predictions of a particular solver’s performance. [Commons Codec investigation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/examples/109-commons-codec-43a9aa66-hex-decoding-restricted-to-ascii/example.json), [Jackson investigation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/examples/108-jackson-core-1203-division-by-1000-as-multiply-and-shift/example.json), [Commons Numbers investigation](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/examples/105-commons-numbers-223-pow-of-minus-two-to-the-31/example.json)

## 7. Invest in the capability that particularly suits this product: relational verification

One of the strongest reasons to own the platform is that your central workload includes comparing program versions.

The repository already exploits this. `shared.rs` recognizes suitable unchanged code and abstracts identical pure primitive callees using shared behavior, with replay and refinement when an abstract counterexample is spurious. This is a valuable starting point for scaling verification. [Existing shared-callee machinery](https://github.com/pilifs/in-the-loop/blob/7031d336e750e3094a33b3dd6eb00c6c2900a33d/lib/src/shared.rs)

I would extend this after the heap and observation foundations are in place.

### Extend sharing from pure values to stateful behavior

An unchanged helper can sometimes be summarized once for both versions. For stateful code, however, equal scalar arguments are insufficient. The helper may read a field that the two callers have modified differently.

A reusable stateful summary needs:

- Its relevant input values and heap reads.
- Its writes and unchanged-state guarantees.
- Exceptional outcomes.
- Relevant allocation and reference relationships.

The relational checker can then establish that the two calls receive corresponding relevant state before sharing their behavior.

This is potentially a larger performance opportunity than changing SAT engines. It can avoid constructing duplicated reasoning about large unchanged computations and focus the proof on changed behavior and its effects.

### Make summary reuse sensitive to the claim

A summary proved under one set of bounds or model assumptions should carry those conditions. Reuse should account for the callee and relevant call graph, model versions, input domain, observed effects, and applicable bounds.

That also creates a route toward useful compositional verification without immediately taking on unrestricted theorem proving.

The distinction matters: a bounded callee result does not become an unbounded method contract merely because it is stored and reused. The platform should retain enough information to compose the claim it actually established.

## 8. Define replacement milestones in terms of completed workloads

I would use a small set of milestones to keep the replatform effort connected to dependency removal.

| Milestone | What it demonstrates |
|---|---|
| **Existing native-capable workload group runs without JBMC installed** | Operational dependency has actually been removed |
| **Selected initializer cases and Quorum 013/071 run natively with their expected strict results** | Static state, reference arrays, and model execution work together |
| **Example 035 runs natively, with JVM validation of the counterexample** | Floating point works across execution, solving, observation, and replay |
| **Methods with nullable and aliased object inputs can be checked and replayed** | The object domain is usable beyond internally allocated objects |
| **A real string/library workload works natively** | Models and bounded object values unlock application-facing coverage |
| **A larger change benefits from a stateful shared summary** | The platform can scale through composition as well as encoding improvements |

For each milestone, measure the same meaningful obligation: domain, observations, bounds, gap policy, and required evidence. A smaller domain or an assumed model can make a check complete, but it is a different result from replacing the previous capability.

Performance evaluation should also grow beyond the current small bounds. Increase array lengths, object counts, alias choices, and relevant call depth to see where a representation starts to deteriorate. Preserve the existing benchmark as a fixed baseline.

As semantic ownership grows, independent validation becomes more important. Two solvers consuming the same incorrect Java translation can agree. JVM conformance tests and replay address a different layer of correctness from solver agreement. Counterexample replay is especially valuable, while successful proofs also require confidence in the encoding and its modeled domain.

## 9. What I would leave outside the first replacement programme

I would keep the initial target focused on bounded verification of the workload families you actually use.

The following should require a concrete demand before becoming major projects:

- General Java concurrency and the Java Memory Model.
- Arbitrary reflection, dynamic class loading, JNI, and native libraries.
- A complete JDK implementation.
- General quantified invariants and unbounded deductive proofs.
- A new SAT or SMT solver.
- Recreating CBMC’s general-purpose intermediate infrastructure.

These are substantial, partly independent programmes. Replacing the JBMC capabilities you use does not require implementing a production JVM’s garbage collector, JIT, or every runtime service; the JVM specification itself separates its abstract behavior from implementation choices. genui{"citation":{"ref":"turn9779953view0"}}

Recognized dynamic-call patterns, particular library families, or limited concurrency models can still be added when the workload justifies them. The important discipline is to attach each expansion to a useful claim and an explicit semantic scope.

**I would make the next major milestone an independently usable native verifier for a defined set of Java workloads.** Complete the common execution bundle first, establish the shared object/domain and typed-term foundations, and use those foundations to deliver floating point, strings, and stateful summaries in measurable increments.

The additional capability work you share may change which application-facing feature comes next. It is much less likely to change the value of owning those common foundations: they determine whether new features reduce JBMC dependence across the whole system or merely add another partially supported path.

---

If you want, I can:

- Suggest next concrete investments for expanding native engine
- Outline a staged implementation plan for symbolic object support
- Explain integration strategy for Bitwuzla alongside existing SAT backend
