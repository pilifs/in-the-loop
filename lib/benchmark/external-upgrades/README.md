# External upgrade evaluation

[Maintainer findings and score status](../../../llm-dlc/loops/external-upgrade-evaluation-results.md) · [Per-case evidence](../../../verification/external-upgrade-calibrations.json) · [Preregistered protocol](protocol.md)

The current campaign uses one gpt-6.2-astra session for all roles and keeps its upgrade pairs, expected observations and first results in the repository. The six earlier Claude opening reports are superseded. [Active protocol](protocol.md#active-engineering-protocol-from-0305-utc-on-21-november)

## Run the engineering corpus

The [corpus](corpus.json) holds 32 original upgrade pairs, their source and Maven identities, selected consumer methods and observations. Twelve main cases come from CompSuite's reported changes and twelve from routine upstream upgrades. A registry entry identifies a historical expectation. Only a reproduced caller observation can establish its actual outcome. Each half of the eight transfer cases includes two represented families and two new ones.

Populate a local Git cache with the pinned objects. A JSON map from case ID to an existing Git repository can also be used. Run the comparison as a verification job. The 32 first reports use the same prepared artifacts for V0 and the repaired reader. CompSuite source builds use the Java 8 installation, current upstreams use Java 21, and the native verifier uses Java 21. The original-module preparations for two clients also carry their complete original runtime classpaths. The other preparations compile the indicated original source and its javac-discovered dependencies against the original module's Maven compile classpath, then check the caller on the separately resolved runtime classpath. Reports keep build, availability and method-level evidence distinct from a maintainer decision.

```sh
python3 lib/benchmark/external-upgrades/corpus_sources.py "$TMPDIR/upgrade-sources"
python3 lib/benchmark/external-upgrades/engineering.py --build V0 --build current \
  --repositories "$TMPDIR/upgrade-sources/repos.json" --work "$TMPDIR/upgrade-builds" \
  --maven-cache "$HOME/.cache/in-the-loop/external-upgrades/maven/repository" \
  --output "$TMPDIR/upgrade-results" --set main
```

Each report records the original commits, exact caller bytes, classpath hashes when available, concrete preparation or checker diagnostic and elapsed time. The V0 checker digest is checked before starting. In a checkout or queue archive without Git history, place V0's `examples/tools/targets/runtime_jar.py` at `$TMPDIR/upgrade-builds/v0-runtime_jar.py`. Its digest is checked before use. The CLI refuses to overwrite a first report.

The [finite caller scenarios](scenarios) take the original classpaths prepared during the corpus run and use the public `build.py --review-upgrade` route. Each scope lists ordinary inputs, independently expected old observations and the reviewed Java source that constructs the real receiver. The debugger observes the exact original method entry in every fresh JVM. These runs report engineering-assisted finite claims separately from the automatic native result.

```sh
python3 lib/benchmark/external-upgrades/check_scenarios.py --case compsuite-i-38 \
  --preparations "$TMPDIR/upgrade-builds" --maven-cache "$MAVEN_CACHE" \
  --output "$TMPDIR/reflectasm-results"
```

For clients that need generated classes or resources, run `baselines/complete_client.py` with the case, repositories, Maven cache, output and an external preparation directory. Pass that directory to `check_scenarios.py --complete`. This preserves the original module and its ordered runtime classpath. The Apollo preparation retains its real Git tags and the Togglz preparation reads the public release repository declared in its original POM.

For a client whose original test environment constructs a framework receiver, use `complete_client.py --with-test-fixtures --phase compile` and declare `"withTestFixtures": true` in the caller scope. Maven compiles the original fixtures and processes their resources. The verifier checks that the selected dependency was already on the production runtime, which takes precedence over all fixture classes and companions. Both sides record the runtime prefix and fixture JAR digest. Package directory entries let Spring discover annotated classes in the resulting JARs.

LanguageTool used the retired JCenter predictor release. Togglz's original Bundlor plugin used seven SpringSource bundles, including the Ant dependency of its Maven plugin API. Restore their exact JARs and POMs with `python3 lib/benchmark/external-upgrades/baselines/restore_archived.py --maven-cache "$MAVEN_CACHE"`. The [release manifest](baselines/archived-releases.json) records the archive and the digest of every file. The importer verifies cold downloads and existing cache entries.

For Togglz use `complete_client.py --phase compile --operand-scope provided`. This includes the DeltaSpike API supplied by the host along with the original module's runtime dependencies. LanguageTool's Wikipedia module declares Derby in test scope on both pins. Use `--phase package --operand-scope test` for its developer-test environment. Each receipt binds the scope to the original module POM and records the actual ordered JARs.

A reviewed scope can identify a synchronous framework callback with `invocationVia`. At the original method's breakpoint, the debugger reads the suspended observer's bytecode offset. It must match an instruction in `observe` that invokes the exact declared owner, name and descriptor. Each receipt records the offset and the implementation frame the JVM actually dispatched to, including Spring proxies and interface implementations. A thrown result also requires the same escaping JVM object to cross the selected call. The ordering and service-validation scopes exercise this route. A scope can set `"workingDirectory": "fixtures"` for applications that resolve their original resources relative to a module directory. Retrofit and the spreadsheet client also have `--variant operational` observations for request serialization and workbook opening.

When a scenario throws before entering its selected method, `build.py --review-upgrade` continues on both revisions and records each input in `beforeEntryComparison`. For a reproduced earlier failure, the old JVM reached the method and matched its expected result twice. Two fresh upgraded JVMs threw the same exception at the same location on the observer's thread. The debugger matches the escaping object to its live throw event, then identifies the original client or upgraded artifact on that stack. The receipt includes exact method descriptors, bytecode positions, source lines when available, and the hashes of the loaded JARs. The downstream claim stays open.

For a missing-class exception the workflow also tries the exact binary name on both original classpaths in fresh JVMs, with initialization disabled. It records every provider visible at the subject JDK's release and the symbolic references in each version of the upgraded JAR. This identifies a class that the old caller actually loaded and a newly required class that neither classpath supplies. An unrelated string literal contributes no linkage evidence.

Check the current published measurements with `python3 lib/benchmark/external-upgrades/pin.py --check lib/benchmark/external-upgrades/v2.json` and `python3 lib/benchmark/external-upgrades/current_report.py --check`. The report command checks the source commit and output hashes of all seven caller batches, the original caller bindings, both repetitions and the independent class lookups. [Current 32-case report](../../../llm-dlc/loops/external-upgrade-current-cases.md)

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

## Historical sealed scorecards (superseded on 21 November)

The curator keeps reference material outside the operator workspace. A first report is one JSON record with a neutral case ID, build and input identities, ordered old/new artifact digests, claim, observer, domain, scope, route, five-line maintainer report, review action, evidence paths and SHA-256 values. It includes intake, first actionable and completion times, the 15-minute observation, cache state, enforced resources, human minutes and measured token/compute use. Open and unavailable outcomes name their first blocker. [Curator procedure](curation/README.md) · [Scorecard implementation](scorecard.py)

```sh
python3 lib/benchmark/external-upgrades/scorecard.py seal-report operator.json "$REPORTS"
python3 lib/benchmark/external-upgrades/scorecard.py score roster.json "$REPORTS" "$GRADES" \
  --build V0 "$V0_LOCK_SHA256"
```

Sealing copies and rehashes evidence, records the seal time and preserves the first report on a retry. On the grader machine, the roster carries the original cutoff, opaque packet and reference identities, and the privately frozen strata. Its `profile_sha256` binds every report to the same approved model and scheduling configuration. The signed `products` entry for each build pins `lock_sha256`, `launch_lock_sha256`, `staged_root_sha256` and `frozen_utc`. This binds the exact checkout, executable and complete staged image for each build while allowing the held-constant environment to be compared independently. The scorer requires all 24 first reports before reading a grade. For transfer, pass both V0 and V1 with their lock digests. It requires all sixteen seals before opening either set of grades and checks the matched environments, caches and operator profiles.

Every transfer roster row records `client_in_main`. Each transfer grade's `transfer_integrity` records whether engineering saw the reference, used the client during the repair or a runner saw the other first report. The paired output retains every observation and reports held-out counts separately. A repair earns transfer credit only on an untouched client with an independent pair of runs and evidence that the case exercised the improved capability.

An unavailable or unverified runtime image still gets a sealed first report. The signed roster binds the intended build and launch, and the report records the actual image digest when it could be inspected. That case keeps its place in the primary denominator. Transfer output distinguishes all attempted pairs from pairs with verified matching conditions.

The signed JSON envelope has `payload` and `signatureHex`. Sign UTF-8 `upgrade-roster-v1` or `upgrade-adjudication-v1`, a NUL byte, then compact, sorted-key UTF-8 JSON of the payload with a final newline. The signer is the Ed25519 key in the pre-product seed commitment. Each adjudication binds a first-report hash and reference hash to two independently attributed reviews, their reasons, recommended actions and written resolution of any disagreement. The machine counts a validated transfer gain separately when the improved capability has supporting evidence.

For a claimed native result, the adjudicators bind `decisive_receipt_sha256`, `decisive_claim_id` and `decisive_status` to the archived result for the relevant caller claim. The scorer reads the actual engine, claim ID, executable digest and vacuity flag from that receipt. An unsubstantiated native label keeps the PR in the denominator and earns no native credit. Review the original model wording in `raw_maintainer_report` when the controller has qualified an unsupported assurance, and record the reporting fault separately from the delivered decision.

Each newly sealed report includes a `client-cost.json` record bound to its immutable hash. `python3 lib/benchmark/external-upgrades/scorecard.py cost SEALED_OPERATOR_JSON` also reconciles earlier reports. The native client returns a running dollar total for each role conversation. Its final reading is that session's estimate. Token usage is incremental. An unsettled request or an inconsistent native session history leaves the dollar estimate unknown. [Disclosed per-request tariff audit](adjudication/operator-cost-audit.json)

Human consent, pre-report CI and intended action, actual decisions and voluntary repeat requests are collected only in each participating team's agreed environment after the retrospective gate opens. A public calibration and a synthetic smoke test cannot establish those outcomes.

## Original CI for the two disclosed upstream PRs

`baselines/public_ci.py` runs the original Linux Maven lifecycle on both detached revisions of Commons Text 586 or Cucumber Reporting 1156. Use `--repo` to pass a local Git repository containing the pinned commits. Each side gets fresh sources, build outputs, test reports and a writable Maven client cache outside the checkout. The application runs in a networkless namespace. A loopback Maven mirror can only read release files from a shared repository or retrieve them serially from Maven Central. The shared cache uses `~/.cache/in-the-loop/external-upgrades/maven/repository` and the adjacent `resolution.lock`. All child JVMs receive a temporary directory under the case scratch area. The output records full-suite counts, the XML digest for each suite, original XML for the named suite, compressed Maven logs and cache usage. The Linux reproduction covers one configured JDK on each side. [CI runner](baselines/public_ci.py) · [Serial release mirror](baselines/maven_mirror.py)

For rxjava-jdbc, `public_ci.py 348 --out FRESH_DIRECTORY` runs the complete Maven test suite. Add `--stock-compsuite` for the original `--info` and `--incompat` commands followed by the individual `--testold` and `--testnew` commands on independent fresh worktrees. The original branch and both H2 tags must exist in the local Git repository. Under the shared `external-upgrades/ci-tools` directory put the original Apache Maven distribution in `apache-maven-3.6.3`, the unpacked Python distribution in `cpython-3.11.14` and the four unmodified CompSuite Python files and disclosed registry entry in `compsuite-6e6d738c8b0c-i87`. The runner checks their identities and retains both the wrapper messages and the actual nested Maven logs. [CompSuite source identities](../../../examples/348-rxjava-jdbc-generated-keys/records/compsuite-cli.json) · [Reference CPython distribution](../../../examples/348-rxjava-jdbc-generated-keys/records/comp-suite-python.json)
