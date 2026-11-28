# Targets: how a real-world change is checked

This folder holds the tools that take a real-world Java change from a question to a published result. It has about
a hundred modules. This page says which route a question takes, and which module owns each step of it. For the
whole path, from a brief to a landed result, see [`ARCHITECTURE.md`](../../../ARCHITECTURE.md#how-a-change-is-proven).
To read the records an example ends with, see [*Follow the evidence*](../../README.md#follow-the-evidence).

Everything is reached through one dispatcher, [`build.py`](../build.py): its usage text lists every command.

## Which route

| You have | Route | Ends with |
|---|---|---|
| A numbered example with a target sidecar (`target.json`): a frozen claim about a method, to be proved or refuted | [A numbered target](#a-numbered-target) | A receipt per task and attempt, under `receipts/<task>/<execution>/` |
| Two deployments of an application or library (before and after an upgrade or change), and public questions a caller would ask | [A change plan](#a-change-plan) | A plan report: each claim's status, its bindings, its open dependency, and what a later run may reuse |
| A finite public caller to run on both original JVM deployments, with no checker | [A public JVM observation](#a-public-jvm-observation) | Recorded observations for each registered history, matched against the predictions |

A question may need more than one route. A numbered task can use the checker **and** an original-JVM control, and a
change plan can hand a claim to a numbered target.

## A numbered target

The claim lives in `claims/*.json` ([schema](../../schema/target-claim.schema.json)). The tasks, the revisions, the
preparation and the independent controls live in `target.json` ([schema](../../schema/target.schema.json)).
Example [338](../../338-commons-io-bom-reset/README.md) is the one to read first.

```
target.json ──► plan_task ──► route.run ──► controls and checker ──► qualification ──► workflow.ingest ──► receipt
  (task, claim)   (frozen)     (execution)    (runtime.py)             (replay, binding)   (format 2)        (result.json)
```

1. **Plan.** `build.py --plan N --task T` prints the plan and runs nothing. [`workflow.plan_task`](workflow.py)
   resolves the task from the sidecar and its claim file alone, and freezes the claim's statement, domain,
   observations, assumptions, allowed change, models and bounds under a digest (`key`). A retry is compared with
   that key, so a changed claim is a new question, not a new attempt.
2. **Execute.** `build.py N --task T`, committed as a job, reaches [`route.run`](route.py). It opens a write-ahead
   execution record ([`executions.py`](executions.py): a retry owns a new directory, and earlier attempts are never
   touched). Then it prepares each revision ([`runtime.py`](runtime.py): `lock`, then `prepare`, every byte hashed
   and the classpath checked).
3. **Run the controls.** [`runtime.run_controls`](runtime.py) runs each revision's driver in its own JVM.
   Where an adapter stands in for the original code, [`qualification.correspondence`](qualification.py) checks
   that it agrees with the controls before the checker's answer can count.
4. **Run the checker.** [`runtime.run_verifier`](runtime.py) runs `jvmcontract` on the prepared bytes. A
   counterexample (a *witness*) is replayed independently on a JVM ([`replay_candidate.py`](replay_candidate.py))
   before it is reported. Which class file a name means is said once, in [`class_binding.py`](class_binding.py):
   the checker's selection and the JVM's observed selection must agree.
5. **Qualify and publish.** [`workflow.ingest`](workflow_ingest.py) binds the claim, the prepared artifacts, the
   controls and the execution records into one format-2 receipt (`result.json`). Beside it go `plan.json`, the
   records with their digests, and a completion digest. [`qualification.py`](qualification.py) compares what was
   actually examined with the typed claim. It refuses a wrong binding, an adapter that disagrees, or evidence
   for a weaker statement.

A receipt's conclusion is `established`, `refuted` or `unresolved`, beside the outcome the task expected. An
unresolved receipt is a result too. For example, Commons Numbers example
[105](../../105-commons-numbers-223-pow-of-minus-two-to-the-31/README.md) has one, marked unverifiable. It stays
published as the record of that attempt.

## A change plan

`build.py --change-plan upgrade --before B --after A --jdk J --output OUT [--workflows FROZEN] [--run]`
([`change_plan.py`](change_plan.py)) compares two deployments of an application.

1. **Inventory and bind.** Both deployments are resolved with their ordered classpaths and JDKs
   ([`change_inventory.py`](change_inventory.py)). [`entry_discovery.py`](entry_discovery.py) indexes the
   artifacts once and ranks the public callers of changed bodies. Each claim records its entry binding on both
   sides. Where more than one measured public history is eligible, the plan asks which one matters to the caller,
   and doesn't choose for it.
2. **Register.** Each frozen workflow (`--workflows`) becomes a claim. Its key covers its scope, intent and
   assumptions, and its execution key covers the runner, the probe, the environment and both deployments. A caller
   can be written by hand or generated from a reviewed public history
   ([`observer_generation.py`](observer_generation.py), which keeps the exact older-API caller for replay).
3. **Replay a finite domain.** With `--run`, [`upgrade_replay.py`](upgrade_replay.py) runs each registered case on
   both original JVMs. [`change_evidence.compose`](change_evidence.py) turns the observations into the claim's
   status. A claim is `established` only when the domain is closed: every runtime input is bound, the observations
   are deterministic under the stated assumptions, and nothing on the classpath changed during the run.
   Otherwise it stays `open` with its first open dependency named.
4. **Reuse exactly.** `--previous REPORT` resumes an earlier plan for the same change. A binding that's unchanged is
   requalified, and a different one is a new binding. With `--cache`, only deterministic, qualified, positive sides
   whose inputs hash the same can skip a new replay ([`change_evidence.SideCache`](change_evidence.py)).

The transfer from ThreeTenBP #77 to Apache POI #1420 used a frozen plan of this kind. Three of the four claim and
revision combinations reused evidence, and the strict attempt stopped at `Locale.equals`, which was recorded as its
limit ([registration](../../../lib/benchmark/organic-composition/poi/registration.json),
[results](../../../llm-dlc/loops/organic-java-pr-capability-composition-fast-follow-results.md#apache-poi-1420)).

## A public JVM observation

An example whose `example.json` names a `publicComparison` file is replayed by `build.py N`
([`public_comparison.py`](public_comparison.py)). A finite public caller runs on byte-pinned deployments in
separate JVMs. Its questions and falsifiers are registered first (`comparison.json`), the same compiled caller runs
on both sides, and the recorded observations are matched against the predictions. JUnit example
[586](../../586-junit-dynamic-suite-leaves/README.md) is one. Its result covers the histories, inputs and
environment recorded, not every input.

An example whose original build runs elsewhere keeps its archived observations, which
[`recorded_comparison.py`](recorded_comparison.py) checks. For a merged pull request, `observe.py
public-observation URL` ([`../observe.py`](../observe.py), [`public_observation.py`](public_observation.py)) freezes
the public behaviour from the original deployment packet, and measures it with `--measure`.

## Other modules

The rest of the folder supports these routes. Each module's docstring says what it owns:
- caller and input generation (`resource_workflows.py`, `integer_codecs.py`, `upgrade_claims.py`);
- the native selector proofs (`native_selectors.py`);
- startup facts (`startup_facts.py`);
- original-test traces (`approved_test_trace.py`);
- the readiness and handoff views (`workflow_handoff.py`, `workflow_discovery.py`).

`grep -l` for the step you need, or start from the command in `build.py`'s usage text that runs it.

Keep this page to routes and owners. A command's options belong in its `--help`, and what one example needs belongs
in that example's `notes`.
