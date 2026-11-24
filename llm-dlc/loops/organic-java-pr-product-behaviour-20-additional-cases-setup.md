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
