# Setup for the merged Java pull requests M01–M10 brief

Mechanical setup for [`organic-java-merged-pr-links-m01-m10-brief.md`](organic-java-merged-pr-links-m01-m10-brief.md), done on
2026-11-25 by a setup session (Claude Opus 5.5) and forks of it, before the domain work starts. The session writes
no claims, examples, sidecars, adapters or checker code, allocates no example ids, and runs neither the project
verifier nor JBMC. Everything fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/merged-pr-links-m01-m10`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR`, `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin, under `~/.sdkman/candidates/java/`) and `$MVN`
(Maven on `PATH` with `-s $O/maven-settings.xml -t $O/toolchains.xml`, local repository `$O/m2`).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `M01`–`M10` follow the brief's order (and the order of the PR list
[`organic-java-merged-pr-links-m01-m10.md`](organic-java-merged-pr-links-m01-m10.md)). They are this record's labels only, not example ids.

## Starting commit

Checkout at setup: `f1f3fda0094b53b24e33ab2e2c8b0c3d17b9edef` (`develop@origin`, "Merge the single-agent run organic-java-merged-pr-links-l01-l20-brief into the line").

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA
(depth 1) from each project's GitHub repository, one request at a time (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`,
log `$O/logs/fetch.log`: 20 of 20 fetched). Mirrors that already existed (`RoaringBitmap`, `jackson-databind`, `vavr`,
`commons-compress`) gained these pins beside earlier setups' ones; `commons-rng`, `agrona`, `spatial4j`, `checkstyle`, `libgdx`
and `tinkerpop` are new. One worktree per revision, `$W/CASE-MIRROR-ROLE` (`$O/scripts/worktrees.sh`; `parent` = the brief's
before pin, `fix` = its after pin). Parents were read from the commit objects (`$O/logs/pins-parents-raw.tsv`; shallow history
hides them from `git log`).

- **Every PR is merged, and its `merge_commit_sha` (from `gh api`, `$O/upstream/prs/CASE-OWNER_REPO-N.json`) equals the
  brief's after revision.** Changed-file lists per PR are in `$O/upstream/prs/CASE-files.tsv`.
