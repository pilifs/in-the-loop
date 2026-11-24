# Setup for twenty more organic Java PRs (product behaviour)

Mechanical setup for [`organic-java-pr-product-behaviour-20-additional-cases.md`](organic-java-pr-product-behaviour-20-additional-cases.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. **In progress**: this record is
committed as it grows.

The session writes no claims, examples, sidecars, adapters, observers or checker code, and allocates no example ids. It
runs neither the project verifier nor JBMC. Everything fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/organic-pr-20`, and `$M` is `~/.cache/in-the-loop/git-mirrors`. JDKs are Temurin,
under `~/.sdkman/candidates/java/`: `8.0.512.0+9-tem`, `11.0.33.0+10-tem`, `17.0.21.0+9-tem`, `21.0.13.0+9-tem`
(the brief's preflight JDK), `25.0.5.0+8-tem`. **The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its
full path. Maven 3.10.0 is on `PATH`. Maven builds take `-s $O/maven-settings.xml` (local repository `$O/m2`);
Gradle builds take `GRADLE_USER_HOME=$O/gradle-home`. `$O/toolchains.xml` names JDKs 8, 11, 17, 21 and 25.

## Starting commit

Checkout at setup: `e51ef46de6eeab3bdddeaadb3bea7614d049edab` ("Merge the single-agent run organic-pr-composition-fast-follow into the line").

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds only the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA
from each project's GitHub repository (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`). There is one worktree per
revision, `$O/worktrees/CASE-MIRROR-ROLE`. Trees and parents were read from the commit objects
(`$O/logs/pins-resolved.tsv`). **Every fix's first parent is the brief's parent.** Every PR is merged, and its
`merge_commit_sha` (from `gh api`, `$O/upstream/prs/CASE-REPO-N.json`) equals the brief's fix revision. Diffstats
are in `$O/logs/pr-diffstats.txt`.

