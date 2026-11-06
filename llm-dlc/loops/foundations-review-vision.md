# Input: toward zero-spec verification of complex Java applications

An outside review (ChatGPT), shared at <https://chatgpt.com/s/t_6aee3bd0baf88191a6cbe904afbd94d3> and extracted from
that page's embedded data on 2026-11-06. It reviews the repository as it stood then and sets out the product vision
that [`foundations.md`](foundations.md) works toward; its section 9 is the source of that brief's four priorities. The
text is as shared, apart from this header. Its interface markup (`<box>`, `<Cite>`, `<Link>` and the like) is the
chat's own and is kept as it came; the proposed formats in it (the hint YAML, the effect-transition IR, the
`compare` command) are its proposals, not features of this repository.

---

# Toward zero-spec verification of complex Java applications

After reviewing the latest `in-the-loop` repository, I think there is a much bigger opportunity here than making relational checking support increasingly sophisticated Java objects.

**The opportunity is to turn a before/after code change into a collection of automatically generated, independently checkable proof obligations — with the developer supplying intent only where the change genuinely introduces new semantics.**

That would move `jvmcontract` from a method-level verification tool toward something resembling a **continuous refinement verifier for real applications**.

The experience I'd work toward:

> Give the tool two revisions of a complex backend application. It discovers the behavioral contracts, establishes what remains equivalent, identifies the intentional changes, and proves that the new implementation preserves the old guarantees wherever they still apply.

No JML everywhere. No requirement to hand-author a complete TLA+ model. Ideally, no annotations for routine refactoring.

There is an important distinction, though: the old implementation can serve as a specification for *preservation*, but it cannot establish whether newly introduced behavior is *correct*. I would design the entire product around minimizing that remaining specification gap.

## 1. What your repository already makes possible

The latest `lib/README.md` describes substantially more than a conventional before/after method checker:

- Relational equivalence across renamed methods, reordered arguments, changed return representations, and primitive-component records.
- Shared-callee abstraction, with unchanged pure callees treated as the same symbolic function.
- A native symbolic checker with SAT-based bit-vector reasoning, path merging, and refinement of expensive arithmetic.
- Spring Boot boundary contracts covering HTTP routes, wire types, stored types, transactions, exceptions, messaging, configuration, and reachable effects.
- TLA+ generation from behavioral contracts, with TLC integration.
- Explicit gap accounting, assumption provenance, vacuity detection, and independently replayed counterexamples.

That last cluster is particularly important. You already have the foundation for distinguishing **what was proven** from **what the verifier simply assumed**.

Your current native checker still supports a relatively constrained object fragment: primitive-component records and primitive arrays, while general reference objects, aliasing, and complex heaps remain future work. <Cite refs={["turn305164view0","turn393557view0","turn393557view1","turn393557view2"]}/>

I see three especially valuable existing foundations:

| Existing capability | Potential next-level capability |
|---|---|
| Relational method checking | Relational application and service checking |
| Boundary/effect discovery | Automatic observable-behavior specifications |
| TLA+ models from contracts | Automatic abstraction and refinement obligations |

The key is to connect these into one verification workflow rather than continually expanding each independently.

## 2. The central idea: prove observable behavior, not implementation equivalence

Imagine replacing a Spring Boot service that uses imperative Java, MongoDB, and Kafka with a reactive implementation backed by PostgreSQL.

The implementations might share almost no internal structure.

Trying to establish equivalence across every allocation, field assignment, method call, and intermediate state would be unnecessarily expensive, and often impossible.

Instead, define an observation function \(O\) that captures externally relevant behavior:

\[
O(P,x)=
(\text{responses},\text{events},\text{persistent effects},\text{errors})
\]

For a conventional refactor, the central obligation becomes:

\[
\forall x \in D:
O(P_{\mathrm{before}},x)
=
O(P_{\mathrm{after}},x)
\]

For a system that introduces new features, this becomes a refinement or compatibility relation rather than equality.

