# in-the-loop: foundation-first plan and domain workstream plans

**November 19, 2026 · Repository baseline `65df5fe7`**

This document has two parts. Do Part 1 first. Part 2 resumes once Part 1's exit checks pass.

- [Part 1: Foundation-first build plan](#part-1-foundation-first-build-plan)
- [Part 2: Domain workstream plans](#part-2-domain-workstream-plans)

---

## Part 1: Foundation-first build plan


**Decision · November 19, 2026.** Put one shared engineering milestone ahead of the Spring, Java data-processing and runtime-safety implementations. Its deliverable is a proof through the public interface for which an independent reviewer can reconstruct the inputs, tell exactly what was observed, replay a distinguishing case on a JVM, and see the same qualification in the final report. A new agent must also be able to recover each required claim, what supports it today, and what earlier attempts learned. Demonstrate both capabilities on a small program that changes an array through one of two possibly shared references.

At the reviewed `main` commit, `65df5fe7`, the repository already has a typed statement, observation variants, harness layouts, a witness runner, claim keys, a proof cache, acceptance checks, benchmark phases and a job queue. The common work is to make those components agree at their boundaries and to challenge the rules they rely on. The plans for 286/288, Commons Text and 053/106 resume after the exit checks below. [Repository snapshot][repo] · [Domain workstream plans (Part 2)](#part-2-domain-workstream-plans)

### What earns a place before the domain work

| Shared investment | Spring authorization and binding | Java data processing | Runtime safety |
|---|---|---|---|
| Independently qualify checker rules and environment assumptions | A result depending on locale, initialization or shared calls carries its real limitations | Array results retain the right contents and identity through calls and merges | Modeled exceptions and their observed attributes have a trustworthy interpretation |
| Carry the planned input domain and observations through execution and acceptance | A bean-state claim cannot quietly become a decision-only check | Shared and distinct arrays, even with equal contents, are distinguishable | An event, an escape and a declared exceptional outcome can have separate meanings |
| Replay the exact input and selected observation on a JVM | A permitted write that disappears is visible to the caller | Wrong array sharing yields a small, reproducible difference | A witness identifies the selected failure even when the method catches it |
| Keep claims and attempt history discoverable | Distinguish a proven binding decision from an open bean-state claim | Recover a slower bounded proof strategy and its baseline | Preserve accepted property evidence when a later replay fails or the run is interrupted |
| Measure failure and cost on a common corpus | Identify where a binder comparison spends its budget | Separate unsupported bytecode from expensive symbolic execution | Separate an unmapped backend check from insufficient unwind or a genuine violation |

### Work order and ownership

| Package | Start | Owner and first reviewable output | Ready to merge when |
|---|---|---|---|
| **A. Qualify the checker** | Immediately | Independent challenge owner. Record the existing countermodels, applicable tests and frozen jobs | The ordered VF-044 pass has checkable dispositions and the accepted evidence points to the qualified checker |
| **B. Bind claims and retain their history** | Alongside A. Begin with B2's read-only view | Evidence owner. Expose existing claims and attempts on 286/288, trace both proof routes, then capture missing execution records | Bounds, observations and assumptions survive both routes. A fresh agent can recover an interrupted or slower attempt and identify currently accepted evidence for each required claim |
| **C. Share a small input domain and its observer** | Design alongside A and B. Integrate against B | Harness/checker owner. One public paired example with three distinct observation claims over two array parameters | Native and JVM cover the finite reference domain. Refutations replay with the intended aliasing and selected poststate. A declared JBMC overlap is exercised |
| **D. Run the transfer and cost checks** | Capture baseline before changes. Finish after integration | Integration owner or the domain owners in rotation. Add a small, versioned selection to the existing conformance/benchmark tools | Each domain owner can use the common path or obtain a precise refusal. A before/after run records verdict, first blocker, time and memory |

These are temporary assignments. An owner can change any layer needed for their result. In particular, C owns a complete public-API outcome, including replay and reporting. A different owner should challenge its controls. If only two agents are available, pair A with D and B with C, then cross-review.

### A. Close the known correctness work before building on it

Preserve the repository's D038 order for the existing findings. B and C can develop independent fixtures while this pass runs. [Verification findings, especially VF-044, VF-042 and VF-041][findings]

1. **Challenge the relational-sharing rule.** Exercise I028/I029 with JVM-distinguishable cases for saved array results, branch-dependent string results and allocation. Include the outstanding two-predecessor `absorb` case. A merged record must retain the correct branch's result or be discarded. Update the stale expectations in the existing challenge script. Record a proof, refutation or explicit refusal for each control.
2. **Re-run the frozen jobs on the checker that results.** Recheck 287 preservation, both relevant 307 tasks, and the 289/290 work named in VF-044 at the frozen bounds. Update task records and re-run acceptance against the collected results. A capped probe is useful for diagnosis. The frozen job is what requalifies the result.
3. **Qualify the semantics already known to yield false proofs.** Exercise all four exception-message countermodels and all six observed-initializer setting cases from VF-042. For each case, implement JVM-consistent behavior, bind the relevant setting and its scope, or refuse the affected observation. Test all ten on the checker. A changed environment must invalidate evidence that depended on the original setting.
4. **Finish the two I026 coverage probes and the VF-041 reporting fix.** Retain `restsOn` and `limits` independently through the milestone view. Example 287 should visibly say that the agreement established is on terminating runs. If later fixes change semantics used by a requalified job, rerun the affected task on the integrated candidate.

**Acceptance:** The reviewer can map every recorded case to a current test, disposition and job where relevant. The D039 order of companion Spring claims stays intact. Example 288's longer preservation run retains its existing trigger of a measured improvement at the bound-8 final comparison.

### B. Make the executed claim match the planned claim

**Start with the two existing routes.** Ordinary sidecar planning already resolves length and unwind defaults before running. Beside-route acceptance currently passes its length-domain check when a frozen claim omits the length bound and no trial flag is present. Separately, the milestone projection copies evidence limits and can drop the checker's assumptions. These are precise changes with regression tests. [Planning][workflow] · [Beside-route domain check][accept-domain-check] · [Milestone projection][changes]

| Where the information belongs | Required behavior |
|---|---|
| **Source claim** — existing `claim.target.claimKey` | Bind entry, domain, assumptions, allowed change, observations and effective bounds to the independent plan. Use the planner's versioned defaults where applicable. Distinguish an irrelevant bound, a plan-resolved default and genuinely missing provenance. |
| **Prepared claim** — existing receipt `claim.id` | Bind the actual revisions, ordered classpaths, prepared bytes and applicable JDK, adapter, oracle and model evidence as the route provides. Compare the executed semantic fields with the plan before promoting a result. A source key can be shared by two revisions whose prepared IDs differ. |
| **Execution evidence and cache** | Record the actual engine, version, profile, outcome, resource limits and assumptions. A timeout is an attempt setting. Keep the tool-sensitive cache key and its existing refusals for inputs it cannot identify. Another engine may decide the same prepared claim without being eligible for a cache hit. |

Use `Statement`, `PreservationContract`, `Observation` and the existing claim planner. Compare complete observation descriptors, including a field path, ordered payload or exception policy when used. For example, two effect observations can have the same display ID and different payloads. A comparison of display strings alone cannot establish semantic equivalence. [Typed observations][spec] · [Statement][statement] · [Prepared receipt][ingest] · [Cache identity][cache]

**Acceptance tests**

- A proof at array bound 2 cannot establish a bound-4 claim. A refutation found at 2 can refute that claim when its witness is replayed and shown to satisfy the full bound-4 inputs, assumptions and observation. An execution result cannot supply its own missing proof bound.
- Change only the alias policy, the observed field or effect payload, the exception policy, or the bound environment. An earlier receipt cannot establish the altered claim. A correct replay with the wrong observer cannot establish that the requested property failed.
- A vacuous result, unfinished unwind, unexamined selected observation or truncated evidence remains visible as incomplete. Test that a legitimate in-domain refutation can still be published when unrelated work is incomplete and its own evidence is complete.
- Keep old receipts readable at their original identities. Mark missing provenance and requalify affected claims through new evidence. Run a compatibility test for an existing ordinary task and an existing beside-route task. Preserve both `restsOn` and `limits` in JSON and the human report.

#### B2. Make claims and attempt history discoverable to the next agent

**Start with a read-only view.** Example 286 already has three claim files, six proof tasks and two replay tasks. The ordinary route retains immutable receipts and the handoff lists current and stale receipts and some strategies. The discovery view selects the latest current receipt for each task. Extend that workflow so an agent can start at an example, choose a claim and revision, then see the latest run, the eligible evidence and the earlier strategies worth knowing about. Preserve the existing task-level output for callers. [Example 286][history286] · [Task schema][task-schema] · [Discovery][discovery] · [Existing handoff][handoff]

| What changed? | What to record |
|---|---|
| A promised observation, assumption or input domain changed | Freeze a separate claim and explain what the earlier one missed. Keep the previous claim and conclusion. |
| The same property is checked on the base, fixed or deliberately altered artifact | Reuse the source claim where the semantics agree. Show the subject-specific tasks, prepared identities and conclusions separately. |
| An agent changes search order, engine, timeout, machine or a proof strategy that preserves the statement | Record another attempt on the same obligation. Identify what changed relative to a named baseline. An additional unproved assumption changes what the result can establish. |
| An agent tries a smaller bound | Attach the trial and its actual bound to the original question. Give a separately published narrower guarantee its own claim. B's membership and replay tests govern whether a trial witness refutes the parent. |

Use the task's existing `parent` for a derived claim and `requires` for scheduling dependencies. Parentage alone establishes no implication. Name the required claim/subject pairs for each milestone before the run. Display those obligations, companions, controls and exploratory work with their expected and observed answers. A refuted control can be the intended outcome. Report attempts and compute separately from required obligations decided. That keeps diagnostic work visible without rewarding an agent for generating easy claims. [Claim keys][workflow] · [Example roll-up][changes]

**Capture work that can disappear.** First index existing receipts, jobs, gap packets and dated progress entries. For new queued attempts and material capped probes, persist a small intention record before expensive work starts. Use one ID per execution and link a genuine retry to its predecessor. Record the example, task, source claim key when available, intended strategy and baseline. Add the prepared claim ID when preparation succeeds. Write the records outside the disposable job checkout and outside `target.json`. The full sidecar digest participates in the prepared ID. Adding notes or retries there could change future identities for unrelated claims. Preserve original receipt IDs and use the existing task-scoped freshness checks. [Receipt identity][ingest] · [Task-scoped freshness][freshness]

- **Record measurements automatically.** Capture actual execution start, source and checker revisions, settings, semantic bounds, resource budget, host/cache condition when available, last confirmed stage, cost and terminal disposition. Link the original job, step, logs, witness, receipt and acceptance report where they exist. Ordinary receipt `startedAt` is assigned during ingestion. Use execution telemetry for timing and mark missing information explicitly.
- **Preserve late failures.** When the solver returns a candidate and replay fails, retain the candidate, replay outcome and reason. For a stop between stages, keep completed stages and the last available artifact. Reconcile a start with no completion against the job record. An unknown ending stays unknown. A sibling with independently accepted evidence retains it. A multi-step job whose acceptance rule requires a passing job remains subject to that rule.
- **Add a short strategy note when it changes the next decision.** Record the hypothesis, observed result versus baseline, evidence for the explanation, and what would justify retrying. If reproducing an abandoned implementation matters, keep a recoverable commit or a bounded patch with its base. Link existing logs and traces. Label a retrospective prose account as such. Routine retries need only the automatic record.
- **Support retries and concurrency.** Store immutable per-execution records or events and derive the index. Re-ingesting one completion is idempotent. Concurrent runs keep separate IDs even when they share a task or an automatically retried job ID. A new note must leave frozen inputs untouched. [Job results and failed outputs][queue] · [Receipt publication][publish]

**Present what is known now.** Show the latest execution outcome beside the currently eligible conclusion, its limits and evidence. A later timeout leaves an earlier still-qualified proof visible. If a qualified proof and a JVM-replayed refutation contradict each other on the same subject and semantics, flag the obligation as disputed and surface both. If a checker defect invalidates prior evidence, retain the attempt and the reason for withdrawal. Compare performance only when the claims, artifacts, versions and resources match apart from the intended experimental change. For a timeout, report the budget consumed and that the attempt ended before a verdict. Its time to a verdict is unknown.

**Acceptance tests**

1. **Inventory on 286.** One read-only handoff shows all three source claims, their six proof tasks and two replays. A new sibling leaves older history discoverable by its original IDs. Grouping does not collapse results across revisions.
2. **Learning from 288.** From its preservation claim, a fresh agent can find the 42-second bound-4 baseline, the 46-second trial that related 154 of 309 lemma applications, and trials at bounds 5 and 6 still unresolved at 150 seconds. Import the actual progress entry as a historical probe. Show the proposed per-release lemma and the bound-8 improvement needed before another long run. The frozen claim remains open. [Recorded experiment][probe288] · [Retry decision][findings]
3. **Separate outcomes on the shared array fixture.** Freeze the return-only, right-root and both-root observations as three claims under one example. A proof of the first leaves the other two open until decided independently. Test a timeout after an accepted proof, a stale checker result and a genuine contradiction.
4. **Recover a late interruption.** Stop a fixture after its solver stage and before replay or receipt publication. An agent with a fresh checkout and no earlier chat must recover the attempted strategy, last confirmed stage, missing evidence and next action. Launch two parallel retries and ingest one completion twice. The view lists each real execution once and leaves the interrupted attempt undecided.

Ship the read-only handoff on 286 and 288 first. Add the start/checkpoint capture and qualification rules next. Expand historical backfill as agents reopen other examples.

### C. Build a shared domain small enough to check exhaustively

**First consumer.** Use two nullable `int[]` roots, each of length 0–2, with cells in `{0,1}`. Allow either root to be null, both to reference the same array, or both to reference distinct arrays with equal or different contents. There are seven array contents and **71 inputs up to renaming heap objects**: one both-null case, 14 one-null cases, 49 distinct non-null pairs and seven shared pairs.

The reference method writes `left[0] = 1` when both arrays are non-null and nonempty, then returns zero. The deliberate alternative skips the write and returns zero. I ran the pair on OpenJDK 21.0.13, rebuilding fresh per-version heaps while preserving sharing within each heap.

| Observation compared | JVM differences across 71 cases | What a correct checker should report |
|---|---:|---|
| Return value only | **0** | Bounded preservation established |
| Final contents of the right root | **3** | Refuted. The changed cell is visible through the right root only when both roots share it |
| Final contents of both roots | **21** | Refuted. This also sees writes through the left root when the right root is distinct |

With two separately allocated `[0]` arrays, the right array stays `[0]`. With both roots pointing to one `[0]`, the right root reads `[1]` after the reference method. That pair of cases catches a harness that clones each argument independently or merges distinct arrays solely because their contents match.

**Implementation**
 
1. Use `harness::Layout` and its existing choice slots. Generate one set of primitive choices for the supported profile and reconstruct roots in bytecode. Give each version its own fresh heap and retain the original alias relationships inside it. Feed the public pairing/property route a supported assumption so the test exercises the composition boundary. The current pairing path clones array arguments individually and excludes explicit aliases. [Harness layout][layout] · [Pairing route][pair]
2. Use the typed observations for result, array contents and identity. Keep the observer read-only. Compare the predeclared projections after the target call. Generate replay inputs from the same primitive choices and validate the resulting roots against an independently written JVM oracle. Shrinking must preserve the selected disagreement. In particular, changing a shared array into two equal arrays destroys the right-root witness. [JVM witness runner][witness]
3. Qualify native on the full 71-case domain through the public entry. For JBMC, establish at least one common profile end to end using **both** a preserving pair and a discriminating pair. Attempt the full nullable/aliased profile using the same generated bytecode. If JBMC cannot consume it, retain a named refusal on the full claim, and qualify an explicitly separate smaller domain with its own identity. Record raw and integrated JBMC separately when diagnosing a disagreement. [Current widened-domain refusal][property]
4. Add an exception fixture shared by the reporting and replay paths. Use a caught division with a dedicated observable catch marker and a specified handler in the fixture. Check a no-event property, a no-escape property and the declared divisor/exception relation under separate policies. The marker distinguishes the caught route on this fixture. General JVM exception-event instrumentation and per-site inventory belong to the runtime-safety stream.

**Acceptance:** The independent JVM oracle enumerates all 71 inputs, including equal-but-distinct arrays. The public native checker establishes return-only preservation and refutes each poststate claim with a reproducing witness. Forced per-argument cloning, a dropped poststate comparison and a swapped observation each fail the corresponding check. Test the finite domain mapping separately from the symbolic verdicts: one solver witness proves existence and does not establish the number of distinguishing inputs.

### D. Prove transfer, then release the domain owners

Use the existing conformance corpus, `Reference.java`, benchmark runner, phase accounting and test tiers. Add the smallest fixtures needed above to the fast tier when they meet its resource criteria. Queue the frozen proofs and the fixed benchmark selection on the existing runner. Record checker commit, artifact digests, semantic bounds, profile, host/resource budget and cold/warm cache state for comparisons. [Benchmark corpus][bench] · [Phase timings][phases] · [Test tiers][tests] · [Verification queue][queue]

| Transfer probe | Evidence that the foundation is ready | Work the domain owner takes next |
|---|---|---|
| **Spring 286/288** | A small synthetic binder with benign data loses a legitimate update without changing its return. The common observer distinguishes it and the receipt names the exact poststate. Recheck one existing Spring receipt with B's qualification rules. | Real `DataBinder.bind` batches, the locale-bound transfer, then ordered authorization descriptors |
| **Java data processing** | Re-run the pinned Commons Text finite JVM oracle from the earlier plan. It reported 0/225 differences on the release source and 44/225 on the row-sharing control. The current native route should either decide the same scoped claim or identify its first blocker. | Implement `multianewarray` on that workload, then extend callback adaptation and parsing |
| **Runtime safety 053/106** | The caught-event fixture reports distinct answers for event occurrence, escape and declared behavior. Existing aggregate callers retain their old result and the report exposes which policy was asked. | Add public list/select, bytecode site IDs and individual traces, then ship the real 106 inventory |

**Read the measurements in order.** First count contradicted establishments and refutations that fail JVM replay. Then count decided claims, explicit refusals and other unresolved outcomes by first blocker. For comparable claims report wall time, peak RSS and the expensive phase, using fields the current runner already collects. Only compare performance at the same semantics and resource settings. Example 288 illustrates why: its recorded profile put about 72 of 136 solver seconds in binder configuration and under three in the matcher. Avoid funding matcher optimization on the basis of total runtime. [Recorded profile][findings]

#### Stop condition and handoff

Release all three streams after A's countermodel dispositions and required evidence are current, B's drift and fresh-agent history tests pass, C works through the public native route with JVM replay and at least one qualified JBMC overlap, and each D probe produces its expected outcome or explicitly permitted blocker. Report required obligations decided against their declared denominator, how often claims get through the public route, the most frequent blocker and the slowest phase on a like-for-like run. Report repeat attempts and compute spent separately. The next investment follows those observations.

A universal heap model, generic object factory, broad cache enablement, all-JDK model audit, new scheduler or solver migration has no first-milestone consumer here. Revisit an item when two concrete workloads identify the missing capability or measurements show where it will pay off. The domain owners retain authority over their implementations.

**Evidence boundary.** The repository findings and implementation references above were inspected at the pinned commit. The 71-input array experiment was performed for this plan. The Commons Text counts come from the earlier workstream experiment. No new native or JBMC proof jobs were run for this planning task.

[history286]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/286-spring-framework-cve-2022-22968-case-sensitive-disallowed-fields/target.json
[task-schema]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/schema/target.schema.json#L189
[discovery]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow_discovery.py#L89
[handoff]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow_handoff.py#L236
[freshness]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow.py#L336
[publish]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow_ingest.py#L676
[probe288]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/llm-dlc/loops/domain-advances-preservation.md#L518
[repo]: https://github.com/pilifs/in-the-loop/tree/65df5fe7ea0385607f4db7f36ca070001c6688cf
[findings]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/verification/findings.md
[workflow]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow.py#L209
[accept-domain-check]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/accept.py#L523
[changes]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/llm-dlc/tools/changes.py#L69
[spec]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/spec/mod.rs#L168
[statement]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/statement.rs
[ingest]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/targets/workflow_ingest.py
[cache]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/proof_cache.rs
[layout]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/harness/mod.rs#L897
[pair]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/pairing.rs#L110
[witness]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/jvm_witness.rs
[property]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/property.rs#L269
[bench]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/benchmark/README.md
[phases]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/phases.rs
[tests]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/tools/test_costs.py
[queue]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/verification/README.md

---

## Part 2: Domain workstream plans


**Engineering brief · November 19, 2026 · Repository baseline `65df5fe7`**

Run three workstreams concurrently. Give Spring first call on extra proving capacity because its next result addresses a documented weakness in the meaning of an accepted claim. Give Java data processing a real algorithm with a cheap independent oracle. Give runtime safety a developer-facing outcome that can be demonstrated on an existing Apache change. Each owner can change the harness, models, checker, public interface and evidence path required for their result. The existing verification runner can serve all three. [Repository snapshot][repo] · [Domain ownership and frozen claims][ownership]

| Stream | First assignment | First result worth shipping | Next use that tests transfer |
|---|---|---|---|
| Spring authorization and binding | Example 286, then 288, on batches of permitted and denied bean updates | A bounded claim about the bean state a caller actually receives, with controls that distinguish a correct binder from one that silently loses a legitimate write | The same observation on the second Spring release family. In parallel, establish ordered matcher descriptors in 290 |
| Java data processing | Apache Commons Text 1.13.1, `LongestCommonSubsequence.apply` | The real implementation agrees with an independent score calculation, and forcing two matrix rows to alias changes the result | A Commons Lang parsing pipeline that requires a boxed method-reference result, followed by floating-point transport in example 106 |
| Runtime safety | Example 053, then Apache Commons Lang example 106 | A developer can list checks, select a failing instruction, replay its witness, and see which other checks completed at the same bound | A qualified native/JBMC comparison that preserves the same input choices, property policy and observations |

### 1. Spring authorization and binding

**Outcome.** An application developer can tell which public binding or authorization behavior survived a change. Today, a one-value binding check can succeed even if a permitted update later in the same batch disappears. Example 290 has the analogous problem for configuration. Two releases can return the same number of matchers of each type while selecting different patterns. Address both with companion claims. D039 gives 286/288 first priority among the existing companion claims. [Binding and evidence findings][findings] · [Example 290][e290]

#### First assignment — the state after a batch of bindings

1. **Freeze a new claim for 286.** Construct a real `DataBinder`, configure it with its public setters, submit a single batch through `bind`, and read the bean and the binding result. Record the fixture's starting values, field names, accepted value types, locale, name length, batch length and pattern bounds. Begin with type-valid values to isolate binding policy. Use at least three effective entries and distinct fields or values so the batch representation preserves the cases being tested. Include a permitted write after denied entries, the reverse order, all-permitted and all-denied batches. Count field repetitions only if the input carrier preserves them.
2. **Specify both sides of the contract.** Every permitted write reaches the intended field with the supplied value. Every denied write leaves that field unchanged, including when another field was legitimately updated. Compare the final relevant fields and the reported set of suppressed names. If the public claim covers intermediate state, run each prefix of the batch on a freshly initialized bean. Preserve aliases within a run when a supported fixture can create them. Isolate the before and after heaps so a write on one side cannot manufacture agreement.
3. **Challenge the observer before extending the engine.** Run the oracle on the fixed release and the existing control set from VF-043, using benign bean values. A binder that stops processing a batch early, or suppresses a later legitimate field, must be distinguishable. Confirm that each distinguishing case actually reaches the affected update. Go through the constructor and `bind` even if a helper-level lemma is easier to prove.
4. **Transfer the same claim shape to 288.** Pin the release, model set, locale table and environment as claim inputs. Share the batch generator and bean observer wherever their contracts agree. State any smaller ASCII domain in its own claim. The original bound-8 proof in 286 has a recorded non-ASCII lowercasing boundary. For 288, the open old/new preservation comparison has a different bottleneck. Benchmark the proposed per-release locale lemma on the bound-8 final comparison against the same baseline before authorizing another long run. The recorded bound-4 comparison took 46 seconds with the previous sharing approach and 42 seconds without it. [Example 286][e286] · [VF-031, VF-040 and VF-043][findings]

**Exit.** For each release family, publish the exact batch and alphabet bounds, the actual public path, an accepted positive result or a replayed refutation, and the disposition of each relevant wrong-binder control. Credit transfer when the same observer decides a second real task. If a larger claim remains open, publish the first unsupported operation or expensive query and the independently decided smaller claim under its own identity.

#### Authorization in parallel — from configuration to a decision

| Step | Work and observations | Discriminator for acceptance |
|---|---|---|
| **290 · configuration** | Retain the 5.8.4 → 5.8.5 lone-`DispatcherServlet` domain. Observe the **ordered** sequence of matcher kind, pattern, HTTP method and applicable servlet path, or the stated exceptional outcome. Obtain descriptors from the actual constructed matchers and compare against an independent JVM observer. Keep fixed-release selection with no `DispatcherServlet` as a separate proposed correctness claim. | A control changes one pattern or swaps two distinct entries while all type counts stay the same. Frozen-bound results relying on observed initializers identify relevant settings or use a qualified alternative. |
| **Composite matchers · positive upstream change** | On the parent and commit `9bba1a1c`, preserve the match Boolean. On the new version, OR returns the first successful child's variables. AND merges variables in child order, later values win on collision, and a failed AND exposes no accumulated variables. Record the delegate call prefix. Use real delegates or a checked contract connecting their `matches` and `matcher` behavior. | Two child maps have the same size and conflicting values. The wrong collision winner and an unnecessary extra child call must each be observable. |
| **Fluent builder · transfer** | On the parent and commit `0cefb279`, build corresponding policies via explicit registrations and fluent calls. Evaluate overlapping matchers and include an unmatched request. Observe the selected rule, decision, delegate calls and forwarded variables. Start with valid registration histories and evaluation before later builder mutation. | Two rules give different decisions on an overlapping input. Reordering those rules or changing only a forwarded value must be detected. |

A later lifecycle milestone can use the fixed-release public filter in example 291 to check allowed and denied downstream calls and cleanup in a bounded dispatch history. It is a catalog entry at this snapshot. The builder and composite positive changes provide a producer and consumer for the observation machinery before that larger campaign. [Example 290][e290] · [Composite change][composite] · [Builder change][builder] · [Example catalog][examples]

**Likely implementation seam.** Extend the pairing and construction paths only as an actual claim requires. For example, allow a receiver constructed by a plan to participate in a paired check with a bounded string array, then compare an explicitly declared poststate. Keep reference sharing, nullable choices, before/after argument correspondence and the observer in the prepared claim. A static adapter can establish a useful intermediate result when its inputs and observation match the claim. Record separately when the ordinary public route can admit that same claim. [Pairing eligibility and observations][pairing] · [Construction][construction]

### 2. Java data processing

**Outcome.** An engineer can verify a small upstream algorithm or a data transformation whose answer depends on Java array identity, callback conversion or numeric semantics. Start with an algorithm where a plausible implementation mistake produces a demonstrably wrong answer.

#### First assignment — verify a real multidimensional array

**Target and baseline.** Apache Commons Text 1.13.1 `LongestCommonSubsequence.apply(CharSequence, CharSequence)` reduces its score calculation to two integer rows. I compiled the pinned upstream class and its two interfaces with OpenJDK 21.0.13. In that build, `algorithmB` contains `multianewarray [[I` with two dimensions at bytecode offset 18. I ran the public method on all 225 ordered pairs of strings of length 0–3 over `{a,b}`. An independent oracle enumerated subsequences of one string and checked membership in the other. [Pinned source][lcs] · [JVM array semantics][jvms]

| JVM run | Disagreements with the oracle | Score for `("ab", "aa")` |
|---|---:|---:|
| Upstream source compiled locally | 0 / 225 | 1 |
| Same source with the second row made to share the first row's storage | 44 / 225 | 2 |

1. **Package the pilot.** Pin the target class files or released JAR, compiler/JDK, source identity, independent oracle and altered artifact. If using the published JAR, repeat the disassembly and JVM run on those exact bytes. Admit actual `String` instances as the two `CharSequence` arguments. The non-null score property and the null-input exception contract can be decided independently.
2. **Implement the missing allocation semantics.** Reuse the existing reference-array heap. Check every supplied dimension for negativity, including a later negative size following an earlier zero. Allocate distinct subarrays, preserve default values and the identity of rows through swaps and writes. Exercise partial allocation with three-dimensional type and two dimensions supplied, e.g. `new int[x][y][]`, and inspect the emitted opcode. Budget allocations explicitly and report an exceeded resource bound as unresolved. A separate primitive fixture covers negative and partial allocation, which the algorithm itself does not exercise.
3. **Prove the public score.** Use the finite oracle as a specification, or independently encode the subsequence predicate. Check that inputs reaching both the array path and its row swaps are admitted. The unchanged target should agree and the row-sharing control should yield a JVM-replayable difference. Store limits for both input lengths and symbolic array sizes, plus unwind and oracle identity. Once accepted, increase one dimension or the alphabet and record time, explored states and peak memory. The 225 JVM comparisons above establish only the stated finite baseline.

#### Second assignment — compose parsing with a real callback

Use Commons Lang 3.17.0 `NumberUtils.toInt(String, int defaultValue)` as the upstream method. Check that valid ASCII decimal input returns the value and null, malformed or overflowing input returns the supplied default. Let the default vary. Add separate boundary cases for maximum and minimum integer values and one value beyond each. A three-character symbolic string domain cannot exercise overflow, so use a declared larger domain or a separate finite boundary claim. [Pinned Commons Lang source][number]

Then compare a **constructed caller** of the upstream API, `Arrays.stream(tokens).map(NumberUtils::toInt).toArray(Integer[]::new)`, to an explicit loop calling the same one-argument overload. That overload defaults to zero. Compare length, order, boxed **values** and the slot for each malformed token. The repository's sequential stream model already exposes the array-generator overload. Inspect the bootstrap descriptors and implement precisely the erased cast and primitive-to-boxed result adaptation the call needs. Add a separate control for null unboxing, widening, a discarded return with an observable side effect, and captured reference choices as those cases are enabled. [Sequential stream model][streams] · [Lambda adaptation contract][lambda]

**Exit.** The real parser satisfies the declared value/error contract. The composed caller agrees with the loop and rejects controls that drop malformed inputs or return the wrong default. A gap for non-ASCII conversion stays visible until its own domain is covered. As a second upstream consumer, example 109's `Hex.decodeHex` can reuse a content observer to compare destination bytes and writes completed before an exception. [Example 109][e109]

#### Third assignment — stage symbolic floating point

| Order | Consumer and deliverable | Evidence required |
|---|---|---|
| 1. Transport | Example 106's historically uncovered `float[]` and `double[]` reverse overloads. Observe every output cell, signed zero and exceptional outcomes at the existing small array bound. | Java-compatible equality policy for NaNs and signed zero. Store witnesses in a reproducible bit encoding and qualify any raw NaN-payload claim on the pinned JVM. |
| 2. Comparison and conversion | Example 035's constructed `fcmp` case and upstream `FloatToIntConversion`. Cover compare direction on NaN, signed zeros, rounding toward zero, saturation and NaN-to-integer conversion. | Boundary JVM cases and wrong-comparison controls. A qualified JBMC result can be published under its engine identity while native support develops. |
| 3. Arithmetic and storage | Add arithmetic, Java floating remainder, conversions, fields and arrays on the supported widths. Choose a real arithmetic consumer before funding a broad implementation. | Include subnormal, infinite and NaN outcomes, validate result/replay encoding, record solver cost and unsupported operations. A symbolic transport result earns credit only for the operations it exercises. |

I would commit to the array and callback milestones now and make the native arithmetic investment a separate decision once the first consumers and solver costs are known. [Example 106][e106] · [Example 035][e035] · [Upstream conversion fixtures][fp]

### 3. Runtime safety and property diagnostics

**Outcome.** A developer can ask which operation may fail, on which input, whether the method handles it, and what the verifier established about the other operations. Native currently emits one harness property for a check. The integrated JBMC parser can classify a failure outside the expected harness assertion as unexpected. Both are concrete starting points for a public inventory. [Native result conversion][native] · [JBMC result conversion][adapter]

#### First assignment — distinguish an event from a contract violation

Use example 053's `Arithmetic.idiv` and a tiny wrapper that deliberately catches divide-by-zero. Give each policy its own claim and expected result.

| Question asked | Expected result on the stated fixture |
|---|---|
| Does execution of the wrapper avoid every divide-by-zero event? | Refuted when the divisor is zero, even though the wrapper handles the exception. |
| Can an `ArithmeticException` escape that wrapper? | Absence established on the bounded domain if the wrapper handles the only source. |
| Does the original kernel throw exactly when its divisor is zero? | Contract established. This is the behavior the repository already documents. |
| Does a selected embedded Java assertion hold? | With assertions enabled, a deliberately false reachable assertion yields a site-specific failure. With assertions disabled, report its status accordingly. Distinguish an explicit `throw new AssertionError` from a compiler-lowered `assert`. |

Record exception class first. Use a caught-event observation in JVM replay when the method returns normally, for example an exception event carrying the throwing site. Record the escaping exception for an escape claim. Read exception messages only when that observation has been qualified. [Example 053][e053] · [Java assertions][asserts] · [VF-042][findings]

#### Implementation and real-library qualification

1. **Inventory and select.** Start with integral division/remainder, null dereference and array-access bounds in the chosen scope. Generate a site key from class-file identity, owner, method name and descriptor, bytecode offset and check kind. Bind the selected sites and policy to the claim. Add list, select and all modes through the normal public route. Repeated runs on identical bytes should yield identical IDs. A source line is display metadata and may refer to multiple bytecodes. Treat cross-revision correspondence separately.
2. **Keep the other obligations visible.** Produce a row for every inventoried site with selection, reachability, verdict and reason. Distinguish a reachable established check, a violated one, a proven-unreachable site, and a site with incomplete analysis. Preserve existing aggregate behavior for existing callers. Unwind failures, unsupported bytecode and missing backend mappings can leave obligations unresolved. A completed, independently replayed violation can still be reported. Retain harness-generated checks and completeness checks as diagnostics with their own provenance.
3. **Ship on example 106.** Its published result for `ArrayUtils.reverse(int[], int, int)` is an aggregate bounded no-throw result on the revised implementation and a failing result on the earlier one. Use the packet's array-length bound 4 and unwind 6. Identify the failing access in the earlier artifact, replay it on the JVM, and list the revised artifact's reachable and unreachable checks under the same policy. Include a small two-site fixture with independent failures so a first failure cannot conceal a second. The selected property's result must match its row in an all-properties run under identical semantics. [Example 106][e106]
4. **Wire diagnostics and qualify JBMC.** Emit the property inventory in machine-readable and text output. Give SARIF findings a stable rule kind, site fingerprint, source mapping when available and bytecode location in the message or properties when debug data is absent. Preserve raw backend property IDs and map them to a site and policy. Begin with integral inputs, then use a deliberately small shared nullable/aliased primitive-array harness. Exercise null, shared and distinct choices, and compare the same poststate in both engines when mutation is observed. Distinguish raw upstream JBMC, the integrated route and native. JVM replay adjudicates concrete differences. [SARIF writer][sarif] · [JBMC preflight][gaps] · [JBMC manual][manual]
5. **Try to disprove the integration.** Select a single failed property, disable assertions, remove debug information, truncate output, omit one mapping and lower unwind below the required bound in separate controls. Confirm the report describes each case accurately. Use the repository's existing handler-disagreement fixture to test refusal or a validated fix on the pinned JBMC version. JBMC's `--assert-no-exceptions-thrown` replaces throws with failing assertions and prunes the path. An escape-policy comparison needs ordinary exception propagation and catching. [Handler fixtures][handlers] · [JBMC instrumentation options][manual]

**Exit.** An engineer can list both checks in the two-site control, select either, identify its location and validate its witness. Example 106 produces an actionable source or bytecode site on the earlier version and a bounded inventory on the revised version. The integrated JBMC profile gets confirmation credit only for mapped properties with matched domains and policies. Coverage outside that profile has a named status.

### Execution, dependencies and acceptance

| Checkpoint | Spring owner | Java data owner | Runtime-safety owner | Independent challenge and integration |
|---|---|---|---|---|
| **First cycle** | Draft 286/288 companion claims and run the batch observers. Specify 290's ordered descriptor oracle | Package the 225-pair oracle and control. Capture native's first refusal on the target bytecode | Freeze 053's three exception policies and implement a public inventory for division | Start the already ordered VF-044 relational-sharing challenge. Capture per-target baseline and resource budgets |
| **First merge** | Land the first batch result with the receipt, control outcomes and remaining limits | Land multi-array semantics with the real LCS claim and allocation fixtures | Land list/select, per-site status and witness handling through 053 | Replay controls on the merged checker and distinguish incomplete from established results |
| **Transfer** | Carry the observer to 288. Advance 290 and the positive composite matcher | Prove the real parser and composed callback. Scope example 106's floating overloads | Ship example 106's integer safety inventory and qualify the first JBMC profile | Reuse the same 106 source pins, JVM runner and array-domain encoding. Keep the integer safety and floating-poststate claims separate |

**Dependencies that affect promotion.** VF-044 already orders an independent challenge of I028/I029, then fresh frozen-bound jobs for 287, 289, 290 and both relevant 307 tasks on the resulting checker. VF-042 records four exception-message countermodels and six initializer-setting cases. Fix, explicitly qualify, or refuse those semantics before accepting claims that depend on them. VF-041 requires carrying `restsOn` through reporting, including agreement only on terminating runs where applicable. These dependencies allow the LCS work, the 053 policy fixture and Spring observer design to start immediately. [Findings and decisions][findings]

**Use the existing proof routes.** For a real example with a target sidecar, preview the ordinary task with `python3 examples/tools/build.py --plan NNN --task T` and queue it through `python3 verification/pipeline.py submit --example NNN --task T` with the normal job metadata. A replay task and a proof task produce different evidence. For an example-specific driver, run it as a verification job and check its collected output with `python3 examples/tools/accept.py NNN T --json`. Keep the route visible in the report. A stronger observation, changed domain or different bound gets a new claim identity. [Example workflow][examples] · [Verification pipeline][pipeline] · [Acceptance checks][accept]

**Report at each merge.** Record the target artifact and checker revisions, exact bounds, model and observation policy, reachability of the interesting branch, replayed controls, and any limits or assumptions. Track real claims newly decided, wrong implementations distinguished, whether the public route can express the same claim, and the first unresolved obligation. Compare elapsed time and peak memory only for like-for-like claims and configurations. After two failed attempts at the same proof idea, record where the time or semantics went and change the approach. An open parent claim remains visible beside a useful component result.

**Scope of this brief.** I checked the repository snapshot and the cited upstream sources. The Commons Text table is a new finite JVM experiment on compiled release source and a deliberately modified control. All proposed solver results, including the three flagship claims, await implementation and proof jobs.

[ownership]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/llm-dlc/loops/domain-advances.md
[findings]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/verification/findings.md
[e286]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/286-spring-framework-cve-2022-22968-case-sensitive-disallowed-fields/README.md
[e290]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/290-spring-security-cve-2023-34035-multiple-servlet-authorization-rules/README.md
[composite]: https://github.com/spring-projects/spring-security/commit/9bba1a1c6be9a891ec6633f373fd92fa7c46d376
[builder]: https://github.com/spring-projects/spring-security/commit/0cefb279280fd24e6047998f36fa070e37157205
[examples]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/README.md
[pairing]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/pairing.rs
[construction]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/construction.rs
[lcs]: https://github.com/apache/commons-text/blob/a70c34e028ab279bb89565606e1ab09011a41bc2/src/main/java/org/apache/commons/text/similarity/LongestCommonSubsequence.java
[jvms]: https://docs.oracle.com/javase/specs/jvms/se21/html/jvms-6.html#jvms-6.5.multianewarray
[number]: https://github.com/apache/commons-lang/blob/29ccc7665f3bc5d84155a3092ab2209a053324e6/src/main/java/org/apache/commons/lang3/math/NumberUtils.java
[streams]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/models/java/util/stream/SequentialArrayStream.java
[lambda]: https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/invoke/LambdaMetafactory.html
[e109]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/109-commons-codec-43a9aa66-hex-decoding-restricted-to-ascii/README.md
[e106]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/106-commons-lang-1750-reverse-with-min-value-end-index/README.md
[e035]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/035-nan-compared-with-equals-turns-fcmpl-into-fcmpg/README.md
[fp]: https://github.com/diffblue/cbmc/tree/f04da2e453786fa81b8ec28056c32af8588d9e51/jbmc/regression/jbmc/FloatToIntConversion
[native]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/bmc/mod.rs#L388
[adapter]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/jbmc.rs#L619
[e053]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/053-idiv-that-leaves-division-by-zero-to-the-host/README.md
[asserts]: https://docs.oracle.com/javase/specs/jls/se21/html/jls-14.html#jls-14.10
[sarif]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/sarif.rs
[gaps]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/src/jbmc_gaps.rs
[manual]: https://diffblue.github.io/cbmc/man/jbmc.html
[handlers]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/lib/tests/fixtures/jbmc-defects/README.md
[pipeline]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/verification/README.md
[accept]: https://github.com/pilifs/in-the-loop/blob/65df5fe7ea0385607f4db7f36ca070001c6688cf/examples/tools/accept.py