| Case | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|
| J01 | `J01-commonmark-java-parent` | `9926b761eb2e9192d80cda46917ea2f0f0f2c7dc` | `531c7475c0a1a9108d6e8db05728344a6c6b449b` | `3c151053d720c99372d2d4c5c6db667135563ecf` | 2025-08-01 | README: Bump version |
| J01 | `J01-commonmark-java-fix` | `4ad81e449ca474d3560a1699f9882e37090906f0` | `19f580e77b01a1f290a0d4dd9759b18a3bd93627` | `9926b761eb2e9192d80cda46917ea2f0f0f2c7dc` `77cadac10faa5cdccf0c8b4c0205d486d648f572` | 2025-09-11 | Merge pull request #401 from rdestefa/issue-398-alt-text-code |
| J02 | `J02-jsoup-parent` | `cc90f726cd721ad2c19cbd27997482a5f9b8a7ae` | `d4ff489fac91d4d10e84e8e4954aa016e209cd63` | `f2128717794737bb644e6e186de50b109d2c7349` | 2025-11-13 | Support parsing custom void tags |
| J02 | `J02-jsoup-fix` | `bcbac427ff4bca1748f8eb5125a23d4c739b75e9` | `08163159af95fac35553239b8e18c4368915dab1` | `cc90f726cd721ad2c19cbd27997482a5f9b8a7ae` | 2025-11-13 | Fix #2422 - Cloned Parser does not reuse TagSet from original (#2423) |
| J03 | `J03-jfreechart-parent` | `4e196e9bf170ae8af9bc4760a2329b3d933acccc` | `886adc0f44268f8640e051a3ff697804855fb3fb` | `da3f416b9129461089a67340bec45e5cfbab1dc7` | 2017-02-22 | Add code to update crosshairs - one last update. |
| J03 | `J03-jfreechart-fix` | `f68f7248a4145828dfa36fc2f76924db3c543162` | `c0c7b2a10974447a3bd9934b9ec207ff2574c909` | `4e196e9bf170ae8af9bc4760a2329b3d933acccc` `071d2473dfdd807e13f3bfd4e5957093d5784090` | 2017-02-24 | Merge pull request #44 from SubliminalTitan/master |
| J04 | `J04-ical4j-parent` | `70955862e728ff5c7392f5d53ed5b27461de6202` | `e1f30bcac83163efc12cce8aca8d69a76dd54486` | `14d817bfba73c1c663c5cd33314b1b1f14ebfacb` `28cfb2dc3e645d19fc7432870babdccf57a3e65f` | 2026-10-28 | Merge pull request #946 from Shrusti-pk/relaxed-duration-regex-linear |
| J04 | `J04-ical4j-fix` | `1342406adcf9f0576a7e4fa60548eea73f58c5e5` | `3c8b09c0030a5941f3562d8fd64a3a46b5103b46` | `70955862e728ff5c7392f5d53ed5b27461de6202` `22f7600bd1ee247693c3fa7c6fbc340e8f85a48c` | 2026-10-28 | Merge pull request #960 from wleeaf/recur-default-wkst-monday |
| J05 | `J05-poi-parent` | `72ad1d5e111c2cd00c4842a0431eb1d9ca4b605c` | `7dbcc020745a5c8aad4214e1321ce5bda8934341` | `20e581f66a37c8a1b1456cb4c0c0ce3ae134f88c` | 2026-11-21 | Update poi-ooxml-full version to 6.0.0 |
| J05 | `J05-poi-fix` | `c94ee8ad9096bdb8cf8e5e59d8d12432e950dbf3` | `cb46cadc2a5b073896dfebc30b0826996af9750e` | `72ad1d5e111c2cd00c4842a0431eb1d9ca4b605c` | 2026-11-21 | XSSF: fix re-adding a removed hyperlink, splitting a hyperlink range a |
| J06 | `J06-zip4j-parent` | `f2e4a5a4f762dab1593f97f34c2b45d599a286cf` | `6a4d7b7f9c6f3fd89d106154bf4f11e67c690ac8` | `7b7bae9f03be4b531e26c33a053684c08f5aec35` | 2026-02-12 | Document how to add an empty folder via ZipOutputStream (#552) |
| J06 | `J06-zip4j-fix` | `6d1678bdf03e6eafadebef9a860e74488485fe65` | `b3509f6a02b092f7db092fbc834936a962eca668` | `f2e4a5a4f762dab1593f97f34c2b45d599a286cf` | 2026-02-12 | Fix renaming when file names start with the same name than the file to |
| J07 | `J07-commons-compress-parent` | `3d9a01ec07aa18b5ff341766378e2ea62639d4f5` | `f0fa814b360668b21ef05a5684535f56afa2ea3e` | `363d2553c34624f8078da7d04220a505b4af9c40` | 2024-01-11 | Javadoc |
| J07 | `J07-commons-compress-fix` | `45023ddcc43e13804dff799ae96f2acce14ce3cd` | `44c207787c0360431cd7d44a83404e28258fbd7e` | `3d9a01ec07aa18b5ff341766378e2ea62639d4f5` | 2024-01-11 | [COMPRESS-655] Fix TAR directory entries being misinterpreted as files |
| J08 | `J08-parquet-java-parent` | `5c360ff5d879d3567f23cea3290894712fb336d9` | `fdca60b7968396b96ac09362e2a90ccfc0064036` | `2a87957256bc193438fd6ec7742dbfc9883d99bf` | 2026-07-14 | GH-3659: Throw IAE when dealing with odd-length/invalid hex string in  |
| J08 | `J08-parquet-java-fix` | `5e14d7cd43403a95d331be8791e8792dbf38683d` | `4005c46207142ab7b0c19de2711fc2114e0414e4` | `5c360ff5d879d3567f23cea3290894712fb336d9` | 2026-07-14 | GH-3637: Fix corrupt output when reusing a dictionary writer across ro |
| J09 | `J09-sqlite-jdbc-parent` | `d36de443c9004ac1eb34f00ceb51c46eeaeafb0e` | `d94269c7168ae13bed24b6571074d504d1b31e82` | `ecabeace781e6cf20e23990447f01d37e23aa485` `fb3d9ff516aa5e082be038d4f6cac8f573714c08` | 2016-06-22 | Merge pull request #125 from xerial/no_src |
| J09 | `J09-sqlite-jdbc-fix` | `44848544c11e3705ee6b208d844a067ffb535012` | `53b93e72989de1c2b44dcd1fe0889513fa3e4c63` | `d36de443c9004ac1eb34f00ceb51c46eeaeafb0e` `231d092bec1fb43df4f28d6eee8925e5a92abbd9` | 2016-06-22 | Merge pull request #126 from archiecobbs/master |
| J10 | `J10-kryo-parent` | `7a433cf0036101c6693cca6b4410454e211dbd6c` | `3974c4a4e7de0d60d94f95f79a4afbfbbbd976d2` | `2f8b3fd39a30a0c1af8091767b3c6282e06fae35` | 2017-07-24 | Update README for release 4.0.1, add compat report |
| J10 | `J10-kryo-fix` | `73540094596bef8874a48726edd0fdd014e84e45` | `e8d2ce2a44636a12e69a15e79f8c6e7248889b69` | `7a433cf0036101c6693cca6b4410454e211dbd6c` `033d659a118d7206dfa8d9c605bcec601c46f116` | 2017-08-12 | Merge pull request #530 from magro/fix-529-serialize-Enum-class |
| J11 | `J11-h2database-parent` | `df37ff0363c0b84758017c8788e313d34646d403` | `6dcf3b6f119ebda4a3de2a8354a75c9c61b27586` | `14fc381e67c6e044c5112b5fdd847fc24b21ed6c` `345d9208853b3a60828be9764b70f371c21942be` | 2026-11-16 | Merge pull request #4579 from lakxtxue/codex/fix-large-page-read |
| J11 | `J11-h2database-fix` | `2b7812b20a421be7116cc75b5abf95a5718f7119` | `8ac9694ec51f473b37207b4125fec29e1bbc62f2` | `df37ff0363c0b84758017c8788e313d34646d403` `4c567633c7414e38161c28ae05ed5392620a5215` | 2026-11-17 | Merge pull request #4575 from Twiink/fix/external-sort-row-values |
| J12 | `J12-calcite-parent` | `f2638b9f7dc878f3f109cbc59d1a6ae02d3d5696` | `fa9eada7522d66f63b6d77b724b4c31b82ee85ed` | `c3fa21b805edf5be79ef4a4992d7b5213488cbaa` | 2019-03-07 | Switch from maven:alpine to maven image for generating javadoc when bu |
| J12 | `J12-calcite-fix` | `f992e6c8fbc3712c6bd70096fb6b05da448b2cab` | `634c8f0fefc47d08da3aa1cf5b0508f3694e61d1` | `f2638b9f7dc878f3f109cbc59d1a6ae02d3d5696` | 2019-03-07 | [CALCITE-2785] In EnumerableAggregate, wrong result produced if there  |
| J13 | `J13-maven-parent` | `c7b164f76189be25a2c6a48ffe74ff3afc39fcc2` | `769dc44869b6b7f4d655390135eb803646b69e3c` | `d8a19432e65de66d990ee07cd752c7935b82685e` | 2026-09-14 | [MNG-8547] Expose repository events through the Maven API |
| J13 | `J13-maven-fix` | `9da38851f517281d66b1b05d25b8785dcc9e7fc9` | `fbc5aa25dc7892ced9b6f28555a251a61b43c5b6` | `c7b164f76189be25a2c6a48ffe74ff3afc39fcc2` | 2026-09-14 | [MNG-6568] Fix comparison cycles in version qualifiers (#13102) |
| J14 | `J14-lucene-parent` | `182ee9c4cc3bc52ace12e699248b750377a3aa2f` | `4752063348a2900ec879136c7e39c00659d53610` | `249ea75bb682ac904ad424d22b9844a49d04a8fd` | 2026-03-02 | fix failing TestHnswFloatVectorGraph test (#15791) |
| J14 | `J14-lucene-fix` | `167503f6d84d8e43db4ec6ae3baf17337290393f` | `960a3171eee14e937579bad793c8747ff74dc6af` | `182ee9c4cc3bc52ace12e699248b750377a3aa2f` | 2026-03-03 | Fix incorrect handling of missing values in ToParentBlockJoinSortField |
| J15 | `J15-spring-batch-parent` | `1b35bff3ec0a681827e507562572f14550a6717f` | `f382e58e7d78d35d9f45b206f073deb074a70a0e` | `dacfe0b350df867122270e4e2670b0d115028ac2` | 2017-07-12 | BATCH-2630 - Infinite loop on job restart when step was repeated Bug f |
| J15 | `J15-spring-batch-fix` | `0506d3793e50a606cd9739ce896de5d80b474e8e` | `4f819ac95e4dec5572535f2e30e95646f0ec84cb` | `1b35bff3ec0a681827e507562572f14550a6717f` | 2017-07-12 | BATCH-2630 - update not to rely on step execution order from DAO |
| J16 | `J16-jgrapht-parent` | `c01e02903d45c82a9ecaf5c4329cdf847eb9e183` | `b995902a8f4373a2cb7298781654e3e23ace3e0b` | `15c5b26f0d2b2d0256b723095bb98ebff43372e8` `1614b78e0dadf9eb001dfa250a3da1effd2f3f1a` | 2020-06-05 | Merge branch 'master' of https://github.com/jgrapht/jgrapht |
| J16 | `J16-jgrapht-fix` | `637503d4ebfbce3bb1ffca97348a90e856f4346e` | `e69fcb7423524b093f484f94a72ed766e9bf2d9f` | `c01e02903d45c82a9ecaf5c4329cdf847eb9e183` | 2020-06-06 | Fixed silently ignored error (#941) |
| J17 | `J17-eclipse-collections-parent` | `9084111e068612ebf817a3fa6fe80d9623df4c29` | `d9ddafabab4a0b53c6c3a9dc58dd0e6b994a0c4a` | `876191ca03c2b987fd401c3ef3e45c6042cada2a` `34415feb3e702efb6b493b72b5479674617056c6` | 2020-01-09 | Merge pull request #781 from LarsEckart/update-gradle-usage-in-readme |
| J17 | `J17-eclipse-collections-fix` | `7ce7a19722e5471a71a2799737c3c2a0ed5510ff` | `7b092f2fe68933162f4dd7023a27ec799a108d32` | `9084111e068612ebf817a3fa6fe80d9623df4c29` `1596cfef0f66556cd3740f61722a2fc8c1a57cb8` | 2020-01-15 | Fix Bug #677 - Optimize removeIf() for UnifiedMap. (#786) |
| J18 | `J18-caffeine-parent` | `5473cab8afb17ec7aa288b57d74d81de6372351e` | `6bff58fe1f86318186dc97466de3947be88db886` | `3116a8b3b0daaa34fd9f153e1dfc37087aa594f9` | 2017-10-08 | Fix JDK9 build |
| J18 | `J18-caffeine-fix` | `78be027a7e89e750e3a1cc27584d7a8224d164bf` | `114102086c5fa91eefb1c1132ca31a46e66c5709` | `5473cab8afb17ec7aa288b57d74d81de6372351e` | 2017-10-25 | Allow configuration of max size and exiry simultaneously for JCache |
| J19 | `J19-resilience4j-parent` | `4e564affebf280ba20880bdc8736b42f8f92234a` | `d06a8b6d6d8f4947ad7dc30884c8f933705469d7` | `755089cd2508dfda948f4cfa211324de89c85dd3` | 2020-03-02 | Delete rudundant library version (#894) |
| J19 | `J19-resilience4j-fix` | `4ecc7c889cad7bfa6cb574af52252480f7e0d7cf` | `620629052e50e5d2feafff1c410846e513045344` | `4e564affebf280ba20880bdc8736b42f8f92234a` | 2020-03-02 | Issue #891: Make Circuit Breaker state transition calls idempotent (#8 |
| J20 | `J20-micrometer-parent` | `41c9493e7f6781f4588906ed36cca87385a5a76c` | `05b1b6d2861e310b1008cf9db9e414a54ca280dd` | `fc2d99cb3a1d980115d1c57eae49f5b48201c196` | 2022-08-23 | Polish (#3368) |
| J20 | `J20-micrometer-fix` | `f18f09fa8d782a39081856f9667827ae00af638a` | `71733254d5eb4b20c4933d216fcd6bdc330c5332` | `41c9493e7f6781f4588906ed36cca87385a5a76c` | 2022-08-24 | signalfx: add tests for emiting percentile and histograms, fix timer ( |

Remarks:
- **J15 Spring Batch #495 is two commits**, merged by rebase onto `3.0.x`: `1b35bff3ec0a681827e507562572f14550a6717f`
  ("Infinite loop on job restart when step was repeated") and `0506d3793e50a606cd9739ce896de5d80b474e8e` ("update not to
  rely on step execution order from DAO"). The brief's pair is the second commit alone; its parent is the PR's first commit.
- No test file changed in J03 (JFreeChart), J06 (Zip4j), J15 (Spring Batch) or J16 (JGraphT): the brief links the changed
  implementation for them. There is no landed test to run on both sides.
- J09 (SQLite JDBC) changes `NativeDB.c` and the bundled Mac binaries; J07 adds the test archive `orjson-3.7.8.tar`.

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` | the same installations as the earlier setups |
| Maven 3.10.0 | on `PATH` | used for every Maven build except Calcite |
| Maven 3.5.4 (Calcite's wrapper version) | `$O/tools/apache-maven-3.5.4` | zip sha256 `6aaa1bee0be0e3a64b3303df0afb36e4bb69922fe46d43b32615796d671a4275`; Central `.sha1` and archive.apache.org `.sha512` match; signature in [Signatures](#signatures) |
| Gradle 4.2.1 (Caffeine) | `$O/tools/gradle-4.2.1` | zip sha256 `b551cc04f2ca51c78dd14edb060621f0e5439bdfafa6fd167032a09ac708fbc0` = services.gradle.org's |
| Gradle 5.3.1 (Resilience4j) | `$O/tools/gradle-5.3.1` | zip sha256 `1c59a17a054e9c82f0dd881871c9646e943ec4c71dd52ebc6137d17f82337436` = published |
| Gradle 7.5.1 (Micrometer) | `$O/tools/gradle-7.5.1` | zip sha256 `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4` = published |
| Gradle 8.5 (ical4j) | `$O/tools/gradle-8.5` | zip sha256 `9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026` = published |
| Gradle 9.3.1 (Lucene) | `$O/tools/gradle-9.3.1` and the wrapper's copy in `$O/gradle-home/wrapper/dists/gradle-9.3.1-bin/` (identical, `diff -r`) | zip sha256 `b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06` = published; wrapper jar `$O/dl/gradle/lucene-gradle-wrapper-9.3.1.jar` `b3a875ddc1f044746e1b1a55f645584505f4a10438c1afea9f15e92a7c42ec13` = published |
| Gradle 9.9.1 (POI) | wrapper's copy in `$O/gradle-home/wrapper/dists/gradle-9.9.1-bin/dol8b552jwt4yhd7ihm3iahwb/` | zip sha256 `d8a18a7a841dd5df825d35a685fad6f2d7f12ac0c280e57b67c27b4a520ba228` = published; POI's wrapper jar `621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8` = published |
| SQLite 3.9.1 amalgamation (J09 native) | `$O/dl/sqlite-3.9.1/sqlite-amalgamation-3090100.zip` | zip sha256 `5e25da9f46d6a7b2a378d26c5069b1efec0b5d1707376d9c34b4f24c329bd74e`; `sqlite3.c` SHA1 `5e6d1873a32d82c2cf8581f143649940cac8ae49` = sqlite.org's release log |
| gcc 15.2.0 | system | J09 native build only, with `-fpermissive` |

Caches and files this work owns:
- `$O/m2`, the Maven local repository named by `$O/maven-settings.xml`. `$O/scripts/maven-settings-https-central.xml` is the same
  repository with an https mirror of `central`, for Calcite.
- `$O/gradle-home`, the `GRADLE_USER_HOME`. `$O/scripts/resolve-all.init.gradle` is a setup-only init script (POI resolution).
- `$O/toolchains.xml`: JDKs 8, 11, 17, 21, 25.
- `$O/gnupg`, the keyring of the signature pass; its agent was stopped.
- `$O/releases/NAME/`: each release graph the brief names, with `lib/`, `sources/`, `tree.txt` and an ordered `classpath.txt`,
  resolved by `$O/scripts/resolve.sh` with `--strict-checksums` from Maven Central. `*-testdeps` and `J17-test-support` are
  test libraries for overlay test runs only.
- `$O/artifacts/`: every built and overlay jar. `$O/overlays/JNN/{parent,fix}/`: overlay sources and classes.
- `$O/probes/JNN/`: throwaway setup probes (not case artifacts), output in `$O/logs/JNN-probe*.txt`.
- `$O/notes/JNN.md`: the per-case sections below, as the setup wrote them.
- Scripts in `$O/scripts/`: `overlay_b.sh`, `overlay_c.sh`, `overlay_D.sh` (overlay compiles), `overlay_test_c.sh`,
  `j08_overlay_test.sh`, `j09_querytest.sh`, `junit_summary.py`, `submit_{B,C,D}.py` (the jobs), `forkA-env.sh`.

`forkA-env.sh` defines what the J01, J02, J03, J06 and J10 commands use: `$J8`, `$J17` (JDK paths),
`$MVN` = `mvn -B -s $O/maven-settings.xml -Daether.syncContext.named.factory=file-lock -Daether.syncContext.named.nameMapper=file-gav`,
and `$SK` (skips report and lint plugins only: rat, japicmp, javadoc, checkstyle and so on; nothing compiled changes).

**Overlays** put the overlay jar first and the release's `classpath.txt` after it:
`java -cp $O/artifacts/JNN-REPO-ROLE-overlay.jar:$(cat $O/releases/NAME/classpath.txt) ...`. Overlay jars are built with
fixed entry dates and rebuild identically; jars from upstream builds carry build timestamps (bind the copies in
`$O/artifacts/` or the class digests).

## Summary by case

"Release side" says which side of the PR the named release's changed source equals: an overlay run of that side is then
the release itself. "Landed test" is fix / parent's own / fix's test on the parent.

| Case | Evidence built | Release side | Landed test | Setup probe of the brief's observation | Upstream build |
|---|---|---|---|---|---|
| J01 CommonMark | source build, both sides | — | 26/26, 24/24, **1 fails** | — (landed test is the `foo bar` case) | inline |
| J02 jsoup | source build | — | 6/6, 5/5, **1 fails** | — | inline |
| J03 JFreeChart | source build (`maven/pom-1.6.xml`, 1.0.20) | — | none (no test changed) | matches | inline |
| J04 ical4j | overlay over 4.4.0 | parent | 94/94, 91/91, **3 fail** | — | inline (Gradle 8.5) |
| J05 POI | overlay over 6.0.0 (+ `ArrayFormulaRanges`) | **fix** (6.0.0 behaves like the fix) | job | matches | job |
| J06 Zip4j | source build | — | none | matches | inline |
| J07 Commons Compress | overlay over 1.26.0, and source build | **fix** | 25/25, 24/24, **1 fails** | matches | inline |
| J08 Parquet | overlay over 1.18.2 (+ unshaded fastutil) | **fix** | overlay run: 24/24, 22/22, **2 fail** | — | not possible (`thrift` 0.23.0 binary) |
| J09 SQLite JDBC | release pair 3.8.11.2 / 3.14.2; native rebuilt at both pins | — | rebuilt native: 10/10, 7/7, **1 error** | matches (releases and pins) | inline |
| J10 Kryo | overlay over 4.0.2, and source build | **fix** | 23/23, 23/23, **1 error** | — | inline |
| J11 H2 | overlay over 2.5.252, and source build | parent | pass, pass, **fails** (`main` run) | matches | inline |
| J12 Calcite | release pair 1.18.0 / 1.19.0; PR pair by job | (1.19.0 has the PR) | job | matches (releases) | job |
| J13 Maven | overlay over 3.9.12 (two variants), and `maven-artifact` build | parent | 57/57, 44/44, **11 failures, 1 error** | matches | inline |
| J14 Lucene | overlay over 10.4.0 | parent | overlay run: 7/7, 4/4, fix tests don't compile on the parent | matches | job |
| J15 Spring Batch | overlay over 3.0.7.RELEASE | neither (3.0.7 predates the PR) | none | matches | not possible (repo.spring.io 401) |
| J16 JGraphT | overlay over 1.5.1 | fix (copyright and formatting differ) | none | matches, both assertion profiles | not attempted (none needed) |
| J17 Eclipse Collections | overlay over 10.2.0 | **fix** | overlay run: 960 pass in every combination (preservation) | — | job |
| J18 Caffeine | overlay over jcache 2.6.1 + cache-api 1.0.0 | neither | overlay run: 2/2, (new test), **`expiry` fails** | — | not possible (repo.spring.io 405, TestNG 6.12 gone) |
| J19 Resilience4j | overlay over 1.3.1 | neither | overlay run: 27/27, 25/25, **3 fail** | — | not possible (plugin deps gone) |
| J20 Micrometer | overlay over 1.10.0 | **fix** | overlay run: 20/20, 12/12, **2 fail** | — | not possible (repo.spring.io 401) |

## Cases

Each section was written as the case was set up; the files are also in `$O/notes/JNN.md`.

### J01 · CommonMark Java #401 (pinned source build)

- **Build**: Maven 3.10.0 on JDK 17.0.21 (`<release>11</release>` in the parent POM; class files major 55), reactor `-pl commonmark -am`
  (core plus `commonmark-test-util`). The project's Maven wrapper names 3.6.3; it was not needed.
- **Artifacts** (`commonmark-0.25.2-SNAPSHOT.jar`, from the online fix build and the offline parent build):

| Jar | sha256 |
|---|---|
| `$O/artifacts/J01-commonmark-java-parent.jar` | `0ee38218fe053e0d09792e8ff303302ca463bd18beb7935791cc8f03ba1fe692` |
| `$O/artifacts/J01-commonmark-java-fix.jar` | `fd324d38b519a0314affeee506c2e46667aa4325513519538722b340a2e1e276` |

- Changed production file: `CoreHtmlNodeRenderer.java` (adds `visit(Code)` to the private `AltTextVisitor`).
  - `org/commonmark/renderer/html/CoreHtmlNodeRenderer.class`: `55901518068c3a2d21090e40e0c45c2edcf7902fd6bd09746316748c9d4998f7` on **both** sides.
  - `org/commonmark/renderer/html/CoreHtmlNodeRenderer$AltTextVisitor.class`: parent `b9954ebc7d196b93af1c1d734a4be909384eab09db562bf667589112b077b074`, fix `d4a37a582040e3b4d1bc577d4839f960f30f41ad359b4002d935ea32b672a07b`.
  - The jar carries its resource `org/commonmark/internal/util/entities.txt`.
- **Runtime classpath**: none. `commonmark/pom.xml` declares only test-scope dependencies (`commonmark-test-util`, `jmh-core`, `jmh-generator-annprocess`).
- **Landed test** `HtmlRendererTest` (logs `$O/logs/J01-commonmark-java-{fix,parent}.*.log`):

| fix | parent's own | fix's file on the parent |
|---|---|---|
| 26/26 pass | 24/24 pass | **1 failure of 26**: `imageAltTextWithCode` (line 289): expected `<p><img src="/url" alt="foo bar" /></p>`, was `<p><img src="/url" alt=" bar" /></p>` |

- **Commands** (each ~12 s; online first, then offline worked on both sides):
  ```bash
  . $O/scripts/forkA-env.sh   # defines $MVN, $SK, $J17, $CAP; see the file
  cd $O/worktrees/J01-commonmark-java-fix && JAVA_HOME=$J17 $MVN $SK -o -pl commonmark -am -Dtest=HtmlRendererTest package   # jar: commonmark/target/commonmark-0.25.2-SNAPSHOT.jar
  ```
- **For the domain agent**: no probe was written; the landed test covers the `foo bar` observation. The brief's `x & y`
  observation was not checked by the setup. Rebuilt jars differ only in `META-INF/MANIFEST.MF`; bind the copies above or the class digests.

### J02 · jsoup #2423 (pinned source build)

- **Build**: Maven 3.10.0 on JDK 17.0.21 (class files major 52, multi-release jar), whole project.
- **Artifacts** (`jsoup-1.22.1-SNAPSHOT.jar`):

| Jar | sha256 |
|---|---|
| `$O/artifacts/J02-jsoup-parent.jar` | `2bf97969f0b08206ada0e17bda915cd43ed024469eb539ecadf98f726caf5dc7` |
| `$O/artifacts/J02-jsoup-fix.jar` | `d0e625c39117cd090b7db2b701f77d67095df9ffbe782ede18b1c9479c445ddd` |

| Class | parent | fix |
|---|---|---|
| `org/jsoup/parser/Parser.class` | `7281843adc3742741a2bfe7bbb08b3a3c6556d70880a28fcc9ce9ad401aa7861` | `7fe8738992a1ac0054eed14afd95e5d0e08000b66513cdd0216aa26d305cd9fb` |
| `org/jsoup/parser/TagSet.class` | `9a9eb1a453fead787d02d5b23cdcb610eaa1d929d589b939edafb3ea3a3ecfc5` | `ce6b41068c1117063263b3445608e3c602eea16115ca2e5f93089a8f050b23e3` |

  The change: the `Parser` copy constructor adds `tagSet = new TagSet(copy.tagSet());`, and `TagSet(TagSet)` copies the original's `customizers`.
- **Runtime classpath** (`$O/logs/J02-jsoup-fix.runtime-classpath.txt`): `$O/m2/com/google/re2j/re2j/1.8/re2j-1.8.jar`, which the POM marks
  `optional`; jspecify is `provided`. jsoup itself needs nothing else to parse.
- **Landed test** `ParserTest`:

| fix | parent's own | fix's file on the parent |
|---|---|---|
| 6/6 pass | 5/5 pass | **1 failure of 6**: `testCloneCopyTagSet` (line 93, `expected: not <null>`) |

- **Commands** (~12 s each; online, then offline on both sides):
  ```bash
  cd $O/worktrees/J02-jsoup-fix && JAVA_HOME=$J17 $MVN $SK -o -Dtest=ParserTest package   # jar: target/jsoup-1.22.1-SNAPSHOT.jar
  ```
- **For the domain agent**: no probe; the brief's `<foo>one<span>two</span>after` tree shapes were not checked by the setup
  beyond the landed test. Rebuilds differ only in `META-INF/MANIFEST.MF`.

### J03 · JFreeChart #44 (pinned source build, non-JavaFX profile)

- **Build**: the root `pom.xml` (version 1.5.0) compiles `org/jfree/chart/fx/**`, which needs JavaFX, absent from Temurin 8.
  The pinned `maven/pom-1.6.xml` (version 1.0.20) is the non-JavaFX build; its `maven/README.txt` says to copy it over the
  root POM. Instead of changing the tracked POM, the setup copied it byte for byte to an **untracked** file in each worktree,
  `pom-1.6-setup.xml` (sha256 `9272df9b3568b7f71d1d27a12b93735c7e68f0e4244407d9c4fcaf53780c87b8`, the same at both revisions), and ran `mvn -f pom-1.6-setup.xml`.
  It excludes `org/jfree/chart/demo/**` and `org/jfree/chart/fx/**`. Maven 3.10.0 on **JDK 8** (source/target 1.6, class files major 50).
- **Artifacts** (`jfreechart-1.0.20.jar`, 0 `fx` entries, 90 non-class resources):

| Jar | sha256 |
|---|---|
| `$O/artifacts/J03-jfreechart-parent.jar` | `4217fcf98cdb3748bb6f390062b793e21a854ba6dc47fe845a2a9a806c8e2dc7` |
| `$O/artifacts/J03-jfreechart-fix.jar` | `169195472bc4e8daad04d04bfd844bf5ffdc3a96c2286df1519953e50989274f` |

  `org/jfree/chart/plot/XYPlot.class`: parent `285514d3d3da0b5ca31a8eb33b6f9a60beff1d447cc263ffd0efcb2212bed2d5`, fix `f0498f8b6720ab21d5058501808c84e8a473121f89f5c548380dcdf6af2370cd`.
  The change: in `panDomainAxes` and `panRangeAxes`, `percent = -percent` (which mutated the loop variable for later axes) became `axis.pan(axis.isInverted() ? -percent : percent)`.
- **Runtime classpath** (`$O/logs/J03-jfreechart-fix.runtime-classpath.txt`, in order): `$O/m2/org/jfree/jcommon/1.0.24/jcommon-1.0.24.jar`,
  `$O/m2/org/jfree/jfreesvg/3.2/jfreesvg-3.2.jar`, `$O/m2/com/orsonpdf/orsonpdf/1.7/orsonpdf-1.7.jar` (servlet-api 2.5 is `provided`).
  JCommon's sha1 `d5016f7703896c38f9e511f8a9edda2585cbac8b` matches Central's `.sha1`, and its sha256 `13e2596044935f76694cce65a22d1df908907ddcba0da2b49ff030930262d417` equals the repository's own `lib/jcommon-1.0.24.jar`.
- **No landed test.** The build ran `XYPlotTest` as a smoke check: 44/44 pass on both sides.
- **Probe** (`$O/probes/J03/PanProbe.java`, JDK 21.0.13, headless; output `$O/logs/J03-probe.txt`): two `NumberAxis` domain axes at `[0,10]`, the first inverted,
  `setDomainPannable(true)`, `panDomainAxes(0.1, null, null)` then `panDomainAxes(-0.1, null, null)`:

| | after +0.1 first / second | after −0.1 first / second |
|---|---|---|
| parent | `[-1.0,9.0]` / `[-1.0,9.0]` | `[0.0,10.0]` / `[0.0,10.0]` |
| fix | `[-1.0,9.0]` / **`[1.0,11.0]`** | `[0.0,10.0]` / `[0.0,10.0]` |

  This is the brief's statement.
- **Commands** (~10 s each; online, then offline on both sides):
  ```bash
  cd $O/worktrees/J03-jfreechart-fix && cp maven/pom-1.6.xml pom-1.6-setup.xml && \
    JAVA_HOME=$J8 $MVN $SK -o -f pom-1.6-setup.xml -Dtest=XYPlotTest package   # jar: target/jfreechart-1.0.20.jar; remove pom-1.6-setup.xml afterwards
  ```
- **For the domain agent**: the built artifact is **1.0.20 from `maven/pom-1.6.xml`**, not the root POM's 1.5.0 (which needs JavaFX). The
  range-axis path, swapped axis order and the no-inverted-axis control were not probed. The fix jar rebuilt offline was byte-identical to the online copy.

### J04 · ical4j #960 — ByDayRule default WKST (overlay over ical4j 4.4.0; upstream Gradle build ran inline)

**Pins.** Parent `70955862e728ff5c7392f5d53ed5b27461de6202`, fix `1342406adcf9f0576a7e4fa60548eea73f58c5e5` (a merge; first parent = the brief's parent).
Changed: `src/main/java/net/fortuna/ical4j/transform/recurrence/ByDayRule.java` and the Spock spec `src/test/groovy/net/fortuna/ical4j/model/RecurSpec.groovy`.
The build declares Java 11 source/target.

**Release set** (`$O/scripts/resolve.sh`, strict checksums; every jar's Central `.sha1` matches; the PGP pass is the main session's).
`org.mnode.ical4j:ical4j:4.4.0` exists on Central under that coordinate. `jspecify-1.0.0` is **compile-only**: `ByDayRule`
imports `org.jspecify.annotations.Nullable`, and ical4j's own build has `compileOnly libs.jspecify` (1.0.0, `gradle/libs.versions.toml`); it is
not on the runtime classpath.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `ical4j-4.4.0` | `ical4j-4.4.0.jar` | `f4cac5c4a16d8c0f2228ad0e3221b90d069ae0efea73402b51888468e86405f9` |
|  | `slf4j-api-2.0.12.jar` | `a79502b8abdfbd722846a27691226a4088682d6d35654f9b80e2a9ccacf7ed47` |
|  | `commons-codec-1.17.0.jar` | `f700de80ac270d0344fdea7468201d8b9c805e5c648331c3619f2ee067ccfc59` |
|  | `commons-lang3-3.18.0.jar` | `4eeeae8d20c078abb64b015ec158add383ac581571cddc45c68f0c9ae0230720` |
|  | `threeten-extra-1.8.0.jar` | `51e4d21edc4e9447f7760c050e0baee75d7d973f387ba605a17abdc4d24fd6d8` |
| `jspecify-1.0.0` | `jspecify-1.0.0.jar` | `1fad6e6be7557781e4d33729d49ae1cdc8fdda6fe477bb0cc68ce351eafdfbab` |

Runtime classpath (order): `$O/releases/ical4j-4.4.0/classpath.txt` (ical4j, slf4j-api 2.0.12, commons-codec 1.17.0, commons-lang3 3.18.0, threeten-extra 1.8.0).

**Which side 4.4.0 is on.** `ByDayRule.java` in `ical4j-4.4.0-sources.jar` is byte-identical to the **parent**
(`f37069e2c5661505a3180b3874565aa02a2981d9117092ed4736edac50871b21`); the fix's file is `5e60a1d64055b18eb5ded9c6a6de4e5b93be739337c375ec6bd0ed110ffed6cd`.

**Overlay** (`$O/scripts/overlay_c.sh`): javac 17.0.21 `--release 11`, over the release classpath plus jspecify (compile only).
Classes in `$O/overlays/J04/{parent,fix}/classes`, sources copied to `.../src`. Jars (fixed entry dates, rebuilt twice with the same digest):
- `$O/artifacts/J04-ical4j-parent-overlay.jar`: `de821a3aa2a4237a9d086c22d2308de855419eac5480be27308c4235b69b70a2`
- `$O/artifacts/J04-ical4j-fix-overlay.jar`: `1c0ecf4427b96c016a9b4ae1fb19aa4582a36f0d229a3f10c70d43e130eac46b`

| Class | parent overlay | fix overlay |
|---|---|---|
| `net/fortuna/ical4j/transform/recurrence/ByDayRule$1.class` | `e86034a8a3238c021f5f8aa8ff767a6911b8f9695de1528e37e82b11a97a0a0e` | `2de57b5760eb59e2fe40d04d4c202bc0351b5896cdf4f4a6eab22fc368a5e052` |
| `net/fortuna/ical4j/transform/recurrence/ByDayRule$LimitFilter.class` | `a76a2d1c7add684a0b086bef3850696dc0d67b3c2ee8b606ece71e3c41170923` | `77ff395931ee0bffb51346237d6fedbb1d00fb646df5c577b70759ca745e0a2c` |
| `net/fortuna/ical4j/transform/recurrence/ByDayRule$MonthlyExpansionFilter.class` | `b00d9248679df48474d53388e4157c225005f86e929255a491401dd689644ce2` | `c1d752ec1e5b1e14c1a29cff3bc2a2736a14c2ab2de6b01ecfccc664af67da07` |
| `net/fortuna/ical4j/transform/recurrence/ByDayRule$WeeklyExpansionFilter.class` | `56a554aba97ed41edc631e1a60bb638cc950d581cf55f5bfd9dd1c5fe0de8c47` | `bb36c63989afe99aa3ef9c6b175f627b92f5dbed168aa92626e4f89e77876beb` |
| `net/fortuna/ical4j/transform/recurrence/ByDayRule$YearlyExpansionFilter.class` | `100f7f1eebfb2f229307606a38a9b8959651592e3fd97a12308a7e4e59a5651b` | `86acd1249b44d89b9f86a2afc115b1ad7cfb07b9c8a6985e58a114e1d09525ed` |
| `net/fortuna/ical4j/transform/recurrence/ByDayRule.class` | `305a54f63435655c9d4cfbf960f6307f53d9a24463156ceacf37efbaff774099` | `633ead7c1335cc3fc1b765e426d56c5ec6fb1ee0390f01ce4b218e9f64b7364d` |

Put the overlay jar before `ical4j-4.4.0.jar` on the classpath.

**Landed test, upstream build** (Gradle 8.5 distribution, `$O/tools/gradle-8.5`, zip sha256
`9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026` = services.gradle.org's; JDK 17.0.21; host locale `en_US.UTF-8`).
The project's `gradle-wrapper.jar` (`76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3`, the same at both pins) equals the
published wrapper of Gradle 9.0.0/9.1.0; the setup ran the verified 8.5 distribution directly instead of the wrapper. Each run took about 10 s.

| Run | Result |
|---|---|
| fix, `RecurSpec` (online, then offline) | 94/94 pass |
| parent, its own `RecurSpec` (offline) | 91/91 pass |
| fix's `RecurSpec.groovy` transplanted onto the parent (offline, restored after) | **3 of 94 fail**: `verify default WKST is MO regardless of locale: en_US` (two rows: `FREQ=WEEKLY;INTERVAL=2;COUNT=4;BYDAY=TU,SU` from 19970805T090000, and `FREQ=WEEKLY;INTERVAL=2;BYDAY=SU,MO` from 20110307) and `…: ar_EG` (the first rule) |

The landed feature sets `Locale.default` inside one JVM and expects, for the brief's rule, `19970805T090000, 19970810T090000, 19970819T090000,
19970824T090000` (5, 10, 19, 24 August) under US and ar-EG. The setup did not run the brief's fresh-process locale matrix or the parent's
dates (5, 17, 19, 31): that is the domain's preflight. Logs: `$O/logs/J04-{fix.test-offline,parent.test-offline,parent.transplanted.test-offline}.log`,
`$O/logs/J04-ical4j-fix.test-online.log`.

Commands (offline form checked; the first online run is needed once, because `test` also resolves `org.jacoco:org.jacoco.agent:0.8.9`,
which `testClasses` does not; it is in `$O/gradle-home` now):

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp GRADLE_USER_HOME=$O/gradle-home JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem
cd $O/worktrees/J04-ical4j-fix && $O/tools/gradle-8.5/bin/gradle --no-daemon --console=plain --offline \
  -Porg.gradle.java.installations.auto-download=false test --tests net.fortuna.ical4j.model.RecurSpec
python3 -I $O/scripts/junit_summary.py build/test-results/test
```

The run ends with a jacoco coverage-rule message (0.2 < 0.7) that does not fail the build. Build trees removed (`git clean -fdxq`); worktrees clean.

**For the domain agent**
- ical4j 4.4.0 carries the **parent's** `ByDayRule`; the fix overlay is the only fix-side artifact. No upstream jar was built.
- `jspecify-1.0.0` is needed to compile `ByDayRule`, not to run it.
- The landed spec changes `Locale.default` in-process; the brief asks for fresh processes per locale. The default locale here is `en_US.UTF-8`.

### J05 · Apache POI #1584

Pins: parent `72ad1d5e111c2cd00c4842a0431eb1d9ca4b605c`, fix `c94ee8ad9096bdb8cf8e5e59d8d12432e950dbf3` (worktrees
`$O/worktrees/J05-poi-{parent,fix}`). Project version `6.1.0-SNAPSHOT` (trunk after the 6.0.0 release; the parent's
subject is "Update poi-ooxml-full version to 6.0.0"). Production changes: `poi-ooxml/.../xssf/usermodel/XSSFHyperlink.java`,
`XSSFSheet.java`, `XSSFWorkbook.java`; the landed test is `poi-ooxml/.../TestXSSFHyperlink.java` (+133 lines).

**Release (common support).** `$O/releases/poi-ooxml-6.0.0/` (strict checksums), ordered classpath in `classpath.txt`:
poi-ooxml, poi, commons-codec, commons-math3, SparseBitSet, poi-ooxml-lite, xmlbeans, commons-compress, commons-lang3,
commons-io, curvesapi, log4j-api, commons-collections4.

| Jar | sha256 |
|---|---|
| `poi-ooxml-6.0.0.jar` | `759d97d608ef03b8aa701f56fef0cf9c67fac49f7fa0de4be43c01ca97542c9c` |
| `poi-6.0.0.jar` | `4977f1ae04e1c77e42c81dd94cca008e0d81ff8d0daa8b85e2a0740c3c1da3cc` |
| `poi-ooxml-lite-6.0.0.jar` | `d722039d325de73562ec79758253e6a659750a53d2e8e998bb3da54c0ad157fc` |
| `xmlbeans-5.4.1.jar` | `b8fe946b41983e86496a7a68508af82a41daafd0e2a2cc8c9302c53fcbd9802c` |
| `commons-codec-1.23.0.jar` | `47504a3ce71d73a1b0af07675546b8d8c5af87f82ef12b6381f9eb3c17dd5a5b` |
| `commons-collections4-4.6.0.jar` | `4e0d0896bac5356cead277bac0283f09813e14417e3e84e0c86b573b54d218a3` |
| `commons-compress-1.28.0.jar` | `e1522945218456f3649a39bc4afd70ce4bd466221519dba7d378f2141a4642ca` |
| `commons-io-2.22.0.jar` | `2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758` |
| `commons-lang3-3.18.0.jar` | `4eeeae8d20c078abb64b015ec158add383ac581571cddc45c68f0c9ae0230720` |
| `commons-math3-3.6.1.jar` | `1e56d7b058d28b65abd256b8458e3885b674c1d588fa43cd7d1cbb9c7ef2b308` |
| `curvesapi-1.08.jar` | `ad95b08b8bbf9d7d17e5e00814898fa23324f32bc5b62f1a37801e6a56ce0079` |
| `log4j-api-2.26.1.jar` | `f1810a4704ccce019d02bba029dc02a4f2ac0c997f647b465e7d409c1927f822` |
| `SparseBitSet-1.3.jar` | `f76b85adb0c00721ae267b7cfde4da7f71d3121cc2160c9fc00c0c89f8c53c8a` |

POI 6.0.0's class files are major 61 (Java 17). The pinned sources differ from 6.0.0's: `XSSFHyperlink` by 68 lines
(parent) / 113 (fix), `XSSFSheet` 150 / 164, `XSSFWorkbook` 83 / 87.

**Overlay** (javac 17.0.21 `--release 17`). The three changed files alone do **not** compile over 6.0.0: the pinned
`XSSFSheet` uses `org.apache.poi.xssf.usermodel.ArrayFormulaRanges`, a class added to trunk after 6.0.0 (the PR does not
change it). The overlay therefore also compiles the pinned `ArrayFormulaRanges.java` (identical class on both sides).
Eight classes per side in `$O/overlays/J05/{parent,fix}/`:

| Class | parent | fix |
|---|---|---|
| overlay jar `$O/artifacts/J05-poi-{side}-overlay.jar` | `4b87fb017fd00b803a106c82279f64707d5d23f6773483642eb8412fd1243f57` | `e8ef645ab77fb880144f0bd77be619c8d62ffcc583f3546648e9bf16cad85340` |
| `ArrayFormulaRanges` | `f093423d661ffc66eacc7e8b7755d532bf0b44f3848061830ea352c7c55030b0` | `f093423d661ffc66eacc7e8b7755d532bf0b44f3848061830ea352c7c55030b0` |
| `XSSFHyperlink` | `0d2b8027aaaae4a356505f77cbddeecea3389ac61c242f8bd099ebdf6e49b020` | `8abe31b37aac9ed046bf89c050a2ab7b3cbfc4d1d8f3cb330e839a20a584b41c` |
| `XSSFHyperlink$1` | `6bf724a084974448d7486a2c3da715ec350c931bef95fa0c50e5b701723297e7` | `05eec6d3a5d034af0e819b2e003b93faf84e7555c05993e37e93a9fc7b9a9b1e` |
| `XSSFSheet` | `221972f089a5b8c1cd4319fdff5a96d91fec1846800d427cc74c424c07f88faa` | `ea6fafd15444dd0c11d59c4264f8048afbc5c276c2f9c0c4fc44b8c25b7e0149` |
| `XSSFSheet$1` | `3caafa6c87d972ed695eb83ae3f7b4dfa82949ae8bff3a9b81ed9ccb188e357c` | `0262d05155ac0a77b709707fb07804575ffaaf2b230324891bc0188dfd82976a` |
| `XSSFWorkbook` | `8ef5fd28f32a54e5349f309c406aa6f919e60d597b226c7031e6d0f71491559a` | `c5f36eb046e9930e0d331fcc70b9d1801cd5f43af86a27a5c79fffe9a38bc71d` |
| `XSSFWorkbook$1` | `7e2a594360355255b874295b4e0d023ede3c2e11d17f80f45e7abff371283509` | `46e09017bd61162c7f1e16b6170b0620c2b4ee948606b9ba9cb702e2deb4fc9c` |
| `XSSFWorkbook$SheetIterator` | `d3010f2ea2dbce9dd19b181ab56d76e0509db58ff038349c33d08100dcef5a20` | `cd4708ed868879c73436a6a881dd24afe916d5959d65c1bba27f46faa9df1940` |

Run as `OVERLAY_JAR:$(cat $O/releases/poi-ooxml-6.0.0/classpath.txt)`.

**Setup probe** (`$O/probes/J05/MoveLinkProbe.java`, JDK 21.0.13, output `$O/logs/J05-probe.txt`). A new workbook, an
external URL link on `S!A1` and an untouched link on sheet `U`; save and reopen in memory; take A1's loaded
`XSSFHyperlink`, `removeHyperlink()` on A1, `setHyperlink(loaded)` on A2; save and reopen again:

| Link on A1 | parent overlay | fix overlay | 6.0.0 alone |
|---|---|---|---|
| address `https://example.com/page` | `IllegalStateException: The hyperlink for cell A2 references relation rId1, but that didn't exist!` on the second reopen | A1 none, A2 `https://example.com/page` | same as fix |
| address `https://example.com/page#section` | the same `IllegalStateException` | A2 `https://example.com/page#section` | same as fix |
| address `https://example.com/page`, `setLocation("section")` | reopens; A2 address `section` (location `section`) | A2 `https://example.com/page#section` (location `section`) | same as fix |

The untouched link on `U` reads `https://example.org/untouched` in every row that reopened. This is the brief's
statement (plain URL throws; URL plus `section` in the location field returns only `section`; the fix returns the full
target). **The 6.0.0 release behaves like the fix in this probe**: the regression lives in trunk code after 6.0.0, so the
parent's behaviour exists only with the parent overlay first.

**Gradle.** POI's wrapper is Gradle 9.9.1, the same `gradle-wrapper.jar` at both pins, sha256
`621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8` = services.gradle.org's
`gradle-9.9.1-wrapper.jar.sha256`. The distribution `gradle-9.9.1-bin.zip` (downloaded separately to
`$O/dl/gradle-9.9.1/`) has sha256 `d8a18a7a841dd5df825d35a685fad6f2d7f12ac0c280e57b67c27b4a520ba228` = the published
`.sha256`, and its tree is identical (`diff -r`) to the one the wrapper unpacked in
`$O/gradle-home/wrapper/dists/gradle-9.9.1-bin/dol8b552jwt4yhd7ihm3iahwb/`. Every resolvable configuration of `:poi`,
`:poi-ooxml-full`, `:poi-scratchpad`, `:poi-ooxml`, `:poi-ooxml-lite-agent` and the root project was resolved online at
both pins with `$O/scripts/resolve-all.init.gradle` (a setup-only init script in the cache folder; nothing in the
checkout changed), and the same resolution then ran `--offline` at the fix (`$O/logs/J05-poi-*.resolve-*.log`).

**Landed test** `TestXSSFHyperlink`: queued as job `20261124-203508-setup-build-apache-poi-s-poi-ooxml-at-bo`
(`verification/jobs/2026/11/24/20261124-203508-setup-build-apache-poi-s-poi-ooxml-at-bo.json`, written by
`$O/scripts/submit_B.py poi`). `:poi-ooxml:test` needs `:poi`, `:poi-ooxml-full` (the XMLBeans schema build),
`:poi-scratchpad` and the ooxml-lite agent jar, which is over the inline limit. Steps: fix online (`:poi-ooxml:jar`,
test), parent offline, the fix's test transplanted onto the parent (expected to fail), the fix again offline, clean.
Results: pending.

The command the job runs (from the worktree):

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp GRADLE_USER_HOME=$O/gradle-home J17=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem
cd $O/worktrees/J05-poi-fix && JAVA_HOME=$J17 ./gradlew --no-daemon --console=plain --offline \
  -Porg.gradle.java.installations.auto-download=false -Porg.gradle.java.installations.paths=$J17 \
  :poi-ooxml:jar :poi-ooxml:test --rerun --tests 'org.apache.poi.xssf.usermodel.TestXSSFHyperlink'
  # jar: build/dist/maven/poi-ooxml/poi-ooxml-6.1.0-SNAPSHOT.jar
```

For the domain agent:
- The 6.0.0 release behaves like the fix; only the parent overlay (or a parent build) shows the defect.
- The overlay includes `ArrayFormulaRanges` (unchanged by the PR) because the pinned `XSSFSheet` needs it over 6.0.0.
- The release resolves `poi-ooxml-lite` (the trimmed schema jar), not `poi-ooxml-full`; the probe's hyperlink paths ran
  with it. A path that needs a schema type missing from lite would need `poi-ooxml-full` 6.0.0.
- The brief's sheet clone and third save/reopen were not probed.

### J06 · Zip4j #541 (pinned source build)

- **Build**: Maven 3.10.0 on **JDK 8** (source/target 1.8, class files major 52), whole production source, `-DskipTests`
  (no landed test; Zip4j's own suite is long and was not run).
- **Artifacts** (`zip4j-2.12.0-SNAPHOT.jar`; the misspelling `SNAPHOT` is upstream's version string):

| Jar | sha256 |
|---|---|
| `$O/artifacts/J06-zip4j-parent.jar` | `f26e1ca17346dbeddac9949b1f3dbe24f75d820d516b984b57f8bc85435aeb3b` |
| `$O/artifacts/J06-zip4j-fix.jar` | `bcf00518d6573e28cb393a42d480923e8c3078e21db0ab50d599df15bd821be7` |

  `net/lingala/zip4j/tasks/RenameFilesTask.class`: parent `4880e11b3fd4b89b61dc393d2a747533be598d49c62d09fa784ecd628dab8501`, fix `cd373e73a658982854b7280e2aa9412c1d62e6c3d0c95f0e33f0325dc1d8e370`.
  The change (private `getCorrespondingEntryFromMap`): prefix matching only when the key ends in `/`, otherwise exact `equals`.
- **Runtime classpath**: none (every dependency is test scope).
- **Probe** (`$O/probes/J06/RenameProbe.java`, JDK 21.0.13; `$O/logs/J06-probe.txt`): `addStream` of `cat`, `catalog`, `other` with distinct payloads,
  `renameFile("cat","dog")`, close, then `java.util.zip.ZipFile` enumerates and reads:
  - parent: `[dog=payload-of-cat, dogalog=payload-of-catalog, other=payload-of-other]`
  - fix: `[dog=payload-of-cat, catalog=payload-of-catalog, other=payload-of-other]`

  This is the brief's statement. The directory control (`cat/` → `dog/`) was not probed.
- **Commands** (~6 s each; online, then offline on both sides):
  ```bash
  cd $O/worktrees/J06-zip4j-fix && JAVA_HOME=$J8 $MVN $SK -o -DskipTests package   # jar: target/zip4j-2.12.0-SNAPHOT.jar
  ```
- **For the domain agent**: rebuilt jars differ only in `META-INF/MANIFEST.MF` (checked with `diff -r` of the unpacked fix jars); bind the copies or the class digest.

### J07 · Apache Commons Compress #460

Pins: parent `3d9a01ec07aa18b5ff341766378e2ea62639d4f5`, fix `45023ddcc43e13804dff799ae96f2acce14ce3cd` (worktrees
`$O/worktrees/J07-commons-compress-{parent,fix}`). The only production change is one line of `TarArchiveEntry.isFile()`:
`return !getName().endsWith("/");` becomes `return linkFlag != LF_DIR && !getName().endsWith("/");`. The project
version at both pins is `1.25.1-SNAPSHOT`.

**Release (common dependency set).** `$O/releases/commons-compress-1.26.0/` (resolved with strict checksums):

| Jar | sha256 |
|---|---|
| `commons-compress-1.26.0.jar` | `051aceb8bbcc62d0f5b2b8ac72c53767f9c59bfbd050151e65bef6f51c8ed9c9` |
| `commons-io-2.15.1.jar` | `a58af12ee1b68cfd2ebb0c27caef164f084381a00ec81a48cc275fd7ea54e154` |
| `commons-lang3-3.14.0.jar` | `7b96bf3ee68949abb5bc465559ac270e0551596fa34523fddf890ec418dde13c` |

Ordered classpath: `$O/releases/commons-compress-1.26.0/classpath.txt` (compress, commons-io, commons-lang3).
**The 1.26.0 release already contains the fix**: on its own it classifies 480 files (the fix's behaviour). The pinned
`TarArchiveEntry.java` differs from the 1.26.0 source by about 50 lines at each pin (later upstream edits).

**Overlay** (`$O/scripts/overlay_b.sh`, javac 17.0.21 `--release 8`, matching the release's class major 52; one class each):

| Side | Overlay jar | sha256 | `TarArchiveEntry.class` sha256 |
|---|---|---|---|
| parent | `$O/artifacts/J07-commons-compress-parent-overlay.jar` | `e7c2e39b4f59f1b432fac33a392ccd556232d0cd40a9cd67691dfcfee727bb80` | `245d760646d1c4f8947cfa09102db3c95069e70960aa5dc8be8266c1faf62cc2` |
| fix | `$O/artifacts/J07-commons-compress-fix-overlay.jar` | `466fe6b9b339b85aa90cd8d303abcc8012ea8b534d586ccb2fc6d70061dd459f` | `2fbfd8117b68745e78f575698f6e69b213ce744b34f2b75d18882e57882f798f` |

Classes are in `$O/overlays/J07/{parent,fix}/`. Run as `OVERLAY_JAR:$(cat $O/releases/commons-compress-1.26.0/classpath.txt)`:
the overlay must come before the release jar. The overlay jars are built with a fixed date, so they rebuild identically.

**Built jars** (Maven 3.10.0 on JDK 17.0.21, `package`; class major 52):

| Jar | sha256 | `TarArchiveEntry.class` sha256 |
|---|---|---|
| `$O/artifacts/J07-commons-compress-parent.jar` (1.25.1-SNAPSHOT) | `0fe2661943bb3ec6150cb1c8307ec3543ab147d0da84339f268666bd91b17792` | `68cfc8fde5165551510c2d71c8e5ae7c0b11f5f74aad2fc6ca0149720c5493b3` |
| `$O/artifacts/J07-commons-compress-fix.jar` (1.25.1-SNAPSHOT) | `8d7158139cc2e2b3ef87ec0f775cf09365d6794d207c420941516ec53a40d486` | `c91ce2143a1dd1b4bb5582a55f8d653bd20de70dfcb497ed51600f6afbbb820a` |

Runtime classpath of the built jar (`$O/logs/J07-commons-compress-fix.runtime-classpath.txt`): zstd-jni 1.5.5-11, brotli
dec 0.1.2, xz 1.9, commons-codec 1.16.0, asm 9.6, commons-io 2.15.1 (all optional for TAR; commons-io is needed).

**Test archive.** `src/test/resources/COMPRESS-657/orjson-3.7.8.tar` (added by the fix) sha256
`bef2af710d208eeaa53f42f47bd8ca38299f9087a586c46a916c9c742bc49cfb`; its `README.md`
`e54193df8db83abe5ead9ffec26268e7634257e42d4119ac64c1da2d341f62db`. Read it from the fix worktree, or
`git -C $M/commons-compress.git show 45023ddcc43e13804dff799ae96f2acce14ce3cd:src/test/resources/COMPRESS-657/orjson-3.7.8.tar`.

**Landed test** `TarFileTest` (upstream Maven build, inline; logs `$O/logs/J07-commons-compress-*.log`):

| Step | Result |
|---|---|
| fix (online, then offline) | 25/25 pass |
| parent's own | 24/24 pass |
| fix's `TarFileTest.java` + `COMPRESS-657/` resources transplanted onto the parent | **1 failure**: `testCompress657`, "Entry 'orjson-3.7.8/include' is both a directory and a file ==> expected: <false> but was: <true>" |

Commands (about 30 s each; the offline form was run for all three steps):

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp
SK="-Drat.skip -Djapicmp.skip -Danimal.sniffer.skip -Dcheckstyle.skip -Dspotbugs.skip -Dpmd.skip -Dcpd.skip -Djacoco.skip \
    -Dmaven.javadoc.skip -Dcyclonedx.skip -Dspdx.skip -Drevapi.skip -Dmaven.source.skip -Dbnd.baseline.skip \
    -Dsurefire.failIfNoSpecifiedTests=false -Dmoditect.skip"
cd $O/worktrees/J07-commons-compress-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem \
  mvn -B -o -s $O/maven-settings.xml $SK -Dtest=TarFileTest package     # jar: target/commons-compress-1.25.1-SNAPSHOT.jar
```

**Setup probe** (`$O/probes/J07/TarKinds.java`, JDK 21.0.13, output `$O/logs/J07-probe.txt`): public `TarFile` over the
archive, both predicates per entry, payloads read through.

| Classpath | entries | directories | files | both | payload bytes |
|---|---|---|---|---|---|
| parent overlay over 1.26.0, and parent built jar | 481 | 1 | 481 | 1 (`orjson-3.7.8/include`, flag `5`) | 1438851 |
| fix overlay over 1.26.0, and fix built jar | 481 | 1 | 480 | 0 | 1438851 |
| 1.26.0 release alone | 481 | 1 | 480 | 0 | 1438851 |

This is the brief's statement (481 entries, one directory, 481 → 480 files, 1,438,851 payload bytes).

For the domain agent:
- The 1.26.0 release behaves like the fix: the parent's behaviour exists only with the parent overlay first on the classpath, or the parent built jar.
- The differing entry is `orjson-3.7.8/include`, type flag `5` (directory) and no trailing slash.
- The probe read payloads once; the brief's "read the payloads twice" and the trailing-slash directory control are domain work.

### J08 · Apache Parquet #3638 (pinned source overlay over 1.18.2)

Pins: parent `5c360ff5d879d3567f23cea3290894712fb336d9`, fix `5e14d7cd43403a95d331be8791e8792dbf38683d`
(worktrees `$O/worktrees/J08-parquet-java-{parent,fix}`, clean). Both trees are `1.18.0-SNAPSHOT` on `master`.
Changed production files (both in `parquet-column`): `column/values/dictionary/DictionaryValuesWriter.java` (1 line) and
`column/values/fallback/FallbackValuesWriter.java`. Landed test: `TestDictionary.java` (two new tests).

**Releases** (resolved with `$O/scripts/resolve.sh`, strict checksums; PGP left to the main session's pass):

| `$O/releases/…` | What | Main jar sha256 |
|---|---|---|
| `parquet-column-1.18.2` | `org.apache.parquet:parquet-column:1.18.2`, 7 jars (parquet-common, parquet-encoding, parquet-format-structures 1.18.2, javax.annotation-api 1.3.2, slf4j-api 1.7.33, jts-core 1.20.0) | `parquet-column-1.18.2.jar` `e453c9725e323ca3a1165b842cae325c35fc3eed0ec37856ba15fe61290569a6`; `parquet-common-1.18.2.jar` `b49a34765ffbaf8d8b66f8b6bdf9a008f3f057b691f74041d26d40fc8759d44f`; `parquet-encoding-1.18.2.jar` `417f925abc073a6f732386694be59942190282e36cf89368f4666145b42cdaf1`; `parquet-format-structures-1.18.2.jar` `9827bead58f8cc1ca1e4f529af042096505fa5e32cee9cab656b2d8ff0be2509` |
| `fastutil-8.5.19` | `it.unimi.dsi:fastutil:8.5.19` (unshaded; see below) | `c767a6bdcb7cb52fe1315ca1f4891389a75e63b2a15a6629865d7740dd3a8cf2` |
| `parquet-hadoop-1.18.2` | `org.apache.parquet:parquet-hadoop:1.18.2` + `org.apache.hadoop:hadoop-client:3.3.0` (the Hadoop version the 1.18.2 POM names, `provided` there), 111 jars, 64 MB, for the public file writer and reader | `parquet-hadoop-1.18.2.jar` `746b75a9b3171a6daebe9d1ee4e152fb95f9c0d63f92b5e51790e88bd13b88a1`; `hadoop-common-3.3.0.jar` `9c876827639d401a7af2d16a49c9fd69133dd4ff4a6f127ce557054274038967`. Its parquet-column and parquet-common jars are the same files as above (same sha256). |
| `j08-testdeps` | junit 4.13.2 (+ hamcrest-core 1.3), assertj-core 3.27.7, mockito-core 5.23.0 (+ byte-buddy, objenesis): the versions the pinned POM names | — |

**Parquet 1.18.2 already contains the fix.** Its sources jar has `DictionaryValuesWriter.java` and
`FallbackValuesWriter.java` byte-identical to the fix revision's; the parent's differ (1 and 13 diff lines). So the bare
release behaves like the fix side, and only the parent overlay reproduces the parent.

**Fastutil shading.** The released `parquet-column-1.18.2.jar` shades fastutil 8.5.19 as `shaded.parquet.it.unimi.dsi.fastutil`
(1,084 entries). The pinned sources import `it.unimi.dsi.fastutil.*` (the build relocates them at package time), so they do
not compile against the release alone. The overlay is compiled and run with the unshaded `fastutil-8.5.19.jar` (the same
version the release shades; the pins' POM names 8.5.18) appended to the classpath. The overlay classes then use the
unshaded copy while the rest of 1.18.2 uses its shaded one; no fastutil type crosses between them in the tests below.

**Overlay** (`$O/scripts/overlay_D.sh`, javac 17.0.21 `--release 11` (the POM's `maven.compiler.release`), sources taken with
`git show HEAD:` from each worktree). Classpath for compiling and running: `$O/overlays/J08-classpath.txt` (= parquet-column-1.18.2
classpath, then fastutil 8.5.19); with Hadoop for the file writer: `$O/overlays/J08-hadoop-classpath.txt`. Put the overlay jar first.

| Jar | sha256 |
|---|---|
| `$O/artifacts/J08-parquet-java-parent-overlay.jar` | `28b3eb17a9d72a4f678e86642f52fa2ec7cf17b42626d1deda37e7c04e9ab2ae` |
| `$O/artifacts/J08-parquet-java-fix-overlay.jar` | `cb7a4d77da751a8ae262afc22a6609803319065cae001f7eb2dd8ac5c0a23095` |

The jars are reproducible (entries dated 1980-01-01). 8 classes each; per-class sha256 in
`$O/logs/J08-{parent,fix}.overlay-classes.sha256`. The two that matter:

| Class | parent | fix |
|---|---|---|
| `FallbackValuesWriter.class` | `a1961ed5fa850d7617021601591cd53edfd9235a48b52d111e002b29f6e7afb5` | `887c5c0f52a6c25d74ab3fda47af2430c1e4759646c764669639847bd3dbbb02` |
| `DictionaryValuesWriter.class` | `b65f86f757eb501133b1543da08e9ad7bbaeb347b9946224187e947ffc32d8bc` | `1fab07f5f41ee86caa025107d3b63534ce133492834117ca4a0de45f232f10b2` |
| `DictionaryValuesWriter$PlainBinaryDictionaryValuesWriter.class` | `58885c2a0394939c734a8dd915618cc848338e989d941c08079d3c6fab6fece6` | `773d5e895cc0f541d7f04e69a9e48ad9313ef6a761dc8e7b464bfd3c3583b71c` |

**Landed test, run as an overlay test, not an upstream build** (`$O/scripts/j08_overlay_test.sh TESTROLE CLASSROLE`, JDK 21.0.13,
JUnit 4 `JUnitCore`; output `$O/logs/J08-overlay-TestDictionary.txt`). `TestDictionary.java` sha256: fix
`0925e30b7ffb4818eee42d02ccfe899dea9c831c20f34ec23ea2270e41fb0106`, parent `5fab322bfdf383fbbf87e03978780e08259fd8e76668770c8432b20480eb4b80`.

| Test file | Classes | Result |
|---|---|---|
| fix | fix overlay | OK, 24 tests |
| parent | parent overlay | OK, 22 tests |
| fix (transplanted) | parent overlay | **2 failures**: `testDictionaryWriterReusableAfterFirstPageFallBack`, `testDictionaryWriterReusableAfterFallBack` |
| parent | fix overlay | OK, 22 tests |
| fix | 1.18.2 alone (no overlay) | OK, 24 tests |

**Why no upstream build.** `parquet-column -am` pulls in `parquet-common`, which depends on `parquet-format-structures`,
which runs `thrift-maven-plugin` with a `thrift` 0.23.0 executable. There is no `thrift` on this machine and the setup did
not build one. The pins' `1.18.0-SNAPSHOT` modules are not published, so `-pl parquet-column` alone cannot resolve its siblings.

**For the domain agent**
- The overlay over 1.18.2 needs the unshaded fastutil jar on the classpath (above). Bind the overlay jar plus
  `$O/overlays/J08-classpath.txt` (or `J08-hadoop-classpath.txt` for the public `ParquetWriter`/`ParquetFileReader` path).
- 1.18.2 itself is fix-equivalent for both changed classes; a "release" run is not a parent control.
- The brief's writer-level replay (PLAIN 0/1,000 vs PLAIN_DICTIONARY 1,000/1,000) was not replayed separately; the landed
  tests that fail on the parent overlay are its reuse-after-fallback checks.
- The Hadoop graph was resolved but nothing was run through it; whole-file readback is the brief's next claim.

### J09 · SQLite JDBC #126 (published release pair; native rebuilt at both pins)

Pins: parent `d36de443c9004ac1eb34f00ceb51c46eeaeafb0e`, fix `44848544c11e3705ee6b208d844a067ffb535012`
(worktrees `$O/worktrees/J09-sqlite-jdbc-{parent,fix}`, clean). Both are version `3.9.1-SNAPSHOT`, `VERSION` = `version=3.9.1`.
The PR changes `src/main/java/org/sqlite/core/NativeDB.c`, the two bundled Mac binaries and `QueryTest.java`. **The bundled
Linux x86-64 library is the same blob at both pins** (`src/main/resources/org/sqlite/native/Linux/x86_64/libsqlitejdbc.so`,
git blob `9d5704bdfc2b3dc385b38a96dab2e11057ebc51e`, sha256 `ef4b065f98706eaf9a9170f813998eb46479bf772a9dc3b10764d619423281b7`);
the Java sources are unchanged, so on Linux the two pins differ only once the native side is rebuilt.

**Release pair** (`$O/releases/sqlite-jdbc-{3.8.11.2,3.14.2}`, no dependencies):

| Release | Jar sha256 | `org/sqlite/native/Linux/x86_64/libsqlitejdbc.so` sha256 |
|---|---|---|
| 3.8.11.2 | `f30968b896af52baaeda4a901f6ef2629319168fa304e9747c7cfabef6c476ec` | `be472851df457b7dd83428cefc71279c7c7d34d09f89f9ee5040e048633a40e2` (776,864 bytes) |
| 3.14.2 | `89db1d0ed530b639b3e4825e663ff6ee674ad4ba0c1e6bb87106c854e616a08d` | `5db4cc4580b86899188ab40d3e1d24b7658727afa433c3869316491f780a5669` (933,512 bytes) |

**Probe** (`$O/probes/J09/BlobProbe.java`, JDK 21.0.13, Linux/amd64, `jdbc:sqlite::memory:`; one `ResultSet` over
`SELECT NULL UNION ALL SELECT zeroblob(0) UNION ALL SELECT zeroblob(5)`, `getBytes(1)` then `wasNull()`; `$O/logs/J09-probe-releases.txt`):
- 3.8.11.2 (native, SQLite 3.8.11): `null/true; null/false; 5 bytes [0,0,0,0,0]/false`
- 3.14.2 (native, SQLite 3.14.2): `null/true; 0 bytes []/false; 5 bytes [0,0,0,0,0]/false`

This is the brief's statement.

**Native rebuild at both pins (Linux x86-64).** Inputs:
- `$O/dl/sqlite-3.9.1/sqlite-amalgamation-3090100.zip`, from `https://www.sqlite.org/2015/` (the Makefile's first matching
  URL for `amalgamation_version.sh 3.9.1` = `3090100`). zip sha256 `5e25da9f46d6a7b2a378d26c5069b1efec0b5d1707376d9c34b4f24c329bd74e`,
  sha1 `3113a7656a25b21d6368af75592b57a7c9edf747`. Its `sqlite3.c` has SHA1 `5e6d1873a32d82c2cf8581f143649940cac8ae49`, which
  equals the "SHA1 for sqlite3.c" on `https://www.sqlite.org/releaselog/3_9_1.html` (saved beside it), and
  `SQLITE_SOURCE_ID` `2015-10-16 17:31:12 767c1727fec4ce11b83f25b3f1bfcfe68a2c8b02`.
- gcc 15.2.0 (Ubuntu 15.2.0-16ubuntu1), JDK 8u512 for `javah`.

Command, per worktree (~21 s each; logs `$O/logs/J09-native-{parent,fix}.log`):

```bash
O=~/.cache/in-the-loop/organic-pr-20; cd $O/worktrees/J09-sqlite-jdbc-fix; mkdir -p target
cp $O/dl/sqlite-3.9.1/sqlite-amalgamation-3090100.zip target/sqlite-3.9.1-amal.zip   # so make does not download
JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem make native CC="gcc -fpermissive"
```

**Substitution:** `CC="gcc -fpermissive"` on the make command line (build files unchanged). Without it GCC 15 stops at
`implicit declaration of function 'RegisterExtensionFunctions'`, which GCC 14+ treats as an error; GCC of 2016 warned.
`-fpermissive` turns it back into a warning. The remaining warnings are `-Wstringop-overflow` and one `-Wreturn-local-addr`
in the amalgamation. `make native` copies the library into `src/main/resources/...`, a tracked file; it was restored with
`git checkout` afterwards.

| Artifact | sha256 |
|---|---|
| `$O/artifacts/J09-sqlite-jdbc-parent-Linux-x86_64-libsqlitejdbc.so` | `7a6e8dc656388dfeba6db587384edf167a16e837f3ad6c43a96edfd6f247813d` |
| `$O/artifacts/J09-sqlite-jdbc-fix-Linux-x86_64-libsqlitejdbc.so` | `f10d2a3bb6c507e1069fb35316d82158f1a4f235ac6ca8a8eb3f447b6a5a7df6` |
| `$O/artifacts/J09-sqlite-jdbc-parent-rebuilt-native.jar` (`mvn package -DskipTests` with the rebuilt library in resources) | `f8895a6843a407c2ae3a2a8ccc0360d37fe0c31e61786c2acb96fc80c0ce7517` |
| `$O/artifacts/J09-sqlite-jdbc-fix-rebuilt-native.jar` | `9bea3bf08fd1c141a922dd1e2b10f04a76ed8c6dfa251366a1bc8b1878acbe83` |

In both jars `org/sqlite/core/NativeDB.class` is `09d13fc7313828793c900d0e25c2adf10c0766c97155acbeaa15f4fa2be45d2c`, and
the Linux library inside is the rebuilt one above. The jars have no dependencies. The setup did not check whether a rebuild is
byte-reproducible; the jar digests include build timestamps.

**Landed `QueryTest`** (Maven 3.10.0 on JDK 8u512, `$O/scripts/j09_querytest.sh ROLE rebuilt|bundled [transplant]`;
summary `$O/logs/J09-QueryTest-summary.txt`, full logs `$O/logs/J09-*.QueryTest.log`):

| Native library | fix | parent's own | landed file on the parent |
|---|---|---|---|
| rebuilt from the pin | 10/10 pass | 7/7 pass | **1 error**: `emptyBlob` (NullPointerException at `QueryTest.java:131`) |
| bundled (the same at both pins) | **1 error**: `emptyBlob` | 7/7 pass | **1 error**: `emptyBlob` |

So on Linux the landed test passes on the fix only with the rebuilt native side, as the brief says. The command:

```bash
cd $O/worktrees/J09-sqlite-jdbc-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem mvn -B -o -s $O/maven-settings.xml \
  -Dtest=QueryTest test-compile org.apache.maven.plugins:maven-surefire-plugin:2.19.1:test
```

**Substitution:** the POM pins no surefire version, and Maven 3.10.0's default (3.6.0) refuses the project's JUnit 4.8.2
("not supported anymore"). The test goal is named with surefire 2.19.1 (a 2016 release) explicitly. The offline form above
was run (fix, rebuilt native: 10/10). `mvn -o -DskipTests package` was run at the fix (the parent's `package` ran online first, to fetch maven-jar-plugin 2.3.2).

**Probe on the pins** (`$O/logs/J09-probe-pins.txt`, JDK 21.0.13, SQLite 3.9.1 in every row; the library chosen with
`-Dorg.sqlite.lib.path`/`-Dorg.sqlite.lib.name`, and again from the rebuilt jars):
- parent classes + rebuilt or bundled native: `null/true; null/false; 5 bytes/false`
- fix classes + rebuilt native (and `J09-sqlite-jdbc-fix-rebuilt-native.jar`): `null/true; 0 bytes []/false; 5 bytes/false`
- fix classes + bundled native: `null/true; null/false; 5 bytes/false`

**For the domain agent**
- Bind the native library, not only the jar: the Java classes are identical across the pins, and the library extracted at
  run time decides the outcome. sqlite-jdbc extracts it to `java.io.tmpdir`; set that to a folder under the cache.
- The release pair differs in SQLite itself (3.8.11 vs 3.14.2) as well as in the JNI code; the rebuilt pin pair holds SQLite 3.9.1 fixed.
- The rebuilt libraries were made with today's GCC and `-fpermissive`, not the 2016 toolchain upstream used; Mac binaries were not rebuilt.

### J10 · Kryo #530 (pinned source overlay over Kryo 4.0.2)

- **Release** `com.esotericsoftware:kryo:4.0.2`, resolved with strict checksums into `$O/releases/kryo-4.0.2/` (`lib/`, `sources/`, `tree.txt`, ordered `classpath.txt`):

| Jar | sha256 |
|---|---|
| `kryo-4.0.2.jar` | `8cd8bcb6920b165ff21b82f7a44f2c7e87dcb24560e52b9dc7d085fba9cfcce5` |
| `reflectasm-1.11.3.jar` | `a61b1919fc26262d1c95b0167f87e6985cdd90be3dab1a14479fb351d08c63d4` |
| `asm-5.0.4.jar` | `896618ed8ae62702521a78bc7be42b7c491a08e6920a15f89a3ecdec31e9a220` |
| `minlog-1.3.0.jar` | `f7b399d3a5478a4f3e0d98bd1c9f47766119c66414bc33aa0f6cde0066f24cc2` |
| `objenesis-2.5.1.jar` | `b043f03e466752f7f03e2326a3b13a49b7c649f8f2a2dc87715827e24f73d9c6` |

- **Overlay**: `src/com/esotericsoftware/kryo/Kryo.java` and `src/com/esotericsoftware/kryo/serializers/DefaultSerializers.java` at each pin,
  compiled with javac 1.8.0_512 `-source 1.7 -target 1.7` (the POM's levels; class files major 51) over `releases/kryo-4.0.2/classpath.txt`.
  Sources in `$O/overlays/J10/{parent,fix}/src`, classes in `.../classes` (39 classes each; every class digest in `$O/logs/J10-kryo-{parent,fix}-overlay.classes.sha256`):

| | parent | fix |
|---|---|---|
| overlay jar (`$O/artifacts/J10-kryo-ROLE-overlay.jar`) | `285e8446e65342467f0e548e92b751b5a7760011b068bd7f8b3c851e65e129ec` | `61bfb3ad28ac30bd5f35e0fce699ea21e9fe936eb5ccf307d09fcfb4817ea911` |
| `com/esotericsoftware/kryo/Kryo.class` | `202c77134efaace4952337a4529c9a07610b4afe98f487ea9bdce7fc28916e84` | `b51285990041c31737217ee8129b6fdfbea8cb3e7930477210caee7a1f990a36` |
| `.../serializers/DefaultSerializers$EnumSerializer.class` | `4c88a4e378d4dff46bb5b2fff7cc55277a149fadd3ced9c91b0a13d06739bf47` | `3d52c7a8adcda5a0c995209aafbeaa3d30868d88711d06d1090429e2217b3190` |

  Classpath for a run: `$O/artifacts/J10-kryo-ROLE-overlay.jar:$(cat $O/releases/kryo-4.0.2/classpath.txt)` (overlay first). Most nested
  `DefaultSerializers$*` classes differ between the sides only because the fix's added comment shifts line numbers.
  **The fix's two files are identical to those in `kryo-4.0.2-sources.jar`** (diff: 0 lines), so the fix overlay reproduces the 4.0.2 source of these files.
- **Upstream source build** as well (cheap): Maven 3.10.0 on JDK 8, `-f pom-main.xml` (version 4.0.2-SNAPSHOT), `-Dclirr.skip`:

| Jar | sha256 | `Kryo.class` | `DefaultSerializers$EnumSerializer.class` |
|---|---|---|---|
| `$O/artifacts/J10-kryo-parent.jar` | `4bb75fd61eaa2f029cc09b239b208fa72d9f4ae7009414e4afbda424d1e79113` | `e7432a3a1d66c0524f39abd8225f372c86b1f2267b0179483d69949fdb3cfe52` | `c8dda09dcd74b495c915d7160e6218b1b9100df321d9dbdf2b4d7c8d4e001ad6` |
| `$O/artifacts/J10-kryo-fix.jar` | `87b5380b7bca50ead14be1b7a1f476fa60f8da95e653b7fd11d7164281ec585c` | `98e2fa40c12678b7f66faee59ed7c634d9af3e310ae067ed2da67a313115bac5` | `9b58ebe6c25f77f54f7cd6eeb7fc9afb2e932aea950295827146d1afffeb4eee` |

  Its runtime classpath (`$O/logs/J10-kryo-fix.runtime-classpath.txt`): reflectasm 1.11.3, asm 5.0.4, minlog 1.3.0, objenesis 2.5.1, the same versions as the release graph.
- **Landed test** `DefaultSerializersTest` (upstream build):

| fix | parent's own | fix's file on the parent |
|---|---|---|
| 23/23 pass | 23/23 pass | **1 error of 23**: `testClassSerializer`, `IllegalArgumentException: type cannot be null.` at `Kryo.getRegistration(Kryo.java:486)` ← `getRegistration(Kryo.java:495)` ← `DefaultClassResolver.writeClass` ← `Kryo.writeClass` ← `ClassSerializer.write`, at the added `kryo.writeObject(out, Enum.class)` (line 317) |

  So in the test's configuration the parent fails in `Kryo.getRegistration` (the enclosing class of `Enum.class` is null), not with the
  `EnumSerializer` message "The type must be an enum". Both are `IllegalArgumentException`, as the brief says.
- **Commands** (~9 s each; online, then offline on both sides):
  ```bash
  cd $O/worktrees/J10-kryo-fix && JAVA_HOME=$J8 $MVN $SK -o -f pom-main.xml -Dtest=DefaultSerializersTest -Dclirr.skip package   # jar: target/kryo-4.0.2-SNAPSHOT.jar
  # add -DtrimStackTrace=false to see the full trace
  ```
- **For the domain agent**: no probe; the brief's byte counts (64 with `Enum.class`, 46 without) depend on the fixture's registration
  settings and were not checked. Which exception path the parent takes depends on the resolver/registration configuration.

### J11 · H2 #4575

Pins: parent `df37ff0363c0b84758017c8788e313d34646d403`, fix `2b7812b20a421be7116cc75b5abf95a5718f7119` (worktrees
`$O/worktrees/J11-h2database-{parent,fix}`; the Maven project is in `h2/`). Project version `2.5.259-SNAPSHOT`,
`maven.compiler.release` 11. The only production change is `h2/src/main/org/h2/mvstore/db/MVSortedTempResult.java`;
the PR adds `testSortPreservesValues` to `TestBigResult`.

**Release (common support).** `$O/releases/h2-2.5.252/`: `h2-2.5.252.jar`
`90b11dc413da82070ef15fc943282c1408e6ffd34fa68998335fea8603b5ff20`, no runtime dependencies (class major 55). It exists
on Maven Central. **The 2.5.252 release behaves like the parent.** The pinned `MVSortedTempResult.java` differs from
2.5.252's by 4 lines at the parent and 62 at the fix.

**Overlay** (javac 17.0.21 `--release 11`, one class each, no inner classes):

| Side | Overlay jar | sha256 | `MVSortedTempResult.class` sha256 |
|---|---|---|---|
| parent | `$O/artifacts/J11-h2database-parent-overlay.jar` | `c3bccd6eaf23522b650d6d144167258e7c54698f532cd74641554d6d96014e06` | `df63908aa4783e1e39f08e2f93a97129cb1dd251ec1bc2819f49462f5f38f0c9` |
| fix | `$O/artifacts/J11-h2database-fix-overlay.jar` | `81b1866c21b55b0c261db0f313288b7f20753850a4057dac803c5b3c775fa330` | `3655d05fb634babb3b526479a18b0e8008b41c4d2c3df8e4356848887cff4446` |

Run as `OVERLAY_JAR:$(cat $O/releases/h2-2.5.252/classpath.txt)`.

**Built jars** (Maven 3.10.0 on JDK 17.0.21, `-DskipTests package` in `h2/`):

| Jar | sha256 | `MVSortedTempResult.class` sha256 |
|---|---|---|
| `$O/artifacts/J11-h2database-parent.jar` (2.5.259-SNAPSHOT) | `cc346137ce9bfe72e83703785b76cf0d4a89717228952194d0c4c402f0b359ad` | `7e7a619c1c7d99a466c7168a6a5268a81d61a0d98a0d7ef26b1dc6722ccdb9fc` |
| `$O/artifacts/J11-h2database-fix.jar` (2.5.259-SNAPSHOT) | `10ce971e7771ad3b15c4216ed2719289b27a6846b1875688af108d6042151028` | `115bb30fa5bbfc7b1d3dfe936f7ece686044ddeb8d070faf1e0cd67a56b77a9c` |

The jar runs JDBC alone; its declared runtime dependencies (servlet APIs, Lucene 9.7.0, slf4j, OSGi, JTS;
`$O/logs/J11-h2database-fix.runtime-classpath.txt`) are optional features.

**Landed test** `TestBigResult`. H2's tests run through its own harness (`TestBase`), not JUnit: surefire only runs
`TestAllJunit`. The cheapest faithful run is the test's own `main` (`TestBase.createCaller().init().testFromMain()`),
which runs `test()` once with the default configuration. It prints nothing on success and throws `AssertionError` on the
first failure, so later subtests do not run after one fails. Logs `$O/logs/J11-h2database-*.TestBigResult.log`.

| Step | Result |
|---|---|
| fix (built online, then offline) | pass (exit 0) |
| parent's own | pass (exit 0) |
| fix's `TestBigResult.java` transplanted onto the parent | **fails** (exit 1) in `testSortPreservesValues` (line 83): `Expected: @8 [null, A<*>BC, Abc, abc, abc, z] (29) actual: [null, abc, abc, abc, abc, z] (29)` |

Commands (each about 10 s; the offline form was run for every step):

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp; J=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem
W=$O/worktrees/J11-h2database-fix/h2
cd $W && JAVA_HOME=$J mvn -B -o -s $O/maven-settings.xml -DskipTests test-compile \
  org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath -DincludeScope=test -Dmdep.outputFile=$O/logs/J11-h2database-fix.test-classpath.txt
mkdir -p $O/tmp/j11-run && cd $O/tmp/j11-run && \
  $J/bin/java -cp $W/target/classes:$W/target/test-classes:$(cat $O/logs/J11-h2database-fix.test-classpath.txt) org.h2.test.db.TestBigResult
cd $W && JAVA_HOME=$J mvn -B -o -s $O/maven-settings.xml -DskipTests package      # jar: target/h2-2.5.259-SNAPSHOT.jar
```

The test writes its database under `./data` in the working directory: run it from a scratch folder, never the checkout.

**Setup probe** (`$O/probes/J11/SpillProbe.java`, JDK 21.0.13, output `$O/logs/J11-probe.txt`): a file database with
`MAX_MEMORY_ROWS=1` or `100000`, `VARCHAR_IGNORECASE` rows `abc, ABC, Abc, abc, z`, `CREATE TABLE R AS SELECT V FROM T
ORDER BY V`, close, reopen, read `R` and sort the spellings.

| Classpath | `MAX_MEMORY_ROWS=1` | `MAX_MEMORY_ROWS=100000` | `COUNT(DISTINCT V)` |
|---|---|---|---|
| parent overlay, parent built jar, 2.5.252 alone | `[abc, abc, abc, abc, z]` | `[ABC, Abc, abc, abc, z]` | 2 |
| fix overlay, fix built jar | `[ABC, Abc, abc, abc, z]` | `[ABC, Abc, abc, abc, z]` | 2 |

This is the brief's statement.

For the domain agent:
- The 2.5.252 release behaves like the parent; the fix exists only as the fix overlay (before the release jar) or the fix built jar.
- `TestBigResult` is not a JUnit test: run its `main`, as above. The landed `testSortPreservesValues` also covers
  `TIMESTAMP WITH TIME ZONE`, `VARCHAR_IGNORECASE ARRAY` and `VARCHAR`; on the parent it stops at the first case.

### J12 · Apache Calcite #1003 (published release pair; exact PR pair built by a job)

Pins: parent `f2638b9f7dc878f3f109cbc59d1a6ae02d3d5696`, fix `f992e6c8fbc3712c6bd70096fb6b05da448b2cab`
(worktrees `$O/worktrees/J12-calcite-{parent,fix}`; both `1.19.0-SNAPSHOT`). The PR changes, in `core/.../adapter/enumerable/`:
`SequencedAdderAggregateLambdaFactory` → `BasicAggregateLambdaFactory` (rename), `OrderedAggregateLambdaFactory` →
`LazyAggregateLambdaFactory` (rename), new `BasicLazyAccumulator`, `EnumerableAggregate`, `SourceSorter`, and
`util/BuiltInMethod`; the landed regression is in `core/src/test/resources/sql/agg.iq`, run by `CoreQuidemTest`.

**Release pair** (`$O/releases/calcite-core-{1.18.0,1.19.0}`, 27 jars each, through `org.apache.calcite:calcite-core`):

| Release | `calcite-core` sha256 | `calcite-linq4j` sha256 |
|---|---|---|
| 1.18.0 | `6429929601f2bcbff79edb465cb2b09495ddaf079f6e077f0b0a888c950c2ee2` | `58471aedc88574aa7f18baf05b1d6f280e74a9b48c93410d6d00c6c0ce2191e4` |
| 1.19.0 | `c766dc3905946154bb6be75fc2b3480b9bdef36dc2bfba8868c3af51685438f0` | `83d7e7c75da0e1e34ad80d6a34c9e150bd852ab892ee1565e9a3258b82799ba3` |

Both use avatica-core 1.13.0 (`b065e18b3c9fafa2b13113bc76a57aef412e1f8ee5caeec331e1f3e3656dda8c`). The graphs differ
outside Calcite too: jackson 2.9.6 → 2.9.8, snakeyaml 1.18 → 1.23, janino/commons-compiler 3.0.9 → 3.0.11. 1.18.0 has
`OrderedAggregateLambdaFactory` and `SequencedAdderAggregateLambdaFactory`; 1.19.0 has `BasicAggregateLambdaFactory`,
`LazyAggregateLambdaFactory` and `BasicLazyAccumulator`, so 1.19.0 contains the PR. Ordered classpaths in `classpath.txt`.

**Probe** (`$O/probes/J12/CollectProbe.java`, `jdbc:calcite:` with no model; input
`(VALUES (10,1),(20,7),(10,3),(10,3),(10,2)) AS t(deptno,n) GROUP BY deptno ORDER BY deptno`; run on JDK 21.0.13 and 8u512
with identical output; `$O/logs/J12-probe-releases.txt`):

| Query | 1.18.0 | 1.19.0 |
|---|---|---|
| `COLLECT(n)`, `COLLECT(n) WITHIN GROUP (ORDER BY n DESC)` | `10 [] [3, 3, 2, 1]; 20 [] [7]` | `10 [1, 3, 3, 2] [3, 3, 2, 1]; 20 [7] [7]` |
| `COLLECT(n)` alone | `10 [1, 3, 3, 2]; 20 [7]` | the same |
| ordered `COLLECT` alone | `10 [3, 3, 2, 1]; 20 [7]` | the same |

This is the brief's statement (empty unordered bags on 1.18.0 only in the mixed query; the ordered column the same on both).
The unordered bag prints in input order here; the brief compares it as a multiset.

**Exact PR pair: job `20261124-203257-setup-build-apache-calcite-core-at-both`**
(`verification/jobs/2026/11/24/20261124-203257-setup-build-apache-calcite-core-at-both.json`, written by `$O/scripts/submit_D.py`;
results pending). Steps: fix `-pl core -am -Dtest=CoreQuidemTest package` online; parent's own, offline; the fix's `agg.iq`
transplanted onto the parent, offline (expected to fail); fix again offline; remove build trees. It copies
`$O/artifacts/J12-calcite-{parent,fix}-{core,linq4j}.jar` with sha256 and writes `$O/logs/J12-calcite-*.core.runtime-classpath.txt`
and JUnit summaries `$O/logs/J12-calcite-*.CoreQuidemTest.junit.txt`. `--stop-on-failure no`, so a failing own run does
not hide the others.

What the job needs, set up and checked inline:
- **Maven 3.5.4** (the pin's wrapper version) in `$O/tools/apache-maven-3.5.4`, from Central: zip sha256
  `6aaa1bee0be0e3a64b3303df0afb36e4bb69922fe46d43b32615796d671a4275`; Central's `.sha1` matches; Central has no `.sha512`
  (404), and archive.apache.org's `.sha512` matches. The `.asc` is saved in `$O/dl/maven-3.5.4/` and was not checked by this fork.
  Maven 3.10.0 cannot read the build: `piglet/pom.xml` declares `calcite-core:test-jar` twice, which 3.10 rejects.
- **`$O/scripts/maven-settings-https-central.xml`**: the same local repository plus a mirror of `central` to
  `https://repo.maven.apache.org/maven2`. The root POM redefines repository `central` as `http://repo.maven.apache.org/maven2`,
  which Central no longer serves over http. Build files unchanged.
- An online `-pl linq4j -DskipTests package` with that Maven and settings on JDK 8 passed in 29 s (`$O/logs/J12-fix.linq4j-precheck.log`).
  The core module's plugins and dependencies are resolved by the job's first, online step; the later steps are offline.

The job's command for the fix (the parent is the same in its worktree):

```bash
cd $O/worktrees/J12-calcite-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem $O/tools/apache-maven-3.5.4/bin/mvn -B \
  -s $O/scripts/maven-settings-https-central.xml [-o] -Drat.skip -Dcheckstyle.skip -Dmaven.javadoc.skip -Dmaven.source.skip \
  -DfailIfNoTests=false -pl core -am -Dtest=CoreQuidemTest package
```

Surefire there runs with `user.language=TR`, `user.country=tr` and `-Xmx1536m` (the POM's configuration). `CoreQuidemTest` is
parameterized over every `sql/*.iq`, not only `agg.iq`.

**For the domain agent**
- The release pair also changes Jackson, SnakeYAML and Janino; Janino compiles the generated accumulator code, so it is part
  of what "bind the generated accumulator" depends on.
- The job's results (and whether the offline form worked) are to be recorded when it has run.

### J13 · Apache Maven #13102

Pins: parent `c7b164f76189be25a2c6a48ffe74ff3afc39fcc2`, fix `9da38851f517281d66b1b05d25b8785dcc9e7fc9` (worktrees
`$O/worktrees/J13-maven-{parent,fix}`). Project version `4.1.0-SNAPSHOT` (Maven master, `javaVersion` 17). The only
production change is `compat/maven-artifact/.../versioning/ComparableVersion.java`; the PR adds tests to
`ComparableVersionTest`, `DefaultArtifactVersionTest` and `VersionRangeTest`.

**Release (common support).** `$O/releases/maven-artifact-3.9.12/`:

| Jar | sha256 |
|---|---|
| `maven-artifact-3.9.12.jar` | `4361cecd7e863c0992a6c901202afbb6db2a06b4f9a5e4b22481d4d39bcf137c` |
| `plexus-utils-3.6.0.jar` | `27ef130e32c236090e408fb5498d94cb9ea26d14070fb1c8985d607b62d098d1` |

Ordered classpath: `$O/releases/maven-artifact-3.9.12/classpath.txt`. 3.9.12's class files are major 52. **The 3.9.12
release behaves like the parent** (the range throws; the fold has a cycle). The pinned `compat/maven-artifact` sources
differ from 3.9.12's in 25 files, `ComparableVersion` by about 400 lines, `DefaultArtifactVersion` 69, `VersionRange` 42,
`Restriction` 41, `DefaultArtifact` 130.

**Overlays.** The pinned sources use Java 14–16 syntax (switch expressions, `instanceof` patterns), so they do **not**
compile with `--release 8`; they were compiled with javac 17.0.21 `--release 17` (class major 61) over the 3.9.12
classpath. They need JDK 17 or later to run. Two variants, because the brief's "comparator, artifact-version, range and
artifact sources" does not name files:

- `comparator`: `ComparableVersion.java` alone (the changed file). `$O/overlays/J13-comparator/{parent,fix}/`, 8 classes.
- `named`: `versioning/ComparableVersion.java`, `ArtifactVersion.java`, `DefaultArtifactVersion.java`, `VersionRange.java`,
  `Restriction.java`, and `org/apache/maven/artifact/Artifact.java`, `DefaultArtifact.java`, `ArtifactUtils.java`.
  `VersionRange` at the pins calls `DefaultArtifact.empty(String)`, which is private in 3.9.12, so `DefaultArtifact`
  (and with it `ArtifactUtils`) had to be included. `$O/overlays/J13-named/{parent,fix}/`, 15 classes.

| Overlay jar | sha256 |
|---|---|
| `$O/artifacts/J13-maven-parent-overlay-comparator.jar` | `f4c274bc711f11df5a2d61c39d7a622ce17d148c17bef8492a56d43d54f78104` |
| `$O/artifacts/J13-maven-fix-overlay-comparator.jar` | `84976e0cd611053698e434b1e8189bcad5f5f0db5726ad16382c7c4902c31578` |
| `$O/artifacts/J13-maven-parent-overlay-named.jar` | `00b2c62cf3664804c31583a0c631bf470822397a2ad8faaab121cde640aa6913` |
| `$O/artifacts/J13-maven-fix-overlay-named.jar` | `d7cd6b8fee7b8e86600eb5b1515bf32e567586bdcca9a4faa923510529d603dd` |

Every class digest is in `$O/logs/J13-overlay-{comparator,named}.txt`. Only four classes differ between the sides:

| Class | parent | fix |
|---|---|---|
| `ComparableVersion` | `5555c4a6e56280454099c89b94cab108fd981365b10786074d4a0739d068a814` | `d660e2ab32112c1ab903b30d2d6c849926a892caa462d36982eb32e23927bef0` |
| `ComparableVersion$CombinationItem` | `d47c29a1f6898aaa62bfa0666154afe185597587372641699a2783e1767047b1` | `0887e42228f9ce4cdc88c1d4db3152820b3d0b3b58da2753374e9c42f45d9651` |
| `ComparableVersion$ListItem` | `752e0ce777a68a94f51f43e269531065895bcf26ce6f1979fab3fc62707ef663` | `c5a8f891e40bc2c9e38b8f3099e5c3b735dd36703181cc2d48779ae9cf96e355` |
| `ComparableVersion$StringItem` | `f0c2434bd5c41f5f247481f3bec4caf6a65d8d6204a6022eed0e66a195058904` | `a58f48fdf2873f3be869382575f041d95ed72b8e2c01b7e7689530eee2957f2c` |

The other classes are identical on both sides: `VersionRange` `9af39be2966497b7c810f4eb3329d8fba8f5fa434db673d7134a020e031dac27`,
`Restriction` `013aa29942f8083a6c5bb0b412b4c01f0e96ce4f8bbafbaf7f482d1a218e8498`, `DefaultArtifactVersion`
`92f271d5a876c4fbd032f6db85357bf8e942afe5a332c43fffe5bcc3fbe405d2`, `DefaultArtifact`
`7b3ad803bb499f750268b1a924dcfc72a2bf8b8b0722e17796d0f9298198e266`.

**Built jars** (`compat/maven-artifact` alone, Maven 3.10.0 on JDK 17.0.21; no runtime dependencies):

| Jar | sha256 | `ComparableVersion.class` sha256 |
|---|---|---|
| `$O/artifacts/J13-maven-parent-maven-artifact.jar` (4.1.0-SNAPSHOT) | `470fc7d27ff5c1a4d402fcd8597e75e62ac1836dd2c96a4b25a02c8709110301` | `25118b87e65552b933938060fe4c98a8f21428642eb1b09712acc69a25624250` |
| `$O/artifacts/J13-maven-fix-maven-artifact.jar` (4.1.0-SNAPSHOT) | `918e3321bf0091ee2d55715184f063777368d55fd9a68e0a285bc55ee11bb487` | `427d06bea256ba4aa396adb771f6a06d771ec6b345820d642c30abbef8224fd2` |

**Landed tests** (upstream build of `compat/maven-artifact`, inline, about 10 s; logs `$O/logs/J13-maven-*.log`):

| Step | `VersionRangeTest` | `ComparableVersionTest` | `DefaultArtifactVersionTest` |
|---|---|---|---|
| fix (online, then offline) | 12/12 pass | 34/34 pass | 11/11 pass |
| parent's own | 10/10 pass | 26/26 pass | 8/8 pass |
| fix's three files transplanted onto the parent | **1 failure, 1 error** | **7 failures** | **3 failures** |

Failing on the parent: `VersionRangeTest.testZeroPrefixedQualifierRange` (error: `InvalidVersionSpecificationException:
Range defies version ordering: [0-alpha,x]`), `VersionRangeTest.testZeroPrefixedReleaseQualifierRange`;
`ComparableVersionTest.testZeroPrefixedQualifiers`, `testQualifierWithLongZeroDigit`,
`testReleaseZeroMixedQualifierTransitivity`, `testZeroPrefixedQualifierOrderingProperties`,
`testZeroPrefixedReleaseQualifierWithZeroDigit`, `testMng6568`, `testNestedQualifierListOrdering`;
`DefaultArtifactVersionTest.testReleaseQualifierWithZeroDigitEqualsAndHashCode`,
`testZeroPrefixedQualifierEqualsAndHashCode`, `testNestedQualifierListEqualsAndHashCode`.

Command (the offline form was run for all three steps):

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp
SK="-Drat.skip -Djapicmp.skip -Danimal.sniffer.skip -Dcheckstyle.skip -Dspotbugs.skip -Dpmd.skip -Dcpd.skip -Djacoco.skip \
    -Dmaven.javadoc.skip -Dcyclonedx.skip -Dspdx.skip -Drevapi.skip -Dmaven.source.skip -Dbnd.baseline.skip \
    -Dsurefire.failIfNoSpecifiedTests=false -Dspotless.check.skip -Dspotless.apply.skip"
cd $O/worktrees/J13-maven-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK \
  -pl compat/maven-artifact '-Dtest=VersionRangeTest,ComparableVersionTest,DefaultArtifactVersionTest' package
  # jar: compat/maven-artifact/target/maven-artifact-4.1.0-SNAPSHOT.jar
```

**Setup probe** (`$O/probes/J13/RangeProbe.java`, JDK 21.0.13, output `$O/logs/J13-probe.txt`). Both overlay variants over
3.9.12 and both built jars give the same results side for side:
- parent (and 3.9.12 alone): `VersionRange.createFromVersionSpec("[0-alpha,x]")` throws `InvalidVersionSpecificationException:
  Range defies version ordering: [0-alpha,x]`. A highest-version fold with `ComparableVersion` over the six orders of
  `0-alpha, 0, x` gives `x, 0, x, 0-alpha, 0, 0-alpha`: three winners, each twice.
- fix: the range is constructed, `matchVersion` selects `x` in all six orders, and the fold gives `x` six times.
- `1-alpha < 1-beta` on every classpath.

This is the brief's statement.

For the domain agent:
- The overlays need JDK 17+ (class major 61) even though 3.9.12 itself is major 52.
- Which files make up the brief's "comparator, artifact-version, range and artifact sources" is not settled: the
  `named` variant is the smallest set around the range that compiles; the `comparator` variant is the changed file alone.
  They behave the same in the probe.
- The 3.9.12 release behaves like the parent.

### J14 · Apache Lucene #15727 — missing child values in ToParentBlockJoinSortField (overlay over Lucene 10.4.0; upstream build queued)

**Pins.** Parent `182ee9c4cc3bc52ace12e699248b750377a3aa2f`, fix `167503f6d84d8e43db4ec6ae3baf17337290393f` (squash, parent = the brief's).
The pins are Lucene **11.0.0-SNAPSHOT** on `main` (`build-options.properties` `version.base=11.0.0`), with `minJava = "25"`
(`gradle/libs.versions.toml`). Changed production files: `lucene/join/src/java/org/apache/lucene/search/join/{BlockJoinSelector,ToParentBlockJoinSortField,ToParentDocValues}.java`;
tests `TestBlockJoinSelector` and `TestBlockJoinSorting` (`lucene/join/src/test/...`).

**Release set.** `org.apache.lucene:lucene-join:10.4.0` and `lucene-core:10.4.0` exist on Central; their classes are major 65
(**Lucene 10.4 needs JDK 21**). `J14-testdeps` is `lucene-test-framework:10.4.0` for the overlay test run only.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `lucene-10.4.0` | `lucene-join-10.4.0.jar` | `6fdb7e7388d6f3ec015f8159a179b367dbc7e505a6b46ecc4bf5d4a44a6f624b` |
|  | `lucene-core-10.4.0.jar` | `8f894d211a8123938ccb9ff6827d136747e0eb6b1782ada6ac9086aa911b52e2` |
| `J14-testdeps` | `lucene-test-framework-10.4.0.jar` | `0b530e2bbaad53b655ac31c5b3c226a2633010fc5831e6b7c04be1e84942100a` |
|  | `lucene-core-10.4.0.jar` | `8f894d211a8123938ccb9ff6827d136747e0eb6b1782ada6ac9086aa911b52e2` |
|  | `randomizedtesting-runner-2.8.1.jar` | `38302cf4c5a8ba4bf0ff2f707340dcd230657b3a766d9df6e3783cce19c5acb5` |
|  | `junit-4.13.1.jar` | `c30719db974d6452793fe191b3638a5777005485bae145924044530ffa5f6122` |
|  | `hamcrest-2.2.jar` | `5e62846a89f05cd78cd9c1a553f340d002458380c320455dd1f8fc5497a8a1c1` |
|  | `lucene-codecs-10.4.0.jar` | `1046679f2eb254fe59c36112daf05e29fa04fce785d6f9b5cc6ada2e5ba01d32` |

Runtime classpath: `$O/releases/lucene-10.4.0/classpath.txt` (lucene-join, lucene-core).

**Which side 10.4.0 is on.** All three changed files in `lucene-join-10.4.0-sources.jar` are byte-identical to the **parent**:
- `BlockJoinSelector.java` `1e04abf268bd1ef369ecbfe6a12eca5dd2d959d82504281d12448b778b46c924` (fix `09d6c008dc22ace9d4a923f47bc9d4d49b78b9268a89bf443f2a55c45fca5e61`)
- `ToParentBlockJoinSortField.java` `03a0e6fb1367c57817a76b17cea8f39bba7870749ff3963f1cf4c341bdeac963` (fix `c27c051b34cd339eb481cdc0cba18cc1c45cde6aa433d6042f4075ead431be71`)
- `ToParentDocValues.java` `74a1f0e477d5127c8b292e7279a0bb47ad983c11a8d3e50dcf97a0de4cd37745` (fix `970845008ad4cd9cbfe9c202d462fcae4deed80607dc7e52f935979ed32efe2e`)

**Overlay**: javac 25.0.5 `--release 21` over the release classpath (both sides compile against 10.4.0 unchanged).
- `$O/artifacts/J14-lucene-parent-overlay.jar`: `a6da3576e882fa0c1760822ebe825c9328cfd9854db09b4cd742d63fdbf54a79`
- `$O/artifacts/J14-lucene-fix-overlay.jar`: `600869bff721f7e75ca24d00dfb67bdf32240c444854e8c5647b2804f7537107`

(The first build of these jars was packed with JDK 25's `jar` and differed only in the manifest's `Created-By`; the class digests below are
the same in both builds, and the tests and the probe were rerun on the jars above.)

| Class | parent overlay | fix overlay |
|---|---|---|
| `org/apache/lucene/search/join/BlockJoinSelector$1.class` | `963be6e341fa3fc7187ff4d75131d0cd60186573ce108b38002208b16738dae4` | the same |
| `org/apache/lucene/search/join/BlockJoinSelector$Type.class` | `85de4ed52386bfaae22f434188372be85be8771e182f4c5e790d46b74e8a633f` | the same |
| `org/apache/lucene/search/join/BlockJoinSelector.class` | `dac046df5641c8733ebb4f28146b21f1f93ccd9a3820737cd025c3065a25574e` | `a2e3f6da175c2997e030e669524c0a318cbf35bf35f95ae2899e261952ce92af` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$1.class` | `67376bb2d1b2aaa3785694dce3a290c40715796f3a2e007ff4cfcd0175843b20` | `5c9b798f804068ee86247323c838e955acd6ad2668b72b69511a05ef04f36a02` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$2$1.class` | `fd9591d05d91ed825786899b47235382db40d2a67d42b102726aff7883258a93` | `cb0a6c6e1c81404b06892abe889f0cbbcd45e70f8601717ccaac529f89205144` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$2.class` | `4499e9bec02452d8ae43cbfeeeed2949001aa68bcf7fbbd9e85854c0d9634023` | `4b12fe7b69df08d68f5b55913e3aa64956313ba7e59b14f96f9148bd7ba274f2` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$3$1.class` | `910289bc830c8b6723035439afbe5aca808581a3b579ac1340fd677ba5a10007` | `c1c8f62f8359fb4d2ee781780209a551f6d07d62c4a4f886e096b02a89a789d9` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$3.class` | `82cd97cbe7eacfa562c31fabc9cd4f8ed5dafc252fbe0acaa3896d423f58c873` | `11598da102659559097acc3ccbfa50d4b44ee214d88650d21550f3a7112d5540` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$4$1$1.class` | `e01804790917c09af3bf86c9c9d0fa215913450a85f5dd2d33b62b2535fb67aa` | `c49715a099cfc0d38d9c3a0ad9363f214e7459c4ca6614388e449136ea5f8273` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$4$1.class` | `992a604595ccd24745d2d4c469262585d207d451d81c89af74ac329fe7da5d85` | `0796442716dd61791df5a78493e309071ed40f3b31e9be31f1eaed8f8bcf65cd` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$4.class` | `ffe6d6d683d70b8915b4c824a5fff46f8f29928cb91af8d6f6744f33b80ac2da` | `fbfbb61fe31c4d43efa66af0282bde3965ac57d3d15081a95aaad9227ea5e21c` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$5$1$1.class` | `a8a8b3ca1fa2d0bc004219707829c675942396bdeaf29d2384041f0c0516cefd` | `5fd61e097f353860a5769dd4d2d09263aa34efefe1cd91056b583019a9dc039b` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$5$1.class` | `e292b647e5bb255452c19cdf4556de641e16f57375b11da396719100cae3d795` | `31f773a2953aac1616026edd514261c27a46d4ee996a5c95f57a5176a1e295ac` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$5.class` | `e802428d48d745c5a2c7cc6bb28c1e677983b6c3766f64675aab4785d71b1428` | `64cc668d7c1c9aae558d116fcdd7e46be10be219675d14622fd6b5d63d915d7d` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField$6.class` | `d3dd0af15b4d03a5131cfdafe49a0207f7f879608b0d1e60529c0c76a3b53f52` | `28202024a2bb1fec7faf4abe6d094ba003b60d1dfcce03ec2eda6ddb5496185c` |
| `org/apache/lucene/search/join/ToParentBlockJoinSortField.class` | `81296b791fe40ed1ee29ebff610f8462987002f8bece7be103420ab73ff9e9ab` | `a2a819cf161eb4ac2ff6cccd723bc72c68880d37d7888ffdcce1e90605852833` |
| `org/apache/lucene/search/join/ToParentDocValues$1.class` | `7a231a26474e4b06855796425dff5730684b23d5134e620cb6498b8b2275ba97` | `761d140797f16c4091cc1b207700bede4f4e1d08f4f746b590c12c37743fd940` |
| `org/apache/lucene/search/join/ToParentDocValues$Accumulator.class` | `cd834e7db8808b8af6ce2a0fd53485b2f1d3da1d9097d18162bb88d945fc2da3` | `cf96978210fc13db7cb227cd58d88ef20417b00435728c8a5c66197eb144833a` |
| `org/apache/lucene/search/join/ToParentDocValues$NumDV.class` | `0432c1fbd62f6ff271883e96b9a2cdb94f6983d14cdcb74b63dedfba67fe0d0b` | `b0c81e217d2305f9e06a3bd9cff4a45b8822f27247c6dd70229a8662a31431a0` |
| `org/apache/lucene/search/join/ToParentDocValues$SortedDVs.class` | `c9590d7df7284a45f26550b7ecc9019696375dc8f56e55b35026f73abd343c69` | `2b04efa3768d0e8d392d85ee7e9066faa96fd963387410f10d2e1051a50e2fdc` |
| `org/apache/lucene/search/join/ToParentDocValues.class` | `488727779a7e121899e24bca16725d121b4a55ae1dbbb59105c7183668458f20` | `980da399ad5eb901aea552ff5385ebfd56adf93aabfa95272fde04b46b1f92a4` |

**Landed tests over the overlay** (`$O/scripts/overlay_test_c.sh`, JUnitCore on JDK 25.0.5 with `-Dtests.seed=DEADBEEF -Dtests.asserts=true -ea`,
classpath: overlay jar, the 10.4.0 jars, `J14-testdeps`). This is an overlay run, not an upstream run.

| Run | Result |
|---|---|
| fix tests on the fix overlay (`TestBlockJoinSorting` + `TestBlockJoinSelector`) | 7/7 pass (`TestBlockJoinSorting` alone: 3/3) |
| parent's own tests on the parent overlay | 4/4 pass (`TestBlockJoinSorting` alone: 1/1) |
| fix tests on the parent overlay | **do not compile**: `TestBlockJoinSelector` calls a five-argument `BlockJoinSelector.wrap(...,boolean)`, and `TestBlockJoinSorting` (11 errors) calls seven- and eight-argument `ToParentBlockJoinSortField` constructors; only the fix has them |

So the landed tests cannot show the difference on the parent. Logs: `$O/logs/J14-overlaytest-{fix,parent,transplant}.{sorting,sorting+selector}.log`.

**Probe** (`$O/probes/J14/MissingChildProbe.java`, JDK 21.0.13, output `$O/logs/J14-probe.txt`): the brief's preflight with the **five-argument**
constructor, which both sides have. Blocks A (children `30`, missing) and B (`20`, `40`) written to a `ByteBuffersDirectory`, reader reopened,
parents sorted by `ToParentBlockJoinSortField("sv", STRING, reverse, parents, children)`:

| Side | ascending | descending | total hits |
|---|---|---|---|
| parent overlay | `[B:"20", A:"30"]` | `[B:"40", A:"30"]` | 2 |
| fix overlay | `[A:null, B:"20"]` | `[B:"40", A:"30"]` | 2 |
| 10.4.0 release alone | `[B:"20", A:"30"]` | `[B:"40", A:"30"]` | 2 |

This is the brief's statement. The fix-only numeric overload and the 5/50 replacement are not probed.

**Upstream build: job `20261124-203513-setup-build-lucene-core-and-join-at-both`** (`verification/jobs/2026/11/24/20261124-203513-setup-build-lucene-core-and-join-at-both.json`,
written by `$O/scripts/submit_C.py`). It runs the upstream `./gradlew` on JDK 25.0.5: `:lucene:core:jar :lucene:join:jar` and the two landed test
classes (`-Ptests.seed=DEADBEEF -Ptests.jvms=4 --max-workers=4`) on the fix online, then on the parent (its own tests) offline, then the fix offline
again; jars to `$O/artifacts/J14-lucene-{fix,parent}-{core,join}.jar`; build trees removed. No transplant step (it cannot compile).
Before it, the setup ran `./gradlew :lucene:join:dependencies --configuration testRuntimeClasspath` online inline (8 s), which compiled
`build-infra` and resolved the test runtime graph (randomizedtesting-runner 2.8.4, junit 4.13.2, hamcrest 3.0). `versions.lock` is the same
at both pins.
- Lucene's `gradlew` downloads `gradle-wrapper.jar` from raw.githubusercontent.com and checks it against `gradle/wrapper/gradle-wrapper.jar.sha256`:
  `b3a875ddc1f044746e1b1a55f645584505f4a10438c1afea9f15e92a7c42ec13`, equal to services.gradle.org's 9.3.1 wrapper checksum. A copy is kept at
  `$O/dl/gradle/lucene-gradle-wrapper-9.3.1.jar`, and the job puts it in place (with the same check) so no step downloads it.
- The Gradle 9.3.1 distribution the wrapper unpacked into `$O/gradle-home/wrapper/dists/gradle-9.3.1-bin/` is identical (`diff -r`) to
  `$O/tools/gradle-9.3.1`, whose zip sha256 `b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06` is the published one.
- Run Lucene through `./gradlew`, not `gradle` directly: `gradlew` sets `-Djava.io.tmpdir=.gradle/tmp` and generates `gradle.properties`; without
  them Lucene's `WipeGradleTempPlugin` fails the build at shutdown (`NoSuchFileException .gradle/tmp`).

**For the domain agent**
- Lucene 10.4.0 carries the **parent's** three classes; the fix overlay is the fix side. The pins themselves are 11.0.0-SNAPSHOT (JDK 25).
- The landed tests use fix-only API, so they don't run on the parent; the probe is the discriminator.
- The overlay test framework is 10.4.0's (randomizedtesting 2.8.1); the upstream build uses its own (2.8.4).

### J15 · Spring Batch #495 (pinned source overlay over 3.0.7)

Pins: parent `1b35bff3ec0a681827e507562572f14550a6717f`, fix `0506d3793e50a606cd9739ce896de5d80b474e8e`
(worktrees `$O/worktrees/J15-spring-batch-{parent,fix}`, clean; branch `3.0.x`, version `3.0.8.BUILD-SNAPSHOT`).
**PR #495 is two commits** (`gh api .../pulls/495/commits`): the parent pin is the PR's own first commit, so the brief's pair is
the second commit alone. Changed production file: `spring-batch-core/.../repository/support/SimpleJobRepository.java`, the
tie-break in `getLastStepExecution`. No test changed.

The three versions of the comparison in `getLastStepExecution`:
- **3.0.7.RELEASE** (before the PR): `latest.getStartTime().getTime() < stepExecution.getStartTime().getTime()`; on a tie the first enumerated wins.
- **parent** (the PR's first commit): `<=`; on a tie the last enumerated wins.
- **fix**: `<`, then on equal times the larger `getId()` wins.

**Release** (`$O/releases/spring-batch-core-3.0.7`, `org.springframework.batch:spring-batch-core:3.0.7.RELEASE` from Central,
17 jars: spring-batch-infrastructure 3.0.7, Spring 4.0.5 aop/beans/context/core/expression/tx, spring-retry 1.1.0, xstream 1.4.7,
jettison 1.2, javax.batch-api 1.0, jbatch tck-spi 1.0, commons-logging 1.1.3, …). `spring-batch-core-3.0.7.RELEASE.jar`
`c77e58e893e007d9512e547431127c0c7555bc5c84f93cf1d76c34254dc0ad6a`, `spring-batch-infrastructure-3.0.7.RELEASE.jar`
`105e03783b17deef048735e0c15c132331ae94ffe3b7f97ce6c87c4899ba23e2`.

For the JDBC restart the brief asks for next, `$O/releases/spring-batch-jdbc-3.0.7` adds `spring-jdbc:4.0.5.RELEASE` and
`hsqldb:2.3.2` (the pin's `hsqldbVersion`; 19 jars). The schema scripts (`schema-hsqldb.sql` and 21 others) are inside
`spring-batch-core-3.0.7.RELEASE.jar`. Nothing was run against a database.

**Overlay** (`$O/scripts/overlay_D.sh`, javac 1.8.0_512 `-source 1.6 -target 1.6`, the pin's `sourceCompatibility` for core;
classpath `$O/releases/spring-batch-core-3.0.7/classpath.txt`, overlay jar first):

| Jar | sha256 | `SimpleJobRepository.class` sha256 |
|---|---|---|
| `$O/artifacts/J15-spring-batch-parent-overlay.jar` | `818fa7e12e70b723742be2276726d4142b0174cb8679da3d0ea8997e7ea65d98` | `9b6fb2bf1d755f86cdd14aa7c55ced84c4b2f212d99c64a2c75cfa9be683dcb6` |
| `$O/artifacts/J15-spring-batch-fix-overlay.jar` | `efd75a29f660f121beaf586dd1c72460dadc86f22bca1fb6853cba3e6a1cc436` | `f5f0cf6eda1dc4d4a612f2c8a0515a319005832b7e79e92ddf2b66b15747bd4a` |

**Probe** (`$O/probes/J15/LastStepProbe.java`, JDK 21.0.13; `$O/logs/J15-probe.txt`). Stub DAOs by `java.lang.reflect.Proxy`:
`findJobExecutions` returns two `JobExecution`s (ids 10, 11) of one `JobInstance` in a chosen order, each holding one step
execution named `step` (ids 1 and 2); `addStepExecutions` does nothing; the execution-context DAO returns
`marker=saved-by-<id>` for a step execution. `getLastStepExecution(instance, name)`:

| Case | parent overlay | fix overlay | 3.0.7 release alone |
|---|---|---|---|
| same start, order [1,2] | id=2, saved-by-2 | id=2, saved-by-2 | id=1, saved-by-1 |
| same start, order [2,1] | id=1, saved-by-1 | id=2, saved-by-2 | id=2, saved-by-2 |
| id 1 one second later, [1,2] | id=1 | id=1 | id=1 |
| id 1 one second later, [2,1] | id=1 | id=1 | id=1 |
| unknown step name | null | null | null |

The parent and fix columns are the brief's statement. The restored marker follows the selected id in every row.

**No upstream build.** There is no landed test. The pin's Gradle 2.12 build declares `https://repo.spring.io/plugins-release`,
`libs-milestone` and `libs-snapshot` (all answer **401** now) and `https://m2.neo4j.org/content/repositories/releases`
(no answer). Its buildscript plugins would have to be substituted, and the brief's evidence is the overlay, so the setup
did not try. The Gradle 2.12 distribution's `.sha256` URL on services.gradle.org still answers (301 redirect).

**For the domain agent**
- 3.0.7.RELEASE itself is neither side: it predates the PR and has its own order dependence (first enumerated wins).
- The parent pin is mid-PR (BATCH-2630's first commit); the brief's question is the second commit's change.
- For the JDBC-backed restart, `spring-batch-jdbc-3.0.7` has the jars; the DAO enumeration order there is the SQL's, not controlled.

### J16 · JGraphT #941 (pinned source overlay over JGraphT 1.5.1)

- **Release** `org.jgrapht:jgrapht-core:1.5.1`, resolved with strict checksums into `$O/releases/jgrapht-core-1.5.1/`:
  `jgrapht-core-1.5.1.jar` `a4d810cb63e0a77a753d147094fea9dd42e82cfc57aa289f9f85229f26043bb4`, `jheaps-0.13.jar` `63414290c3497f8ac0f102209207088dec46fd4747e0f56a26c69308e85c6415`.
- The pins are version **1.4.1-SNAPSHOT** (June 2020); the release is 1.5.1 (class files major 55).
- **Overlay**: `jgrapht-core/src/main/java/org/jgrapht/graph/AsWeightedGraph.java` at each pin, javac 17.0.21 `--release 11` (the POM's release) over the release classpath.
  One class each (`$O/overlays/J16/{parent,fix}/classes`):

| | parent | fix |
|---|---|---|
| overlay jar (`$O/artifacts/J16-jgrapht-ROLE-overlay.jar`) | `3d7eed8543f2e84b60650d356c63ecc96e3a277af0f1d5b10c6ae5859808fdd4` | `c0df756fdf05cede6a5b00d5844cd1bace3d37b12c874bcfbd9abb828bf440b0` |
| `org/jgrapht/graph/AsWeightedGraph.class` | `d00d07af112ad8f784c288d74a0245d9cf7af7dc3f2a69ad6f779b5397081351` | `6900426dd68dfb000491d01db71085f7308cdda484007f65d6885d713f84a9e7` |

  Classpath: `$O/artifacts/J16-jgrapht-ROLE-overlay.jar:$(cat $O/releases/jgrapht-core-1.5.1/classpath.txt)`. The fix's source differs from
  1.5.1's `AsWeightedGraph.java` only in the copyright year and the formatting of the new `throw`.
  The change: `setEdgeWeight` replaced `assert weightFunction == null || cacheWeights` with `throw new UnsupportedOperationException(...)` when a weight function is used and caching is off.
- **No landed test.** **Probe** (`$O/probes/J16/WeightProbe.java`, JDK 21.0.13; `$O/logs/J16-probe.txt`): a `SimpleWeightedGraph` edge with backing weight 2,
  `new AsWeightedGraph<>(g, e -> 7.0, cache, true)`, `setEdgeWeight(e, 9)`, then both handles read:

| Side, profile | cache off, write-through on | cache on, write-through on |
|---|---|---|
| parent `-da` | returned; view 7.0, backing **9.0** | returned; 9.0 / 9.0 |
| parent `-ea` | `AssertionError`; view 7.0, backing 2.0 | returned; 9.0 / 9.0 |
| fix `-da` | `UnsupportedOperationException`; view 7.0, backing 2.0 | returned; 9.0 / 9.0 |
| fix `-ea` | `UnsupportedOperationException`; view 7.0, backing 2.0 | returned; 9.0 / 9.0 |

  This is the brief's statement in both assertion profiles.
- **For the domain agent**: no upstream build was made (the brief's evidence is the overlay). The overlay class shadows the release's by classpath order.

### J17 · Eclipse Collections #786

Pins: parent `9084111e068612ebf817a3fa6fe80d9623df4c29`, fix `7ce7a19722e5471a71a2799737c3c2a0ed5510ff` (worktrees
`$O/worktrees/J17-eclipse-collections-{parent,fix}`). Project version `10.2.0-SNAPSHOT`. The only production change is
`eclipse-collections/src/main/java/org/eclipse/collections/impl/map/mutable/UnifiedMap.java` (the `removeIf` loop); the
landed test adds three collision maps to the `removeIf` test of the interface
`unit-tests-java8/.../test/map/mutable/MutableMapIterableTestCase.java` (the assertions sit inside an existing test
method, so test counts do not change).

**Release (common support).** `$O/releases/eclipse-collections-10.2.0/`:

| Jar | sha256 |
|---|---|
| `eclipse-collections-10.2.0.jar` | `5c2a53c4442c54bb278564922772c531437f65151802f9a2efa312fb43adccc6` |
| `eclipse-collections-api-10.2.0.jar` | `18e623235a8e8871e6e489bf55a25d9d448ceb740b854dd4c8c3a925a1dff125` |

Ordered classpath: `$O/releases/eclipse-collections-10.2.0/classpath.txt` (class major 52). **The 10.2.0 release
contains the fix**: its `UnifiedMap.java` source is identical to the fix pin's; the parent pin differs by 45 lines.

**Overlay** (javac 17.0.21 `--release 8`; `UnifiedMap` and its 11 inner classes, `$O/overlays/J17/{parent,fix}/`, every
class digest in `$O/logs/J17-overlay.txt`):

| | parent | fix |
|---|---|---|
| overlay jar `$O/artifacts/J17-eclipse-collections-{side}-overlay.jar` | `73c80baaee881f5a1ededfab727a34c450efb5f08fe5f0f49578e48f1f6afc72` | `85cf792bf2d887c10229ff8f31a0a906715e7d9afe82594e6c0cfde227ddc094` |
| `UnifiedMap.class` | `99f5fe0a00409d347d16e3d3cb2c6fdc1f9e559f14999dc065d6e46d14938521` | `469788c63dc52235ea870c7970cac89f2d30e4e0a4d4cc9d4da4bb22829b809d` |

`UnifiedMap$1` and `UnifiedMap$2` are identical on both sides; the other inner classes differ (constant-pool shifts).
With the overlay first, `-verbose:class` shows `UnifiedMap` loaded from the overlay jar.

**Which tests run the landed interface.** Ten concrete classes in `unit-tests-java8` implement
`MutableMapIterableTestCase` (directly or through `MutableMapTestCase`/`UnsortedMapIterableTestCase`):
`UnifiedMapTest`, `UnifiedMapNoIteratorTest`, `strategy.UnifiedMapWithHashingStrategyTest`,
`UnifiedMapWithHashingStrategyNoIteratorTest`, `UnmodifiableMutableMapTest`, `SynchronizedMutableMapTest`,
`MapAdapterTest`, `ConcurrentHashMapTest`, `ConcurrentHashMapUnsafeTest`, `ConcurrentMutableHashMapTest` (all in
`org.eclipse.collections.test.map.mutable`). The tests use the `junit-trait-runner` reactor module, which is not on
Maven Central.

**Landed test over the overlay (not an upstream run).** `$O/probes/J17-overlay-test/`: `junit-trait-runner` (fix pin
source) and each side's whole `unit-tests-java8/src/test/java` (184 classes) compiled with javac 17 `--release 8` over
`$O/releases/J17-test-support/` (eclipse-collections and -api 10.2.0, eclipse-collections-testutils 10.2.0
`c85ad49854a74e2a8c1f6eaa42a9c0d18b9351583c8e2ac35f083af4de41d954`, junit 4.12
`59721f0805e223d84b90677887d9ff567dc534d7c502ca903c0c2b17f05c116a`, hamcrest-core 1.3
`66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9`, hamcrest-library 1.3
`711d64522f9ec410983bd310934296da134be4254a125080a0416ec178dfad1c`). The ten classes run with `JUnitCore` on JDK
21.0.13 (`$O/logs/J17-overlay-test.txt`):

| Overlay first | Test sources | Result |
|---|---|---|
| fix | fix | OK, 960 tests |
| parent | parent | OK, 960 tests |
| parent | fix (landed assertions on the parent) | OK, 960 tests |
| none (10.2.0 alone) | fix | OK, 960 tests |

As the brief says, this is a preservation case: the landed collision assertions pass on both sides.

**Upstream build**: queued as job `20261124-203508-setup-build-eclipse-collections-at-both`
(`verification/jobs/2026/11/24/20261124-203508-setup-build-eclipse-collections-at-both.json`, `$O/scripts/submit_B.py ec`).
`-pl unit-tests-java8 -am` builds the code generator, its Maven plugin, api and impl (generated primitive collections),
testutils and the trait runner, which is over the inline limit. Maven 3.10.0 on JDK 8 (upstream CI used JDK 8; the
reactor was validated online inline), `install` into `$O/m2` as upstream CI does; first step online, the rest offline;
the transplant step expects a pass. Results: pending.

```bash
O=~/.cache/in-the-loop/organic-pr-20; export TMPDIR=$O/tmp
cd $O/worktrees/J17-eclipse-collections-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem mvn -B -o -s $O/maven-settings.xml \
  -Dmaven.javadoc.skip -Dcheckstyle.skip -Dfindbugs.skip -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false \
  -pl unit-tests-java8 -am '-Dtest=UnifiedMapTest,UnifiedMapNoIteratorTest,UnifiedMapWithHashingStrategyTest,UnifiedMapWithHashingStrategyNoIteratorTest,UnmodifiableMutableMapTest,SynchronizedMutableMapTest,MapAdapterTest,ConcurrentHashMapTest,ConcurrentHashMapUnsafeTest,ConcurrentMutableHashMapTest' install
```

(The job passes the longer skip list in `$O/scripts/submit_B.py`.)

For the domain agent:
- The 10.2.0 release already has the fix's `UnifiedMap`: the parent's loop exists only as the parent overlay first on the classpath.
- No regression is expected anywhere: report it as preservation. The brief's 127-subset sweep was not reproduced by the setup.

### J18 · Caffeine #194 — JCache maximum size with expiry (overlay over Caffeine/JCache 2.6.1 and JCache API 1.0.0)

**Pins.** Parent `5473cab8afb17ec7aa288b57d74d81de6372351e`, fix `78be027a7e89e750e3a1cc27584d7a8224d164bf` (one commit; the PR's head is the
fix). Changed: `jcache/src/main/java/com/github/benmanes/caffeine/jcache/CacheFactory.java`; new test
`jcache/src/test/java/com/github/benmanes/caffeine/jcache/expiry/JCacheExpiryAndMaximumSizeTest.java` (TestNG; absent on the parent).

**Release set.** `jcache-2.6.1`'s POM declares `javax.cache:cache-api:1.1.0`; the setup's resolution names `cache-api:1.0.0` directly, as the brief
does (it is also the version the pins build with: `gradle/dependencies.gradle` `jcache: '1.0.0'`), so 1.0.0 wins. `jsr305-3.0.2` is compile-only
(`CacheFactory` imports `javax.annotation.Nullable`; Caffeine's build has it as `provided`). `J18-testdeps` is for the overlay test run only.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `caffeine-jcache-2.6.1` | `jcache-2.6.1.jar` | `a08b844ccab7547bcdae7f18a7175c81edbbcc070d852dfd0b1615f1104a8884` |
|  | `config-1.3.2.jar` | `6563d1723f3300bf596f41e40bc03e54986108b5c45d0ac34ebc66d48c2e25a3` |
|  | `javax.inject-1.jar` | `91c77044a50c481636c32d916fd89c9118a72195390452c81065080f957de7ff` |
|  | `caffeine-2.6.1.jar` | `e45e7995bd0f9924e105691127d9b092f37ef314fab8364a2302a4dfb416d1ca` |
|  | `cache-api-1.0.0.jar` | `d2836213144722e2eb1d7461f6e2ea3349d6fbbf9cd5f345c7133bc29bd39ca1` |
| `jsr305-3.0.2` | `jsr305-3.0.2.jar` | `766ad2a0783f2687962c8ad74ceecc38a28b9f72a2d085ee438b7813e928d0c7` |
| `J18-testdeps` | `testng-6.11.jar` | `55d5897ac09339010eed2051124309a7127988d82ff0634228926d51da3540f6` |
|  | `jcommander-1.64.jar` | `156be736199c990321d9ff77090b199629cfc9865e2d6c13f7cd291bb1641817` |
|  | `snakeyaml-1.17.jar` | `5666b36f9db46f06dd5a19d73bbff3b588d5969c0f4b8848fde0f5ec849430a5` |
|  | `guice-4.1.0.jar` | `9b9df27a5b8c7864112b4137fd92b36c3f1395bfe57be42fedf2f520ead1a93e` |
|  | `javax.inject-1.jar` | `91c77044a50c481636c32d916fd89c9118a72195390452c81065080f957de7ff` |
|  | `aopalliance-1.0.jar` | `0addec670fedcd3f113c5c8091d783280d23f75e3acb841b61a9cdb079376a08` |
|  | `mockito-core-2.10.0.jar` | `b27f101c278c36957fa357e6803c258225df96a17aabf427a85a9c00313b1d67` |
|  | `byte-buddy-1.7.4.jar` | `17f9fc3b81f3c5b3d0ba3b6496f4512099c4755799e9786e38d53d3af0b42abf` |
|  | `byte-buddy-agent-1.7.4.jar` | `c0f43cc1813a9bdc93347b32033a19bc3619cb1527d177618ea6960fe053c839` |
|  | `objenesis-2.6.jar` | `5e168368fbc250af3c79aa5fef0c3467a2d64e5a7bd74005f25d8399aeb0708d` |
|  | `java-hamcrest-2.0.0.0.jar` | `09bc7044d57a497846e2480250e7a72ff3ae58efefc8c3a9ceecd0f4e092851c` |
|  | `guava-23.1-jre.jar` | `08aaaa2e67346e3a3e1508e7c6b12af77024403d0d6d87a78d8a7bcf3971f381` |
|  | `jsr305-1.3.9.jar` | `905721a0eea90a81534abb7ee6ef4ea2e5e645fa1def0a5cd88402df1b46c9ed` |
|  | `error_prone_annotations-2.0.18.jar` | `cb4cfad870bf563a07199f3ebea5763f0dec440fcda0b318640b1feaa788656b` |
|  | `j2objc-annotations-1.1.jar` | `2994a7eb78f2710bd3d3bfb639b2c94e219cedac0d4d084d516e78c16dddecf6` |
|  | `animal-sniffer-annotations-1.14.jar` | `2068320bd6bad744c3673ab048f67e30bef8f518996fa380033556600669905d` |
|  | `guava-testlib-23.1-jre.jar` | `f9a9cb70eb9d574c8b4a87236ff8347625bf88c862f09645948c612400e83ab3` |
|  | `junit-4.11.jar` | `90a8e1603eeca48e7e879f3afbc9560715322985f39a274f6f6070b43f9d06fe` |
|  | `hamcrest-core-1.3.jar` | `66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9` |

Runtime classpath: `$O/releases/caffeine-jcache-2.6.1/classpath.txt` (jcache 2.6.1, config 1.3.2, javax.inject 1, caffeine 2.6.1, cache-api 1.0.0).

**Which side 2.6.1 is on: neither.** `CacheFactory.java` in `jcache-2.6.1-sources.jar` is `01f406aaa862ac5745a4119944121cb92b54d26f358d85749ae869881e67f136`;
parent `e6661860ad326037207496787511aa987caca9f1aecf590081dd2397f378ee0c`, fix `926ea97048c883b162c8ce741fea2c19402a087fda6f27d0fc16e7c93ca53d12`
(2.6.1 was released after the fix and carries later edits).

**Overlay**: JDK 8 javac 1.8.0_512 `-source 8 -target 8`, release classpath plus jsr305 3.0.2 (compile only).
- `$O/artifacts/J18-caffeine-parent-overlay.jar`: `7068c59169dedb9c222b0797e577b86ef80d73bc9e48e8e7272121d84ea70551`
- `$O/artifacts/J18-caffeine-fix-overlay.jar`: `7db8b12c4e231cdb5ba6fcfcfdeb58fcdc51f97d6fd39d07705028dc54bdda49`

| Class | parent overlay | fix overlay |
|---|---|---|
| `com/github/benmanes/caffeine/jcache/CacheFactory$Builder$1.class` | `73d5c06dd32a6ffb86cf958421e141629451ec3862e94f63774b344b2cd27dd6` | the same |
| `com/github/benmanes/caffeine/jcache/CacheFactory$Builder.class` | `aeba9ccf71cf95590fb4a5f9a4f6c36fc13f03687929e3bf54213d1057ea22c6` | `080b4966b338c436ef623c1a0ec69736a5a73ae8158795eeee7616f602021f5c` |
| `com/github/benmanes/caffeine/jcache/CacheFactory.class` | `48fef53d941395ac06ea73baeb1d602a139f7b84a4b6e2ee001a9c83e222f6b1` | the same |

**Landed test over the overlay** (TestNG on JDK 8; classpath: `jcache/src/test/resources` of the fix (its `application.conf`), overlay jar, release
jars, `J18-testdeps`; test sources `JCacheExpiryAndMaximumSizeTest.java` `b2c2f42afee21a299d762c8d4ae0d7b4d7277a423f24bb415f83288074f965d8`
and its base `AbstractJCacheTest.java` `6465160664ac3228b4784f1eeb236273d633ca1dd459172bacd4aa4b3e736025`, the same at both pins):

| Run | Result |
|---|---|
| fix test on the fix overlay | 2/2 pass (`expiry`, `size`) |
| parent's own | none: the test file is new in the PR |
| fix test on the parent overlay | **`expiry` fails** (Mockito "Wanted but not invoked" on the expiry policy), `size` passes |

Logs: `$O/logs/J18-overlaytest-{fix,transplant}.log`, TestNG XML in `$O/overlays/J18/test-*/testng-out/`.

**Substitution: TestNG 6.11 for 6.12.** The pins' build names `org.testng:testng:6.12` (with guice 4.1.0); 6.12 is not on Maven Central (6.11 and
6.13 are), and JCenter now answers 404. The setup used 6.11, the nearest earlier release on Central. Mockito 2.10.0, java-hamcrest 2.0.0.0,
guava/guava-testlib 23.1-jre are the pins' versions.

**Upstream build: not practical.** Gradle 4.2.1 (distribution verified, `$O/tools/gradle-4.2.1`, zip sha256
`b551cc04f2ca51c78dd14edb060621f0e5439bdfafa6fd167032a09ac708fbc0`) on JDK 8 fails configuring the root project:
`io.spring.gradle:propdeps-plugin:0.0.10.RELEASE` comes from `http://repo.spring.io/plugins-release`, which answers 405 (it now needs
credentials), and TestNG 6.12 is missing as above. The project's `gradle-wrapper.jar` (`4425226080db24ddcdb01204ffb6c01e28f40a9fbef4cd0e4b3262905e697799`)
is Gradle 2.14.1-rc-2's, for which services.gradle.org publishes no checksum (404); it was not run. Log: `$O/logs/J18-caffeine-fix.resolve.log`.

**For the domain agent**
- Caffeine 2.6.1's `CacheFactory` is **neither** side; bind the overlay jars.
- cache-api 1.0.0 is forced over jcache 2.6.1's declared 1.1.0.
- TestNG 6.11 replaced the unavailable 6.12 in the overlay test run. No probe of the brief's `[20,20]` / `[null,null]` values was run; the landed
  `expiry` test is the discriminator.

### J19 · Resilience4j #892 — idempotent circuit-breaker transitions (overlay over Resilience4j 1.3.1)

**Pins.** Parent `4e564affebf280ba20880bdc8736b42f8f92234a`, fix `4ecc7c889cad7bfa6cb574af52252480f7e0d7cf` (squash, parent = the brief's).
Changed: `resilience4j-circuitbreaker/src/main/java/io/github/resilience4j/circuitbreaker/CircuitBreaker.java` and
`.../internal/CircuitBreakerStateMachine.java`; test `.../internal/CircuitBreakerStateMachineTest.java`.

**Release set.** `J19-testdeps` (junit 4.12, assertj-core 3.12.2, mockito-core 2.25.1, mock-clock 1.0: the pins' `libraries.gradle` versions) is
for the overlay test run only.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `resilience4j-1.3.1` | `resilience4j-circuitbreaker-1.3.1.jar` | `13ec2a66fe0ebc6f5391c7e80d0d9591b737668cb18113db14f048e71ce770cd` |
|  | `vavr-0.10.2.jar` | `1b2ae46cf352627e05b39ac1f1d3bda7b285a8f643cdc7472aea4aa279492e54` |
|  | `vavr-match-0.10.2.jar` | `5d7a9515b05e3291194e04e641acf74a9a544c1caa1e2c24f59a1424c6ec8288` |
|  | `slf4j-api-1.7.26.jar` | `6d9e5b86cfd1dd44c676899285b5bb4fa0d371cf583e8164f9c8a0366553242b` |
|  | `resilience4j-core-1.3.1.jar` | `ed0e473adaf6c46368e82b0e3d7729713ef4eddf282e7e18e5d58b35c00e43d4` |
| `J19-testdeps` | `junit-4.12.jar` | `59721f0805e223d84b90677887d9ff567dc534d7c502ca903c0c2b17f05c116a` |
|  | `hamcrest-core-1.3.jar` | `66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9` |
|  | `assertj-core-3.12.2.jar` | `f0d4eace1208744a61f021c580ae954a6c31b5884616e079bf6a84feff49397c` |
|  | `mockito-core-2.25.1.jar` | `60a2987f55d3948815ee9e542d40bbc013d4bb9c15227504408c6fb6b7dd0dd6` |
|  | `byte-buddy-1.9.7.jar` | `69a9140c11de463789a1badfe6c3dcdc17608c4304cb443c5c3a179585b78b39` |
|  | `byte-buddy-agent-1.9.7.jar` | `145ce0fab5390374e69b2b4070d65fedaa2b07c3cfad06b330bea1b6dcfa826f` |
|  | `objenesis-2.6.jar` | `5e168368fbc250af3c79aa5fef0c3467a2d64e5a7bd74005f25d8399aeb0708d` |
|  | `mock-clock-1.0.jar` | `d8566e33bbc32c528c7d41624d97ecc8389567a724c77f8d3599c3a3756f510f` |

Runtime classpath: `$O/releases/resilience4j-1.3.1/classpath.txt` (circuitbreaker 1.3.1, vavr 0.10.2, vavr-match 0.10.2, slf4j-api 1.7.26, core 1.3.1).

**Which side 1.3.1 is on: neither.** In `resilience4j-circuitbreaker-1.3.1-sources.jar`:
- `CircuitBreaker.java` `dfa6d5a5f056eb60874ab30454dbdf54843cc0c9c7d2474e517b4ef30d843ab6` (parent `896c006c7b42a613f3629df384974c9bf9fb8e13afb763562b8ce08006b3a59d`, fix `66b79538b1b4828d1644fde533ca553d2fb8ee2b9f0cbcb74e970db7d8b8e62d`)
- `CircuitBreakerStateMachine.java` `3981c501edca4afb96945ca84387a33632d4ccc2395691755a060185df1c4e71` (parent `124e3679d20a52b141d9e683e20464b7eec944184f7be0583a02989455cf04f3`, fix `dbc5de7f184b31f7ef84b0b186a38b3a524548f548662bb9251e893c5e59a9fc`)

**Overlay**: javac 17.0.21 `--release 8` over the release classpath; both files compile unchanged. All inner classes of both files are in the overlay.
- `$O/artifacts/J19-resilience4j-parent-overlay.jar`: `8fc2cc4e6d78ef867c8dbc87adea3df80bc6ac45df18de76b1fa987a6bc2f2a2`
- `$O/artifacts/J19-resilience4j-fix-overlay.jar`: `8c96138ef35c44e4f7134c737483f55e2db41512eeb9ced8df88e182a58f37e0`

| Class | parent overlay | fix overlay |
|---|---|---|
| `io/github/resilience4j/circuitbreaker/CircuitBreaker$CircuitBreakerFuture.class` | `1b51fa8f16d0fc0f10f423b43486ab9da3ac049d46171dbac87d7e2e377dd301` | `cce1d05769a1022012328fb2bd6f950db418c1d716cf3bde676fddd5bff5347d` |
| `io/github/resilience4j/circuitbreaker/CircuitBreaker$EventPublisher.class` | `bd05a01996f2ab8913a882871d3ffe75963435304fe005f0a7e4c5248fff59bd` | the same |
| `io/github/resilience4j/circuitbreaker/CircuitBreaker$Metrics.class` | `a401ce03e347876517b67e47452a25faf8bbf82bb3cfcd70f91b3eef1f864623` | the same |
| `io/github/resilience4j/circuitbreaker/CircuitBreaker$State.class` | `54b4319bb5718589b4d278fb98abd1cc9802d5c29c5006b00a85044cbd319043` | `fc2deda92a85b5d69a7d3be35bfb790e9f2547a1f5a27010a525bc8a9c9ba8c2` |
| `io/github/resilience4j/circuitbreaker/CircuitBreaker$StateTransition.class` | `4adf76044a52eb5f0ac55036ad5932b6054ecb339a30ccf618f7395ed5a8804a` | `04cfa551aaa3650a08a034317b6bdd2a0c2f9192097ee9d76e1901b7b682730f` |
| `io/github/resilience4j/circuitbreaker/CircuitBreaker.class` | `fa8fa066f649ae6e38c3eee624d1d96ad358eafac1ea47c783f7a2d8eddc8b00` | `8fb3b9c0686a507a9c56df1c15c801630b738cf0ed00557da38e0dcd9137bcc5` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$1.class` | `194f4f8893fc939d19d9da226ccdfa85f7b8b304f38d0ea23c896862e17635f5` | the same |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$CircuitBreakerEventProcessor.class` | `3d9ba489b6b5713f781e735e489b43fe604bbbc71174644151250317e5b69dad` | `023de0f0f232156cb67de1d7498698088b16de3b8a2ae3aebd377d12f2100f30` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$CircuitBreakerState.class` | `985f3957c122fac6e0cb4579ce58ecd236de4091365c30532e9c18b2de76f3df` | `5cf44e3034d460ac679da065e73967326f18aa9263b40949820da838efe35f78` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$ClosedState.class` | `7ee33e80bad6affa764f4ef3129b64d7b395cc4ddfde49bc9be111b54684c165` | `d0d3c83f8f7d3ee37da1fd31d41473adbea46c4a6598c848142206c6a12fb079` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$DisabledState.class` | `a8716317bff89e6553c61979c609919ee448ca6c9c39abc6e428ff381ef07220` | `d97e1758dd36c03a9d88d5eb37ab9f63cc0ea74d832c80a1fd29d904b6b4a2c7` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$ForcedOpenState.class` | `55a603121ba22758ced4c89cbe44b23d0834bde6ebc3bbd9bfd7b116412e340e` | `6e3891b8cebb7956a77f3dbfb695f0857416a6e56d4cc1043347d8febb70c4b6` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$HalfOpenState.class` | `fc1d5939ebc005899dab9049086408a5bab5812d02e46aac789b2292ebf16687` | `592018e9493e5ed7de95c524db2fe671cfe26ce7af8be9ba1777f698cd562949` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$MetricsOnlyState.class` | `5bedb877553ebbf6e83bd1d2397bf87b0d6a148b6773f38b3e038b5e2edce0fe` | `7fcf5208f47efb45f35774d4690b855c2cade50d82535d8ef2c2672f3ce7fdaf` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine$OpenState.class` | `61602343808946046911a48c91a0fa88ace69316ddff0e431deef7a047829fb7` | `411ce56d27afba5b4256240a0e62421989b2a51e555e0cf7e1c89df5624ca8fe` |
| `io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachine.class` | `bdbb918245e2294cc58eff6e50b4e2b95402fa107656e1a54ce328e1f7d9689a` | `c44a8a1013b8a4c5d900a035df026ce12f0a2f4134b7c0e5feb1b96730ad54e6` |

**Landed test over the overlay** (JUnitCore on JDK 8; test source at the fix `27537af637a1fee3a0dd40ac341f71437d7ba663c194298231c342844a32ad5f`):

| Run | Result |
|---|---|
| fix test on the fix overlay | 27/27 pass |
| parent's own test on the parent overlay | 25/25 pass |
| fix test on the parent overlay | **3 of 27 fail** with `IllegalStateTransitionException`: `circuitBreakerDoesNotPublishStateTransitionEventsForInternalTransitions` (OPEN to OPEN), `allCircuitBreakerStatesAllowTransitionToItsOwnState` (DISABLED to DISABLED), `allCircuitBreakerStatesAllowTransitionToMetricsOnlyMode` (METRICS_ONLY to METRICS_ONLY) |

Logs: `$O/logs/J19-overlaytest-{fix,parent,transplant}.log`. Command:

```bash
O=~/.cache/in-the-loop/organic-pr-20
$O/scripts/overlay_test_c.sh J19 resilience4j resilience4j-1.3.1 J19-testdeps 8.0.512.0+9-tem junit4 resilience4j-circuitbreaker/src/test/java \
  io.github.resilience4j.circuitbreaker.internal.CircuitBreakerStateMachineTest io/github/resilience4j/circuitbreaker/internal/CircuitBreakerStateMachineTest.java
```

**Upstream build: not practical.** Gradle 5.3.1 (distribution verified, `$O/tools/gradle-5.3.1`, zip sha256
`1c59a17a054e9c82f0dd881871c9646e943ec4c71dd52ebc6137d17f82337436`; the project's wrapper jar `660ab018b8e319e9ae779fdb1b7ac47d0321bde953bf0eb4545f14952cfdcaa3`
is Gradle 4.10.3's published wrapper) on JDK 8 cannot configure the root project: the root `plugins {}` block (sonarqube, bintray, jmh,
asciidoctor, artifactory) needs `org.jfrog.buildinfo:build-info-extractor:2.13.5` (only on releases.jfrog.io), `org.ysb33r.gradle:grolifant:0.10`
(only on repo.gradle.org) and `org.codehaus.groovy.modules.http-builder:http-builder:0.7.2` (found in none of Central, JCenter, the Plugin
Portal, releases.jfrog.io, repo.gradle.org). These are publishing and docs plugins, unrelated to the test; substituting them would mean
changing the build. JCenter itself now redirects to Central. Log: `$O/logs/J19-resilience4j-fix.resolve.log`.

**For the domain agent**
- Resilience4j 1.3.1's two classes are **neither** side; bind the overlay jars, which also replace `CircuitBreaker`'s nested types (`State`, `StateTransition`, …).
- The landed test's three failures on the parent are the repeat (same-state) transitions; the brief's event counts `1,1,2,2,3,3` were not probed.

### J20 · Micrometer #3369 — SignalFx timer percentiles (overlay over Micrometer 1.10.0)

**Pins.** Parent `41c9493e7f6781f4588906ed36cca87385a5a76c`, fix `f18f09fa8d782a39081856f9667827ae00af638a` (squash, parent = the brief's).
Changed: `implementations/micrometer-registry-signalfx/src/main/java/io/micrometer/signalfx/SignalfxTimer.java`; test
`.../src/test/java/io/micrometer/signalfx/SignalFxMeterRegistryTest.java` (JUnit 5).

**Release set.** `J20-testdeps` (junit-jupiter 5.9.0, junit-platform-console-standalone 1.9.0, assertj-core 3.23.1) is for the overlay test only.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `micrometer-1.10.0` | `micrometer-registry-signalfx-1.10.0.jar` | `c6e4ad7cd6b118d4aebba733205357ff6c9ce7a8bbb7ab02465b27dff310bac0` |
|  | `signalfx-java-1.0.25.jar` | `664fdbcc002cf3abce1c7746a29dfa42bec88967f66eef71a6b9664c5abddc12` |
|  | `slf4j-api-2.0.3.jar` | `68ddcda65300ff8097ad1a096d7cd2fb06cef25193887cec3f2690e01bdbf421` |
|  | `micrometer-core-1.10.0.jar` | `ece52bd972f554ffa023df61d4571728e719135573f594d69810d0b6886e82ce` |
|  | `micrometer-commons-1.10.0.jar` | `1da4fb8218c832fb443f99114d62d36997e3ecdbdd2d1b19c42adbd00de7db8e` |
|  | `micrometer-observation-1.10.0.jar` | `af6ff881c71ec62027b91dd1658459c211d261d9867a4552db8c7ffdf899455d` |
|  | `HdrHistogram-2.1.12.jar` | `9b47fbae444feaac4b7e04f0ea294569e4bc282bc69d8c2ce2ac3f23577281e2` |
|  | `LatencyUtils-2.0.3.jar` | `a32a9ffa06b2f4e01c5360f8f9df7bc5d9454a5d373cd8f361347fa5a57165ec` |
| `J20-testdeps` | `junit-jupiter-5.9.0.jar` | `2db2e4aa2b5e82fefcbf18d0af20c8095a43e94ad9ab9d16bd87557cdaa397dd` |
|  | `junit-jupiter-api-5.9.0.jar` | `3e370bcbb1e857fda5f0b203724116d02b05e788faa1eb2518814accf9cfb5b1` |
|  | `opentest4j-1.2.0.jar` | `58812de60898d976fb81ef3b62da05c6604c18fd4a249f5044282479fc286af2` |
|  | `junit-platform-commons-1.9.0.jar` | `e5894b710094b4caafc6280b8829a439fb764901ea0ae18d06ed80388b309b7a` |
|  | `apiguardian-api-1.1.2.jar` | `b509448ac506d607319f182537f0b35d71007582ec741832a1f111e5b5b70b38` |
|  | `junit-jupiter-params-5.9.0.jar` | `b8cef7982dd53df84c957a6e9ac89ede967cf2e6d9340ef4c51786e20548c41b` |
|  | `junit-jupiter-engine-5.9.0.jar` | `db86cbb3352719fa0a97800edfd09c20463c7f2ab4a04699244430bd8954583b` |
|  | `junit-platform-engine-1.9.0.jar` | `aaec735f7444a9fc055e206598de3d829c24e9c7a8eea6efdeeb1962087fe811` |
|  | `junit-platform-console-standalone-1.9.0.jar` | `a7b9590966ec414920fc54eb4b2a5900f90a6fffacee66e5a987583ee13027a2` |
|  | `assertj-core-3.23.1.jar` | `36af798af9fc20537669e02618bd39f2c797f4813824ef222108cb686fa4c88e` |
|  | `byte-buddy-1.12.10.jar` | `1a1ac9ce65eddcea54ead958387bb0b3863d02a2ffe856ab6a57ac79737c19cf` |

Runtime classpath: `$O/releases/micrometer-1.10.0/classpath.txt` (registry-signalfx, signalfx-java 1.0.25, slf4j-api 2.0.3, micrometer-core,
-commons, -observation 1.10.0, HdrHistogram 2.1.12, LatencyUtils 2.0.3).

**Which side 1.10.0 is on: the fix.** `SignalfxTimer.java` in `micrometer-registry-signalfx-1.10.0-sources.jar` is byte-identical to the fix's
(`f70c30df8af83e4c38282b2e4368960072c46a87a64fd53262506f72c838398f`); the parent's is `8b1d8737554101e9343c96bd1c883f18cdc741f17040119800265aead857f15d`.

**Overlay**: javac 17.0.21 `--release 8` over the release classpath.
- `$O/artifacts/J20-micrometer-parent-overlay.jar`: `85c12ad2377354d0c54b925e7295d189bac300e2de2f38472986c5acc754a425`
- `$O/artifacts/J20-micrometer-fix-overlay.jar`: `3dd6ea40c31a9fba9ed3b981a5f9b884aff4e655ba6fb8925cb99fb5008546cc`

| Class | parent overlay | fix overlay |
|---|---|---|
| `io/micrometer/signalfx/SignalfxTimer.class` | `927bdca9582e93b2a8734a9ff49bfc497be8e42b52331300cc5a75176fd03cca` | `98c05e45c0cfa0e7af16cbaa86df72fcaaea98e0555a50743936e0687661bf5e` |

`SignalfxTimer` has a package-private constructor; the overlay class sits in `io.micrometer.signalfx` like the release's.

**Landed test over the overlay** (JUnit Platform console on JDK 17.0.21; test source at the fix `099bc7d93535f5bb10413b0839eed4f07dbe8fe34c1f6c8c4b9033f04cf57e65`):

| Run | Result |
|---|---|
| fix test on the fix overlay | 20/20 pass |
| parent's own test on the parent overlay | 12/12 pass |
| fix test on the parent overlay | **2 of 20 fail**: `shouldExportDeltaHistogramData_Timer` rows [3] (`[PT0.001S, PT0.01S, PT0.1S, PT1S], [0.95, 0.99]`) and [4] (the same SLOs plus `PT2562047H47M16.854775807S`, percentiles `[0.95, 0.99]`), at `SignalFxMeterRegistryTest.java:252`; the rows without percentiles pass |

Logs: `$O/logs/J20-overlaytest-{fix,parent,transplant}.log`.

**Substitution: test library versions.** At these pins Micrometer declares test dependencies as `latest.release` (and `junit-bom:5.9.+`) with no
lockfile for the module (only `buildscript-gradle.lockfile` is committed), so the upstream versions are not pinned. The setup chose releases
current at the fix's date (2022-08-24): junit-jupiter 5.9.0 and assertj-core 3.23.1. signalfx-java is 1.10.0's 1.0.25.

**Upstream build: not practical.** Gradle 7.5.1 (distribution verified, `$O/tools/gradle-7.5.1`, zip sha256
`f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4`; the wrapper jar `91a239400bb638f36a1795d8fdf7939d532cdc7d794d1119b7261aac158b1e60`
is the published 7.5.1 one) on JDK 17 fails in `settings.gradle`: the settings plugin `io.spring.ge.conventions:0.0.11` is only on
`repo.spring.io/release`, which answers 401 now; it is on neither Central nor the Plugin Portal. Log: `$O/logs/J20-micrometer-fix.resolve.log`.

**For the domain agent**
- Micrometer 1.10.0's `SignalfxTimer` **is the fix's**: the release alone is the fix side; the parent overlay is the only parent-side artifact.
- Test-library versions are a setup choice (upstream used dynamic versions).
- The brief's count/total/bucket values and the emitted-datapoint labels were not probed; the landed percentile rows are the discriminator.

## Jobs

Written by `$O/scripts/submit_{B,C,D}.py` and committed with this record. Each builds the upstream project at both pins and
runs the landed test: fix online, then the parent's own, the fix's test transplanted onto the parent (where it compiles),
and the fix again, offline; then removes the build trees.

| Job | Case | Status |
|---|---|---|
| `20261124-203257-setup-build-apache-calcite-core-at-both` | J12: Calcite `-pl core -am`, `CoreQuidemTest` (Maven 3.5.4, JDK 8) | pending |
| `20261124-203508-setup-build-apache-poi-s-poi-ooxml-at-bo` | J05: POI `:poi-ooxml:jar`, `TestXSSFHyperlink` (Gradle 9.9.1, JDK 17) | pending |
| `20261124-203508-setup-build-eclipse-collections-at-both` | J17: `-pl unit-tests-java8 -am install`, the ten `MutableMapIterableTestCase` classes (JDK 8) | pending |
| `20261124-203513-setup-build-lucene-core-and-join-at-both` | J14: `:lucene:core:jar :lucene:join:jar`, `TestBlockJoinSorting` and `TestBlockJoinSelector` (Gradle 9.3.1, JDK 25); no transplant step (the fix's tests do not compile on the parent) | pending |
