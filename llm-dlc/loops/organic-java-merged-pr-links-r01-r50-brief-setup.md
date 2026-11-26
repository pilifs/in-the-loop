# Setup for the organic Java merged PR links R01–R50 brief

Mechanical setup for [`organic-java-merged-pr-links-r01-r50-brief.md`](organic-java-merged-pr-links-r01-r50-brief.md), done on
2026-11-26 by a setup session (Claude Opus 5.5), before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/merged-pr-links-r01-r50`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR` (= `$O/tmp`), `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`, the
installations earlier setups used) and `$MVN` (Maven 3.10.0 from `PATH` with `-s $O/maven-settings.xml -t $O/toolchains.xml`,
local repository `$O/m2`, file-lock sync context). **The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `R01`–`R50` follow the brief's order (and the PR list [`organic-java-merged-pr-links-r01-r50.md`](organic-java-merged-pr-links-r01-r50.md)).
They are this record's labels only, not example ids.

## Starting commit

Checkout at setup: `84849fb0f7d2cb336f237086426f0b0e7dc2f99d` (`develop@origin`, "Merge the single-agent run spring-framework-pr-links-q01-q30-brief into the line").

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA (depth 1) from each
project's GitHub repository, one request at a time (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`, log `$O/logs/fetch.log`: 100 of 100 present,
94 fetched now, 6 already there). `assertj`, `jackson-dataformat-xml`, `javapoet`, `jimfs` and `moshi` are new mirrors; the other 26 existed and
gained these pins. One worktree per revision, `$W/CASE-MIRROR-ROLE` (`$O/scripts/worktrees.sh`; `parent` = the brief's before pin, `fix` = its
after pin). Parents were read from the raw commit objects (shallow history hides them from `git log`; `$O/logs/revisions.tsv`, `$O/logs/pins-parents.tsv`).

- **Every PR is merged, and its `merge_commit_sha` (`gh api`, `$O/upstream/prs/CASE-OWNER_REPO-N.json`) equals the brief's after revision**
  (`$O/logs/pr-meta.txt`). Changed-file lists per PR: `$O/upstream/prs/CASE-files.tsv` (status, path, additions, deletions).
