# Acceptance contract: application core

The acceptance contract of [`application-core.md`](application-core.md) and its four streams. It sets criteria, not
results. Phase 0 freezes the exact Java fixtures and claim projections before any stream forks. Don't choose their
semantics after seeing which proof succeeds. Like the briefs, this file is not edited while the loops run.

## Small fixture families

### Q: the quote endpoint or service

Extend the existing quote fixture (`examples/apps/shop`, examples 190–196) where that is feasible.
- **The service**: an ordinary service receiver holds a primitive fee or rate policy. An explicitly bounded request
  carries a String code and a primitive-array representation of quantities.
- **What it does**:
  1. it uses a dependency's result: a normal integral value, or an explicitly modelled exception, with a separate
     variant returning a nullable DTO;
  2. it calls one heap-reading helper of the same shape;
  3. it attempts one event, with snapshotted code and amount fields.
- **What stays the same**: before and after keep the same external meaning of request and response, and the same
  exact contract on the trace of attempts. Changes to the internal layout of methods and classes may be inferred
  under that contract.
- **No list.** Don't add one to this fixture just to combine every feature.

Defective siblings can share the same source skeleton:
- the wrong query key;
- the returned rate ignored;
- an exception caught in one version but not the other;
- an event emitted on the wrong branch;
- the wrong String prefix;
- the helper reading an extra field;
- the result becoming a copy that breaks an alias where identity is required.

### H: lifecycle

A throttle or counter with a simple constructor and one or two explicit setup calls. The existing `TokenBucket`
fixture of examples 160–161 is a candidate.
- The target behaves the same right after construction, but differs after the prefix.
- The expected refutation holds the whole witness: construction, setup, target.
- A separate constructor-only claim may rightly stay verified, labelled for that domain only.

Setup effects are never silently hidden. For preservation of the whole history, compare them. For a setup-only
domain, state explicitly what is outside the observation contract.

### L: the immutable list

A small kernel takes a supported bounded immutable list of application elements, traverses it, and computes a
primitive result or returns a chosen element.
- **Covered**: empty, single and several elements; order; duplicates; aliases of mutable elements; null rejection;
  the relevant exceptions.
- **No scaffolding**: no Spring, no database.

## Mandatory rows

| ID | Requirement | Expected evidence | Owner |
|---|---|---|---|
| G0 | The cleanup merge, and the gate that validates the supported domain | The revision, and its relevant jobs passing; an unsupported domain policy refused | coordinator (Phase 0) |
| O1 | An ordinary receiver through the regression and property entry points | A correct rewrite verified, and a defect replayed | objects |
| O2 | An array-valued constructor, faithful to identity | A legal construction, and agreement between snapshot and replay | objects |
| O3 | A defect only a history reaches | The constructor-only scope labelled; the prefix-domain refutation replayed | objects |
| V1 | A symbolic String crosses the whole proof boundary | A proof and a refutation that depend on content; a field or effect snapshot; JVM replay | values |
| V2 | A bounded supported list as input | Order, duplicates and identity kept; a defect replayed; unsupported implementations refused | values |
| E1 | A consumed return value and a declared failure | The correct case verified; a wrong query and a missing catch refuted, under one explicit environment | environment |
| E2 | A nullable returned DTO | The shared construction plan and modelled replay, with no object builder of the environment's own | environment |
| R1 | The native property cache | Exact reuse of successes and refutations; replay; invalidation by assertion, domain and bounds | reuse |
| R2 | Composing a heap-reading helper | The helper's proof, checked on its own, used by a changed caller; no reuse when applicability fails | reuse |
| J1 | The quote family composes O, V, E and R | On the real combined revision, with no hand-written substitute adapter, and every old observation accounted for | coordinator |
| J2 | A run without JBMC, and a regression guard | The new native claims succeed with JBMC unavailable; unsupported confirmation explicit | coordinator |
| J3 | Cross-products of semantic invalidation | Histories, model outcomes, value bounds and helper assumptions change the right claim keys | reuse and coordinator |
| J4 | A small report on preparation and cost | Preparation, solving and replay apart; reuse implemented, or a justified finding of no change | reuse |

R4's local write summary is optional and never changes these rows. General verification of distributed models is not
a row.

**Required stream items that are not rows.** Three items each stream brief marks required have no row here:
- **V3**, semantic evidence and end-to-end model registration ([values](application-core-values.md));
- **E3**, constructor-made nullable return objects ([environment](application-core-environment.md));
- **R3**, one improvement to preparation reuse, implemented only if the evidence calls for it
  ([reuse](application-core-reuse.md)).

They are judged by [`application-core.md`'s Done when](application-core.md#done-when), per stream, not by this
table. Phase 5's for-review list, in that brief's Progress, reports them beside the rows. At the merge, all three
passed: V3 and E3 on their tests, and R3 with its justified outcome (the JDK image's class table shared within a
process).

## Adversarial checks of claim integrity

- **Inputs and outputs**:
  - a mapping cannot shift an externally anchored request to hide a defect;
  - an output projection cannot leave out a required field;
  - a new constructor that rejects inputs admitted earlier, under an anchor, cannot silently shrink the claim;
  - an ignored domain mode cannot produce a successful verdict for a different mode.
- **Bounds and keys**:
  - a bounded String or trace cannot be silently truncated;
  - a smaller bound cannot borrow a larger-sounding label;
  - a property proof cannot reuse a regression result just because the target matches.
- **Helper summaries**: a read-only summary cannot leave out a field newly read, ignore a relevant alias, or treat
  the same receiver after a mutation as the same input.
- **The environment**:
  - a deterministic dependency model is functionally consistent for equal queries in the declared snapshot, and
    never equates different queries by their position;
  - a modelled exception choice survives shrinking and JVM replay;
  - object responses need explicit semantics of identity and freshness.

## The evidence record

Each acceptance run records:
- the source revision and the identity of the compiled artifact;
- the identities of the tools and models, and the canonical claim key;
- the external contract, the domain and every bound;
- the assumptions and their evidence levels;
- the engine chosen, the verifier's verdict, the execution status and the expected outcome that applies;
- the status of the counterexample and its replay;
- the cache and summary dependencies.

A run under generated dependency stubs is labelled as such. Sampled JVM conformance is labelled tested, not proved. A
native verdict that succeeds is not independently certified just because the counterexample path has a JVM replayer.

## Measurement, deliberately limited

- At most a few small fixture families, not a campaign over held-out libraries.
- For Q, H and L, where it is relevant, compare:
  - a cold run;
  - an exact rerun;
  - an unrelated edit;
  - a safe rewrite of a helper;
  - a real defect.
- A small sweep over a length or bound is allowed, for a particular encoding decision.

No performance percentage is an acceptance target. Semantic correctness and coverage that was blocked before are.