The crucial innovation is that **much of the observation function can be derived from compiled bytecode, annotations, framework configuration, and dependency behavior**.

Your new boundary analysis is already a first step toward this.

### What I would automatically observe

| Boundary | Generated proof obligation |
|---|---|
| HTTP | Same responses, status codes, and relevant side effects for preserved API behavior |
| Database | Equivalent logical records after an operation |
| Messaging | Same required events and payload semantics, with explicit ordering guarantees |
| Transactions | Preserved atomicity and failure behavior |
| Exceptions | Equivalent externally visible failures |
| Authorization | No unintended expansion of allowed operations |
| Distributed state | Preserved invariants across modeled interleavings |

Not every internal difference matters.

Changing the number of database queries may be acceptable. Changing a payment amount is not. Replacing an immediate event with an eventually delivered event might be acceptable, but only under an explicit delivery contract.

This suggests a foundational abstraction:

**A relational proof should compare the behaviors that consumers can observe, under a clearly stated environment model, rather than demanding identical internal execution.**

That is where the dramatic reduction in verification cost could come from.

## 3. Build an automatic specification inference pipeline

I'd make specification discovery a first-class subsystem, separate from the symbolic execution engine.

Rather than asking developers to write properties, collect evidence from several sources and synthesize candidate obligations.

<box border radius="xl" padding={3} gap={2}>
  <text weight="medium" size="sm">Proposed verification architecture</text>
  <box background="surface-secondary" radius="lg" padding={3} align="center" gap={1}>
    **Before and after artifacts**

    <text color="secondary" size="xs">Bytecode · Git diff · Framework metadata · Config · Tests</text>
  </box>
  <row justify="center">
    <icon name="arrow-down" color="tertiary" size="lg"/>
  </row>
  <box background="rgba(45,109,185,0.08)" border={{size:1,color:"rgba(45,109,185,0.24)"}} radius="lg" padding={3} align="center" gap={1}>
    **Semantic discovery and matching**

    <text color="secondary" size="xs">Methods · Objects · Schemas · Entry points · Effects · State transitions</text>
  </box>
  <row justify="center">
    <icon name="arrow-down" color="tertiary" size="lg"/>
  </row>
  <box background="surface-secondary" radius="lg" padding={3} align="center" gap={1}>
    **Relational specification IR**

    <text color="secondary" size="xs">Input mappings · State relations · Observations · Assumptions · Temporal properties</text>
  </box>
  <row justify="center">
    <icon name="arrow-down" color="tertiary" size="lg"/>
  </row>
  <grid columns={2} gap={2}>
    <grid-item>
      <box border radius="md" padding={2} align="center" gap={1}>
        <icon name="git-compare" color="secondary"/>
        <text weight="medium" size="xs" textAlign="center">Relational symbolic execution</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={2} align="center" gap={1}>
        <icon name="network" color="secondary"/>
        <text weight="medium" size="xs" textAlign="center">TLA+ / temporal model checking</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={2} align="center" gap={1}>
        <icon name="shield-check" color="secondary"/>
        <text weight="medium" size="xs" textAlign="center">Contract and invariant checking</text>
      </box>
    </grid-item>
    <grid-item>
      <box border radius="md" padding={2} align="center" gap={1}>
        <icon name="activity" color="secondary"/>
        <text weight="medium" size="xs" textAlign="center">Trace validation and replay</text>
      </box>
    </grid-item>
  </grid>
  <row justify="center">
    <icon name="arrow-down" color="tertiary" size="lg"/>
  </row>
  <box background="rgba(35,130,85,0.08)" border={{size:1,color:"rgba(35,130,85,0.24)"}} radius="lg" padding={3} align="center" gap={1}>
    **Evidence-backed change report**

    <text color="secondary" size="xs">Proven preservation · Intended differences · Counterexamples · Unresolved gaps</text>
  </box>
</box>

