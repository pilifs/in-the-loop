# V0-Claude operator profile

**V0-Claude qualified on a live public synthetic case with first-party Claude Code 2.1.327.** Fable 5.2 high and Opus 5.5 high each used the isolated case MCP, compiled both released Java revisions, returned `42` twice and echoed a fresh value available only through a successful case call. Fable took 4.075 s at an estimated $0.0664384 and Opus took 6.328 s at $0.0225228. Both used the same released pair and pinned V0 checker. The total client estimate was $0.0889612. [Live receipt](evidence/live.json) · [Frozen profile](v0-claude.json)

| First-party role | Uncached input, including cache creation | Generated tokens | Cached input | Tool calls |
| --- | ---: | ---: | ---: | ---: |
| Fable planner, reviewer and prover | 3,837 | 109 | 3,592 | 1 |
| Opus preparation | 2,479 | 113 | 2,234 | 1 |

At the study's frozen list prices Fable and Astra both cost $8/$40 per million ordinary input/output tokens. Opus at $4/$20 costs twice as much as Sol at $2/$10. The table above records observed client estimates for the synthetic tasks. The unchanged deterministic engine uses repository revision `e7cdfb6a6edea96c8653ee87a7c1e2ef3f602665`. Scored reports use `build=V0`, the original engine lock's SHA-256 as `product_sha256`, and `343d4af671dfa6328f5a55e2a7feb65246c7ab1370c1b29e767c035aeaed1952` as `profile_sha256`. [Pricing assumptions and stage roles](v0-claude.json) · [Original engine lock](../../v0.json)

## Effective tool boundary

The control-side client uses its existing first-party login, a neutral empty working directory, `--restricted`, `--tools ""`, explicit `--strict-mcp-config`, `--disable-slash-commands`, `--permission-mode dontAsk`, `--no-session-persistence`, and `ENABLE_TOOL_SEARCH=false`. The MCP fixes one case before reading model input. The case tool sees immutable V0 files and only the released source and dependency bytes, plus its private writable space. The controller never reads, copies or forwards account credentials.

Five loopback Messages requests per role exposed exactly `mcp__neutral_case__case_command`. Each real CLI dispatched the frozen case command once, wrote only into its own case, rejected direct `Read`, `Agent` and placeholder dispatch, and denied all outside canaries. The ten requests contained none of the planted home, temporary path, project instructions, rules, auto-memory, other history or private reference markers. Only the neutral guest working directory and ordinary account/device/session metadata field names were present. A planted user hook and unlisted project MCP never started. Earlier profiles remain available. Safe mode suppressed the explicit case MCP, and default deferred search also advertised a placeholder. [Qualified catalogues and actual dispatch](evidence/restricted.json) · [Safe-mode trial](evidence/safe-mode.json) · [Deferred-search trial](evidence/deferred.json)

## Run one released case

`run_case.py` owns one case. The default route uses the official GitHub-only V0 intake and the team's normal stage responsibilities. A fresh Fable reviewer sees the released pair, its closure and the proposed plan in a separate workspace, with no planner transcript or previous case reports. Approved plans and review decisions return to the main case store. Opus prepares the registered tasks. The controller runs V0's ordinary plan and verification commands and freezes their artifacts before Fable reviews the results. Both successful and unavailable original attempts are sealed through `scorecard.seal_report`. [Runtime procedure](../../../../../llm-dlc/runtime.md) · [Role instructions](stages.json) · [Scorecard](../../scorecard.py)

From the repository root, supply the issuer's original intake timestamp, including any queue wait, and the actual released pair and ordered dependency manifest. Keep case work and the report store private. The launcher can create its own systemd scope and uses a matching inherited verification scope when available.

```sh
runner=lib/benchmark/external-upgrades/operator/claude-alternate/run_case.py
python3 "$runner" \
  --release "$RELEASE_DIR/pair" --pair-sha256 "$PAIR_SHA256" \
  --dependencies "$RELEASE_DIR/dependencies/manifest.json" --dependency-sha256 "$DEPS_SHA256" \
  --product "$STAGED_V0" --case-dir "$PRIVATE_CASE_DIR" --reports "$PRIVATE_REPORT_STORE" \
  --received-at "$RECEIVED_AT_UTC" --cohort disclosed \
  --github "$REVIEW_TIME_GITHUB_REPOSITORY" --before "$BEFORE_COMMIT" --after "$AFTER_COMMIT"
```

Omit the three GitHub options for a local-only neutral release. The official workflow then seals the original intake failure before inference. `--assisted-local-source-bridge` is an explicit separate disclosed diagnostic, with a fresh case directory and separate scorecard destination. The restriction that source must be available through the official route still determines the original denominator. A scored or transfer run also takes `--cohort-release` and `--cohort-release-sha256` and checks the curator's Ed25519-signed roster. The standard workflow can still encounter an honest build, dependency, source or verifier blocker. [Packet and case authority](../README.md)

The common case allowance is four vCPUs, 16 GiB, zero swap, two hours from intake, 15 human review minutes and 250,000 uncached input plus generated tokens across all stages. A durable checkpoint records what evidence existed at 900 s. An earlier finish records that fact. `CASE_DIR/first-report.json` and `REPORTS/V0/CASE_ID/` hold the immutable original scorecard and its hashed evidence. Retrying a sealed case returns its original identity. A stopped worker retains its last reservation and an unrecoverable or expired run seals unavailable. The controller prints case-level seal metadata. Solver output and model observations are kept with the private case.

**The metered stage scheduler differs from an uninterrupted native Claude conversation.** It runs exactly one native model request at a time and hands the stage's own files and bounded recent tool observations to the next fresh process. It reserves twice the measured full first-request envelope for the pinned role, 8,192 tokens of additional framing headroom, the JSON-escaped prompt bytes and the maximum 2,048 generated tokens before each request. Only settled native usage is charged. Cache reads are recorded separately, and a missing usage receipt retains the reservation and stops the run. Too little remaining capacity may stop a stage before the numerical ceiling. The native client demonstrated continuity across tool results in the two live smoke sessions, but the scored launcher does not preserve a native conversation between bounded requests. This difference is recorded on the first report and matters for comparisons of claim selection. [Single-request boundary test](evidence/single-request.json) · [Deadline, review isolation and first-report test](evidence/lifecycle.json)

Reproduce the control-plane lifecycle without model calls with `python3 lib/benchmark/external-upgrades/operator/claude-alternate/check_lifecycle.py --scratch FRESH --product STAGED_V0`. The synthetic transport and explicitly budgeted live smoke programs are retained under `qualification/`. A new live smoke requires separate authorization.