- **For 48 cases the after revision's first parent is the brief's before revision.** R24 (javaparser #5207) and R50 (junit-framework #4466) are the
  two-commit ranges the brief names: R24's middle commit is `ba880df507664d320f54028810c42e07e429515f` ("test: cover annotated varargs with the legal
  array notation", parent = R24's before pin), R50's is `f7f1d51d4c57322dece17011a3da540b0f98bfbb` ("Add 5.12.2 release notes from template", parent
  = R50's before pin). Both were fetched into their mirrors (`refs/pins/middle-SHA`).
- The diff before→after of every case names exactly the PR's changed files (`$O/logs/landed-vs-pr-files.txt`; diffstats in `$O/logs/CASE-landed-diffstat.txt`).


| Case | PR | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|---|
| R01 | eclipse-collections/eclipse-collections#1786 | `R01-eclipse-collections-parent` | `3b3c55a47406ca11ece6c077b96c9564f73dfc53` | `5e85d917c3a5b5c7615a02805703ee2d8d760e61` | `8b240aaaafa8758187ffe208563ae7dcf2200745` `78b8031e7b040de94715bdfd22621ca8d053b79b` | 2025-08-15 | Merge pull request #1783 from motlin/task/non-mutating-functions |
| R01 | eclipse-collections/eclipse-collections#1786 | `R01-eclipse-collections-fix` | `4af700cda608e6817d7d17ab340b91442278cf14` | `53fcbaf78e424676bf9e081b53b5abffb073604d` | `3b3c55a47406ca11ece6c077b96c9564f73dfc53` `2d2107d954eaa91060d9103fb0d5a1ccc6c19a16` | 2025-08-22 | Merge pull request #1786 from motlin/non-mutating-functions |
| R02 | apache/commons-collections#688 | `R02-commons-collections-parent` | `dad2ff61e516a601da8179708959263e38af8d68` | `3011e5a3a12bb1e069deff936e163885731e9e23` | `5974e618e61e5abe7ead57488c76c741c2e3e5f7` | 2026-06-19 | TransformIterator now fail-fast on a null Iterator (#686). |
| R02 | apache/commons-collections#688 | `R02-commons-collections-fix` | `ca83f8699e10403be6987b92fb1a877743df8262` | `ca628ba9a5191bc6067734d29fe7972a219b3e27` | `dad2ff61e516a601da8179708959263e38af8d68` | 2026-06-19 | [COLLECTIONS-892] Fix unique IndexedCollection add atomicity (#688) |
| R03 | vavr-io/vavr#3276 | `R03-vavr-parent` | `f74004d3cef44fcccc7996783d34f734ba25ffd3` | `ad7be533a67cf2a209ea649ceca26d7f900329c1` | `eced14d578041cb57da6e6511d0c055d30028385` | 2026-05-17 | Replace comments with nested test classes (#3275) |
| R03 | vavr-io/vavr#3276 | `R03-vavr-fix` | `2b77936d4788fee24b99e8a372fd93923d8b6c12` | `130b4e9422b5556fa8a7e130b2e92919bda0da4f` | `f74004d3cef44fcccc7996783d34f734ba25ffd3` | 2026-05-17 | fix Map#computeIfPresent returning None for null (#3276) |
| R04 | vigna/fastutil#325 | `R04-fastutil-parent` | `faa22ac0b26ec1af680ada5eabf94bdedf9c824f` | `3e68f8af0beeb1304619039bc2f22f7d60d65efd` | `3e59d8a9577801e9df866b259e4c9ebfcb9c3923` | 2024-07-21 | Added missing @Test annotations |
| R04 | vigna/fastutil#325 | `R04-fastutil-fix` | `a1840bcc81f0fe2fb495856dded719125d869242` | `ed8a1f1c93c61a2fa20e8a8241ee8746231fe67e` | `faa22ac0b26ec1af680ada5eabf94bdedf9c824f` `d054bf30dd0c08ca3642bda600b38ebe3f49346a` | 2024-07-21 | Merge pull request #325 from Ampflower/master |
| R05 | google/guava#8811 | `R05-guava-parent` | `efae76a11d06cff9bd2a9d0865e0e4cfe554804d` | `a78cf62e072d1061059637fd813e52877c15acc5` | `1dcf53a90be93483c3f68b5c11b5facbfa4e1674` | 2026-10-30 | Refresh `ClassPath` Javadoc: |
| R05 | google/guava#8811 | `R05-guava-fix` | `c0a8a1edc69393e8141424037571d9825f5fc0f4` | `11abf700e9b74fc2b8518bb657f97765f1ac497b` | `efae76a11d06cff9bd2a9d0865e0e4cfe554804d` | 2026-10-30 | Fix rotating by `Integer.MIN_VALUE`. |
| R06 | apache/commons-lang#1865 | `R06-commons-lang-parent` | `ef7586831c7842c97ad4be8693ddef6f94bb8b64` | `5a08f1f9cc45341265802a701a43b380fedccddc` | `adc2e69162ba6bb4ddaf356a5ebc502cfceda2f0` | 2026-11-14 | [LANG-1425] Clarify DateUtils millisecond parsing (#1871) |
| R06 | apache/commons-lang#1865 | `R06-commons-lang-fix` | `355f246760cad21ca597424b49bb1151c0a63a96` | `f544570dd933fc324ae6a1af0216148d019886f2` | `ef7586831c7842c97ad4be8693ddef6f94bb8b64` | 2026-11-15 | Fix premature overflow in Fraction.divideBy (#1865) |
| R07 | locationtech/jts#1168 | `R07-jts-parent` | `45744222b0b8a861c44dbc2c03dcf4f1e85c27fd` | `1ae71a309d0438414a75908895e73715ecf01552` | `c72711eff956987dff2786bdd0e1ee167728c6ab` | 2025-12-04 | Refactor WKTReadWriteTest code |
| R07 | locationtech/jts#1168 | `R07-jts-fix` | `c406f5abe914d471ceb9cf0b872e8a634a1a1be6` | `7957a93244e17d27a070d6cd4295ad60d8f28542` | `45744222b0b8a861c44dbc2c03dcf4f1e85c27fd` | 2025-12-05 | Fix CoordinateList.clone() to copy correctly (#1168) |
| R08 | jgrapht/jgrapht#1379 | `R08-jgrapht-parent` | `fabfabe6f279c0dd61b417a543d33d94fd039249` | `0a27e37c9b827beefc29488e5c3ae561e8f22f9d` | `ab3924783305e5fc8d08a50507688f3440f5a4e3` | 2026-09-20 | Credits for last merge. |
| R08 | jgrapht/jgrapht#1379 | `R08-jgrapht-fix` | `955e5cfb9b22d7ac2ef956849523d22041baf730` | `0eda97f53c6d2624935b14cc98ba2b2ebf81c79a` | `fabfabe6f279c0dd61b417a543d33d94fd039249` | 2026-09-20 | fix: handle connectivity listener updates before cache initialization (#1379) |
| R09 | google/guava#8801 | `R09-guava-parent` | `ae0fa4bdaeef91c6f309c886263eb3b319b21568` | `7414c4934e6e7041d1ce263750d8f9691c4ec44a` | `59d4eb204dd9f920afa3a7886543e94f1b476881` | 2026-10-28 | Add test demonstrating that `Graphs.hasCycle` can miss cycles in undirected graphs. |
| R09 | google/guava#8801 | `R09-guava-fix` | `ca8aedb2fdaf40fd6937a0643180aea51ca4154e` | `9d7d68729583676edf5042958596e243c4154eec` | `ae0fa4bdaeef91c6f309c886263eb3b319b21568` | 2026-10-29 | Fix `Graphs.hasCycle` missing cycles in undirected graphs. |
| R10 | jgrapht/jgrapht#1376 | `R10-jgrapht-parent` | `e5bc1c06804bd90c5cf549954587728fc8dae101` | `785f558db332c888ac393fbdaf108b6651731865` | `5feaaf4371e60ef4d8a797c426218cd5cffd94ca` | 2026-09-20 | Credits for last merge. |
| R10 | jgrapht/jgrapht#1376 | `R10-jgrapht-fix` | `9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a` | `ea66511559acebd1fbaa465d54eab083c2e94d7f` | `e5bc1c06804bd90c5cf549954587728fc8dae101` | 2026-09-20 | Fix FarthestInsertionHeuristicTSP crash on negative edge weights (#1376) |
| R11 | apache/commons-io#931 | `R11-commons-io-parent` | `31cc5e824df9726d08cf5ee8154c1721abc2668d` | `440134a9b3675a9f8cd789573c7295475c4626f7` | `39d422cb55b61f5e4a41310066ff9d5706089287` | 2026-11-11 | Bump commons-lang3 from 3.21.0 to 3.22.0 |
| R11 | apache/commons-io#931 | `R11-commons-io-fix` | `1af75d36371fb56603cccca8bfd8083f5c97d6f2` | `aea4a1851f5f702d42b96af2817beb4fc68f22d8` | `31cc5e824df9726d08cf5ee8154c1721abc2668d` | 2026-11-16 | Fix AbstractCharacterFilterReader bulk reads and skip counts (#931) |
| R12 | apache/commons-io#860 | `R12-commons-io-parent` | `cfe19ad9dcc9d0c7308e2dc187b2f8b57de21af0` | `dd4163f3db54436f24c53412ab559a268ca054c7` | `e100c754d9922e9787fed65331536ce8acd947f4` | 2026-06-19 | Add serialVersionUID to test fixture |
| R12 | apache/commons-io#860 | `R12-commons-io-fix` | `e806e6b5926993ec6348a78542b1e1377a765e88` | `3f58de04fe7c9d668c2fee17423be8bc6ca6bbec` | `cfe19ad9dcc9d0c7308e2dc187b2f8b57de21af0` | 2026-06-18 | [IO-891] Fix BoundedReader.skip(long) accounting and bounds handling (#860) |
| R13 | google/jimfs#435 | `R13-jimfs-parent` | `f0dcab50faa6626b9275d6604a89d7debfff3677` | `5306aaccc057dae5710d95654eb852f37318b1fe` | `cf84588aacb26cd40e8ebbc239f8a59ee2ca7509` | 2025-09-17 | Bump Guava to 33.5.0. |
| R13 | google/jimfs#435 | `R13-jimfs-fix` | `0e5725b4d44ec51d54fba15336aa23147c1bedc7` | `ca4376727c4063621702441c5506d711a276a5e2` | `f0dcab50faa6626b9275d6604a89d7debfff3677` | 2025-09-18 | Fix `JimfsInputStream.read` to always return 0 when `len` is 0. Fixes #434 |
| R14 | vigna/fastutil#384 | `R14-fastutil-parent` | `a3d44187dca3deb185455274bb877703f2f541fe` | `02eff75d6f87e3a805e74aaf4e05da3c2c85be79` | `e96d67fe2aab0c52ca62dfc6086b436c254ce019` | 2026-07-23 | curl.sh -> publish.sh |
| R14 | vigna/fastutil#384 | `R14-fastutil-fix` | `cbf3c2ec706d16c56e6896b13ef0b5361be981c8` | `489d1f83e19bd0c6f46c9d543a6ad9d210c5788e` | `a3d44187dca3deb185455274bb877703f2f541fe` `397d741a07901ef2998e36fc05237fe06394ebe3` | 2026-09-13 | Merge pull request #384 from arimu1/fix/367-write-advance-position |
| R15 | apache/commons-codec#437 | `R15-commons-codec-parent` | `ac982579962c32ee28be1e80cdb514a829e3366f` | `2fe2b64866fc7ec41e9c222eaa0e6f3e9690d8e5` | `472a2894046e14fe2fd6e4f5312da8afb93c8769` | 2026-06-18 | Fix up changes.xml after merge |
| R15 | apache/commons-codec#437 | `R15-commons-codec-fix` | `98986558dc1c0e2013b76bea92d75bde80568a00` | `d218a14a2686f3f872053108a7b08e276759d2a6` | `ac982579962c32ee28be1e80cdb514a829e3366f` | 2026-06-17 | [CODEC-340] Fix Base58 custom alphabet handling (#437) |
| R16 | apache/commons-compress#725 | `R16-commons-compress-parent` | `a7a749f028a38a07c6b3765a4b2c3607b1ab6e71` | `99710b5e913ee62b8decd6cf36a177ef2ec6dec1` | `268c451e8a0594199b67de91f6fe2c638302c015` | 2025-10-08 | Bump org.apache.commons:commons-parent from 88 to 89 |
| R16 | apache/commons-compress#725 | `R16-commons-compress-fix` | `befbfe070270f61c29e032b51363dfc8c8ef51f1` | `d3c870b01370da037d49cd51203e4b0959246721` | `a7a749f028a38a07c6b3765a4b2c3607b1ab6e71` | 2025-10-10 | [COMPRESS-711] Fix incorrect CPIO checksum verification (#725) |
| R17 | apache/commons-compress#775 | `R17-commons-compress-parent` | `a8cb750e5bdd0fe136d5d9cab38781f9447b2dd3` | `a8185f79b055c9ff0ebb33970bdfb43e164355d2` | `225811e1085844eca54f1ec7f7151c1e4a23c1de` | 2026-07-11 | Add org.apache.commons.compress.archivers.zip.ZipFileNameMapBenmark |
| R17 | apache/commons-compress#775 | `R17-commons-compress-fix` | `948512a35a9f8ed1f8eac12f743e879aff9266d2` | `7f0c3edb424fd8c6d7054b4ed2f9ac6d740f85ad` | `a8cb750e5bdd0fe136d5d9cab38781f9447b2dd3` | 2026-07-11 | [COMPRESS-724] Fix PAX 1.x sparse header alignment (#775) |
| R18 | FasterXML/jackson-core#1716 | `R18-jackson-core-parent` | `2a0ea7beeb9eb0a16f04c14e07b5d0804c64433d` | `2ba5d379984b2a3a7787d8855b347564fe10f29d` | `cfec81afc42ca7e046379c01af3e110a8ae83980` | 2026-09-11 | Add cve id CVE-2026-89425 for #1698 in release notes |
| R18 | FasterXML/jackson-core#1716 | `R18-jackson-core-fix` | `15591d013c44ef3b2a84bb639df396149a5917f5` | `6733ade8a4051535445313e06b267adf6b04e9a5` | `2a0ea7beeb9eb0a16f04c14e07b5d0804c64433d` | 2026-09-16 | Fix #1713: `UTF32Reader` corrupts low surrogate split across `read()` boundary (#1716) |
| R19 | locationtech/jts#1092 | `R19-jts-parent` | `a7597288e551757426015db75c22603c0baeff20` | `d807f706d822c93e3fed8be94be88dd823ee43cf` | `e7cd7cfc33c8c5d3e2e5897bb80371db860d750d` | 2025-04-30 | Update JTS_Version_History.md |
| R19 | locationtech/jts#1092 | `R19-jts-fix` | `034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3` | `12233f11f5a35e36e2cb7150052345af4e80b492` | `a7597288e551757426015db75c22603c0baeff20` | 2025-05-02 | Fix writing XYM geometries as WKB (#1092) |
| R20 | apache/commons-csv#412 | `R20-commons-csv-parent` | `2abebaa74eb413ece7a56d86f826bc690ee26df9` | `d502e0db42ec8d279760ff9bdcd0b2d898b3f16e` | `cf1e392f8585dbf2428f99445982d820e91a4687` `214725b24f188227df3934b2ae4d4cc0f5101769` | 2024-04-05 | Merge branch 'master' of https://gitbox.apache.org/repos/asf/commons-csv.git |
| R20 | apache/commons-csv#412 | `R20-commons-csv-fix` | `5770cc07e351cc124d34a6049c59e9aea8885675` | `2b7edf104f447f8e26ba831fefb69a1ad32e48bf` | `2abebaa74eb413ece7a56d86f826bc690ee26df9` `df7c340e7be5f662e641e911f1d5c76685abeaba` | 2024-04-06 | Merge pull request #412 from ikfid/mongo_db_csv_empty_first_column |
| R21 | square/javapoet#994 | `R21-javapoet-parent` | `aaebc488320bd11aab1a6248d6b8058a255c92df` | `ac2c05a2c0eb1ac791d26b50b35da17f89144f50` | `62eb8d2e81db857af70eb91d9f832960df21073e` `a24c125dd164436d9ec2a1e71822ef93a938d82a` | 2023-12-24 | Merge pull request #992 from square/renovate/org.apache.maven.plugins-maven-compiler-plugin-3.x |
| R21 | square/javapoet#994 | `R21-javapoet-fix` | `c9925e48577e3e74b91eb737b2c2b3c22109cde8` | `2416ed2d111f46207002d9135119546bae0ccb06` | `aaebc488320bd11aab1a6248d6b8058a255c92df` `fa579e1b403315558abc0178cd84c31b5e02b37e` | 2024-01-16 | Merge pull request #994 from Tim203/fix/correct-long-interpretation |
| R22 | square/javapoet#986 | `R22-javapoet-parent` | `0d55218ae3b8c8d6fe84132b7867d8c12698ce5e` | `374ab6f6dd0e387ad04f5e1fc0b4f661fe4d3795` | `44afd4876cebc49b571c58d8e0119b35b087f93e` `cadaa8a1768137f33393d02713f8e70abe0094ed` | 2023-10-24 | Merge pull request #987 from square/renovate/org.apache.maven.plugins-maven-checkstyle-plugin-3.x |
| R22 | square/javapoet#986 | `R22-javapoet-fix` | `d682f2013751d25725349d79b449870d0e77354c` | `d53ab59df5ea9066e98d3cb82dae7cc54c7edbd9` | `0d55218ae3b8c8d6fe84132b7867d8c12698ce5e` | 2023-10-30 | Fix boxing and unboxing of annotated primitives |
| R23 | javaparser/javaparser#5176 | `R23-javaparser-parent` | `a322c502cfac7d97495fc3f41c6b74a06924267f` | `e9c909372462207711429bcab9b3f4d81da0e0b5` | `0a9424cefafae806e6e97c56765dbe5ed5e192ae` `9933fa3f1bdd8781d8643cb219dc85e64f636a00` | 2026-10-24 | fix: translate the \s escape in string and char literals |
| R23 | javaparser/javaparser#5176 | `R23-javaparser-fix` | `c9c78dd4c965646dd97bbf3108ff1faefa1ae198` | `045b673fc86bef7b2f98823828994239e2f2a2a5` | `a322c502cfac7d97495fc3f41c6b74a06924267f` | 2026-10-24 | fix: notify observers from the typed literal setters (#5176) |
| R24 | javaparser/javaparser#5207 | `R24-javaparser-parent` | `7bb33415ec75aa3fe01c1b3741cbe9ee48413739` | `b2d7bc2ffdac9e5aa441066916413e0154c12b33` | `004c4d3a496898049b2201f8aca3b95645fb8d4b` | 2026-10-27 | fix: limit the range of a declared name to its identifier (fixes #2310) |
| R24 | javaparser/javaparser#5207 | `R24-javaparser-fix` | `ae2e9400810933b1523f3182acc69bf8998e26ca` | `2a89971aa9ad0da2b55d357f3b2f087e0c7bd77c` | `ba880df507664d320f54028810c42e07e429515f` | 2026-10-27 | fix: preserve C-style array brackets in the lexical preserving printer |
| R25 | square/moshi#1442 | `R25-moshi-parent` | `751e8219e992a9aecd286aac830fef81da790baa` | `2aa3effca3ae464f76bbb10570007ab0068559c4` | `9f81ac897aa2214235c126f89f8d93519233a47b` | 2021-11-30 | Fix code cleanups (#1441) |
| R25 | square/moshi#1442 | `R25-moshi-fix` | `cdcf0da4ee260b72d7e1ea2be691a568e03720b3` | `358c54da60d0dc0b367a52f0a00625969e69a26a` | `751e8219e992a9aecd286aac830fef81da790baa` | 2021-12-04 | Fix a crash when combining generics and records (#1442) |
| R26 | google/gson#2998 | `R26-gson-parent` | `c616243d1d78c0466b53be39f893094ebb7c6918` | `45e30358e3135298edb7a212f811185a166c871b` | `6c06cbc679fc088fbc36117c9e45244b6b1fe9c4` | 2026-11-16 | Preserve checked I/O failures in tree type adapters (#3130) |
| R26 | google/gson#2998 | `R26-gson-fix` | `e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c` | `f821d0d59d7291d3cca7e0206f52d65db77cd75a` | `c616243d1d78c0466b53be39f893094ebb7c6918` | 2026-11-16 | fix: Preserve integral Number type in toJsonTree for byte/short/int (#2998) |
| R27 | FasterXML/jackson-core#1816 | `R27-jackson-core-parent` | `682b4062b60d8317956ca80a28c3c92cf46d93ce` | `e5b19d095d304ff7b0e767eccfc4fbddb362400e` | `312c5f62ef41d089a1d2d4ff459dd54bf60adeb0` | 2026-11-03 | Fix deferred double value after float access (fix #1813) (#1779) |
| R27 | FasterXML/jackson-core#1816 | `R27-jackson-core-fix` | `b251524f3a857fd5960548ea12d4ba2dc92f8c43` | `6e3a41544e2557c39143f0ff3408058b7539b360` | `682b4062b60d8317956ca80a28c3c92cf46d93ce` | 2026-11-03 | Fix stale BigDecimal from previous token (fix #1815) (#1816) |
| R28 | FasterXML/jackson-databind#6407 | `R28-jackson-databind-parent` | `b02acce88765473e3d883c877f1e64e1c1d8910d` | `daec3ec8c16988eff9da9296d610f34764f110af` | `34cfa072ae45c32843e8e743c1e44cca76a4fbf0` | 2026-11-07 | Update CLAUDE.md branch info for 3.3.0 release (3.x -> 3.4.0) |
| R28 | FasterXML/jackson-databind#6407 | `R28-jackson-databind-fix` | `0736200316cc75d98d38b73622aad09f28a1fc93` | `b2d2cec32a0eb41e4e479aaf683d825101cf333f` | `b02acce88765473e3d883c877f1e64e1c1d8910d` | 2026-11-09 | Fix #6397: Preserve buffered properties in immutable creator-based builders (#6407) |
| R29 | FasterXML/jackson-databind#6473 | `R29-jackson-databind-parent` | `66ade176743438d3b8247348465aa31eb95e24f7` | `c693afbd24b470094f340b257feacdd1bdd48f3b` | `b2ab08ea9d8021c2bee036951bbaae2b44402f59` | 2026-11-20 | Fix #6476: convert JDK integral `Number`s exactly in `POJONode` decimal accessors (#6479) |
| R29 | FasterXML/jackson-databind#6473 | `R29-jackson-databind-fix` | `949188f567b60b88851f4898eeb9bc82d098cfbe` | `0efe5357fa68645abd7f92b384a4b6f6123c882a` | `66ade176743438d3b8247348465aa31eb95e24f7` | 2026-11-21 | Fix #6445: merge existing values with `@JsonMerge` on `EnumMap` (#6473) |
| R30 | FasterXML/jackson-dataformat-xml#895 | `R30-jackson-dataformat-xml-parent` | `f560daa9ecb75c50de084c5a57559f84134554b3` | `afbf547e45ebbcdefd93537bf8f1137b044fe26a` | `b632c2a3a04a69d6166ed32e47222d4a107be21f` `74c954239a58bd7b6b15f59c4a3591dd9a16cd64` | 2026-08-21 | Merge branch '3.2' into 3.x |
| R30 | FasterXML/jackson-dataformat-xml#895 | `R30-jackson-dataformat-xml-fix` | `c3584c7120d6a11e3d417a081d8600be47103fe9` | `196a552c982539a59137dcb2173fa32e2fe6df68` | `f560daa9ecb75c50de084c5a57559f84134554b3` | 2026-08-21 | Fix leading digit in `AlwaysOnBase64NameProcessor` encoded names (#895) |
| R31 | h2database/h2database#4034 | `R31-h2database-parent` | `e69ff62a4bb5fb84d4f4eee916efa1c432a200c4` | `f39edb27a13bde2184a6b9e68a364ff992314033` | `8f5c541d3bb8d67e7664c9dd8a6c43bba266da20` `b3c20eb38a2b8fdb193dadd10a54511f7ef0776a` | 2024-03-23 | Merge pull request #4006 from andreitokar/issue-3909 |
| R31 | h2database/h2database#4034 | `R31-h2database-fix` | `23bf50db54de6ef20877e3ac4e53786d8bea1998` | `5d9f50469e43ffcdec9425c22596ad9d50b50569` | `e69ff62a4bb5fb84d4f4eee916efa1c432a200c4` `2a08820f62aeb042dc429dd25779e1614c5de6f6` | 2024-03-26 | Merge pull request #4034 from katzyn/type |
| R32 | h2database/h2database#2614 | `R32-h2database-parent` | `3d939b6a4e3d4f60ca7e378bc3af3fc0087d0249` | `bdd34f7f58c43878f666f32de967c3a4bb8d9cc1` | `8138ff3d8ee95811e13befdbd8cfbd39b4a86012` `1095d60b9218f3e57b3e1a5ae1a902549923aecc` | 2020-05-07 | Merge pull request #2612 from katzyn/concatenation |
| R32 | h2database/h2database#2614 | `R32-h2database-fix` | `6940fc30b60af16b06376a6c2ed8c46815820730` | `a74a3f08a158e77be1343df12ae81ba8560dc54b` | `3d939b6a4e3d4f60ca7e378bc3af3fc0087d0249` `d7f7e7d183e8e2b60967b2abd1dda63f7c65a0aa` | 2020-05-08 | Merge pull request #2614 from katzyn/array |
| R33 | apache/calcite#5345 | `R33-calcite-parent` | `c368970b2950903432ed61ecd7ff404a67e16fb1` | `a17bcc6c26271313b3a83454b6d7ed02ea7fa7c5` | `73b05e37c75bc38e663be7dcd87315324b44a9e5` | 2026-10-23 | [CALCITE-7885] RelDecorrelator merges distinct correlation fields and produces extra rows |
| R33 | apache/calcite#5345 | `R33-calcite-fix` | `a2e574ec271866eb352f98d7101a386a30dc8bc8` | `faa7ded176b7bdf622c882d0413735022c847cda` | `c368970b2950903432ed61ecd7ff404a67e16fb1` | 2026-10-23 | [CALCITE-7870] RexSimplify removes some casts which change semantics |
| R34 | apache/calcite#4942 | `R34-calcite-parent` | `3fc5f464ee087f69cd7b1f8dd54ee612050a917d` | `d29295f498fc20cc3c8e74f71028bea04f351b1e` | `c60d0883ccdad88154f556551b138befea91e064` | 2026-06-02 | [CALCITE-7563] Oracle dialect generates invalid CAST to VARCHAR without precision |
| R34 | apache/calcite#4942 | `R34-calcite-fix` | `b25114f7c616b6e3fb4007071406f79e765ff66f` | `ceace992fe9f056070b06051a1a5f4bc23aff18f` | `3fc5f464ee087f69cd7b1f8dd54ee612050a917d` | 2026-06-02 | [CALCITE-7529] Casts between literals and TIME/TIMESTAMP can lose precision beyond milliseconds |
| R35 | apache/arrow-java#1518 | `R35-arrow-java-parent` | `a99297ce3ca5c6cd8dc2c5ea3f5541b0788fdd62` | `a90690936e3da079340e32797f22fb5b34903c50` | `14fef469519763c63b62f51cc6ee040b7fd43fe0` | 2026-11-23 | MINOR: [Flight] Fix cookie header parsing in ServerSessionMiddleware (#1517) |
| R35 | apache/arrow-java#1518 | `R35-arrow-java-fix` | `1718ad7aeef4209d3a620541672e1af7fc5cbb1e` | `e22d17057076232bdddb8091a9909de1cdfa46ac` | `a99297ce3ca5c6cd8dc2c5ea3f5541b0788fdd62` | 2026-11-23 | MINOR: Decode decimal holders with the correct byte order and byte offset (#1518) |
| R36 | apache/arrow-java#1342 | `R36-arrow-java-parent` | `f745a59d4c944ce47c109b89be021915b3484cce` | `ef2ea6e16db0315c521d6458d6a2469f8312ea7d` | `45fa93be0ee6a90324e5dd0076a098f2dc9a4583` | 2026-10-30 | MINOR: Bump git-commit-id-maven-plugin from 4.9.10 to 10.0.1 (#1339) |
| R36 | apache/arrow-java#1342 | `R36-arrow-java-fix` | `2f35627084d27e06fcaca800bc05c772e3fc1113` | `cc21a0cdd2d7d5c68c7252e233dbb6c0173f2d72` | `f745a59d4c944ce47c109b89be021915b3484cce` | 2026-10-30 | MINOR: Fix validation of decimals at their declared precision (#1342) |
| R37 | apache/avro#2282 | `R37-avro-parent` | `4ec81bd0cdc8615e833582f257684cb61c892578` | `1b8157168054757aeca6a795588b8f29a0b84f26` | `51851d49af3283cd31caecf6bdc7b3a4e973a5a6` | 2023-10-06 | AVRO-3878: Rename default git branch to be 'main' (#2537) |
| R37 | apache/avro#2282 | `R37-avro-fix` | `3ea027ac26b41edc0f08fd8c042ee918c523bdac` | `21270f981ddbfdb51a1254293bf13dc90f3bbd87` | `4ec81bd0cdc8615e833582f257684cb61c892578` | 2023-10-09 | AVRO-3779: [java] any big decimal conversion (#2282) |
| R38 | apache/avro#2520 | `R38-avro-parent` | `119c3fc99203cf6fb63dda7c3bb307c8841f179a` | `4a4ae7173f6d1803cef9fceb82a0a1d88b392e92` | `69679cb6113cdf437e8138c85f0a9e080c36b186` | 2023-10-04 | AVRO-3653: [CI] Linux ARM64 on GitHub actions (#1964) |
| R38 | apache/avro#2520 | `R38-avro-fix` | `abe6d421e82fa1d7e2ff4ae19b8a73f2e75ca396` | `39ec44d0b8612ad8a7afd24068a18731db9c1e5c` | `119c3fc99203cf6fb63dda7c3bb307c8841f179a` | 2023-10-05 | AVRO-2123: Java duration logical type (#2520) |
| R39 | apache/parquet-java#3830 | `R39-parquet-java-parent` | `6ae2a8f173dcd2a121e41e3dc05d3dfc284d84a5` | `00cc514745e072af072044a25f122df0a588222b` | `24e70f1da5746c7ea227b715e91a0da0a3228557` | 2026-10-14 | GH-3826: Preserve component paths for Bloom filters (#3827) |
| R39 | apache/parquet-java#3830 | `R39-parquet-java-fix` | `bca2eaeac0afc88197c622f0f27c8a55739a5be9` | `dfb0e98a8f926abcf2a44f65aaca438cbe0ef8a3` | `6ae2a8f173dcd2a121e41e3dc05d3dfc284d84a5` | 2026-10-15 | GH-3828: Preserve column path identity in dictionary lookup (#3830) |
| R40 | ThreeTen/threeten-extra#433 | `R40-threeten-extra-parent` | `9b5e316f5fad89ef80a05d8cdec522315c2e26ba` | `3e16ce2bc490f43a83fd91a4a661c2448b7bd229` | `b290f44f9332df07377453b306e0d4038b4887a7` | 2026-10-24 | Fix `MutableClock` update threading (#432) |
| R40 | ThreeTen/threeten-extra#433 | `R40-threeten-extra-fix` | `cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0` | `64f766c37e3c0ac96996d153918b9455ad492b38` | `9b5e316f5fad89ef80a05d8cdec522315c2e26ba` | 2026-10-24 | Fix OffsetDate.until() (#433) |
| R41 | ReactiveX/RxJava#5101 | `R41-RxJava-parent` | `5a8be22b6501feefe10fb00731c00ce1ad215b89` | `511c3f166d43e5c0903af5f68e035c6b4e50241c` | `7bfecccedd8641027a17438192a1ff30fd1addb8` | 2017-02-15 | Release 2.0.6 |
| R41 | ReactiveX/RxJava#5101 | `R41-RxJava-fix` | `6daf59ebc19f5ef8914086fe466823f51ca628a9` | `f7447c9f8bf6773538b6ab9fac7f3820b725adee` | `5a8be22b6501feefe10fb00731c00ce1ad215b89` | 2017-02-16 | 2.x: fix Maybe.concat() subscribe-after-cancel, verify others (#5101) |
| R42 | reactor/reactor-core#937 | `R42-reactor-core-parent` | `0ad7976bf1c02bccc28bb478758591bc8108b11a` | `86b1beb9247fb7078776538c00585009d6501955` | `e443bb9847b419292412ce506bb28303fc4a3d81` | 2017-11-07 | fix #906 Add Mono#blockOptional (#918) |
| R42 | reactor/reactor-core#937 | `R42-reactor-core-fix` | `af0cb628ece3c0a543512ea9913c4ff72ba18566` | `0c475df4ccce079d8571cb5ef0186c7c8f5efa29` | `0ad7976bf1c02bccc28bb478758591bc8108b11a` | 2017-11-07 | fix #936 concat[Map]DelayError(veryEnd) delays Callable errors |
| R43 | reactor/reactor-core#3783 | `R43-reactor-core-parent` | `92c8ea05eaa4e009fe5459bd4a1fe51b244bcc52` | `4fa9d9de69ff114c70a0b425ec8ce54a64ac733f` | `c8ff304d9255f3d2390e2d73ebdca794fb03aa58` | 2024-04-09 | [release] Next development version 3.4.38-SNAPSHOT |
| R43 | reactor/reactor-core#3783 | `R43-reactor-core-fix` | `2a664dd587e74793fb473d81e8b26a199ff07d1e` | `cce130ccb8a57365bae7b3e8473b3bd9ae25c04e` | `92c8ea05eaa4e009fe5459bd4a1fe51b244bcc52` | 2024-04-11 | Remove Flux#thenMany optimization breaking concat (#3783) |
| R44 | ReactiveX/RxJava#6664 | `R44-RxJava-parent` | `c2dc134221ad6bd623f6160ec5338ad4496c5112` | `ed1e8853522078df901e7c0a1253f7af0b08aa51` | `877702e284b78503d9ba13f76ddf76918cbe93a5` | 2019-10-04 | Update Additional Docs to include Reactive Programming on Android with RxJava (#6665) |
| R44 | ReactiveX/RxJava#6664 | `R44-RxJava-fix` | `cb7ff83a2444731dd7eca4760e9410a6c2980b6d` | `bafc4a9d8c7ff9b2c134498d0badafd8e0b31caa` | `c2dc134221ad6bd623f6160ec5338ad4496c5112` | 2019-10-05 | 3.x: Fix groupBy group emission in some cases (#6664) |
| R45 | resilience4j/resilience4j#2067 | `R45-resilience4j-parent` | `12f66a31d7b4619ed0ffd1fddee9da683c41b9b7` | `764fd9a6ac9ac01a790c93ee88f71df355994e9e` | `dc8d1559e261d5e586ce106d3d8a4269ff69c8fc` | 2023-11-18 | Support class name using SpEL expression at Circuitbreaker annotation name field. (#2053) |
| R45 | resilience4j/resilience4j#2067 | `R45-resilience4j-fix` | `a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c` | `b15a0fb967bb3ad6103a216188a48cea1f24d7f1` | `12f66a31d7b4619ed0ffd1fddee9da683c41b9b7` | 2023-12-06 | Issue #1565: Do not retry if IntervalFunction returns interval less than 0. Emit correct events based on result of IF. (#2067) |
| R46 | resilience4j/resilience4j#1999 | `R46-resilience4j-parent` | `e328decc50954d70420359acea78491fce539d20` | `9c40e8d310ee75889b46e2bbb69a04783a0751e8` | `302df7553749e71081b26b73cdb3b52fd0817eda` | 2023-07-05 | Issue #1600: Metric for total number of invoked calls from retry (#1895) |
| R46 | resilience4j/resilience4j#1999 | `R46-resilience4j-fix` | `17dc97b1c8e472e1c295f112b8b761298cd1321a` | `b1deed0f6907c1ec77c388a032326fe37969276d` | `e328decc50954d70420359acea78491fce539d20` | 2023-07-20 | fix Feign fallback from lambda (#1999) |
| R47 | remkop/picocli#2036 | `R47-picocli-parent` | `7c7c8b954277b6e18c57ff5ea1791b59569c0511` | `655d9286e570be7b29f558f1b8037e9c3ca8b60e` | `d20d711b88a34cf69ea40f5cfa2d8fa74537122d` | 2023-06-01 | [2029] Fallback to default charset if the charset provided by sun.st*.encoding is invalid |
| R47 | remkop/picocli#2036 | `R47-picocli-fix` | `5984589f57bcf2bb716e3dee21025ddaa387c3da` | `3ec80ca4bf248cc5e90b1f09e3c5b5aa16ec6bd9` | `7c7c8b954277b6e18c57ff5ea1791b59569c0511` | 2023-06-02 | Fixes #2035 - include mapFallbackValue for inherited opts |
| R48 | assertj/assertj#3710 | `R48-assertj-parent` | `d2257cab92a263fde1159ad5bcc7339de2effbc9` | `78d5a93d678729465825355110eb03e0fc1541df` | `b401a23b32acad63d2c08b791f9aae72917aa458` | 2024-12-22 | Move group properties test to test project |
| R48 | assertj/assertj#3710 | `R48-assertj-fix` | `f3ece963d761d66a7ee31d29ccd9158df3794024` | `879151e31836fdd788d83fa9540434883fa9fc35` | `d2257cab92a263fde1159ad5bcc7339de2effbc9` | 2024-12-22 | Fix missing introspection for record accessors (#3710) |
| R49 | junit-team/junit-framework#5839 | `R49-junit-framework-parent` | `f8686f1e6482e41bd40548fd08c5340f414b968f` | `3f3db360bb7a3196e91a76becb76bc5f07c3ee1d` | `e6b79dae9fcf6ad348b4e36a9b6c7d460cab4949` | 2026-07-04 | Create initial 6.1.2 release notes from template |
| R49 | junit-team/junit-framework#5839 | `R49-junit-framework-fix` | `7e7183fe2989400b98c8ef06981ab0ae3e62d6d8` | `e3e59aae84a9335ddd93b571dba4e24511f40e58` | `f8686f1e6482e41bd40548fd08c5340f414b968f` | 2026-07-04 | Fix NoTestsDiscoveredException for suites containing only dynamic tests (#5839) |
| R50 | junit-team/junit-framework#4466 | `R50-junit-framework-parent` | `96d0c6dae456021a664a2283ab30fca28c4fbae2` | `b827fdc509a4d96b324056817ed074bee00f346f` | `f10ba0d983d7b1ada6c1f6a1fdcd11a3becc15ba` | 2025-04-11 | Introduce internal `RecordsArguments` interface |
| R50 | junit-team/junit-framework#4466 | `R50-junit-framework-fix` | `48276fd094821f79afb3cd384b8c70946d73350b` | `03a9443a67a71603209d8366316e67baac331c57` | `f7f1d51d4c57322dece17011a3da540b0f98bfbb` | 2025-04-11 | Fix handling of `CleanupMode.ON_SUCCESS` |

PR metadata (`gh api`, `$O/upstream/prs/`): base branch, head, commits, changed files, merged at.

| Case | Base | Head | Commits | Files | Merged at |
|---|---|---|---|---|---|
| R01 | `master` | `2d2107d954eaa91060d9103fb0d5a1ccc6c19a16` | 2 | 7 | 2025-08-22T14:05:31Z |
| R02 | `master` | `617010416bf0a5bde6a332fa4caf12844580e813` | 1 | 3 | 2026-06-19T17:26:27Z |
| R03 | `main` | `1593f946e689dae4d397a8b96fe0a5ca211439a8` | 1 | 2 | 2026-05-17T14:21:38Z |
| R04 | `master` | `d054bf30dd0c08ca3642bda600b38ebe3f49346a` | 1 | 3 | 2024-07-21T07:27:55Z |
| R05 | `master` | `c0a8a1edc69393e8141424037571d9825f5fc0f4` | 1 | 32 | 2026-10-31T02:20:42Z |
| R06 | `master` | `52b323674b289fd17c94711e8dc7d69f3dd9f3ea` | 1 | 2 | 2026-11-15T12:23:03Z |
| R07 | `master` | `8704fc16bcec4417d70371e6c5bd5b456c9255bf` | 1 | 2 | 2025-12-05T20:17:21Z |
| R08 | `master` | `c08f710e61de98adb1ad3fa86ad1b3c16290e47f` | 1 | 2 | 2026-09-21T05:26:41Z |
| R09 | `master` | `ca8aedb2fdaf40fd6937a0643180aea51ca4154e` | 1 | 4 | 2026-10-29T12:00:08Z |
| R10 | `master` | `63ddf41b6af6a3804982bd10e8e3f3d0a72ea45f` | 1 | 2 | 2026-09-21T05:10:39Z |
| R11 | `master` | `fbdd8ba9717abcb7121d373822fc12a0718fe57c` | 1 | 2 | 2026-11-16T15:41:55Z |
| R12 | `master` | `9b8dae331e95266628c1dc39d2cafc3c4ba4205a` | 3 | 2 | 2026-06-19T01:29:42Z |
| R13 | `master` | `0e5725b4d44ec51d54fba15336aa23147c1bedc7` | 1 | 3 | 2025-09-18T17:08:58Z |
| R14 | `master` | `397d741a07901ef2998e36fc05237fe06394ebe3` | 1 | 2 | 2026-09-13T05:54:12Z |
| R15 | `master` | `5af4c8e5eb7c32b83fc81e0ff6db05b5b01db23e` | 2 | 3 | 2026-06-18T02:16:35Z |
| R16 | `commons_io_2_21_0` | `f4743334053d6fc4adeaa207dcddb8e2186f97cb` | 1 | 3 | 2025-10-10T11:58:14Z |
| R17 | `master` | `b323142785f7385c57ad25f8705614076a1da5d8` | 3 | 3 | 2026-07-11T14:53:21Z |
| R18 | `2.21` | `1770cf10a28033602e191234f25b851c69d8beab` | 2 | 4 | 2026-09-17T01:27:51Z |
| R19 | `master` | `8cb3ac8feb08f61cb5f3de26f1a9b9bb1338406c` | 2 | 4 | 2025-05-02T16:58:54Z |
| R20 | `master` | `df7c340e7be5f662e641e911f1d5c76685abeaba` | 2 | 2 | 2024-04-06T12:14:50Z |
| R21 | `master` | `fa579e1b403315558abc0178cd84c31b5e02b37e` | 1 | 2 | 2024-01-16T19:16:50Z |
| R22 | `master` | `e7c21ea5becf9f5499afdf65a6ef3b50ee034569` | 4 | 2 | 2023-10-30T18:49:14Z |
| R23 | `master` | `4375af79a2b2ee3e58ea0574f10b39021792e6f4` | 2 | 7 | 2026-10-24T20:57:58Z |
| R24 | `master` | `aa37e23c9e4217564767eda34b3b2b173890140c` | 2 | 7 | 2026-10-27T17:21:27Z |
| R25 | `master` | `1cb15e3cee4380f3b5663a3ea080730204dd692c` | 1 | 2 | 2021-12-04T21:31:58Z |
| R26 | `main` | `76d8a271fef35b71892a27b1a217dcca4a0e8d44` | 2 | 2 | 2026-11-16T13:56:35Z |
| R27 | `2.21` | `44bc6f76fb824b0e14a64297df6c4adc22ec0656` | 4 | 5 | 2026-11-03T22:52:01Z |
| R28 | `3.x` | `079f97b2f23a411cf6e832abec5edc5bfbf17786` | 9 | 5 | 2026-11-10T03:31:18Z |
| R29 | `3.x` | `ca99f9e665c6b9314ac62a9fef36d1028a3db5c0` | 3 | 4 | 2026-11-22T02:18:08Z |
| R30 | `3.x` | `f506e647f7dc6b6e55ac4d042474c6a714bdc1a4` | 6 | 4 | 2026-08-22T02:24:17Z |
| R31 | `master` | `2a08820f62aeb042dc429dd25779e1614c5de6f6` | 1 | 8 | 2024-03-26T11:37:47Z |
| R32 | `master` | `d7f7e7d183e8e2b60967b2abd1dda63f7c65a0aa` | 1 | 5 | 2020-05-08T07:39:34Z |
| R33 | `main` | `129fed5ff267788f3e6be306955238325e3f6b07` | 1 | 5 | 2026-10-23T21:04:19Z |
| R34 | `main` | `f5d8c720eea2b10d6fdc4d98609c19ff10d0d65a` | 1 | 6 | 2026-06-02T18:49:09Z |
| R35 | `main` | `830651feaa4ad68519644593c8b9bc7303a2087d` | 1 | 3 | 2026-11-23T17:08:02Z |
| R36 | `main` | `3a20fadcad6038134a3f160e2376821a9fece7fb` | 1 | 2 | 2026-10-30T09:24:49Z |
| R37 | `main` | `973af4a0ae8f41770da7cb1aa417b1dfa88aa945` | 4 | 8 | 2023-10-09T11:31:40Z |
| R38 | `master` | `cd08aec842a4d31765c4bf017463d430ff54e046` | 5 | 6 | 2023-10-05T08:38:55Z |
| R39 | `master` | `3eb9c7a75dfb15cb7421266035c48f60dde585cc` | 2 | 2 | 2026-10-15T03:27:56Z |
| R40 | `main` | `24fba8978d13a35a5c63636f7ed1829b99036020` | 1 | 3 | 2026-10-24T20:36:39Z |
| R41 | `2.x` | `488fcd08f857b887ae5d8b69c8ac02bf7c989804` | 1 | 8 | 2017-02-16T17:20:41Z |
| R42 | `master` | `7b31eedb2727d07eec35dd6247f418cfde0ffd55` | 2 | 9 | 2017-11-07T17:39:12Z |
| R43 | `3.4.x` | `d3f88624105e2d5bede903778f24b4fc8c17d401` | 3 | 4 | 2024-04-11T08:30:48Z |
| R44 | `3.x` | `122345fa88f98a06c82335910bf05f93a30ec9c4` | 2 | 4 | 2019-10-05T16:12:46Z |
| R45 | `master` | `c03c9afc4ef57d69119d02d97f2ba1b1ea4260b3` | 1 | 4 | 2023-12-06T12:28:09Z |
| R46 | `master` | `50a2948a2c413fd6d19047b65728a98c70e84f22` | 2 | 4 | 2023-07-20T12:41:13Z |
| R47 | `main` | `3d5cf2264dc4088f4f2e655a87dcb991ee838afa` | 1 | 2 | 2023-06-02T01:02:56Z |
| R48 | `3.x` | `a185dcc2b0568638db5be8e3c4bf9084ba14952e` | 1 | 2 | 2024-12-22T22:15:45Z |
| R49 | `main` | `a9b9d4af8c1ad500904b9bbeb0166d102243f913` | 2 | 5 | 2026-07-04T21:34:54Z |
| R50 | `main` | `b36e605570c200fdaa65e4e3c9f14208b36e3e74` | 2 | 4 | 2025-04-11T13:42:18Z |

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` (`$J8` `$J11` `$J17` `$J21` `$J25`) | earlier setups' installations; none added |
| Maven 3.10.0 | on `PATH` (sdkman, `~/.sdkman/candidates/maven/3.10.0`) | all Maven cases |
| Gradle distributions | `$O/tools/`, zips in `$O/dl/gradle/` | see the fork D section (Gradle cases) |

Caches and files this work owns:
- `$O/m2` (Maven local repository, shared by all Maven cases), `$O/gradle-home` (`GRADLE_USER_HOME`, Gradle cases), `$O/maven-settings.xml`
  (sets only the local repository), `$O/toolchains.xml` (JDKs 8, 11, 17, 21, 25).
- `$O/artifacts/CASE-ROLE/`: built jars, `SHA256SUMS` (jar + every class of each changed production source file), `runtime-classpath.txt`,
  `test-classpath.txt` (`:`-joined, paths into `$O/m2` or `$O/gradle-home`); per-case exceptions are named in the case's section.
- `$O/releases/A-V/`: released artifacts from Maven Central with their `.sha1` (and `.sha256`/`.sha512` where published) checked and `.asc` beside them.
- `$O/logs/`: every build and test log (`TAG.log`) with a summary (`TAG.junit.txt`). `$O/upstream/prs/`: each PR's `gh api` record and changed files.
- Keyrings `$O/gnupg-A` … `$O/gnupg-D` (one per part of the setup; agents stopped), keys `$O/keys-A/` … `$O/keys-D/`.
- Helpers in `$O/scripts/`: `env.sh`, `pins.tsv`, `fetch.sh`, `worktrees.sh`, `mvn_case.sh` (one Maven run, 4 GB scope, log + JUnit summary),
  `keep_mvn.sh` (artifacts and classpaths), `junit_summary.py`, `central_get.sh` (Central download with checksum checks), `resolve-all.init.gradle`
  (adds tasks `setupResolveAll`, `setupWriteClasspath`; changes no upstream file), `cp_localize.py`, `assemble_record.sh` (writes this record from
  `$O/notes/`), and per-case job scripts `CASE_job.sh`.

`mvn_case.sh DIR TAG JDK [online] ARGS...` runs `systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- $MVN [-o] ARGS`
in DIR with `JAVA_HOME=JDK`, `MAVEN_OPTS=-Xmx1g`. The Maven commands in the case sections are its ARGS.

The setup was done in four parts at once (A: small Maven projects, B: medium Maven projects, C: large Maven projects and fastutil's Ant build,
D: Gradle projects); each part's section follows the summary.


## Cases R02–R40 (fork A)

Thirteen Maven cases, all built and tested inline (every run under a minute), with `$O/scripts/run_A.sh CASE JDK TESTS [MODULE]`: online `-DskipTests package` and the landed tests at the fix, online `-DskipTests package` at the parent, then offline: `package`, the landed tests on the fix, the parent's own copy of them on the parent, and the fix's changed test files overlaid on a copy of the parent (`$O/build/CASE-parent-landed`, the parent's tracked files plus the fix's changed `src/test` files; removed again, its surefire reports kept in `$O/logs/surefire/CASE-parent-landed/`). Each Maven run goes through `$O/scripts/mvn_A.sh DIR TAG JDK REPORTDIR [online] ARGS` (4 GB scope, `choom -n 500`, `MAVEN_OPTS=-Xmx1g`, log `$O/logs/TAG.log`, summary `$O/logs/TAG.junit.txt`). Test runs add `-Drat.skip` (RAT would flag the copy). Artifacts by `$O/scripts/keep_A.sh CASE ROLE JDK [MODULE] [online]`: `$O/artifacts/CASE-ROLE/` holds the jar, `SHA256SUMS` (jar and every class of each changed production file), `runtime-classpath.txt` and `test-classpath.txt` (`:`-joined, paths into `$O/m2`), each written online once and then again offline (checked). Build trees were removed afterwards (`git clean -fdx`); the offline commands rebuild in seconds.

Release side: jars, `-sources.jar` and POMs from Maven Central in `$O/releases/ARTIFACT-VERSION/` by `$O/scripts/central_get.sh` (every file's `.sha1`, and `.sha256`/`.sha512` where published, matched: 92 checks, `$O/logs/A-central-get.txt`). All 45 `.asc` signatures (15 releases × jar, sources, POM) are **good**, checked in the keyring `$O/gnupg-A` (agent and dirmngr stopped) with keys in `$O/keys-A/`: the Apache Commons `KEYS` (https://downloads.apache.org/commons/KEYS) and, from keyserver.ubuntu.com, `1D0A8B5E77C678A7C724445ABF984B4145EA13F7` (Egor Andreevici, JavaPoet), `B41089A2DA79B0FA5810252872385FF0AF338D52` (Stephen Colebourne, ThreeTen-Extra), `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (Christopher Povirk, Jimfs) and `C7BE5BCC9FEC15518CFDA882B0F3710FA64900E7` (Éamonn McManus, Gson). The Commons releases are signed by `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` or `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` (Gary Gregory). Per file: `$O/logs/A-release-signatures.txt`; jar digests: `$O/logs/A-release-sha256.txt`. Source comparison: `$O/scripts/relcmp_A.py` (git blob ids of each changed production file in the `-sources.jar` against both pins, `$O/logs/A-release-blobs.txt`) and, where neither matches, `$O/scripts/relhunks_A.py` (how many of the fix's added and the parent's removed lines the release file holds, `$O/logs/A-release-hunks.txt`).

### R02 · Apache Commons Collections #688 — unique IndexedCollection add atomicity

**Pins.** Parent `dad2ff61e516a601da8179708959263e38af8d68`, fix `ca83f8699e10403be6987b92fb1a877743df8262`. Changed: `src/changes/changes.xml` (+1 −0); `src/main/java/org/apache/commons/collections4/collection/IndexedCollection.java` (+11 −0); `src/test/java/org/apache/commons/collections4/collection/IndexedCollectionTest.java` (+11 −0).

**Build facts.** `org.apache.commons:commons-collections4:4.6.0-SNAPSHOT` (same at both pins), parent `org.apache.commons:commons-parent:102`, source/target 1.8 (classes major 52). Runtime classpath: `commons-codec-1.22.0.jar` only. Tests: JUnit Jupiter 5.14.3, junit-pioneer 1.9.1, EasyMock 5.6.0, guava-testlib 33.6.0-jre.

**Commands** (in `$W/R02-commons-collections-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 39 s, parent 17 s)
- **offline (checked)**: `-o -DskipTests package` (fix 6 s, parent 7 s)
- landed tests, offline: `-o -Drat.skip -Dtest=IndexedCollectionTest test` (fix 4 s)

**Landed tests.** Fix: `IndexedCollectionTest` 33 run, 0 failures. Parent's own copy on the parent: 32 run, 0 failures. Fix's copy on the parent: 33 run, **1 failure**, the new test: `testFailedUniqueAddDoesNotPolluteDecoratedCollection:144 expected: <1> but was: <2>` (the backing collection gained the rejected element). Logs: `$O/logs/R02-fix-landed.log`, `$O/logs/R02-parent-own.log`, `$O/logs/R02-parent-landed.log`.

**Release side.** Maven Central: 4.5.0 (2025-04-19, before the fix) and 4.6.0 (2026-08-06, after the merge). **Neither release's `IndexedCollection.java` is either pin** (blob `17084b2b6728722d6265cf6897e72a1bc2f1ab76` in 4.5.0, `c18ca39222faf29aec67736eedbf61bd6a0d3d86` in 4.6.0; the pins' blob ids are in `$O/logs/A-release-blobs.txt`) and neither contains the fix's added lines (0 of 2 distinct). 4.6.0's `add()` calls `toValidKey(object)` before `super.add(object)`, a different implementation from both pins; what that does with a duplicate key is for the domain work. No release on Central carries the fix's code. Signatures good (above).

**Artifacts** (`$O/artifacts/R02-parent/`, `$O/artifacts/R02-fix/`), sha256:
- parent: `commons-collections4-4.6.0-SNAPSHOT.jar` `6588aa90992c87ab9058e90ee459948857d8727da96f86062e93ec284c10be9b`
- parent: `org/apache/commons/collections4/collection/IndexedCollection.class` `d9db129fdcaecc38119fc02b6042b02689c53ac4dd0058b578188f94ab029404`
- fix: `commons-collections4-4.6.0-SNAPSHOT.jar` `b6ec4619cf6c5b43379c087acd4a9f5bdde960a7c346462adfa28005092c2d91`
- fix: `org/apache/commons/collections4/collection/IndexedCollection.class` `4bc76711ce285e4591153a8d11d335d55b2956a03bd378521e3f814a97ed4bc8`

### R06 · Apache Commons Lang #1865 — Fraction.divideBy at Integer.MIN_VALUE

**Pins.** Parent `ef7586831c7842c97ad4be8693ddef6f94bb8b64`, fix `355f246760cad21ca597424b49bb1151c0a63a96`. Changed: `src/main/java/org/apache/commons/lang3/math/Fraction.java` (+18 −1); `src/test/java/org/apache/commons/lang3/math/FractionTest.java` (+46 −0).

**Build facts.** `org.apache.commons:commons-lang3:3.22.1-SNAPSHOT`, parent `org.apache.commons:commons-parent:107`, source/target 1.8 (major 52). **No runtime dependencies** (the jar alone). Tests: JUnit Jupiter 5.14.4, junit-pioneer 1.9.1, Mockito 4.11.0, EasyMock 5.6.0. Built on JDK 17 (the PR reports JDK 25 targeting Java 8; CI covers 8–27).

**Commands** (in `$W/R06-commons-lang-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 40 s, parent 31 s)
- **offline (checked)**: `-o -DskipTests package` (fix 18 s, parent 13 s)
- landed tests, offline: `-o -Drat.skip -Dtest=FractionTest test` (fix 4 s)

**Landed tests.** Fix: `FractionTest` 58 run, 0 failures. Parent's own: 39 run, 0 failures. Fix's copy on the parent: 58 run, **10 errors**, the ten invocations the PR names: `testDivideIntegerMinValue(int, int, int, int, int, int)[1]`–`[9]` and `testDivideZeroByIntegerMinValue`, each `ArithmeticException: overflow: can't negate numerator` (lines 415 and 439). Logs: `$O/logs/R06-fix-landed.log`, `$O/logs/R06-parent-own.log`, `$O/logs/R06-parent-landed.log`.

**Release side.** Latest release 3.22.0 (2026-11-08, before the merge on 2026-11-15): its `Fraction.java` **is the parent's byte for byte** (blob `7a88070744d26f61a04f325533892aa5ac75446e`). No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R06-parent/`, `$O/artifacts/R06-fix/`), sha256:
- parent: `commons-lang3-3.22.1-SNAPSHOT.jar` `5d59b16aadb3a575ecd197dc1910bbbfe2018141465d224fa5bfda68292a1e4d`
- parent: `org/apache/commons/lang3/math/Fraction.class` `169d7d5cdb572abe6849948743a7eabd7cbca8b4b77f4ebbb26cdf6770ebd2eb`
- fix: `commons-lang3-3.22.1-SNAPSHOT.jar` `83c55bb5cf70de521699ddbe41212cf4fd893c7a33f54b91af5aabbeeddf2b3f`
- fix: `org/apache/commons/lang3/math/Fraction.class` `61135e062cac40633c0099a926200084b11f642092887d04ea175470dbb1d945`

### R11 · Apache Commons IO #931 — CharacterFilterReader bulk read and skip

**Pins.** Parent `31cc5e824df9726d08cf5ee8154c1721abc2668d`, fix `1af75d36371fb56603cccca8bfd8083f5c97d6f2`. Changed: `src/main/java/org/apache/commons/io/input/AbstractCharacterFilterReader.java` (+20 −13); `src/test/java/org/apache/commons/io/input/AbstractCharacterFilterReaderTest.java` (+191 −0, new).

**Build facts.** `commons-io:commons-io:2.23.0-SNAPSHOT`, parent `org.apache.commons:commons-parent:107`, source/target 1.8 (major 52), no runtime dependencies. Tests: JUnit Jupiter 5.14.x, Mockito 4.11.0.

**Commands** (in `$W/R11-commons-io-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 16 s, parent 15 s)
- **offline (checked)**: `-o -DskipTests package` (fix 6 s, parent 5 s)
- landed tests, offline: `-o -Drat.skip -Dtest=AbstractCharacterFilterReaderTest test` (fix 4 s)

**Landed tests.** The test class is **new** in the fix (`added`), so the parent has no copy of its own (`-Dtest=` matched nothing there). Fix: 28 run, 0 failures. Fix's copy on the parent: 28 run, **16 failures**, 8 tests × 2 values of their boolean parameter: `testReadAfterFilteredChunk:43 expected: <1> but was: <0>`, `testReadAllFiltered:55 expected: <-1> but was: <0>`, `testReadCharBuffer:64 expected: <1> but was: <0>`, `testReadShortDelegate:113 expected: <1> but was: <0>`, `testSkipAllFiltered:138 expected: <0> but was: <1>`, `testSkipBeyondEof:147 expected: <2> but was: <6>`, `testSkipCountsRetainedCharacters:158 expected: <98> but was: <97>`, `testSkipNegative:175 Expected java.lang.IllegalArgumentException to be thrown, but nothing was thrown.` Logs: `$O/logs/R11-fix-landed.log`, `$O/logs/R11-parent-own.log`, `$O/logs/R11-parent-landed.log`.

**Release side.** The PR says sixteen cases fail on "the released 2.22.0 JAR". 2.22.0 (2026-04-19) is the latest release; its `AbstractCharacterFilterReader.java` is neither pin byte for byte (blob `b9851d93b1dd91a3d9689f9fdce798e15bcde6dd`) but holds all 7 of the parent's removed lines and none of the fix's 10 added ones. **Checked on a JVM:** the fix's compiled test classes run against the classes of the released `commons-io-2.22.0.jar` (unpacked in place of `target/classes`, `jacoco:prepare-agent surefire:test`, offline): 28 run, **the same 16 failures** (`$O/logs/R11-release-2.22.0-landed.log`). No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R11-parent/`, `$O/artifacts/R11-fix/`), sha256:
- parent: `commons-io-2.23.0-SNAPSHOT.jar` `c1e58e416ac18390cdbca5ae38bfe4f85a079f54fd09c2418cb8b3651fcf7b8a`
- parent: `org/apache/commons/io/input/AbstractCharacterFilterReader.class` `49d29d5c4cff732f42974feb9acda99d1190bda490834545a54a7550c71eadac`
- fix: `commons-io-2.23.0-SNAPSHOT.jar` `b73226bb990f126dd45f4737b73c8cd319b7ed46ba73af591351b54067f5a206`
- fix: `org/apache/commons/io/input/AbstractCharacterFilterReader.class` `0e6b0c2b07ab94dc12d21739c14e3576fd231fa82af0715e6b742506cb89d1c7`

### R12 · Apache Commons IO #860 — BoundedReader.skip and the delegate position

**Pins.** Parent `cfe19ad9dcc9d0c7308e2dc187b2f8b57de21af0`, fix `e806e6b5926993ec6348a78542b1e1377a765e88`. Changed: `src/main/java/org/apache/commons/io/input/BoundedReader.java` (+10 −2); `src/test/java/org/apache/commons/io/input/BoundedReaderTest.java` (+30 −0).

**Build facts.** `commons-io:commons-io:2.23.0-SNAPSHOT`, parent `org.apache.commons:commons-parent:102`, source/target 1.8 (major 52), no runtime dependencies.

**Commands** (in `$W/R12-commons-io-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 16 s, parent 19 s)
- **offline (checked)**: `-o -DskipTests package` (fix 7 s, parent 9 s)
- landed tests, offline: `-o -Drat.skip -Dtest=BoundedReaderTest test` (fix 5 s)

**Landed tests.** Fix: `BoundedReaderTest` 19 run, 0 failures. Parent's own: 16 run, 0 failures. Fix's copy on the parent: 19 run, **3 failures**: `testSkipDoesNotExceedBound:250 expected: <3> but was: <11>`, `testSkipDoesNotOverflowCharsRead:258 expected: <3> but was: <11>`, `testSkipUsesActualSkippedCount:272 expected: <50> but was: <-1>`. The landed tests do not exercise `mark` with `skip` (the brief's challenge 860.3). Logs: `$O/logs/R12-fix-landed.log`, `$O/logs/R12-parent-own.log`, `$O/logs/R12-parent-landed.log`.

**Release side.** 2.22.0 (latest) `BoundedReader.java`: neither pin byte for byte (blob `5ba0dfe6b18d1938f0e2f37e8001aa2ef20d4509`); has the parent's 1 removed line, none of the fix's 7 added: parent side. No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R12-parent/`, `$O/artifacts/R12-fix/`), sha256:
- parent: `commons-io-2.23.0-SNAPSHOT.jar` `acc7044d601b86f4366548c519ddbd86fe2d5b73322478b3ab5a2e6235c1455b`
- parent: `org/apache/commons/io/input/BoundedReader.class` `4c572e26290c22448995921dfdf4201f72a27290b181e2532145be22f733d815`
- fix: `commons-io-2.23.0-SNAPSHOT.jar` `82a92fb64d84989329ddb93f6df0b470c612fd17ec3f6b43defb7144377adfcc`
- fix: `org/apache/commons/io/input/BoundedReader.class` `29db73f51ef61adcaa749ad68a63521ea0affe0639a24f1a0dec7366ddd4dc3f`

### R13 · Google Jimfs #435 — zero-length read after EOF

**Pins.** Parent `f0dcab50faa6626b9275d6604a89d7debfff3677`, fix `0e5725b4d44ec51d54fba15336aa23147c1bedc7`. Changed: `jimfs/src/main/java/com/google/common/jimfs/JimfsInputStream.java` (+3 −0); `jimfs/src/test/java/com/google/common/jimfs/JimfsInputStreamTest.java` (+19 −0); `jimfs/src/test/java/com/google/common/jimfs/JimfsUnixLikeFileSystemTest.java` (+1 −1).

**Build facts.** Module `jimfs` of the multi-module build (`-pl jimfs -am`), `com.google.jimfs:jimfs:HEAD-SNAPSHOT`, parent `com.google.jimfs:jimfs-parent:HEAD-SNAPSHOT`, `java.version` 1.8 (major 52); built on JDK 21 (CI runs 8, 11, 21). Runtime classpath (9 entries, `runtime-classpath.txt`): guava 33.5.0-jre, failureaccess, listenablefuture, error_prone_annotations 2.41.0, j2objc-annotations, icu4j 77.1, auto-service-annotations, jsr305, jspecify. Tests: JUnit 4.13.2, Truth.

**Commands** (in `$W/R13-jimfs-ROLE`, JDK `$J21`; ARGS of `mvn_A.sh`):
- online, first resolution: `-pl jimfs -am -Dsurefire.failIfNoSpecifiedTests=false -DskipTests package` (fix 24 s, parent 17 s)
- **offline (checked)**: `-o -pl jimfs -am -Dsurefire.failIfNoSpecifiedTests=false -DskipTests package` (fix 5 s, parent 6 s)
- landed tests, offline: `-o -pl jimfs -am -Dsurefire.failIfNoSpecifiedTests=false -Drat.skip -Dtest=JimfsInputStreamTest,JimfsUnixLikeFileSystemTest test` (fix 2 s)

**Landed tests.** Fix: `JimfsInputStreamTest` 15 + `JimfsUnixLikeFileSystemTest` 101, 0 failures. Parent's own: 13 + 101, 0 failures. Fix's copies on the parent: 15 + 101, **1 failure**: `JimfsInputStreamTest.testRead_zeroLengthAtEof_returnsZero:133 value of: read(...) expected: 0 but was : -1`. The adjusted `JimfsUnixLikeFileSystemTest` passes on the parent too. Logs: `$O/logs/R13-fix-landed.log`, `$O/logs/R13-parent-own.log`, `$O/logs/R13-parent-landed.log`.

**Release side.** 1.3.1 (2025-07-11) lacks the fix's one added line (blob `41bcc91135547db84c8e81f33e76377d3d4e0e65`, parent side). **1.3.2 (2026-08-18) `JimfsInputStream.java` is the fix's byte for byte** (blob `f83aa2f1cccbb6843d20cf311090be30e998498c`). Signatures good (above).

**Artifacts** (`$O/artifacts/R13-parent/`, `$O/artifacts/R13-fix/`), sha256:
- parent: `jimfs-HEAD-SNAPSHOT.jar` `696942f8352984abb66a67fe6e350c98aaecb27e99952b5efcd3df8ed853fd74`
- parent: `com/google/common/jimfs/JimfsInputStream.class` `e83b147789b2370af6b78d5cf3cbb17c55539ef8bf5f14632040d46651b796e0`
- fix: `jimfs-HEAD-SNAPSHOT.jar` `cfb54d8fec9ef0a8ec7b55ab7514b63c9ea90945c83619a74cb5c5df6651e4cd`
- fix: `com/google/common/jimfs/JimfsInputStream.class` `43f11611814faa8a8597b2a9f4fece1abe8244af3ad6ac4056bf15e36e89bba9`

### R15 · Apache Commons Codec #437 — custom Base58 alphabet

**Pins.** Parent `ac982579962c32ee28be1e80cdb514a829e3366f`, fix `98986558dc1c0e2013b76bea92d75bde80568a00`. Changed: `src/changes/changes.xml` (+1 −0); `src/main/java/org/apache/commons/codec/binary/Base58.java` (+69 −23); `src/test/java/org/apache/commons/codec/binary/Base58Test.java` (+53 −0).

**Build facts.** `commons-codec:commons-codec:1.22.1-SNAPSHOT`, parent `org.apache.commons:commons-parent:102`, source/target 1.8 (major 52), no runtime dependencies.

**Commands** (in `$W/R15-commons-codec-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 12 s, parent 14 s)
- **offline (checked)**: `-o -DskipTests package` (fix 6 s, parent 6 s)
- landed tests, offline: `-o -Drat.skip -Dtest=Base58Test test` (fix 5 s)

**Landed tests.** Fix: `Base58Test` 27 run, 0 failures. Parent's own: 22 run, 0 failures. Fix's copy on the parent: 27 run, **5 failures**: `testBuilderCustomEncodeTableAffectsEncodeAndDecode:86 expected: <1> but was: <2>`, `testBuilderCustomEncodeTableAffectsIsInAlphabet:95 expected: <true> but was: <false>`, `testBuilderCustomEncodeTableAffectsLeadingZeros:106 expected: <221> but was: <112>`, `testBuilderCustomEncodeTableRejectsDuplicateEntries:114` and `testBuilderCustomEncodeTableRejectsInvalidLength:119` (`Expected java.lang.IllegalArgumentException to be thrown, but nothing was thrown.`). Logs: `$O/logs/R15-fix-landed.log`, `$O/logs/R15-parent-own.log`, `$O/logs/R15-parent-landed.log`.

**Release side.** 1.22.0 (2026-04-19): parent side (all 22 of the parent's removed lines, none of the fix's 49 added; blob `5372dd8e53674becfb4ad349d32808c6212a320e`). 1.22.1 (2026-07-27): 46 of the 49 added lines, none of the removed (blob `7633646a95622acbf9c81d5161c745ca90432486`). 1.23.0 (2026-10-04): 40 of 49 added, none removed (blob `8c309bb57c5d046d6d4028523ce01a9360feb5c8`). So 1.22.1 is the first release with the fix, though **no release file equals the fix's byte for byte**. Signatures good (above).

**Artifacts** (`$O/artifacts/R15-parent/`, `$O/artifacts/R15-fix/`), sha256:
- parent: `commons-codec-1.22.1-SNAPSHOT.jar` `fc764314c518341e67b7b6d53a55485fdbac1545bf81882e776cf8807b82e2a0`
- parent: `org/apache/commons/codec/binary/Base58$Builder.class` `70e90adb7489b961e29c1b230e7ed3ea50ebcc8a9f5c1223710fe77dcb4164e8`
- parent: `org/apache/commons/codec/binary/Base58.class` `baba8a2b287e64d6a9459f417bfa94230dec607faba5c23b538f35b8040481f9`
- fix: `commons-codec-1.22.1-SNAPSHOT.jar` `33fef9d7b8501930257b86f54756e754f628337edbb703b28a2ea4e3d49f76a2`
- fix: `org/apache/commons/codec/binary/Base58$Builder.class` `11ec7d218d86408c23c07d58d459df13a732ad9998c89dac91e0484e9952546d`
- fix: `org/apache/commons/codec/binary/Base58.class` `e08c91f1a298689b635c8b3664a40e29ed3ee5ed534a763b7d20d8eb2de3af23`

### R16 · Apache Commons Compress #725 — CPIO checksum with a destination offset

**Pins.** Parent `a7a749f028a38a07c6b3765a4b2c3607b1ab6e71`, fix `befbfe070270f61c29e032b51363dfc8c8ef51f1`. Changed: `src/changes/changes.xml` (+1 −0); `src/main/java/org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream.java` (+2 −2); `src/test/java/org/apache/commons/compress/archivers/cpio/CpioArchiveInputStreamTest.java` (+17 −0).

**Build facts.** `org.apache.commons:commons-compress:1.29.0-SNAPSHOT`, parent `org.apache.commons:commons-parent:89`, source/target 1.8 (major 52). The PR's base branch is `commons_io_2_21_0`, and both pins depend on **`commons-io:commons-io:2.21.0-SNAPSHOT`**, which the Apache snapshot repository no longer serves (404; its commons-io snapshots are now 2.23.0-SNAPSHOT) and Central never had. **Substitution:** commons-io built from its public source at `e19519ad1a61ec6852601d28ffe94a8967e4e3e0` (tree `4a439badec33636a6a34fe62551ad12ad8337f1a`, 2025-10-10T06:58:55-04:00, the last commit on commons-io `master` before the fix merged; its version is `2.21.0-SNAPSHOT`), worktree `$W/R16-subst-commons-io-e19519ad1a61ec6852601d28ffe94a8967e4e3e0`, `mvn -DskipTests -Drat.skip install` on JDK 17 (17 s) into `$O/m2`; jar sha256 `3740da21bcac36e8cda476d6afc40cc60dd122be1c3df535bf965341c6a9b845`. Between the parent's date (2025-10-08 18:42Z) and the fix's, commons-io `master` gained only 5 commits (typos, commons-parent 88→89, test/CI bumps), so one revision stands for both sides. No upstream file was changed. Runtime classpath: zstd-jni 1.5.7-4, brotli dec 0.1.2, xz 1.10, commons-codec 1.19.0, asm 9.9, commons-io 2.21.0-SNAPSHOT (the substitute), commons-lang3 3.19.0.

**Commands** (in `$W/R16-commons-compress-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 25 s, parent 31 s)
- **offline (checked)**: `-o -DskipTests package` (fix 25 s, parent 16 s)
- landed tests, offline: `-o -Drat.skip -Dtest=CpioArchiveInputStreamTest test` (fix 6 s)
- The offline `package` right after a `-Dtest=` run fails jacoco's coverage `check` (the partial `jacoco.exec` is left in `target`); use `clean package` (checked) or `-Djacoco.skip`. Classpaths for the older parent 89 needed the dependency plugin resolved online once (done).

**Landed tests.** Fix: `CpioArchiveInputStreamTest` 10 run, 0 failures. Parent's own: 9 run, 0 failures. Fix's copy on the parent: 10 run, **1 error**: `testCrcVerification:195 Unexpected exception thrown: org.apache.commons.compress.archivers.ArchiveException: CRC Error. Occurred at byte: 155`. Logs: `$O/logs/R16-fix-landed.log`, `$O/logs/R16-parent-own.log`, `$O/logs/R16-parent-landed.log`.

**Release side.** Latest release 1.28.0 (2025-07-26): `CpioArchiveInputStream.java` is neither pin (blob `09199fd5ed49bea51260b75688656113e11a951c`, no Builder class); its loop has `this.crc += b[pos] & 0xFF;` — the parent's indexing. No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R16-parent/`, `$O/artifacts/R16-fix/`), sha256:
- parent: `commons-compress-1.29.0-SNAPSHOT.jar` `41e50bb790b6da650cc7a7e5b560336544bcc72bfd211824a338c59a18c20b66`
- parent: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream$1.class` `f0d7331680a1cbdb12707a97f1e3732d356e1d337c899ebf2334bbec25efc298`
- parent: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream$Builder.class` `7784c58e27586369c22b87db6c5b28c7a3e182df8de765ccef1b44a0b5a51282`
- parent: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream.class` `12a0f34d7ff3174ca48c6897ba7221b7f90c942ed32546bc8491c9bdb127c974`
- fix: `commons-compress-1.29.0-SNAPSHOT.jar` `5e368b873069e12bcf95c7ac73e8cb99c404206009da9c006f1262ef198e1108`
- fix: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream$1.class` `f0d7331680a1cbdb12707a97f1e3732d356e1d337c899ebf2334bbec25efc298`
- fix: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream$Builder.class` `7784c58e27586369c22b87db6c5b28c7a3e182df8de765ccef1b44a0b5a51282`
- fix: `org/apache/commons/compress/archivers/cpio/CpioArchiveInputStream.class` `eb0d85a87d19f3914513621268cf18bec033c270cd481a35117e28e57d676848`

### R17 · Apache Commons Compress #775 — aligned GNU PAX 1.0 sparse map

**Pins.** Parent `a8cb750e5bdd0fe136d5d9cab38781f9447b2dd3`, fix `948512a35a9f8ed1f8eac12f743e879aff9266d2`. Changed: `src/changes/changes.xml` (+1 −0); `src/main/java/org/apache/commons/compress/archivers/tar/TarUtils.java` (+1 −1); `src/test/java/org/apache/commons/compress/archivers/tar/TarUtilsTest.java` (+43 −0).

**Build facts.** `org.apache.commons:commons-compress:1.29.0-SNAPSHOT`, parent `org.apache.commons:commons-parent:102`, source/target 1.8 (major 52). Runtime classpath: zstd-jni 1.5.7-11, brotli dec 0.1.2, xz 1.12, commons-codec 1.22.0, asm 9.10.1, commons-io 2.22.0, commons-lang3 3.20.0 (all released).

**Commands** (in `$W/R17-commons-compress-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 37 s, parent 24 s)
- **offline (checked)**: `-o -DskipTests package` (fix 11 s, parent 12 s)
- landed tests, offline: `-o -Drat.skip -Dtest=TarUtilsTest test` (fix 5 s)