I would explicitly distinguish four sources of inferred specifications.

| Source | What can be inferred | Confidence |
|---|---|---|
| Bytecode semantics | Exact local behavior, effects, exceptions, arithmetic | High when fully modeled |
| Framework conventions | Routes, transaction boundaries, serialization, binding | Depends on resolved runtime configuration |
| Previous implementation | Behavior that should remain unchanged | Exact preservation target, not necessarily correct behavior |
| Tests, documentation, LLMs | Candidate invariants, intended exceptions, mappings | Hypotheses requiring validation |

This distinction matters enormously.

An LLM can propose that a checkout operation should never debit an account twice. The verifier may be able to prove this property, but it cannot automatically establish that the proposed property faithfully captures the product requirements.

I would therefore treat LLM-generated specifications as **untrusted suggestions** and solver-checked evidence as the authoritative result.

## 4. The biggest technical investment: relational heap semantics

Your current focus on complex objects is probably the highest-leverage next investment for the core checker.

But I would aim beyond simply adding support for `List`, `Map`, and arbitrary Java classes.

**The real goal should be proving relationships between two differently structured heaps.**

Consider an application that originally represents an order as:

```java
class Order {
    long totalCents;
    List<LineItem> items;
}
```

After refactoring:

```java
record Order(
    Money total,
    Map<String, LineItem> itemsBySku
) {}
```

A naïve equivalence checker fails immediately. The objects have different types, allocation structures, and access patterns.

But the logical relationship is simple:

\[
R(o_{\mathrm{old}},o_{\mathrm{new}})
\iff
\begin{cases}
o_{\mathrm{old}}.totalCents =
o_{\mathrm{new}}.total.cents\\
\operatorname{bag}(o_{\mathrm{old}}.items)=
\operatorname{bag}(o_{\mathrm{new}}.itemsBySku.values)
\end{cases}
\]

The multiset comparison assumes SKU uniqueness is not important to the old representation; if uniqueness is a required invariant, it must be included explicitly.

The user shouldn't have to write this relation in most straightforward cases.

### I would build five capabilities together

1. **Symbolic object graphs.** References, nullable fields, symbolic allocation, inheritance, arrays of references, aliasing, and heap mutation.
2. **Heap correspondence.** Two different references can represent the same logical entity, even when their physical layouts differ.
3. **Field and collection projections.** Derive logical observations from objects, including record components, getters, nested properties, and recognized collections.
4. **Frame reasoning.** Prove which portions of the heap are unchanged, so the verifier doesn't repeatedly analyze irrelevant data.
5. **Relational state mappings.** Automatically propose transformations between old and new representations, then prove obligations under those mappings.

The critical feature is number five.

The research on <Link url="https://www.sciencedirect.com/science/article/pii/S1567832610000354" title="Relational bytecode correlations"/> is especially relevant: it develops a formal system for relationships between bytecode programs, including objects, virtual calls, and heap-local reasoning. <Cite ref="turn360687search3"/>

### An important optimization: don't compare full heaps

Suppose an operation mutates 15 objects, but only two fields eventually affect a persisted order.

A complete heap equivalence proof may be expensive or simply wrong as a specification.

A better analysis:

- Determines which objects and fields are observable.
- Performs backward slicing from those observations.
- Tracks only the required heap relations.
- Abstracts the remaining heap through sound summaries or frame conditions.

This suggests a useful internal concept: a *relational footprint*.

For each externally visible operation, compute the subset of reachable state required to explain the observed behavior.

That would make complex-object reasoning considerably more scalable than merely increasing the maximum size of symbolic object graphs.

## 5. Transient annotations should be proof hints, not permanent developer obligations

I particularly like your idea of a transient annotation system.

I would avoid making JML-style source annotations the default interface. Instead, generate machine-readable verification hints outside the source tree.

Imagine the tool discovers that a large refactor has changed a record representation. It infers a correspondence but needs a single decision.

A generated file might look like this:

```yaml
# Proposed verification hints, not a current jvmcontract format
version: 1

change:
  before: OrderService.placeOrder
  after: CheckoutService.submit

inputs:
  mapping: inferred

state:
  correspondence:
    - before: Order.totalCents
      after: Order.total.cents
    - before: Order.items
      after: Order.itemsBySku.values
      relation: multiset-equality

observations:
  - http.response
  - persisted.Order
  - emitted.OrderPlaced

assumptions: []
```

The verifier would generate this, validate the mapping, and attempt the proof.

Most such files could be ephemeral build artifacts. Only the genuine semantic choices would need to become persistent contracts.

I would give inferred hints a distinct lifecycle:

<box gap={2}>
  <row align="center" gap={2}>
    <badge color="secondary">Candidate</badge>
    <text size="sm">Derived from source, bytecode, or an LLM; not yet established</text>
  </row>
  <row align="center" gap={2}>
    <badge color="secondary">Validated</badge>
    <text size="sm">Its consistency and relevant proof obligations have been checked</text>
  </row>
  <row align="center" gap={2}>
    <badge color="secondary">Pinned</badge>
    <text size="sm">Developer-approved intent, retained for future changes</text>
  </row>
</box>

A validated mapping is not necessarily a validated correctness requirement. That distinction should remain explicit.

This creates a compelling interaction model:

**The tool proposes the equivalence relationship; the developer only intervenes when intent cannot safely be inferred.**

One warning: a mapping that excludes all relevant states can make a proof vacuous. You already detect vacuity in local proofs; extend that discipline to relational heaps, state mappings, and generated protocol assumptions.

## 6. Compositional verification is where application-scale economics change

Even with a powerful native symbolic checker, repeatedly verifying a whole backend from scratch is unlikely to scale.

The real cost reduction comes from avoiding work.

Your shared-callee optimization is an early form of this idea. I would generalize it into persistent, reusable summaries.

Suppose a service contains:

- 250 application methods.
- 35 changed methods.
- 12 changed entry-point effects.
- 4 changes that cross service boundaries.

You shouldn't have to symbolically execute all 250 methods to prove each of the four externally visible changes.

Instead, prove smaller relationships and reuse them.

