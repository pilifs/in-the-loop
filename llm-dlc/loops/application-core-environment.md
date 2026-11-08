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

- Forked 2026-11-08 after the main brief's [launch prerequisites](application-core.md#launch-prerequisites),
  Phase 0 included. No integration report yet; no open finding is in this stream's files.
- 2026-11-08, **E1, first part: the coupling policy, and a consumed primitive return under a query**:
  - **The policy, defined first** (`lib/src/environment.rs`'s documentation):
    - A deterministic read-only **query** answers with one function of its key: the same for both builds and for
      every call, any function, stateless.
    - A declared nondeterministic or fallible **choice** is a different model, refused by name until it is built.
  - **The encoding** (`effects.rs`): the query's answers come from a table of `2 × bound` keys and answers plus a
    default, passed as the generated `observe` method's inputs after the handler's, the same for both builds.
    - Each build makes at most `bound` calls, and one more marks the log. So any function on the keys the two
      builds ask for is one choice of the table: the proof covers every snapshot.
    - Every choice is a function of the key, so a counterexample is one environment. Its witness names the
      environment (`(arg0=0) gives 1, any other key gives 0`), and the JVM replays it under the stubs.
    - Shrinking reduces the table with the inputs, and the reduced case is replayed.
  - **What stays in place**:
    - A used result without a model is still refused, or unresolved where the walk can't follow the call.
    - A walk note on the model's owner is dismissed only where the owner's simple name names one class: every
      other call on that owner is a stub that marks the log.
    - Everything not encoded is refused by name (`Part::Environment`): throws (E2), DTOs (E3), String keys
      (values), field or receiver keys (objects), non-integral results, a bound outside 1 to 8.
  - **Reproducers**, in `lib/tests/environment.rs` (11 tests), on a static controller fixture that uses a rate:
    - the rewrite is proved;
    - a wrong query key, an ignored rate and an event on the wrong branch of the rate are each refuted and
      replayed;
    - keys asked for in the other order prove, and the difference taken the other way round is refuted: no
      position coupling;
    - one key asked for twice proves: functional consistency;
    - a call past the model's bound is unresolved;
    - the proof is reused exactly, another bound is a miss, and a stored refutation is replayed again;
    - `effects --environment FILE` checks under the declared model.
  - **An existing bug fixed, with its reproducer** (`the_old_builds_unresolved_mark_says_only_what_happened_in_it`):
    - The two builds' unresolved marks were offset by `tag × 16`, and bit 16 is `NULL_THROWN`. So the old build's
      unresolved reasons always included a NullPointerException it never had.
    - The tag now sits above every mark bit (`TAG = 64`), and a model's bound has a bit of its own.
    - Only the text of an unresolved result changes. No recorded output holds the spurious note.
  - **Passing inline**: `effects` (18), `environment` (11), `compare`, `foundations`, `application_core` (14) and
    the library's unit tests (228). E1 and E2 of the contract still stop at this stream's named refusal: Q's
    receiver needs the objects stream's plan, and its code the values stream's String adapter.
  - **Interface requests, for the merge** (not purely additive, in files this stream doesn't own):
    1. `main.rs`: the `--environment` help of `effects` and `compare` says "Refused until it builds them". Now a
       query of primitive keys is checked.
    2. `compare.rs`: `Options::environment`'s doc says the same. Its effort report never counts a declared
       `--environment` model as an "environment assumption" decision, though a person made it.
    3. `lib/README.md`'s effect-trace paragraph says a used result "is refused until modeled return values come".
       The paragraph added after it supersedes that, since the README takes additions only.
  - **Next**: the choice coupling (a per-call occurrence policy), which completes E1. Then E2's modelled failures:
    a `throws` result under either coupling, checked exceptions included, on the same fixture.
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