**Landed tests.** Fix: `TarUtilsTest` 63 run, 0 failures. Parent's own: 62 run, 0 failures. Fix's copy on the parent: 63 run, **1 failure**: `testParsePAX1XSparseHeadersDoesNotSkipAlignedDataRecord:370 expected: <65> but was: <66>` (the next raw byte is `B` instead of `A`, as the brief says). Logs: `$O/logs/R17-fix-landed.log`, `$O/logs/R17-parent-own.log`, `$O/logs/R17-parent-landed.log`.

**Release side.** 1.28.0 (latest) `TarUtils.java`: neither pin (blob `72c0cf0f7c2a8ec2bae50a31cd4407310761734e`), has the parent's removed line, not the fix's: parent side. No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R17-parent/`, `$O/artifacts/R17-fix/`), sha256:
- parent: `commons-compress-1.29.0-SNAPSHOT.jar` `43f751ba0860c83284612038620532e9408d6aad276cc43561a75948f038e5ab`
- parent: `org/apache/commons/compress/archivers/tar/TarUtils$1.class` `3fbd3c0fc79d1a28a58537a4a851d9536ff02a42cdc82565c79a04d4bd4c79ed`
- parent: `org/apache/commons/compress/archivers/tar/TarUtils.class` `4473131dba1900c74b6ba3714ddfa1e185cec818e543a3b9ce249fa8d70f2390`
- fix: `commons-compress-1.29.0-SNAPSHOT.jar` `0996f45284ce748dfa6eaf60db21f67d993ae93f24cbc29e8b20cecb4aed0c27`
- fix: `org/apache/commons/compress/archivers/tar/TarUtils$1.class` `3fbd3c0fc79d1a28a58537a4a851d9536ff02a42cdc82565c79a04d4bd4c79ed`
- fix: `org/apache/commons/compress/archivers/tar/TarUtils.class` `623b94eeadbc2260ba1cb2eea650a3513257f1e35cdd4636be707bc6ecd3d40b`

### R20 · Apache Commons CSV #412 — MONGODB_CSV empty first column

**Pins.** Parent `2abebaa74eb413ece7a56d86f826bc690ee26df9`, fix `5770cc07e351cc124d34a6049c59e9aea8885675`. Changed: `src/main/java/org/apache/commons/csv/Lexer.java` (+12 −12); `src/test/java/org/apache/commons/csv/CSVParserTest.java` (+35 −0).

**Build facts.** `org.apache.commons:commons-csv:1.11.0-SNAPSHOT`, parent `org.apache.commons:commons-parent:69`, source/target 1.8 (major 52). Runtime classpath: commons-io 2.16.0, commons-codec 1.16.1.

**Commands** (in `$W/R20-commons-csv-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 23 s, parent 12 s)
- **offline (checked)**: `-o -DskipTests package` (fix 6 s, parent 5 s)
- landed tests, offline: `-o -Drat.skip -Dtest=CSVParserTest test` (fix 4 s)

**Landed tests.** Fix: `CSVParserTest` 117 run, 0 failures, 4 skipped. Parent's own: 116 run, 4 skipped. Fix's copy on the parent: 117 run, **1 error**: `testParsingPrintedEmptyFirstColumn:1587 RuntimeException: format: MongoDBCsv` caused by `IOException: (startline 2) EOF reached before encapsulated token finished` (with a suppressed `format: MongoDBTsv`). Logs: `$O/logs/R20-fix-landed.log`, `$O/logs/R20-parent-own.log`, `$O/logs/R20-parent-landed.log`.

**Release side.** 1.10.0 (2023-01-28): parent side (blob `06b2c9c222e507c97f19a2b97d69e1be107a33c7`). **1.11.0 (2024-04-28) `Lexer.java` is the fix's byte for byte** (blob `80bde6c7e8161141e31a50e2854eef867dadba63`). Signatures good (above).

**Artifacts** (`$O/artifacts/R20-parent/`, `$O/artifacts/R20-fix/`), sha256:
- parent: `commons-csv-1.11.0-SNAPSHOT.jar` `21ead670a5dc7baa056185fcf35f2d3cb6b8797752eca7c6866689562fbe07ca`
- parent: `org/apache/commons/csv/Lexer.class` `2bdbf22f594b086913c0014f906ce76c3d3ae6a9932bf0e203bd5c7b0b289e45`
- fix: `commons-csv-1.11.0-SNAPSHOT.jar` `d8a7a7391bc192ada00426432109950c9964c29398443535e163d2cd1281c9eb`
- fix: `org/apache/commons/csv/Lexer.class` `5cf3677f061176248826537dd9393d91fded573621af0a6357b50f7844790651`

### R21 · Square JavaPoet #994 — long annotation member literal

**Pins.** Parent `aaebc488320bd11aab1a6248d6b8058a255c92df`, fix `c9925e48577e3e74b91eb737b2c2b3c22109cde8`. Changed: `src/main/java/com/squareup/javapoet/AnnotationSpec.java` (+3 −0); `src/test/java/com/squareup/javapoet/AnnotationSpecTest.java` (+2 −2).

**Build facts.** `com.squareup:javapoet:1.14.0-SNAPSHOT`, parent `org.sonatype.oss:oss-parent:7`, `java.version` 1.8 (major 52); built on **JDK 8** (CI uses 8). No runtime dependencies. Tests: JUnit 4.13.2, Truth, compile-testing 0.21.0, Mockito.

**Commands** (in `$W/R21-javapoet-ROLE`, JDK `$J8`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 8 s, parent 6 s)
- **offline (checked)**: `-o -DskipTests package` (fix 2 s, parent 2 s)
- landed tests, offline: `-o -Drat.skip -Dtest=AnnotationSpecTest test` (fix 3 s)

**Landed tests.** Fix: `AnnotationSpecTest` 11 run, 0 failures. Parent's own: 11 run, 0 failures (the PR only edits the golden string). Fix's copy on the parent: 11 run, **1 failure**: `reflectAnnotationWithDefaults:304` with the diff `-    d = 12345678910L,` / `+    d = 12345678910,`. Logs: `$O/logs/R21-fix-landed.log`, `$O/logs/R21-parent-own.log`, `$O/logs/R21-parent-landed.log`.

**Release side.** The only and last release is 1.13.0 (2020-06-18); its `AnnotationSpec.java` (blob `5525d7b487561e75c596c0dfd1d2ab084eff9e8a`) lacks the fix's 2 added lines. No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R21-parent/`, `$O/artifacts/R21-fix/`), sha256:
- parent: `javapoet-1.14.0-SNAPSHOT.jar` `b7c5b03820aa38d35e1c2547901f7d68f373f6c388ba2420cadd7c775e96bd67`
- parent: `com/squareup/javapoet/AnnotationSpec$1.class` `cc537c781cd1c3dab44e43f8a798c71a96b14d110ae57b7b10398c2fe3c84d83`
- parent: `com/squareup/javapoet/AnnotationSpec$Builder.class` `f6d3ec9f5338322988d6eb11187069d1454272b2b9f121597ec121ed331ed2e1`
- parent: `com/squareup/javapoet/AnnotationSpec$Visitor.class` `80ba9202ba5274c817fb6e5a1b236b5bc40ac8e53537bb415314961f4b1b6449`
- parent: `com/squareup/javapoet/AnnotationSpec.class` `6714477394f561e5ec7def68427167ebe8c1e46a3ce9b7aea742f35b065e24bb`
- fix: `javapoet-1.14.0-SNAPSHOT.jar` `3fc2cb4ab0e3c945ce4f87dc55354cbdc22256c6a77e9a4b6d4d8987b7c14652`
- fix: `com/squareup/javapoet/AnnotationSpec$1.class` `cc537c781cd1c3dab44e43f8a798c71a96b14d110ae57b7b10398c2fe3c84d83`
- fix: `com/squareup/javapoet/AnnotationSpec$Builder.class` `1428979fc3f7694f55ec3c9cb71b860b4b6ccfdd823ad21ca611c753f2de9030`
- fix: `com/squareup/javapoet/AnnotationSpec$Visitor.class` `1fad5c7c788c08b40516a08fd1f748276effe05a6c1d9d5e603b6e407a426da9`
- fix: `com/squareup/javapoet/AnnotationSpec.class` `6714477394f561e5ec7def68427167ebe8c1e46a3ce9b7aea742f35b065e24bb`

### R22 · Square JavaPoet #986 — box and unbox annotated primitives

**Pins.** Parent `0d55218ae3b8c8d6fe84132b7867d8c12698ce5e`, fix `d682f2013751d25725349d79b449870d0e77354c`. Changed: `src/main/java/com/squareup/javapoet/TypeName.java` (+37 −28); `src/test/java/com/squareup/javapoet/TypeNameTest.java` (+15 −0).

**Build facts.** As R21: `com.squareup:javapoet:1.14.0-SNAPSHOT`, JDK 8, major 52, no runtime dependencies.

**Commands** (in `$W/R22-javapoet-ROLE`, JDK `$J8`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 7 s, parent 6 s)
- **offline (checked)**: `-o -DskipTests package` (fix 2 s, parent 2 s)
- landed tests, offline: `-o -Drat.skip -Dtest=TypeNameTest test` (fix 2 s)

**Landed tests.** Fix: `TypeNameTest` 14 run, 0 failures. Parent's own: 12 run, 0 failures. Fix's copy on the parent: 14 run, **2 failures, 1 error**: `canBoxAnnotatedPrimitive:184` (message `boolean`), `isBoxedPrimitive:180 value of: isBoxedPrimitive()`, and `canUnboxAnnotatedPrimitive:190 UnsupportedOperationException: cannot unbox java.lang. @java.lang.Object Boolean`. Logs: `$O/logs/R22-fix-landed.log`, `$O/logs/R22-parent-own.log`, `$O/logs/R22-parent-landed.log`.