<box border radius="lg" padding={3} gap={2}>
  <text weight="medium" size="sm">Example: compositional proof graph</text>
  <svg viewBox="0 0 340 178" width="100%" xmlns="http://www.w3.org/2000/svg">
    {#each [{x:60,y:40},{x:170,y:40},{x:280,y:40}] as p}
      <rect x={p.x-46} y={p.y-22} width="92" height="44" rx="9" fill="#64748b" fillOpacity=".12" stroke="#64748b" strokeOpacity=".65"/>
    {/each}
    <rect x="110" y="112" width="120" height="44" rx="9" fill="#16a34a" fillOpacity=".12" stroke="#16a34a" strokeOpacity=".75"/>
    <g stroke="currentColor" strokeOpacity=".48" strokeWidth="1.6" fill="none">
      <path d="M60 62 L142 112"/>
      <path d="M170 62 L170 112"/>
      <path d="M280 62 L198 112"/>
    </g>
    <g fill="currentColor" fontSize="10" textAnchor="middle">
      <text x="60" y="35">Payment</text><text x="60" y="48">summary</text>
      <text x="170" y="35">Inventory</text><text x="170" y="48">summary</text>
      <text x="280" y="35">Pricing</text><text x="280" y="48">summary</text>
      <text x="170" y="130" fontWeight="600">Checkout contract</text><text x="170" y="143">relational proof</text>
    </g>
    <g fill="currentColor" fillOpacity=".6" fontSize="9" textAnchor="middle">
      <text x="170" y="171">Each dependency is verified or has an explicit assumption</text>
    </g>
  </svg>
</box>

Each node should have a reusable summary describing:

\[
\{\text{Precondition}\}
\quad
f
\quad
\{\text{Postcondition, Effects}\}
\]

Or, more powerfully, a relational summary:

\[
R_{\mathrm{in}}(s_0,s_1)
\Longrightarrow
R_{\mathrm{out}}(f_0(s_0),f_1(s_1))
\]

### Three opportunities for major savings

**A. Summary reuse across commits**

If a method and all its relevant dependencies retain the same semantics and assumptions, reuse its verified summary.

A prior proof should become an input to the next proof.

**B. Incremental proof repair**

If one dependency changes, invalidate only proofs that depend on its affected semantics.

The existing research on <Link url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10564826/" title="SMT-based verification through summary repair"/> is directly relevant. It demonstrates an order-of-magnitude improvement on its benchmark by incrementally repairing reusable summaries rather than re-verifying everything. That isn't a performance prediction for Java, but it's strong evidence for the direction. <Cite ref="turn360687search12"/>

**C. Automatic relational alignment**

When two versions have different control flow, discover correspondence points: equivalent loop states, calls, fields, or effects.

For example, an old loop and a new stream pipeline can share an invariant without taking identical execution paths.

The alignment itself needs verification; matching source patterns alone is insufficient. <Cite ref="turn360687search13"/>

These capabilities have compounding value. More expensive proofs become worth doing because they can be reused across hundreds of subsequent changes.

I would prioritize this persistent proof graph alongside heap semantics, rather than waiting until object support is complete.

## 7. For distributed systems, generate models of effects, not models of code

This is where I would deliberately separate the verification approach from general symbolic JVM execution.

Your existing boundary analysis can identify that an HTTP operation:

1. Reads an order from a database.
2. Updates an order.
3. Publishes an event.
4. Returns a response.

That is not yet a distributed-system model, because it says little about ordering, concurrency, retries, crashes, and delivery guarantees.

But it gives you the ingredients for generating one.

### Introduce an effect-transition intermediate representation

Instead of directly producing TLA+, first transform bytecode and framework information into a small, structured transition system.

For example:

```yaml
operation: Checkout.submit

reads:
  - Order
  - Inventory

transitions:
  - reserve_inventory
  - create_order
  - enqueue_payment

atomic:
  - reserve_inventory
  - create_order

emits:
  - PaymentRequested

failure_points:
  - before_commit
  - after_commit
  - before_publish

properties:
  - inventory_never_negative
  - payment_requested_at_most_once
```

Again, this is a proposed internal representation, not an existing repository feature.

The first four sections are partially discoverable from program analysis and framework semantics. The properties require separate justification: they may originate from existing specifications, business requirements, trusted protocol templates, or developer approval.

Then generate a TLA+ model from the IR.

That model would be much smaller than the full Java implementation, and potentially much more useful for reasoning about asynchronous behavior.

### The essential additional step: prove the connection

There are two fundamentally different verification results:

- The generated model satisfies a property.
- The implementation actually conforms to that model.

The first doesn't establish the second.

I would generate refinement obligations connecting concrete code effects to abstract transitions.

For an operation \(C\) implementing abstract transition \(T\), a simplified safety obligation is:

\[
R(s,a)\land C(s,s')
\Longrightarrow
\exists a':
T(a,a')\land R(s',a')
\]

Here \(R\) relates the application's concrete state to its abstract state.

In practice, the relation must also account for intermediate internal steps, atomicity boundaries, and observable events. For concurrent systems, proving a suitable forward simulation or linearizability relation is more demanding than proving an isolated handler correct.

This provides a path to **compositional implementation-to-model verification**.

For a Spring application, an early version could focus on deterministic decision kernels, transaction boundaries, and message emission conditions. Expanding to full event-driven execution would require explicit models of the brokers, transactions, and failure environment.

### Use multiple complementary engines

I wouldn't make TLA+ the universal intermediate language.

- **Native relational checker:** precise Java behavior, state mutations, safety assertions.
- **TLC:** finite-state protocol exploration and interleavings.
- **<Entity category="software" value="Apalache" disambig="symbolic model checker for TLA+"/>:** SMT-backed reasoning over finite-state TLA+ models, including induction-oriented safety checks.
- **Trace validation:** evidence that actual execution follows permitted modeled behavior, without falsely equating sampled executions with proof.

Apalache is worth exploring because your growing SAT/SMT experience is directly relevant, although its guarantees and supported domains differ from the native checker. <Cite refs={["turn360687search0","turn360687search9"]}/>

For implementation-to-model trace validation, the research behind <Link url="https://arxiv.org/abs/2404.16075" title="Validating Traces of Distributed Programs Against TLA+ Specifications"/> is highly pertinent. It instruments Java executions and checks recorded traces against TLA+ specifications. This supplies an additional validation layer, not a universal implementation proof. <Cite ref="turn360687academia36"/>

## 8. The experience I'd aim to deliver

A developer runs a single command on a major refactor:

```bash
jvmcontract compare \
  --before main \
  --after HEAD \
  --scope application
```

The tool builds both revisions, discovers entry points and state, proposes mappings, reuses previous proof artifacts, and executes the remaining obligations.

The report might look like this:

<box border radius="xl" padding={3} gap={3}>
  <row align="center" justify="between">
    <box gap={1}>
      <text weight="medium">Checkout service refactor</text>
      <caption>Illustrative verification report</caption>
    </box>
    <badge color="warning">Review required</badge>
  </row>
  <grid columns={3} gap={2}>
    <grid-item>
      <box background="surface-secondary" radius="lg" padding={2} gap={1}>
        <text color="success" weight="medium" size="xs">Proven</text>
        <title size="xl" color="default" tabularNums>87</title>
        <caption>Obligations</caption>
      </box>
    </grid-item>
    <grid-item>
      <box background="surface-secondary" radius="lg" padding={2} gap={1}>
        <text color="danger" weight="medium" size="xs">Refuted</text>
        <title size="xl" color="default" tabularNums>2</title>
        <caption>Obligations</caption>
      </box>
    </grid-item>
    <grid-item>
      <box background="surface-secondary" radius="lg" padding={2} gap={1}>
        <text color="secondary" weight="medium" size="xs">Unresolved</text>
        <title size="xl" color="default" tabularNums>6</title>
        <caption>Obligations</caption>
      </box>
    </grid-item>
  </grid>
  <box gap={1}>
    <row align="center" justify="between">
      <text size="sm">Proven obligations</text>
      <text size="xs" color="secondary" tabularNums>87 / 95</text>
    </row>
    <box height="10px" direction="row" clip radius="full" background="surface-tertiary" gap={0}>
      <box width="91.58%" background="rgba(27,136,86,0.8)"/>
      <box width="2.11%" background="rgba(201,72,72,0.85)"/>
      <box flex="1" background="rgba(148,163,184,0.65)"/>
    </box>
  </box>
  <divider color="subtle"/>
  <box gap={3}>
    <row align="start" gap={2}>
      <icon name="check-circle-2" color="success"/>
      <box flex="1" gap={1}>
        **Order pricing preserved**
        <text color="secondary" size="sm">All 64-bit values · exact arithmetic semantics</text>
      </box>
    </row>
    <row align="start" gap={2}>
      <icon name="check-circle-2" color="success"/>
      <box flex="1" gap={1}>
        **Persistence mapping preserved**
        <text color="secondary" size="sm">Old record and new document agree under the validated state mapping</text>
      </box>
    </row>
    <row align="start" gap={2}>
      <icon name="x-circle" color="danger"/>
      <box flex="1" gap={1}>
        **Payment event duplication**
        <text color="secondary" size="sm">Counterexample: commit succeeds, publish retries, duplicate event emitted</text>
      </box>
    </row>
    <row align="start" gap={2}>
      <icon name="circle-help" color="secondary"/>
      <box flex="1" gap={1}>
        **New cancellation behavior**
        <text color="secondary" size="sm">Requires an intended-behavior contract; no previous equivalent operation</text>
      </box>
    </row>
  </box>
</box>

The numbers and results above are hypothetical, but the design objective is concrete: a developer should see **what was proven, what changed, and what needs human judgment** without understanding SAT solvers or formal logic.

### Ask questions only at semantic boundaries

The verifier shouldn't interrupt to ask how to map `Order.totalCents` to `Money.cents` when the equivalence can be checked automatically.

But it should ask when the implementation now permits cancellation after payment authorization and the previous version did not.

The developer might answer:

> Cancellation after authorization is intentional, provided it always triggers a refund.

That one statement becomes the seed of a new contract.

An LLM can translate it into candidate assertions and temporal properties. The system then verifies them against the proposed implementation, with unresolved assumptions surfaced explicitly.

The result is a useful feedback loop:

**Code change → inferred obligations → proofs → minimal intent clarification → permanent verified contract.**

## 9. What I would prioritize building

Here is how I would allocate engineering effort, based on the current repository rather than an entirely greenfield verifier.

| Priority | Investment | Why |
|---|---|---|
| 1 | Relational heap and object correspondence | Unlocks real Java domain models and structural refactors |
| 2 | Compositional summaries and proof caching | Makes repeated verification economically viable |
| 3 | Automatic entry-point observations | Moves checking from methods to application behavior |
| 4 | State-mapping and relational alignment inference | Reduces developer-written specifications |
| 5 | Structured effect-transition IR | Bridges implementation verification and TLA+ |
| 6 | Selective transient specification generation | Adds automation without increasing trusted assumptions |
| 7 | Implementation-to-model refinement checking | Supports increasingly strong distributed-system claims |

I'd actually develop priorities 1–4 in parallel, because each makes the others dramatically more useful.

And I would not begin with a full distributed-system verifier.

## 10. The experiment I'd run next

Your Box Office sample is almost perfectly suited to this research direction. It already contains Spring Boot services, Kafka, MongoDB, behavioral contracts, and a TLA+ model. <Cite ref="turn113758view0"/>

I'd create a major refactor benchmark with three transformations, increasing in difficulty.

<box gap={3}>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" size="44px" align="center" justify="center">
      <icon name="boxes" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Experiment A — Domain representation refactor**

      Replace records and primitive-centric structures with richer object hierarchies, collections, and value objects. Preserve behavior.

      <text color="secondary" size="sm">Success: automatically infer the state relation and formally establish equivalent observable outcomes across the supported domain.</text>
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" size="44px" align="center" justify="center">
      <icon name="database" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Experiment B — Persistence and service refactor**

      Split an operation into new methods, change its persistence representation, and reorganize service boundaries without changing logical business behavior.

      <text color="secondary" size="sm">Success: prove preservation of logical state and observable effects without requiring individual method equivalence.</text>
    </box>
  </row>
  <divider color="subtle"/>
  <row align="start" gap={3}>
    <box background="surface-secondary" radius="lg" size="44px" align="center" justify="center">
      <icon name="network" size="lg"/>
    </box>
    <box flex="1" gap={1}>
      **Experiment C — Distributed protocol refactor**

      Replace direct message publication with a transactional outbox and retries. Permit implementation-level differences while requiring the agreed logical delivery guarantees.

      <text color="secondary" size="sm">Success: verify the modeled protocol invariant, then discharge meaningful implementation-to-model proof obligations or identify precisely what remains unproven.</text>
    </box>
  </row>
</box>

For each experiment I'd introduce at least one known bug that ordinary tests are liable to miss.

Measure four things:

- **Human specification effort:** number of user decisions and manually authored contract lines.
- **Proof coverage:** proportion of relevant observable obligations discharged without unverified assumptions.
- **Verification economics:** cold-run CPU time, incremental CPU time, and reusable proof artifacts.
- **Defect detection:** whether the system finds planted defects while avoiding misleading successful verdicts.

I would also track false matches and incorrect inferred specifications. A tool that requires no input because it silently chooses a weak relation is much worse than one that asks a precise question.

The most revealing metric might be **developer minutes per successfully discharged, meaningful proof obligation**.

That is a much better optimization target than the raw count of methods supported.

## 11. Four limitations I would enforce rigorously

There are a few places where this approach could accidentally overstate its guarantees.

**First: bounded proof is not unbounded proof.** A symbolic object graph bounded to four nodes, an array of eight elements, or a TLC model with three services proves something about that modeled domain. It should not silently become a claim about arbitrary production configurations. Unbounded claims need inductive reasoning, sound abstraction, or another appropriate proof.

**Second: observational equivalence isn't automatically trivial.** Exact trace equality may reject harmless internal scheduling differences, whereas comparing only final states may miss duplicate messages, security violations, or temporary inconsistency. The abstraction must state what is hidden, what is observable, and what temporal reorderings are allowed.

**Third: the external environment becomes part of the specification.** A JVM proof of a method invoking Kafka does not itself prove Kafka delivery semantics. Framework advice, broker guarantees, transaction management, storage isolation, crash behavior, and eventual scheduling all require modeled or justified assumptions.

**Fourth: two independently incorrect implementations can be equivalent.** Relational verification is especially strong at preventing regressions. It does not replace correctness properties. That is why extracting and retaining invariants matters as much as comparing revisions.

These limitations shouldn't be treated as reasons to abandon the approach. They should become explicit parts of your proof-reporting format.

---

## 12. Where I think this could become genuinely differentiated

There's an interesting product distinction between three types of tools:

| Tool | Primary question |
|---|---|
| Traditional static analyzer | Does this implementation contain a known class of mistake? |
| Traditional formal verifier | Does this implementation satisfy a specified property? |
| Proposed `jvmcontract` evolution | What guarantees survive this change, what new behavior needs specification, and what can be proved automatically? |

The third question is particularly relevant to AI-assisted development.

An agent can rewrite a 50,000-line Java system, replace major abstractions, rearrange service responsibilities, and introduce new capabilities much faster than developers can manually audit every consequence.

A capable verifier could give both the coding agent and the human reviewer a precise picture of what remains established.

And importantly, it doesn't require the user to adopt formal methods as a development discipline beforehand.

### My preferred long-term architecture

I would make **relational change verification the principal workflow**, with specifications and invariants accumulating over time.

The first run on a mature codebase may rely heavily on before/after preservation and automatically extracted boundary contracts.

The tenth run can reuse independently checked state mappings and method summaries.

The hundredth run can reuse a growing set of explicit invariants, protocol abstractions, and refinement obligations.

That creates an unusually appealing economic property:

**The more a codebase is verified, the cheaper and stronger subsequent change verification can become.**

Not automatically — proof invalidation, changes to dependencies, and accumulated model assumptions still matter — but it gives you a clear architectural direction.

I wouldn't position TLA+ as something every developer needs to write. I'd position it as one of several backends that receives automatically derived obligations whenever the change crosses a concurrency or protocol boundary.

And I wouldn't make permanent annotations a prerequisite either. I'd start with inferred, transient relations, promote only meaningful intent to durable specifications, and retain independently checkable proof evidence.

The north-star product statement I'd use is:

> **Make it possible to radically change the implementation of a complex software system without losing the guarantees you have already established.**

That is more achievable than automatically proving that arbitrary software is correct, and potentially much more commercially useful.

Most importantly, your current project is already on a credible path toward it. The next big leap isn't simply adding more instructions or data types to the native checker. It's **building the relational state, observational, and compositional abstractions that let relatively small proofs explain very large changes**.

---

If you want, I can:

- Describe next steps for relational heap semantics
- Outline approach for compositional verification
- Expand on effect-transition IR for distributed systems
