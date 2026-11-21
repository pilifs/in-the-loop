# Curator workflow

The curator keeps the candidate docket, original source, tests, repeat observations, exclusion evidence, selection seed and custody keys in a private workspace outside the evaluation checkout. The operator receives a neutral `pair/` directory. Run the entire operator session with that directory mounted read-only, a fresh writable work area and the pinned product. The curator workspace, original Git history, compiler caches, original client CI and past case reports must remain inaccessible to its tools. [Selection and scoring protocol](../protocol.md)

## Reproduce the registry overlap

`python3 registry_overlap.py SUITE_JSON KNOWLEDGE_JSON` checks the two file digests and prints aggregate counts. The full pinned CompSuite registry has 123 entries and CompCheck has 24 knowledge records. Thirteen CompSuite entries match on client, Maven coordinate, old version, new version and exact developer test. Each old version in a CompCheck record's `versions` array contributes a possible match.

## Record the private docket

Store a stable ID, discovery source, prior client/library exposure, disposition and supporting evidence for every candidate. Keep source retrieval, build failures, attempted replays and successful admissions distinguishable. A case can acquire several attempted reproductions as archived inputs become available. Record an earlier exclusion or deferred build in its history before resuming it.

`screen.py order CANDIDATES OUTPUT --seed SEED --commitment COMMITMENT` reads a private JSON array containing a `stable_id` per row. It verifies the seed commitment and writes a new private ordered file. CompSuite precedes BUMP. For routine candidates, supply `--anchor` with the original upgrade's timestamp and records with a UTC `merged_at` and `match_tier` of 1, 2 or 3. The order uses tier, absolute time distance and seed rank. Retain the search responses and candidate evidence for each tier. Account for an incomplete search or an earlier uninspected candidate before claiming the nearest eligible match.

## Audit a reference replay

Run `python3 screen.py audit PRIVATE_PACKET`. The packet contains `reference.json` and the files it names. Paths are relative to the packet. Store the reproducer source, commands, input fixtures, original named-test reports and runtime logs there. Preserve original client CI in its own evidence records. Describe full CI availability and the actual command for a scoped direct JVM run separately.

| Reference field | Contents |
|---|---|
| `stable_id`, `source_kind` | The registry/PR ID and `upstream_pr` or `benchmark_pair`. |
| `entry`, `observer`, `scope`, `consequence` | The original consumer operation, caller observation, admitted inputs and environment, and the effect on a maintainer decision. |
| `eligibility_review` | A JSON file recording the curator's `ordinary_functional_upgrade`, `production_java_maven`, `security_incident` decisions and an `evidence` path. |
| `closure_review`, `independent_basis` | Files documenting the resolved upgrade closure, causal attribution, and the independent expectation or discriminator. |
| `basis_kind` | `developer_expectation`, `independent_discriminator`, `exhaustive_oracle`, `justified_contract` or `independent_proof`. Preservation also supplies an `expected_observation` JSON file. |
| `named_test` | Exact `class` and `name` for the developer test, including the registered subclass or parameterized name as appropriate. |
| `companion_absence` | Explanation when a changed observation has no feasible preserving companion. |

Each of `old` and `new` contains the detached `revision`, a `production_manifest` JSON file mapping original paths to SHA-256 in separate `source` and `generated` objects, and paths to `effective_pom`, `subject_environment` and `ordered_classpath`. The classpath is an ordered array of objects with `name` and `sha256`. Record how the manifest was enumerated and which generator ran. Retain material needed to obtain or reproduce the recorded bytes.

Each side's `runs` array names independent executions. Each run has an `execution_log`, `loaded_artifacts` and `receipt`. The latter is a JSON record written by the runtime observer in a fresh run directory, containing a unique `run_id`, the actual `entry`, `reached`, the caller's `observation` and an optional preserving `companion`. Loaded artifacts identify each observed `class`, its `role` (`consumer` or `dependency`) and its runtime classpath `sha256`. Capture the real JVM class origins. A CompSuite case repeats both sides independently. For a named test, `test` in each run records `class`, `name`, `format` of `junit-xml`, and the `reports` paths. A custom runner can supply `format` of `custom`, an `execution_record` and an executed `outcome`.

The checks compare both actual observations, source manifests, loaded artifact versions and repeat trials. They reject skipped, absent and ambiguous named testcases, disagreement between repeats, and preservation without a matching independent expectation. The curator and adjudicator inspect the submitted evidence to decide whether the observer reached the real consumer, whether the classpath and generated-source manifests are complete, and whether a proof or exhaustive domain covers the claimed scope.

## Seal the answer

`seal_reference.py` uses Python's `cryptography` package. Keep its 32-byte AES-256 key and raw 32-byte Ed25519 private key outside the packet. The public key comes from the pre-product seed commitment. A neutral packet ID appears in the authenticated header. Use an ID independent of the stratum.

```sh
python3 seal_reference.py seal NEUTRAL_ID PRIVATE_PACKET SEALED_FILE \
  --signing-key SIGNING_KEY --encryption-key ENCRYPTION_KEY --commitment COMMITMENT
python3 seal_reference.py verify SEALED_FILE --commitment COMMITMENT
python3 seal_reference.py open SEALED_FILE PRIVATE_ARCHIVE.tar.gz \
  --encryption-key ENCRYPTION_KEY --commitment COMMITMENT
```

The tool archives regular files, encrypts the archive with a fresh AES-GCM nonce and signs the header, ciphertext and tag using Ed25519 over a domain-separated SHA-256 digest. Verification needs only the pinned public key. Opening checks the signature and the authentication tag before publishing the decrypted archive. Each output is written once. Publish only neutral IDs, signed envelope receipts and aggregate counts during the blind phase. Seal the membership and exclusion records separately for the main and transfer sets.