- **For every case the after revision's first parent is the brief's before revision.** M06 (agrona) is a two-parent merge
  (second parent `e95962c28014c76a6f7e0a2861784bb7bf847ec7`, the PR's head); the other nine are squash or rebase commits with one parent.
- The diff before→after of every case names exactly the PR's changed files (diffstats in `$O/logs/CASE-landed-diffstat.txt`).

| Case | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|
| M01 | `M01-RoaringBitmap-parent` | `ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088` | `4881a976111b9ec8f5c1b3243a3370b4a252c61f` | `08a78d395187c25ec798cab84ed3cfbf9d6d96ba` | 2026-10-19 | Size and/andNot array results by cardinality, not backing capacity (#864) |
| M01 | `M01-RoaringBitmap-fix` | `baea79f84f78a8b697b10af5e3e0de034d6c66e8` | `fac2f31efb328c62ee6d3b9e25f854b414103077` | `ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088` | 2026-10-19 | Fix contains(long, long) for ranges ending in an absent key or at the end (#863) |
| M02 | `M02-jackson-databind-parent` | `e14262e2b96abd0a5db9dcb8d2bc18550488b105` | `a33a7a72b2ec5abe5a2ff863d0a8754df5852563` | `bdd27126eaa670dd2668f8ff7ddc1573cd9912a1` | 2026-04-14 | Add passing test to show #3169 (objectid w/ ignore props) works (#5912) |
| M02 | `M02-jackson-databind-fix` | `9a7d8eb3e6ae7adba3470ed15a4f1b2361558640` | `f1c5cd6dbab53a099efd91b7752a5866f62cbc00` | `e14262e2b96abd0a5db9dcb8d2bc18550488b105` | 2026-04-15 | Fix #5911: aliases w/ unwrapped (#5913) |
| M03 | `M03-vavr-parent` | `c6f0be585529bf16a4597b35f966439cffde894b` | `fc22de6faaf45cd2bfe92c656ab0f093dce8f5e7` | `1b22db5717662f93a1e97fb13f5cc9e59aa3753b` | 2026-05-17 | Bump com.diffplug.spotless:spotless-maven-plugin from 3.4.0 to 3.5.0 (#3269) |
| M03 | `M03-vavr-fix` | `8bd9c6b92ac07259f82ce30a09d037dfc5c78d81` | `e7b3c6a8a6452efd2e38ab6a1f18a0c2256ee5b7` | `c6f0be585529bf16a4597b35f966439cffde894b` | 2026-05-17 | fix Iterator#findLast returning None for null matches (#3272) |
| M04 | `M04-commons-compress-parent` | `755fad2347c4b9ea4b56c61209d8f1f387cd5a67` | `11a96ed0d6a8c13a03d5bec51a87a4582e05beb5` | `9c798f58077dbfb73224a78fad64e22d2fd18de8` | 2022-12-07 | Javadoc |
| M04 | `M04-commons-compress-fix` | `0bacf83eb0b3367cd5572ab27e42a444efbcd5f8` | `389beb81f6bfc53e05f7e20598b2ddbd091deb5e` | `755fad2347c4b9ea4b56c61209d8f1f387cd5a67` | 2022-12-07 | COMPRESS-621: Fix calculation the offset of the first zip central directory entry (#334) |
| M05 | `M05-commons-rng-parent` | `9f30ec9c6dede48347c8939d18b1fd560b9229b8` | `7faf31e331e7f23d7a572824703baa91a43f48f8` | `63e682be407fe22122b983a7b18338ac90b99eb8` | 2019-08-28 | Add SFC32 and SFC64 stress test results. |
| M05 | `M05-commons-rng-fix` | `592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77` | `76cd77323629cddb51719c22389d75e97d81dcdb` | `9f30ec9c6dede48347c8939d18b1fd560b9229b8` | 2019-09-02 | RNG-115: Fix JDKRandom to restore state to a new instance. |
| M06 | `M06-agrona-parent` | `45d86347910231d66e5f7270d3b03053a1f80b23` | `c46dd5b2729debe8fc981f7b3157fc7132a14914` | `59f45a37f52376be4a28f0a4b971e2452fe1d7d0` | 2020-02-05 | [Java] Configure `maven-publish` to use credentials for Maven Central |
| M06 | `M06-agrona-fix` | `13a9083e32f886c652041a536d13980a1ff982e0` | `e6aa7811837bdee7e465df85340a397c50c28672` | `45d86347910231d66e5f7270d3b03053a1f80b23` `e95962c28014c76a6f7e0a2861784bb7bf847ec7` | 2020-02-06 | Merge pull request #202 from ratcashdev/master |
| M07 | `M07-spatial4j-parent` | `9180d076b6683b54a961b373419d3e4347ac0b35` | `05f166366783af09de3acf9e6af81bb84453e47d` | `9d75547c183f14b2bf5490394d06164d1d4f823b` | 2021-12-10 | Bump jackson-databind from 2.9.10.5 to 2.9.10.8 (#211) |
| M07 | `M07-spatial4j-fix` | `81f473f4dc4ad0edc1fab12eb8908dadff69944a` | `590b49b370fa91eafd49ed9bd59cc9f0bada74be` | `9180d076b6683b54a961b373419d3e4347ac0b35` | 2021-12-17 | Fixed GeoJSON serialization of MULTIPOINT (#212) |
| M08 | `M08-checkstyle-parent` | `d3f020a5c477edbb57afc0f3fa2d1fab0849d6fb` | `065bbf59c1a7ac18492be3e70145e751f99f9568` | `1043cfd7f397272cf380c0bc596c5bb258205cd2` | 2023-12-22 | Issue #13345: Enable LambdaParameterNameCheckExamplesTest |
| M08 | `M08-checkstyle-fix` | `d150018d141294ac9bb02ae653d01072c5c4c4ae` | `5211b74892d43f2a53d2299e5b2da111f389fe61` | `d3f020a5c477edbb57afc0f3fa2d1fab0849d6fb` | 2023-12-22 | Issue #14028: HiddenField false positive on inner records |
| M09 | `M09-libgdx-parent` | `0de4d893abc4d02d8e1bf949edda4a9d5c547e18` | `35e9eac743321f530c164e10769f30e7333d57d8` | `7c9a5429a2d5344d84b4971dec33708d2b5e4576` | 2024-02-18 | Fix javadoc format (#7344) |
| M09 | `M09-libgdx-fix` | `7bed7d3666d3b343aebeb1c3f733eae63380dd10` | `b1ed724ce003ece015c82888f1fd420790b5853b` | `0de4d893abc4d02d8e1bf949edda4a9d5c547e18` | 2024-02-19 | Fix Intersector.intersectPolygons() corner case (#7278) |
| M10 | `M10-tinkerpop-parent` | `007fd228a992f1dccba22e25a88e647168e5ba4f` | `5799bdb2a1250fe24b819c521bd2f46b45438b8c` | `5b7eea59a4264f06cc05a76383db2eda480379c4` | 2025-05-05 | [TINKERPOP-3149] Prevent multiple by modulators for sack step and changed GroupCount.feature test to verify the error message received. (#3102) |
| M10 | `M10-tinkerpop-fix` | `a97db03618fa2fd7c17d24e331ff62adfe9c8df4` | `8ee419f03501a6691d640d58d741bd3ec9c5135b` | `007fd228a992f1dccba22e25a88e647168e5ba4f` | 2025-05-05 | TINKERPOP-3148 Prevent multiple by modulators from being used for the dedup step by throwing IllegalStateException if modulateBy is called more than once. (#3105) |

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` (`$J8` … `$J25`) | the installations of the earlier setups; no JDK was added |
| Maven 3.10.0 | on `PATH` | every Maven case (M02–M05, M07, M08, M10) |
| Gradle 9.6.1, 6.1.1, 8.4 | `$O/tools/gradle-VERSION` | zips checked against services.gradle.org (table below) |

Caches and files this work owns:
- `$O/m2`, the Maven local repository named by `$O/maven-settings.xml`; `$O/toolchains.xml` names JDKs 8, 11, 17, 21 and 25.
  `$MVN` uses a file-lock sync context, so several builds may share `$O/m2`.
- `$O/gradle-home`, the shared `GRADLE_USER_HOME`; `$O/mavenlocal-empty`, an empty folder M09's build reads in place of `mavenLocal()`.
- `$O/releases/NAME/`: release graphs resolved from Maven Central with strict checksums (`lib/`, `sources/`, `tree.txt`, an ordered `classpath.txt`).
- `$O/artifacts/`: built jars, class digests and classpath files. `$O/logs/`: build and test logs. `$O/notes/CASE.md`: each case's section as written.
- `$O/upstream/prs/`: each PR's `gh api` record and changed-file list.
- Keyrings `$O/gnupg-A`, `-B`, `-C` (one per fork of this session; every agent stopped); keys in `$O/keys-A/` … `$O/keys-C/`.
- Helpers by fork, all in `$O/scripts/`: A `mvn_A.sh`, `cp_digests_A.sh`, `relcmp_A.py`, `M02_snapshots.sh`, `pins-M02-snapshots.tsv`;
  B `mvn_B.sh`, `M08_job.sh`, `M10_job.sh`, `M10_cp.py`, `submit_B.py`, `M08-cli-check/`; C (listed under the Gradle table).

#### Gradle distributions and wrapper checks (fork C)

Zips in `$O/dl/gradle/` with services.gradle.org's `.sha256` beside them, unpacked in `$O/tools/gradle-VERSION`. The distributions run
directly (`$O/tools/gradle-VERSION/bin/gradle`), never through the repositories' `gradlew`. `GRADLE_USER_HOME` is `$O/gradle-home` for all three cases.

| Gradle | Cases | zip sha256 (= services.gradle.org's `.sha256`) | Note |
|---|---|---|---|
| 9.6.1 | M01 | `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` | copied from the earlier setup's `~/.cache/in-the-loop/merged-pr-links/dl/gradle/gradle-9.6.1-bin.zip`, re-checked |
| 6.1.1 | M06 | `9d94e6e4a28ad328072ef6e56bce79a810494ae756751fdcedffdeaf27c093b1` | the `-bin` zip; the wrapper names `-all` (same Gradle plus docs and sources), whose published sha256 is in `$O/dl/gradle/gradle-6.1.1-all.zip.sha256` |
| 8.4 | M09 | `3e1af3ae886920c3ac87f7a91f816c0c7c436f276a6eefdb3da152100fef72ae` |  |

None of the three wrappers sets `distributionSha256Sum`.

Wrapper jars in the repositories (not used), against services.gradle.org's published wrapper-jar checksums (`$O/dl/gradle/wrapper/`):

| Case | `gradle-wrapper.jar` sha256 (both pins) | equals the published wrapper jar of |
|---|---|---|
| M01 | `7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172` | 8.14.3 (`gradle-8.14.3-wrapper.jar.sha256`), not 9.6.1's (`497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`): the jar was not regenerated when the properties moved to 9.6.1 |
| M06 | `96f793a18e056c23ffeec67c1f3bb8eccff5a4a407fc9ceac183527e7eedf4b6` | 6.1.1 (`gradle-6.1.1-wrapper.jar.sha256`) |
| M09 | `0336f591bc0ec9aa0c9988929b93ecc916b3c1d52aed202c7381db144aa0ef15` | 8.4 (`gradle-8.4-wrapper.jar.sha256`) |

JDKs: the sdkman Temurin 17.0.21 (M01, M09) and 8u512 (M06); none added. Fork C's helpers in `$O/scripts/`: `gradle_case_C.sh` (one Gradle
run with log and JUnit summary), `nofailfast_C.init.gradle` (M01), `resolve-all.init.gradle` (tasks `setupResolveAll`, `setupWriteClasspath`;
adds tasks only), `classdiff_C.py`, `srccmp_C.py`, `junit_failures_C.py`, `resolve_C.sh` (release graphs, strict checksums), `sigs_C.sh` +
`sigs_C.list`. Keyring `$O/gnupg-C` (agent stopped), keys `$O/keys-C/`, signatures `$O/dl/sigs-C/`, Central metadata read `$O/dl/meta-C/`.
An empty `$O/mavenlocal-empty` stands in for `mavenLocal()` in M09's build.

## Summary by case

"Release side" says which side of the PR a published release's changed source equals. "Landed tests" is fix's tests on the fix /
parent's own on the parent / fix's tests on the parent.

| Case | Built | Release side | Landed tests | Upstream run |
|---|---|---|---|---|
| M01 RoaringBitmap #863 | Gradle 9.6.1, JDK 17, `:roaringbitmap` at both pins | 1.6.24 = parent's `contains` lines; 1.6.25 has the fix's lines + later changes | 273/273, 267/267, 6 fail (three `testContainsRange_*` in each of heap and buffer) | inline |
| M02 jackson-databind #5913 | source build, JDK 17; four vanished snapshot inputs rebuilt from their own pins | 3.0.4, 3.1.1, 3.1.2 lack the fix (3.1.2's `BeanPropertyMap.java` = parent); 3.2.0 first with it | 5/5, (no such class at the parent), 4 fail (`expected: <Hello> but was: <null>`) | inline |
| M03 vavr #3272 | source build of `vavr` module, JDK 21 | 1.0.1 = parent logic, 1.1.0 = fix logic (neither byte-equal) | 576/576 (9 skipped), 573/573 (9 skipped), 2 fail (`expected: Some(null) but was: None`) | inline |
| M04 commons-compress #334 | source build, JDK 11 | 1.22 close to parent, no accessors; 1.23.0 has them, heavily reworked | 45/45, 44/44, landed test does not compile (fix-only accessors); copy without the 4 accessor lines: 1 error (NPE, `getEntry` null) on the parent, passes on the fix | inline |
| M05 commons-rng #65 | source build `-pl commons-rng-core -am`, JDK 8 | 1.2 = parent's `JDKRandom.java` byte for byte; 1.3 = fix logic | 2/2, 1/1, 1 error (`testRestoreToNewInstance`: `IllegalStateException: java.io.EOFException`) | inline |
| M06 agrona #202 | Gradle 6.1.1, JDK 8, `:agrona` at both pins | 1.3.0 = parent (all four files byte for byte); 1.4.0 equals neither | 108/108, 96/96, 12 fail (all three new tests in each of four classes) | inline |
| M07 spatial4j #212 | source build, JDK 11 | 0.8 (last release) = parent's serializer; no release has the fix | no landed test; existing GeoJSON/Jackson tests 90/90 at both pins; issue #210's `Main`: parent throws `JsonGenerationException: Current context not Array but Object`, fix prints the MultiPoint list | inline |
| M08 checkstyle #14128 | upstream Maven build, JDK 17 (job) | 10.12.4 (named) and 10.12.6 = parent's `HiddenFieldCheck.java`; 10.12.7 = fix's | see [Jobs](#jobs) | job `20261125-202838-setup-build-checkstyle-at-both-14128-rev` |
| M09 libgdx #7278 | Gradle 8.4, JDK 17, `:gdx` only | 1.11.0 = parent's method; 1.12.1 = parent's file; 1.13.0 = fix's file (byte for byte) | 6/6, 5/5, 1 fails (`IllegalArgumentException: polygons must contain at least 3 points.`) | inline |
| M10 tinkerpop #3105 | upstream Maven build `-pl gremlin-core,tinkergraph-gremlin -am`, JDK 11 (job) | 3.7.3, 3.7.4 lack the check; 3.8.0 has it (+ a later change) | see [Jobs](#jobs) | job `20261125-202839-setup-build-tinkerpop-gremlin-core-and-t` |

## Cases

### M01 · RoaringBitmap #863 — containment across a missing block and the unsigned upper bound (upstream Gradle 9.6.1 build of `:roaringbitmap` at both pins, inline)

**Pins.** Parent `ffa685e6dbfb002c484f2bb5e0f3c5d6f5120088`, fix `baea79f84f78a8b697b10af5e3e0de034d6c66e8` (squash, one parent = the brief's). Worktrees `$W/M01-RoaringBitmap-parent`, `$W/M01-RoaringBitmap-fix`.
Changed production files: `roaringbitmap/src/main/java/org/roaringbitmap/RoaringBitmap.java` and
`roaringbitmap/src/main/java/org/roaringbitmap/buffer/ImmutableRoaringBitmap.java` (`contains(long, long)`). Changed tests:
`TestRoaringBitmap.java` and `buffer/TestImmutableRoaringBitmap.java`, three new tests each: `testContainsRange_LastKeyAbsent`,
`testContainsRange_EndOfUniverse`, `testContainsRange_AgreesWithRangeCardinality`.

**Build facts.** Gradle (Kotlin DSL), wrapper Gradle **9.6.1** (run from `$O/tools/gradle-9.6.1`, see [Gradle toolchain](#gradle-distributions-and-wrapper-checks-fork-c)),
on **JDK 17.0.21** (`$J17`). Project version `1.6.24` (from `gradle.properties`, not a `-SNAPSHOT`, the same at both pins: **it is not the
released 1.6.24**, see Release side). The root build sets `options.release = 8`; the module uses the `org.javamodularity.moduleplugin`
(1.8.12) for `module-info` (Java 9) and a `java11` source set packed under `META-INF/versions/11` (multi-release jar). Classes are Java 8
bytecode (major 52). The test JVM is the build's own (`testOnJava` defaults to 11, the current JDK wins when newer), heap 2G (the build's
`minHeapSize`/`maxHeapSize`). **The build sets `failFast = true` on `test`**: `$O/scripts/nofailfast_C.init.gradle` turns it off (after
evaluation) so a run reports every failure; nothing else is changed. The module has **no runtime dependencies** (test: JUnit Jupiter 5.12.2,
platform launcher 1.12.2, Guava 20.0, commons-lang3 3.4, kryo 5.0.0-RC6, jackson-databind 2.10.3, assertj 3.23.1, jol 0.16). Build files are the
same at both pins. Spotless (`ratchetFrom("origin/master")`) is not run by these tasks.

**Commands** (via `$O/scripts/gradle_case_C.sh WT 9.6.1 $J17 TAG roaringbitmap/build/test-results/test ARGS...`, which runs
`JAVA_HOME=$J17 choom -n 500 -- $O/tools/gradle-9.6.1/bin/gradle --no-daemon --console=plain --max-workers=2 -Dorg.gradle.jvmargs=-Xmx1536m
-Porg.gradle.java.installations.auto-download=false ARGS` in `$W/WT` with `GRADLE_USER_HOME=$O/gradle-home`, logs `$O/logs/TAG.log`, summary `TAG.junit.txt`):
- online (first resolution, 58 s): `-I $O/scripts/nofailfast_C.init.gradle -I $O/scripts/resolve-all.init.gradle :roaringbitmap:setupResolveAll :roaringbitmap:jar :roaringbitmap:test --tests org.roaringbitmap.TestRoaringBitmap --tests org.roaringbitmap.buffer.TestImmutableRoaringBitmap`
- **offline (checked, 14–27 s at both pins)**: `--offline -I $O/scripts/nofailfast_C.init.gradle :roaringbitmap:jar :roaringbitmap:test --tests org.roaringbitmap.TestRoaringBitmap --tests org.roaringbitmap.buffer.TestImmutableRoaringBitmap`
- classpath files: `--offline -I $O/scripts/resolve-all.init.gradle :roaringbitmap:setupWriteClasspath -PsetupCpOut=FILE [-PsetupCpConf=testRuntimeClasspath]`

**Artifacts** (`$O/artifacts/`; the jars' entries carry the fixed 1980-02-01 timestamp):

| File | sha256 |
|---|---|
| `M01-RoaringBitmap-parent.jar` | `4706c38b152f1dd7727c02c78af950f2d23849bcd5bbd536ffee9e82c0c8c1df` |
| `M01-RoaringBitmap-fix.jar` | `17a1401ae403bd2ef6d7e970107c3441688fcdf57ae7ae09f5f7f3ef8bf7f2b2` |
| `org/roaringbitmap/RoaringBitmap.class` (parent) | `2be1e1ebd39db019c71f00cc50f8749d6ee3897e290831c831faae1f30fab20d` |
| `org/roaringbitmap/RoaringBitmap.class` (fix) | `0f197f04f44ed4d3f8a99eb001d688313cb7d2984046d33dab94e1727ccc91ea` |
| `org/roaringbitmap/buffer/ImmutableRoaringBitmap.class` (parent) | `2df9e3a20aaf8a6b3921160ce3edc32f431762c9b313934b5286d9bcaadd0764` |
| `org/roaringbitmap/buffer/ImmutableRoaringBitmap.class` (fix) | `58a998094e164d2c84eaaab0688fb0d615d6d05f482624abba44024a34aca472` |

Every class that differs between the two jars, with both digests: `$O/artifacts/M01-RoaringBitmap.classdiff.txt` (the two above plus
`RoaringBitmap$1`, `RoaringBitmap$2`, `ImmutableRoaringBitmap$2`). Runtime classpath: empty at both pins
(`$O/artifacts/M01-RoaringBitmap-ROLE.runtime-classpath.txt`); test classpath `$O/artifacts/M01-RoaringBitmap-fix.test-classpath.txt` (same at both pins).
Use: `$J17/bin/java -cp $O/artifacts/M01-RoaringBitmap-ROLE.jar:CLASSES ...` (no other jar is needed).

**Landed tests** (`TestRoaringBitmap` and `TestImmutableRoaringBitmap`, upstream Gradle build, JDK 17; logs `$O/logs/M01-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own tests (online, then offline) | tests=273 failures=0 errors=0 skipped=0; offline tests=273 failures=0 errors=0 skipped=0 |
| parent, its own tests (offline) | tests=267 failures=0 errors=0 skipped=0 |
| fix's two test files on the parent (offline) | tests=273 failures=6 errors=0 skipped=0: in **each** class `testContainsRange_LastKeyAbsent` (`expected: <false> but was: <true>`; TestRoaringBitmap.java:5494, TestImmutableRoaringBitmap.java:1778), `testContainsRange_EndOfUniverse` (`expected: <false> but was: <true>`; :5504, :1794), `testContainsRange_AgreesWithRangeCardinality` (`contains(0, 65537) on 65536 values ==> expected: <false> but was: <true>`; :5554, :1849) — `$O/logs/M01-transplant-failures.txt` |

The first transplant attempt ran with the build's `failFast` still on (the first version of the init script did not take effect) and stopped
after three failures; the run above is the rerun with failFast off, whose log replaced it.

**Release side.** Resolved with strict checksums into `$O/releases/roaringbitmap-1.6.24/` and `$O/releases/roaringbitmap-1.6.25/`
(`lib/`, `sources/`, `tree.txt`, `classpath.txt`; no dependencies). **1.6.24** (on Central 2026-10-05, before the parent) has the
**parent's** `contains(long, long)` lines in `RoaringBitmap.java` (the files are not byte-equal to the parent: 9 and 6 lines differ).
**1.6.25** (on Central 2026-10-19 22:11 UTC) has **every line the fix adds to `RoaringBitmap.java`** and none it removes, plus later
changes (38 lines differ from the fix). Neither release's two files equal either pin byte for byte (`$O/logs/M01-release-srccmp.txt`).

| Jar | sha256 |
|---|---|
| `RoaringBitmap-1.6.24.jar` | `940ab05878dc0b874fd375a34b625256ec9b339d6fd30a0100d37965dcfbc118` |
| `RoaringBitmap-1.6.25.jar` | `e463f85d9a7f5f1d67ece01e5964c78854aae25438b7c3f16af0e420ad26108f` |

**Signatures** (keyring `$O/gnupg-C`, `.asc` from Central in `$O/dl/sigs-C/`; key from keyserver.ubuntu.com, `$O/keys-C/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `RoaringBitmap-1.6.24.jar`, `-sources.jar` | `015479E1055341431B4545AB72475FD306B9CAB7` (Daniel Lemire) | GOODSIG |
| `RoaringBitmap-1.6.25.jar`, `-sources.jar` | `015479E1055341431B4545AB72475FD306B9CAB7` (Daniel Lemire) | GOODSIG |

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds and carry no dependency. Both say version 1.6.24 in their build, but the **release** 1.6.24 is older
  code (parent side); 1.6.25 is the first release with the fix's logic, among later changes.
- The landed tests check `contains(long, long)` against `rangeCardinality` on heap and buffer bitmaps; no serialized snapshot history and
  no `MutableRoaringBitmap` mutation sequence was run.

### M02 · jackson-databind #5913 — alias routed into an unwrapped child (pinned source build; vanished 3.2.0-SNAPSHOT inputs rebuilt from their own pins)

**Pins.** Parent `e14262e2b96abd0a5db9dcb8d2bc18550488b105`, fix `9a7d8eb3e6ae7adba3470ed15a4f1b2361558640` (squash of the PR's two commits, one parent = the brief's; PR base branch `3.x`). Worktrees `$W/M02-jackson-databind-parent`, `$W/M02-jackson-databind-fix`.
Changed production files: `src/main/java/tools/jackson/databind/deser/bean/BeanDeserializerBase.java` (the unwrapped child's name set now also takes `_beanProperties.collectAliasNames(names)`) and `src/main/java/tools/jackson/databind/deser/bean/BeanPropertyMap.java` (new public `collectAliasNames(Set<String>)`, `@since 3.2`). Added test: `src/test/java/tools/jackson/databind/struct/UnwrappedWithAlias5911Test.java` (5 tests). `release-notes/CREDITS` and `VERSION` also change.

**Build facts.** Maven, single module, version **3.2.0-SNAPSHOT**, `javac.src.version` 17, `module-info.java` in the sources; `pom.xml` identical at both pins. Built with Maven 3.10.0 on **JDK 17.0.21** (`$J17`). Runtime dependencies: `com.fasterxml.jackson.core:jackson-annotations:2.22-SNAPSHOT` and `tools.jackson.core:jackson-core:3.2.0-SNAPSHOT`; the parent POM is `tools.jackson:jackson-base:3.2.0-SNAPSHOT` (test: JUnit Jupiter 6.0.3, AssertJ 3.27.7, Mockito 5.21.0, guava-testlib 32.0.1-jre, JUnit 4.13.2).

**Substitution: the snapshot inputs are gone and were rebuilt.** None of `jackson-base`/`jackson-bom` 3.2.0-SNAPSHOT, `jackson-core` 3.2.0-SNAPSHOT, `jackson-annotations` 2.22-SNAPSHOT or `jackson-parent` 2.22-SNAPSHOT is still served: the Central Portal snapshot repository (`https://central.sonatype.com/repository/maven-snapshots`, the one the POM names) now lists only 3.1.8+ / 3.2.4+ / 3.3.x / 3.4.0 and 2.18.x / 2.23+ snapshots, and the first build failed with `Non-resolvable parent POM ... tools.jackson:jackson-base:pom:3.2.0-SNAPSHOT (absent)` (`$O/logs/M02-fix-online.log` was overwritten by the later successful run; the error is the one above). The released 3.2.0 (Central, 2026-06-08) and 2.22 (2026-05-31) came after both pins, so they are not the inputs either. Each of the four was therefore built from its own upstream at the last first-parent commit of its branch before the **parent** pin's commit time (2026-04-14T14:56:38-07:00); on every one of the four branches the next commit is after the **fix** pin's time (2026-04-15T11:16:33-07:00), so the same inputs serve both sides (`$O/scripts/pins-M02-snapshots.tsv`, `$O/logs/M02-snapshot-pins.txt`; worktrees `$W/M02-snap-NAME`, mirrors `$M/jackson-{parent,annotations,bom,core}.git`, refs `refs/pins/M02-snap-SHA`):

| Input | Branch | Commit | Date | Next commit on the branch |
|---|---|---|---|---|
| `com.fasterxml.jackson:jackson-parent:2.22-SNAPSHOT` | `2.22` | `b45d09c5e6c0bf29c8eac30a68ce397cc9a4d75f` | 2026-03-27 | `34bac3e35df60f4539f43fa1b46e21ba78f3a5bf` (2026-05-30) |
| `com.fasterxml.jackson.core:jackson-annotations:2.22-SNAPSHOT` | `2.22` | `bdf79ad667eef570978a75a7ca405fc203147a83` | 2026-04-06 | `85366adedaa535cfdc5cb40234fb3431be10874e` (2026-04-21) |
| `tools.jackson:jackson-bom` + `jackson-base:3.2.0-SNAPSHOT` | `3.2` | `0112ce586dd7be96d7d46b08a3540f9c51df3076` | 2026-04-13 | `127e43e5facaae43f89fed5c715f9ed8edd84ebf` (2026-05-01) |
| `tools.jackson.core:jackson-core:3.2.0-SNAPSHOT` | `3.2` | `ab0f53b5f7590c21d6ee55fe23ffb47da0f0a8b4` | 2026-04-11 | `01334d3a724ccb2265640b37062ca74bb9c4a483` (2026-04-20) |

(The `2.22` and `3.2` branches are today's names of what was `2.x` and `3.x` in April; their history up to the cut is the same commits.)
They are installed into `$O/m2` under their own coordinates by `$O/scripts/M02_snapshots.sh` (JDK 17, `install -DskipTests`, moditect left on so the jars carry `module-info.class`; online 49 s, **offline checked**, 16 s). The upstream build files are unchanged. Digests (copies in `$O/artifacts/M02-snapshots/`; locally built, so jar bytes carry build times):

| File | sha256 |
|---|---|
| `jackson-annotations-2.22-SNAPSHOT.jar` | `40c601d55876895f4bd47139af0dd080b83cfe3c855f263b0d29f556d80324b0` |
| `jackson-core-3.2.0-SNAPSHOT.jar` | `5e8529ef17c5e59d6f05654c12d23e663dee0f26167c1259f2cab47cfd8368e1` |
| `jackson-base-3.2.0-SNAPSHOT.pom` | `f1b09e335713ebba884e0d48b478ba0bbd3ab5510e764a3b474ce54e58aaf09a` |
| `jackson-bom-3.2.0-SNAPSHOT.pom` | `0db04f2d0e98b54f538559354c28288b9fe8cf55ed0275c435f7a356ea16af26` |
| `jackson-parent-2.22-SNAPSHOT.pom` | `78bd9451023987cbf705e501fb8d1abe91c1f2dbe045ad0b5a2c368b400ba40b` |

The databind POM's `jackson-core` `tests` test-jar dependency is commented out at both pins, so no test jar is needed.

**Commands** (from `$W/M02-jackson-databind-ROLE`; wrapped as `$O/scripts/mvn_A.sh M02-jackson-databind-ROLE . TAG $J17 TESTS [online]`, whose `$SK` lint/report skips are those of the previous setup's `mvn_A.sh`). First `bash $O/scripts/M02_snapshots.sh` (offline; `online` the first time) if `$O/m2` lacks the snapshot inputs.
- online (first resolution, 17 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=UnwrappedWithAlias5911Test -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 14–17 s on both pins)**: the same with `-o` in place of the thread setting.
- classpaths: `$O/scripts/cp_digests_A.sh M02-jackson-databind ROLE . $J17 CLASS...` (offline, checked).

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests):

| File | sha256 |
|---|---|
| `M02-jackson-databind-parent.jar` | `f573bf21859bd2a508386e23d7615089f593056a8859e1973aee33360229118f` |
| `M02-jackson-databind-fix.jar` | `d764607eddf779495be66ce5cca7964b93d093ced3424a39a7026461279dcb2f` |
| `tools/jackson/databind/deser/bean/BeanDeserializerBase.class` (parent) | `c82be33d8432e14ac9fcd7351489bcc177081a4eb78b8b8b8a8b7756f4d82318` |
| `tools/jackson/databind/deser/bean/BeanDeserializerBase.class` (fix) | `3c894f3e79ef26b50ed5da14d143455a802d002a82ebd483098de8982d6776c0` |
| `tools/jackson/databind/deser/bean/BeanPropertyMap.class` (parent) | `81f48f5810ed1e3603bee08a4f2924c094eb3b30e67ff8ba3b5ab354897f3194` |
| `tools/jackson/databind/deser/bean/BeanPropertyMap.class` (fix) | `1fee4816ca2fd72f1af1721cf8686293550ebb98b3f2baebc0c9afabefb67c24` |

Runtime classpath (the same file at both pins, sha256 `e68924abacd3c6f65b53d49b6e6b9ddcd8b35a736de615b8bc77353ea674d861`): `$O/artifacts/M02-jackson-databind-fix.runtime-classpath.txt` = the two rebuilt snapshot jars above; test classpath `$O/artifacts/M02-jackson-databind-ROLE.test-classpath.txt`.
Use: `$J17/bin/java -cp $O/artifacts/M02-jackson-databind-ROLE.jar:$(cat $O/artifacts/M02-jackson-databind-fix.runtime-classpath.txt) ...` (records in the fixture need JDK 17+).

**Landed tests** (`UnwrappedWithAlias5911Test`, upstream Maven build, JDK 17; logs `$O/logs/M02-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=5 failures=0 errors=0 skipped=0 both times |
| parent (no such test class at the parent; build only) | builds, tests=0 |
| fix's test file on the parent (offline) | tests=5 failures=4 errors=0 skipped=0: `testRecordAlias` (`:33 expected: <Hello> but was: <null>`), `testPojoAlias` (`:41 expected: <Hello> but was: <null>`), `testPojoSecondAlias` (`:49 expected: <Hi> but was: <null>`), `testCreatorPojoAlias` (`:70 expected: <Hello> but was: <null>`); `testPojoPrimaryName` passes |

So at the parent the alias input is accepted without an exception and the unwrapped child's value stays `null` in the landed tests.

**Release side** (resolved with strict checksums: `$O/releases/jackson-databind-VERSION/` with `classpath.txt`, `lib/`, `sources/`, `tree.txt`; compared by `$O/scripts/relcmp_A.py`):

| Release | Runtime graph | `BeanDeserializerBase.java` | `BeanPropertyMap.java` | `collectAliasNames` |
|---|---|---|---|---|
| 3.0.4 | jackson-core 3.0.4, jackson-annotations 2.20 | neither pin | neither pin | absent |
| 3.1.1 | jackson-core 3.1.1, jackson-annotations 2.21 | neither pin | neither pin | absent |
| 3.1.2 | jackson-core 3.1.2, jackson-annotations 2.21 | neither pin | **= parent** byte for byte | absent |
| 3.2.0 (2026-06-08, not named by the brief) | jackson-core 3.2.0, jackson-annotations 2.22 | neither pin | neither pin | present in both files |

No release equals either pin in both changed files; 3.0.4, 3.1.1 and 3.1.2 (the issue's versions) lack the fix, 3.2.0 is the first with it, plus seven weeks of later changes.

**Signatures** (keyring `$O/gnupg-A`, `.asc` from Central; key from keyserver.ubuntu.com, `$O/keys-A/`, nothing further vouching for it; `$O/logs/M02-sigs.txt`): `jackson-databind` 3.0.4, 3.1.1, 3.1.2, 3.2.0, `jackson-core` 3.0.4, 3.1.1, 3.1.2, 3.2.0 and `jackson-annotations` 2.20, 2.21, 2.22 are all GOODSIG by `28118C070CB22A0175A2E8D43D12CA2AC19F3181` (Tatu Saloranta (cowtowncoder)). The rebuilt snapshot inputs are not signed; they rest on the git commits fetched by SHA.

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The pins' own databind builds run against the four rebuilt snapshot inputs above, not anything published. If an observation could depend on jackson-core or jackson-annotations behaviour, note that they are April 2026 source builds of their branches.
- The landed transplant shows the parent's failure mode for the landed fixtures (child value `null`, no exception); the brief's own record `Outer`/`Inner` and the write/read round trip were not run.
- Released 3.1.2 has the parent's `BeanPropertyMap.java` but a different `BeanDeserializerBase.java`; it is not a stand-in for either pin.

### M03 · vavr #3272 — findLast keeps a matched null (pinned source build of the `vavr` module)

**Pins.** Parent `c6f0be585529bf16a4597b35f966439cffde894b`, fix `8bd9c6b92ac07259f82ce30a09d037dfc5c78d81` (squash, one parent = the brief's; PR base `main`). Worktrees `$W/M03-vavr-parent`, `$W/M03-vavr-fix`.
Changed production file: `vavr/src/main/java/io/vavr/collection/Iterator.java` (`findLast` keeps a `found` flag and returns `found ? Option.some(last) : Option.none()` instead of `Option.of(last)`). Changed test: `vavr/src/test/java/io/vavr/collection/IteratorTest.java` (new `shouldFindLastNullElement`, `shouldFindLastNullWhenLastElementIsNull`, `shouldReturnNoneWhenFindLastFindsNothing`).

**Build facts.** Maven, module `vavr` of the root reactor, version **2.0.0-SNAPSHOT**, `java.version` 21 (`release` 21; classes are major 65); both POMs identical at both pins. Built with Maven 3.10.0 on **JDK 21.0.13** (`$J21`). The build first regenerates `vavr/src-gen` with a Scala script (`scala-maven-plugin` 4.9.10, `scala:script`); it works offline. Runtime dependencies: `io.vavr:vavr-match:1.0.0`, `io.vavr:vavr-match-processor:1.0.0`, `org.jspecify:jspecify:1.0.0`. No SNAPSHOT dependency.

**Commands** (from `$W/M03-vavr-ROLE/vavr`; wrapped as `$O/scripts/mvn_A.sh M03-vavr-ROLE vavr TAG $J21 IteratorTest [online]`):
- online (first resolution, 40 s): `JAVA_HOME=$J21 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=IteratorTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 21–23 s on both pins)**: the same with `-o` in place of the thread setting.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests; all `Iterator*` class digests in `$O/artifacts/M03-vavr-ROLE.class-digests.txt`):

| File | sha256 |
|---|---|
| `M03-vavr-parent.jar` | `f27222a50219d0cc7732bfacb152547f395836556a8c35c262f7ce6bee996134` |
| `M03-vavr-fix.jar` | `5c58a37ec13e98f7279ea6281a05c0d34ea246a717bb86b5850f8883ec4872c4` |
| `io/vavr/collection/Iterator.class` (parent) | `70422794c42ce445135a0aa9f9e4c1ee7089192b78d545a69e69520162ffa014` |
| `io/vavr/collection/Iterator.class` (fix) | `a49e52b5683a9dd7445b0126ded7c17c406693dcccb6805a34cae3800cbf9109` |

Runtime classpath (same file at both pins, sha256 `11e793a812091e9b941c67134d98e8d713e7b1e0323214a2641cceea9b8983b6`): `$O/artifacts/M03-vavr-fix.runtime-classpath.txt`; test classpath `$O/artifacts/M03-vavr-ROLE.test-classpath.txt`.
Use: `$J21/bin/java -cp $O/artifacts/M03-vavr-ROLE.jar:$(cat $O/artifacts/M03-vavr-fix.runtime-classpath.txt) ...` (Java 21 bytecode: JDK 21 or later).

**Landed tests** (`IteratorTest`, which inherits the traversable suite; upstream Maven build, JDK 21; logs `$O/logs/M03-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=576 failures=0 errors=0 skipped=9 both times |
| parent, its own test (offline) | tests=573 failures=0 errors=0 skipped=9 |
| fix's test file on the parent (offline) | tests=576 failures=2 errors=0 skipped=9: `IteratorTest#shouldFindLastNullElement` (`IteratorTest.java:957`, `expected: Some(null) but was: None`) and `IteratorTest#shouldFindLastNullWhenLastElementIsNull` (`:963`, the same message); `shouldReturnNoneWhenFindLastFindsNothing` passes |

**Release side** (strict checksums; `$O/releases/vavr-VERSION/`): `vavr 1.0.1` (2026-03-01) has the **parent's** `findLast` (`return Option.of(last);`) and `vavr 1.1.0` (2026-10-24) the **fix's** (`found` flag); neither file equals either pin byte for byte (other parts of `Iterator.java` differ: 1.x is a release line, the pins are 2.0.0-SNAPSHOT `main`). Runtime graph of both: `vavr-match` 1.0.0, `jspecify` 1.0.0.

**Signatures** (keyring `$O/gnupg-A`; key from keyserver.ubuntu.com, nothing further vouching for it; `$O/logs/M03-sigs.txt`): `vavr-1.0.1.jar`, `vavr-1.1.0.jar`, `vavr-match-1.0.0.jar` GOODSIG by `0942F59B726DA4BD2837DD44F45F03308EE961FF` (Grzegorz Piwowarek).

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds. 1.0.1 and 1.1.0 show the parent's and the fix's `findLast` logic in released form, not the pins' bytes.
- The landed tests compare `Option` values only; the supplier-counting and reordered histories of the brief were not run.

### M04 · Apache Commons Compress #334 — prefixed ZIP and the bytes before the first entry (pinned source build)

**Pins.** Parent `755fad2347c4b9ea4b56c61209d8f1f387cd5a67`, fix `0bacf83eb0b3367cd5572ab27e42a444efbcd5f8` (squash, one parent = the brief's; PR base `master`). Worktrees `$W/M04-commons-compress-parent`, `$W/M04-commons-compress-fix`.
Changed production file: `src/main/java/org/apache/commons/compress/archivers/zip/ZipFile.java` (offset correction for prepended bytes; new `getFirstLocalFileHeaderOffset()` and `getContentBeforeFirstLocalFileHeader()`). Changed test: `src/test/java/org/apache/commons/compress/archivers/zip/ZipFileTest.java` (new `testReadingOfExtraDataBeforeZip`). Added fixture `src/test/resources/COMPRESS-621.zip`.

**Fixture.** `COMPRESS-621.zip` at the fix pin: **217 bytes**, sha256 `198e954c1f2eaf9cf1cf8b7ce991d74ac3a0e2acfa7616dfbf7c8231ee6b20e0`, git blob `e4ce3e380ec36c690d49b6c84bff06b16257a61e`; its first 15 bytes read `Before Zip file`. Path: `$W/M04-commons-compress-fix/src/test/resources/COMPRESS-621.zip` (absent at the parent pin).

**Build facts.** Maven, single module, version **1.23-SNAPSHOT**, parent `org.apache.commons:commons-parent:54`, `maven.compiler.release` 8; `pom.xml` identical at both pins. Built with Maven 3.10.0 on **JDK 11.0.33** (`$J11`); classes are Java 8 bytecode. Runtime classpath file lists only the optional compression libraries (`zstd-jni` 1.5.2-5, `org.brotli:dec` 0.1.2, `xz` 1.9, `asm` 9.4); ZIP reading needs none of them. No SNAPSHOT dependency.

**Commands** (from `$W/M04-commons-compress-ROLE`; wrapped as `$O/scripts/mvn_A.sh M04-commons-compress-ROLE . TAG $J11 ZipFileTest [online]`):
- online (first resolution, 28 s): `JAVA_HOME=$J11 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=ZipFileTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 5–8 s on both pins)**: the same with `-o` in place of the thread setting.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests; the nested classes' digests are in `$O/artifacts/M04-commons-compress-ROLE.class-digests.txt`):

| File | sha256 |
|---|---|
| `M04-commons-compress-parent.jar` | `22f06a046530eff9667eb10a61316185659b68a4e6b42a3103dc1984f961b27b` |
| `M04-commons-compress-fix.jar` | `bc7b01eae0cd8acbffed4f9839b4d288c70c2c5498e172af7a759ca7c31c27f8` |
| `org/apache/commons/compress/archivers/zip/ZipFile.class` (parent) | `485fa264044aa68d835040ce265cc412768133660c8ad76f2cfaec79b17f4152` |
| `org/apache/commons/compress/archivers/zip/ZipFile.class` (fix) | `32949e0a4e56f104897fdb8dcfcf517229956c93aa3623a4b00e123bfb731336` |

Runtime classpath (same file at both pins, sha256 `d3ef483f23988db2f967ef1bb2849ae72f6c3b40c03ac3d974fcec8ddb03dade`): `$O/artifacts/M04-commons-compress-fix.runtime-classpath.txt`; test classpath `$O/artifacts/M04-commons-compress-ROLE.test-classpath.txt`.
Use: `$J11/bin/java -cp $O/artifacts/M04-commons-compress-ROLE.jar ...` (no runtime dependency is needed for `ZipFile`; add `$(cat $O/artifacts/M04-commons-compress-fix.runtime-classpath.txt)` for the other formats).

**Landed tests** (`ZipFileTest`, upstream Maven build, JDK 11; logs `$O/logs/M04-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=45 failures=0 errors=0 skipped=0 both times |
| parent, its own test (offline) | tests=44 failures=0 errors=0 skipped=0 |
| fix's test file and fixture on the parent (offline) | **does not compile**: `getFirstLocalFileHeaderOffset()` and `getContentBeforeFirstLocalFileHeader()` are fix-only (`ZipFileTest.java:[841,52]`, `[842,45]` cannot find symbol) |
| a **modified** copy on the parent: the landed file with the four accessor lines 841–844 deleted (`$O/dl/M04-modified/ZipFileTest.java`), plus the fixture | tests=45 failures=0 errors=1: `ZipFileTest#testReadingOfExtraDataBeforeZip` `java.lang.NullPointerException` at `ZipFileTest.java:843` (`e.getSize()`: `getEntry("COMPRESS-621.txt")` returned `null`) |
| the same modified copy on the fix (control) | tests=45 failures=0 errors=0 |

**Release side** (strict checksums; `$O/releases/commons-compress-VERSION/`): neither release's `ZipFile.java` equals a pin byte for byte. `1.22` is close to the **parent** (36 differing lines: Javadoc and small refactors) and lacks both accessors; `1.23.0` has both accessors but differs from either pin in over 1,500 lines (later rework), so it stands for the fix's API, not its bytes. Neither has a runtime dependency.

**Signatures** (keyring `$O/gnupg-A`, keys from the Apache Commons KEYS file `https://downloads.apache.org/commons/KEYS`, saved as `$O/keys-A/commons-KEYS`, sha256 `f154a693df7d01290487b3bf4c045481cdde6bd310b9eeb37b7a533b03b3299a`; `$O/logs/M04-sigs.txt`): `commons-compress-1.22.jar` GOODSIG by `8378BFAAD82FE5AA602AC356031EE010CA15D1EE` (Matt Sicker); `commons-compress-1.23.0.jar` GOODSIG by `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory (Code signing key)); both keys are in the KEYS file.

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds. The parent's `ZipFile` opens the prefixed fixture without an exception in the modified test and then finds no entry by name; whether `getEntries()` enumerates zero entries, as the brief expects, was not run.
- The writer-produced preamble file (`ZipArchiveOutputStream.writePreamble`) and the 15-byte-trimmed copy are not made: they are the domain work.

### M05 · Apache Commons RNG #65 — JDKRandom state restored into a fresh instance (pinned source build of `commons-rng-core` with `-am`)

**Pins.** Parent `9f30ec9c6dede48347c8939d18b1fd560b9229b8`, fix `592ad0be4fe4fa912b5cdaf5f83b006eb8a02f77` (squash, one parent = the brief's; PR base `master`). Worktrees `$W/M05-commons-rng-parent`, `$W/M05-commons-rng-fix`.
Changed production file: `commons-rng-core/src/main/java/org/apache/commons/rng/core/source32/JDKRandom.java` (the `stateSize` field is gone; `getStateInternal` prefixes the serialized delegate with its 4-byte length via `NumberFactory.makeByteArray`, `setStateInternal` reads it back). Changed test: `commons-rng-core/src/test/java/org/apache/commons/rng/core/source32/JDKRandomTest.java` (new `testRestoreToNewInstance`). `commons-rng-client-api`, `IntProvider.java` and every POM are identical at both pins.

**Build facts.** Maven reactor, version **1.3-SNAPSHOT**, parent `org.apache.commons:commons-parent:48`, `maven.compiler.source`/`target` 1.6. Built from the root with `-pl commons-rng-core -am` (root, `commons-rng-client-api`, `commons-rng-core`) with Maven 3.10.0 on **JDK 8u512** (`$J8`; javac 8 still accepts `-source 1.6`). `commons-rng-core`'s only runtime dependency is the same pin's `commons-rng-client-api` (`commons-math3` is test scope). No SNAPSHOT dependency outside the reactor. The log's `[ERROR] org.eclipse.jgit.errors.MissingObjectException` comes from the buildnumber plugin reading the shallow worktree's history; it does not fail the build.

**Commands** (from `$W/M05-commons-rng-ROLE`; wrapped as `REPORTS=commons-rng-core/target/surefire-reports $O/scripts/mvn_A.sh M05-commons-rng-ROLE . TAG $J8 JDKRandomTest [online] -pl commons-rng-core -am`):
- online (first resolution, 22 s): `JAVA_HOME=$J8 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=JDKRandomTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -pl commons-rng-core -am package`
- **offline (checked, 4–5 s on both pins)**: the same with `-o` in place of the thread setting.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests):

| File | sha256 |
|---|---|
| `M05-commons-rng-parent.jar` (core) | `c6224278557d42fdd9024a000e8f14d9ded7b161a991918ad27f25851720a6c3` |
| `M05-commons-rng-fix.jar` (core) | `6b804273ee325b66f9e553bc7a49b5de27e0f363774d9fac0784bd2880c62b6b` |
| `M05-commons-rng-client-api-parent.jar` | `2c621f3c5128e10445a2c03379f3ca8a56ee0d89d8a27f1025c2394a9af8bfe3` |
| `M05-commons-rng-client-api-fix.jar` | `4e01188383baf32d6564b4be56216ceb404c3ab080c31897c7594094a795df5c` |
| `org/apache/commons/rng/core/source32/JDKRandom.class` (parent) | `07e294dd3560071dfecfa3465892a97d17333ad6f047e30203de342ee4d9d1f7` |
| `org/apache/commons/rng/core/source32/JDKRandom.class` (fix) | `a4fbf1de5556eb72bd6079cd7aaf6843e605201b2d363edb2a3221d35b057d48` |

The two client-api jars differ only in build timestamps: every class in them has the same digest (`$O/artifacts/M05-commons-rng-client-api-ROLE.class-digests.txt` are identical).
Runtime classpath: `$O/artifacts/M05-commons-rng-ROLE.runtime-classpath.txt` = that side's client-api jar (written by hand: the reactor module is not installed).
Use: `$J8/bin/java -cp $O/artifacts/M05-commons-rng-ROLE.jar:$(cat $O/artifacts/M05-commons-rng-ROLE.runtime-classpath.txt) ...` (checked: a one-line `JDKRandom(1L).nextInt()` runs on both and prints `-1155869325`, equal to `new java.util.Random(1L).nextInt()`).

**Landed tests** (`JDKRandomTest`, upstream Maven build, JDK 8; logs `$O/logs/M05-*.log`, summaries `*.junit.txt`; surefire reruns a failing test twice, so a failing run's XML counts three executions):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=2 failures=0 errors=0 skipped=0 both times |
| parent, its own test (offline) | tests=1 failures=0 errors=0 skipped=0 |
| fix's test file on the parent (offline) | 2 tests, 1 error in each of 3 runs: `JDKRandomTest#testRestoreToNewInstance` `java.lang.IllegalStateException: java.io.EOFException` at `JDKRandomTest.java:60` (the restore) |

**Release side** (strict checksums; `$O/releases/commons-rng-core-VERSION/`): `commons-rng-core 1.2`'s `JDKRandom.java` is the **parent's** byte for byte; `1.3` has the **fix's** state-length logic (`splitStateInternal(s, 4)` then `NumberFactory.makeInt`) but differs from the fix's file in other lines (37 differing lines). `IntProvider.java` equals neither pin in either release. Runtime graphs: `commons-rng-client-api` 1.2 and 1.3 respectively.

**Signatures** (keyring `$O/gnupg-A`, keys from the Apache Commons KEYS file `$O/keys-A/commons-KEYS`, sha256 `f154a693df7d01290487b3bf4c045481cdde6bd310b9eeb37b7a533b03b3299a`; `$O/logs/M05-sigs.txt`): `commons-rng-core-1.2.jar`, `commons-rng-client-api-1.2.jar` GOODSIG by `B39617E095CD748DFE505816703413011E22D5B8` (Gilles Sadowski); `commons-rng-core-1.3.jar`, `commons-rng-client-api-1.3.jar` GOODSIG by `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert); both keys are in the KEYS file.

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds; 1.2 stands for the parent's `JDKRandom` exactly.
- The landed test checks ten integers after a cross-instance restore. Whether the parent's failed restore leaves the receiver's sequence untouched, and the boolean-cache continuation, were not run.
- The state format differs between the pins (the fix adds a 4-byte length), so a state saved on one side is not meant to be restored on the other.

### M06 · Agrona #202 — entry-set arrays copy each pair (upstream Gradle 6.1.1 build of `:agrona` at both pins, inline)

**Pins.** Parent `45d86347910231d66e5f7270d3b03053a1f80b23`, fix `13a9083e32f886c652041a536d13980a1ff982e0` (a two-parent merge: first
parent = the brief's before pin, second `e95962c28014c76a6f7e0a2861784bb7bf847ec7`, the PR's head). Worktrees `$W/M06-agrona-parent`, `$W/M06-agrona-fix`.
Changed production files (`agrona/src/main/java/org/agrona/collections/`): `Int2IntHashMap.java`, `Int2ObjectHashMap.java`,
`Object2IntHashMap.java`, `Object2ObjectHashMap.java` (both `toArray` overloads on the entry sets). Changed tests: the three matching
`*Test.java` files and the new `Object2ObjectHashMapTest.java`, each with `testToArray`, `testToArrayTyped`, `testToArrayWithArrayListConstructor`.

**Build facts.** Gradle (Groovy DSL), wrapper Gradle **6.1.1** (`-all` in the wrapper; run from the checked `-bin` distribution
`$O/tools/gradle-6.1.1`, the same Gradle without docs and sources), on **JDK 8u512** (`$J8`; Gradle 6.1 runs on 8–13). Project version
`1.3.1-SNAPSHOT` (the project's own, at both pins; no snapshot dependency). Plugins `com.github.johnrengelman.shadow` 5.2.0,
`io.freefair.javadoc-links` 4.1.6, `biz.aQute.bnd.builder` 5.0.0, `com.github.ben-manes.versions` 0.27.0 all resolved from the Plugin Portal;
no jcenter use, nothing substituted. Classes are Java 8 bytecode (major 52). **The `agrona` jar includes a generated source set**:
`generatePrimitiveSpecialisations` writes the `Long*` variants from the `Int*` sources, so the fix also changes
`Long2LongHashMap`, `Long2ObjectHashMap` and `Object2LongHashMap` (see the class diff). Runtime classpath **empty**
(test: hamcrest 2.2, mockito-junit-jupiter 3.2.4, JUnit Jupiter and vintage 5.6.0, JUnit 4.13, guava-testlib 28.2-jre; 19 files).
`build.gradle` is the same at both pins. The jar is built by bnd with `-reproducible: true`.

**Commands** (via `$O/scripts/gradle_case_C.sh WT 6.1.1 $J8 TAG agrona/build/test-results/test ARGS...`; same wrapper as M01's):
- online (first resolution, 22 s): `-I $O/scripts/resolve-all.init.gradle :agrona:setupResolveAll :agrona:jar :agrona:test --tests org.agrona.collections.Int2IntHashMapTest --tests org.agrona.collections.Int2ObjectHashMapTest --tests org.agrona.collections.Object2IntHashMapTest --tests org.agrona.collections.Object2ObjectHashMapTest`
- **offline (checked, 6–9 s at both pins)**: `--offline :agrona:jar :agrona:test` with the same `--tests` (the parent has no `Object2ObjectHashMapTest`: drop that filter there)
- classpath files: `--offline -I $O/scripts/resolve-all.init.gradle :agrona:setupWriteClasspath -PsetupCpOut=FILE [-PsetupCpConf=testRuntimeClasspath]`

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M06-agrona-parent.jar` | `c3f74d81a20ba383e8ebfb8de8297a8f4ab2e64fe9965254b67e6c7eb1a05584` |
| `M06-agrona-fix.jar` | `7ccdafcd56cb700664de384eab6cc45c01f0d591f30d2912002c13b6ebc479a9` |
| `org/agrona/collections/Int2IntHashMap$EntrySet.class` (parent) | `50bee35ebc436c537705da303f629c8dce8d7072d025b8e8b73915339da5d789` |
| `org/agrona/collections/Int2IntHashMap$EntrySet.class` (fix) | `336b831029d6516b96f7c0b38b4056c48990b2e1d07a5c95af13cc6ad7b01b37` |
| `org/agrona/collections/Int2IntHashMap$EntryIterator.class` (parent) | `2da93088755ecacfe790cc8f44640c12371bffaff41939e0d1497186748bcb80` |
| `org/agrona/collections/Int2IntHashMap$EntryIterator.class` (fix) | `e8cb040dc7f5298f34f03270cf4b08e775825b0bc4eff6c76c40977a0dc09a02` |
| `org/agrona/collections/Int2ObjectHashMap$EntrySet.class` (parent) | `7ef756767be7d3995508d5400d69e1942f6885b6298c6c21cdbb5130ea740dc3` |
| `org/agrona/collections/Int2ObjectHashMap$EntrySet.class` (fix) | `8baeebd07cfd1d81c00c07c3eec08c46e666f1293705bd6e37ce8c6334b65dfe` |
| `org/agrona/collections/Object2IntHashMap$EntrySet.class` (parent) | `6d3efcd40fbd2c88b27da93277a4174e68814f131581056d5550fd55f7c1d718` |
| `org/agrona/collections/Object2IntHashMap$EntrySet.class` (fix) | `de1ab14d8b9832fcddf882283fd7408b4a70d0f49c736716f69afbc4c58b5756` |
| `org/agrona/collections/Object2ObjectHashMap$EntrySet.class` (parent) | `bd40976db3fefc45e3b7c458d027ffe359e04ca86817c70a4b7a54d63a798a7a` |
| `org/agrona/collections/Object2ObjectHashMap$EntrySet.class` (fix) | `c7b5ff1c467624a9259989e1d315dca94d4e9292d46b864c5bc2b03832647316` |

All 41 entries that differ between the jars, with both digests (iterators, entry sets, outer classes, and the generated `Long*` variants):
`$O/artifacts/M06-agrona.classdiff.txt`. `Int2IntHashMap.class` itself is identical in both jars. Runtime classpath: empty at both pins
(`$O/artifacts/M06-agrona-ROLE.runtime-classpath.txt`); test classpath `$O/artifacts/M06-agrona-fix.test-classpath.txt` (same at both pins).
Use: `$J8/bin/java -cp $O/artifacts/M06-agrona-ROLE.jar:CLASSES ...` (no other jar is needed; on JDK 9+ agrona's tests add
`--add-opens java.base/java.lang.reflect=ALL-UNNAMED --add-opens java.base/sun.nio.ch=ALL-UNNAMED --add-exports jdk.unsupported/sun.misc=ALL-UNNAMED`, not needed for `org.agrona.collections`).

**Landed tests** (the four map test classes, upstream Gradle build, JDK 8; logs `$O/logs/M06-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own tests (online, then offline) | tests=108 failures=0 errors=0 skipped=0 (Int2Int 64, Int2Object 21, Object2Int 20, Object2Object 3); offline tests=108 failures=0 errors=0 skipped=0 |
| parent, its own three classes (offline) | tests=96 failures=0 errors=0 skipped=0 |
| fix's four test files on the parent (offline) | tests=108 failures=12 errors=0 skipped=0: all three new tests in each class. `Int2IntHashMapTest` and `Int2ObjectHashMapTest`: `expected: <true> but was: <false>` (Int2IntHashMapTest.java:675, :692, :708; Int2ObjectHashMapTest.java:443, :460, :476); `Object2IntHashMapTest` and `Object2ObjectHashMapTest`: `java.lang.NullPointerException` (Object2IntHashMapTest.java:456, :473, :489; Object2ObjectHashMapTest.java:33, :50, :66) — `$O/logs/M06-transplant-failures.txt` |

**Release side.** Resolved with strict checksums into `$O/releases/agrona-1.3.0/` and `$O/releases/agrona-1.4.0/` (no dependencies).
**1.3.0** (Central 2020-01-21): all four changed files equal the **parent's** byte for byte. **1.4.0** (Central 2020-02-26, the first release
after the merge): equals neither (100+ lines differ from each pin in every file), and carries `toArray` overrides in all four
(`$O/logs/M06-release-srccmp.txt`); it was not compared further.

| Jar | sha256 |
|---|---|
| `agrona-1.3.0.jar` | `52cd84bf242f460161ce8fbd783ea226493778dde3df565ad47502d18d1ad22d` |
| `agrona-1.4.0.jar` | `0a60f11877ea666be7affb6c9202509236f50cc66706324752d4367494361e20` |

**Signatures** (keyring `$O/gnupg-C`; key from keyserver.ubuntu.com, `$O/keys-C/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `agrona-1.3.0.jar`, `-sources.jar` | `D89F96C914228178B3D5AD54ED2F1A1C5301FCF2` (Todd L. Montgomery) | EXPKEYSIG with VALIDSIG: signed 2020-01-21, key expired 2020-08-10 |
| `agrona-1.4.0.jar`, `-sources.jar` | `D89F96C914228178B3D5AD54ED2F1A1C5301FCF2` (Todd L. Montgomery) | EXPKEYSIG with VALIDSIG: signed 2020-02-26, key expired 2020-08-10 |

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds and carry no dependency. 1.3.0 stands for the parent's four map files exactly; no release equals the fix.
- The landed tests consume the arrays through `toArray`, `toArray(T[])` and the `ArrayList` constructor and remove by retained key; no
  `HashSet` probe or entry `hashCode` was run.

### M07 · Spatial4j #212 — GeoJSON MultiPoint closed before its container resumes (pinned source build, inline)

**Pins.** Parent `9180d076b6683b54a961b373419d3e4347ac0b35`, fix `81f473f4dc4ad0edc1fab12eb8908dadff69944a` (squash of the PR's two commits, one parent = the brief's). Worktrees `$W/M07-spatial4j-parent`, `$W/M07-spatial4j-fix`.
Changed production file: `src/main/java/org/locationtech/spatial4j/io/jackson/GeometryAsGeoJSONSerializer.java` (one line removed: the `return;`
after the MultiPoint coordinates, so the method falls through to the closing `writeEndObject`). Also `CHANGES.md`. **The PR adds no test.**

**Build facts.** Maven, single root module `spatial4j`, version **0.9-SNAPSHOT**, `maven.compiler.source`/`target` 1.8; `pom.xml` identical at both
pins. Built with Maven 3.10.0 on **JDK 11.0.33** (`$J11`); classes are Java 8 bytecode (major 52). No SNAPSHOT dependencies.
Dependencies, all declared `<optional>true</optional>`: `org.noggit:noggit:0.8`, `com.fasterxml.jackson.core:jackson-databind:2.9.10.8`
(pulls jackson-annotations 2.9.10 and jackson-core 2.9.10), `org.locationtech.jts:jts-core:1.18.1`. Test: JUnit 4.13.1, slf4j-simple 1.7.25,
randomizedtesting-runner 2.5.3. Plugins: compiler 3.8.0, surefire 2.22.1 (no enforcer).

**Commands** (from `$W/M07-spatial4j-ROLE`; wrapped as `$O/scripts/mvn_B.sh M07-spatial4j-ROLE . TAG $J11 TESTS [online]`, which adds the
lint/report skips and `-DforkCount=1`, `-Dmaven.test.failure.ignore=true`, `package`):
- online (first resolution, 32 s): `JAVA_HOME=$J11 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=GeneralGeoJSONTest,JacksonGeoJSONWriterTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 4–5 s on both pins)**: the same with `-o`, tests `GeneralGeoJSONTest,JacksonGeoJSONWriterTest,JacksonGeoJSONReaderTest,SimpleJacksonTest`.
- runtime classpath: `JAVA_HOME=$J11 $MVN -q -o dependency:build-classpath -DincludeScope=runtime -Dmdep.outputFile=FILE` (identical at both pins).
  Because the project's own dependencies are optional only towards *its* consumers, this classpath **includes** jackson-databind 2.9.10.8 and
  jts-core 1.18.1, as the brief needs.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests). Only one class differs between the two jars
(109 classes each; `classdiff_C.py` from the L01–L20 setup).

| File | sha256 |
|---|---|
| `M07-spatial4j-parent.jar` | `09d4385c391ef52acbec98ff3f120593f8a4f6890f7607d02d3d929770a3c5bf` |
| `M07-spatial4j-fix.jar` | `9d6523102b891915932160bd2952ecf10e5623e25a8c757a4bf4acdaa5621a3d` |
| `org/locationtech/spatial4j/io/jackson/GeometryAsGeoJSONSerializer.class` (parent) | `a4f654b78203c5d7029b083da70803db1cc0b8194051f0b1b67dae49f37b86d2` |
| `org/locationtech/spatial4j/io/jackson/GeometryAsGeoJSONSerializer.class` (fix) | `cf9dd80a5725ee968f2c0553b2944a49c9dc7186df32d91d8d55f4a4e92a17f7` |
| `M07-spatial4j.runtime-classpath.txt` (both pins) | `cf42c44efa8db975efd78adedb0c02f036a73d04338bb42d32626fd7fb06da53` |
| `noggit-0.8.jar` | `dd9901c7d72ffd97d952271e3c486ddc9c78dd25a74db69ddbf2670431c7c81f` |
| `jackson-databind-2.9.10.8.jar` | `8fd3467359648c1ad89e91f2b8bb8ba75460b0b1fbff8ac4a3308af8b27501b6` |
| `jackson-annotations-2.9.10.jar` | `c876f2e85d0f108a34cdd11ccc9d8d7875697367efc75bf10a89c2c26aee994c` |
| `jackson-core-2.9.10.jar` | `65fe26d7554a4409652c86ee38f2e94bc42934326d88b3c78c61f66ff2222c53` |
| `jts-core-1.18.1.jar` | `722ac3abeaea84a9496b632a227d09c612cf20069d31f8ebf25ff5810379d235` |

The five runtime jars (in `$O/m2`) each match the `.sha1` Maven Central served beside them. Test classpath: `$O/artifacts/M07-spatial4j.test-classpath.txt`.
Use: `$J11/bin/java -cp $O/artifacts/M07-spatial4j-ROLE.jar:$(cat $O/artifacts/M07-spatial4j.runtime-classpath.txt) ...`.

**Landed tests.** None landed. The existing Jackson/GeoJSON classes were run at both pins (upstream Maven build, JDK 11; logs `$O/logs/M07-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `GeneralGeoJSONTest` + `JacksonGeoJSONWriterTest` (online) | tests=59 failures=0 errors=0 skipped=0 |
| fix, those two + `JacksonGeoJSONReaderTest` + `SimpleJacksonTest` (offline) | tests=90 failures=0 errors=0 skipped=0 (29 + 30 + 29 + 2) |
| parent, the same four (offline) | tests=90 failures=0 errors=0 skipped=0 |

**Issue #210's reproduction** (its `Main` verbatim, `$O/repro/M07/Main.java`, compiled and run on JDK 11 with each built jar and the runtime
classpath above; output `$O/logs/M07-issue210-repro.txt`):
- parent: prints `[{"type":"Point","coordinates":[100.0,100.0]}]`, then throws `com.fasterxml.jackson.core.JsonGenerationException: Current context not Array but Object` from `WriterBasedJsonGenerator.writeEndArray`, as the issue reports.
- fix: prints the Point line, then `[{"type":"MultiPoint","coordinates":[[100.0,100.0]]}]`.

**Release side.** Maven Central has spatial4j 0.6, 0.7, 0.8 only (metadata last updated 2020-11-26): **no release carries the fix**. `0.8`'s
`GeometryAsGeoJSONSerializer.java` is the **parent's** byte for byte (resolved with strict checksums: `$O/releases/spatial4j-0.8/`, jar sha256
`566cfe7eea3a96ef7dd2f4e30394edefca71454505513f090fa54be21c529082`).

**Signatures** (keyring `$O/gnupg-B`, `.asc` from Central in `$O/dl/sigs-B/`; key from keyserver.ubuntu.com, `$O/keys-B/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `spatial4j-0.8.jar` | `0143E2AA6983731F9D1DD82A2184C00ABBCD7E0E` (David Smiley) | GOODSIG (signed 2020-11-26) |

**Jobs.** None: every run took under a minute inline. Build trees deleted; worktrees kept.

**For the domain agent**
- The built jars are the pins' own builds; they differ in exactly the one serializer class above.
- The issue's own two-line reproduction is confirmed at both pins. Nothing beyond it (nested collections, readback) was run.

### M08 · Checkstyle #14128 — HiddenField stops at an implicitly static member record (upstream Maven build at both pins, by job)

**Pins.** Parent `d3f020a5c477edbb57afc0f3fa2d1fab0849d6fb`, fix `d150018d141294ac9bb02ae653d01072c5c4c4ae` (one commit, one parent = the brief's). Worktrees `$W/M08-checkstyle-parent`, `$W/M08-checkstyle-fix`.
Changed production file: `src/main/java/com/puppycrawl/tools/checkstyle/checks/coding/HiddenFieldCheck.java` (the static-type test in the
frame walk gains `|| ast.getType() == TokenTypes.RECORD_DEF`, "inner record is implicitly static"). Changed test:
`src/test/java/com/puppycrawl/tools/checkstyle/checks/coding/HiddenFieldCheckTest.java` (two new tests); new inputs
`src/test/resources-noncompilable/com/puppycrawl/tools/checkstyle/checks/coding/hiddenfield/InputHiddenFieldInnerRecordsImplicitlyStatic.java` and
`.../InputHiddenFieldRecordsImplicitlyStaticClassComparison.java`.

**Build facts.** Maven, single module `checkstyle`, version **10.12.7-SNAPSHOT**, `java.version` 11; `pom.xml` identical at both pins.
Enforcer requires Maven ≥ 3.6.3; Maven 3.10.0 passes `validate` offline (enforcer, tidy, xml check-format run there). `.mvn/jvm.config` adds
`--add-exports/--add-opens jdk.compiler/...` (so build on JDK ≥ 11; **JDK 17.0.21**, `$J17`, is used). No SNAPSHOT dependencies.
The default lifecycle runs antlr4 4.13.1, build-helper, compiler 3.12.0, plexus-component-metadata, and `exec:java` (`JavadocPropertiesGenerator`,
needs compiled classes) before tests; surefire 3.2.3 with `src/test/resources-noncompilable` as an additional classpath element.
An all-in-one jar is only made by the `assembly` profile (not built).
**`dependency:go-offline` fails** (`org.apache.ws.commons.axiom:axiom:jar:1.2.15` is a POM-only artifact some plugin's graph names);
instead the lifecycle up to `compile` was resolved inline with `-Dmaven.main.skip -Dmaven.test.skip=true -Dantlr4.skip package` (it then stops
at `exec:java`, as expected), and the job's first step is the online build, which resolves the rest (surefire's provider, test classpath).

**Commands** (from `$W/M08-checkstyle-ROLE`; job steps `$O/scripts/M08_job.sh STEP`, each `$O/scripts/mvn_B.sh M08-checkstyle-ROLE . TAG $J17 HiddenFieldCheckTest [online]` with `MAVEN_OPTS=-Xmx2g`):
- online: `JAVA_HOME=$J17 MAVEN_OPTS=-Xmx2g $MVN -Daether.connector.basic.threads=1 $SK -Dtest=HiddenFieldCheckTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dmaven.test.failure.ignore=true package`
- offline: the same with `-o` (checked by the job's second step: see Jobs).
- runtime classpath: `JAVA_HOME=$J17 $MVN -q -o dependency:build-classpath -DincludeScope=runtime -Dmdep.outputFile=FILE`.
- CLI (checked inline on the 10.12.4 release; on both built jars by the job's `cli` step):
  `$J17/bin/java -cp JAR:$(cat CLASSPATHFILE) com.puppycrawl.tools.checkstyle.Main -c $O/scripts/M08-cli-check/hidden.xml -f xml FILE.java`.
  `hidden.xml` is `Checker → TreeWalker → HiddenField` with default properties. The process exits with the number of errors (1 on the smoke
  file), and prints `Checkstyle ends with N errors.` on stdout after the XML: use `-o OUT.xml` to keep the XML apart.

**Artifacts** (`$O/artifacts/`, written by the job): `M08-checkstyle-ROLE.jar`, `M08-checkstyle-ROLE.sha256` (jar and
`com/puppycrawl/tools/checkstyle/checks/coding/HiddenFieldCheck.class` digests), `M08-checkstyle-ROLE.runtime-classpath.txt`.
**Pending job `20261125-202838-setup-build-checkstyle-at-both-14128-rev`**: digests to be copied here when it is back.
Use: `$J17/bin/java -cp $O/artifacts/M08-checkstyle-ROLE.jar:$(cat $O/artifacts/M08-checkstyle-ROLE.runtime-classpath.txt) com.puppycrawl.tools.checkstyle.Main ...`.

**Landed tests** (`HiddenFieldCheckTest`, upstream Maven build, JDK 17; logs `$O/logs/M08-*.log`, summaries `*.junit.txt`): **pending the job**.

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | pending |
| parent, its own test (offline) | pending |
| fix's test file and its two new inputs on a copy of the parent (offline) | pending (expected to fail) |

**Release side.** The brief names **10.12.4** (issue #14028). Its `HiddenFieldCheck.java` (sources jar) equals the **parent's** byte for byte;
so does 10.12.6's. **10.12.7** is the first release whose file equals the **fix's**; 10.13.0's differs from both (later changes). 10.12.4 was
resolved with strict checksums with its runtime graph: `$O/releases/checkstyle-10.12.4/` (`lib/` 37 jars, `sources/`, `tree.txt`,
`classpath.txt` sha256 `de5e44bf32e29e16cc9a0e0057373def344895ef756a1db5db98c3c674b6dd79`), jar sha256
`1ea984bd2772caade3867e797297c9ee16044c5f5d7b9a2d49faff1d5ab7123a`. The 10.12.6, 10.12.7 and 10.13.0 sources jars (`$O/dl/sources-B/`) were
checked by Central's `.sha1` only. **The 10.12.4 CLI runs**: the smoke file `$O/scripts/M08-cli-check/Trivial.java` (a setup file, not a brief
fixture) gives one `HiddenFieldCheck` error, `'n' hides a field.` at 2:37 (`$O/logs/M08-cli-10.12.4.xml`).

**Signatures** (keyring `$O/gnupg-B`, `.asc` from Central in `$O/dl/sigs-B/`; key from keyserver.ubuntu.com, `$O/keys-B/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `checkstyle-10.12.4.jar` | `06D34ED6FF73DE368A772A781063FE98BCECB758` (Roman Ivanov) | GOODSIG (signed 2023-10-02) |

**Jobs.** `20261125-202838-setup-build-checkstyle-at-both-14128-rev` (`$O/scripts/submit_B.py m08`; 3 CPU, 4G, ~30 m): fix online, fix offline
(+ jar, digests, classpath), parent offline (+ the same), transplant on a `git archive` copy of the parent in `$O/build/` (passes only when
the test fails), CLI on both jars, clean. A Checkstyle build compiles its 439 main sources, runs its generators and compiles over 750 test-side sources (`src/test/java`, `src/it/java`, `src/xdocs-examples/java`), so none of it ran inline.

**For the domain agent**
- Until the job is back, the 10.12.4 release (= parent's `HiddenFieldCheck`) is the only runnable Checkstyle here; 10.12.7 from Central would
  stand for the fix's file but was not resolved as a graph.
- The XML message text depends on locale; `source` and line/column do not.

### M09 · libGDX #7278 — `intersectPolygons` needs three clipped vertices (upstream Gradle 8.4 build of `:gdx` only, at both pins, inline; releases 1.11.0, 1.12.1 = parent, 1.13.0 = fix)

**Pins.** Parent `0de4d893abc4d02d8e1bf949edda4a9d5c547e18`, fix `7bed7d3666d3b343aebeb1c3f733eae63380dd10` (squash, one parent = the brief's). Worktrees `$W/M09-libgdx-parent`, `$W/M09-libgdx-fix`.
Changed production file: `gdx/src/com/badlogic/gdx/math/Intersector.java` (in `intersectPolygons(Polygon, Polygon, Polygon)`,
`if (floatArray2.size != 0)` becomes `if (floatArray2.size >= 6)`). Changed test: `gdx/test/com/badlogic/gdx/math/IntersectorTest.java`
(new `testIntersectPolygons`; the static imports become `org.junit.Assert.*`). `Polygon.java` is the same at both pins.

**Build facts.** Gradle (Groovy DSL), wrapper Gradle **8.4** (run from `$O/tools/gradle-8.4`), on **JDK 17.0.21** (`$J17`). Project version
`1.12.2-SNAPSHOT` (the project's own). `gdx` compiles with `options.release = 7` (`versions.java`), so classes are **Java 7 bytecode (major 51)**.
Runtime dependency: `com.badlogicgames.gdx:gdx-jnigen-loader:2.3.1` only (test: JUnit 4.13.2, Hamcrest 1.3). The `Intersector`/`Polygon`
code is pure Java; the jar holds no native library, and none is needed for `com.badlogic.gdx.math`.
Two things are needed to build `:gdx` alone, without changing a build file:
- **`--configure-on-demand`**: without it Gradle configures every project, and `:backends:gdx-backend-android` needs the Android Gradle
  Plugin 8.1.2 (and an Android SDK), which is not set up (checked: `$O/logs/M09-fix-no-cod.log`).
- **`-Dmaven.repo.local=$O/mavenlocal-empty`**: the build lists `mavenLocal()` first; this points it at an empty folder instead of the
  user's `~/.m2`. The build also lists `oss.sonatype.org` snapshot/release repositories; nothing was resolved from them (everything came from
  Maven Central and the Plugin Portal: spotless, `gdx-jnigen-gradle` 2.4.1).

**Commands** (via `$O/scripts/gradle_case_C.sh WT 8.4 $J17 TAG gdx/build/test-results/test ARGS...`; same wrapper as M01's; `$G` =
`-Dmaven.repo.local=$O/mavenlocal-empty --configure-on-demand`):
- online (first resolution, 19 s): `$G -I $O/scripts/resolve-all.init.gradle :gdx:setupResolveAll :gdx:jar :gdx:test --tests com.badlogic.gdx.math.IntersectorTest`
- **offline (checked, 5–11 s at both pins)**: `--offline $G :gdx:jar :gdx:test --tests com.badlogic.gdx.math.IntersectorTest`
- classpath files: `--offline $G -I $O/scripts/resolve-all.init.gradle :gdx:setupWriteClasspath -PsetupCpOut=FILE [-PsetupCpConf=testRuntimeClasspath]`

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M09-libgdx-parent.jar` | `fe72ddb187d193733c681dd16910e08e437a5e943499cad0ffe29fb473e390e6` |
| `M09-libgdx-fix.jar` | `b6772556479d1a7ed00cc4b0cb5357d4ac3b84068bf7f3ab0b2dcef33c7866cb` |
| `com/badlogic/gdx/math/Intersector.class` (parent) | `4f6c48bedf360164f85a2ae7b15b28d7e4524e75eb1e388ac01cfde5bd4d55de` |
| `com/badlogic/gdx/math/Intersector.class` (fix) | `b994f697d93975c51fab5b0b3f8499da274f1a53076d6c0ddb11bc3ccdf699c4` |
| `gdx-jnigen-loader-2.3.1.jar` (runtime dependency, both pins) | `6490dda225a61c7602c27bbec4e481137ff595f8ce0b2ddba414f0c3406aee60` |

The only other entries that differ: `Intersector$MinimumTranslationVector.class` and `Intersector$SplitTriangle.class`
(`$O/artifacts/M09-libgdx.classdiff.txt`, both digests). Runtime classpath (same at both pins): `$O/artifacts/M09-libgdx-fix.runtime-classpath.txt`
(the jnigen loader in `$O/gradle-home`); test classpath `$O/artifacts/M09-libgdx-fix.test-classpath.txt`.
Use: `$J17/bin/java -cp $O/artifacts/M09-libgdx-ROLE.jar:$(cat $O/artifacts/M09-libgdx-fix.runtime-classpath.txt):CLASSES ...`.

**Landed tests** (`IntersectorTest`, upstream Gradle build, JDK 17; logs `$O/logs/M09-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=6 failures=0 errors=0 skipped=0; offline tests=6 failures=0 errors=0 skipped=0 |
| parent, its own test (offline) | tests=5 failures=0 errors=0 skipped=0 |
| fix's test file on the parent (offline) | tests=6 failures=1 errors=0 skipped=0: **IntersectorTest#testIntersectPolygons** (`java.lang.IllegalArgumentException: polygons must contain at least 3 points.` at `Polygon.setVertices(Polygon.java:118)` ← `Intersector.intersectPolygons(Intersector.java:205)` ← `IntersectorTest.java:230`) |

**Release side.** Resolved with strict checksums into `$O/releases/gdx-1.11.0/`, `gdx-1.12.1/`, `gdx-1.13.0/` (`lib/`, `sources/`,
`tree.txt`, `classpath.txt`; each `gdx` plus its `gdx-jnigen-loader`). Against the pins (`$O/logs/M09-release-srccmp.txt`):
- **1.11.0** (the version of issue #6986): `Intersector.java` equals neither pin as a file (an older file), but its
  `intersectPolygons(Polygon, Polygon, Polygon)` method is **the parent's, line for line** (the `size != 0` branch). `Polygon.java` equals the pins'.
- **1.12.1** (Central 2023-11-02): `Intersector.java` equals the **parent's** byte for byte; `Polygon.java` equals the pins'.
- **1.13.0** (Central 2024-10-17, first release after the fix): `Intersector.java` equals the **fix's** byte for byte; `Polygon.java` equals the pins'.

| Jar | sha256 |
|---|---|
| `gdx-1.11.0.jar` | `23153c67e19560644e0fa1235232b5d85ee41cf289281c2da7ec8c28e35750b9` |
| `gdx-1.12.1.jar` | `8d3209e948211fde9cdacc2b01faced323e548aa52ef78e5c760845a88746970` |
| `gdx-1.13.0.jar` | `eeb1ffdef777204af8ab41adb2a5e51fb0517b374dd4e50aa3ae134423caf86b` |
| `gdx-jnigen-loader-2.3.1.jar` (1.11.0, 1.12.1) | `6490dda225a61c7602c27bbec4e481137ff595f8ce0b2ddba414f0c3406aee60` |
| `gdx-jnigen-loader-2.5.2.jar` (1.13.0) | `df81f23cfd6785c52d35e108eeaa3930f559d4d2770a6102e75ca7bfa6f9f27a` |

**Signatures** (keyring `$O/gnupg-C`; key from keyserver.ubuntu.com, `$O/keys-C/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `gdx-1.11.0.jar`, `gdx-1.12.1.jar`, `gdx-1.13.0.jar` and their `-sources.jar` | `5F9B2AF3084E4EADB2F5AE1EB0F79A98780D77FA` (Mario Zechner) | GOODSIG |
| `gdx-jnigen-loader-2.3.1.jar`, `-2.5.2.jar` and their `-sources.jar` | `5F9B2AF3084E4EADB2F5AE1EB0F79A98780D77FA` (Mario Zechner) | GOODSIG |

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds; 1.12.1 stands for the parent's `Intersector` exactly and 1.13.0 for the fix's exactly, both
  signed, if a released jar is wanted (their other classes differ from the pins').
- The landed test checks the regression triangle with a fresh output only; no null-output call and no reused, already-read output polygon was run.

### M10 · Apache TinkerPop #3105 — a second by() on one global dedup is rejected (upstream Maven build of gremlin-core and tinkergraph-gremlin at both pins, by job)

**Pins.** Parent `007fd228a992f1dccba22e25a88e647168e5ba4f`, fix `a97db03618fa2fd7c17d24e331ff62adfe9c8df4` (squash of the PR's two commits, one parent = the brief's; base branch `3.8-dev`). Worktrees `$W/M10-tinkerpop-parent`, `$W/M10-tinkerpop-fix`.
Changed production file: `gremlin-core/src/main/java/org/apache/tinkerpop/gremlin/process/traversal/step/filter/DedupGlobalStep.java`
(`modulateBy` throws `IllegalStateException("Dedup step can only have one by modulator")` when a by-traversal is already set). Changed tests:
`gremlin-core/src/test/java/org/apache/tinkerpop/gremlin/process/traversal/step/filter/DedupGlobalStepTest.java` and the Gherkin
`gremlin-test/src/main/resources/org/apache/tinkerpop/gremlin/test/features/filter/Dedup.feature` (one new error scenario), plus its
translations for .NET, Go, JavaScript and Python and `CHANGELOG.asciidoc`.

**Build facts.** Maven multi-module, version **3.8.0-SNAPSHOT**; root `pom.xml` identical at both pins. Enforcer: Java `[1.8,18)`, Maven `[3.5.3,)`;
compiler source 1.8. No `.mvn/` directory. Built with Maven 3.10.0 on **JDK 11.0.33** (`$J11`; the enforcer refuses 18+, so not the default 25).
Restricted to `-pl gremlin-core,tinkergraph-gremlin -am`, whose reactor is: the root pom, `gremlin-language` (ANTLR grammar), `gremlin-shaded`
(shade plugin), `gremlin-core`, `gremlin-test` (tinkergraph's test-scope dependency, holds the feature files), `tinkergraph-gremlin`. No .NET, Go,
Python or JavaScript module is built. All inter-module dependencies are this reactor's own 3.8.0-SNAPSHOT; no external SNAPSHOT.
Surefire 2.22.2 (`**/*IntegrateTest.java` excluded); feature tests use Cucumber 6.11.0 via `TinkerGraphFeatureTest`
(`features = classpath:/org/apache/tinkerpop/gremlin/test/features`, tags `not @GraphComputerOnly and not @AllowNullPropertyValues`).
External dependencies resolved inline first: `$MVN -Daether.connector.basic.threads=1 -pl gremlin-core,tinkergraph-gremlin -am dependency:go-offline -DexcludeReactor=true`
(27 s, BUILD SUCCESS, `$O/logs/M10-go-offline.log`); `-o ... validate` on the same modules passes (enforcer included).

**Commands** (from `$W/M10-tinkerpop-ROLE`; job steps `$O/scripts/M10_job.sh STEP`, each `$O/scripts/mvn_B.sh M10-tinkerpop-ROLE . TAG $J11 DedupGlobalStepTest,TinkerGraphFeatureTest [online] ...` with `MAVEN_OPTS=-Xmx2g`):
- online: `JAVA_HOME=$J11 MAVEN_OPTS=-Xmx2g $MVN -Daether.connector.basic.threads=1 $SK -Dtest=DedupGlobalStepTest,TinkerGraphFeatureTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dmaven.test.failure.ignore=true -pl gremlin-core,tinkergraph-gremlin -am -Dcucumber.features=classpath:org/apache/tinkerpop/gremlin/test/features/filter/Dedup.feature dependency:build-classpath -DincludeScope=runtime -Dmdep.outputFile=$O/tmp/TAG.cp.txt package`
- offline: the same with `-o` (checked by the job's second step: see Jobs).
- `-Dcucumber.features=...` limits the feature run to `filter/Dedup.feature`; drop it to run every feature file.
- The classpath file is written by every module in turn; the last, `tinkergraph-gremlin`, wins. `$O/scripts/M10_cp.py` rewrites its reactor paths to the copied jars.

**Artifacts** (`$O/artifacts/`, written by the job): `M10-tinkerpop-ROLE/` with `gremlin-language-`, `gremlin-shaded-`, `gremlin-core-`,
`gremlin-test-` and `tinkergraph-gremlin-3.8.0-SNAPSHOT.jar`; `M10-tinkerpop-ROLE.sha256` (those jars and
`org/apache/tinkerpop/gremlin/process/traversal/step/filter/DedupGlobalStep.class`); `M10-tinkerpop-ROLE.runtime-classpath.txt`
(tinkergraph-gremlin's runtime classpath, pointing at the copied jars and `$O/m2`).
**Pending job `20261125-202839-setup-build-tinkerpop-gremlin-core-and-t`**: digests to be copied here when it is back.
Use: `$J11/bin/java -cp $O/artifacts/M10-tinkerpop-ROLE/tinkergraph-gremlin-3.8.0-SNAPSHOT.jar:$(cat $O/artifacts/M10-tinkerpop-ROLE.runtime-classpath.txt) ...`
(check that the classpath file already lists the tinkergraph jar before adding it).

**Landed tests** (upstream Maven build, JDK 11; logs `$O/logs/M10-*.log`, per-module summaries `*.junit.txt`): **pending the job**.

| Run | Result |
|---|---|
| fix: `DedupGlobalStepTest` and Dedup.feature (online, then offline) | pending |
| parent: its own `DedupGlobalStepTest` and Dedup.feature (offline) | pending |
| fix's `DedupGlobalStepTest` and Dedup.feature on a copy of the parent (offline) | pending (expected to fail in both modules) |

**Release side.** gremlin-core sources jars from Central (checked by `.sha1` only, `$O/dl/sources-B/`): **3.8.0** has the fix's check in
`DedupGlobalStep.java` (its file differs from the fix's only by a later `getPopInstructions()` override); **3.7.3 and 3.7.4 lack it** (older
`Barrier` interface, no check). No release equals either pin's file. 3.8.1 and 3.8.2 are also on Central (not compared).

**Signatures.** None checked: no release graph was resolved for this case.

**Jobs.** `20261125-202839-setup-build-tinkerpop-gremlin-core-and-t` (`$O/scripts/submit_B.py m10`; 3 CPU, 5G, ~35 m): fix online, fix
offline (+ jars, digests, classpath), parent offline (+ the same), transplant on a `git archive` copy of the parent in `$O/build/` (passes only
when both modules show a failure), clean.

**For the domain agent**
- The embedded `TinkerFactory.createModern()` graph is in `tinkergraph-gremlin`; nothing beyond the upstream tests was run.
- 3.8.0 from Central carries the fix's behaviour, but a newer tree than the fix pin.


## Jobs

Two jobs, queued by fork B with `$O/scripts/submit_B.py m08` and `m10`. Each resolves online first (one connector thread), runs its later
steps offline, copies its jars, digests and classpaths to `$O/artifacts/`, and ends by removing its build trees (`$O/build/`). A transplant
step passes only when the named tests fail. Every other case ran inline (each run under a minute).

| Job | Case | What it runs | Estimate | Result |
|---|---|---|---|---|
| `20261125-202838-setup-build-checkstyle-at-both-14128-rev` | M08 | `HiddenFieldCheckTest` on the fix (online, then offline) and on the parent, with jars, class digests and runtime classpaths; the fix's test and its two new inputs on a `git archive` copy of the parent; the CLI on both built jars | 3 CPU, 4G, 30m | pending |
| `20261125-202839-setup-build-tinkerpop-gremlin-core-and-t` | M10 | `DedupGlobalStepTest` and `TinkerGraphFeatureTest` limited to `filter/Dedup.feature` on the fix (online, then offline) and on the parent, with the five module jars, digests and tinkergraph's runtime classpath; the fix's test and feature file on a copy of the parent | 3 CPU, 5G, 35m | pending |

## Signatures

Each case's section has its own table. In short:
- **Good against a project KEYS file:** Apache Commons Compress 1.22 and 1.23.0, Commons RNG 1.2 and 1.3 (core and client-api), with the
  Apache Commons KEYS file (`$O/keys-A/commons-KEYS`, sha256 `f154a693df7d01290487b3bf4c045481cdde6bd310b9eeb37b7a533b03b3299a`).
- **Good, key from keyserver.ubuntu.com with nothing further vouching for it:** jackson-databind 3.0.4, 3.1.1, 3.1.2, 3.2.0 with their
  jackson-core and jackson-annotations; vavr 1.0.1, 1.1.0, vavr-match 1.0.0; RoaringBitmap 1.6.24, 1.6.25; spatial4j 0.8; Checkstyle 10.12.4;
  gdx 1.11.0, 1.12.1, 1.13.0 and gdx-jnigen-loader 2.3.1, 2.5.2.
- **Good but by an expired key, signed before it expired:** agrona 1.3.0 and 1.4.0 (signed 2020-01-21 and 2020-02-26, key expired 2020-08-10).
- **Checked by Central's `.sha1` only:** the Checkstyle 10.12.6, 10.12.7, 10.13.0 and gremlin-core 3.7.3, 3.7.4, 3.8.0 sources jars used for
  the release-side comparisons; spatial4j's five runtime jars (also checked against Central's sha1).
- **Not signed, checked by checksum instead:** the Gradle distributions and wrapper jars (sha256 against services.gradle.org), the pins
  themselves (git commits fetched by SHA).
- **Not signed at all:** M02's four rebuilt snapshot inputs (local builds from pinned commits fetched by SHA; see M02's section).

## Disk

`$O` is 3.0 GB: worktrees 1.1 GB, `m2` 0.7 GB, `gradle-home` 0.4 GB, tools (Gradle distributions) 0.4 GB, `dl` 0.4 GB, release sets 73 MB,
artifacts 15 MB. Inline build trees were deleted after their jars and digests were recorded; the jobs remove theirs. The mirrors under `$M`
hold only the pins (plus earlier setups' pins in the four shared mirrors, and M02's four snapshot-input pins in the new
`jackson-{parent,annotations,bom,core}.git`).

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/merged-pr-links-m01-m10` (`$O`); `source $O/scripts/env.sh` gives `$O`, `$M`, `$W`, `$MVN`,
  `GRADLE_USER_HOME`, `TMPDIR` and the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25`. **The default `java` is 25**: name a JDK by path.
- Both revisions of every case at the brief's pins: `$W/MNN-MIRROR-parent` and `$W/MNN-MIRROR-fix` (full SHAs, trees and parents in
  [Upstream revisions](#upstream-revisions)). Every PR's merge SHA is the brief's after pin, and every after pin's first parent is the before pin.
- Built jars of both sides in `$O/artifacts/` (`MNN-MIRROR-ROLE.jar`), with full sha256s and the changed classes' digests in each case's
  **Artifacts** table, and runtime classpath files beside them; each section ends its Artifacts part with a `java -cp` line. M01–M07 and M09 are
  built; M08 and M10 are built by the two jobs in [Jobs](#jobs), which write the same files.
- The JDK per case: M01 17, M02 17, M03 21, M04 11, M05 8, M06 8, M07 11, M08 17, M09 17, M10 11 (TinkerPop's enforcer refuses 18+).
- Exact build and test commands, online and checked offline, in each case's **Commands**. Gradle runs from `$O/tools/gradle-VERSION`, never
  `gradlew`.
- Release graphs with sources, resolved with strict checksums: `$O/releases/` (jackson-databind 3.0.4, 3.1.1, 3.1.2, 3.2.0; vavr 1.0.1, 1.1.0;
  commons-compress 1.22, 1.23.0; commons-rng-core 1.2, 1.3; RoaringBitmap 1.6.24, 1.6.25; agrona 1.3.0, 1.4.0; spatial4j 0.8; checkstyle
  10.12.4; gdx 1.11.0, 1.12.1, 1.13.0).
- M04's fixture: `$W/M04-commons-compress-fix/src/test/resources/COMPRESS-621.zip`, 217 bytes, sha256
  `198e954c1f2eaf9cf1cf8b7ce991d74ac3a0e2acfa7616dfbf7c8231ee6b20e0`.
- M08's CLI configuration (`Checker → TreeWalker → HiddenField`, default properties): `$O/scripts/M08-cli-check/hidden.xml`; the CLI command is
  in M08's **Commands**.
- M07's issue #210 reproduction: `$O/repro/M07/Main.java` (the issue's `Main` verbatim).

### What was verified on a JVM

- Landed regressions, at both pins (each case's **Landed tests** table, [Summary by case](#summary-by-case)): the fix's tests pass on the fix,
  the parent's own pass on the parent, and the fix's tests fail on the parent: M01 (6), M02 (4 of 5, child value `null`, no exception),
  M03 (2, `expected: Some(null) but was: None`), M05 (1, `IllegalStateException: java.io.EOFException` on restore), M06 (12), M09 (1,
  `IllegalArgumentException: polygons must contain at least 3 points.`). M04's landed test does not compile on the parent (it calls the new
  accessors); with those four lines removed it fails on the parent (`getEntry("COMPRESS-621.txt")` returns null) and passes on the fix.
- M07 has no landed test: the issue's own reproduction throws `JsonGenerationException: Current context not Array but Object` on the parent and
  writes `[{"type":"MultiPoint","coordinates":[[100.0,100.0]]}]` on the fix; the existing GeoJSON/Jackson tests pass at both pins (90/90).
- M08 and M10: pending the jobs. Checkstyle 10.12.4's CLI (= the parent's `HiddenFieldCheck.java`) runs on a setup smoke file.
- Offline builds (`mvn -o`, `gradle --offline`) checked for every inline case.

### What to know before starting

- **M02's snapshot inputs are substitutes.** `jackson-base`/`jackson-bom`/`jackson-core` 3.2.0-SNAPSHOT and `jackson-annotations`/`jackson-parent`
  2.22-SNAPSHOT are no longer served by any snapshot repository; they were rebuilt from their own upstreams at the last branch commit before
  the parent pin (same inputs serve both sides; commits in M02's section's table, digests beside them). Released 3.2.0/2.22 came later and are
  not the inputs. Nothing published equals either pin.
- **Released versions are not the pins.** Byte-equal stand-ins: commons-rng-core 1.2 = parent `JDKRandom.java`; agrona 1.3.0 = parent's four
  maps; gdx 1.12.1 = parent `Intersector.java`, 1.13.0 = fix's; spatial4j 0.8 = parent serializer; Checkstyle 10.12.4 = parent
  `HiddenFieldCheck.java`, 10.12.7 = fix's (not resolved as a graph); jackson-databind 3.1.2 = parent `BeanPropertyMap.java` only. Every other
  release carries other changes.
- **M01:** the built jars say version 1.6.24, but the *released* 1.6.24 is older code; the build's `failFast = true` is turned off by
  `$O/scripts/nofailfast_C.init.gradle` so a run reports every failure. M01's wrapper jar is 8.14.3's, not 9.6.1's (unused).
- **M06:** the build generates `Long*` maps from the `Int*` sources, so the fix also changes `Long2LongHashMap`, `Long2ObjectHashMap` and
  `Object2LongHashMap`.
- **M09:** `:gdx` builds alone only with `--configure-on-demand` (the Android backend needs an SDK) and `-Dmaven.repo.local=$O/mavenlocal-empty`;
  classes are Java 7 bytecode.
- **M05:** the state format differs between pins (the fix adds a 4-byte length); surefire reruns a failing test twice.
- **M08:** `dependency:go-offline` fails on a POM-only `axiom:1.2.15`; the job resolves the rest online first. The CLI exits with the number of
  errors and prints a trailer after the XML: use `-o OUT.xml`. Message text depends on locale.
- **M10:** the build is restricted to `-pl gremlin-core,tinkergraph-gremlin -am`; the classpath file's reactor paths are rewritten to the copied
  jars by `$O/scripts/M10_cp.py`.

### What is left for the domain work on purpose

- Every claim, fixture and history in the brief: none of the brief's public scenarios was run (the brief's own records, bitmaps, iterators,
  ZIP variants, RNG sequences, map arrays, nested GeoJSON, Checkstyle audit files, polygon reuse and Modern-graph traversals).
- Example scaffolding, ids, sidecars, adapters and recipes; the choice of which jar (pin build or release) a claim runs against.
