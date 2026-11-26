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

