# Setup for the merged Java pull requests N01–N05 brief

Mechanical setup for [`organic-java-merged-pr-links-n01-n05-brief.md`](organic-java-merged-pr-links-n01-n05-brief.md), done on
2026-11-25 by a setup session (Claude Opus 5.5), before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/merged-pr-links-n01-n05`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR` (= `$O/tmp`), `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`, the
installations earlier setups used; no JDK was added) and `$MVN` (Maven 3.10.0 from `PATH` with `-s $O/maven-settings.xml -t $O/toolchains.xml`,
local repository `$O/m2`, file-lock sync context). **The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `N01`–`N05` follow the brief's order (and the PR list [`organic-java-merged-pr-links-n01-n05.md`](organic-java-merged-pr-links-n01-n05.md)).
They are this record's labels only, not example ids.

## Starting commit

Checkout at setup: `19ba373d5ad8778b69e836afe7ed1c2167ca3c6a` (`develop@origin`, "Merge the single-agent run organic-java-merged-pr-links-m01-m10-brief into the line").

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA (depth 1) from each
project's GitHub repository, one request at a time (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`, log `$O/logs/fetch.log`: 10 of 10 fetched).
`commons-cli`, `HdrHistogram`, `threeten-extra` and `geometry-api-java` are new mirrors (under 1.3 MB each); `spring-framework.git` already
existed and gained these two pins. One worktree per revision, `$W/CASE-MIRROR-ROLE` (`$O/scripts/worktrees.sh`; `parent` = the brief's
before pin, `fix` = its after pin). Parents were read from the raw commit objects (`$O/logs/pins-parents-raw.tsv`; shallow history hides them
from `git log`).

- **Every PR is merged, and its `merge_commit_sha` (from `gh api`, `$O/upstream/prs/CASE-OWNER_REPO-N.json`) equals the brief's after revision.**
  Changed-file lists per PR: `$O/upstream/prs/CASE-files.tsv`.
