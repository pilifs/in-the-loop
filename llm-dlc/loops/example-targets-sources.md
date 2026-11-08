# Sources and review scope for example targets

Prepared **2026-11-08**. Source inspection and design research only. No repository modifications, builds, concrete reproductions, or formal verification attempts were performed for this review.

## Repository baseline

Repository: [pilifs/in-the-loop](https://github.com/pilifs/in-the-loop).

Immutable reviewed commit: [57f04e556377d6c7d01524d0f0cc537ab87c58da](https://github.com/pilifs/in-the-loop/commit/57f04e556377d6c7d01524d0f0cc537ab87c58da), “Record session traces,” authored 2026-11-08 04:29:30 UTC. This was remote HEAD when inspection began; launching implementation requires a new baseline check.

| Subject | Primary source and supported finding |
|---|---|
| Local workflow | [CLAUDE.md](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/CLAUDE.md): jj/sync workflow, queued proofs, numbered example router and example-local notes |
| Loop conventions | [brief-template.md](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/llm-dlc/loops/brief-template.md): one step per cycle, two-failure timebox, pipeline mode and launch metadata |
| Current application-core | [application-core.md](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/llm-dlc/loops/application-core.md): recounted baseline, Phase 0 progress, reserved IDs, user decisions and deferred replay/initializer findings |
| Pending implementations | [construction.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/construction.rs), [values.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/values.rs), [environment.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/environment.rs), [reuse.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/reuse.rs): registered interfaces still return unsupported/no-summary results at this snapshot |
| Existing composition | [compare.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/compare.rs): observation, effect, alignment, kernel and cache composition |
| Proof entrypoints | [main.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/main.rs), [equivalence.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/equivalence.rs), [property.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/property.rs): actual CLI, input gates and absence of a standalone fix command |
| Current runner seam | [build.py](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples/tools/build.py): pure planning, real-world refusal, claim records, publication and index behavior |
| Result representation | [result_format.py](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples/tools/result_format.py), [stored-result.schema.json](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples/schema/stored-result.schema.json), [result.schema.json](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples/schema/result.schema.json): format 2, separate execution and semantic conclusion, statements and constrained evidence |
| Authored metadata | [example.schema.json](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples/schema/example.schema.json): source metadata lacks full artifact/build locks |
| Pipeline | [pipeline.py](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/verification/pipeline.py), [verification README](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/verification/README.md): independent example gate, clean exports, resources, execution-based job status |
| Known failures | [findings.md](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/verification/findings.md), [witness.rs](https://github.com/pilifs/in-the-loop/blob/57f04e556377d6c7d01524d0f0cc537ab87c58da/lib/src/witness.rs): historical failed jobs and the need to validate both replay outcomes |
| Current inventory | [examples](https://github.com/pilifs/in-the-loop/tree/57f04e556377d6c7d01524d0f0cc537ab87c58da/examples): 164 authored example metadata files; five real-world entries, 105–109. Counts are from this tree, not the historical root README. |

No tracked AGENTS.md was found. This review read the repository's CLAUDE.md and relevant workflow documents. Existing user choices and current code take precedence over the outside brief.

## Prior discussions and saved brief

Relevant context was recovered from the named discussions **“Zero Spec Verification”** and **“Review And Rank Proof Checkers.”** The retrieved material supplies summaries/excerpts of the design discussions, not a complete authenticated transcript of each titled chat. No exact message URLs were returned; none are invented here.

The preserved direction is low-input relational verification under fixed external inputs and observations; untrusted agents can propose correspondences, tactics and supporting arguments, while deterministic evidence determines proof conclusions. Preservation, security improvement, model fidelity, artifact fidelity and evidence status remain separate.

The saved `application-core-all-documents.txt` (the user's own copy of the earlier outside plan), prepared 2026-11-07 against the reported earlier snapshot `cbf183a`, was read for the prior four-stream plan and scope. Its proposed objects/values/environment/reuse work is historical planning context. The repository's later adopted application-core brief and actual code establish what is currently present. Its earlier deferral of broad CVE campaigns is consistent with this new request for scaffolding a small portfolio, while leaving the broad proof campaign for later.

The available `agent-plan.txt` was also consulted for handoff conventions. It is overlapping historical design material, not proof of current implementation.

## Original CVE research input

The package includes `inputs/spring-cve-targets.research-2026-11-04.json` (committed here as `example-targets-inputs/spring-cve-targets.research-2026-11-04.json`), an unchanged copy of the earlier registry. It contains 15 CVEs across 10 families, with research metadata for 16 primary fix commits and two unconfirmed introduction candidates. Every case was unexecuted.

Original SHA-256: `e86301abe767bcd9c39c5c9dc8889dfcbb1c22bb45bead53fc630acd0b9c62e5`.

That input's verifier review used the older commit `4c279ba6f3b46ecac8cf938903059ee993a36968`. Its capability descriptions are stale for this design. Preserve its historical facts and uncertainty, then revalidate the specific artifact/revision mappings used by a promoted target.

The new seed plan is research metadata for this design, not an executable target schema or generated result. It does not claim build recipes, JVM reproductions, proof support or proof conclusions that have not been demonstrated.

## Negative target sources

| Case | Official scope and selected fix |
|---|---|
| CVE-2023-34055 | [Advisory](https://spring.io/security/cve-2023-34055/) identifies the Boot MVC/WebFlux Actuator DoS issue and 2.7.18 fix. [Patch 5490e739](https://github.com/spring-projects/spring-boot/commit/5490e73922b37a7f0bdde43eb318cb1038b45d60) supplies the method-label change. |
| CVE-2022-22968 | [Advisory](https://spring.io/security/cve-2022-22968/) describes case-sensitive disallowed-field patterns and 5.3.19 fix. [Patch a7cf19ce](https://github.com/spring-projects/spring-framework/commit/a7cf19cec5ebd270f97a194d749e2d5701ad2ab7) supplies normalization changes and regression tests. |
| CVE-2025-22228 | [Advisory](https://spring.io/security/cve-2025-22228/) identifies incorrect long-password matches and lists 6.3.8/6.4.4. [Patch 46f0dc6d](https://github.com/spring-projects/spring-security/commit/46f0dc6dfc8402cd556c598fdf2d31f9d46cdbf3) tests byte length, an important precision beyond the advisory's word “characters.” |
| CVE-2024-38820 | [Advisory](https://spring.io/security/cve-2024-38820/) and [patch 23656aeb](https://github.com/spring-projects/spring-framework/commit/23656aebc6c7d0f9faff1080981eb4d55eff296c) are the linked locale-normalization challenge retained from the earlier registry. |

The first three advisories were reopened during this review. Exact fix-parent metadata derives from the prior source inspection and remains subject to materialization checks. No new introducing transition was proved.

## Independent positive sources

| Seed | Exact parent → child | Primary evidence |
|---|---|---|
| Boot MVC outcome classification | `9b8decf99c9665f219cdd3a7c3fa9aaa61aec3ca` → `e8de5a6d95ffb45cd532c2a863e6a726e159b7e3` | [Commit](https://github.com/spring-projects/spring-boot/commit/e8de5a6d95ffb45cd532c2a863e6a726e159b7e3), [issue 18150](https://github.com/spring-projects/spring-boot/issues/18150). Full eight-file patch/parent inspected; the chosen MVC slice extracts outcome classification into an enum. |
| Framework wildcard prefix comparison | `27bfcbbc823897169942ddc9a9ff9538486426c5` → `db9a10bf3524923e8cd5be3f2b847002b8289f75` | [Commit](https://github.com/spring-projects/spring-framework/commit/db9a10bf3524923e8cd5be3f2b847002b8289f75), [issue 26822](https://github.com/spring-projects/spring-framework/issues/26822). Full patch/parent inspected; replaces prefix-substring equality with startsWith. |
| Security password UTF-8 API | `fb39d9c255196031a9622cfd197d1fb05fd96bb2` → `fe9e4549780e940c9cef7f2991e75e0b686fc5d1` | [Commit](https://github.com/spring-projects/spring-security/commit/fe9e4549780e940c9cef7f2991e75e0b686fc5d1). Full patch/parent inspected; BCrypt uses StandardCharsets.UTF_8 in place of a charset-name lookup. |

These commits were found in upstream path history and their public commit API responses inspected. Their claimed preservation is the proposed experiment, not a checked result. The MVC slice's expected behavior must not be generalized to every file in the Boot commit.

A reserve [Boot allocation optimization, d6761476](https://github.com/spring-projects/spring-boot/commit/d6761476803e519ecb74e2c7e1fd78ea2e165250), is useful for demonstrating that preservation can hold while both revisions still violate a security invariant. It is not a fourth mandatory positive.

## BCrypt follow-up chronology

The [CVE-2025-22234 advisory](https://spring.io/security/cve-2025-22234/) explicitly attributes the broken timing-attack mitigation to the CVE-2025-22228 fix. It names 6.3.8/6.4.4 as affected and 6.3.9/6.4.5 as the OSS fixes. The [upstream regression issue 16802](https://github.com/spring-projects/spring-security/issues/16802) links the fix and legacy-password behavior.

[Repair c1aa99fd](https://github.com/spring-projects/spring-security/commit/c1aa99fdd2113a232986e9c3a44673ae752de840), parent `eb013944277879b4c1541857a5b8263f5235ff82`, changes the length guard to apply only to new encoding, with tests for legacy matching. Public compare responses establish that `46f0dc6d` is its ancestor and that the repair is in the 6.3.8 → 6.3.9 release window. The repair's snapshot is 6.3.9-SNAPSHOT.

Vendor attribution and ancestry are stronger than a guessed introduction, but they are not a formally established good-to-bad timing transition. The seed remains a linked challenge. A functional API claim, an explicit cost model and actual wall-clock behavior are different scopes.

## Evidence limits

This design recommends an architecture, work split and acceptance gates from the inspected code and history. It establishes neither current buildability nor formal success of any new target. Public patch/parent inspection supports the revision metadata; running original artifacts and freezing executable contracts is the implementation wave's work. Past authored reports and proposed agent briefs are never substituted for current proof receipts.

## How this page was adapted

Kept as the outside review wrote it on 2026-11-08, except for the earlier plan's private link, which is replaced by a
description, and the registry's path in this repository. Its claims about the code were recounted in
[`example-targets.md`](example-targets.md#where-it-starts-from), which corrects three of them: the one-sided replay it
attributed to example 109's record is VF-015's step 4 (job `20261108-024648`) and is fixed after `57f04e55`
(`lib/src/witness.rs:779-786`); example numbers are reserved only in briefs, and 197–279 are all unused; and
`example.schema.json` is closed on every object, so a sidecar reference is a schema change. Its seed metadata is
[`example-targets-inputs/seeds.json`](example-targets-inputs/seeds.json), unchanged.
