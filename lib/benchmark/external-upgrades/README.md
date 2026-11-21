# External upgrade evaluation

[Maintainer findings and score status](../../../llm-dlc/loops/external-upgrade-evaluation-results.md) · [Per-case evidence](../../../verification/external-upgrade-calibrations.json) · [Preregistered protocol](protocol.md)

## Reproduce an open calibration

Examples 348 and 349 include a source-build reproduction in their own folders. For 350, 351 or 352, obtain the two commits and the JARs in that example's `materials.json`. Give the script the local Git repository, directory of named JARs, recorded subject JDK and an empty output location. It checks every JAR digest, the parent relationship, the POM-only tracked diff, loaded class origins and the original caller's observations. For the two named JUnit 4 tests it requires the specified class and method to appear exactly once in fresh Surefire XML.

```sh
python3 lib/benchmark/external-upgrades/replay_open.py 351 \
  --repo "$AWS_SDK_REPO" --jars "$CALIBRATION_JARS" --jdk "$JAVA8_HOME" \
  --out "$TMPDIR/aws-date-reproduction"
```

Each numbered example also has the standard public plan, JVM replay, proof task and Markdown handoff. `pinned_task.py` runs that workflow at the configured Bitwuzla and JDK versions, checks the frozen source and executable before and after, and retains the actual workflow exit. The queue runs proof tasks. A missing binary has to be supplied with `--checker` or placed in `~/.cache/in-the-loop/external-upgrades/<binary-sha256>/jvmcontract`. The lock identifies it by content. [V0 toolchain](v0.json) · [Portable source manifest](v0-files.json.gz)

### Reproduce a disclosed operator packet

`open_packets.py` takes the original Git repository and the independently replayed JARs. For Commons Text, also supply the full-source reproduction directory with its two client archives. Use a fresh output directory outside the checkout. Only its `release/pair` and `release/dependencies` directories are operator inputs. The curator plan records original blob digests and exactly which bytes were withheld.

```sh
python3 lib/benchmark/external-upgrades/open_packets.py 348 \
  --repo "$RXJAVA_REPO" --jars "$RXJAVA_JARS" --out "$TMPDIR/open-rxjava"
python3 lib/benchmark/external-upgrades/open_packets.py 349 \
  --repo "$COMMONS_TEXT_REPO" --jars "$TEXT_JARS" --text-run "$TEXT_FULL_SOURCE_RUN" \
  --out "$TMPDIR/open-commons-text"
```

| Disclosed packet | Source files and runtime archives per side | SHA-256 of pair.json | SHA-256 of dependencies/manifest.json |
|---|---|---|---|
| rxjava-jdbc | 91 files, 10 ordered JARs. The named and companion tests, one identifying comment and an ignored duplicate were removed from the two test classes. | `ab9fe13149d401a4ea11f81021aa0ebf39e99286ea34c475bf0849303f17d5e1` | `0646ba9b94b7024076e22a79f9e15d12607dd194efb8f949c861aedbf3bc40d7` |
| Commons Text | 242 files, 2 ordered JARs. Its independent oracle and mutant were created outside the upstream trees. | `6b6e62a785f4772b7fafaf48a97b13f9d6099573f2a87e8760bd3d9a83472acd` | `d40962103d922d794ab45bb333f7b420b802965d8f5446d2739744ff76e557b0` |

## Sealing and reading scores

The curator keeps reference material outside the operator workspace. A first report is one JSON record with a neutral case ID, build and input identities, ordered old/new artifact digests, claim, observer, domain, scope, route, five-line maintainer report, review action, evidence paths and SHA-256 values. It includes intake, first actionable and completion times, the 15-minute observation, cache state, enforced resources, human minutes and measured token/compute use. Open and unavailable outcomes name their first blocker. [Curator procedure](curation/README.md) · [Scorecard implementation](scorecard.py)

```sh
python3 lib/benchmark/external-upgrades/scorecard.py seal-report operator.json "$REPORTS"
python3 lib/benchmark/external-upgrades/scorecard.py score roster.json "$REPORTS" "$GRADES" \
  --build V0 "$V0_LOCK_SHA256"
```

Sealing copies and rehashes evidence, records the seal time and preserves the first report on a retry. On the grader machine, the roster carries the original cutoff, opaque packet and reference identities, and the privately frozen strata. Its `profile_sha256` binds every report to the same approved model and scheduling configuration. The signed `products` entry for each build pins `lock_sha256`, `launch_lock_sha256`, `staged_root_sha256` and `frozen_utc`. This binds the exact checkout, executable and complete staged image for each build while allowing the held-constant environment to be compared independently. The scorer requires all 24 first reports before reading a grade. For transfer, pass both V0 and V1 with their lock digests. It requires all sixteen seals before opening either set of grades and checks the matched environments, caches and operator profiles.

Every transfer roster row records `client_in_main`. Each transfer grade's `transfer_integrity` records whether engineering saw the reference, used the client during the repair or a runner saw the other first report. The paired output retains every observation and reports held-out counts separately. A repair earns transfer credit only on an untouched client with an independent pair of runs and evidence that the case exercised the improved capability.

The signed JSON envelope has `payload` and `signatureHex`. Sign UTF-8 `upgrade-roster-v1` or `upgrade-adjudication-v1`, a NUL byte, then compact, sorted-key UTF-8 JSON of the payload with a final newline. The signer is the Ed25519 key in the pre-product seed commitment. Each adjudication binds a first-report hash and reference hash to two independently attributed reviews, their reasons, recommended actions and written resolution of any disagreement. The machine counts a validated transfer gain separately when the improved capability has supporting evidence.

Human consent, pre-report CI and intended action, actual decisions and voluntary repeat requests are collected only in each participating team's agreed environment after the retrospective gate opens. A public calibration and a synthetic smoke test cannot establish those outcomes.

## Original CI for the two disclosed upstream PRs

`baselines/public_ci.py` runs the original Linux Maven lifecycle on both detached revisions of Commons Text 586 or Cucumber Reporting 1156. Use `--repo` to pass a local Git repository containing the pinned commits. Each side gets fresh sources, build outputs, test reports and a writable Maven client cache outside the checkout. The application runs in a networkless namespace. A loopback Maven mirror can only read release files from a shared repository or retrieve them serially from Maven Central. The shared cache uses `~/.cache/in-the-loop/external-upgrades/maven/repository` and the adjacent `resolution.lock`. All child JVMs receive a temporary directory under the case scratch area. The output records full-suite counts, the XML digest for each suite, original XML for the named suite, compressed Maven logs and cache usage. The Linux reproduction covers one configured JDK on each side. [CI runner](baselines/public_ci.py) · [Serial release mirror](baselines/maven_mirror.py)

For rxjava-jdbc, `public_ci.py 348 --out FRESH_DIRECTORY` runs the complete Maven test suite. Add `--stock-compsuite` for the original `--info` and `--incompat` commands followed by the individual `--testold` and `--testnew` commands on independent fresh worktrees. The original branch and both H2 tags must exist in the local Git repository. Under the shared `external-upgrades/ci-tools` directory put the original Apache Maven distribution in `apache-maven-3.6.3`, the unpacked Python distribution in `cpython-3.11.14` and the four unmodified CompSuite Python files and disclosed registry entry in `compsuite-6e6d738c8b0c-i87`. The runner checks their identities and retains both the wrapper messages and the actual nested Maven logs. [CompSuite source identities](../../../examples/348-rxjava-jdbc-generated-keys/records/compsuite-cli.json) · [Reference CPython distribution](../../../examples/348-rxjava-jdbc-generated-keys/records/comp-suite-python.json)
