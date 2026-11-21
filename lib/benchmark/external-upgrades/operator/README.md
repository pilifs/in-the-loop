# Blind operator execution

**The frozen verifier and both official Claude roles have passed isolation checks.** The first disclosed local pair stopped at source intake before inference. Scored launches await the two signed rosters. The original Codex profile still advertises file and cross-thread tools whose confinement has yet to be demonstrated. Its admission check exits 2. [Disclosed first report](claude-alternate/opening-reports/V0/u-7b26f3c1/operator.json) · [Native proof](evidence/native/result.json) · [Stock Codex catalogue](evidence/stock-codex.json)

## What the synthetic case exercised

A fresh operator packet contained a Maven descriptor and an integer method on each side. Each original JVM returned `42` for input `41`. The pinned `build.py --plan`, `build.py --task preserve` and `workflow_handoff.py` ran in the same private filesystem. Bitwuzla established equality for the signed Java `int` domain using the checker at `e7cdfb6a6edea96c8653ee87a7c1e2ef3f602665`. The native attempt took 0.3 seconds. Its receipt records the executable hash, JDK, classpaths, solver and bound. This is a synthetic toolchain check with a human-supplied property. [Pinned product](../v0.json) · [Synthetic claim](synthetic/claims/preserve.json)

The host prepares the tool root from named system programs, the system Python standard library and schema-validation packages, selected JDK files, the pinned solver binaries, and V0 workflow files read from the immutable revision. Each launch verifies the assembled root, the released pair and its expected digest before `bubblewrap` creates private mount, PID, IPC, UTS and network namespaces. Only the packet and trusted tools are mounted read-only. The case work area and generated example are separate writable mounts. The operator process starts with an explicit environment and zero effective capabilities. The root uses no host home, repository, daemon socket or model credential mount. [Environment builder](isolation.py)

Inside the guest, the positive canary was readable and a private work file was writable. The original packet and product rejected writes. Separate synthetic files for curator references, hidden tests, knowledge, previous reports, transcripts and another case were inaccessible by their known absolute host paths. A connection to a non-loopback documentation address failed with no external interface. A second case saw empty working and cache directories. The dependency control exposed one explicitly released file, rejected writing it and excluded its unlisted sibling. [Dependency control](evidence/dependencies.json)

## Model admission

`mcp_server.py` accepts one MCP command. Its process fixes the case and product roots before any model input. `case_command` takes an argument vector, launches it in the namespace, bounds wall time and output, and returns the exit code and combined output. Unknown tool names and caller-supplied mounts, environment and host paths in the control envelope are rejected. A released file path passed to a guest program resolves inside the guest. The MCP server has empty prompt and resource lists. [Command gate](control.py) · [MCP server](mcp_server.py)

The real installed `codex exec` client constructed requests for `gpt-6.2-sol` and `gpt-6.2-astra` with the pinned effort and prompt in separate empty profiles. Its only configured MCP server advertised `case_command`. Shell and unified execution, web search, apps and multi-agent feature settings were disabled. A new process in the networkless synthetic guest captured the full tool catalogue, including the `additional_tools` input item, at a loopback provider endpoint. Both requests were rejected before inference. The only check on the real account was `codex login status`, which reported a signed-in ChatGPT session. The receipt records the boolean and login kind. The run made zero live model calls. [Stock-client probe](codex_probe.py)

Both roles still advertised `apply_patch`, `view_image` and the collaboration namespace. There is no observation that confines these stock paths to the neutral case on the normally authenticated control side. A scored run requires that observation for every path. A control service whose ordinary model tools all execute in the restricted namespace could use this same physical host. A dedicated clean VM or role account with authenticated inference brokered outside the model tools is another way to establish the boundary. Run the positive, outside and cross-session canaries through the ordinary client before admitting either architecture. [Admission check](admission.py)

## Restricted Claude operator

The team’s Fable 5.2 and Opus 5.5 roles each completed an authenticated synthetic observation through the ordinary installed client. The positive tool read and write succeeded. In a separate loopback trial, synthetic curator data, other cases and prior sessions were inaccessible. The client exposed only the neutral case command. Each role reproduced both integer observations. The reported cost is the client's estimate. [Live receipts](claude-alternate/evidence/live.json) · [Tool catalogue and isolation controls](claude-alternate/evidence/restricted.json)

The disclosed scheduler reserves the cost in tokens of one request at a time. A fresh process continues from case files and a bounded history of that stage. The independent reviewer can see the proposal and the released inputs. Native continuous sessions have a different history and can make additional requests in response to internal tool rejections. Keep the scheduler qualification with any claim-selection result. The profile binds the six controller and prompt files, stock client, product and executable. The lifecycle checks cover interrupted workers, the 15-minute checkpoint, queue time, token reservations and duplicate report publication. [Profile](claude-alternate/v0-claude.json) · [Lifecycle controls](claude-alternate/evidence/lifecycle.json) · [One-request control](claude-alternate/evidence/single-request.json)

For a disclosed run, place the verified isolated product under `~/.cache/in-the-loop/external-upgrades/tool-roots/<tool-root-sha256>` and each public `release` under `disclosed-pairs/<pair-sha256>` in that cache. The queued Commons Text invocation records the four-vCPU, 16-GiB scope and the exact issue-time UTC, source pair and dependency-manifest hashes. The model has no access to the host cache or queue. Only the case's adjudicable first report and its declared evidence are collected. [Reproduce the released inputs](../README.md#reproduce-a-disclosed-operator-packet) · [Run a fresh case](claude-alternate/run_case.py)

## Reproduce

From the repository root on the Ubuntu x86-64 runner, use a fresh directory below `$TMPDIR`. `isolation.py product` verifies the cached V0 checker and the source manifest. The synthetic native check is one capped probe under the repository's verification procedure.

```sh
op=lib/benchmark/external-upgrades/operator
area="$TMPDIR/neutral-operator-reproduction"
python3 "$op/isolation.py" product "$area/product" \
  --jdk "$HOME/.sdkman/candidates/java/21.0.13.0+9-tem" \
  --bitwuzla "$HOME/tools/bitwuzla/current/lib/x86_64-linux-gnu"
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 timeout 300 \
  python3 "$op/probe.py" --product "$area/product" --native --with-dependencies \
  --scratch "$area/synthetic-case" --output "$area/namespace.json"
python3 "$op/codex_probe.py" --product "$area/product" \
  --codex-bin "$CODEX_NATIVE_BIN_DIR" --scratch "$area/synthetic-control" \
  --output "$area/stock.json"
python3 "$op/admission.py" --namespace "$area/namespace.json" --stock "$area/stock.json"
```

`CODEX_NATIVE_BIN_DIR` is the installed native Codex package directory containing `codex` and `codex-code-mode-host`. For a released neutral pair, `isolation.py case NEW_CASE RELEASED_PAIR EXPECTED_PAIR_JSON_SHA256` creates private case storage. An optional `--dependencies RELEASE.json --dependency-digest EXPECTED_SHA256` copies only the explicitly listed dependency files, preserves their ordered manifest, and exposes them read-only at `/case/dependencies`. The manifest contains `case_id` and `artifacts`. Each artifact has `side` (`old`, `new`, or `both`), a relative `path` and `sha256`. Supply the expected digests from the independently approved operator release. The curator remains responsible for removing the hidden trigger and duplicates from those inputs. [Neutral-pair release format](../curation/README.md)
