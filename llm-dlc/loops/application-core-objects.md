# Stream brief: application core, objects and lifecycle inputs

One of four streams of [`application-core.md`](application-core.md) that run in parallel, each in its own jj
workspace on its own branch. The others are [`application-core-values.md`](application-core-values.md),
[`application-core-environment.md`](application-core-environment.md) and
[`application-core-reuse.md`](application-core-reuse.md). Once all four are finished, the main brief's loop merges
them ([Reconciling](application-core.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh application-core` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh application-core-objects` from this stream's workspace
(`jj workspace root --name application-core-objects`). The loop refuses any other.

**The main brief is the instruction.** Read [`application-core.md`](application-core.md) and the acceptance contract
[`application-core-acceptance.md`](application-core-acceptance.md) in full every cycle, with their inputs. Their
direction, starting point, working rules, safety rules, deferrals and decisions all apply here. This file says which
items are yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section. Edit
implementation files according to the main brief's [ownership](application-core.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/application-core-integration.md`, if it exists. A failure
in your files on the latest combined commits is your next piece of work, and a conflict in a file you own is a
coordination task: record it under Progress, don't work around it.

## Goal

Check the instance methods developers actually write, with explicit bounded construction and replay. Cover a small
state domain beyond the values right after the constructor.

## Starting evidence

Recounted in the main brief's [Where it starts from](application-core.md#where-it-starts-from). In short:
- `equivalence.rs` takes an instance receiver only when it is a record of primitive components, and refuses ordinary
  non-record receivers;
- `property.rs` refuses non-static targets;
- ordinary constructor-made application parameters already exist. Extend that capability; don't build a second heap
  system.

The documented object inputs flatten primitive constructor leaves and refuse array constructor arguments. Phase 0's
domain-validation audit is the gate. It doesn't license reinterpreting unsupported policies.

## Your items

In order, with acceptance rows O1–O3 of the [contract](application-core-acceptance.md#mandatory-rows).

### O1. One construction path for receivers and parameters (required)

- Use the existing construction semantics to support an ordinary non-null receiver, in both regression
  (`equivalence`, `compare`) and property (`prove`) checks. Keep `this` a named root for field observations and for
  the argument aliases the plan allows. A nullable invocation target, if one is ever modelled, is a property of the
  call site, never a target receiver that is silently nullable.
- Generalize a constructor's leaves from primitives to bounded primitive arrays:
  - keep the array nullability and aliasing choices the plan explicitly allows;
  - keep copies apart between the before and after heaps, without breaking sharing within one version.
- Add only narrow selection machinery: the existing unambiguous constructor, or one explicitly selected
  constructor or factory descriptor.
  - Ambiguous constructors are a named choice, never a guess.
  - A factory must have a supported body, modelled or executable, and its dependencies enter the claim.
  - Broad factory inference is optional.
- Feed the common plan through `equivalence`, `prove` and `compare`. Alignment consumes the new layout through its
  existing thin interface. Don't weaken external anchoring or rewrite alignment.

### O2. Construction, snapshots and replay agree (required)

- Represent construction as a typed bounded DAG with stable node ids. The same node reused at two argument or field
  paths means one object, not two equal copies. A reference choice inside a nested object is supported only where
  the construction recipe can realize it; otherwise it is refused.
- Snapshot these through the existing observation system: receiver mutations, parameter mutations, the relevant
  nested identities, and results. Rebuild exactly those identities on the real JVM.
- Shrinking checks that the new recipe is still legal and still reproduces the same failure.
- Use the values stream's String and list adapter for construction and replay. Don't add separate representations
  of those values to the witness layer.
- Register every constructor, factory, model and setup method used as a claim root, for reuse.

Required negative controls:
- a receiver returned as a copy;
- an array defensively copied before, but leaked after;
- two parameters that were one object becoming distinct;
- unsupported side effects in a constructor;
- a narrower new constructor under an externally anchored input domain.

### O3. A short explicit setup sequence (required, narrow)

- Support a fixed sequence of one or two setup method calls with symbolic arguments, before the target. The
  sequence is selected, bounded and serialized. There is no search over histories and no invariant inference.
- Both versions start from corresponding constructions and get the same logical setup inputs.
  - Setup outcomes and effects are compared when externally visible.
  - Alternatively, an explicitly stated setup-only domain may hide them, and is then never reported as preserving
    the full history.
  - An input one version rejects is never silently dropped from an anchored compatibility claim.
- The witness is the constructor or factory, then the setup calls, then the target call. The claim names that exact
  domain. Zero-step and one-step claims are distinct, and neither result can pass for the other.
- Model it on the existing constructor-only defect pattern (example 195): a defect that is absent right after
  construction becomes reachable after a setup call, and must be refuted with the whole history replayed.

### Optional, after the core

One more unambiguous factory route, or a bounded construction of reference arrays that the values stream needs.

Out of scope: wider inheritance, cycles, arbitrary field-by-field states, deserialization semantics, and unrestricted
sequences of public methods.

## Ownership and cooperation

- **Yours**: the construction and sequence code, `harness/`, `spec/heap.rs`, `equivalence.rs`, `property.rs`, and the
  plumbing for object witnesses, replay and shrinking.
- **Not yours**:
  - values owns `bmc/`, the interpreter's and the models' semantics, and its value adapter;
  - environment owns the effect harness rewriting;
  - reuse owns the cache implementations.

  Apply only the agreed prepared-claim hook in `property.rs`, not a second cache.
- Ask the coordinator, through Progress, for a change to a shared schema or registration file.
- Put your tests in a stream-specific file. Don't edit generated indexes or another stream's fixture variants.
- Example numbers 240–249.

## Acceptance

- O1 and O2 pass for both regression and property checks, with JVM replay and correct identity observations.
- A receiver with a primitive-array constructor is accepted without a hand-written application adapter.
- O3 finds the defect that only a history reaches, and labels its coverage precisely.
- Each of these changes the claim or makes it uncacheable: a construction descriptor, the setup order, a setup
  argument domain, nullability, aliasing, or a bound.
- The combined quote and lifecycle fixtures (Q and H) exercise this stream's real interface.

## Working rules

The main brief's [How to work through it](application-core.md#how-to-work-through-it): the pipeline and the two-failure
timebox. Queue proofs, and record each job's revision and id. When a core item depends on another stream and is
blocked, say so under Progress, and keep it visible through acceptance. Meanwhile, work on independent fixtures.
Never relax the interface to unblock it.

## Progress

- Not started. Forks after the main brief's [launch prerequisites](application-core.md#launch-prerequisites),
  Phase 0 included.
- Status: working

## Loop settings

- session: 3ba3cc03-2dbc-4a1f-ac36-a1cc13b778a9
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: application-core-objects
- fork: 3da21514-fe46-49d5-8200-08d3cf89ea17

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when O1–O3 and your share of the combined acceptance pass, or each is
deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream,
and is recorded under Progress. Optional construction work must not delay the core or grow into a heap project.
Anything new you find goes under Progress, for the main brief's for-review list.
