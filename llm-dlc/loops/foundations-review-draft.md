# Input: a review of the draft foundations briefs

An outside review (ChatGPT) of the first draft of [`foundations.md`](foundations.md) and its four stream briefs, shared
at <https://chatgpt.com/s/t_6aee447b99ec8191a1197561f7f76fbb> and extracted from that page's embedded data on
2026-11-06. It reviews the briefs against the vision in [`foundations-review-vision.md`](foundations-review-vision.md),
not the repository. The briefs were revised after it; [Review of the draft](foundations.md#review-of-the-draft) in the
main brief says what changed. The text is as shared, apart from this header; `fileciteturn…` and `citeturn…`
markers are the chat's citation markup, pointing at the draft briefs and at its web sources.

---

**I would keep the four-agent split and the overall direction, but amend the briefs before launching.** The plan translates the vision into bounded engineering work rather than attempting a general application verifier all at once. Its strongest choices are explicit provenance, strict handling of gaps, replayed witnesses, and keeping inferred relationships separate from developer intent. fileciteturn0file0L31-L49

My main concern is that **the streams’ minimum completion criteria do not guarantee the combined experience you actually want**. Several essential integration capabilities sit outside the stated core phases, and the joint demonstration can count as finished merely by explaining what prevented it from running. There are also a few semantic ambiguities worth resolving before four agents independently encode different interpretations. fileciteturn0file0L220-L229

This is a review of the five attached briefs against the vision in our conversation—not a fresh audit of the repository at `e42ea83` or the referenced `engine-priorities` implementation.

## 1. The vision is right; make the acceptance target more concrete

The main brief makes an important distinction: this iteration builds four foundations, not the entire product. Deferring collections, stateful summaries, distributed refinement, and control-flow alignment is sensible. I would not expand that scope. fileciteturn0file0L25-L36

However, I would give the iteration a more specific product outcome:

> **For one bounded application change, automatically propose the internal correspondence, prove preservation of a fixed set of externally meaningful observations, expose every unsupported part, and reuse applicable evidence on subsequent changes.**

The word **fixed** matters. The tool should be free to discover how two implementations correspond internally. It should not be free to redefine what counts as preserved external behavior merely because a different comparison is easier to prove.

This also sharpens your low-input ambition:

**Automate the proof machinery and representation matching; ask people about genuine changes in meaning.**

The existing `candidate → validated → pinned` distinction points in that direction. The next step is making that distinction constrain the actual verification workflow, rather than only the report. fileciteturn0file0L38-L45

## 2. The biggest semantic issue: inference must not “explain away” a regression

The alignment brief accepts a candidate as validated when its regression proof succeeds and is not vacuous. It correctly acknowledges that a wrong mapping accepted by a proof is a particularly bad outcome. fileciteturn0file1L21-L37

**Non-vacuity is necessary, but it is nowhere near sufficient to establish a meaningful preservation claim.** CBMC’s documentation describes the basic vacuity problem: inconsistent assumptions can empty the state space and make assertions pass. Your problem extends beyond that to satisfiable but inappropriate relationships. citeturn247709search0

Consider this deliberately simple hypothetical change:

```java
// Before
long price(long cents) {
    return cents;
}

// After — an unintended regression
long price(long cents) {
    return cents + 1;
}
```

An inferred input mapping could propose:

```text
before.cents = after.cents + 1
```

Under that mapping, the return values agree. The relation is non-vacuous. Under Java’s fixed-width arithmetic, it even covers the whole input space bijectively.

But it does **not** establish preservation for a consumer making the same request.

The same problem can occur when an inferred output relation compensates for a defect, or when the selected observation projection excludes the field that changed incorrectly.

The briefs already recognize the distinction between mathematical validation and intent. What is missing is an operational rule:

> **Automatic correspondence inference may change internal representation, but it may not change the externally anchored input meaning, required observations, or accepted behavior without explicit authorization.**

### What I would add to Phase 0 and A3

Give each comparison an explicit **preservation contract**, containing the external input domain and required observations. Infer internal mappings underneath that contract.

For an unchanged HTTP operation, for example, both versions should receive inputs derived from the same logical request. A proposed internal object mapping must be consistent with those derivations; it must not independently shift the meaning of the request.

For a standalone method without such an external anchor, the honest result can be:

> “This relationship is proved. Whether it is the intended replacement relationship remains unconfirmed.”

That is still useful, but it is different from automatically approving the refactor.

I would also require an **observation-accounting check**: every previously required observation is preserved, explicitly approved as changed, or unresolved. A mapping cannot silently remove an obligation from the denominator.

### Separate intent state from proof state

The proposed hints format puts `candidate`, `validated`, and `pinned` into one lifecycle. fileciteturn0file0L178-L184

I would represent at least two independent dimensions:

| Dimension | Example states |
|---|---|
| Intent | Proposed, developer-approved |
| Evidence | Unchecked, proved for claim key X, refuted, unknown, stale |

A developer can pin a relationship **before** it is proved. A pinned relationship can later be refuted. A previously validated relationship can become stale when either implementation changes.

Keep the existing terminology in the interface if helpful, but do not let “pinned” imply “proved,” or let “validated” survive independently of its exact claim key.

One smaller improvement: A3 currently asks whenever several candidates prove. Before asking, attempt to collapse candidates that are demonstrably equivalent under the fixed preservation contract. Otherwise the tool may ask users to choose between expressions with no observable difference. fileciteturn0file1L30-L46

## 3. Four agents are appropriate—but the shared contract needs more than types

The ownership boundaries and the instruction to keep shared-file changes as small hooks are good. Waiting for the `engine-priorities` merge also avoids overlapping changes to the symbolic execution core. I would retain both decisions. fileciteturn0file0L122-L146

The risk is **semantic integration**, not merely merge conflicts.

### The current “core phases” stop short of the joint result

| Stream | Currently designated core | Additional capability needed for the intended joint demonstration |
|---|---|---|
| Heap | H1–H3 | H4’s identity-preserving replay and H5’s different-shape correspondence |
| Summaries | S1–S3 | A narrow S4 case to demonstrate composition across changed code, rather than only exact-result caching |
| Observations | O1–O2 | O3: actually discharge an entry-point obligation |
| Alignment | A1–A3 | A4: propose the field relationship consumed by H5 |

Those distinctions are explicit in the stream briefs. fileciteturn0file2L35-L48 fileciteturn0file4L37-L50 fileciteturn0file3L37-L47 fileciteturn0file1L39-L48

As written, each agent could make substantial, legitimate progress and stop without producing the combined capability.

**I would keep each stream’s broad scope, but make one narrow contribution to the shared example mandatory.** That is preferable to requiring every optional phase in full.

### Move the joint example’s definition into Phase 0

Phase 0 currently establishes types, documentation, serialization tests, and example-number reservations. fileciteturn0file0L168-L189

Add a small executable integration contract:

- One before/after fixture and a defective sibling.
- Golden examples of the domain, observations, correspondence, and normalized claim.
- Agreed producer/consumer interfaces.
- Expected final verdicts and explicit intermediate unsupported results.

The implementations can initially return a named unsupported result. The important thing is that all four agents know **exactly the same target** before they start.

In particular, resolve the recording-stub interface before the fork. The observations brief currently defers any required harness changes to the heap owner at merge time. That makes O3’s most important integration point arrive very late. fileciteturn0file3L55-L63

### Add an integration check before the final reconciliation

I would use a coordinator-owned, disposable integration workspace to combine immutable stream snapshots and run the shared fixture during development. The agents can retain their prohibition on merging or rebasing their own branches.

The purpose is to detect disagreements such as:

> Alignment emits a relation that the heap engine interprets differently, or observations produces an effect kind the harness cannot record.

These should not first appear after all four agents have stopped.

Also distinguish **process stopped**, **waiting on verification**, and **accepted complete**. The briefs allow agents to stop while jobs are pending, while reconciliation begins after the scopes are inactive. The orchestration needs an explicit rule that inactivity alone does not establish completion. Every result should identify the immutable code snapshot and configuration it checked. fileciteturn0file1L82-L87 fileciteturn0file0L161-L164

One wording correction before launch: the repeated instruction “Don’t edit … anything outside this file’s `## Progress` section” can be read as prohibiting implementation edits. Change it to:

> “Within this brief, edit only `Progress`. Edit implementation files according to the ownership rules.”

That removes an unnecessary ambiguity for autonomous agents. fileciteturn0file2L12-L15

## 4. Heap: preserve the narrow scope, but tighten what the claim means

The heap stream is well targeted: symbolic references, explicit aliasing, bounded construction, observable fields, and replayable object identities. I would keep the concrete-reference fast path and avoid pulling collections or general polymorphism into this iteration. fileciteturn0file2L21-L45

Three details need clarification.

### Constructor-generated states are not all valid entry states

Constructor/factory inputs are a practical default because they provide a concrete construction recipe. But they can describe a much narrower domain than the objects a method receives in normal use.

For example:

```java
class Account {
    long balance;

    Account() {
        balance = 0;
    }

    void deposit(long amount) {
        balance += amount;
    }
}
```

Constructing `Account` and immediately checking a method only covers `balance == 0`. It does not cover accounts after deposits.

The main brief recommends constructor/factory construction as producing reachable states. That is a useful starting point, but it must not become an implicit completeness claim about reachable states. fileciteturn0file0L250-L257

I would label the initial domain precisely:

> “Objects generated by these constructors/factories under these argument constraints.”

Later, the domain can support bounded initialization sequences or symbolic states constrained by established invariants. The distinction matters because constructor postconditions and method-entry invariants play different roles; OpenJML’s formulation explicitly requires constructors to establish invariants and methods to preserve them. citeturn247709view1

**Do not add general invariant inference now. Add the domain distinction now.**

### Primitive-field equality can miss observable alias changes

H3 defaults to reachable primitive fields and includes alias observations, with `result == input` as an example. fileciteturn0file2L35-L41

Make the alias policy explicit for nested reference paths. Consider:

```text
Before: result.left and result.right refer to the same mutable object.
After:  they refer to two distinct objects with identical field values.
```

A caller can distinguish these by mutating `result.left`. Primitive-field equality at return time does not capture that difference.

You do not need to compare physical object identities across versions. You need to compare relevant **within-version identity relationships**, such as:

```text
old.result.left == old.result.right
    iff
new.result.left == new.result.right
```

Which relationships matter depends on the boundary. They may matter for a Java API returning mutable objects but not for a wire response whose declared observation is only serialized values.

That boundary-dependent policy belongs in the observation specification, not in an implicit universal default.

### Replay must arrive with object inputs

I would not let H2/H3 reach accepted completion while H4 remains optional. The main brief requires replayed witnesses, and object aliasing is precisely where reconstruction mistakes could undermine a counterexample. fileciteturn0file0L38-L39

Likewise, specify how bounds work across different representations. Wrapping a primitive in a value object increases the object count without necessarily changing behavior. Distinguish input-object bounds from execution-allocation bounds, and permit explicit before/after bounds where needed.

Exhausting a bound must either restrict the clearly stated claim or produce an unresolved result—not silently truncate observations while retaining a broader verdict.

## 5. Summaries: distinguish exact-result caching from compositional reuse

This is the stream I would tighten most after alignment.

The cache’s conservative rules are good: unknown key material makes a claim uncacheable; refutations are replayed on reuse; unverifiable results are not stored as reusable conclusions. fileciteturn0file4L21-L32

But two architectural distinctions matter.

### Hash a canonical claim, not an entire evolving result record

The brief recommends digesting the serialized `Statement` so newly added fields automatically affect the key. The main brief also describes `Statement` as carrying provenance, assumptions, observations, and vacuity. fileciteturn0file4L64-L65 fileciteturn0file0L92-L94

The intent is right: do not maintain a fragile hand-written list that forgets new semantic fields.

However, a raw whole-record digest risks including result-dependent or incidental fields: run identifiers, proof status, validation evidence, and eventually reuse provenance. Some may not exist until after checking.

I would define a **canonical claim projection from the existing schema**, not introduce a competing specification system:

```text
Claim semantics and assurance requirements
    → canonical claim key

Claim key + verdict + evidence + run provenance
    → result record
```

The key should include every validity-relevant dependency, while excluding incidental reporting metadata.

Perform lookup only after flags, hints, inferred mappings, models, and generated observations have been resolved into that normalized claim. “One call at the start” must mean the start of checking a prepared claim, not before its meaning is known. fileciteturn0file4L55-L65

### Dependency closure needs adversarial invalidation tests

S1 covers reachable bytecode, class layouts, initializers, and models. That is a good basis. fileciteturn0file4L21-L25

I would add tests for changes that need not alter an already-hashed method body:

| Change | Required behavior |
|---|---|
| A new possible dispatch target | Recompute the relevant resolution dependency or refuse reuse |
| A framework annotation/configuration change used by the claim | Invalidate the claim |
| A constructor/factory or input-domain policy change | Invalidate the claim |
| A recording-stub or observation-policy change | Invalidate the claim |
| A dependency proof’s assumptions change | Recheck applicability |
| The verifier binary changes without a package-version bump | Do not mistake it for the same checker |

Also verify that the existing `shape` representation is suitable as a **semantics-preserving fingerprint**, not merely a similarity representation. The briefs do not establish that property; it needs checking against the code.

### S4 needs an explicit applicability obligation

The plan already says a reused callee proof must cover the caller’s domain and bounds. Make that operational: the caller must establish the callee summary’s preconditions for the **actual pair of arguments and states at that call site**. This is the standard modular-verification obligation, not merely a comparison of numeric bounds. fileciteturn0file4L37-L43 citeturn247709search4

For this iteration, I would restrict shared proved callees to a deliberately narrow class: pure, deterministic helpers with compatible input semantics and equal observable outcomes, including supported exceptional outcomes. A general relation between differently represented outputs cannot automatically be implemented by assigning both calls the same equal-output stub.

Require acyclic proof dependencies unless a separate recursive proof rule exists. A caller’s proof cannot ultimately justify the callee summary that justified the caller.

Finally, make one narrow S4 example mandatory. **A warm rerun of identical artifacts demonstrates caching; it does not demonstrate that major refactors become cheaper.** A changed helper proved once and reused in a caller is much closer to the economic claim you want.

## 6. Observations: call logs are valuable, but they are not persistence semantics

The observation stream makes a useful distinction between static obligation discovery and discharging those obligations. It also explicitly identifies recording stubs as assumptions. Keep that. fileciteturn0file3L21-L44

The main amendment is to define exactly what a recorded effect means.

A stub recording:

```text
store.save(order)
```

establishes that the application attempted that modeled call with that observed payload. By itself, it does not establish a committed database state, successful delivery, transaction atomicity, or eventual processing.

For O3, I would deliberately choose a narrow contract:

> **Preserve an ordered trace of modeled boundary-call attempts, together with the response and supported failure outcome, under an explicit environment model.**

That is useful and implementable without prematurely building the deferred effect-transition system.

Three details should be in the brief.

**Environment behavior must be coupled explicitly.** A store read, client call, or broker operation may return values or fail. The before and after versions cannot receive arbitrary unrelated outcomes and still be treated as executions in the same environment. Nor should both simply receive “success” unless that restriction is stated.

**Payload observations must be snapshots.** Recording a reference and inspecting it after later mutation can change the apparent payload of an earlier event. Record the declared observed values at the event point.

**Trace bounds and observation completeness must be visible.** A log that overflows cannot silently discard effects. An unresolved boundary cannot vanish from the observation specification. An unchanged payload type cannot by itself discharge preservation of payload values.

The ordering policy should also be explicit. Exact trace order is a reasonable first version; it may reject some harmless reorderings, but that is preferable to quietly assuming effects commute.

Finally, distinguish a JVM replay **under modeled dependencies** from replay against real infrastructure. The former is a strong check of the counterexample within the declared abstraction, not evidence that the database or broker model is complete.

## 7. Make the joint demonstration the acceptance gate

The current Phase 5 is directionally right, but “if the code is behind an entry point” makes observations optional, and “record what stopped it” permits the milestone to finish without integration. fileciteturn0file0L207-L218

I would use **a small Crosscut-style kernel behind one thin, real annotated entry point**. That preserves the recommended kernel’s simplicity while requiring the observation stream to participate.

The fixture should combine a primitive amount becoming a value object, an internal method or field mapping, one changed pure helper, and one recorded outgoing effect. The external request meaning and required observations remain fixed.

The accepted end-to-end result should demonstrate:

| Requirement | Evidence |
|---|---|
| Automatic mapping | Alignment proposes the internal relationship without a hand-written mapping for this fixture |
| Object correspondence | The relationship is checked over the declared bounded domain |
| Boundary preservation | The same required response/effect observations are proved |
| Exact reuse | An unchanged rerun reuses the result |
| Compositional reuse | The changed helper’s established equivalence is used in a caller |
| Defect detection | A defective sibling produces a replayed counterexample |
| Honest incompleteness | An unsupported case remains visibly unresolved |

A blocked integration is a legitimate stopping point for an agent run. It should be recorded as **partial milestone completion**, not the same success state as a working demonstration.

### Add defects aimed at the verifier’s abstractions

The planted-defect rule is already a strength. Extend it beyond straightforward application mistakes to defects that challenge the inferred specification and reuse mechanisms. fileciteturn0file0L109-L120

The most valuable cases are an offset mapping that hides a changed result; an alias-to-copy change with identical primitive values; a dropped or duplicated effect; a state outside the constructor-generated domain; and a stale cached result after a relevant metadata or model change.

These tests ask a more important question than “can the checker find this bug?”:

> **Can any automation layer accidentally redefine, narrow, or reuse the claim so that the bug disappears?**

### Measure change economics, not only warm-cache speed

S6 already measures cold, warm, and one-method-change runs. Make the one-method change semantically categorized rather than arbitrary. fileciteturn0file4L44-L48

Distinguish an unrelated edit, a behavior-preserving helper rewrite, a representation change, and an actual regression. Report preparation/hashing time separately from solver time, and distinguish exact cache hits from reused callee evidence.

For low-input measurement, count not only manually written mapping lines but also user-approved exclusions, domain restrictions, observation changes, and environment assumptions. Otherwise the reported effort can look excellent while the human work has merely moved into another category.

## My decisions on the open questions

The brief asks for five choices before execution. My recommendations are:

| Decision | Recommendation |
|---|---|
| Start timing | **After the `engine-priorities` merge.** Keep the clean ownership boundary. |
| Object construction | **Constructor/factory by default**, with the generated-state domain explicitly reported and no claim to cover all valid object states. |
| Cache location | **Local, uncommitted.** Persist portable claim/evidence identities, but defer a shared proof store. |
| Joint test bed | **A small kernel behind one real entry point.** Neither a kernel-only demonstration nor a broad Box Office verification attempt. |
| Agent configuration | Keep your established configuration for this run. Add the integration and acceptance controls above rather than changing models as part of the same experiment. |

These address the choices listed in the brief without bringing the deferred capabilities back into scope. fileciteturn0file0L250-L263

## Bottom line

**This is a good foundation plan, but I would change the acceptance contract before changing the scope.**

The three most important amendments are:

1. **Anchor inference to a preservation contract it cannot weaken.**
2. **Require one working four-stream example, with its interfaces and fixture defined before the agents fork.**
3. **Make domain coverage, summary applicability, and cache identity executable checks rather than prose expectations.**

I would retain the deferrals around distributed refinement, general collections, and stateful summaries. I would also keep “independently checkable obligations” distinct from independently checked proofs of successful verdicts: JVM witness replay validates refutations, while the supplied acceptance criteria do not establish an independent certificate-checking path for successes. That is a scope distinction, not a reason to add another major workstream now. fileciteturn0file0L13-L17 fileciteturn0file0L220-L229

The result worth aiming for is not four impressive subsystems. It is **one meaningful application change whose preservation argument the tool assembles automatically, whose limitations it cannot hide, and whose evidence makes the next change cheaper to verify**.
