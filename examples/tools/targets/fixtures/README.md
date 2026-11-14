# Phase 0 fixtures

The local, deterministic fixtures of [`example-targets.md`](../../../../llm-dlc/loops/example-targets.md)'s Phase 0,
which every stream's unit checks and the integration contract ([`test_targets_contract.py`](../../test_targets_contract.py))
run on. Nothing here is fetched, and nothing here is an example: this folder is laid out as one (`example.json`,
`target.json`) so the target route can be driven on it from a copy, but it is never placed in `examples/`. Its
`example.json` says `origin: real-world` only because the route takes a real-world example; its sidecar's role is
`control`, and its revisions are fixture sources, never upstream commits.

| Path | What it is |
|---|---|
| `gate/before`, `gate/after` | The two revisions: `fixture.Gate.allowed(int)` denies code 65 ('A'); the fix also denies 97 ('a') |
| `gate/mutant` | A constructed mutation of `after` that denies 97 only: it must fail the same security claim |
| `gate/both` | `fixture.RegexGate`, the same in every revision: a check through `java.util.regex`, the deliberate capability refusal |
| `gate/adapter`, `gate/driver` | A minimal adapter compiled separately against each revision's JAR, and the driver that prints one JSON line per input |
| `gate/oracle.py` | The independent oracle, written from the statement: 65 and 97 never allowed, the legitimate probes allowed |
| `build_fixtures.py OUT` | Builds `before.jar`, `after.jar`, `mutant.jar`, `adapter-*.jar` and `driver.jar` with `--release 21`, `-parameters` (its `JAVAC_FLAGS`, so the classes keep the names `code` and `field` the claims use), a fixed timestamp and sorted entries, and writes `OUT/manifest.json` with their sha256s, the flags and the JDK |
| `claims/` | The tasks' claim files, added by the workflow stream: `gate-security.json` (the three security tasks), `gate-preservation.json` and `regex-probe.json`, in the keys its `plan_task` gives `TaskPlan.claim` |
| `make_records.py` | Rewrites `records/` and `results/` |
| `records/controls.json` | Recorded: each revision's driver in its own JVM, on JDK 25 and 21, with the oracle's verdict on each (`before` fails at 97, `mutant` at 65, `after` passes) |
| `records/regex-gate-gaps.json` | Recorded: `jvmcontract gaps` on `RegexGate.allowed` in `after.jar` (a static scan that proves nothing): `Pattern.compile`, `Pattern.matcher` and `Matcher.matches` |
| `records/bad-runs.json` | Constructed: a killed control, a malformed control output, a one-sided replay, and a verifier that exited 1 with no witness. None is a violation |
| `results/incomplete`, `results/bundle-mismatch` | Constructed from example 025's committed result: a format-2 receipt without its conclusion, and one whose `verifier-output.txt` is not the file its bundle lists |

`records/regex-gate-gaps.json` was recorded with the `lib/target/release/jvmcontract` built on 2026-11-08 at 19:40,
before application-core's last `lib/src` change (`yrlkzqvw`, 19:53); its sha256 is in the record. The scan's gaps are
JDK calls the checker has always refused, and a rerun of `make_records.py` with a current build records it again.
The records were remade on 2026-11-14, in Phase 5, when the recipe gained `-parameters` (VF-024): every JAR's sha256
changed, the controls' outputs didn't, and the gap scan used the same binary.

The tasks in `target.json` are the fixture's: `vulnerable-security` (expected refuted), `fixed-security` (expected
established), `preservation` outside `code == 97` (expected established), `mutant-security` (expected refuted),
`regex-probe` (expected unresolved: a capability refusal), and `replay` and `mutant-replay` (the concrete controls
on the fix's pair and on the mutation's). Each is over `int`
codes, inside the tool's own checker, except `regex-probe`.
