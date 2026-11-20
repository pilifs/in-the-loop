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

## Sealing and reading scores

The curator keeps reference material outside the operator workspace. A first report is one JSON record with a neutral case ID, build and input identities, ordered old/new artifact digests, claim, observer, domain, scope, route, five-line maintainer report, review action, evidence paths and SHA-256 values. It includes intake, first actionable and completion times, the 15-minute observation, cache state, enforced resources, human minutes and measured token/compute use. Open and unavailable outcomes name their first blocker. [Curator procedure](curation/README.md) · [Scorecard implementation](scorecard.py)

```sh
python3 lib/benchmark/external-upgrades/scorecard.py seal-report operator.json "$REPORTS"
python3 lib/benchmark/external-upgrades/scorecard.py score roster.json "$REPORTS" "$GRADES" \
  --build V0 "$V0_LOCK_SHA256"
```

Sealing copies and rehashes evidence, records the seal time and preserves the first report on a retry. On the grader machine, the roster carries the original cutoff, opaque packet and reference identities, and the privately frozen strata. The scorer requires all 24 first reports before reading a grade. For transfer, pass both V0 and V1 with their lock digests. It requires all sixteen seals before opening either set of grades and checks the matched environments and caches.

The signed JSON envelope has `payload` and `signatureHex`. Sign UTF-8 `upgrade-roster-v1` or `upgrade-adjudication-v1`, a NUL byte, then compact, sorted-key UTF-8 JSON of the payload with a final newline. The signer is the Ed25519 key in the pre-product seed commitment. Each adjudication binds a first-report hash and reference hash to two independently attributed reviews, their reasons, recommended actions and written resolution of any disagreement. The machine counts a validated transfer gain separately when the improved capability has supporting evidence.

Human consent, pre-report CI and intended action, actual decisions and voluntary repeat requests are collected only in each participating team's agreed environment after the retrospective gate opens. A public calibration and a synthetic smoke test cannot establish those outcomes.