## Allocate the main and transfer sets together

Run the allocator in the private curator workspace before opening any scored report. It needs local Z3 on the path. The input and output stay outside the evaluation checkout. Standard output gives aggregate counts and outstanding audit requirements.

```sh
python3 allocate.py PRIVATE_DOCKET.json NEW_PRIVATE_RESULT.json --seed PRIVATE_SEED --commitment PUBLIC_COMMITMENT.json
```

Use a JSON object with `changes`, `routines`, `searches` and `audit`. Every evidence pointer below is an object with a `file` relative to the docket and its `sha256`. The allocator checks the files against these digests.

| Input | Required contents |
|---|---|
| Every candidate | Its `stable_id`, `review` of `qualified`, `pending`, `excluded` or `deferred`, and `evidence` for that decision. A pending candidate can already have a signed reference. |
| A qualified candidate | `client`, `family`, `old_version`, `new_version`, `trigger`, `incident`, `version_step`, `build`, and `changed_at` for a change or `merged_at` for a PR, with a time zone. Normalize the upstream client and release-family identities across sources. Give duplicates from the same underlying incident the same incident identity. The fallback tier compares `major`, `minor`, or `patch` and `single` or `reactor`. |
| Original-production reference | Set `reference_audited` after reviewing the original reference and supply its signed envelope as `reference`. The JSON decision named by `evidence` must bind `stable_id`, `stratum` of `change` or `preservation`, `packet_id` and `signed_envelope_sha256`. The allocator verifies the envelope signature against the pre-product public key. |
| Each search | Its change `anchor`, distinct `routine_ids` from the frozen discovery frame, boolean `complete` and `evidence`. Include closer unresolved leads in the docket as pending. An exhausted search can have an empty list. |
| Audit | Boolean `before_v0_scoring` and `ranked_review_complete`, and `ledger` covering the full candidate and exclusion record, prior exposure, aliases and discovery frame. Include all decisions that could affect the ranked selection in the allocator input. The ledger can record later unvisited entries outside that frontier. |

The allocator pairs all sixteen changes, including the reserve, with distinct routine upgrades. It orders pairs by change source and seed rank, then by matching tier, absolute date distance and the PR's seed rank. It chooses the earliest main pair that still admits a full main and transfer allocation, repeating for the remaining main pairs and then the reserve. Both strata contribute to the set of clients and families represented in the 24.

Long private BUMP replays can use `queued_bump.py` as a verification job. The queue receives an opaque packet ID, the submitting custody session and the digest of the frozen input manifest. The launcher checks the reviewed generic worker and public networkless runtime before starting four original Maven trials. It publishes only the number of complete attempts and fresh exact testcases, elapsed time and the hashes binding them to the private receipts. The original Maven commands, logs, XML, application observations and stratum remain with the curator. A completed queue job alone confers no eligibility or cohort assignment.

Exit status 0 produces a private `ready-to-seal` allocation with separate main and transfer membership digests, verified reference receipts and the full input digest. The curator signs the rosters. Exit status 2 gives an aggregate shortfall or outstanding audit work and publishes no memberships. Its attainable counts describe one simultaneous allocation, maximizing main pairs first, then reserve pairs and then represented-family counts within each reserve stratum. Exit status 1 means the input, signature or local solver could not be validated.

## Release the review-time source pair

`python3 export_pair.py PRIVATE_PLAN FRESH_DESTINATION` emits `pair/old/`, `pair/new/` and `pair/pair.json`. The last contains the neutral case ID and hashes of the two exported trees. The private plan specifies `case_id`, `forbidden_literals`, and `old`/`new` objects. Each side identifies a local upstream `repository`, pinned commit `revision`, and a `files` object accounting for every tracked path in that Git tree. Submodules can supply a nested plan pinned at the gitlink. Retain this plan in the signed custody packet to tie every released source and dependency descriptor to its original blob.

For each file set `original_sha256`, `role` and `action`. Use `copy` for ordinary review-time files, including ordinary test methods and fixtures. `omit` requires a private reason. For a mixed test class, use `strip` with a private reason, ordered byte deletions (`start` inclusive, `end` exclusive and `sha256` for each removed span) and the resulting `retained_sha256`. Only the specified bytes are deleted. Production source and dependency descriptors are copied unchanged. The complete original code and the hidden triggers stay with the curator.

Include specific trigger methods, fixtures, duplicates, provenance strings and their compiled spellings among the forbidden literals. The exporter also scans for both original revisions, history directories, test build outputs and test reports. It inspects names and uncompressed contents of nested JARs, ZIPs and tar archives. Supply a neutral read-only mount to the operator after reviewing the exported pair. Run the ordinary historical build and full original test suite separately on the unredacted checkout.

To supply the measured production classpaths, add a `runtime_artifacts` array to each side of the private plan. Its first entry has `role` of `client`, the original build's `source` JAR path, its `sha256`, and `production_members` mapping every original production class or resource in that JAR to its SHA-256. The following entries have `role` of `dependency`, their original JAR path and digest, in the order used by the JVM. The exporter checks the complete client membership and scans each JAR for hidden fixtures. It writes the files and the ordered `side`, `path`, `sha256` rows under a separate `dependencies/` directory. Supply its `manifest.json` and trusted SHA-256 to operator intake alongside the neutral source pair and its trusted manifest digest. [Operator intake](../operator/README.md)