**Release side.** 1.13.0's `TypeName.java` **is the parent's byte for byte** (blob `c0986bb998d6765202b34b0c9c03e7e99891b3ca`). No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R22-parent/`, `$O/artifacts/R22-fix/`), sha256:
- parent: `javapoet-1.14.0-SNAPSHOT.jar` `e691f97cec33f441b314f5238d70b649cce257b9ebc1fbda7e4544f8b1757a2f`
- parent: `com/squareup/javapoet/TypeName$1.class` `56bafc05874e1cecb267c10fff75845c6c76f113d259a76960c204bbe6703941`
- parent: `com/squareup/javapoet/TypeName$2.class` `88d953f92b290c65d6b92e9c0850b27980586e028bc567a960a2834a116c27c3`
- parent: `com/squareup/javapoet/TypeName.class` `c767daa9f8022d9c529c0beef6fde04b3950d791d0ed54cb610f1c0e437fc377`
- fix: `javapoet-1.14.0-SNAPSHOT.jar` `160644be3c1422534ec9886474d70492a05493d7e8cb71d083a4d13aa60ab054`
- fix: `com/squareup/javapoet/TypeName$1.class` `3d6d5254ad01cc622f6dd616fb678a9e21e43b53eb85c2b9e1f87f169edbea2c`
- fix: `com/squareup/javapoet/TypeName$2.class` `0813d487d1adc603b9cbb898cad12f62a14e2ad9916a70a473b8c11159df8429`
- fix: `com/squareup/javapoet/TypeName.class` `cd042c7a989bb1b79733e87fc7ba3133ecbbc765dafbf7d4171c418f53644f7f`

### R26 · Google Gson #2998 — toJsonTree keeps Byte/Short/Integer

**Pins.** Parent `c616243d1d78c0466b53be39f893094ebb7c6918`, fix `e83ef91dc7614e6f8fb5ea8dd3fd67530602f05c`. Changed: `gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java` (+3 −3); `gson/src/test/java/com/google/gson/functional/PrimitiveTest.java` (+27 −0).

**Build facts.** Module `gson` (`-pl gson -am`), `com.google.code.gson:gson:2.15.1-SNAPSHOT`, parent `com.google.code.gson:gson-parent:2.15.1-SNAPSHOT`, `maven.compiler.release` 8 (major 52). The enforcer requires a JDK in [17,26): built on JDK 17. Runtime classpath: `error_prone_annotations-2.51.0.jar`. The module has a second surefire execution, `java-time-test`, which runs `JavaTimeTest` (23 tests) even with `-DskipTests` and `-Dtest=`; it passes everywhere.

**Commands** (in `$W/R26-gson-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-pl gson -am -Dsurefire.failIfNoSpecifiedTests=false -DskipTests package` (fix 12 s, parent 10 s)
- **offline (checked)**: `-o -pl gson -am -Dsurefire.failIfNoSpecifiedTests=false -DskipTests package` (fix 6 s, parent 4 s)
- landed tests, offline: `-o -pl gson -am -Dsurefire.failIfNoSpecifiedTests=false -Drat.skip -Dtest=PrimitiveTest test` (fix 5 s)

**Landed tests.** Fix: `PrimitiveTest` 107 run, 0 failures. Parent's own: 106 run, 0 failures. Fix's copy on the parent: 107 run, **1 failure**: `testToJsonTreePreservesIntegralType:169 value of: getClass() expected: class java.lang.Byte but was : class java.lang.Long`. Logs: `$O/logs/R26-fix-landed.log`, `$O/logs/R26-parent-own.log`, `$O/logs/R26-parent-landed.log`.

**Release side.** Latest release 2.15.0 (2026-10-24): `TypeAdapters.java` neither pin byte for byte (blob `5c7cc5df0ff618858111544da26356884817b3e4`) but holds the parent's 3 removed lines and none of the fix's: parent side. No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R26-parent/`, `$O/artifacts/R26-fix/`), sha256:
- parent: `gson-2.15.1-SNAPSHOT.jar` `d0f1405d0f7ff2bfe9b58ae2590cf8735f9b22ec56e4d0c0e9c4263a1fba2a31`
- parent: `com/google/gson/internal/bind/TypeAdapters$10.class` `94a4e51d8abe6a272a87c3b8b72b83ed0dd55e5d561ec60890e637abf788c0fc`
- parent: `com/google/gson/internal/bind/TypeAdapters$11.class` `9696e30f97f8d14dd716548433069311fa7d0bed3921775dba5929d65dba365b`
- parent: `com/google/gson/internal/bind/TypeAdapters$12.class` `97e04db29158b380c8240c0ea1967c38d006c7cf8bc7b09eb892276e47e7b1d7`
- parent: `com/google/gson/internal/bind/TypeAdapters$13.class` `25a5a5f7451117379c2ca9c301e979ed1e3152d1b39190c0619e9273f4d0693b`
- parent: `com/google/gson/internal/bind/TypeAdapters$14.class` `01738c48e6d5c8d16cf7afc980bdf43dfe4a296618748fd1d41ae6c3b893f639`
- parent: `com/google/gson/internal/bind/TypeAdapters$15.class` `1ecc3a2c94352f2439b72affdf5b8de4aed78bd3e842e607dbf17a6b09756779`
- parent: `com/google/gson/internal/bind/TypeAdapters$16.class` `5b3f2a4145689874c4e8b59722a57b3bb5449811533971236723fbf328d3bc60`
- parent: `com/google/gson/internal/bind/TypeAdapters$17.class` `9c16d9867e12504ec360a50648b44ac0bf5b283f22d0a4a66282b10c57fae010`
- parent: `com/google/gson/internal/bind/TypeAdapters$18.class` `5f3150b23ba283c9e258ceb25f652fbc561d47bc480e785a46937050823bf9dd`
- parent: `com/google/gson/internal/bind/TypeAdapters$19.class` `1b5b76739daaeeefb7c52bc7d59f27ac8bb40b0a5eb6a317950c7c49a38a2dc8`
- parent: `com/google/gson/internal/bind/TypeAdapters$1.class` `f0bfd46456f59c8f152a4da6ca70b4b7bd8f319e3883bd1d6c1b7e2e611eb527`
- parent: `com/google/gson/internal/bind/TypeAdapters$20.class` `ce2e32190ae801770f14f77d41222f556136c081b0525ff1335d742080d6128b`
- parent: `com/google/gson/internal/bind/TypeAdapters$21.class` `9e58da882f522d483bd2e7ba651d0332ce1eecea601bf60b4989a3b9ef4424b6`
- parent: `com/google/gson/internal/bind/TypeAdapters$22.class` `5470c1fe83985e4ee6712aba602b9adcb2756c414ac504bb6f8bd2e59c641aa0`
- parent: `com/google/gson/internal/bind/TypeAdapters$23.class` `61dc57a94bb47c1547f650b99f8d649517dd70682010117be612226539d75dfe`
- parent: `com/google/gson/internal/bind/TypeAdapters$24.class` `b0e6e4d1f56985a6a3f5e4714eb4d96bbcf53585534d76c9e86e28e9dafc1980`
- parent: `com/google/gson/internal/bind/TypeAdapters$25.class` `fd37589f64926b8a0ad9d2ebdc01bec016e1b4c9187fd396fea6ffc0b2c1f593`
- parent: `com/google/gson/internal/bind/TypeAdapters$26.class` `cf564d2d219dc5f14d90031bde152c2693c58faa6a2ed1ab2413192fc55402ba`
- parent: `com/google/gson/internal/bind/TypeAdapters$27.class` `d7baef3b289511dd8ea97dc748c7445fda07a5bccb6234f5ebd28e2cf74440ba`
- parent: `com/google/gson/internal/bind/TypeAdapters$28.class` `e664a7de2d4146c8106f0c9a2f4b0f74c0984b4fe55e31b5881ba7362da65e0f`
- parent: `com/google/gson/internal/bind/TypeAdapters$29.class` `48b04580508018244cb04e71a5d7ab52fbf414ea5f1cce25a3c0a18835f4d867`
- parent: `com/google/gson/internal/bind/TypeAdapters$2.class` `01d7e5a008ca8406a7360ba362f6e29fe668adcacf3a53c92918ea4c9984a110`
- parent: `com/google/gson/internal/bind/TypeAdapters$30.class` `bd06aeb151a3186a110b82d9f1fde30f3c2ec6d6031f829d89eadde15af98a04`
- parent: `com/google/gson/internal/bind/TypeAdapters$31.class` `9dd9fad5584763499567485b625e61be34807490b82a917fa141e91e353331f0`
- parent: `com/google/gson/internal/bind/TypeAdapters$32.class` `912b9bb59686204c23f6dc56d38bf7e7e1dea94478cb5a8a08de726c89883ea3`
- parent: `com/google/gson/internal/bind/TypeAdapters$33$1.class` `06f54a61e6907cb3fb1bf91354ebab8eb72748386214092769b894f573588bf8`
- parent: `com/google/gson/internal/bind/TypeAdapters$33.class` `ea8c14b95e03ca787915484e12b99d6d3118f6f93e10741e79afb8cdf0bdfafb`
- parent: `com/google/gson/internal/bind/TypeAdapters$34.class` `2ab5428411e976d5345d49c5bd576e8df37f022652fae0cb0975291674ee452e`
- parent: `com/google/gson/internal/bind/TypeAdapters$3.class` `18f1ded9b1636bc66ff0b404dee6e5c6b0c78ea2e049542bc9ea9627ae53f9c1`
- parent: `com/google/gson/internal/bind/TypeAdapters$4.class` `21fa71a81c4d4492339e21134fae22b8940f90f518f5ea0625bc2bb56af76d10`
- parent: `com/google/gson/internal/bind/TypeAdapters$5.class` `9ccac6deefd5d2a77504da4248a9457de9da1af933d11fee04e6c360e3448c6f`
- parent: `com/google/gson/internal/bind/TypeAdapters$6.class` `4d4a5d69bb56b4c28064320e6c1440ef3184bf4058ebfbc397dbe94564698015`
- parent: `com/google/gson/internal/bind/TypeAdapters$7.class` `50a66a66f1f38d30bc99dfba5e624ea4315dea27795574d90089cb764a2d8475`
- parent: `com/google/gson/internal/bind/TypeAdapters$8.class` `e0e004e54317b6865cda1466453a322493bd7552e38d1c170a1ae479f7bd9df7`
- parent: `com/google/gson/internal/bind/TypeAdapters$9.class` `9dd24dc234d83da49e311e6a78cbcea36f0c35ea2ed659ab88e07ae73c28a0d0`
- parent: `com/google/gson/internal/bind/TypeAdapters$DoubleAdapter.class` `109cdc18b5f2cde2cac0aea5ac3f34f447e71dbbb5bc8d93742c4a058686964b`
- parent: `com/google/gson/internal/bind/TypeAdapters$FloatAdapter.class` `223a3f78eeb67076e867fbf2274ff6181fac98b8e4434fb9f5f6409375950772`
- parent: `com/google/gson/internal/bind/TypeAdapters$IntegerFieldsTypeAdapter.class` `58163cf5e855305e7d6d3fbdfe7512548c6e90aa1bc6a0737af78751a93d0885`
- parent: `com/google/gson/internal/bind/TypeAdapters.class` `9f1ae499020777ea671f1811970cbd109dcdd988d3f8ec5bceebdaa60e07f22e`
- fix: `gson-2.15.1-SNAPSHOT.jar` `5f93c520f0a2440b4602ea6efabb214cd8f976f4337d1f2d7778b5f095c5b1e8`
- fix: `com/google/gson/internal/bind/TypeAdapters$10.class` `94a4e51d8abe6a272a87c3b8b72b83ed0dd55e5d561ec60890e637abf788c0fc`
- fix: `com/google/gson/internal/bind/TypeAdapters$11.class` `9696e30f97f8d14dd716548433069311fa7d0bed3921775dba5929d65dba365b`
- fix: `com/google/gson/internal/bind/TypeAdapters$12.class` `97e04db29158b380c8240c0ea1967c38d006c7cf8bc7b09eb892276e47e7b1d7`
- fix: `com/google/gson/internal/bind/TypeAdapters$13.class` `25a5a5f7451117379c2ca9c301e979ed1e3152d1b39190c0619e9273f4d0693b`
- fix: `com/google/gson/internal/bind/TypeAdapters$14.class` `01738c48e6d5c8d16cf7afc980bdf43dfe4a296618748fd1d41ae6c3b893f639`
- fix: `com/google/gson/internal/bind/TypeAdapters$15.class` `1ecc3a2c94352f2439b72affdf5b8de4aed78bd3e842e607dbf17a6b09756779`
- fix: `com/google/gson/internal/bind/TypeAdapters$16.class` `5b3f2a4145689874c4e8b59722a57b3bb5449811533971236723fbf328d3bc60`
- fix: `com/google/gson/internal/bind/TypeAdapters$17.class` `9c16d9867e12504ec360a50648b44ac0bf5b283f22d0a4a66282b10c57fae010`
- fix: `com/google/gson/internal/bind/TypeAdapters$18.class` `5f3150b23ba283c9e258ceb25f652fbc561d47bc480e785a46937050823bf9dd`
- fix: `com/google/gson/internal/bind/TypeAdapters$19.class` `1b5b76739daaeeefb7c52bc7d59f27ac8bb40b0a5eb6a317950c7c49a38a2dc8`
- fix: `com/google/gson/internal/bind/TypeAdapters$1.class` `f0bfd46456f59c8f152a4da6ca70b4b7bd8f319e3883bd1d6c1b7e2e611eb527`
- fix: `com/google/gson/internal/bind/TypeAdapters$20.class` `ce2e32190ae801770f14f77d41222f556136c081b0525ff1335d742080d6128b`
- fix: `com/google/gson/internal/bind/TypeAdapters$21.class` `9e58da882f522d483bd2e7ba651d0332ce1eecea601bf60b4989a3b9ef4424b6`
- fix: `com/google/gson/internal/bind/TypeAdapters$22.class` `5470c1fe83985e4ee6712aba602b9adcb2756c414ac504bb6f8bd2e59c641aa0`
- fix: `com/google/gson/internal/bind/TypeAdapters$23.class` `61dc57a94bb47c1547f650b99f8d649517dd70682010117be612226539d75dfe`
- fix: `com/google/gson/internal/bind/TypeAdapters$24.class` `b0e6e4d1f56985a6a3f5e4714eb4d96bbcf53585534d76c9e86e28e9dafc1980`
- fix: `com/google/gson/internal/bind/TypeAdapters$25.class` `fd37589f64926b8a0ad9d2ebdc01bec016e1b4c9187fd396fea6ffc0b2c1f593`
- fix: `com/google/gson/internal/bind/TypeAdapters$26.class` `cf564d2d219dc5f14d90031bde152c2693c58faa6a2ed1ab2413192fc55402ba`
- fix: `com/google/gson/internal/bind/TypeAdapters$27.class` `d7baef3b289511dd8ea97dc748c7445fda07a5bccb6234f5ebd28e2cf74440ba`
- fix: `com/google/gson/internal/bind/TypeAdapters$28.class` `e664a7de2d4146c8106f0c9a2f4b0f74c0984b4fe55e31b5881ba7362da65e0f`
- fix: `com/google/gson/internal/bind/TypeAdapters$29.class` `48b04580508018244cb04e71a5d7ab52fbf414ea5f1cce25a3c0a18835f4d867`
- fix: `com/google/gson/internal/bind/TypeAdapters$2.class` `01d7e5a008ca8406a7360ba362f6e29fe668adcacf3a53c92918ea4c9984a110`
- fix: `com/google/gson/internal/bind/TypeAdapters$30.class` `bd06aeb151a3186a110b82d9f1fde30f3c2ec6d6031f829d89eadde15af98a04`
- fix: `com/google/gson/internal/bind/TypeAdapters$31.class` `9dd9fad5584763499567485b625e61be34807490b82a917fa141e91e353331f0`
- fix: `com/google/gson/internal/bind/TypeAdapters$32.class` `912b9bb59686204c23f6dc56d38bf7e7e1dea94478cb5a8a08de726c89883ea3`
- fix: `com/google/gson/internal/bind/TypeAdapters$33$1.class` `06f54a61e6907cb3fb1bf91354ebab8eb72748386214092769b894f573588bf8`
- fix: `com/google/gson/internal/bind/TypeAdapters$33.class` `ea8c14b95e03ca787915484e12b99d6d3118f6f93e10741e79afb8cdf0bdfafb`
- fix: `com/google/gson/internal/bind/TypeAdapters$34.class` `2ab5428411e976d5345d49c5bd576e8df37f022652fae0cb0975291674ee452e`
- fix: `com/google/gson/internal/bind/TypeAdapters$3.class` `18f1ded9b1636bc66ff0b404dee6e5c6b0c78ea2e049542bc9ea9627ae53f9c1`
- fix: `com/google/gson/internal/bind/TypeAdapters$4.class` `21fa71a81c4d4492339e21134fae22b8940f90f518f5ea0625bc2bb56af76d10`
- fix: `com/google/gson/internal/bind/TypeAdapters$5.class` `e0c0b3f57ee156f7ec48e08f6c86082f8c632a9666800177032f9ac6e824acea`
- fix: `com/google/gson/internal/bind/TypeAdapters$6.class` `a609a82285074787a01479b79e7b2910aef18ad599f59df48d9dac839bfd31bf`
- fix: `com/google/gson/internal/bind/TypeAdapters$7.class` `c3ad3dffbce15dc2c33d5fe2c4b6a0dde34079ba1025b4c6f4b16f50397079ff`
- fix: `com/google/gson/internal/bind/TypeAdapters$8.class` `e0e004e54317b6865cda1466453a322493bd7552e38d1c170a1ae479f7bd9df7`
- fix: `com/google/gson/internal/bind/TypeAdapters$9.class` `9dd24dc234d83da49e311e6a78cbcea36f0c35ea2ed659ab88e07ae73c28a0d0`
- fix: `com/google/gson/internal/bind/TypeAdapters$DoubleAdapter.class` `109cdc18b5f2cde2cac0aea5ac3f34f447e71dbbb5bc8d93742c4a058686964b`
- fix: `com/google/gson/internal/bind/TypeAdapters$FloatAdapter.class` `223a3f78eeb67076e867fbf2274ff6181fac98b8e4434fb9f5f6409375950772`
- fix: `com/google/gson/internal/bind/TypeAdapters$IntegerFieldsTypeAdapter.class` `58163cf5e855305e7d6d3fbdfe7512548c6e90aa1bc6a0737af78751a93d0885`
- fix: `com/google/gson/internal/bind/TypeAdapters.class` `9f1ae499020777ea671f1811970cbd109dcdd988d3f8ec5bceebdaa60e07f22e`

### R40 · ThreeTen-Extra #433 — OffsetDate.until across offsets

**Pins.** Parent `9b5e316f5fad89ef80a05d8cdec522315c2e26ba`, fix `cad4ef4bdf209d8d76016e9d8322c18eab7c8cb0`. Changed: `src/changes/changes.xml` (+5 −0); `src/main/java/org/threeten/extra/OffsetDate.java` (+60 −2); `src/test/java/org/threeten/extra/TestOffsetDate.java` (+39 −0).

**Build facts.** `org.threeten:threeten-extra:1.11.1-SNAPSHOT` (no parent POM), `maven.compiler.release` 8 (major 52). Runtime classpath: jspecify 1.0.1, joda-convert 2.2.4.

**Commands** (in `$W/R40-threeten-extra-ROLE`, JDK `$J17`; ARGS of `mvn_A.sh`):
- online, first resolution: `-DskipTests package` (fix 24 s, parent 21 s)
- **offline (checked)**: `-o -DskipTests package` (fix 5 s, parent 5 s)
- landed tests, offline: `-o -Drat.skip -Dtest=TestOffsetDate test` (fix 6 s)

**Landed tests.** Fix: `TestOffsetDate` 408 run, 0 failures. Parent's own: 402 run, 0 failures. Fix's copy on the parent: 408 run, **5 failures, 1 error**: five invocations of `test_until_differentOffset(long, OffsetDate, OffsetDate, TemporalUnit)` `[1]`–`[5]` (`expected: <0> but was: <-1>` ×3 at line 602, `expected: <-1> but was: <-2>` and `expected: <0> but was: <-1>` at 604), and `test_until_extremes:609 DateTimeException: Invalid value for Year (valid values -999999999 - 999999999): 1000000000`. Logs: `$O/logs/R40-fix-landed.log`, `$O/logs/R40-parent-own.log`, `$O/logs/R40-parent-landed.log`.

**Release side.** Latest release 1.11.0 (2026-10-15, before the merge on 2026-10-24): its `OffsetDate.java` **is the parent's byte for byte** (blob `39d6a79b77b83ea3eb465b2feda10ae6983cb8fd`). No release with the fix. Signatures good (above).

**Artifacts** (`$O/artifacts/R40-parent/`, `$O/artifacts/R40-fix/`), sha256:
- parent: `threeten-extra-1.11.1-SNAPSHOT.jar` `44738fd0b6455cc89d7bf417decb1f109022a71091ba0370906053f776fb550e`
- parent: `org/threeten/extra/OffsetDate.class` `3d67f1131dedb1b4a11b261d044841c8ad00ba2a92899fa11579b692583c1dba`
- fix: `threeten-extra-1.11.1-SNAPSHOT.jar` `2989d4ed5441b6fbe50c01af258caaaa700c31c72054a59b8957097ccaa7e1e8`
- fix: `org/threeten/extra/OffsetDate$1.class` `093a214ed838d8859bd97206c85e997b15d572125b6999cdaf44452aa8b2f2cd`
- fix: `org/threeten/extra/OffsetDate.class` `5e22c299bf1e948b973e63ce65fdfd21b3e3f623c5f6a9e41a8eec277268770c`


## Cases R03–R48 (fork B)