- **For every case the after revision's first parent is the brief's before revision.** N02 (HdrHistogram) is a two-parent merge (second
  parent `b7622c26c63437dab6399fda38deab974d0b665c`, the PR's head); the other four are squash commits with one parent.
- The diff before→after of every case names exactly the PR's changed files (diffstats in `$O/logs/CASE-landed-diffstat.txt`).

| Case | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|
| N01 | `N01-commons-cli-parent` | `d959de8fb66f8aee8964dd3080920dfb9cdfcdc3` | `12694a5929c21763f65bbbcf50d6db51cd02b68e` | `131d59b0a6b088a177350f8fc3b9da752914f89e` | 2026-10-28 | Add DefaultParserTest.testPropertiesPreserveExistingOptionValue() |
| N01 | `N01-commons-cli-fix` | `e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516` | `65b448a9df33757efc742c96596b6cb35e455e30` | `d959de8fb66f8aee8964dd3080920dfb9cdfcdc3` | 2026-10-28 | Fix DefaultParser keeping property values across parses (#450) |
| N02 | `N02-HdrHistogram-parent` | `89b0d5981bafb6b4b4ac624473a1771405d4da20` | `4c26a577f140b290bc450246f21192b89a6d5a1d` | `ad520e5fc2a337fdafdd8e825660f1fb1efc11ec` `fb8eb6baca91138e2dce86931d0d8c51b1de76ba` | 2018-11-05 | Merge pull request #149 from nitsanw/revert-to-original-log-reader-exception-handling |
| N02 | `N02-HdrHistogram-fix` | `1b51671cf06062671af931f98a8af2a53d335a70` | `54a4d3b8e7828032ee9b5759ceee02ec8660d4fd` | `89b0d5981bafb6b4b4ac624473a1771405d4da20` `b7622c26c63437dab6399fda38deab974d0b665c` | 2018-11-05 | Merge pull request #145 from nitsanw/equals-exception-fix |
| N03 | `N03-threeten-extra-parent` | `ded297257577f8dba1aa06f4ddd879a9b2d0d486` | `38f07b81efb60734f2d853d452de03f937888295` | `862462ff0ec05d4cbb23c65dfc3b9ab5918338dc` | 2026-11-13 | Bump org.apache.maven.plugins:maven-enforcer-plugin from 3.6.3 to 3.7.0 (#453) |
| N03 | `N03-threeten-extra-fix` | `c5f44114d357c1dc25d0e6f00dec5a126cae5cc6` | `06773b9a5e99e4b62354e2fa1359e1063a52570c` | `ded297257577f8dba1aa06f4ddd879a9b2d0d486` | 2026-11-15 | Fix Julian/BritishCutover chronologies (#463) |
| N04 | `N04-geometry-api-java-parent` | `0318320724ef2b94d4d11e056cd18c04eeb23661` | `8da0eebcbdb0b3e7c1e614303a6763fda4c76bb3` | `70a3c014cfbdede16eedde2e2a9e7aaa4947f027` | 2026-08-11 | Geometry release v2.3.0 |
| N04 | `N04-geometry-api-java-fix` | `1ac0c090047076329cb8c3906286086f313ac9de` | `d3012daf6caf903b42c27c98845bc551c3963360` | `0318320724ef2b94d4d11e056cd18c04eeb23661` | 2026-09-08 | Fix an issue with polyline difference (#329) |
| N05 | `N05-spring-framework-parent` | `eb9928f993fc650ba92a833ecfd28194c28afd3e` | `371cd077bcd1845928b8d229e1b942bf3d305d88` | `5e45b9be1b742c7493e2bafbb0f1d1d0828194e3` | 2026-10-04 | Fix Kotlin example in Spring MVC test docs |
| N05 | `N05-spring-framework-fix` | `f96403da2a821f9b8281161847e32a1c4e35e470` | `adb46b9dfd8011aeb9d30c25da8c5c610733e8a0` | `eb9928f993fc650ba92a833ecfd28194c28afd3e` | 2026-10-04 | Fix cached ID reuse after commit failure in MySQLMaxValueIncrementer |

PR metadata: N01 base `master`, head `f5809722f818c38b6264afd31ad179ec0609e5df`, 2 commits, 3 files; N02 base `master`, head
`b7622c26c63437dab6399fda38deab974d0b665c`, 1 commit, 2 files; N03 base `main`, head `38575742b41469865581349d190cfef28dd5c8a4`, 3 commits, 8 files;
N04 base `master`, head `41acac3de7f1a3a6742b64a1beab14cd08da58e8`, 2 commits, 2 files; N05 base `7.0.x`, head `00e09ec2ec8d95714de8a37cf6ba88cc737a408c`, 1 commit, 2 files.

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 17.0.21, 25.0.5 (11, 21 unused) | `~/.sdkman/candidates/java/` (`$J8` `$J17` `$J25`) | earlier setups' installations; none added |
| Maven 3.10.0 | on `PATH` (sdkman) | N01–N04 |
| Gradle 9.8.0 | `$O/tools/gradle-9.8.0`, zip `$O/dl/gradle/gradle-9.8.0-bin.zip` | zip sha256 `bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c` = services.gradle.org's `.sha256` (beside the zip) |
| Docker image `mysql:9.1.0` | local Docker | `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` (image id the same digest), amd64, created 2024-10-14T22:24:51Z, pulled plainly from Docker Hub |

Spring's `gradle/wrapper/gradle-wrapper.jar` (same at both pins) has sha256 `238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5`,
equal to services.gradle.org's published `gradle-9.8.0-wrapper.jar.sha256` (`$O/dl/gradle/wrapper/`). The wrapper properties (same at both pins) name
`gradle-9.8.0-bin.zip` and set no `distributionSha256Sum`. The wrapper is not used: the unpacked distribution runs directly.

Caches and files this work owns:
- `$O/m2` (Maven local repository, 281 MB), `$O/gradle-home` (`GRADLE_USER_HOME`, 946 MB), `$O/maven-settings.xml`, `$O/toolchains.xml` (JDKs 8, 11, 17, 21, 25).
- `$O/artifacts/CASE-ROLE/`: built jars, `SHA256SUMS` (jar + every class of each changed production source file), `runtime-classpath.txt`,
  `test-classpath.txt` (Maven cases; `:`-joined, paths into `$O/m2`). N05's arrive from the job (below).
- `$O/releases/A-V/`: released artifacts from Maven Central with their `.sha1` (and `.sha256`/`.sha512` where published) checked and `.asc` beside them.
- `$O/logs/`: every build and test log (`TAG.log`) with a summary (`TAG.junit.txt`); `$O/logs/surefire/CASE-parent-landed/` keeps the surefire
  reports of the landed tests on the parent. `$O/upstream/prs/`: each PR's `gh api` record and changed files.
- Keyring `$O/gnupg` (agent stopped), keys `$O/keys/`, signature results `$O/logs/release-signatures.txt`.
- Helpers in `$O/scripts/`: `env.sh`, `pins.tsv`, `fetch.sh`, `worktrees.sh`, `mvn_case.sh` (one Maven run, 4 GB scope, log + JUnit summary),
  `keep_mvn.sh` (artifacts and classpaths), `junit_summary.py`, `gradle_case.sh` (one Gradle 9.8.0 run, see N05), `resolve-all.init.gradle`
  (adds tasks `setupResolveAll`, `setupWriteClasspath`; changes no upstream file), `cp_localize.py`, `N05_job.sh`, `central_get.sh`, `smoke/MySqlSmoke.java`.
- Build trees of N01–N04 were deleted once their digests were recorded (`git clean -fdx` in the worktrees); the offline commands below rebuild in seconds.

`mvn_case.sh DIR TAG JDK [online] ARGS...` runs `systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- $MVN [-o] ARGS`
in DIR with `JAVA_HOME=JDK`, `MAVEN_OPTS=-Xmx1g`. The commands below are its ARGS.

## Summary by case

"Landed tests" is the landed test class(es) on the fix / the parent's own copy on the parent / the fix's copy on the parent.

| Case | Built | Release side | Landed tests | Upstream run |
|---|---|---|---|---|
| N01 commons-cli #450 | Maven, JDK 17, full `package` at both pins (998 / 995 tests pass) | latest release 1.11.0 predates the fix (has the parent's 6 removed lines, 6 of the fix's 13 added); no release with the fix | `DefaultParserTest` 91/91 (2 skipped), passes within the parent's full run, **3 fail** | inline |
| N02 HdrHistogram #145 | Maven, JDK 8, full `package` at both pins (150 / 149 pass) | 2.1.10 lacks the fix; 2.1.11 has all 14 lines the fix added (not byte-equal) | `HistogramAutosizingTest` 16/16, 15/15, **1 error** (`ArrayIndexOutOfBoundsException: 54272`) | inline |
| N03 threeten-extra #463 | Maven, JDK 17, full `package` at both pins (13857 / 13787 pass) | latest release 1.11.0 predates the fix; no release with it | `TestBritishCutoverChronology`+`TestJulianChronology` 1668/1668, 1598/1598, **51 fail** (49 + 2) | inline |
| N04 geometry-api-java #329 | Maven, JDK 8, full `package` at both pins (506 / 505 pass) | 2.2.4 (last on Central) `TopologicalOperations.java` = parent byte for byte; **2.3.0 is not on Maven Central** | `TestDifference` 5/5, 4/4, **1 error** (`GeometryException: internal error`) | inline |
| N05 spring-framework #37322 | Gradle 9.8.0, JDK 25 + toolchains 17/25, dependencies resolved inline; build and tests by job | 7.0.9 lacks the line; 7.0.10 `MySQLMaxValueIncrementer.java` = fix byte for byte | by job | job `20261125-225459-setup-build-spring-jdbc-at-both-37322-re` (pending) |

## Cases

### N01 · Apache Commons CLI #450 — option defaults across parses

**Pins.** Parent `d959de8fb66f8aee8964dd3080920dfb9cdfcdc3`, fix `e04b9bc29d1a2c3c203b7cd81235fcac9c4ec516` (one parent = the brief's). Changed:
`src/main/java/org/apache/commons/cli/DefaultParser.java` (+13 −6), `src/test/java/org/apache/commons/cli/DefaultParserTest.java` (+44: new tests
`testPropertiesDoNotChangeRegisteredOption`, `testPropertiesDoNotLeakIntoNextParse`, `testPropertiesReuseOptions`), `src/changes/changes.xml`.

**Build facts.** `commons-cli:commons-cli:1.12.0-SNAPSHOT` (the same version at both pins, POMs identical), parent POM
`org.apache.commons:commons-parent:106`, `maven.compiler.source`/`target` 1.8, classes major 52. **No runtime dependencies**
(`runtime-classpath.txt` is empty: the jar alone is the runtime classpath). Tests: JUnit Jupiter 5.14.4, junit-pioneer 1.9.1, Mockito 4.11.0,
commons-io 2.22.0, commons-text 1.15.0, commons-lang3 3.20.0. Built on JDK 17 (`$J17`); the default `package` runs enforcer, apache-rat, jacoco
(prepare-agent), moditect (adds `module-info`), cyclonedx/spdx SBOMs, javadoc resources and surefire 3.6.0; all passed.

**Commands** (in `$W/N01-commons-cli-ROLE`, JDK `$J17`):
- online, first resolution (30 s): `-Dmaven.test.failure.ignore=true package`
- **offline (checked, 6 s at each pin)**: `-o -Dmaven.test.failure.ignore=true package`
- landed class only (offline, 4 s): `-o -Dtest=DefaultParserTest test`
- on a copy with other sources, add `-Drat.skip` (rat flags unknown files).

**Landed tests.** Fix: `DefaultParserTest` 91 run, 0 failures, 2 skipped (`$O/logs/N01-fix.landed.test.junit.txt`). Fix's `DefaultParserTest`
on a copy of the parent: 91 run, **3 failures**, exactly the three new tests (`$O/logs/N01-parent-landed.test.log`):
`testPropertiesDoNotChangeRegisteredOption:413 expected: <null> but was: <[fromProperties]>`;
`testPropertiesDoNotLeakIntoNextParse:428 expected: <fromArgs> but was: <fromProperties>`;
`testPropertiesReuseOptions:459 expected: <second> but was: <first>`.

**Release side.** Maven Central's latest is 1.11.0 (no 1.12.0): its `DefaultParser.java` holds all 6 lines the fix removed and 6 of the
13 it added (the rest is older code), so it is on the parent's side. Signature valid (below).

### N02 · HdrHistogram #145 — equality after growth and reset

**Pins.** Parent `89b0d5981bafb6b4b4ac624473a1771405d4da20`, fix `1b51671cf06062671af931f98a8af2a53d335a70` (merge; first parent = the brief's,
second `b7622c26c63437dab6399fda38deab974d0b665c`). Changed: `src/main/java/org/HdrHistogram/AbstractHistogram.java` (+19 −3),
`src/test/java/org/HdrHistogram/HistogramAutosizingTest.java` (+17: `testHistogramEqualsAfterResizing`).

**Build facts.** `org.hdrhistogram:HdrHistogram:2.1.11-SNAPSHOT`, packaging `bundle`, parent `org.sonatype.oss:oss-parent:7`; compiler
plugin 2.3.2 with source/target 1.6, so classes are **major 50**; built on **JDK 8** (`$J8`; JDK 12+ cannot target 1.6). JUnit 4.10, surefire 2.12.4,
no runtime dependencies. The build's replacer plugin writes `src/main/java/org/HdrHistogram/Version.java` from its template and the
dependency plugin copies the jar to `HdrHistogram.jar` in the worktree (both git-ignored; removed by `git clean -fdx`).

**Commands** (in `$W/N02-HdrHistogram-ROLE`, JDK `$J8`):
- online (17 s): `-Dmaven.test.failure.ignore=true package`
- **offline (checked, 6–7 s)**: `-o -Dmaven.test.failure.ignore=true package`
- landed class only (offline, 2 s): `-o -Dtest=HistogramAutosizingTest test`

**Landed tests.** Fix: 16 run, 0 failures. Parent's own: 15 run, 0 failures. Fix's test on a copy of the parent: 16 run, **1 error**,
`testHistogramEqualsAfterResizing`: `java.lang.ArrayIndexOutOfBoundsException: 54272` at `Histogram.getCountAtIndex(Histogram.java:52)` from
`AbstractHistogram.equals(AbstractHistogram.java:1016)` via `Assert.assertEquals` (`HistogramAutosizingTest.java:45`)
(`$O/logs/surefire/N02-parent-landed/`).

**Release side.** 2.1.10 has 4 of the fix's 14 added lines (it predates the fix); 2.1.11 has all 14 (not byte-equal to the fix's file:
other later changes). 2.1.11's signature is valid; 2.1.10's could not be checked (key not on the keyservers tried).

### N03 · ThreeTen-Extra #463 — arithmetic across the British calendar cutover

**Pins.** Parent `ded297257577f8dba1aa06f4ddd879a9b2d0d486`, fix `c5f44114d357c1dc25d0e6f00dec5a126cae5cc6` (squash, one parent). Changed main
files in `src/main/java/org/threeten/extra/chrono/`: `BritishCutoverChronology.java`, `BritishCutoverDate.java`, `JulianChronology.java`,
`JulianDate.java`, `package-info.java`; tests `TestBritishCutoverChronology.java` (+211 −31), `TestJulianChronology.java` (+143); `src/changes/changes.xml`.

**Build facts.** `org.threeten:threeten-extra:1.11.1-SNAPSHOT`, no parent POM, `maven.compiler.release` 8 (a JDK 9+ profile compiles
`module-info` separately), classes major 52; built on **JDK 17**. Runtime classpath (optional compile deps): `jspecify-1.0.1.jar`,
`joda-convert-2.2.4.jar`. Tests: JUnit 5.14.4, guava-testlib, junit-pioneer, assertj. The default `package` runs checkstyle (report only),
jacoco, javadoc, and surefire 3.5.2 in **two executions** (`default-test` and `test-without-modules`; the reports folder keeps one).

**Commands** (in `$W/N03-threeten-extra-ROLE`, JDK `$J17`):
- online (29–34 s): `-Dmaven.test.failure.ignore=true package`
- **offline**: `-o -Dmaven.test.failure.ignore=true package` (every plugin it needs was resolved by the online run; the offline form was checked
  with the `test` runs below, 5–11 s)
- landed classes only (offline): `-o -Dcheckstyle.skip -Djacoco.skip -Dtest=TestBritishCutoverChronology,TestJulianChronology test`

**Landed tests.** Fix: 1668 run (1167 British + 501 Julian), 0 failures. Parent's own: 1598, 0 failures. Fix's two classes on a copy of the
parent: 1668 run, **51 failures** (49 British, 2 Julian; `$O/logs/N03-parent-landed.test.log`, `$O/logs/surefire/N03-parent-landed/`):
`test_with_TemporalField[52–57]`, `test_until_TemporalUnit_cutoverGap`, `test_until_CLD_backwardAcrossCutover`, `test_minus_Period`,
`test_plus_Period`, `test_prolepticYear_overflow`, `test_plus_TemporalUnit[26,27]`, 15 cases of `test_with_TemporalField_dayOverflow`,
24 cases of `test_until_CLD`, `test_until_Period_plusIsInverse` (British); `test_with_TemporalField_dayOverflow`, `test_prolepticYear_specific` (Julian).

**Release side.** Latest on Central is 1.11.0 (2026-10-15), before the fix: none of the fix's added lines in `BritishCutoverChronology.java` or
`JulianChronology.java`, all the parent-only lines present. Signature valid.

### N04 · Esri Geometry API #329 — restoring a closed polyline after subtraction

**Pins.** Parent `0318320724ef2b94d4d11e056cd18c04eeb23661`, fix `1ac0c090047076329cb8c3906286086f313ac9de` (one parent). Changed:
`src/main/java/com/esri/core/geometry/TopologicalOperations.java` (+36 −42), `src/test/java/com/esri/core/geometry/TestDifference.java`
(+16: `testIssue328`, the brief's WKT, forward and backward subtractor, expected JSON for both).

**Build facts.** `com.esri.geometry:esri-geometry-api:2.3.0` (not a snapshot, the same at both pins: **neither build is a published 2.3.0**),
compiler plugin 2.3.1 with source/target 1.7, classes **major 51**; built on **JDK 8** (Travis names JDK 9–14; 8 builds it). Runtime classpath:
`jackson-core-2.9.6.jar`. Tests: JUnit 4.12 (the test classes are JUnit 3 `TestCase`s), Mockito 3.12.4, jol 0.9. Surefire has no pinned
version, so Maven 3.10.0's default (3.6.0) runs. bnd-maven-plugin 6.4.0 writes the OSGi manifest.

**Commands** (in `$W/N04-geometry-api-java-ROLE`, JDK `$J8`):
- online (9–16 s): `-Dmaven.test.failure.ignore=true package`
- **offline**: `-o -Dmaven.test.failure.ignore=true package` (checked through the offline `test` runs, 2–4 s, after the online runs resolved every plugin)
- landed class only (offline): `-o -Dtest=TestDifference test`

**Landed tests.** Fix: 5 run, 0 failures. Parent's own: 4. Fix's `TestDifference` on a copy of the parent: **1 error**, `testIssue328`:
`com.esri.core.geometry.GeometryException: internal error` at `TopologicalOperations.restorePolylineParts_(TopologicalOperations.java:778)`
← `topoOperationPolylinePolylineOrPolygon_:875` ← `difference:1333` ← `difference:1607` ← `OperatorDifferenceLocal.difference:127` ←
`TestDifference.testIssue328(TestDifference.java:520)`. Line 520 is the **forward** call (`execute(g1, g2, …)`, subtractor A–T); the test stops
there, so the backward (T–A) call was not reached on the parent. Nothing else was run.

**Release side.** Maven Central's newest is 2.2.4 (2020); its `TopologicalOperations.java` equals the parent's byte for byte. The parent
commit is titled "Geometry release v2.3.0", but no 2.3.0 is on Central (metadata `lastUpdated` 20200921204048). Signature of 2.2.4 valid.

### N05 · Spring JDBC #37322 — allocating IDs after a sequence transaction fails

**Pins.** Parent `eb9928f993fc650ba92a833ecfd28194c28afd3e`, fix `f96403da2a821f9b8281161847e32a1c4e35e470` (one parent; base branch `7.0.x`).
Changed: `spring-jdbc/src/main/java/org/springframework/jdbc/support/incrementer/MySQLMaxValueIncrementer.java` (+1),
`spring-jdbc/src/test/java/org/springframework/jdbc/support/incrementer/DataFieldMaxValueIncrementerTests.java` (+28).

**Build facts.** Version `7.0.10-SNAPSHOT` at both pins (build files identical). Gradle 9.8.0 (wrapper's; the verified distribution runs
directly). buildSrc sets the Java toolchain to **25** and `release` 17; `org.gradle.jvmargs=-Xmx2048m`, parallel on, build cache on in
`gradle.properties`. `settings.gradle` applies `io.spring.develocity.conventions` 0.0.25 (build scans; remote cache at ge.spring.io):
`gradle_case.sh` passes `--no-build-cache --no-scan -Dorg.gradle.caching=false`. Repositories: Maven Central, and for a `-SNAPSHOT` version
also `repo.spring.io/milestone` and `repo.spring.io/snapshot` (the resolution log shows no artifact taken from them). spring-jdbc's runtime
dependencies are spring-beans, spring-core, spring-tx (projects) and commons-logging/jspecify; derby, h2, hsqldb are optional. **No MySQL
driver is on any spring-jdbc classpath** (see MySQL below).

`gradle_case.sh DIR TAG RESULTDIR ARGS...` runs, in DIR, `JAVA_HOME=$J25 choom -n 500 -- $O/tools/gradle-9.8.0/bin/gradle --no-daemon
--console=plain --max-workers=4 --no-build-cache --no-scan -Dorg.gradle.caching=false -Porg.gradle.java.installations.auto-detect=false
-Porg.gradle.java.installations.auto-download=false -Porg.gradle.java.installations.paths=$J17,$J25 ARGS` with `GRADLE_USER_HOME=$O/gradle-home`.

**Commands** (in `$W/N05-spring-framework-ROLE`):
- online resolution (inline, 111 s, then 22 s): `-I $O/scripts/resolve-all.init.gradle -PsetupResolve=Classpath,kotlin,Kotlin,annotationProcessor,AnnotationProcessor`
  then `-PsetupResolve=ALL`, each with `:P:setupResolveAll` for P in spring-core, spring-beans, spring-tx, spring-context, spring-aop, spring-expression,
  spring-jdbc, spring-core-test, framework-platform (logs `$O/logs/N05-fix.resolve*.online.log`). All real classpaths resolved; only Kotlin's IDE-only
  `*DependenciesMetadata` configurations fail (they need the repackaged spring-core jars built first), which no compile or test task uses.
- offline configuration check (inline, 9 s): `--offline --dry-run :spring-jdbc:jar :spring-jdbc:test` — BUILD SUCCESSFUL.
- **offline build and tests (the job)**: `--offline :spring-jdbc:jar :spring-jdbc:test` (whole spring-jdbc test task), landed class alone:
  `--offline :spring-jdbc:test --tests org.springframework.jdbc.support.incrementer.DataFieldMaxValueIncrementerTests`
- classpaths: `--offline -I $O/scripts/resolve-all.init.gradle :spring-jdbc:setupWriteClasspath -PsetupCpConf=runtimeClasspath|testRuntimeClasspath -PsetupCpOut=FILE`

**Job** `20261125-225459-setup-build-spring-jdbc-at-both-37322-re` (`$O/scripts/N05_job.sh fix|parent|transplant|clean`): builds and tests at
both pins offline, keeps `$O/artifacts/N05-ROLE/` (spring-jdbc jar, `SHA256SUMS` with the `MySQLMaxValueIncrementer` class digest,
`runtimeClasspath.txt` and `testRuntimeClasspath.txt` with the project outputs copied under `tree/`), runs the fix's
`DataFieldMaxValueIncrementerTests` on a copy of the parent (expected to fail), and removes the build trees. Pending at the time of writing.

**Release side.** spring-jdbc 7.0.10's `MySQLMaxValueIncrementer.java` equals the fix's byte for byte; 7.0.9's lacks the added line.

**MySQL.** The PR reports MySQL 9.1.0. Pulled `mysql:9.1.0` = `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6`
and MySQL Connector/J 9.1.0 from Central (`$O/releases/mysql-connector-j-9.1.0/`, sha1 checked, good signature by Oracle Maven Release Key 3,
which has since expired), with its compile dependency `protobuf-java-4.26.1` (`$O/releases/protobuf-java-4.26.1/`, signature valid; not needed by
classic JDBC: the smoke ran without it). Smoke (once, container removed): `docker run -d --rm --name n05-setup-mysql-smoke -p 127.0.0.1:33061:3306
-e MYSQL_ROOT_PASSWORD=… -e MYSQL_DATABASE=setup mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6`; ready
(`mysqladmin --protocol=tcp ping`) after ~12 s; `$J17/bin/java -cp $O/releases/mysql-connector-j-9.1.0/mysql-connector-j-9.1.0.jar
$O/scripts/smoke/MySqlSmoke.java jdbc:mysql://127.0.0.1:33061/setup root …` printed
`driver=mysql-connector-j-9.1.0 (Revision: cf2917ea44ae2e43a4514a33771035aa99de73bf) server=9.1.0 engine=InnoDB isolation=REPEATABLE-READ autocommit=1`.
Note the image's entrypoint first runs a socket-only temporary server; wait for a TCP ping before connecting.

## Digests of the built artifacts (N01–N04)

Class digests are of the classes in these jars; jar digests are of this build. `$O/artifacts/CASE-ROLE/SHA256SUMS` holds the same.

| Case | Role | File | sha256 |
|---|---|---|---|
| N01 | parent | `commons-cli-1.12.0-SNAPSHOT.jar` | `b1789f61dd9fe52f75e531b16382c0cfb406f5ff348c8df44758cc9818fa1db3` |
| N01 | parent | `org/apache/commons/cli/DefaultParser$1.class` | `0a734b1fe84e496f8e797dc0f06ff78dee97c0acc29debfa480640a1914447c6` |
| N01 | parent | `org/apache/commons/cli/DefaultParser$Builder.class` | `4cb612c79daadba65672ef5931776d8a6b0944aefa890f2d121e782c567c5d29` |
| N01 | parent | `org/apache/commons/cli/DefaultParser$NonOptionAction.class` | `7f8b901639a75a028b1c4bb92932aeadbf9e449630dcb84168141ea8c6d4259a` |
| N01 | parent | `org/apache/commons/cli/DefaultParser.class` | `1aeda2232b90424b15b6a16da60df2133288946e64492aaaac86a05bba7b7e8d` |
| N01 | fix | `commons-cli-1.12.0-SNAPSHOT.jar` | `7c9b397e5ec0c68fefbcdb961b8f9aed586d8c58923368e147446af4c8732377` |
| N01 | fix | `org/apache/commons/cli/DefaultParser$1.class` | `0a734b1fe84e496f8e797dc0f06ff78dee97c0acc29debfa480640a1914447c6` |
| N01 | fix | `org/apache/commons/cli/DefaultParser$Builder.class` | `4cb612c79daadba65672ef5931776d8a6b0944aefa890f2d121e782c567c5d29` |
| N01 | fix | `org/apache/commons/cli/DefaultParser$NonOptionAction.class` | `7f8b901639a75a028b1c4bb92932aeadbf9e449630dcb84168141ea8c6d4259a` |
| N01 | fix | `org/apache/commons/cli/DefaultParser.class` | `68d2f176e6aa8b143bb78c580576c681c4024917079f0328e9b9482d59cfc3b8` |
| N02 | parent | `HdrHistogram-2.1.11-SNAPSHOT.jar` | `c86a8582057336385e2760439e47c7265ef8bc274792f2f2e1962f9cbd70662f` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$1.class` | `2842d2dfab11ecc5f4317541670b27548709cda62d6b16a9b818a5d1d9556374` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$AllValues.class` | `5bc8ca0c394148e73235cadaeed293d4e142f91d7597886296926fc6c6d1d237` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$LinearBucketValues.class` | `2c63f8a9bf42d901ce9b40c2faac67afb5fa9e3f1850323fed798588985fca60` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$LogarithmicBucketValues.class` | `8c420689636c84549bf4122e626d58ccf76f8e5a94d55e67000c9d33ff0aecc5` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$Percentiles.class` | `3e999676bfc482615e2f35e4998abede5b5e2d42800cf6a79c1a398b504e2b7c` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram$RecordedValues.class` | `8f9e3324a3f26d798ba859da391763bdf33f70ed0549327c806eb2dda454bee0` |
| N02 | parent | `org/HdrHistogram/AbstractHistogram.class` | `a0d4b1d3c89efabea7624c6b3aa69abdce73b3992545a8754f6cd78c3bf9ba09` |
| N02 | fix | `HdrHistogram-2.1.11-SNAPSHOT.jar` | `c1ae2d8c5dbd117f37228762f4cefda831a6047d27f38fccce95639d7c35737a` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$1.class` | `2842d2dfab11ecc5f4317541670b27548709cda62d6b16a9b818a5d1d9556374` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$AllValues.class` | `2a4497ad69838c4acf50e7124bf39f9d462852b304ba251551a4e11c41020718` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$LinearBucketValues.class` | `146e6bdc3fd942a90945fbbd2fb0f2dba044bfab1d979790dd4d09c39d14f069` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$LogarithmicBucketValues.class` | `69b2ce1ce34e39e857a1580b1dbea7dfc33f063e09c8e840ea155a7384755f6e` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$Percentiles.class` | `c56f08a638270015076624772bb7aba57c1883b8e26f4b761765ac8eede571ab` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram$RecordedValues.class` | `fb7ada8ca803e06b80a6c051079ed43679326a91cfab00b5a77e5ef400e928f9` |
| N02 | fix | `org/HdrHistogram/AbstractHistogram.class` | `823bc2f8a392a0705a5c2fdf8c96c1a1f1009d69b8d9dd2158ee00445be63ac1` |
| N03 | parent | `threeten-extra-1.11.1-SNAPSHOT.jar` | `9be421dba6b1207cb0fae72f5848eacf5bc43ae72b1badd5e54fcaf651b10164` |
| N03 | parent | `org/threeten/extra/chrono/BritishCutoverChronology$1.class` | `74bffe583d61028c86928cb2cd9d4d2b4d86009981b5c3a192b626406e0fd681` |
| N03 | parent | `org/threeten/extra/chrono/BritishCutoverChronology.class` | `404eec5d2eb1aaaf450552bdb110f54584c20e15cd2b7c3c74f202a3a203e3cb` |
| N03 | parent | `org/threeten/extra/chrono/BritishCutoverDate$1.class` | `ea45cf995cb30aeecc19d40dfebeb9bf1ab47824d27f59ae4551350d4364ef15` |
| N03 | parent | `org/threeten/extra/chrono/BritishCutoverDate.class` | `ab41eb5d264c91efe284c2f2f6aa9503ab7ad801c28be19f0cb5a1caaa8c88aa` |
| N03 | parent | `org/threeten/extra/chrono/JulianChronology$1.class` | `aef3905d2831c31b3fc595cb7589a5f5b059df063cfe0007683a60117dc2451c` |
| N03 | parent | `org/threeten/extra/chrono/JulianChronology.class` | `8e2110c7f5419e1f7b35e1852b10e303711161d160e112f90317771ad35af925` |
| N03 | parent | `org/threeten/extra/chrono/JulianDate.class` | `dfd5cec2c8e25c36406a30b1ecb5180df775d3ad1ce4f93a6be45b4ebc156fda` |
| N03 | parent | `org/threeten/extra/chrono/package-info.class` | `bb75ded6d2e84efac4877edebc7e2fc511b78c5825ef07a9cde921db59f4ffd7` |
| N03 | fix | `threeten-extra-1.11.1-SNAPSHOT.jar` | `bbcc2df5cca863f2542a9dea5d4221772e9838f3430d28d201ca2a2773f93bf2` |
| N03 | fix | `org/threeten/extra/chrono/BritishCutoverChronology$1.class` | `af2dd0ac42c274d1214057e6bfe2502d391797bbe2591a16a48c2699363e6ab2` |
| N03 | fix | `org/threeten/extra/chrono/BritishCutoverChronology.class` | `28b985008c36f99af554866d97d95cc8b82bd8a736bc5b2a5bcbe4f4b5034fe7` |
| N03 | fix | `org/threeten/extra/chrono/BritishCutoverDate$1.class` | `ea45cf995cb30aeecc19d40dfebeb9bf1ab47824d27f59ae4551350d4364ef15` |
| N03 | fix | `org/threeten/extra/chrono/BritishCutoverDate.class` | `016fcaa0dd54ab3014f6e0c72f141862521d1482b8def4537cafb56d4f7c6746` |
| N03 | fix | `org/threeten/extra/chrono/JulianChronology$1.class` | `d65b9e701c2caab23a13874133fbd9e7aafe21204bfb350475924492e568ddfc` |
| N03 | fix | `org/threeten/extra/chrono/JulianChronology.class` | `7bd9080d1d21f94969d9c972ae3b791d3faf9e3784d772de6480f28b4ce2c543` |
| N03 | fix | `org/threeten/extra/chrono/JulianDate.class` | `cf51d84a9ddb804cf541221ad5bbed65a9a91308b2c17d18ba8b4b3ffb0e443b` |
| N03 | fix | `org/threeten/extra/chrono/package-info.class` | `bb75ded6d2e84efac4877edebc7e2fc511b78c5825ef07a9cde921db59f4ffd7` |
| N04 | parent | `esri-geometry-api-2.3.0.jar` | `fc8cc29ab53c691a7188ccf142b03f83669ab0194aa2bfedb68374c02c08e774` |
| N04 | parent | `com/esri/core/geometry/TopologicalOperations$CompareCuts.class` | `e8c94123fb786f3f3f97a48421570a557888569c7cc24b2353cc122dca8764b3` |
| N04 | parent | `com/esri/core/geometry/TopologicalOperations.class` | `f3355d921f4fee7b3701c8cd9e04000daf24075f9485aeb6b0ce0b09e13bf301` |
| N04 | fix | `esri-geometry-api-2.3.0.jar` | `bf4180c492babbb86fbe28cf53a00ee1df0251c4117480885ff0a30ac2dd48fa` |
| N04 | fix | `com/esri/core/geometry/TopologicalOperations$CompareCuts.class` | `e8c94123fb786f3f3f97a48421570a557888569c7cc24b2353cc122dca8764b3` |
| N04 | fix | `com/esri/core/geometry/TopologicalOperations.class` | `437f25efdaef62604dad8570dfa7fcc257a1dcc6e31a0d32b6a0500619de5680` |

## Released artifacts and signatures

From Maven Central into `$O/releases/A-V/`; every jar and POM matched Central's `.sha1` (and `.sha256`/`.sha512` where published:
threeten-extra, spring-jdbc). Signatures checked with the keyring `$O/gnupg` (keys from keyserver.ubuntu.com, `$O/keys/`; the commons-cli
key is also in `https://downloads.apache.org/commons/KEYS`, `$O/keys/apache-commons-KEYS`). POMs carry the same results (`$O/logs/release-signatures.txt`).
None of these is named by the brief; they say which side a release is on and give the domain agent a released driver.

| Jar | sha256 | Signature |
|---|---|---|
| `commons-cli-1.11.0.jar` | `8f7f8605d68e15bf32db61ec94eac6fdafc51b1bdbe1e0e0802b57d23f387792` | VALIDSIG 2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB |
| `commons-cli-1.11.0-sources.jar` | `c65b544468eafd3e1036671fb22fd9ba4c3f67c03f76298e8aaeb6943755a70b` | VALIDSIG 2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB |
| `esri-geometry-api-2.2.4.jar` | `eb5e0c8395a9a27d5192b6c54bfbe04d8f4565de73794d997e1fc80ab493f90d` | VALIDSIG 33D48BF3F7B9D663B7B5EE3CEA7A86CC164A59B3 |
| `esri-geometry-api-2.2.4-sources.jar` | `c7a35e818a032c689cea3fa143d8eac79150fd61cb8b31732c27c13d2e711f77` | VALIDSIG 33D48BF3F7B9D663B7B5EE3CEA7A86CC164A59B3 |
| `HdrHistogram-2.1.10.jar` | `6a65119ee9372e58b490e889e9f8293802efd3bbc2549dd47b6e1259cd12402c` | not checked: key 14D155C4C1CAF659 on neither keyserver.ubuntu.com nor keys.openpgp.org |
| `HdrHistogram-2.1.10-sources.jar` | `bf9b88e6ce01536b6a53354eb32e6199fd55777bd819b9312a344117198021ee` | not checked: key 14D155C4C1CAF659 on neither keyserver.ubuntu.com nor keys.openpgp.org |
| `HdrHistogram-2.1.11.jar` | `96671e0898b35d602869efd9339b1929cdac855d2bc64922efbbcdd2209816bc` | VALIDSIG E113159331A1F87BFC2A93D0960D2E8635A91268 |
| `HdrHistogram-2.1.11-sources.jar` | `3a5b981f132ab458ce6428d7489734266802c982073ec9ea419302d33823a748` | VALIDSIG E113159331A1F87BFC2A93D0960D2E8635A91268 |
| `mysql-connector-j-9.1.0.jar` | `8776e2ebc46072c9a47ea59d98298c4273bd9f16a7b26b5dfa4744535aa26c62` | EXPKEYSIG C8D37E9675158FF5B29B6D6452FC3551DA8DC57E (good signature; key expired 2026-10-01) |
| `protobuf-java-4.26.1.jar` | `091933e5870af810748326f7ace4a673aca721253177542842f044b546f14282` | VALIDSIG 1A55F091AD28C07F831FA44D7905DE25C78AD456 |
| `spring-jdbc-7.0.10.jar` | `bc4ba6bd242f2db2642938960ae27589b53dd6a611d700a260af7b3383cd0c6c` | VALIDSIG 48B086A7D843CFA258E83286928FBF39003C0425 |
| `spring-jdbc-7.0.10-sources.jar` | `4434b234da9710ccee14aa882a27e3a3009d0c81cb0fbad22deecf60a98ab2a0` | VALIDSIG 48B086A7D843CFA258E83286928FBF39003C0425 |
| `spring-jdbc-7.0.9.jar` | `ca0d9af1c5721eef8cac1f94c8b9d27a753248bc33c86e3472bd3d1dbd78f450` | VALIDSIG 48B086A7D843CFA258E83286928FBF39003C0425 |
| `spring-jdbc-7.0.9-sources.jar` | `7dd78f9d227747a14d721cd4ab979b72e3b07e46c90c8b2383b2a3df6f8b6934` | VALIDSIG 48B086A7D843CFA258E83286928FBF39003C0425 |
| `threeten-extra-1.11.0.jar` | `af10f12e7a1afc93a1fae5c5c6977c19b13aa7df54353555ae0b9ca89fa19629` | VALIDSIG B41089A2DA79B0FA5810252872385FF0AF338D52 |
| `threeten-extra-1.11.0-sources.jar` | `cdb3d65146d65594bcf5d809706ae0c724b198300b378865efae942e67731287` | VALIDSIG B41089A2DA79B0FA5810252872385FF0AF338D52 |

## What failed or was not done

- HdrHistogram 2.1.10's signature: key `14D155C4C1CAF659` is on neither keyserver.ubuntu.com (only a revocation certificate) nor keys.openpgp.org; sha1 matched.
- Esri 2.3.0 is not on Maven Central; nothing substituted.
- No upstream build file was changed and nothing was substituted. Nothing was refused.
- Not run on purpose: the brief's scenarios and claims, the N04 backward subtractor on the parent (the brief leaves it open), anything against MySQL beyond the connection smoke.

## Setup Agent Notes

### What is ready, and where

- `source ~/.cache/in-the-loop/merged-pr-links-n01-n05/scripts/env.sh` sets `$O`, `$W`, `$MVN`, `$J8` … `$J25`, `TMPDIR`, `GRADLE_USER_HOME`.
  The default `java` on `PATH` is JDK 25: name the JDK by path.
- Worktrees at both pins of every case: `$W/N01-commons-cli-{parent,fix}`, `$W/N02-HdrHistogram-{parent,fix}`, `$W/N03-threeten-extra-{parent,fix}`,
  `$W/N04-geometry-api-java-{parent,fix}`, `$W/N05-spring-framework-{parent,fix}`; full commit ids in [Upstream revisions](#upstream-revisions).
- Built jars, digests and classpaths: `$O/artifacts/CASE-ROLE/` (`SHA256SUMS`, `runtime-classpath.txt`, `test-classpath.txt`); full digests in
  [Digests of the built artifacts](#digests-of-the-built-artifacts-n01n04). N01 and N02 have no runtime dependencies (the jar alone);
  N03 needs `jspecify-1.0.1.jar` and `joda-convert-2.2.4.jar` only as optional deps; N04 needs `jackson-core-2.9.6.jar` (paths in `runtime-classpath.txt`).
- Offline Maven commands per case (each a few seconds) in the case sections: N01 and N03 on `$J17`, N02 and N04 on `$J8` (their bytecode
  targets are 1.6 and 1.7). Everything they need is in `$O/m2`.
- N05: Gradle 9.8.0 at `$O/tools/gradle-9.8.0`, run through `$O/scripts/gradle_case.sh` (JDK 25 launcher, toolchains 17/25, no build cache, no scan);
  dependencies are in `$O/gradle-home`. Jars and classpaths arrive in `$O/artifacts/N05-{fix,parent}/` from job
  `20261125-225459-setup-build-spring-jdbc-at-both-37322-re`.
- For N05's durable claims: Docker image `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` (`mysql:9.1.0`, the version the PR
  tested), Connector/J `$O/releases/mysql-connector-j-9.1.0/mysql-connector-j-9.1.0.jar` (sha256 in [Released artifacts](#released-artifacts-and-signatures));
  a connection smoke worked (InnoDB default, REPEATABLE-READ, autocommit on). Command in the N05 section.
- Released jars with checked checksums and signatures in `$O/releases/` (commons-cli 1.11.0, HdrHistogram 2.1.10/2.1.11, threeten-extra 1.11.0,
  esri-geometry-api 2.2.4, spring-jdbc 7.0.9/7.0.10).

### What was verified on a JVM

- Each landed regression passes on the fix and fails on the parent, as the brief says:
  - N01: three new `DefaultParserTest` tests fail on the parent (`expected: <second> but was: <first>` in `testPropertiesReuseOptions`, and two more).
  - N02: `testHistogramEqualsAfterResizing` errors on the parent with `ArrayIndexOutOfBoundsException: 54272` inside `AbstractHistogram.equals`.
  - N03: 51 of the 1668 landed British/Julian tests fail on the parent (`test_prolepticYear_overflow`, `test_with_TemporalField_dayOverflow`,
    `test_until_Period_plusIsInverse`, `test_until_CLD_backwardAcrossCutover`, …).
  - N04: `testIssue328` errors on the parent with `GeometryException: internal error` in `TopologicalOperations.restorePolylineParts_`, on the
    **forward** (A–T) call; the backward call is never reached on the parent.
- Each Maven case's full upstream `package` passes at both pins (N01 998/995, N02 150/149, N03 13857/13787, N04 506/505 tests).
- N05: pending in the job above (spring-jdbc tests at both pins, and the landed `DataFieldMaxValueIncrementerTests` on the parent).

### What to know before starting

- All four Maven builds are `-SNAPSHOT` or unreleased versions of the pinned trees, not published artifacts: N04's builds say `2.3.0`, but no
  2.3.0 is on Maven Central (2.2.4 is the newest, and its `TopologicalOperations.java` = the parent's). N02's fix landed in release 2.1.11, N05's in 7.0.10
  (`MySQLMaxValueIncrementer.java` byte for byte); commons-cli and threeten-extra have no release with their fix yet.
- N02 is a merge commit: diff against its first parent `89b0d5981bafb6b4b4ac624473a1771405d4da20`.
- N03's build runs surefire twice (`default-test`, `test-without-modules`); the reports folder keeps one set.
- N05: no MySQL driver is on spring-jdbc's classpaths; Connector/J 9.1.0 is in `$O/releases/`. The MySQL image's entrypoint restarts its server
  once during init: wait for a TCP ping. Spring's build applies the Develocity conventions plugin; keep `--no-scan --no-build-cache` (as
  `gradle_case.sh` does) so nothing is uploaded or fetched from ge.spring.io. The version is `7.0.10-SNAPSHOT`, so the build also lists
  repo.spring.io's milestone and snapshot repositories; none of the resolved artifacts came from them.
- HdrHistogram 2.1.10's signature could not be checked (signing key on no keyserver tried); its sha1 matched Central.

### What is left for the domain work on purpose

- Every scenario and claim of the brief: harnesses against the built jars, the predictions (N01 failed-parse retry, N02 symmetry and the
  interior-count challenge, N03 18 March → 1 September readback, N04 reversed and extended subtractors on both revisions), and N05's JDBC test
  double or MySQL fixture (failing commit, failing `setAutoCommit(true)`, independent reader). No example folders, claims or sidecars exist.
