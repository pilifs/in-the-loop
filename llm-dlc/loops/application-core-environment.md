# Stream brief: application core, dependency outcomes

One of four streams of [`application-core.md`](application-core.md) that run in parallel, each in its own jj
workspace on its own branch. The others are [`application-core-objects.md`](application-core-objects.md),
[`application-core-values.md`](application-core-values.md) and [`application-core-reuse.md`](application-core-reuse.md).
Once all four are finished, the main brief's loop merges them ([Reconciling](application-core.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh application-core` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh application-core-environment` from this stream's workspace
(`jj workspace root --name application-core-environment`). The loop refuses any other.

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

Check the decision paths of an application that uses data a dependency returns, or handles its failures. Keep the
environment contract explicit and replayable.

## Starting evidence

Recounted in the main brief's [Where it starts from](application-core.md#where-it-starts-from). In short:
- `effects.rs` records the ordered call attempts and snapshots their payloads;
- a modelled call returns normally, and a non-void result must be discarded or the check is refused;
- the generated handler is made with null dependency fields, and its calls are rewritten to recording stubs.

Keep the existing out-of-model safeguards. A null dependency must not turn into an accidental proof of runtime
behaviour.

## Your items

In order, with acceptance rows E1 and E2 of the [contract](application-core-acceptance.md#mandatory-rows).

### E1. Consumed primitive returns (required)

- Extend the environment plan and the generated stubs with symbolic integral and boolean outcomes. Their domain,
  constraints, call identity and correlation are part of the canonical claim and of the witness.
- **Define the coupling policy before implementing it.** These are different models, not interchangeable
  optimizations:
  - **A deterministic read-only query**: equal operation, receiver identity and arguments within one declared
    snapshot get consistent results. A different argument doesn't get the same value just because it has the same
    call index.
  - **A declared nondeterministic or fallible operation**: a bounded occurrence or history policy can govern the
    choices.
- Before and after see one declared environment, not two independent arbitrary streams of responses. A program that
  changes its query key shows that as a changed call or an observable consequence. Handing both versions the same
  response at position N must never hide it.
- The first model is stateless and read-only. Read-after-write database behaviour needs a separate contract for
  state transitions, and is never inferred from a method's name.

### E2. Supported modelled failures (required)

- Allow a bounded, explicit set of outcomes, normal or a throw.
  - Tell the attempted call apart from any modelled successful outcome.
  - Record the chosen exception type and any exception data the caller observes. Otherwise refuse that inspection;
    never invent a message or cause.
- Check the application's catch and propagation behaviour, and the resulting differences in status or effects. A
  newly missing catch, or an event emitted on the wrong failure branch, must be refutable.
- A modelled exception may be checked (an `IOException`, say). Phase 0's step 7 (VF-015) makes the equivalence
  harness catch the checked exceptions the two versions declare. Build on it, and ask the coordinator under Progress
  if it falls short.
- The counterexample holds the dependency choices and their correlation keys, and replays under generated
  deterministic stubs on the real JVM.
  - It is labelled replay under the model, never execution against Kafka, MongoDB or a live service.
  - Shrinking keeps the chosen model and replays the reduced case.

### E3. Constructor-made nullable return objects (required, narrow)

- Use the objects stream's common construction plan for a dependency's response with supported primitive fields:
  first one DTO, and null. String fields come later, through the values stream's adapter, with no object builder of
  the environment's own.
- Record whether repeated responses have a fresh or a stable identity under this model. Never assume either.
- The model is a DTO that carries data, not an arbitrary client object with callbacks or side effects.
  - Refuse unmodelled methods and fields, and object cycles.
  - Register in the claim: the constructors, model choices, bounds, exception policy and snapshot semantics.

### Optional, after the core

Either of these, if a fixture needs it:
- one explicitly modelled clock or random primitive, with a declared ordering and correlation policy;
- a simple finite script of responses.

Out: a transactional store model, a broker delivery model, arbitrary stateful dependencies, a concurrency scheduler,
and temporal or liveness claims.

## Observation policy

- Exact ordered traces of call attempts stay in this wave. So a performance refactor that changes calls may fail
  preservation, or need an explicitly different contract. Never hide calls automatically to make it prove.
- Snapshots capture values at the call, not an object's later contents. Running out of trace or response budget is
  unresolved.
- Checking a query result that succeeded doesn't prove committed state, delivery, retries, or an external system's
  atomicity.

## Ownership and cooperation

- **Yours**: `effects.rs`, `spec/observe.rs`, the environment plan's implementation, and the boundary
  classification changes its cases need.
- **Others' work you use**: the construction and value adapters of objects and values. Don't edit:
  - `harness/mod.rs`;
  - the native engine's internals;
  - the cache implementations.
- The coordinator owns the shared claim types and the schema registrations.
- Start on your own with a static fixture that returns a primitive. The final quote handler uses the real common
  object and String pathway, after integration.
- Example numbers 260–269.

## Acceptance

- A handler that uses a returned price or rate proves under the explicit model.
- Each of these gives a replayed refutation:
  - a wrong query key;
  - an ignored result;
  - a missing exception handler;
  - an event emitted wrongly, or dropped.
- A nullable DTO branch is covered and replayed.
- Repeated deterministic reads are functionally consistent, and different arguments are not coupled by call order.
- Changing outcomes, correlations, exception types, the response identity policy or bounds invalidates the cached
  evidence they affect.
- The result names the modelled environment and every unsupported behaviour.

## Working rules

The main brief's [How to work through it](application-core.md#how-to-work-through-it): the pipeline and the
two-failure timebox. Acceptance needs no network service. Spring annotations in the source are evidence for finding
entry points, not proof that a dependency's contract is right.

## Progress

- Not started. Forks after the main brief's [launch prerequisites](application-core.md#launch-prerequisites),
  Phase 0 included.
- Status: working

## Loop settings

- session: 73918f92-0381-4271-b3bb-48ca4e45803b
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: application-core-environment
- fork: 3da21514-fe46-49d5-8200-08d3cf89ea17

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when E1–E3 and your share of the combined acceptance pass, or each is
deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream,
and is recorded under Progress. Don't grow exact call-trace checking into a verifier of distributed systems.
Anything new you find goes under Progress, for the main brief's for-review list.
