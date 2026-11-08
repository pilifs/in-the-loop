# Acceptance contract: example targets

The acceptance contract of [`example-targets.md`](example-targets.md), drafted 2026-11-08 from the outside plan. It is a
set of requirements, not observed results, and it is frozen with Phase 0's fixtures before the streams fork. Every
stream reads it in full every cycle. It is not a brief: no loop runs on it.

## What the feature must establish

External changes become reproducible, fixed-claim work packets that later agents can execute, prove, refute, or connect
to an observed library gap. Importing research metadata alone doesn't meet that.

Infrastructure and targets are accepted separately. The infrastructure must execute real upstream bytecode through the
integrated path and correctly ingest at least one supported verifier task. A target can be a reproducible scaffold
while its proof is blocked, once its sources, build, concrete oracle and JVM replay are established; a metadata or
build blocker leaves it partial.

Neither a desired outcome nor a pipeline exit code is proof. The pipeline's `passed` means the steps exited as expected
([`verification/README.md`](../../verification/README.md)), which is an execution status, not a verifier result. Keep
that distinction in every gate.

## Tier A: infrastructure

Every row passes on the merged revision, with its commit and job ids, not only branch-local tests. The case packets
meet the infrastructure in Phase 5 ([decision 2](example-targets.md#decisions)), so A3–A5 are the main loop's, built from
the streams' work.

| Gate | Required observation | Built by | Checked |
|---|---|---|---|
| A0 Shared contract | The strict sidecar schema, `TaskPlan`, `PreparedTarget`, attempt ingestion, hooks, fixtures, reserved numbers and JDKs committed before the fork | Phase 0 | Phase 0 |
| A1 Offline planning | Plan, lint, discovery and handoff inspection run with no network, build, solver or source mutation; unsupported requirements are visible | workflow | stream, then Phase 5 |
| A2 Preparation integrity | Exact revisions, dependency and artifact hashes, JDK, adapter, classpath order and the original target's identity recorded; wrong bytes, shadowed classes and escaping paths refused | runtime | stream, then Phase 5 |
| A3 Original negative replay | At least one seeded CVE's vulnerable/fixed pair materializes; its independent predicate observes the vulnerable violation, the fixed security response on the same trigger, and retained legitimate behaviour, on the original pinned libraries | negative's packet, runtime's path | Phase 5 |
| A4 Independent positive replay | At least one independent positive pair materializes and passes its declared original-JVM controls, and its nearby constructed mutation fails the same claim and control | positive's packet, runtime's path | Phase 5 |
| A5 Supported verifier calibration | Example 105 (or 106, with the documented reason) produces an actual established or refuted structured result through the integrated path under a fixed claim, with non-vacuity evidence or an independently replayed witness. Unresolved doesn't pass. | positive's migration, runtime and workflow | Phase 5 |
| A6 Receipt integrity | Several tasks and attempts keep distinct format-2 receipts; execution, conclusion, expectation, scope and replay stay separate | workflow | stream, then Phase 5 |
| A7 Agent continuation | A fresh agent or isolated session follows an exported packet to reproduce a result or one observed blocker, without rediscovery or weakening the claim | workflow | Phase 5 |
| A8 Combined integration | Existing relevant examples keep their outcomes; the new native tasks run with JBMC absent; shared tests and queued acceptance jobs pass at the merged revision | the main loop | Phase 5 |

A3 and A4 execute the selected original upstream implementation and its declared dependency closure. Schema
validation, a surrogate target or an assumed replacement can't satisfy them. A deterministic request or response test
carrier may supply the declared raw inputs, if its behaviour and hashes are recorded and it neither normalizes the
trigger nor impersonates the target: that is a method-scope experiment, not a proof about a servlet container. A5 keeps
an all-blocked corpus from making an untested verifier integration look complete. Use a small, already supported
obligation of 105 first; document a genuine blocker before selecting 106; never substitute a constructed example.

## Tier B: targets and the portfolio

The 15 CVEs of the archived registry and the linked research-only CVE-2025-22234 are in the catalog. The entries for
CVE-2023-34055, CVE-2022-22968 and CVE-2025-22228 are promoted in place, never numbered twice, and paired with the three
independent historical positives of the seed file (Boot, Framework, Security).

Each of the six deep targets has its own row, with:
1. exact source revisions and provenance evidence, the fix, release and introduction roles kept apart;
2. a pinned build or materialization recipe, resolved dependencies, and artifact identity;
3. named property and preservation tasks, target descriptors, explicit domains and observations, bounds, and expected
   semantic outcomes;
4. a concrete independent oracle and replay driver, with meaningful triggers and legitimate inputs;
5. a capability probe, the current evidence, and the next executable action.

| State | Meaning |
|---|---|
| Catalogued | Research identity and relevant evidence exist; build and replay may be absent |
| Partial scaffold | A packet exists, but provenance, build or replay is blocked or incomplete |
| Reproducible scaffold | Both required revisions materialize, the oracle executes, and the claims are frozen; proof support may still be blocked |
| Attempted | A claim has an actual verifier receipt, unresolved included |
| Claim closed | That claim has its required established or refuted evidence at its stated scope; other tasks stay independent |

A source lock with a build blocker is not reproducible. A capability refusal coexists with a reproducible scaffold only
when the concrete original-JVM path is sound. A predicted missing feature stays a prediction until a probe produces
evidence.

Portfolio completion is reported as counts at each stage, with all six targets listed. Catalog-only cases stay in the
denominator and the router. A run that stops with partial seeds reports a partial portfolio: Tier A passing doesn't
turn six incomplete packets into six complete scaffolds.

## Fixed claims and expectations

Each promoted CVE has separate tasks: the vulnerable security property (expected refuted), the same property on the fix
(expected established), and preservation outside an explicit allowed-change region (expected established). Actual
unresolved results stay unresolved. The sixteen CVEs' expectations are never all set to `unverifiable` to satisfy a
gate.

The two security tasks share a property definition and domain, and bind different artifacts, so their claim identities
differ. Plain before/after equivalence may rightly refute an intended fix; that alone doesn't show the defect.

A positive preserves specified observations or satisfies a named independent property. An upstream merged change is not
universally secure because it is a positive target, and its matched CVE need not share a whole-program property: the
common semantic demands are recorded. The CVE fix is remediation, not an independent positive sample.

Introduction tasks need verified ancestry and a stable independent oracle; candidate attribution isn't enough. Where
that evidence is missing, they stay unattempted.

## Required adversarial checks

Focused unit and integration tests at the trust boundary. [`examples/tools/test_build.py`](../../examples/tools/test_build.py)
already covers many of these for constructed examples (kills, timeouts, malformed output, witnesses, bundles); extend
them through the new adapter.

| Challenge | Required result |
|---|---|
| Exit 1 with malformed output, no witness, a kill or a timeout | No accepted negative or security finding |
| A witness whose second version can't replay | Unconfirmed replay, never `reproduced` |
| A vacuous property, or an allowed region that excludes every relevant input | No non-vacuous success; reachability status and missing evidence shown |
| A deny-all or constant-rejection implementation | Legitimate-input and preservation controls fail |
| A changed source, adapter, oracle, dependency, model, observation or domain | A new claim or a stale receipt, never silent reuse |
| Unknown fields, a mutable revision, an artifact mismatch or a path escape | Refused before the target runs |
| A source slice or surrogate kernel in place of the original code | A separate task and a narrower scope; no original-bytecode claim without a correspondence |
| An old report's authored success label | Historical context only; no receipt or success synthesized |
| Native execution without JBMC installed | Works for supported tasks; no hidden mandatory dependency |
| A downloaded file whose sha256 differs from its lock | Refused as a preparation failure, never rebuilt silently |

Relevant revisions run in separate JVMs or classpaths, every side's complete outcome is recorded, and target-class
shadowing is detected. Class initialization is never removed, the trigger never normalized away, and no throwable
caught as success. Generated-environment replay is explicitly model replay.

For BCrypt: 71, 72 and 73 UTF-8 bytes and multibyte inputs, against a valid pre-existing stored hash so that encoding
can't short-circuit the match. Output or call-trace equivalence establishes no timing guarantee; CVE-2025-22234 stays a
catalog-only challenge to that scope.

## Evidence and gap closure

Every receipt binds the task and canonical claim to source and artifact, tool, JDK, dependency, adapter, model and
oracle identities, and keeps the exact bounds, assumptions, trust levels, observations, execution outcome,
per-obligation conclusions, witness, replay status, logs and resource use. Earlier attempts stay.

An observed gap packet names the exact command, revision, diagnostic, minimal reproducer, missing semantics, suggested
owner and closure test. A later extension closes it only by rerunning the original claim with the new implementation
and recording new evidence; a narrower substitute is useful, but doesn't close it. Advised-mode contracts keep their
proved, tested and trusted levels; an assumption that changes semantics creates a linked new claim; no contract assumes
the vulnerable target behaves securely.

## Completion record

The main loop's final record lists every Tier A gate, the six deep targets, every catalog entry, every queued job, every
timebox deferral, and the ranked v1 gap inventory. It says which claims were proved, refuted, unresolved or not
attempted, and what each scope permits concluding. The feature is ready for use only once its Tier A gates pass; claim
completion and portfolio completion keep their own status. Broad CVE proof campaigns, engine extensions, timing models
and the user-deferred VF-015 work are outside this contract.