Thirteen cases, all Maven, all built and checked inline (no run took over a minute offline; the longest offline run is R03's 38–39 s,
the longest online first resolution R48's 67 s). **No verification job was needed for these cases.**

Helpers (fork B, in `$O/scripts/`):
- `mvn_B.sh DIR TAG JDK REPORTDIR [online] ARGS...`: `mvn_case.sh` with the surefire report directory of a module: `systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- $MVN [-o] ARGS` in DIR with `JAVA_HOME=JDK`, `MAVEN_OPTS=-Xmx1g`; log `$O/logs/TAG.log`, JUnit summary `$O/logs/TAG.junit.txt`. Offline unless `online`.
- `case_B.sh CASE JDK MODDIR TESTS`: offline, with `-pl MODDIR -am` (none when MODDIR is `.`), `-Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=TESTS package`: (1) the fix worktree → `CASE-fix-landed`; (2) the parent worktree with its own copy of TESTS → `CASE-parent-landed`; (3) `$O/build/CASE-parent-landed` → `CASE-parent-landedfix`, failures with messages in `$O/logs/CASE-parent-landedfix.failures.txt`.
- `overlay_B.sh CASE`: `$O/build/CASE-parent-landed` = `git archive` of the parent pin plus every test file the PR changed, copied from the fix (list in `$O/logs/CASE-parent-landedfix.overlay.txt`).
- `keep_B.sh CASE ROLE JDK MODDIR [online]`: `keep_mvn.sh` for a module directory (jar, `SHA256SUMS` of the jar and of every class of each changed production source, `runtime-classpath.txt`, `test-classpath.txt`, `:`-joined, paths into `$O/m2`).
- `junit_fail_B.py` (failure names, types, messages), `relcmp_B.sh` (git blob ids of the changed production sources in a release `-sources.jar` vs both pins), `relcmp2_B.sh` + `lines_B.py` (how many of the removed and added lines a release holds).

Common facts:
- Every built jar is in `$O/artifacts/CASE-ROLE/`; its digest is in that folder's `SHA256SUMS` (first line), followed by the digest of every class of each production source file the PR changed. **Jar digests are of the kept copy only: a rebuild gives a different jar digest (entry timestamps) but the same class digests** (checked on R07: `org/locationtech/jts/geom/CoordinateList.class` rebuilt from a clean tree = `3b6e19a68ee11603a68dcc49c9cfbdbba8e69103b09ca8f95c64e87c1cfae2e1`, as kept).
- Build trees were removed (`git clean -fdx` in the 26 worktrees, `$O/build/CASE-*` deleted) after the digests were recorded; offline rebuilds take seconds (checked after cleaning on R07 and R30).
- Release artifacts are under `$O/releases/A-V/` (jar, pom, `-sources.jar`, with Central's `.sha1`/`.sha256`/`.sha512` beside them, all matching: 48 sha1, 42 sha256, 42 sha512 checks, `$O/logs/B-release-hashes.txt`; jar digests in `$O/logs/B-release-sha256.txt`). Every `.asc` checked in the keyring `$O/gnupg-B` (daemons stopped) with keys from keyserver.ubuntu.com saved in `$O/keys-B/`: 48 of 48 GOODSIG (`$O/logs/B-release-signatures.txt`). Nothing further vouches for the keys. Signers: vavr `0942F59B726DA4BD2837DD44F45F03308EE961FF` (Grzegorz Piwowarek); jts-core `6EB0DED2F354B5D1DD24006168127E5CB45F41F3` (Jody Garnett); jgrapht-core `78F389DC7C11455EAD8897EE24AE93BAFAF1CAD9` (John Sichi); jackson-core, jackson-databind, jackson-dataformat-xml `28118C070CB22A0175A2E8D43D12CA2AC19F3181` (Tatu Saloranta); javaparser-core `6DE9B8077FBB2F8A019F4904BD17A565509DEE20` (uid jean-pierre.lerbscher); assertj-core `BE685132AFD2740D9095F9040CC0B712FEE75827` (AssertJ).
- Release comparisons: `$O/logs/B-relcmp-1.txt`, `$O/logs/B-relcmp-2.txt` (blob ids in full). "= parent"/"= fix" below means the release's source file has the same git blob id as that pin's.
- The parent-side "own copy" run finds no test when the PR added the test class (`junit tests=0`); that is expected.

| Case | Built | Release side | Landed tests (fix / parent's own / fix's on parent) | Upstream run |
|---|---|---|---|---|
| R03 vavr #3276 | Maven, JDK 21, `-pl vavr -am`, offline | 1.0.1 lacks; **1.1.0** has the fix line (not byte-equal) | 1900/1900, 1897/1897, **3 fail** | inline |
| R07 jts #1168 | Maven, JDK 17, `-pl modules/core -am`, offline | 1.20.0 lacks; no release with it | 4/4, 3/3, **1 fail** | inline |
| R19 jts #1092 | as R07 | 1.20.0 `WKBWriter`/`WKTWriter` = parent; no release with it | 13/13, 12/12, **1 error** | inline |
| R08 jgrapht #1379 | Maven, JDK 21, `-pl jgrapht-core -am`, offline | 1.5.3 lacks; no release with it | 10/10, 2/2, **8 errors** | inline |
| R10 jgrapht #1376 | as R08 | 1.5.3 = parent; no release with it | 10/10, 8/8, **2 errors** | inline |
| R18 jackson-core #1716 | Maven, JDK 17, offline; **vanished snapshot parent rebuilt** | 2.21.6 = parent; **2.21.7 = fix** | 4/4, (none), **4 fail** | inline |
| R27 jackson-core #1816 | Maven, JDK 17, offline; snapshot parent predates pins | 2.21.8 lacks; **2.21.9** has all added lines | 7/7, (none), **6 fail** | inline |
| R28 jackson-databind #6407 | Maven, JDK 17, offline; **snapshot deps postdate pins** | 3.3.0 = parent (4 files); no release with it | 8/8, (none), **7 fail** | inline |
| R29 jackson-databind #6473 | as R28 | 3.3.0 and 3.1.9 lack; no release with it | 10/10, (none), **1 fail + 2 errors** | inline |
| R30 jackson-dataformat-xml #895 | Maven, JDK 17, offline; **snapshot deps 2½ months after pins** | 3.2.2, 3.2.3 lack; **3.3.0** has all 42 added lines | 15/15, 11/11, **4 fail** | inline |
| R23 javaparser #5176 | Maven, JDK 17, `-pl javaparser-core-testing -am`, offline | 3.28.2 = parent (5 files); no release with it | 16/16, 8/8, **7 fail** | inline |
| R24 javaparser #5207 | as R23 | 3.28.2 lacks; no release with it | 36/36, 14/14, **11 fail + 4 errors** | inline |
| R48 assertj #3710 | Maven, JDK 21, `-pl assertj-tests/assertj-integration-tests/assertj-core-tests -am`, offline | 3.27.0 = parent; **3.27.1** has all 8 added lines | 1/1, (none), **1 fail** | inline |

### Jackson snapshot inputs (R18, R27–R30) — unstable inputs

All five Jackson pins are `-SNAPSHOT` versions whose parent POM and Jackson dependencies are `-SNAPSHOT`s served only by the Central Portal
snapshot repository the POMs declare (`https://central.sonatype.com/repository/maven-snapshots`), which keeps **only the latest build** of each
snapshot version. What was resolved on 2026-11-26 (each file's `.sha1` from that repository matched, `$O/artifacts/snapshots-B/remote-sha1-check.txt`;
timestamped copies and sha256 in `$O/artifacts/snapshots-B/SHA256SUMS`):

| Snapshot | Resolved build | sha256 | Used by | Relative to the pins |
|---|---|---|---|---|
| `com.fasterxml.jackson:jackson-base:2.21.7-SNAPSHOT` (+ `jackson-bom`) | **absent** from the repository; rebuilt (below) | `600895e418942eebb133b28d4801b556bacf9b64cf8d6b88c53d4f1aee7bf177` (base), `404c848b5fa0f2f2739338b9774d88e74d08abe4500cad15275ff7fdc46cec06` (bom) | R18 | source at 2026-08-15, before both pins |
| `com.fasterxml.jackson:jackson-base:2.21.9-SNAPSHOT` | `2.21.9-20261017.195440-2` | `6dd8fde86c59a0bb2f6bfa61f4894d345a37a1f2a67b303fbffbd547565cd25a` | R27 | before both pins (2026-11-03) |
| `com.fasterxml.jackson:jackson-bom:2.21.9-SNAPSHOT` | `2.21.9-20261017.195440-2` | `1b1be4454bf13e09a07be0224674c4db156951d75ad09d2d4b11e74e3a662d78` | R27 | before |
| `tools.jackson:jackson-base:3.4.0-SNAPSHOT` | `3.4.0-20261108.022425-1` | `af28e1dff5feecbd26084a4d2f0b491a7d622339c479b3b8c93ef73f86af9888` | R28, R29 | before R28's parent pin (2026-11-08T05:52Z) and R29 |
| `tools.jackson:jackson-bom:3.4.0-SNAPSHOT` | `3.4.0-20261108.022425-1` | `fdfe95299daa5d7bb38e40646cb322cecff5f60a636a67c4ef4c99a959207bc2` | R28, R29 | before |
| `tools.jackson.core:jackson-core:3.4.0-SNAPSHOT` (jar) | `3.4.0-20261126.043215-13` | `d2b4ddbf754a4340daf0fd306773464b2fe6dad38c5c21910a0a1634678c7ea2` | R28, R29 (runtime) | **after** all R28/R29 pins |
| `com.fasterxml.jackson.core:jackson-annotations:2.24-SNAPSHOT` (jar) | `2.24-20261124.040648-4` | `178d396bc61050c6181519d390537464a223383d70e04bf3abee30ad1719d7a5` | R28, R29 (runtime) | **after** |
| `com.fasterxml.jackson:jackson-parent:2.24-SNAPSHOT` | `2.24-20261107.233449-2` | `d27368f42c607ea352b41bf03ee9e45982fceae7eaec974cb3c0257a6d892524` | (annotations' parent) | |
| `tools.jackson:jackson-base:3.3.0-SNAPSHOT` | `3.3.0-20261108.015624-14` | `d51bba0a25a935d7702d078ccf5e59974759225b5710a288c2c147341bcde101` | R30 | **after** R30's pins (2026-08-22) |
| `tools.jackson:jackson-bom:3.3.0-SNAPSHOT` | `3.3.0-20261108.015624-14` | `3b116ccb2abff445d6a0a25d9a83caf4aee3a47e4a19b527b808902214377f5d` | R30 | **after** |
| `tools.jackson.core:jackson-core:3.3.0-SNAPSHOT` (jar) | `3.3.0-20261106.043746-116` | `f08441718942668bb1eb7b9834e05a08bd68f6cc1f75760ea02328a2a1175b0e` | R30 (runtime) | **after** |
| `tools.jackson.core:jackson-databind:3.3.0-SNAPSHOT` (jar) | `3.3.0-20261107.181845-176` | `be7d7b485da10541b10436d1d1ad01e5e6a1c82163b9734fe7ec53d280c4f365` | R30 (runtime) | **after** |
| `com.fasterxml.jackson.core:jackson-annotations:2.23-SNAPSHOT` (jar) | `2.23-20261106.041643-18` | `838ae67b1430bed7cf66b4560d7e86bb8b08745d33e0fb78ebc582e712dacce3` | R30 (runtime) | **after** |
| `com.fasterxml.jackson:jackson-parent:2.23-SNAPSHOT` | `2.23-20261103.010715-5` | `481f4c2098ab2aac3864fc189b81d4e6a34b20ba55127a0712203fd6398fb30a` | (annotations' parent) | |
| `tools.jackson.module:jackson-module-jakarta-xmlbind-annotations:3.3.0-SNAPSHOT` (jar) | `3.3.0-20261103.185810-24` | `07a3e4ac25f08c707ec63eb2cbb3589c599baa8b306dc52fc2dd13c9afe750e8` | R30 (test) | **after** |
| `tools.jackson.module:jackson-modules-base:3.3.0-SNAPSHOT` | `3.3.0-20261103.185810-24` | `05795f1124f5e309bbfee839d89ba9e51252587541741198a55d30b6bfb8a8cc` | (its parent) | |

(The timestamped POMs of the jars are in the same folder with their own sha256.) So R28, R29 and R30 were built and tested against
**later builds** of their Jackson dependencies than the ones the pins were built with: the pins' own snapshot builds are no longer served.
The PRs change only the case's own module, and the landed tests behave as the PRs say on these inputs; a claim that could depend on
jackson-core, jackson-annotations or (R30) jackson-databind behaviour should say which build it ran on. The m2 copies under the plain
`-SNAPSHOT` names equal these timestamped files today, but a later online (`-U`) Maven run could replace them: **use the offline commands**, or the
`*-classpath.pinned.txt` files in `$O/artifacts/R28-*/`, `R29-*/`, `R30-*/`, which name the timestamped copies in `$O/artifacts/snapshots-B/` instead.
Not done: rebuilding the R28–R30 snapshot inputs from their upstream branches at the pins' times (as the M01–M10 setup did for M02). R28 and R29
would need different `jackson-core:3.4.0-SNAPSHOT` builds under one coordinate, so it would need a local repository per case; left as is.

**R18's substitution.** `jackson-base:2.21.7-SNAPSHOT` (and its parent `jackson-bom:2.21.7-SNAPSHOT`) are gone (`Non-resolvable parent POM … (absent)`,
`$O/logs/R18-jackson-core-fix-resolve-online.log`); 2.21.7 itself was released 2026-09-21, after both pins. Both POMs were built from their own
upstream, `FasterXML/jackson-bom` branch `2.21`, at the last first-parent commit before R18's parent pin (2026-09-11T19:22:26-07:00):
`7796a7ddb240ce41c1b6c6a3a435b29948a6a727` (2026-08-15, "Merge branch '2.20' into 2.21"); the branch's next commit, `6702bf32e5dfab76ebd57906eee2ff4f68b3eb41`,
is 2026-09-20, after the fix pin (2026-09-16), so the same input serves both sides. Mirror `$M/jackson-bom.git` (ref `refs/pins/R18-snap-7796a7ddb240ce41c1b6c6a3a435b29948a6a727`,
branch history fetched `--shallow-since=2026-07-01`), worktree `$W/R18-snap-jackson-bom`, installed into `$O/m2` with `mvn_B.sh $W/R18-snap-jackson-bom R18-snap-jackson-bom-install $J17 x online install` (3 s);
copies in `$O/artifacts/snapshots-B/rebuilt-R18/`. Its diff to the 2.21.7 release commit `62d4d51724430074c0b7223fa69bacab444bee04` is the version strings and
`project.build.outputTimestamp` only (3 files, 6 lines). jackson-base's parent `com.fasterxml.jackson:jackson-parent:2.21` is a release.

### R03 · vavr #3276 — `computeIfPresent` with a null result

**Pins.** Parent `f74004d3cef44fcccc7996783d34f734ba25ffd3`, fix `2b77936d4788fee24b99e8a372fd93923d8b6c12`. Changed: `vavr/src/main/java/io/vavr/collection/Maps.java` (+1 −1:
`Option.of(newValue)` → `Option.some(newValue)`), `vavr/src/test/java/io/vavr/collection/AbstractMapTest.java` (+7 −1).

**Build facts.** `io.vavr:vavr:2.0.0-SNAPSHOT`, parent `io.vavr:vavr-parent:2.0.0-SNAPSHOT` (the reactor root; no external snapshot), `java.version` 21, classes
**major 65**, `module-info.class` present. JUnit Jupiter 6.0.3. Runtime classpath: `io.vavr:vavr-match:1.0.0`, `io.vavr:vavr-match-processor:1.0.0`, `org.jspecify:jspecify:1.0.0`.
Built on JDK 21 (`$J21`; CI builds 21–26).

**Commands** (in `$W/R03-vavr-ROLE`, `$J21`, report dir `vavr/target/surefire-reports`):
- online, first resolution (58 s): `-pl vavr -am -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=HashMapTest,LinkedHashMapTest,TreeMapTest package`
- **offline (checked, 38–39 s)**: the same with `-o` (`case_B.sh R03 $J21 vavr HashMapTest,LinkedHashMapTest,TreeMapTest`).

**Landed tests.** `AbstractMapTest` is abstract; its concrete subclasses are `HashMapTest`, `LinkedHashMapTest`, `TreeMapTest`. Fix: 1900 run, 0 failures.
Parent's own: 1897, 0 failures. Fix's `AbstractMapTest` on the parent: 1900 run, **3 failures**, one per map type, `AbstractMapTest$ComputeIfPresentTests#shouldComputeIfPresentWithNullResult`:
`expected: (Some(null), HashMap((1, null))) but was: (None, HashMap((1, null)))` (likewise `LinkedHashMap`, `TreeMap`).

**Release side.** `io.vavr:vavr` 1.0.1 (2026-03-01) holds the removed line, not the added one; **1.1.0** (2026-10-24) holds the added line `Option.some(newValue)` and not the
removed one (its `Maps.java` is not byte-equal to either pin). Both signed (GOODSIG). Jars: `$O/releases/vavr-1.0.1/`, `$O/releases/vavr-1.1.0/`.

**Artifacts.** `$O/artifacts/R03-ROLE/vavr-2.0.0-SNAPSHOT.jar`; `Maps.class` fix `c2c0834b4bc23f0c5cb844aacd916fc03d52475b191c5600897b1b2783bab914`, parent `f944d9eec8ee191f438ec0bee204e210de648b556e75fa2dfa0a869dd57362ec`
(`Maps$OfEntries.class` the same on both, `f76f15f17edae614628c9baf5aaab6c99c73ebd37a5af28f433ef483c0444334`).

### R07 · jts #1168 — `CoordinateList.clone()` doubles the list

**Pins.** Parent `45744222b0b8a861c44dbc2c03dcf4f1e85c27fd`, fix `c406f5abe914d471ceb9cf0b872e8a634a1a1be6`. Changed: `modules/core/src/main/java/org/locationtech/jts/geom/CoordinateList.java` (+1 −1:
`clone.add(i, …)` → `clone.set(i, …)`), `modules/core/src/test/java/org/locationtech/jts/geom/CoordinateListTest.java` (+8 −1, new `testClone`).

**Build facts.** `org.locationtech.jts:jts-core:1.20.1-SNAPSHOT` (root `org.locationtech.jts:jts:1.20.1-SNAPSHOT`, modules `build-tools`, `modules/{core,io,example,tests,app,lab}`),
source/target 1.8, classes **major 52**, no `module-info`. **No runtime dependencies.** Tests JUnit 4.13.1 (surefire 2.15). Built on `$J17`. The checkstyle plugin of
jts-core depends on the reactor's `build-tools` module, so **every command needs `-am`** (without it, offline fails: `build-tools-1.20.1-SNAPSHOT.jar NOT allowed from apache.snapshots`).

**Commands** (in `$W/R07-jts-ROLE`, `$J17`, report dir `modules/core/target/surefire-reports`):
- online (10 s): `-pl modules/core -am -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=CoordinateListTest package` (a `-DskipTests` run first does not resolve the surefire JUnit 4 provider)
- **offline (checked, 10–16 s)**: the same with `-o` (`case_B.sh R07 $J17 modules/core CoordinateListTest`).

**Landed tests.** Fix: `CoordinateListTest` 4/4. Parent's own: 3/3. Fix's test on the parent: **1 failure**, `CoordinateListTest#testClone`:
`list has wrong length expected:<6> but was:<3>` (the assertion is `assertEquals(msg, coordArray.length, ords.length / 2)`, so the parent's clone has **6** coordinates for the 3 inputs).

**Release side.** Latest release 1.20.0 (2024-08-30) holds the removed `clone.add(i, …)` line: parent side. No later release (none with the fix). Signed (GOODSIG).

**Artifacts.** `$O/artifacts/R07-ROLE/jts-core-1.20.1-SNAPSHOT.jar`; `CoordinateList.class` fix `3b6e19a68ee11603a68dcc49c9cfbdbba8e69103b09ca8f95c64e87c1cfae2e1`, parent `1e09c97b72d8d47007b56fba13ab54833546336330ec7600444d0603b4a8a04c`.

### R19 · jts #1092 — WKB ordinate flags for measured geometry

**Pins.** Parent `a7597288e551757426015db75c22603c0baeff20`, fix `034207b1de6605ad3eb8dbf8373b1ad8fab1b1b3`. Changed: `modules/core/src/main/java/org/locationtech/jts/io/CheckOrdinatesFilter.java`
(added, +79: the former `WKTWriter$CheckOrdinatesFilter` made a top-level class), `…/io/WKBWriter.java` (+41 −30), `…/io/WKTWriter.java` (−55), `modules/core/src/test/java/org/locationtech/jts/io/WKBWriterTest.java` (+21 −12).

**Build facts.** As R07 (same module, version and JDK).

**Commands.** As R07 with `-Dtest=WKBWriterTest`; offline checked (11–19 s; `case_B.sh R19 $J17 modules/core WKBWriterTest`).

**Landed tests.** Fix: `WKBWriterTest` 13/13. Parent's own: 12/12. Fix's on the parent: **1 error**, `WKBWriterTest#testWkbLineStringM`: `java.lang.IllegalArgumentException: Invalid ordinate index: 3`.

**Release side.** 1.20.0's `WKBWriter.java` and `WKTWriter.java` = parent byte for byte; `CheckOrdinatesFilter.java` absent. No release with the fix.

**Artifacts.** `$O/artifacts/R19-ROLE/`; fix `CheckOrdinatesFilter.class` `0d669783153c4f6c3fdf660faa9929e0b26c0c5f7218682ec2b3d8789f0ee08d`, `WKBWriter.class` `e9ec283b649026eb88339eceaf0bb946d1c8f6d521685a75cdbbd01266146178`,
`WKTWriter.class` `53707e0705ef1a558d2eb89c7b3ae32300ce49cf70e390f8b92966a2589c6b78`; parent `WKBWriter.class` `30e711fa83ddbdfbc7eb9ffe51d378eee02ad3bcf487d691c73cabe823bdfef6`, `WKTWriter.class`
`214e5b86bb172f9cad9c26106c5e29704aeb725f814475f0656458179a08636d`, `WKTWriter$1.class` `accbf24829689f1b62c0bdfc1f9b1620495a880521c9a70d24fb79664a4f84d4`, `WKTWriter$CheckOrdinatesFilter.class` `8669e211823278a54d057e12e4f650a1f020a92cdbe413e462daf8f1d792240d`.

### R08 · jgrapht #1379 — connectivity listener before the sets are computed

**Pins.** Parent `fabfabe6f279c0dd61b417a543d33d94fd039249`, fix `955e5cfb9b22d7ac2ef956849523d22041baf730`. Changed: `jgrapht-core/src/main/java/org/jgrapht/alg/connectivity/ConnectivityInspector.java` (+9:
two `if (connectedSets == null)` guards, one clearing `vertexToConnectedSet`), `jgrapht-core/src/test/java/org/jgrapht/alg/connectivity/ConnectivityInspectorTest.java` (+79).

**Build facts.** `org.jgrapht:jgrapht-core:1.6.0-SNAPSHOT` (root `org.jgrapht:jgrapht:1.6.0-SNAPSHOT`), `java.version` 21, classes **major 65**, `module-info` present.
Runtime: `org.jheaps:jheaps:0.14`, `org.apfloat:apfloat:1.16.0`. Tests JUnit Jupiter 6.1.2. Built on `$J21`.

**Commands** (in `$W/R08-jgrapht-ROLE`, `$J21`, report dir `jgrapht-core/target/surefire-reports`):
- online (19 s): `-pl jgrapht-core -am -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=ConnectivityInspectorTest package`
- **offline (checked, 5–18 s)**: the same with `-o` (`case_B.sh R08 $J21 jgrapht-core ConnectivityInspectorTest`).

**Landed tests.** Fix: 10/10. Parent's own: 2/2. Fix's on the parent: **8 errors**, both parameters (`(boolean)[1]`, `[2]`) of `testListenerVertexAddBeforeQuery`,
`testListenerVertexAddAfterRemoval` (`NullPointerException: Cannot invoke "java.util.List.add(Object)" because "this.connectedSets" is null`), `testListenerEdgeAddBeforeQuery`,
`testListenerEdgeAddAfterRemovalAndPartialQuery` (`… "java.util.List.remove(Object)" because "this.connectedSets" is null`). The PR reports eight failing regressions.

**Release side.** Latest release 1.5.3 (2026-04-11) lacks the guards (none of the fix-specific added lines). No release with the fix. Signed (GOODSIG).

**Artifacts.** `$O/artifacts/R08-ROLE/jgrapht-core-1.6.0-SNAPSHOT.jar`; `ConnectivityInspector.class` fix `7037805aa54cbd8039003187d753bc7142607008acf1cbf4b5c784183506f305`, parent `ecffbb8bddb584b8532a6d7564ad1bcc93528bdaa8c7851b21ae498e1b9a6c65`;
`ConnectivityInspector$MyTraversalListener.class` fix `72ecfbe1a0b628754eb2e2fc469b16dfaba76fe17b832cc14888a9e6fff0b7e9`, parent `4c90d7219024b8f8e9940661316494407c4e15463b6bca7b4885ccb64d36a531`.

### R10 · jgrapht #1376 — farthest insertion with negative weights

**Pins.** Parent `e5bc1c06804bd90c5cf549954587728fc8dae101`, fix `9fc7edbcc3d1e753bc1863bda0cf1c2f652e083a`. Changed: `jgrapht-core/src/main/java/org/jgrapht/alg/tour/FarthestInsertionHeuristicTSP.java` (+2 −2),
`jgrapht-core/src/test/java/org/jgrapht/alg/tour/FarthestInsertionHeuristicTSPTest.java` (+40).

**Build facts.** As R08. **Commands.** As R08 with `-Dtest=FarthestInsertionHeuristicTSPTest`; offline checked (13–23 s).

**Landed tests.** Fix: 10/10. Parent's own: 8/8. Fix's on the parent: **2 errors**: `testNegativeEdgeWeights` (`:194 ArrayIndexOutOfBoundsException: Index -1 out of bounds for length 5`, the K4 case)
and `testNegativeEdgeWeightsAllNegative` (`:214 NullPointerException: Cannot invoke "Object.toString()" because "e" is null`, the triangle).

**Release side.** 1.5.3's `FarthestInsertionHeuristicTSP.java` = parent byte for byte. No release with the fix.

**Artifacts.** `$O/artifacts/R10-ROLE/`; `FarthestInsertionHeuristicTSP.class` fix `ed8684c759c319ed5111d570df20282d272b36efc78c3ec14e3af7e6045bcd6d`, parent `2ba2ede1af23442dcc77a455dee995c6a9bbe6d4d55a855cb6fc92b315692652`.

### R18 · jackson-core #1716 — UTF-32 surrogate pair split at a buffer refill

**Pins.** Parent `2a0ea7beeb9eb0a16f04c14e07b5d0804c64433d`, fix `15591d013c44ef3b2a84bb639df396149a5917f5` (base branch `2.21`). Changed: `src/main/java/com/fasterxml/jackson/core/io/UTF32Reader.java` (+1 −1),
`src/test/java/com/fasterxml/jackson/core/io/UTF32ReaderSurrogate1713Test.java` (added, +122), `release-notes/CREDITS-2.x`, `release-notes/VERSION-2.x`.

**Build facts.** `com.fasterxml.jackson.core:jackson-core:2.21.7-SNAPSHOT`, parent `com.fasterxml.jackson:jackson-base:2.21.7-SNAPSHOT` **(rebuilt, see above)**. Classes **major 52**
(Java 8 target), multi-release `module-info`. The jar shades `ch.randelshofer:fastdoubleparser:2.0.1` (listed as its one runtime-classpath entry). Tests JUnit Jupiter 5.14.1. Built on `$J17`.

**Commands** (in `$W/R18-jackson-core-ROLE`, `$J17`, report dir `target/surefire-reports`; needs the rebuilt POMs in `$O/m2`, present):
- online (10 s): `-Dtest=UTF32ReaderSurrogate1713Test package`
- **offline (checked, 7 s)**: `-o -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=UTF32ReaderSurrogate1713Test package` (`case_B.sh R18 $J17 . UTF32ReaderSurrogate1713Test`).

**Landed tests.** Fix: 4/4. Parent: no such class. Fix's on the parent: **4 failures**, every test: `singleCharReadBigEndian`, `singleCharReadLittleEndian`, `chunkedReadSplitsPair`
(`bigEndian=true, chunkSize=1 ==> expected: <a😀𐀀􏿿b…> but was: <a…`), `viaParserAtBufferBoundary` (`prefixLen=3995, bigEndian=true ==> expected: <mnopq😀𐀀…> but was: <mnopq😀…`); the
"but was" strings hold unpaired or replaced surrogates (`$O/logs/R18-parent-landedfix.failures.txt`).

**Release side.** 2.21.6 (2026-08-14) `UTF32Reader.java` = parent; **2.21.7** (2026-09-21) = fix, byte for byte. Both signed (GOODSIG).

**Artifacts.** `$O/artifacts/R18-ROLE/jackson-core-2.21.7-SNAPSHOT.jar`; `UTF32Reader.class` fix `bfef62d28d5432823a0268f500c281158d3667b53f45d707b95b26c7dba40675`, parent `cfe9b05ad0df709a02e9893968e5d9e6a9c34c9aa8059582081245d44334e042`.

### R27 · jackson-core #1816 — stale deferred numbers across tokens

**Pins.** Parent `682b4062b60d8317956ca80a28c3c92cf46d93ce`, fix `b251524f3a857fd5960548ea12d4ba2dc92f8c43` (base `2.21`). Changed: `src/main/java/com/fasterxml/jackson/core/base/ParserBase.java` (+31 −15),
`…/json/async/NonBlockingJsonParserBase.java` (+10), `…/json/async/NonBlockingUtf8JsonParserBase.java` (+4 −4), `src/test/java/com/fasterxml/jackson/core/read/NumberStaleValue1815Test.java` (added, +191), `release-notes/VERSION-2.x`.

**Build facts.** `jackson-core:2.21.9-SNAPSHOT`, parent `jackson-base:2.21.9-SNAPSHOT` resolved as `2.21.9-20261017.195440-2` (before both pins). Otherwise as R18.

**Commands.** As R18 with `-Dtest=NumberStaleValue1815Test`: online 11 s, **offline checked 7–8 s**.

**Landed tests.** Fix: 7/7. Parent: no such class. Fix's on the parent: **6 failures**: `staleBigDecimal` and `staleBigDecimalAsync` (`expected: <7> but was: <2>`), `deferredBigInteger` and
`deferredBigIntegerAsync` (`expected: <1.5> but was: <0.0>`), `staleValuesAtEOFAsync` (`expected: <7.0> but was: <2.5>`), `staleNumberStringBeforeNaNAsync` (`expected: <true> but was: <false>`); one test passes.

**Release side.** 2.21.8 (2026-10-17): the two async files = parent; `ParserBase.java` holds 12 of the 15 removed lines and 13 of the 30 added (generic ones): parent side. **2.21.9** (2026-11-24):
the two async files = fix byte for byte; `ParserBase.java` holds all 30 added lines (not byte-equal: 11 of the 15 removed lines still occur elsewhere in the file). 2.23.0 (2026-11-08,
another line) has the async lines but only 15 of the 30 `ParserBase` additions: not compared further. All signed.

**Artifacts.** `$O/artifacts/R27-ROLE/jackson-core-2.21.9-SNAPSHOT.jar`; fix `ParserBase.class` `4287e01cb828dd26c063e34b01576afa6c076afa3cc98419b3b0a5691da9de2e`, `NonBlockingJsonParserBase.class`
`3e0062104825e575246ba8a3159aa8ea71ab52bf19e5597465e47ac65def8f8d`, `NonBlockingUtf8JsonParserBase.class` `6b312a3f3495498d86923053e74212200036ea0387f0ebc90ee22795b338cd1b`; parent `6145e112266bf5f3c991b3e9af15a0516d5b9db2c63714cee54e3af09d70e8a0`,
`7a5d8f88bfa44313f9ffb10e44661c0b614c3a88ab068c46739a44db6880ab16`, `4989b359732a6b064c7ca06455a9181eb94c4b391178d678201c94fa8f1dd8d4`.

### R28 · jackson-databind #6407 — immutable builder replacements with a late creator property

**Pins.** Parent `b02acce88765473e3d883c877f1e64e1c1d8910d`, fix `0736200316cc75d98d38b73622aad09f28a1fc93` (base `3.x`). Changed: `src/main/java/tools/jackson/databind/deser/bean/BeanAsArrayBuilderDeserializer.java` (+2 −2),
`…/BuilderBasedDeserializer.java` (+4 −4), `…/PropertyBasedCreator.java` (+29 −1), `…/PropertyValue.java` (+21), `src/test/java/tools/jackson/databind/deser/builder/ImmutableBuilderWithCreator6397Test.java` (added, +189).

**Build facts.** `tools.jackson.core:jackson-databind:3.4.0-SNAPSHOT`, parent `tools.jackson:jackson-base:3.4.0-SNAPSHOT`; `javac.src.version` 17, classes **major 61**, `module-info` present.
Runtime: `jackson-annotations:2.24-SNAPSHOT`, `jackson-core:3.4.0-SNAPSHOT` (**later builds than the pins'**, table above). Tests JUnit Jupiter 6.0.3. Built on `$J17`.

**Commands** (in `$W/R28-jackson-databind-ROLE`, `$J17`, report dir `target/surefire-reports`): online 19 s `-Dtest=ImmutableBuilderWithCreator6397Test package`; **offline checked, 17–19 s**
(`case_B.sh R28 $J17 . ImmutableBuilderWithCreator6397Test`).

**Landed tests.** Fix: 8/8. Parent: no such class. Fix's on the parent: **7 failures** (one passes): `retainsBufferedObjectBuilderProperties` (`expected: <Value[a=5, b=6, c=7, d=8]> but was: <Value[a=0, b=0, c=7, d=8]>`),
`retainsBufferedArrayBuilderProperties` (same), `retainsBufferedObjectBuilderPropertiesCreatorLast` (`… but was: <Value[a=0, b=0, c=7, d=0]>`), `retainsBufferedObjectBuilderPropertiesCreatorMissing`
(`expected: <Value[a=5, b=6, c=0, d=8]> but was: <Value[a=0, b=0, c=0, d=0]>`), `retainsBufferedArrayBuilderPropertiesCreatorMissing` (`expected: <Value[a=5, b=6, c=0, d=0]> but was: <Value[a=0, b=0, c=0, d=0]>`),
`retainsBufferedUnwrappedBuilderProperties` (`expected: <UnwrappedValue[a=5, c=7, x=3]> but was: <UnwrappedValue[a=0, c=7, x=3]>`), `retainsBufferedUnwrappedBuilderPropertiesCreatorMissing`.

**Release side.** 3.3.0 (2026-11-08): all four files = parent byte for byte. 3.1.9 (2026-11-24, older line) holds the removed lines: parent side. No 3.4.0 release; none with the fix. 3.3.0 signed.

**Artifacts.** `$O/artifacts/R28-ROLE/jackson-databind-3.4.0-SNAPSHOT.jar` (11 class digests in `SHA256SUMS`; e.g. `PropertyBasedCreator.class` fix `25d00d3bf2722700b4e42a69de1b007c4ce8fa597fc9dd9d54ec306728589c0a`,
parent `c4b9f83c96b9b2d4ab1da53d0db5de862155a2e11ad927dabcd806fa93ed4722`); classpaths also as `*-classpath.pinned.txt`.

### R29 · jackson-databind #6473 — merging into an existing EnumMap

**Pins.** Parent `66ade176743438d3b8247348465aa31eb95e24f7`, fix `949188f567b60b88851f4898eeb9bc82d098cfbe` (base `3.x`). Changed: `src/main/java/tools/jackson/databind/deser/jdk/EnumMapDeserializer.java` (+85 −5),
`src/test/java/tools/jackson/databind/deser/merge/EnumMapMerge6445Test.java` (added, +292), `release-notes/CREDITS`, `release-notes/VERSION`.

**Build facts.** As R28 (same version and snapshot inputs). **Commands.** As R28 with `-Dtest=EnumMapMerge6445Test`; offline checked (17–20 s).

**Landed tests.** Fix: 10/10. Parent: no such class. Fix's on the parent: **1 failure + 2 errors**: `mergeKeepsExistingValueAndAddsMissingKeys` (`expected: <…EnumMapMerge6445Test$Creatable@5b5b59> but was: <…$Creatable@1934ad7c>`:
the existing value object was replaced), `mergeIntoEnumMapWithNonCreatableValues` and `mergeIntoMapTypedEnumMap` (`InvalidDefinitionException: Cannot construct instance of `…EnumMapMerge6445Test$Value` (no Creators, like default constructor, exist)`);
the other 7 (fresh maps, content overrides) pass on the parent too.

**Release side.** 3.3.0 and 3.1.9: `EnumMapDeserializer.java` holds all 5 removed lines and only generic added lines: parent side. No release with the fix.

**Artifacts.** `$O/artifacts/R29-ROLE/`; `EnumMapDeserializer.class` fix `75eb7cb28993009f0fb05d72a88f39ae2059a906fe33bf65e279bcaab9ef8e3c`, parent `365448e874668dc0d25f377e68bf7406caef3a184335b6989b84d9825ff36224`.

### R30 · jackson-dataformat-xml #895 — always-on Base64 names starting with a digit

**Pins.** Parent `f560daa9ecb75c50de084c5a57559f84134554b3`, fix `c3584c7120d6a11e3d417a081d8600be47103fe9` (base `3.x`). Changed: `src/main/java/tools/jackson/dataformat/xml/XmlNameProcessors.java` (+44 −2),
`src/test/java/tools/jackson/dataformat/xml/misc/XmlNameEscapeTest.java` (+119), `release-notes/CREDITS`, `release-notes/VERSION`.

**Build facts.** `tools.jackson.dataformat:jackson-dataformat-xml:3.3.0-SNAPSHOT`, parent `tools.jackson:jackson-base:3.3.0-SNAPSHOT`; classes **major 61**, `module-info` present. Runtime:
`jackson-core:3.3.0-SNAPSHOT`, `jackson-annotations:2.23-SNAPSHOT`, `jackson-databind:3.3.0-SNAPSHOT` (**all November builds, about 2½ months after the pins**, table above), `org.codehaus.woodstox:stax2-api:4.3.1`,
`com.fasterxml.woodstox:woodstox-core:7.3.0`. Test: `jackson-module-jakarta-xmlbind-annotations:3.3.0-SNAPSHOT`, JUnit Jupiter 6.0.3. Built on `$J17`.

**Commands** (in `$W/R30-jackson-dataformat-xml-ROLE`, `$J17`): online 10 s `-Dtest=XmlNameEscapeTest package`; **offline checked, 7–8 s** (`case_B.sh R30 $J17 . XmlNameEscapeTest`; rechecked from a clean tree).

**Landed tests.** Fix: 15/15. Parent's own: 11/11. Fix's on the parent: **4 failures**: `testAlwaysOnBase64NameInvariants` (`Invalid XML name '0IA' encoded from 'Ѐ' ==> expected: <true> but was: <false>`),
`testAlwaysOnBase64NameStartBoundary` (`<DTO><YmFkTWFw><0IA>at</0IA><z78>below</z78></YmFkTWFw></DTO> ==> expected: <true> but was: <false>`), `testAlwaysOnBase64NonAsciiKeysRoundTrip`
(`<DTO><YmFkTWFw><5Lit5paH>cjk</5Lit5paH>…`), `testAlwaysOnBase64AttributeNameRoundTrip` (`<AttrDTO 0IBmaXJzdA="x"/>`).

**Release side.** 3.2.2 (2026-08-14, the last before the fix) and 3.2.3 (2026-09-22) hold both removed lines and few added ones: parent side. **3.3.0** (2026-11-08) holds all 42 added lines and
neither removed one (not byte-equal to the fix). 3.2.2 and 3.3.0 jars kept and signed; 3.2.3 sources only.

**Artifacts.** `$O/artifacts/R30-ROLE/jackson-dataformat-xml-3.3.0-SNAPSHOT.jar`; `XmlNameProcessors.class` fix `d5dbcc736c5284f79da964e56ca56b4e8dd87595a1623d03b447249199d32a81`, parent `1bc5bf167d845e429c161de86a6feb82a5ce3a66710be2ae81096a7822230ad6`;
`XmlNameProcessors$AlwaysOnBase64NameProcessor.class` fix `a408ef2147a986b8fad3d39c0a0e32506b009352fef355f7a47e16834392ce6a`, parent `bef5872b5bb6e66627193815d5b5c420fd75857c5314108b567ed61c7a181189` (other nested classes in `SHA256SUMS`); `*-classpath.pinned.txt` as R28.

### R23 · javaparser #5176 — typed literal setters notify observers

**Pins.** Parent `a322c502cfac7d97495fc3f41c6b74a06924267f`, fix `c9c78dd4c965646dd97bbf3108ff1faefa1ae198`. Changed (each +1 −1 unless noted): `javaparser-core/src/main/java/com/github/javaparser/ast/expr/CharLiteralExpr.java`,
`…/DoubleLiteralExpr.java`, `…/IntegerLiteralExpr.java`, `…/LongLiteralExpr.java`, `…/StringLiteralExpr.java` (+2 −2); tests `javaparser-core-testing/src/test/java/com/github/javaparser/ast/expr/LiteralStringValueExprTest.java` (+60),
`…/printer/lexicalpreservation/LiteralValueSettersTest.java` (added, +84).

**Build facts.** `com.github.javaparser:javaparser-core:3.29.0-SNAPSHOT` (root `javaparser-parent:3.29.0-SNAPSHOT`, 8 modules; only `javaparser-core` and `javaparser-core-testing` built), `java.version` 1.8,
classes **major 52**, no `module-info` (Automatic-Module). **No runtime dependencies.** Tests (`javaparser-core-testing`): JUnit Jupiter 5.14.4, AssertJ 3.27.7, Mockito 4.11.0, Hamcrest 3.0. Built on `$J17`. No external snapshot.

**Commands** (in `$W/R23-javaparser-ROLE`, `$J17`, report dir `javaparser-core-testing/target/surefire-reports`):
- online (18 s): `-pl javaparser-core-testing -am -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=LiteralStringValueExprTest,LiteralValueSettersTest package`
- **offline (checked, 10–14 s)**: the same with `-o` (`case_B.sh R23 $J17 javaparser-core-testing LiteralStringValueExprTest,LiteralValueSettersTest`).

**Landed tests.** Fix: 16/16. Parent's own: 8/8 (`LiteralStringValueExprTest` only). Fix's on the parent: **7 failures**: `LiteralStringValueExprTest#typedSettersNotifyObservers` (`Wanted but not invoked:
astObserver.propertyChange("b\n", VALUE, "a", "b\n") … Actually, there were zero interactions with this mock.`) and `LiteralValueSettersTest#setInt` (`expected: <class A { int i = 2; }> but was: <class A { int i = 1; }>`),
`setDouble`, `setString` (`expected: <class A { String s = "b\n"; }> but was: <class A { String s = "a"; }>`), `setEscapedValue`, `setChar`, `setLong` (`expected: <… long l = 2; }> but was: <… long l = 1L; }>`).

**Release side.** Latest release 3.28.2 (2026-05-31): all five files = parent byte for byte. No 3.29.0 release; none with the fix. Signed.

**Artifacts.** `$O/artifacts/R23-ROLE/javaparser-core-3.29.0-SNAPSHOT.jar` (five class digests in `SHA256SUMS`, e.g. `StringLiteralExpr.class` fix `146defc223e3d9c1fe76a3776fb80c939b588646779aa70951c8651294b360be`,
parent `09f6e9b1ed2d1ee48a7e3a29df999b4fdbd56f4b980d3ff0f79dee1faea6ebcd`); `core-testing-test-classpath.txt` = the test classpath of `javaparser-core-testing`, with the kept jar in place of the reactor's.

### R24 · javaparser #5207 — lexical printing of C-style array brackets

**Pins.** Parent `7bb33415ec75aa3fe01c1b3741cbe9ee48413739`, fix `ae2e9400810933b1523f3182acc69bf8998e26ca`, two commits: middle `ba880df507664d320f54028810c42e07e429515f` (test only: `ArrayTypeTest.java` +15,
annotated-varargs legal notation). Changed overall: `javaparser-core/src/main/java/com/github/javaparser/ast/type/ArrayType.java` (+13 −1), `…/printer/ConcreteSyntaxModel.java` (+9 −6),
`…/printer/concretesyntaxmodel/CsmArrayBrackets.java` (added, +172), `…/printer/lexicalpreservation/LexicalDifferenceCalculator.java` (+12), `…/LexicalPreservingPrinter.java` (+6 −17);
tests `javaparser-core-testing/src/test/java/com/github/javaparser/ast/type/ArrayTypeTest.java` (+20), `…/printer/lexicalpreservation/CStyleArrayDeclarationTest.java` (added, +147).

**Build facts.** As R23. **Commands.** As R23 with `-Dtest=ArrayTypeTest,CStyleArrayDeclarationTest`; offline checked (12–14 s).

**Landed tests.** Fix: 36/36. Parent's own: 14/14 (`ArrayTypeTest`). Fix's on the parent: **11 failures + 4 errors**: `ArrayTypeTest#ellipsisCanHaveAnnotationsToo` (`expected: <int[]@X... a[]> but was: <int[][]@X... a>`;
the fix commit changed this assertion), and in `CStyleArrayDeclarationTest`: `renameIdentifier[1–3]` (e.g. `expected: <class A { void m(String b[]) {} }> but was: <class A { void m(String a[]b) {} }>`,
`[3]`: `expected: <… m(String[] b[]) …> but was: <… m(String[] a[]b) …>`), `replaceName[1]` (same), `replaceName[3–5]` (`UnsupportedOperationException: NodeText: …`), `replaceTypeByArrayType[1–2]`
(e.g. `expected: <class A { void m(long[] a) {} }> but was: <class A { void m(long[]) {} }>`), `[3]` (`UnsupportedOperationException: removed CsmToken(property:]) vs ";"`), `replaceTypeByNonArrayType[1–4]`
(e.g. `expected: <class A { long a; }> but was: <class A { long a[][]; }>`). Full list `$O/logs/R24-parent-landedfix.failures.txt`. The middle commit's `ArrayTypeTest` on the parent: **15/15 pass**
(`$O/logs/R24-parent-middletest.junit.txt`), so the middle commit changes no behaviour.

**Release side.** 3.28.2: `ArrayType.java`, `ConcreteSyntaxModel.java` = parent; `CsmArrayBrackets.java` absent; the two lexical-preservation files hold all removed lines: parent side. No release with the fix.

**Artifacts.** `$O/artifacts/R24-ROLE/` (13 / 12 class digests; e.g. `LexicalPreservingPrinter.class` fix `d681be3cb8be0754d0f515f89f6e062393df4d92afc8a9e99035a7f5e33cf06c`, parent `841f1e7ae1cb2b68b7b443c7f99f7cfc6f1284b3ebb9e1e04ba6f9682334eed8`;
`CsmArrayBrackets.class` fix only, `f09fbe5932f4f113d146966da4705c720b8a04f3aa3399c441d8c741f4a86f7d`), `core-testing-test-classpath.txt` as R23.

### R48 · assertj #3710 — record component accessor before the `is` alias

**Pins.** Parent `d2257cab92a263fde1159ad5bcc7339de2effbc9`, fix `f3ece963d761d66a7ee31d29ccd9158df3794024` (base `3.x`). Changed: `assertj-core/src/main/java/org/assertj/core/util/introspection/Introspection.java` (+9 −1),
`assertj-tests/assertj-integration-tests/assertj-core-tests/src/test/java/org/assertj/tests/core/api/recursive/comparison/RecursiveComparisonAssert_isNotEqualTo_with_record_Test.java` (added, +33).

**Build facts.** `org.assertj:assertj-core:3.27.1-SNAPSHOT` (root `assertj-build`), compiled with release 8 (classes **major 52**, `module-info` via release 9). Runtime: `net.bytebuddy:byte-buddy:1.15.11`
(a separate jar, not shaded). The landed test's module `assertj-core-tests` needs **Java 21** (`assertj-tests` sets `java.version` 21; records). Built on `$J21`. No external snapshot.

**Commands** (in `$W/R48-assertj-ROLE`, `$J21`, report dir `assertj-tests/assertj-integration-tests/assertj-core-tests/target/surefire-reports`):
- online (67 s, first resolution): `-pl assertj-tests/assertj-integration-tests/assertj-core-tests -am -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dtest=RecursiveComparisonAssert_isNotEqualTo_with_record_Test package`
- **offline (checked, 17–20 s)**: the same with `-o`.

**Landed tests.** Fix: 1/1. Parent: no such class. Fix's on the parent: **1 failure**, `should_compare_records_with_component_named_as_boolean_accessor`: `java.lang.AssertionError: Expecting actual:
Record[field=value1, isField=true] not to be equal to: Record[field=value2, isField=true] when recursively comparing field by field …`.

**Release side.** 3.27.0 (2024-12-19) `Introspection.java` = parent; **3.27.1** (2025-01-01) holds all 8 added lines and not the removed one (not byte-equal). Both signed.

**Artifacts.** `$O/artifacts/R48-ROLE/assertj-core-3.27.1-SNAPSHOT.jar`; `Introspection.class` fix `61e7baea5a900f4c4c98591e925f304eb0cacdf79b12c79896c08f9504df6036`, parent `2e583508bf1f87ef0c38496cf05644ea808dbbf9edf8b2c9a9c69a08897d9a4c`;
`core-tests-test-classpath.txt` = the test classpath of `assertj-core-tests` with the kept jar in place.

## Cases R25–R50 (fork D, Gradle)

Fork D of the setup did the twelve Gradle cases: R25 (moshi), R33, R34 (Calcite), R41, R44 (RxJava), R42, R43 (Reactor Core), R45, R46 (Resilience4j),
R47 (picocli), R49, R50 (JUnit). Eight ran inline (each Gradle run under a minute once resolved); **R42's pinned build cannot be configured** from public
sources and took the slice route; **R33, R34, R49 and R50 build and test by two jobs**, `20261126-172339-setup-build-apache-calcite-at-both-pins` (Calcite) and `20261126-172339-setup-build-junit-at-both-pins-of-5839-a` (JUnit), queued by
`$O/scripts/submit_D.py` after everything they need was resolved online into `$O/gradle-home`.

### Toolchain (fork D)

Gradle distributions in `$O/tools/gradle-V`, zips in `$O/dl/gradle/` with services.gradle.org's `.sha256` beside them (`$O/logs/D-gradle-dists.tsv`); every zip equals its
published sha256. Each pin's `gradle/wrapper/gradle-wrapper.jar` was matched against the published wrapper checksums of all 166 Gradle releases
(`https://services.gradle.org/versions/all`, `$O/logs/D-wrapper-matches.txt`); every one is a published wrapper jar, often an older version's. The wrappers are not run:
the unpacked distributions are.

| Gradle | Cases | zip sha256 (= published) | pins' wrapper jar sha256 | = published wrapper of |
|---|---|---|---|---|
| 2.14 | R41 | `993b4f33b652c689e9721917d8e021cab6bbd3eae81b39ab2fd46fdb19a928d5` | `b5ca811c057b3eb4164c78f4155d667c6092ff98ba91a4c90d29e127426f37a7` | 2.14 |
| 4.2.1 | R42 | `b551cc04f2ca51c78dd14edb060621f0e5439bdfafa6fd167032a09ac708fbc0` | `53aa048fef3c06a8442c6a44df5edd2e8c791ee883e42ded6189c7eed112095d` | 4.2 |
| 5.6 | R44 | `15c02ef5dd3631ec02ac52e8725703e0285d9a7eecbf4e5939aa9e924604d01d` | `383f4efa709b52632a520708e8a07353961970941ab3867ab8ac182132ce1c54` | 4.3.1 |
| 7.3 | R25 | `de8f52ad49bdc759164f72439a3bf56ddb1589c4cde802d3cec7d6ad0e0ee410` | `33ad4583fd7ee156f533778736fa1b4940bd83b433934d1cc4e9f608e99a6a89` | 7.3 |
| 7.4.2 | R45, R46 | `29e49b10984e585d8118b7d0bc452f944e386458df27371b49b4ac1dec4b7fda` | `660ab018b8e319e9ae779fdb1b7ac47d0321bde953bf0eb4545f14952cfdcaa3` | 4.10.3 |
| 7.6 | R47 | `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` | `575098db54a998ff1c6770b352c3b16766c09848bee7555dab09afc34e8cf590` | 7.4, 7.4.1, 7.4.2 |
| 8.6 | R43 | `9631d53cf3e74bfa726893aee1f8994fee4e060c401335946dba2156f440f24c` | `d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd` | 8.6 |
| 8.13 | R50 | `20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78` (= wrapper `distributionSha256Sum`) | `81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f` | 8.13 |
| 8.14.4 | R33, R34 | `f1771298a70f6db5a29daf62378c4e18a17fc33c9ba6b14362e0cdf40610380d` (= `distributionSha256Sum`) | `498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17` | 8.9 |
| 9.6.1 | R49 | `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` (= `distributionSha256Sum`) | `497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7` | 9.6.1 |

The 4.2.1, 7.6, 8.14.4 and 9.6.1 zips were copied from earlier setups' caches and checked again; the others were downloaded. JDKs: the sdkman Temurin set of
`env.sh` plus Temurin 24.0.2+12 from an earlier setup (R49's `JDK24`; see R49). No JDK was added.

**Substitute repository** `$O/dl/subst-repo-D` (log `$O/logs/D-subst-repo.txt`, every pom and jar there equal to its source's `.sha1`), added by
`$O/scripts/subst-repo-D.init.gradle` to plugin and build-script resolution only: `org.ysb33r.gradle:grolifant:0.10` (R45, R46) and nine modules for R41 from
`https://repo.grails.org/grails/core`; `org.jfrog.buildinfo:build-info-{extractor,client,api}:2.8.2` (R44) from JFrog's jcenter mirror, also equal to
`releases.jfrog.io/artifactory/oss-release-local`. Details in each case. Nothing compiled or tested uses them.

**Helpers** (`$O/scripts/`): `gradle_case_D.sh` (one Gradle run: verified distribution, JDK, 6 GB scope with `choom -n 500` unless `SCOPE=" "` in a job, `--no-daemon`,
offline unless `ONLINE=1`, `-Dorg.gradle.caching=false`, toolchain auto-detect/download off and paths = the sdkman JDKs unless `NOTC=1`, init scripts from `GINIT`, log
`$O/logs/TAG.log` and JUnit summary `TAG.junit.txt`), `junit_gradle_D.sh`, `overlay_D.sh CASE` (copy of the parent with the fix's changed test files, `$O/build/CASE-parent-landed`),
`standalone_D.sh`, `cp_D.sh` (classpaths), `digests_D.sh`, `classdiff_D.py`, `failmsgs_D.py`, `relcmp_D.sh` (git blob ids of released sources vs the pins), `linecmp_D.py`
(the PR's added/removed lines found in a release), `subst_add_D.sh`, `subst_find_D.sh`, `write-classpath-old.init.gradle` (Gradle < 4.9), `resolve-all-D.init.gradle`,
`slice_D.sh` with `slice-R42.conf`, `verify_cp_D.sh`, `sigs_D.sh`, `calcite_job.sh`, `junit_job.sh`, `submit_D.py`.

| Case | Built | Release side | Landed tests (fix / parent's own / fix's tests on the parent) | Upstream run |
|---|---|---|---|---|
| R25 moshi #1442 | Gradle 7.3, JDK 17, :moshi jar + records-tests at both pins | 1.12.0 has no records support; 1.13.0 has the fix (not byte-equal) | 6/6 · 5/5 · 1 of 6 FAILS (indirectGenerics: No JsonAdapter for T) | inline |
| R33 calcite #5345 | Gradle 8.14.4, JDK 21 + toolchain 25; resolved inline | none has the fix; 1.42.0 predates the parent | by job | job 20261126-172339-setup-build-apache-calcite-at-both-pins |
| R34 calcite #4942 | Gradle 8.14.4, JDK 21 + toolchain 25; resolved inline | none has the fix; 1.42.0 = parent for all 5 changed files | by job | job 20261126-172339-setup-build-apache-calcite-at-both-pins |
| R41 RxJava #5101 | Gradle 2.14, JDK 8, standalone clones, 9 jcenter-only build-script modules substituted | 2.0.6 = parent, 2.0.7 = fix (exact) | 150 · 136 · 3 of 150 FAIL (Maybe noSubsequentSubscription*) | inline |
| R42 reactor-core #937 | NOT configurable (propdeps-plugin 0.0.7, spring-io-plugin 0.0.4.RELEASE, dokka integration 0.9.15 only on repo.spring.io, 401/405); slice route on 3.1.1.RELEASE | 3.1.0/3.1.1 = parent, 3.1.2 = fix (code files; Flux.java Javadoc only) | slice: 226/226 · 210/210 · 10 of 226 FAIL (delayError…WithMonoError/FluxError); 3.1.1 alone same 10 fail, 3.1.2 alone all pass | inline (slice) |
| R43 reactor-core #3783 | Gradle 8.6, JDK 8, :reactor-core at both pins | 3.4.37 = parent, 3.4.38 = fix (exact) | 7/7 · 6/6 · 3 of 7 FAIL (testThenManyOnConcatArray, 2× testThenManyRepeated) | inline |
| R44 RxJava #6664 | Gradle 5.6, JDK 8, build-info 2.8.2 substituted | 3.0.0-RC3 = parent; RC4 = fix for ObservableGroupBy, fix + later changes for FlowableGroupBy | 104 · 100 · 1 of 104 FAILS (FlowableGroupByTest#newGroupValueSelectorFails) | inline |
| R45 resilience4j #2067 | Gradle 7.4.2, JDK 17, grolifant 0.10 substituted | 2.1.0 predates, 2.2.0 has the fix (not byte-equal) | 16/16 · 12/12 · 3 of 16 FAIL (×4 with test-retry) | inline |
| R46 resilience4j #1999 | Gradle 7.4.2, JDK 17, same substitution | 2.1.0 (brief) predates, 2.2.0 has the fix | 1/1 · (new test) · 1 of 1 FAILS (IllegalAccessException on Issue560 lambda) | inline |
| R47 picocli #2036 | Gradle 7.6, JDK 11, root jar | 4.7.3 predates, 4.7.4 has the fix | 13/13 · 10/10 · 3 of 13 FAIL (the three new inherited fallback tests) | inline |
| R49 junit #5839 | Gradle 9.6.1, JDK 25 (+17,21,24), standalone clones; resolved inline | 6.1.1 (brief) predates; 6.1.2 = 6.1.1 + exactly the fix's 7 lines | by job | job 20261126-172339-setup-build-junit-at-both-pins-of-5839-a |
| R50 junit #4466 | Gradle 8.13, JDK 21, standalone clones; resolved inline | 5.12.1 = parent, 5.12.2 (brief) = fix (exact) | by job | job 20261126-172339-setup-build-junit-at-both-pins-of-5839-a |

### R25 · moshi #1442 — nested record components resolved in the enclosing parameterized type (upstream Gradle 7.3 build at both pins, inline)

**Pins.** Parent `751e8219e992a9aecd286aac830fef81da790baa`, fix `cdcf0da4ee260b72d7e1ea2be691a568e03720b3` (squash on `master`, one parent = the brief's).
Changed: `moshi/src/main/java16/com/squareup/moshi/RecordJsonAdapter.java` (+5 −30: component types through `Util.resolve(type, rawType, …)`),
`moshi/records-tests/src/test/java/com/squareup/moshi/records/RecordsTest.java` (+15: `indirectGenerics` with `HasIndirectGenerics`/`IndirectGenerics<T>`).

**Build facts.** Gradle 7.3 (`$O/tools/gradle-7.3`; wrapper jar = 7.3's published one), run on **JDK 17** (`$J17`); Kotlin 1.6.0 plugin. Version
`1.13.0-SNAPSHOT`. `moshi` is a **multi-release jar**: the record adapter is compiled from `src/main/java16` with `--release 16` into
`META-INF/versions/16/`, beside a Java 8 stub `com/squareup/moshi/RecordJsonAdapter.class`; so the records path needs a JVM ≥ 16 and the jar on the
class path (not exploded classes). `records-tests` uses a Java 17 toolchain (`$J17`), `--release 16`. Runtime classpath of `:moshi`: okio-jvm 2.10.0,
kotlin-stdlib(-jdk7,-jdk8,-common) 1.6.0, annotations 13.0. Tests: JUnit 4.13.2, Truth 1.1.3. `gradle_case_D.sh` ran with `GOPTS=-Xmx512m`
(the client JVM; the build's own `org.gradle.jvmargs=-Xmx2048m` applies to the daemon it forks). Central and the Plugin Portal only; nothing substituted.

**Commands** (`GOPTS=-Xmx512m $O/scripts/gradle_case_D.sh DIR TAG 7.3 $J17 moshi/records-tests/build/test-results/test ARGS`):
- online at the fix (64 s): `ONLINE=1 … :moshi:jar :moshi:records-tests:test --tests com.squareup.moshi.records.RecordsTest`
- **offline (checked, 7 s at the fix, 16 s at the parent)**: the same without `ONLINE=1`
- classpaths: `$O/scripts/cp_D.sh R25 ROLE 7.3 $J17 :moshi` and `… :moshi:records-tests`

**Landed tests** (JDK 17.0.21):

| Run | Result |
|---|---|
| fix, `RecordsTest` (online, then offline) | 6/6 pass |
| parent, its own `RecordsTest` (offline) | 5/5 pass |
| the fix's `RecordsTest` on a copy of the parent (offline) | **1 of 6 fails**, the new `indirectGenerics`: `java.lang.IllegalArgumentException: No JsonAdapter for T (with no annotations) for T for java.util.List<T> for com.squareup.moshi.records.RecordsTest$IndirectGenerics<java.lang.Long> for class com.squareup.moshi.records.RecordsTest$HasIndirectGenerics` (`$O/logs/R25-parent-landed.failures.txt`) |

**Artifacts** (`$O/artifacts/R25-{parent,fix}/`: `moshi-1.13.0-SNAPSHOT.jar`, `SHA256SUMS`, `moshi.{runtime,testRuntime}Classpath.txt`, `moshi_records-tests.testRuntimeClasspath.txt`):

| File | parent sha256 | fix sha256 |
|---|---|---|
| `moshi-1.13.0-SNAPSHOT.jar` | `89089638e260d3741c30c81b6d225334bb34ab0f8b9cae7ca356f3f0a55338c8` | `a5bfe2ad8afdbeed7fb8f412b09bae6c62ee3ec0e21dd88d1e693fb69e4f7e6b` |
| `META-INF/versions/16/com/squareup/moshi/RecordJsonAdapter.class` | `bafe56e3f15b86f3d6f0e3d99360492ad320c4f05cb5a8b641946b7159e0fdce` | `2db9f951fb8f4197adb89d26b5f041ba80952b1cfebe5d5c58205f314eae456c` |
| `META-INF/versions/16/com/squareup/moshi/RecordJsonAdapter$ComponentBinding.class` | `99644e0e8a13a7c6eb668331a96f540ac4c3f7610cb1a30cccd4fce37d0aa0d6` | `f84cfad45c2237c3e6fa8508aa3031638d7d31adaffc4f56fdb093438812aa79` |
| Java 8 stub `com/squareup/moshi/RecordJsonAdapter.class` (both) | `d9abd3e496f7ad70636669a3df4fa8791fdaf42ca82fe75066dce25494b0b890` | the same |
| stub `com/squareup/moshi/RecordJsonAdapter$1.class` (both) | `bb0f255bcb8c92d9d51a0ce30c93eed7957a71d53d14937d857254e3ae4c3595` | the same |

**Release side** (`$O/releases/moshi-1.1{2,3}.0/`, jar, pom, `-sources.jar`, checked against Central's hashes):
- **1.12.0 has no record support at all**: no `RecordJsonAdapter` in its jar or sources. `moshi-1.12.0.jar` `ee9091e1d1a5926fa9b4df2642c1fb7bb96aec08639b6219c19e0b8724d42475`. No release is on the parent's side.
- **1.13.0 (2021-12-08) is the first release with the fix**: its `-sources.jar` omits the `java16` source, so the release tag's commit
  `09a454329751e19adb18e39dee043c9a4eeada61` ("Prepare for release 1.13.0.", tag `moshi-parent-1.13.0`) was fetched into the mirror: its
  `RecordJsonAdapter.java` (blob `cc69e40eb210b1f2c961fe4c04ec7aa7a1ccb3eb`; parent `6152d10a57c61a1b1449fff4ac474725ce42fd11`, fix `21f305abada635103e537e87162c09f349b06e27`)
  holds all five added lines (one rewrapped) amid later reformatting, so 1.13.0's records path is not byte-equal to the fix's (bytecode differs, `javap -c`).
  `moshi-1.13.0.jar` `bd004dd9ba175e603ad44420bf605250291b9b7bc6b9d9e916f5741ac8663307`.

### R33 · Calcite #5345 — nested casts keep intermediate precision and formatting (upstream Gradle 8.14.4 build; jars and landed tests by job `20261126-172339-setup-build-apache-calcite-at-both-pins`)

**Pins.** Parent `c368970b2950903432ed61ecd7ff404a67e16fb1`, fix `a2e574ec271866eb352f98d7101a386a30dc8bc8` (squash on `main`, one parent = the brief's).
Changed production files: `core/src/main/java/org/apache/calcite/rex/RexSimplify.java` (+79 −27), `core/src/main/java/org/apache/calcite/rex/RexUtil.java` (+18 −4).
Tests: `core/src/test/java/org/apache/calcite/rex/RexLosslessCastTest.java` (+78 −9), `core/src/test/resources/sql/cast.iq` (+112, run by `CoreQuidemTest`),
`core/src/test/java/org/apache/calcite/rel/rel2sql/RelToSqlConverterTest.java` (+3 −1: an expected dialect string now `CAST(CAST(employee_id AS STRING) AS TIMESTAMP)`).

**Build facts.** Gradle 8.14.4 (`$O/tools/gradle-8.14.4`; zip sha256 = the wrapper's `distributionSha256Sum`; the pins' wrapper jar is 8.9's), run on **JDK 21**
(`$J21`), compiling with the build's default **JDK 25 toolchain** (`jdkBuildVersion` 25) at `--release 8`; `--no-scan`, `-Dorg.gradle.caching=false`
(`gradle.properties` sets caching on), `NOTC` unset so toolchain paths are the sdkman JDKs. Version `1.43.0-SNAPSHOT` (`calcite.version=1.43.0`).
The build has a Kotlin `buildSrc` (fmpp, javacc). **Online resolution inline** (`$O/logs/R33-fix.resolve-online.log`, 114 s): `setupResolveAll -PsetupResolve=ALL`
on `:core`, `:linq4j`, `:testkit` (54 configurations, none failed); the parent then resolved offline with nothing missing (`R33-parent.resolve-offline.log`).
No substitution.

**Commands** (`$O/scripts/calcite_job.sh R33 fix|parent|landed|clean`, the job's steps; each runs
`$O/scripts/gradle_case_D.sh DIR TAG 8.14.4 $J21 core/build/test-results/test --no-scan --continue :core:jar :linq4j:jar :testkit:jar :core:test --tests org.apache.calcite.rex.RexLosslessCastTest --tests org.apache.calcite.rel.rel2sql.RelToSqlConverterTest --tests org.apache.calcite.test.CoreQuidemTest`
offline, `GRADLE_WORKERS=3`, `GOPTS=-Xmx512m`). The offline task graph was checked inline with `-m` (R34 fix, 27 s). A single Quidem file can run outside Gradle: `CoreQuidemTest.main sql/cast.iq` on the core test runtime classpath.

**Landed tests and artifacts:** produced by job `20261126-172339-setup-build-apache-calcite-at-both-pins` (steps 1–4); results go to `$O/logs/R33-{fix,parent,parent-landed}.test-offline.{log,junit.txt,failures.txt}`,
jars (`calcite-core`, `-linq4j`, `-testkit` `1.43.0-SNAPSHOT`), `SHA256SUMS` and `core.{runtime,testRuntime}Classpath.txt` to `$O/artifacts/R33-{parent,fix}/`.
<!-- R33-job -->

**Release side.** **No release has the fix**: Central's newest `calcite-core` is **1.42.0** (2026-05-28), older than the parent; its `RexSimplify.java` and
`RexUtil.java` are on neither side byte for byte and lack the fix's added code (`$O/scripts/linecmp_D.py`). `calcite-core-1.42.0.jar`
`2ed5489201baab842001c95f939a0829849cf3cdaed9cdbf4b9078633c35792b` (with `-sources.jar`, `$O/releases/calcite-core-1.42.0/`).

### R34 · Calcite #4942 — sub-millisecond temporal literals survive constant reduction (upstream Gradle 8.14.4 build; jars and landed tests by job `20261126-172339-setup-build-apache-calcite-at-both-pins`)

**Pins.** Parent `3fc5f464ee087f69cd7b1f8dd54ee612050a917d`, fix `b25114f7c616b6e3fb4007071406f79e765ff66f` (squash on `main`, one parent = the brief's).
Changed production files: `core/src/main/java/org/apache/calcite/rex/RexBuilder.java` (+127), `core/src/main/java/org/apache/calcite/rex/RexExecutorImpl.java` (+24 −3),
`core/src/main/java/org/apache/calcite/adapter/enumerable/RexToLixTranslator.java` (+4 −2), `core/src/main/java/org/apache/calcite/util/BuiltInMethod.java` (+4).
Tests: `core/src/test/java/org/apache/calcite/rex/RexExecutorTest.java` (+207) and the test library `testkit/src/main/java/org/apache/calcite/test/SqlOperatorTest.java`
(+1 −1: an expected `VARCHAR` result becomes `"2024-07-06 12:15:48.678"`; it runs in core's `CalciteSqlOperatorTest`).

**Build facts.** As R33 (Gradle 8.14.4 on JDK 21, JDK 25 toolchain, `1.43.0-SNAPSHOT`). Online resolution inline at both pins (`$O/logs/R34-{fix,parent}.resolve-online.log`, 42 s and 15 s);
the first offline try had failed only on the `com.gradle.develocity` 3.18.2 settings plugin, which the online run then fetched. Offline task graph checked with `-m` (27 s).

**Commands** (`$O/scripts/calcite_job.sh R34 fix|parent|landed|clean`): `… :core:jar :linq4j:jar :testkit:jar :core:test --tests org.apache.calcite.rex.RexExecutorTest --tests org.apache.calcite.test.CalciteSqlOperatorTest`.
The overlay for the landed run copies `RexExecutorTest.java` and the testkit `SqlOperatorTest.java` (`$O/scripts/overlay_D.sh`).

**Landed tests and artifacts:** produced by job `20261126-172339-setup-build-apache-calcite-at-both-pins` (steps 5–8), into `$O/logs/R34-*.test-offline.*` and `$O/artifacts/R34-{parent,fix}/` (the testkit jar's `SqlOperatorTest` classes are in `SHA256SUMS` as a changed file).
<!-- R34-job -->

**Release side.** **No release has the fix.** **1.42.0 is a parent stand-in for every changed file**: `RexBuilder.java`, `RexExecutorImpl.java`,
`RexToLixTranslator.java`, `BuiltInMethod.java` in `calcite-core-1.42.0-sources.jar` and `SqlOperatorTest.java` in `calcite-testkit-1.42.0-sources.jar` are
byte-equal to the parent's (git blob ids; other files differ). `calcite-core-1.42.0.jar` `2ed5489201baab842001c95f939a0829849cf3cdaed9cdbf4b9078633c35792b`,
`calcite-testkit-1.42.0.jar` `b43fe364aa58ef52a495bc3b65f1e180b1ba81955cef4b4bd01206dd60246e62` (`$O/releases/calcite-{core,testkit}-1.42.0/`; the dependency graph was not resolved for them).

### R41 · RxJava #5101 (2.x) — Maybe concatenation does not subscribe to the next source after cancellation (upstream Gradle 2.14 build at both pins, inline; nine jcenter-only build-script modules substituted)

**Pins.** Parent `5a8be22b6501feefe10fb00731c00ce1ad215b89`, fix `6daf59ebc19f5ef8914086fe466823f51ca628a9` (squash on `2.x`, one parent = the brief's).
Changed production files (`src/main/java/io/reactivex/internal/operators/maybe/`): `MaybeConcatArray.java`, `MaybeConcatArrayDelayError.java`,
`MaybeConcatIterable.java` (+3 −2 each: a `isCancelled()`/`isDisposed()` recheck before the next source). Tests (`src/test/java/io/reactivex/internal/operators/`):
`flowable/FlowableConcatTest.java` (+84), `maybe/MaybeConcatArrayTest.java` (+41), `maybe/MaybeConcatIterableTest.java` (+42),
`observable/ObservableConcatTest.java` (+83), `single/SingleConcatTest.java` (+43); `$O/scripts/R41-tests.txt` holds the five `--tests` filters.

**Checkouts.** `$W/R41-RxJava-parent` and `$W/R41-RxJava-fix` are **standalone depth-1 clones** of the mirror at the pins (`$O/scripts/standalone_D.sh`),
not linked worktrees: the build applies `nebula.rxjava-project` 4.0.0, whose release plugin needs a `.git` directory (in a linked worktree it fails with
`Cannot set property 'defaultVersionStrategy' on null object`). Trees parent `511c3f166d43e5c0903af5f68e035c6b4e50241c`, fix `f7447c9f8bf6773538b6ab9fac7f3820b725adee`, as in the revisions table.
Without tags the version is `2.0.0-DP0-SNAPSHOT` (`gradle.properties`), so the jars are `rxjava-2.0.0-DP0-SNAPSHOT.jar`.

**Build facts.** **Gradle 2.14** (`$O/tools/gradle-2.14`; wrapper jar = 2.14's published one) on **JDK 8** (`$J8`; Gradle 2.14 runs on nothing later),
`CI=true`, `NOTC=1` (no toolchain properties). Source/target 1.6 (class files major 50). Runtime dependency `org.reactivestreams:reactive-streams:1.0.0`
only (`ef867702a614b96eb6c64fb65a8f5e14bdfcabbc1ae056f78a1643f7b79ca0eb`, in `$O/gradle-home`). Tests: JUnit 4.12, Mockito 2.1.0, reactive-streams-tck 1.0.0, TestNG 6.9.10.
Results are under `build/test-results/` (Gradle 2.x layout).

**Substitution (build-script classpath only).** The build script's only repository is `jcenter()`. jcenter no longer serves the nebula plugin's
publishing dependencies, and neither Central nor the Plugin Portal has them. The **same coordinates** were copied from `https://repo.grails.org/grails/core`
into `$O/dl/subst-repo-D`, each pom and jar equal to that repository's `.sha1` (`$O/scripts/subst_add_D.sh`, `$O/logs/D-subst-repo.txt`), and added by
`$O/scripts/subst-repo-D.init.gradle` (adapted to Gradle 2.14, which has no `pluginManagement`). `http-builder-0.7.2.jar`'s SHA-1 equals the one an earlier
setup took independently from JFrog's jcenter mirror and repo.grails.org (`merged-pr-links` record, M13). Nothing compiled or tested uses them.

| Module | jar SHA-1 (= published) |
|---|---|
| `com.github.jengelman.gradle.plugins:shadow:1.2.3` | `52bbde5e384f0860df145abe24070d74dd8ed590` |
| `com.jfrog.bintray.gradle:gradle-bintray-plugin:1.5` | `7f3dc1cd3c538b4906006ffcf90d23aee569be3f` |
| `com.perforce:p4java-jfrog:2011.1.297684` | `1de41848e31c6428e6eb7a71e8f88b9561d35fe1` |
| `nl.javadude.gradle.plugins:license-gradle-plugin:0.11.0` | `af79687fb505c520abb404ed9e822be15b25eb62` |
| `org.jfrog.buildinfo:build-info-extractor-gradle:4.0.0` | `37347d4122e50d83a30a07ef35fea47932722fe8` |
| `org.codehaus.groovy.modules.http-builder:http-builder:0.7.2` | `323092cd786480311c1cf693770f9e6fc20a8bef` |
| `org.jfrog.buildinfo:build-info-extractor:2.5.4` | `c8c416564baae94bf0e447c1ff63e55a7f23fced` |
| `org.jfrog.buildinfo:build-info-client:2.5.4` | `1ff780d21f3182b41b3d12c1222556feda0d4bb4` |
| `org.jfrog.buildinfo:build-info-api:2.5.4` | `a0f635a1ba06824b8c69b8a95755dd9a5cdc6160` |

**Commands** (`CI=true NOTC=1 GINIT=$O/scripts/subst-repo-D.init.gradle $O/scripts/gradle_case_D.sh DIR TAG 2.14 $J8 build/test-results ARGS`):
- online at the fix (32 s): `ONLINE=1 … jar test $(cat $O/scripts/R41-tests.txt)`
- **offline (checked, 24 s)**: the same without `ONLINE=1`
- classpaths: `GINIT="$O/scripts/subst-repo-D.init.gradle $O/scripts/write-classpath-old.init.gradle" … setupWriteClasspath -PsetupCpConf=runtime|testRuntime -PsetupCpOut=FILE`

**Landed tests** (JDK 8u512):

| Run | Result |
|---|---|
| fix, the five changed test classes (online, then offline) | 150 run, 0 failures, 2 skipped |
| parent, its own copies (offline) | 136 run, 0 failures, 2 skipped |
| the fix's five test files on a copy of the parent clone (offline) | **3 of 150 fail** (`$O/logs/R41-parent-landed.failures.txt`): `MaybeConcatArrayTest#noSubsequentSubscription`, `MaybeConcatArrayTest#noSubsequentSubscriptionDelayError`, `MaybeConcatIterableTest#noSubsequentSubscription`, each `java.lang.AssertionError: expected:<1> but was:<2>` |

The new Flowable, Observable and Single tests pass on the parent too (only the Maybe operators changed).

**Artifacts** (`$O/artifacts/R41-{parent,fix}/`: jar, `SHA256SUMS`, `runtime.txt`, `testRuntime.txt`):

| File | parent sha256 | fix sha256 |
|---|---|---|
| `rxjava-2.0.0-DP0-SNAPSHOT.jar` | `41243f5b735ce07da6e515fcdf78db065851dc6de3f67b97142f70af06ce9a3e` | `0840ad766e2df93f1adc118af4be0b40f0c8e4fbef02d7ddb5a43ce147e0744e` |
| `io/reactivex/internal/operators/maybe/MaybeConcatArray$ConcatMaybeObserver.class` | `b91ace43d10d70363722ba86ccfeea28c222d755edf1b4cf599f6694a52a2080` | `2f86eb611725b1d381d1d5fe70f95fd364741a3d81c5e8ecb931e836728f1dfb` |
| `io/reactivex/internal/operators/maybe/MaybeConcatArrayDelayError$ConcatMaybeObserver.class` | `fd1867c5ae696a96baf6005e58cd4b0c3934d00a4948502087eebdf7146af016` | `d2a4c1e1365e31a1d6051bd8197d363585ac5bfed5bedcb23e1afbc34c787a11` |
| `io/reactivex/internal/operators/maybe/MaybeConcatIterable$ConcatMaybeObserver.class` | `ade022af70467d48ef29be5e3508ebdc3c4cc6734305e3be1c253cd226eec6c2` | `5cad9fd1643ceab4f5b1bc650081ae579797666cddfba6075f719942a2f27d7c` |

The outer classes are identical on both sides: `MaybeConcatArray.class` `308b49fa67515aa2936b1b81111ccc42f15a3c1487456468954c3cdf7fe29404`,
`MaybeConcatArrayDelayError.class` `b638bb018e1657d06c21f7e2057e462d521ce44db13acf4871379afc4fab636a`, `MaybeConcatIterable.class` `1c7556cf1a6e5adaa4cafdda595e53ba110f8742c4feafdec9a8771c4217f5dc`.

**Release side** (`$O/releases/rxjava-2.0.{6,7}/`, checked against Central's hashes): **an exact published pair for the three changed files.**
`rxjava-2.0.6-sources.jar`'s three files are byte-equal to the **parent**'s, `rxjava-2.0.7-sources.jar`'s to the **fix**'s (git blob ids equal; `$O/scripts/relcmp_D.sh`).
`rxjava-2.0.6.jar` `39799db09efc9545863b5fa7624c8ca932d8736d76df5e05707e5e7854ce52c6`, `rxjava-2.0.7.jar` `99d480d623030e32d8ea3c20caf1cbc9e8f28bb9705ee69a034dddba36515d2a`
(each needs `reactive-streams-1.0.0.jar` beside it). The releases differ from the pins in other files.

### R42 · reactor-core #937 — concatDelayError keeps going past a callable inner error (pinned Gradle 4.2.1 build cannot be configured; slice route)

**Pins.** Parent `0ad7976bf1c02bccc28bb478758591bc8108b11a`, fix `af0cb628ece3c0a543512ea9913c4ff72ba18566` (one commit on `master`, one parent = the brief's;
the PR's 2 commits landed as one). Changed production files (`reactor-core/src/main/java/reactor/core/publisher/`): `Flux.java` (+8 −6, **Javadoc only**),
`FluxConcatMap.java` (+8 −3: with `veryEnd`, a callable inner source's error is added to `ERROR` and the loop continues), `FluxFlatMap.java` (+3 −1).
Tests (`reactor-core/src/test/java/reactor/core/publisher/`): `FluxConcatArrayTest` (+26), `FluxConcatMapTest` (+52), `FluxFlatMapTest` (+27),
`FluxMergeSequentialTest` (+56), `FluxMergeTest` (+25), `ParallelConcatMapTest` (+31). Version `3.1.2.BUILD-SNAPSHOT`.

**The pinned build cannot be configured from public sources.** Gradle 4.2.1 (`$O/tools/gradle-4.2.1`; the pins' wrapper jar is 4.2's) on JDK 8,
at both pins (`$O/logs/R42-{parent,fix}.help-online.log`): the build script's only repository is `http://repo.spring.io/plugins-release`, which
answers 405 over http and 401 over https, and three of its build-script modules are nowhere else: `org.springframework.build.gradle:propdeps-plugin:0.0.7`,
`io.spring.gradle:spring-io-plugin:0.0.4.RELEASE` and `org.jetbrains.dokka:integration:0.9.15` (looked for at Central, the Plugin Portal, repo.grails.org
core and plugins, JFrog's jcenter mirror (401), Atlassian, JBoss, Red Hat, Jenkins, repo.gradle.org: 404; the Q01–Q30 and P01–P30 setups found
`propdeps-plugin:0.0.7` and dokka `integration:0.9.15` nowhere either). Nothing was substituted and no upstream file changed.

**Slice route** (the user's standing decision of 2026-11-26; `$O/scripts/slice_D.sh`, configuration `$O/scripts/slice-R42.conf`, results `$O/slices/R42-RUN/`,
`junit.log` with every test and `reports/` JUnit XML):
1. **Which release matches which pin** (git blob ids of the files in Central's `-sources.jar`, `$O/scripts/relcmp_D.sh`): `FluxConcatMap.java` and
   `FluxFlatMap.java` of **3.1.0.RELEASE and 3.1.1.RELEASE are byte-equal to the parent's**, those of **3.1.2.RELEASE to the fix's**. `Flux.java`
   matches no release exactly (Javadoc-only change; 3.1.2.RELEASE has all 8 added Javadoc lines).
2. **Slice.** Each pin's `FluxConcatMap.java` and `FluxFlatMap.java` compiled by `javac` 1.8.0_512 (`-source 8 -target 8 -parameters -proc:none -implicit:none`)
   against the base release **reactor-core 3.1.1.RELEASE** (+ reactive-streams 1.0.1) into `$O/slices/R42-slice-ROLE/main/`, jarred as `slice.jar`,
   class digests in `main.SHA256SUMS`; the pin's three changed production files are copied beside it in `src/`. `Flux.java` was not compiled (Javadoc only).
   Slice jars: parent `3609eb52befef5d097252e7447532ab6f73118277eee942d98fad5438d8d19f2`, fix `dbd201aadf0170b74349f14e22caf3f04a4c89a8930508ab070c0fd4390796bf`.
   The slice classes differ in bytes from the releases' (those were compiled by 1.8.0_144), source-equal as above.
3. **Tests.** The six landed test classes compiled from the chosen pin's own test tree (`-sourcepath`, so helpers such as `FluxOperatorTest` come from
   that pin), with the test libraries the pins' `build.gradle` declares (JUnit 4.12, hamcrest 1.3, TestNG 6.8.5, AssertJ 3.8.0, Mockito 2.10.0, reactive-streams-tck 1.0.1,
   logback 1.1.2, slf4j-api 1.7.12, jsr305 3.0.2, kotlin-stdlib 1.1.51) and **reactor-test 3.1.1.RELEASE** (the pins' own `reactor-test` project cannot be built either),
   resolved by `$O/releases/tests-R42/pom.xml` into `$O/m2` (24 jars, each equal to its downloaded `.sha1`, `$O/scripts/verify_cp_D.sh`), run on JDK 8 with the
   JUnit Platform console launcher 1.10.2 (vintage engine). Classpath: slice, test classes, test resources, base release, test libraries.

| Run | Slice | Tests from | Result |
|---|---|---|---|
| `fix` | fix | fix | 226/226 pass |
| `parent` | parent | parent | 210/210 pass |
| `transplant` | parent | fix | **10 of 226 fail** |
| `release-3.1.1` | none (3.1.1.RELEASE alone) | fix | **the same 10 fail** |
| `release-3.1.2` | none (3.1.2.RELEASE alone) | fix | 226/226 pass |

The ten (`$O/logs/R42-slice-failures.txt`), each `java.lang.AssertionError: expectation "expectNext(3)" failed (expected: onNext(3); actual: onError(java.lang.Exception: test))`:
`FluxConcatMapTest#concatDelayErrorWithFluxError`, `#concatDelayErrorWithMonoError`, `#concatMapDelayErrorWithFluxError`, `#concatMapDelayErrorWithMonoError`;
`FluxFlatMapTest#delayErrorWithFluxError`, `#delayErrorWithMonoError`; `FluxMergeTest#delayErrorWithFluxError`, `#delayErrorWithMonoError`;
`ParallelConcatMapTest#concatDelayErrorWithFluxError`, `#concatDelayErrorWithMonoError`. The new `FluxConcatArrayTest` and `FluxMergeSequentialTest` tests pass on the parent slice.

**Release jars** (`$O/releases/`, each checked against Central's `.sha1` and, where published, `.sha256`/`.sha512`):

| Release | `reactor-core` sha256 | `reactor-test` sha256 | Side for the code files |
|---|---|---|---|
| 3.1.0.RELEASE (named by the brief, issue #936) | `80e30d4e25f052ef45ff6120897dbda6406de2791e37bce51602d56286e9789a` | `59c8e144a9bc6684596d15818a0094492e63defd5ce052d42c3ce3871c77ccc6` | parent |
| 3.1.1.RELEASE (slice base) | `17e06176a410d876a532830c9c5d9beca020b5b8f77f86e5af275a56c20f689d` | `ccecb6fb350c30b63b40f9fb48dec8d6798b764b489065e1fd20874a54e329b7` | parent |
| 3.1.2.RELEASE | `2412ae7a74bef85faff78aa83e0b1f1205517890e21630650cb080c51bfb8b18` | `e9da6c94149ccac634a8cb51f1daff5c66dc01561fae78d7e615885537c7432f` | fix |

Each runs with `reactive-streams-1.0.1.jar` (in `$O/m2`). **Evidence label:** every R42 result above is from the slice route or the release jars, not
from the pinned build.

### R43 · reactor-core #3783 (3.4.x) — thenMany discards every concatenated value (upstream Gradle 8.6 build at both pins, inline)

**Pins.** Parent `92c8ea05eaa4e009fe5459bd4a1fe51b244bcc52`, fix `2a664dd587e74793fb473d81e8b26a199ff07d1e` (squash on `3.4.x`, one parent = the brief's).
Changed: `reactor-core/src/main/java/reactor/core/publisher/Flux.java` (+1 −7: `thenMany` no longer special-cases `FluxConcatArray`),
`reactor-core/src/main/java/reactor/core/publisher/FluxConcatArray.java` (+1 −23); tests `reactor-core/src/test/java/reactor/core/publisher/FluxThenManyTest.java`
(+13 −3: new `testThenManyOnConcatArray`), `…/MonoThenManyTest.java` (+4 −3). `$O/scripts/R43-tests.txt` holds the two `--tests` filters.

**Build facts.** Gradle 8.6 (`$O/tools/gradle-8.6`; wrapper jar = 8.6's published one) on **JDK 8** (`$J8`; the 3.4.x build compiles with the JDK it runs on
and targets 8; `NOTC=1`). Version `3.4.38-SNAPSHOT`. Not a multi-release jar at this line. Runtime dependency `org.reactivestreams:reactive-streams:1.0.4`
(`f75ca597789b3dac58f61857b9ac2e1034a68fa672db35055a8fb4509e325f28`). Tests: JUnit Jupiter 5.10.2, AssertJ 3.25.3, Mockito 4.11.0, the project's `reactor-test`
(26 entries in `reactor-core.testRuntimeClasspath.txt`). Central and the Plugin Portal only; no substitution (the init script is not needed).

**Commands** (`NOTC=1 $O/scripts/gradle_case_D.sh DIR TAG 8.6 $J8 reactor-core/build/test-results/test ARGS`):
- online (76 s at the fix, 35 s at the parent): `ONLINE=1 … :reactor-core:jar :reactor-core:test $(cat $O/scripts/R43-tests.txt)`
- **offline (checked, 9 s at the fix)**: the same without `ONLINE=1`
- classpaths: `$O/scripts/cp_D.sh R43 ROLE 8.6 $J8 :reactor-core`

**Landed tests** (JDK 8u512):

| Run | Result |
|---|---|
| fix, `FluxThenManyTest` + `MonoThenManyTest` (online, then offline) | 7/7 pass |
| parent, its own copies (online, then offline) | 6/6 pass |
| the fix's two test files on a copy of the parent (offline) | **3 of 7 fail** (`$O/logs/R43-parent-landed.failures.txt`) |

- `FluxThenManyTest#testThenManyOnConcatArray()`: `expectation "expectNext(c)" failed (expected value: c; actual value: a)`
- `FluxThenManyTest#testThenManyRepeated()`: `Expected size: 2 but was: 3 in: [MonoIgnoreElements, MonoIgnorePublisher, FluxArray]`
- `MonoThenManyTest#testThenManyRepeated()`: `Expected size: 2 but was: 3 in: [MonoIgnoreElement, MonoIgnorePublisher, FluxArray]` (the assembly-shape assertions the brief calls internal)

**Artifacts** (`$O/artifacts/R43-{parent,fix}/`: `reactor-core-3.4.38-SNAPSHOT.jar`, `SHA256SUMS` (8 classes of the two files), `reactor-core.{runtime,testRuntime}Classpath.txt`):

| File | parent sha256 | fix sha256 |
|---|---|---|
| `reactor-core-3.4.38-SNAPSHOT.jar` | `899a1d6e6baf9e355421c0a78c39feba3efb33472df175c6a0f4f30bece596e9` | `c38f456be7f5b93143ad4cf5d731f0a77c964450449dc4d5e5ed1ffb5135643b` |
| `reactor/core/publisher/Flux.class` | `3c8b28e9b0327e7587e056b3ffab7ba69c222212e6599cde8c388be94cee5b4f` | `b9013107eb7581bd5806f5601e506e98d8f8d2049808d907cb4371ddb559f9d2` |
| `reactor/core/publisher/Flux$2.class` | `a298d38245ce5702fa7bbebe65a2a4f6ce8684bc94fa341605c1ab99afe69af3` | `830fa9b89cc25f85e8e6ba49a93839c8a36d0e94295989e95f050e261b32caa0` |
| `reactor/core/publisher/Flux$3.class` | `5291692512c1d03cf69f386a4f66b45c7dce7567cdc22a176095e2e3caffe276` | `c65c5400b06f25b11afdc144f1a422bb741a0190a93e26adaedf9c33809b1bc3` |
| `reactor/core/publisher/FluxConcatArray.class` | `ca2072cbcbd2148b19a1b9814d5b1cca00096eabd357e6edccc838dee193a564` | `4ad69de70078c909fafd34585f34d0c32a5311925318985a9f6198f4e9abde15` |
| `reactor/core/publisher/FluxConcatArray$ConcatArraySubscriber.class` | `0167dccee5d733be53d57a5dd7aeb6b5fbd043ba870df1664080e927457d4ed1` | `c03affe42158df4823d43f86c32dbcc68853953679dc9078288b68ca93277c08` |
| `reactor/core/publisher/FluxConcatArray$ConcatArrayDelayErrorSubscriber.class` | `5387c2a7af9ac27f26c1986273ce07fe8d716da3e66e81846739f3780536893c` | `29bd8e3e4b9dc84c6475b96dddd5c905bee39ac0895a31835890509bb6e0529a` |

**Release side** (`$O/releases/reactor-core-3.4.3{7,8}/`, checked against Central's hashes): **an exact published pair.** Both changed files of
`reactor-core-3.4.37-sources.jar` are byte-equal to the **parent**'s, those of `3.4.38` to the **fix**'s (git blob ids). `reactor-core-3.4.37.jar`
`3b972076cd9466395d944a00ebdfdea1b77cc7e0d48b02d044c61d4cee257988`, `reactor-core-3.4.38.jar` `a9255f60d92e8fc58c3c87320cc439936e08227db65bd88eb97e844af853e608`
(each with `reactive-streams-1.0.4.jar`; `reactor-test` of the same version for `StepVerifier`, not downloaded).

### R44 · RxJava #6664 (3.x) — new groups expose their first value or the value selector's error (upstream Gradle 5.6 build at both pins, inline; three jcenter-only build-script modules substituted)

**Pins.** Parent `c2dc134221ad6bd623f6160ec5338ad4496c5112`, fix `cb7ff83a2444731dd7eca4760e9410a6c2980b6d` (squash on `3.x`, one parent = the brief's).
Changed: `src/main/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy.java` (+4: offer and drain a new group before the value
selector's failure), `src/main/java/io/reactivex/rxjava3/internal/operators/observable/ObservableGroupBy.java` (+14 −6); tests
`src/test/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupByTest.java` and `…/observable/ObservableGroupByTest.java` (+57 each: `newGroupValueSelectorFails`,
`existingGroupValueSelectorFails`). `$O/scripts/R44-tests.txt` holds the two `--tests` filters.

**Build facts.** Gradle 5.6 (`$O/tools/gradle-5.6`; the pins' wrapper jar is 4.3.1's) on **JDK 8** (`$J8`), `CI=true`, `NOTC=1`. Linked worktrees work.
Version `3.0.0-SNAPSHOT` (`rxjava-3.0.0-SNAPSHOT.jar`), source/target 1.8. Runtime dependency `org.reactivestreams:reactive-streams:1.0.3` only
(`1dee0481072d19c929b623e155e14d2f6085dc011529a0a0dbefc84cf571d865`). Tests: JUnit 4.12, Mockito 3.0.0, TestNG 7.0.0, Guava 28.0-jre.

**Substitution (build-script classpath only).** Build-script repositories `jcenter()`, Central, the Plugin Portal. `build-info-extractor-gradle:4.5.2`
(on Central) needs `org.jfrog.buildinfo:build-info-extractor`, `-client` and `-api` **2.8.2**, which only jcenter served (Central, the Portal and
repo.grails.org: 404). They were copied with the same coordinates from JFrog's public jcenter mirror `https://releases.jfrog.io/artifactory/jcenter` into
`$O/dl/subst-repo-D` (`$O/logs/D-subst-repo.txt`): each pom and jar equals that mirror's `.sha1` **and** the `.sha1` of `releases.jfrog.io/artifactory/oss-release-local`,
and the jar SHA-1s equal the ones an earlier setup recorded for the same modules (M13): extractor `81999cbb9550b22bab79672c3d3b4bb1da98fa81`,
client `cf64685e65904b39c28ac31554bcc63471f43aad`, api `09ade14380d2e088250c4bca8fe4a5d3cb3753f0`. Same init script (`GINIT=$O/scripts/subst-repo-D.init.gradle`).

**Commands** (`CI=true NOTC=1 GINIT=$O/scripts/subst-repo-D.init.gradle $O/scripts/gradle_case_D.sh DIR TAG 5.6 $J8 build/test-results/test ARGS`):
- online at the fix (25 s once the substitutes were in): `ONLINE=1 … jar test $(cat $O/scripts/R44-tests.txt)`
- **offline (checked, 17 s at the fix, 25 s at the parent)**: the same without `ONLINE=1`
- classpaths: `GINIT=… $O/scripts/cp_D.sh R44 ROLE 5.6 $J8 ""` (files `root.*Classpath.txt`)

**Landed tests** (JDK 8u512):

| Run | Result |
|---|---|
| fix, `FlowableGroupByTest` + `ObservableGroupByTest` (online, then offline) | 104 run, 0 failures, 2 skipped |
| parent, its own copies (offline) | 100 run, 0 failures, 2 skipped |
| the fix's two test files on a copy of the parent (offline) | **1 of 104 fails** (`$O/logs/R44-parent-landed.failures.txt`): `FlowableGroupByTest#newGroupValueSelectorFails`: `java.lang.AssertionError: Value counts differ; expected: 1 but was: 0 (latch = 0, values = 0, errors = 1, completions = 0)` |

The Observable tests and `existingGroupValueSelectorFails` pass on the parent: the landed tests do not separate the Observable change (first item
queued before an unclaimed group can finish) from the parent. The brief's delayed-subscription Observable scenario is not among them.

**Artifacts** (`$O/artifacts/R44-{parent,fix}/`: jar, `SHA256SUMS` (all 9 classes of the two files), `root.runtimeClasspath.txt`, `root.testRuntimeClasspath.txt`):
- `rxjava-3.0.0-SNAPSHOT.jar` parent `2d900e4fd44059bcd9524ea6371d8507749dda9c5ea10f6f3e2a2812498616bf`, fix `3574c3c2541e23f08d530abaebd2ef5a68c239346cdd09c802ead785d323324c`

| Class | parent sha256 | fix sha256 |
|---|---|---|
| `io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy$EvictionAction.class` | `69a346688ff0fdbf2d27c960e3dae7f2152a83c5e464f7d7c9c94841e56e7fb4` | `bab14cbfe2a56fc4ef9387aff1d700895284e18c55dd9d8ec6c6f1449cce9efc` |
| `io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy$GroupBySubscriber.class` | `31e62cb7e7ebbd169990800e0c101d2bad44f67e41f4021c12a83ef59cf93a0d` | `ab93f0eb329d2577faafef987d604ed9ee82a97e4d5d80fef0435bf87d425a49` |
| `io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy$GroupedUnicast.class` | `92ec8cf3ee6c9e0c366e30f3e146cc0f3329bc1af013d50afe4f514ff5f1d527` | `4959a7c65dd0a0eb474e16c1d4e3a89a3678bc63b672000d737235ccc6be5b44` |
| `io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy$State.class` | `59ca64eeff031b4acc17c83c62b170513c505f585c9a9fb7990fac8240425434` | `7a5b59aeb35f3e4ed20692d94379da0ae2eacd5b0aed255d201e1ff683885cc7` |
| `io/reactivex/rxjava3/internal/operators/observable/ObservableGroupBy$GroupByObserver.class` | `c140fca42238becc5add6a8afee75dfde47a509628423c7bab712569fa6a440c` | `9f773c7d3ab5e59783d5f179acd4c8edd546340b0756a0040c095a2211330b73` |
| `io/reactivex/rxjava3/internal/operators/observable/ObservableGroupBy$GroupedUnicast.class` | `b210161390fefcf7ccb66b855698d156ac8442ce44c37665e567c8435d4f99d7` | `b38a6af2325cec83153adc694b4d36f46797668e96eef9894bd807c8853c5b59` |
| `io/reactivex/rxjava3/internal/operators/observable/ObservableGroupBy$State.class` | `b0a6e3bcdb74cdccff8f969b7d3c33c7bd48459fa324755b1e6911f10a661b7f` | `eab8644f227fb7a1c575977c657847b68c44a93f0ba53dd96c417659e50dedd4` |

`FlowableGroupBy.class` (`3eaed04e0e0c8dc9e6ba1c457ecbc14ecdb8873b688eb0d9391f0872e0ed9301`) and `ObservableGroupBy.class` (`f29062a7cdbc0449613d0e73a9b3e83da82fd3c77d3c3413f07a7c3e5a368d77`) are identical on both sides.

**Release side** (`$O/releases/rxjava-3.0.0-RC{3,4,5}/`, checked against Central's hashes; git blob ids of the two files):
- **3.0.0-RC3**: both files byte-equal to the **parent**'s. `rxjava-3.0.0-RC3.jar` `52b15d7639e98e33d1b42bd34b16647120479596ecf3435884307103bb63ca91`.
- **3.0.0-RC4** (first with the fix): `ObservableGroupBy.java` byte-equal to the **fix**'s; `FlowableGroupBy.java` has the fix's four added lines plus two later
  changes (`!outputFused &&` in a drain guard, one `q.clear()` removed). `rxjava-3.0.0-RC4.jar` `6e7623803eac1bff82cfef42ec8309669ffe309749004ca2af60b26e1b836ffb`.
- 3.0.0-RC5 likewise (fix's Observable file, later Flowable file): `rxjava-3.0.0-RC5.jar` `25c96e331d2bb0cb61cc873f08ef60e007922e9488cfcdeee6b94bface5d8943`.
- So RC3 is an exact parent stand-in; no release is byte-equal to the fix for `FlowableGroupBy.java`. Each needs `reactive-streams-1.0.3.jar`.

### R45 · resilience4j #2067 — asynchronous retry with a zero interval, stop on a negative one (upstream Gradle 7.4.2 build at both pins, inline; one jcenter-only plugin dependency substituted)

**Pins.** Parent `12f66a31d7b4619ed0ffd1fddee9da683c41b9b7`, fix `a1a4acb85c83dbd1b1a67cd97dac994fb8bb034c` (squash on `master`, one parent = the brief's).
Changed (all in `resilience4j-retry`): `src/main/java/io/github/resilience4j/retry/Retry.java` (+2 −2), `src/main/java/io/github/resilience4j/retry/internal/RetryImpl.java` (+21 −5),
tests `src/test/java/io/github/resilience4j/retry/internal/CallableTest.java` (+80 −3), `src/test/java/io/github/resilience4j/retry/internal/CompletionStageRetryTest.java` (+79).

**Build facts.** Gradle 7.4.2 (`$O/tools/gradle-7.4.2`; the pins' `gradle-wrapper.jar` is 4.10.3's, see the toolchain table), run on **JDK 17** (`$J17`);
the build compiles with source/target 17. Version `2.2.0-SNAPSHOT` (root `build.gradle`). `gradle.properties` sets `org.gradle.caching=true`;
the commands pass `-Dorg.gradle.caching=false`. Every core project applies `org.gradle.test-retry` with `maxRetries = 3`, so **a failing test runs
four times** and its JUnit XML holds four results. Runtime classpath of `resilience4j-retry`: `resilience4j-core` (project) and `slf4j-api:1.7.30`.
Tests: JUnit 4, AssertJ, Mockito, PowerMock, Awaitility, RxJava 2, logback, vavr (67 entries).

**Substitution (plugin classpath only).** The `org.asciidoctor.convert` 1.6.0 plugin needs `org.ysb33r.gradle:grolifant:0.10`, which only jcenter
served: Central has 0.12.1 and later, the Plugin Portal redirects to Central (404). The **same coordinates** were copied from
`https://repo.grails.org/grails/core` into the file repository `$O/dl/subst-repo-D`, pom and jar each equal to that repository's `.sha1`
(`$O/scripts/subst_add_D.sh`, log `$O/logs/D-subst-repo.txt`; no second public source serves it):
`grolifant-0.10.jar` sha1 `e2ad2b34631cd8f19f2a992984a0dc4c71bee78f`, sha256 `c13e871892b9820f27d96f5a2216e888960e5c2d4383d8ea1837d18f1c733153`;
`grolifant-0.10.pom` sha1 `3c42e5a501bccc1a0773ba508231542735522476`. `$O/scripts/subst-repo-D.init.gradle` adds the file repository to the plugin and
build-script repositories (`GINIT=$O/scripts/subst-repo-D.init.gradle`). Nothing compiled or tested uses it (documentation plugin).

**Commands** (`GINIT=$O/scripts/subst-repo-D.init.gradle $O/scripts/gradle_case_D.sh DIR TAG 7.4.2 $J17 resilience4j-retry/build/test-results/test ARGS`):
- online, first resolution at the fix (34 s): `ONLINE=1 … :resilience4j-retry:jar :resilience4j-retry:test --tests io.github.resilience4j.retry.internal.CallableTest --tests io.github.resilience4j.retry.internal.CompletionStageRetryTest`
- **offline (checked, 11 s at the fix, 16 s at the parent)**: the same without `ONLINE=1`
- classpaths: `GINIT=… $O/scripts/cp_D.sh R45 ROLE 7.4.2 $J17 :resilience4j-retry`

**Landed tests** (JDK 17.0.21; logs `$O/logs/R45-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `CallableTest` + `CompletionStageRetryTest` (online, then offline) | 16/16 pass |
| parent, its own copies (offline) | 12/12 pass |
| the fix's two test files on a copy of the parent (offline) | **3 of 16 tests fail** (each four times under test-retry: 25 results, 12 failures; `$O/logs/R45-parent-landed.failures.txt`, XML in `$O/logs/junit-xml/R45-parent-landed/`) |

- `CallableTest#shouldStopRetryingAndEmitProperEventsIfIntervalFunctionReturnsLessThanZero`: `Expecting <AtomicInteger(2)> to have value: <1> but did not.`
- `CompletionStageRetryTest#shouldContinueRetryingAndEmitProperEventsIfIntervalFunctionReturnsZeroOrMore`: `Expecting <AtomicInteger(1)> to have value: <2> but did not.`
- `CompletionStageRetryTest#shouldStopRetryingAndEmitProperEventsIfIntervalFunctionReturnsLessThanZero`: `Expecting <AtomicBoolean(false)> to have value: <true> but did not.`

**Artifacts** (`$O/artifacts/R45-{parent,fix}/`: `resilience4j-retry-2.2.0-SNAPSHOT.jar`, `resilience4j-core-2.2.0-SNAPSHOT.jar`, `SHA256SUMS`,
`resilience4j-retry.runtimeClasspath.txt`, `resilience4j-retry.testRuntimeClasspath.txt`, project entries copied under `tree/`):

| File | parent sha256 | fix sha256 |
|---|---|---|
| `resilience4j-retry-2.2.0-SNAPSHOT.jar` | `1df91159be0aff5667df17b8cf610a2204f53efd17dd9099ce84b5cae89aa361` | `6bef988d2936dcfc39fc3d7fd040df462979ea549b350219fdcde3ad90e337c1` |
| `resilience4j-core-2.2.0-SNAPSHOT.jar` (no source change; jar timestamps differ) | `a500a8fad8877eaba8dc05eb3e3cbaba3ad8ec9cdd08a1230b6d4280ca0638d4` | `85c0c0cc0361e33c0d1e19cc27acc03ace71f017e834c776f282bf070b28a8f6` |
| `io/github/resilience4j/retry/Retry$AsyncRetryBlock.class` | `7e152705f833133ecf8c80b4bcb32192eb89ecee90af27407386a0852bef9e64` | `b9ad55c2541157c1e04de547c0da14fe999b52af7f239c34f5315e343c88f0c0` |
| `io/github/resilience4j/retry/internal/RetryImpl$AsyncContextImpl.class` | `4f7ddbf3a0eabc0a8d89bdc6dc0ab54da7a8a0ca0b9ed03f43ae48cf502e53ee` | `a6cb0aecc59ece8959632e1349cbe9cdc60d31474143aaf7f1da0d4743b9e63a` |
| `io/github/resilience4j/retry/internal/RetryImpl$ContextImpl.class` | `4f9b2d8594378832e7ca970eca7025472ef5cf98d6132c370ebaa54f203be306` | `d96cd41d13f0ad83c0930fd0a92a809b238cdbf5175f3e6af03a95efe5c50447` |
| `io/github/resilience4j/retry/internal/RetryImpl$RetryEventProcessor.class` | `9868604c9817c81c289f54815f3d7c4942c33ff7f13f51b88985dcc0cfd6fb74` | `bb110ee48ab624e5f67d598bc68d54fba9fca345ad881d6b0140ff1ed125991d` |
| `io/github/resilience4j/retry/internal/RetryImpl$RetryMetrics.class` | `402174aea8bf403687d34481b220df72f4f872375927222be909772a093b9953` | `26d6e58e634ff1c025fd3a1e0137618e8951e6d763e6c174cd33ed8fe6624340` |

The other six classes of the two files are identical on both sides (`SHA256SUMS`), among them `Retry.class` `4c9dd0df7ec34fdb6fbe29ea520fef35968acea978ed4072a88ded8fd1fcf5d2` and `RetryImpl.class` `5affc68cc20a3ab1309035bdf7b7ab37eceea1f14d744de4771c3e10436d243e`.

**Release side** (`$O/releases/resilience4j-{retry,feign,core,circuitbreaker,ratelimiter,bulkhead}-{2.1.0,2.2.0}/`, jars and poms, plus retry and feign
`-sources.jar`, each equal to Central's `.sha1`/`.sha256`/`.sha512` where published):
- **2.1.0 predates the fix**: its `Retry.java` has both removed lines and neither added one; `RetryImpl.java` has all 4 removed lines. `resilience4j-retry-2.1.0.jar` `e2dd918093bc263f1d725d0c17beea31ce34cbbf56eecfb92dce82a3c479e7b5`, `resilience4j-core-2.1.0.jar` `3c279de9c066215d04b89cc8864996660a05815ab47202089726aac7f3bd96fe`.
- **2.2.0 is the first release with the fix**: all 2 + 14 added lines; neither file byte-equal to the fix's (later changes). `resilience4j-retry-2.2.0.jar` `5256badd000a3dfd74914241e7095adf96ccde955dabb9d204f1e7b60fe6bcba`, `resilience4j-core-2.2.0.jar` `6200917bb21c30134c27e3de8bc8c6e4a7760d87579a0dc4e2dc54888beab5ce`.

### R46 · resilience4j #1999 — a lambda from a Feign fallback factory is invoked (upstream Gradle 7.4.2 build at both pins, inline; same substitution as R45)

**Pins.** Parent `e328decc50954d70420359acea78491fce539d20`, fix `17dc97b1c8e472e1c295f112b8b761298cd1321a` (squash on `master`, one parent = the brief's).
Changed (all in `resilience4j-feign/src/main/java/io/github/resilience4j/feign/`): `DefaultFallbackHandler.java` (+1 −3), `FallbackFactory.java` (+1 −2),
`FallbackHandler.java` (+6); new test `resilience4j-feign/src/test/java/io/github/resilience4j/feign/Resilience4jFeignFallbackFactoryLambdaTest.java` (+68, one method
`testFallbackFactory`, using the existing `test/Issue560.java` lambda from another package and WireMock).

**Build facts.** As R45 (Gradle 7.4.2 on JDK 17, `2.2.0-SNAPSHOT`, test-retry ×4, `-Dorg.gradle.caching=false`, `GINIT=$O/scripts/subst-repo-D.init.gradle`).
`feign-core` 12.0 is `compileOnly` (on the test classpath, not the runtime one). Runtime classpath of `resilience4j-feign`: the project jars
`resilience4j-retry`, `-circuitbreaker`, `-ratelimiter`, `-bulkhead`, `-core` and `slf4j-api:1.7.30` (`$O/artifacts/R46-ROLE/resilience4j-feign.runtimeClasspath.txt`, project
jars copied under `tree/`). Tests: WireMock `wiremock-jre8` 2.26.0 (Jetty 9.4.20), feign-core 12.0 and the common test libraries (121 entries).

**Commands** (`GINIT=… $O/scripts/gradle_case_D.sh DIR TAG 7.4.2 $J17 resilience4j-feign/build/test-results/test ARGS`):
- online at the fix (28 s): `ONLINE=1 … :resilience4j-feign:jar :resilience4j-feign:test --tests io.github.resilience4j.feign.Resilience4jFeignFallbackFactoryLambdaTest`
- **offline (checked, 9 s)**: the same without `ONLINE=1`; parent (online first, 11 s): `:resilience4j-feign:jar :resilience4j-feign:testClasses`

**Landed tests** (JDK 17.0.21):

| Run | Result |
|---|---|
| fix, `Resilience4jFeignFallbackFactoryLambdaTest` (online, then offline) | 1/1 pass |
| parent | no copy (the test is new) |
| the fix's test on a copy of the parent (offline) | **1 of 1 fails** (four attempts; `$O/logs/R46-parent-landed.failures.txt`, XML in `$O/logs/junit-xml/R46-parent-landed/`): `testFallbackFactory`: `java.lang.reflect.UndeclaredThrowableException`, caused by `java.lang.IllegalAccessException: class io.github.resilience4j.feign.FallbackFactory cannot access a member of class io.github.resilience4j.feign.test.Issue560$$Lambda$194/0x… with modifiers "public"` |

**Artifacts** (`$O/artifacts/R46-{parent,fix}/`):

| File | parent sha256 | fix sha256 |
|---|---|---|
| `resilience4j-feign-2.2.0-SNAPSHOT.jar` | `d01a9ccfd9f21957c2bcc98960e74abe286762109c1b131b3b6c73f91b447368` | `06ed24b91d27693e34ecb868b0ecd0523d04dc087f028693184b3c3eed816eb5` |
| `io/github/resilience4j/feign/DefaultFallbackHandler.class` | `83a3503f7f70acab272a01ae00882d1766ab0c68a03036475fda0f7378d8675a` | `d26b35779c91f5a4f377a8dc36b434afea2f7b384011d7bc04355208e3aef767` |
| `io/github/resilience4j/feign/FallbackFactory.class` | `5a0042b8093772e3b296a5e75b1af0c0f963f7fd9cf8aecc362ef419efc14990` | `c6fd0446d1abcf112a566dee839c657a1d7e81c060d72cee04eb1de2555681f2` |
| `io/github/resilience4j/feign/FallbackHandler.class` | `2147046c923ed02ad74eecb2e99fdbf643dafef936994186b5032b6ce98209c9` | `c5b4580ea4de85032d818e642d769f261d27b312bf001e00debc0bcaa84dfd20` |

**Release side** (same downloads as R45). The brief names **Resilience4j 2.1.0** (issue #2000): it **predates the fix** (all 3 + 2 removed lines of
`DefaultFallbackHandler.java`/`FallbackFactory.java`, none of the added lines). **2.2.0 is the first release with it** (all 7 added lines; files not
byte-equal to the fix's). Jars (sha256): 2.1.0 `resilience4j-feign` `93e6d9faf7906cbaff9fc50d67e0d66c891fd73fd36eba75de3f74651bb291a0`, `-retry` `e2dd918093bc263f1d725d0c17beea31ce34cbbf56eecfb92dce82a3c479e7b5`,
`-circuitbreaker` `0e6f73a1f17b2c813acca7cc131d2c1b6a5a56f3d55047872bbe7fe2cc73c312`, `-ratelimiter` `15377bd6ffe4e5a24e35611ed921ffe4fc111380c5b2c153cdb21ff4b08e3c2b`, `-bulkhead` `17d83e1751c3b91d17e45f43ba1814707706cb2209f07b59766a4d85bfe97c68`,
`-core` `3c279de9c066215d04b89cc8864996660a05815ab47202089726aac7f3bd96fe`; 2.2.0 `resilience4j-feign` `2342c8073e962eb00f92ece37123a01a55389b3c196d6359d3a8cb228eedd3b2`, `-retry` `5256badd000a3dfd74914241e7095adf96ccde955dabb9d204f1e7b60fe6bcba`,
`-circuitbreaker` `b87b0de1051e466190a2ea35f53e5c67d9268fb4000400e07bd1cbf9f006fbf4`, `-ratelimiter` `b285699e8f45e83bd1dec985ee7646086fcd0234871f4cf4fa5d2487a585601d`, `-bulkhead` `5211f86fdeff5aff8ef9f3f6491e101a992f215671c80404e9900b4242061394`,
`-core` `6200917bb21c30134c27e3de8bc8c6e4a7760d87579a0dc4e2dc54888beab5ce`. A release run also needs `feign-core` (12.0 is what the pins test with; in `$O/gradle-home`) and `slf4j-api`.

### R47 · picocli #2036 — inherited map options keep mapFallbackValue (upstream Gradle 7.6 build at both pins, inline)

**Pins.** Parent `7c7c8b954277b6e18c57ff5ea1791b59569c0511`, fix `5984589f57bcf2bb716e3dee21025ddaa387c3da` (squash on `main`, one parent = the brief's).
Changed: `src/main/java/picocli/CommandLine.java` (+1: `mapFallbackValue = original.mapFallbackValue;` in the copy of an `ArgSpec` builder),
`src/test/java/picocli/MapOptionsTest.java` (+53: `testInheritedOptionMapFallbackValueEmptyString`, `testInheritedOptionMapFallbackValueNull`,
`testInheritedPositionalMapFallbackValueNull`).

**Build facts.** Gradle 7.6 (`$O/tools/gradle-7.6`, the wrapper's version; the pins' `gradle-wrapper.jar` is 7.4.x's, see the toolchain table),
run on **JDK 11** (`$J11`). Version `4.7.4-SNAPSHOT` (from `dependencies.gradle`), so the jar is `picocli-4.7.4-SNAPSHOT.jar`; on JDK 9+ the build
sets source/target 1.8 (class files major 52). **No runtime dependencies.** Tests: JUnit 4, hamcrest, system-rules, JUnitParams, groovy, jansi
(`testRuntimeClasspath.txt`, 7 entries). Repositories `repo.spring.io/libs-snapshot` and Central; everything resolved from Central, no substitution.
The root project only; the subprojects (`picocli-codegen`, …) were not built.

**Commands** (`$O/scripts/gradle_case_D.sh DIR TAG 7.6 $J11 build/test-results/test ARGS`; offline unless `ONLINE=1`):
- in `$W/R47-picocli-fix` online, first resolution (36 s): `ONLINE=1 … :jar :test --tests picocli.MapOptionsTest`
- **offline (checked, 8 s at the fix, 13 s at the parent)**: `… :jar :test --tests picocli.MapOptionsTest`
- classpaths: `GINIT=$O/scripts/resolve-all.init.gradle … :setupWriteClasspath -PsetupCpConf=testRuntimeClasspath -PsetupCpOut=FILE`

**Landed tests** (JDK 11.0.33; logs `$O/logs/R47-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `MapOptionsTest` (online, then offline) | 13/13 pass |
| parent, its own `MapOptionsTest` (offline) | 10/10 pass |
| the fix's `MapOptionsTest` on a copy of the parent (`$O/scripts/overlay_D.sh R47`, offline) | **3 of 13 fail**, exactly the three new tests (`$O/logs/R47-parent-landed.failures.txt`, XML in `$O/logs/junit-xml/R47-parent-landed/`) |

- `testInheritedOptionMapFallbackValueEmptyString`: `CommandLine$ParameterException: Value for option option '-D' (<String=String>) should be in KEY=VALUE format but was key`
- `testInheritedOptionMapFallbackValueNull`: the same `ParameterException` message
- `testInheritedPositionalMapFallbackValueNull`: `CommandLine$UnmatchedArgumentException: Unmatched argument at index 1: 'key'`

**Artifacts** (`$O/artifacts/R47-{parent,fix}/`: jar, `SHA256SUMS` with the jar and all 216 `picocli/CommandLine*.class` entries, `runtimeClasspath.txt` (empty), `testRuntimeClasspath.txt`):
- `R47-parent/picocli-4.7.4-SNAPSHOT.jar` `01363c5c77b15ca1b5c0fa47962c996727e5352981de694d328ad5fed96e7137`
- `R47-fix/picocli-4.7.4-SNAPSHOT.jar` `d73b56e5e55c024cc8811b913dccf5d35e9976964352713194acf2f05d1b1430`
- 126 of the 216 `CommandLine*` classes differ between the sides (line-number tables shift; `python3 -I $O/scripts/classdiff_D.py R47 all` lists them); `picocli/CommandLine.class` parent `a4580b58f7cbfaf56ef8b1b27a179bee23121b373d43e51744ce6916ba0a56da`, fix `ebb8b6b773d99fe154f32df9bcaa9c96b87e1ad9d62275b0bed721b8be3dfdf2`.

**Release side** (`$O/releases/picocli-4.7.{3,4}/`, jar, pom and `-sources.jar`, each checked against Central's `.sha1`, `.sha256`, `.sha512`; `$O/scripts/linecmp_D.py`):
- **4.7.3 predates the fix**: its `CommandLine.java` lacks the added line. `picocli-4.7.3.jar` `6442745031a59fdd0d9841a3f2332a03f7aa37735536dad206ee4fac8800ab93`.
- **4.7.4 is the first release with the fix**: it has the added line; not byte-equal to the fix's file (later commits). `picocli-4.7.4.jar` `1964e89575b43aa177aa4e534946b25bde9f3a48a9675d61d9ef7c4ca83d94b4`.
- Signatures: see [Signatures (fork D)](#signatures-fork-d).

### R49 · JUnit #5839 — the suite engine counts dynamically registered tests (upstream Gradle 9.6.1 build; jars and landed tests by job `20261126-172339-setup-build-junit-at-both-pins-of-5839-a`)

**Pins.** Parent `f8686f1e6482e41bd40548fd08c5340f414b968f`, fix `7e7183fe2989400b98c8ef06981ab0ae3e62d6d8` (squash on `main`, one parent = the brief's).
Changed production file: `junit-platform-suite-engine/src/main/java/org/junit/platform/suite/engine/SuiteTestDescriptor.java` (+7: `dynamicTestRegistered` increments
`testsFound` for a test identifier). Tests (`platform-tests/src/test/java/org/junit/platform/suite/engine/`): `SuiteEngineTests.java` (+60 −44),
`BeforeAndAfterSuiteTests.java` (+5 −5), new helper `SuiteEventConditions.java` (+36); release notes `release-notes-6.1.2.adoc`.

**Checkouts.** `$W/R49-junit-framework-{parent,fix}` are **standalone depth-1 clones** (`$O/scripts/standalone_D.sh`; JUnit's build reads git metadata, as
earlier setups found); trees parent `3f3db360bb7a3196e91a76becb76bc5f07c3ee1d`, fix `e3e59aae84a9335ddd93b571dba4e24511f40e58`, as in the revisions table.

**Build facts.** Gradle 9.6.1 (`$O/tools/gradle-9.6.1`; zip sha256 = the wrapper's `distributionSha256Sum`; wrapper jar = 9.6.1's published one) on **JDK 25**,
default toolchain 25, `org.gradle.java.installations.fromEnv=GRAALVM_HOME,JDK17,JDK21,JDK24,JDK25` given `JDK17=$J17 JDK21=$J21 JDK25=$J25` and `JDK24` = the earlier
setup's checked Temurin 24.0.2+12 (`~/.cache/in-the-loop/merged-pr-links/tools/jdk-24.0.2+12`, tarball sha256 `aea1cc55e51cf651c85f2f00ad021603fe269c4bb6493fa97a321ad770c9b096` = Adoptium's, per
that setup's record); no GraalVM. Version `6.2.0-SNAPSHOT`. `$O/scripts/junit_gradle_D.sh R49 DIR TAG RESULTDIR ARGS` adds `--no-build-cache --no-scan
-Pkotlin.compiler.execution.strategy=in-process -Ptesting.retries=0 -Pjunit.develocity.predictiveTestSelection.enabled=false`, toolchain auto-detect/download off.
**Online resolution inline** (`$O/logs/R49-{fix,parent}.resolve-online.log`, 149 s and 40 s): `setupResolveAll -PsetupResolve=ALL` in every project, 459 configurations;
only `:nmcpAggregation` (the publishing aggregate of the project's own modules) cannot resolve, and nothing needs it. Offline task graph checked with `-m` (29 s). No substitution.

**Commands** (`$O/scripts/junit_job.sh R49 fix|parent|landed|clean`): `:junit-platform-suite-engine:jar :junit-platform-suite-api:jar :junit-platform-launcher:jar
:junit-platform-engine:jar :junit-platform-commons:jar :junit-jupiter-api:jar :junit-jupiter-engine:jar :junit-jupiter-params:jar :platform-tests:test
--tests org.junit.platform.suite.engine.SuiteEngineTests --tests org.junit.platform.suite.engine.BeforeAndAfterSuiteTests` offline.

**Landed tests and artifacts:** produced by job `20261126-172339-setup-build-junit-at-both-pins-of-5839-a` (steps 1–4), into `$O/logs/R49-*.test-offline.*` and `$O/artifacts/R49-{parent,fix}/` (module jars,
`SHA256SUMS`, `junit-platform-suite-engine.runtimeClasspath.txt`, `platform-tests.testRuntimeClasspath.txt`).
<!-- R49-job -->

**Release side** (`$O/releases/junit-platform-suite-engine-{6.1.1,6.1.2,6.2.0-M1}/` with `-sources.jar`; full runtime sets `$O/releases/junit-set-{6.1.1,6.1.2}/classpath.txt`,
13 jars each — platform suite/suite-api/suite-engine/launcher/engine/commons, jupiter/-api/-params/-engine, opentest4j 1.3.0, apiguardian 1.1.2, jspecify 1.0.0 —
resolved from Central into `$O/m2`, each jar equal to its `.sha1`):
- **6.1.1 (named by the brief, issue #5837) predates the fix; 6.1.2 has it, and the two differ in `SuiteTestDescriptor.java` by exactly the fix's 7 added lines**
  (the 6.1.x maintenance line; neither is byte-equal to a pin, whose `main` file has 44 more lines of 6.2 work). 6.2.0-M1 also has the fix.
- `junit-platform-suite-engine-6.1.1.jar` `cc8e80d44a13e8734d1ef85bf87a7f8dc3182b24d772a001851f3c5be8f67c60`, `-6.1.2.jar` `2f478dfd1ccda57c576c761d07d5417f9048d5d97ae27d334ebdc76caaebcfda`.

### R50 · JUnit #4466 — @TempDir ON_SUCCESS cleanup follows the owning test (upstream Gradle 8.13 build; jars and landed tests by job `20261126-172339-setup-build-junit-at-both-pins-of-5839-a`)

**Pins.** Parent `96d0c6dae456021a664a2283ab30fca28c4fbae2`, fix `48276fd094821f79afb3cd384b8c70946d73350b`; the range is two commits, as the brief says: middle
`f7f1d51d4c57322dece17011a3da540b0f98bfbb` ("Add 5.12.2 release notes from template", documentation only), then the fix ("Fix handling of `CleanupMode.ON_SUCCESS`").
Changed production file: `junit-jupiter-engine/src/main/java/org/junit/jupiter/engine/extension/TempDirectory.java` (+16 −7); test
`jupiter-tests/src/test/java/org/junit/jupiter/engine/extension/TempDirectoryCleanupTests.java` (+52 −10); release notes (`index.adoc`, new `release-notes-5.12.2.adoc`).

**Checkouts.** Standalone depth-1 clones `$W/R50-junit-framework-{parent,fix}`; trees parent `b827fdc509a4d96b324056817ed074bee00f346f`, fix `03a9443a67a71603209d8366316e67baac331c57`.

**Build facts.** Gradle 8.13 (`$O/tools/gradle-8.13`; zip sha256 = the wrapper's `distributionSha256Sum`; wrapper jar = 8.13's) on **JDK 21**, default toolchain 21,
`fromEnv=JDK8,JDK18,…,JDK24` (given `JDK8`, `JDK21`, `JDK24`). Version `5.13.0-SNAPSHOT` (platform `1.13.0-SNAPSHOT`). **This build's `junitbuild.build-parameters`
plugin rejects any unknown `-P` property** (`Unknown build parameter: …`), so for R50 the Kotlin strategy is `-Dkotlin.compiler.execution.strategy=in-process` and the setup's
init-script parameters are system properties (`$O/scripts/resolve-all-D.init.gradle`, `-DsetupResolve=ALL`, `-DsetupCpConf`, `-DsetupCpOut`). `gradle.properties` sets
`org.gradle.warning.mode=fail`; the init script's resolution trips it at the end (the resolution itself completed, 501 configurations, none failed), so the classpath export passes
`--warning-mode=summary`. Online resolution inline: `$O/logs/R50-{fix,parent}.resolve-online.log`. Offline task graph checked with `-m` (29 s). No substitution.

**Commands** (`$O/scripts/junit_job.sh R50 fix|parent|landed|clean`): `:junit-jupiter-engine:jar :junit-jupiter-api:jar :junit-jupiter-params:jar :junit-platform-launcher:jar
:junit-platform-engine:jar :junit-platform-commons:jar :jupiter-tests:test --tests org.junit.jupiter.engine.extension.TempDirectoryCleanupTests` offline.

**Landed tests and artifacts:** produced by job `20261126-172339-setup-build-junit-at-both-pins-of-5839-a` (steps 5–8), into `$O/logs/R50-*.test-offline.*` and `$O/artifacts/R50-{parent,fix}/`
(`junit-jupiter-engine.runtimeClasspath.txt`, `jupiter-tests.testRuntimeClasspath.txt`).
<!-- R50-job -->

**Release side** (`$O/releases/junit-jupiter-engine-{5.12.1,5.12.2,5.13.0}/` with `-sources.jar`; runtime sets `$O/releases/junit-set-{5.12.1,5.12.2}/classpath.txt`, 13 jars each, platform 1.12.x):
**an exact published pair**: `TempDirectory.java` of **5.12.1 = the parent's**, of **5.12.2 (named by the brief) = the fix's** (git blob ids). 5.13.0 has the fix plus later changes (30 lines).
`junit-jupiter-engine-5.12.1.jar` `0e7f2dbeb91bfaeb0d4cb33a487351baf0e5a6ed72906154d8fd9975d329c592`, `-5.12.2.jar` `f576c06b8accde9985063b8bc80526cb980eec24dee0b7221fc8ddd7ace65800`.

### Signatures (fork D)

Every `.asc` of fork D's release downloads (100 files: jar, pom and `-sources.jar` of each release folder in `$O/notes/D-releases.tsv`) was verified with the
keyring `$O/gnupg-D` (`$O/scripts/sigs_D.sh`, results `$O/logs/D-signatures.tsv`, exported keys `$O/keys-D/`); missing keys were fetched by the signature's issuer
from keyserver.ubuntu.com, keys.openpgp.org or pgp.mit.edu (the last served the ReactiveX and old Spring keys). Its daemons were stopped
(`gpgconf --homedir $O/gnupg-D --kill all`). **All 100 verify**:

| Releases | Signer key (fingerprint) | Files | Note |
|---|---|---|---|
| picocli 4.7.3, 4.7.4 | `AA417737BD805456DB3CBDDE6601E5C08DCCBB96` Popma Remko | 6 | good |
| moshi 1.12.0, 1.13.0 | `A6D6C97108B8585F91B158748671A8DF71296252` Jesse Wilson | 6 | good |
| reactor-core / reactor-test 3.1.0–3.1.2.RELEASE | `E2ACB037933CDEAAB7BF77D49A2C7A98E457C53D` Spring Buildmaster | 15 | good |
| reactor-core 3.4.37, 3.4.38 | `48B086A7D843CFA258E83286928FBF39003C0425` Spring Builds (JAR Signing) | 6 | good |
| calcite-core, calcite-testkit 1.42.0 | `04749577FD934674B9CD45C5D77C3383F1927570` Stamatis Zampetakis | 6 | good |
| junit-platform-suite-engine 6.1.1, 6.1.2, 6.2.0-M1; junit-jupiter-engine 5.12.1, 5.12.2, 5.13.0 | `FF6E2C001948C5F2F38B0CC385911F425EC61B51` Marc Philipp | 18 | good |
| rxjava 2.0.6, 2.0.7, 3.0.0-RC3, RC4, RC5 | `1D9AA7F9E1E2824728B8CD1794B291AEF984A085` ReactiveX Admin | 15 | good signature, key expired 2018-08-19 (signatures made 2017 and 2019) |
| resilience4j-{retry,feign,core,circuitbreaker,ratelimiter,bulkhead} 2.1.0, 2.2.0 | `94FAC9D5B165E80F1F2D9A103FFA7DB1EC0FF1A2` Robert Winkler | 28 | good signature, but the keyserver copy of the key **expired 2023-05-21, before the signatures were made** (2023-06-29, 2023-12-17) |

The JUnit runtime sets and the R42 test libraries resolved through Maven into `$O/m2` were checked against Central's `.sha1` only (`$O/scripts/verify_cp_D.sh`).


