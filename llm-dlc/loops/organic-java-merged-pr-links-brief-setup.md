# Setup for the merged Java pull requests brief

Mechanical setup for [`organic-java-merged-pr-links-brief.md`](organic-java-merged-pr-links-brief.md), done on
2026-11-25 by a setup session (Claude Opus 5.5) and forks of it, before the domain work starts. The session writes
no claims, examples, sidecars, adapters or checker code, allocates no example ids, and runs neither the project
verifier nor JBMC. Everything fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/merged-pr-links`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR`, `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin, under `~/.sdkman/candidates/java/`) and `$MVN`
(Maven 3.10.0 with `-s $O/maven-settings.xml -t $O/toolchains.xml`, local repository `$O/m2`).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `M01`–`M20` follow the brief's order. They are this record's labels only, not example ids.

## Starting commit

Checkout at setup: `46892f143191006b300b519478985c72a324b6de` ("Queue the brief organic-java-merged-pr-links-brief").


## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds only the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA
(depth 1) from each project's GitHub repository, one request at a time (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`,
log `$O/logs/fetch.log`: 41 of 41 fetched). Mirrors that already existed (`lucene`, `commons-csv`, `ical4j`, `guava`)
gained these pins beside earlier ones. One worktree per revision, `$W/CASE-MIRROR-ROLE` (`$O/scripts/worktrees.sh`).
Trees and parents were read from the commit objects (`$O/logs/pins-parents.tsv`; shallow history hides them from `git log`).

- **Every PR is merged, and its `merge_commit_sha` (from `gh api`, `$O/upstream/prs/CASE-OWNER_REPO-N.json`) equals the
  brief's after revision.** Changed-file lists per PR are in `$O/upstream/prs/CASE-files.tsv`.
- **Every after revision's first parent is the brief's before revision.** M04, M06, M10 and M16 are two-parent merges
  (the brief's before pin is the target parent); the rest are squash or rebase commits with one parent.
- Diffstats parent→fix are in `$O/logs/landed-diffstats.txt`; each equals the PR's file list.
- M16 also pins `5a98d74deb44ca78838d4b62e376dbc4a704cc0f`, the reporter's separate H2 test commit the brief links
  (worktree `M16-jOOQ-reporter-test`).

| Case | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|
| M01 | `M01-lucene-fix` | `5c886602a8e8146203deb1a9c3c0121a4241108c` | `606269959c943664ac5231744bae8e88ccaf4196` | `36ddc378eac62f931e98da0ed5cd3edbbddc920e` | 2025-05-30 | Fix IndexSortSortedNumericDocValuesRangeQuery for int sort (#14732) |
| M01 | `M01-lucene-parent` | `36ddc378eac62f931e98da0ed5cd3edbbddc920e` | `8ce67c438a1db1096b2ab4fd6c19331aaad94e5f` | `ed815dad4d998224a17df140f31b014740a2211a` | 2025-05-30 | Grammar and typo fixes (#14734) |
| M02 | `M02-jts-fix` | `ecb26e190e539ea1e4303d100f39f7f30ddeec3e` | `4f55c20d0ae51fe76b8091acf5123fb3af2a6369` | `f1b596aabc664fd59d9028de10885e84b67febd8` | 2026-02-03 | Fix LineSegment.project to handle segments projecting onto a single endpoint (#1179) |
| M02 | `M02-jts-parent` | `f1b596aabc664fd59d9028de10885e84b67febd8` | `e8e7c111211bc7f7a597de0f041a2c64133241fc` | `37b31540438095a2ca948b82d77f76367b1a14ba` | 2026-01-30 | Add GeometryTestCase checkEqualExact with a tolerance |
| M03 | `M03-RoaringBitmap-fix` | `b4b0ba16e50d40688753a3cf057a47804773e233` | `748bbf80d85f4a2da6f9788a39a5c10701c181c6` | `49e120dad9c21349c44f3aa3edfc9a6601e7a7b0` | 2026-11-22 | Fix ArrayStoreException in priorityqueue_or with subtype arrays (#914) |
| M03 | `M03-RoaringBitmap-parent` | `49e120dad9c21349c44f3aa3edfc9a6601e7a7b0` | `b675ec24efff3f37eb3565c4a38fb8ce56730b46` | `ee04085ca216435e326fa2498cdb0d662ad5d3ce` | 2026-11-22 | Skip redundant slices in RangeBitmap range queries (#911) |
| M04 | `M04-datasketches-java-fix` | `7b4068860c3d50da28f3dd734e14f74cd6c5657d` | `86ee8e338aa22e8d06d93558752e7c48e0c42420` | `3857c0cca71a9f5bd462d92e6208d0e0a1c1ac52` `5098a65c8c99e726e8f9a58ec23e8fff8d1a70f3` | 2026-09-16 | Merge pull request #767 from jaideeppyne/fix-kll-items-query-serialize-sorted-view-756 |
| M04 | `M04-datasketches-java-parent` | `3857c0cca71a9f5bd462d92e6208d0e0a1c1ac52` | `3c7fcf2b9a7dd6a0b24195a6dc140cec15a77dcc` | `44c62015f3ab9a6ef35457e681dc398274b0960a` `9bf19ff6b18505009f7d36b2e15d17705dee0534` | 2026-09-16 | Merge pull request #769 from jaideeppyne/fix/tdigest-merge-minmax |
| M05 | `M05-solr-fix` | `f66aa9ed07fa76b5db45186073a9b2ac20c01fd4` | `479b516801afe4a59bb9b2efd8ba261df2ce0ed0` | `c367cb75ac453bb3cd642c46649455e2b4b018b3` | 2025-02-12 | SOLR-17649: Fix JSON faceting on multiValued number types (#3158) |
| M05 | `M05-solr-parent` | `c367cb75ac453bb3cd642c46649455e2b4b018b3` | `26f7300a3d79d40b7ae5672de0b6a1c7c5407358` | `a080cf96ddb2969ca37f723bcbbb0658d53e0fb4` | 2025-02-11 | SolrTestCaseJ4: revert reset of SSL from #3037 |
| M06 | `M06-commons-csv-fix` | `871f7457b9373c8668a2324f4d662b18e74d63d3` | `e47843469742dabeeb3b5d11402044f643f87009` | `d8e12423b47109c76196bbae454726a114cf7c07` `f25f3d5fb5b8332e9759dd34ddbdeefc9bcbc5c4` | 2026-06-19 | Merge pull request #613 from OldTruckDriver/fix/CSV-329_trackbytes_supplementary_delimiter |
| M06 | `M06-commons-csv-parent` | `d8e12423b47109c76196bbae454726a114cf7c07` | `94746578c0b519691e8a6ddd0353b318701bdb31` | `28d8bfba1dc3aede4f3f7651c515b6968b12658f` | 2026-06-19 | Bump actions/checkout from 6.0.3 to 7.0.0. |
| M07 | `M07-jackson-dataformats-text-fix` | `1600e2068acdb983ace981ff943aa4cdd0a2ac81` | `48d63e4021849439bd40bf03674f74f370cd7962` | `fa7e1968282c288589a10af35c45709b01c35421` | 2026-03-27 | Fix #9: (csv) MappingIterator, `String[]` (#625) |
| M07 | `M07-jackson-dataformats-text-parent` | `fa7e1968282c288589a10af35c45709b01c35421` | `ea274ac63b4e513f8ca7f86c1c2873ed1b1b2020` | `df5da70fc2cc7424ac69e876eaabdffbcfc15eb3` `4e5752e3a7ae4e4acb3086b981b1eff3fb175883` | 2026-03-27 | Merge branch '3.1' into 3.x |
| M08 | `M08-woodstox-fix` | `dbc439f112e45147e15954d9bbfc63c6fe1114b2` | `c41f21f74389ea1d0040e05d8d59c76f4218e006` | `0b527e25180a7a8634bee3a3d923322a10a096ba` | 2026-09-28 | Fix #334: BufferingXmlWriter.writeCData(char[], off, len) passes len instead of end index  |
| M08 | `M08-woodstox-parent` | `0b527e25180a7a8634bee3a3d923322a10a096ba` | `8dbd41f2f01e85a20896f0c5f7cf6db093d88058` | `4867018c5c650c0065597c02090b4cc079db0462` | 2026-09-28 | lazy URL construction in WstxInputFactory (#333) |
| M09 | `M09-avro-fix` | `4c29cfb234c6ca0d9df8a572ca04b65ccc7c21e4` | `186a2805de9564e0f1dffe5017606f9bdb215205` | `d28279dace6ffd2deaf6a66e5e82f81a582c3252` | 2026-05-11 | AVRO-4211: Java fix schema generation for union fields with default value that isn't the f |
| M09 | `M09-avro-parent` | `d28279dace6ffd2deaf6a66e5e82f81a582c3252` | `8c329c49abf00b664e13910f498a617ee3770b1e` | `4502c1ba1c453702fd26966a5e5c10441e0d1384` | 2026-05-11 | AVRO-4247: Enforce decompression size limits (#3745) |
| M10 | `M10-ical4j-fix` | `ca6f39764affcc6cacb8845bb66054dee7c04c26` | `6160ee1db6153e372dc17013073bc61019f15bd6` | `a63eeb542d33dfd4302d6e169a0190cfa7da3f8e` `3bd846b2e5d77fb01a6761ca470215064874dab7` | 2026-10-09 | Merge pull request #931 from ical4j/fix/component-group-override-recurrences |
| M10 | `M10-ical4j-parent` | `a63eeb542d33dfd4302d6e169a0190cfa7da3f8e` | `1184b63589c37582cb2f93aaef31e1b8566f18d4` | `6d31d2be63cbb017df16a252a62e0ddd703c140a` `c1f804dff44ed3454357c8653463b43e3032cdb4` | 2026-10-08 | Merge pull request #929 from Shrusti-pk/codec-bare-cr |
| M11 | `M11-HikariCP-fix` | `b81bbc9d438ffac5ef7be4609121d76bb8a31564` | `abf1f6f5fddfe2b0c80f373ec18ef40d64da5897` | `ee5328d209e32d43365538db4d5a2f5ae1361967` | 2025-08-08 | fixes #2323 always reset schema upon connection retrieval (#2346) |
| M11 | `M11-HikariCP-parent` | `ee5328d209e32d43365538db4d5a2f5ae1361967` | `6c208e723cb8a49c3f26368de440a03b5cf6fb01` | `1da3a33ca8e818e8b0239a6b9e22c3f107198ad6` | 2025-07-29 | decrease yield() frequency during direct hand-off attempts |
| M12 | `M12-commons-pool-fix` | `1fe14bbb2ea23c98abcfac3019d1daf34568d5ea` | `fcd12ea6d2125c590742d3a05baa2465ec9e0cac` | `e405182e6eaabc7422dfd6f65511b7883443b1e9` | 2021-06-22 | POOL-396: Handle validation exceptions during eviction. (#85) |
| M12 | `M12-commons-pool-parent` | `e405182e6eaabc7422dfd6f65511b7883443b1e9` | `c6968e03a0aa51de517df1b359eb69ebf26c1b38` | `b93003a8b62fd42086670fe14c2ab1f9d3be7446` | 2021-06-06 | Add BaseGenericObjectPool.{get\|set}MaxWaitDuration(Duration) and deprecate {get\|set}MaxW |
| M13 | `M13-RxJava-fix` | `07e126f030a34d25b23c476fdb24384deb028c63` | `9ac693506e4f4531742ea1cc30a411fdc48532b0` | `b9f5ef81237b16cb3d30d404740fb3ebf0511ed3` | 2018-05-25 | 2.x: Fix Single.takeUntil, Maybe.takeUntil dispose behavior (#6019) |
| M13 | `M13-RxJava-parent` | `b9f5ef81237b16cb3d30d404740fb3ebf0511ed3` | `47a55e642b6468e50e58c08c8364da3426bc93d2` | `9ff403e1a4cc6cbd209d5468583c4177d7e64d5e` | 2018-05-23 | 2.x: benchmark (0..1).flatMap and flattenAs performance (#6017) |
| M14 | `M14-reactor-core-fix` | `e58658d16daa89f521a6b0b78f0d1ce6fbabd238` | `969152004adbd2d992d6be6a0a2f1a64df2b8a23` | `6b71ff09efba7acc06feffe7dca2d80f1538b024` | 2024-08-22 | [#3821] Support Set for exact buffers in Flux.buffer (#3822) |
| M14 | `M14-reactor-core-parent` | `6b71ff09efba7acc06feffe7dca2d80f1538b024` | `0ca18da9716bceb50183fccade2b34b1807335b7` | `ef152df80d57713f9d33cb6080d8f2ee2b90d093` `b732811685a6ea521221500e1aec8035b1602793` | 2024-08-22 | Merge #3876 into 3.7.0-M6 |
| M15 | `M15-logback-fix` | `42caff87ae6eb553dcbf77e25ba87a9d340357ee` | `13db24a76b1fde1f1296f7a48f8e60ce11cc928e` | `91961ad72a1416185abe260c4d56a0762a452223` | 2024-09-21 | fix writing the header for RollingFileAppender (#862) |
| M15 | `M15-logback-parent` | `91961ad72a1416185abe260c4d56a0762a452223` | `2fe30ac0dd538957804dbfcb06cef99715914de7` | `6d11eff9cd3ec0ae15a71455849f630819295934` | 2024-09-21 | add comments to OutputStreamAppender |
| M16 | `M16-jOOQ-fix` | `1a3575be9bf33f3e3f022226d7fd6869a8874e63` | `1147150024998923371cba8d7f817a5ec32b9549` | `fe798c2c9296d13d32e469f60b26778ebc1ac1c4` `b440c42e0f245f754e4c0e840f4a5de62be33c1d` | 2026-04-20 | Merge pull request #19875 from rmorton-r7/rm-fix-issue-19856 |
| M16 | `M16-jOOQ-parent` | `fe798c2c9296d13d32e469f60b26778ebc1ac1c4` | `46bb87ee66fe2ff4371441b2a84173acd44dd1d5` | `909c5ab04e6122a1278d2d2bca4b06178916b44a` | 2026-04-20 | [jOOQ/jOOQ#19870] Render MATERIALIZED keyword for YugabyteDB when using asMaterialized() |
| M16 | `M16-jOOQ-reporter-test` | `5a98d74deb44ca78838d4b62e376dbc4a704cc0f` | `53448499a7bdde01ce0011559d8d9188b55fc916` | `820985f7a466f068974a33f221749128982a10ea` | 2026-04-09 | Add test for loader api regression with static statements |
| M17 | `M17-jOOL-fix` | `d1e06969ff748049aa8d1a9bf5d7f96dee7dc201` | `10eced6d0fae07b4137ab9c4b855ea7d1e85037c` | `5ef86d6525374c6cc412a5a2d996d3d6457cb59c` | 2026-10-16 | [#417] Window.firstValue() and Window.lastValue() are empty when the frame exceeds the par |
| M17 | `M17-jOOL-parent` | `5ef86d6525374c6cc412a5a2d996d3d6457cb59c` | `4df9e3c2f05a9d468405182e2c0ee39e79957119` | `b9195c9061822292c453c2aa804f14e8326d6f27` | 2026-10-16 | [#415] Window functions returning a Seq or a collection share cached results between rows |
| M18 | `M18-eclipse.jdt.core-fix` | `2008a7280a5a72807ace4cba42c22211f58165b5` | `849c79f9cf731b0b9341416bc473d8dc128dd2b3` | `1b3a126e2d26e53aeb79796ec1c881aff66424cd` | 2026-09-15 | Fix formatter crash for empty leading region (#5380) |
| M18 | `M18-eclipse.jdt.core-parent` | `1b3a126e2d26e53aeb79796ec1c881aff66424cd` | `7e08f06c36cfdaaa6c86c3b2ad7980d1dc7ba0b0` | `b0f4c2e96634f36ed39a631098d64c322b65e4d5` | 2026-09-14 | Refresh after preparing test project in JavaSearchBugsTests.testBug231622 |
| M19 | `M19-junit-framework-fix` | `694efb6dbd8506d623d5c117d1df39f9260f72df` | `610e33a9c050e989d977c2842661a1f87e58a68f` | `882bf488e228b1f55ed3b636838825dec31ec20d` | 2021-06-17 | Fix enclosing class bug in IndicativeSentences |
| M19 | `M19-junit-framework-parent` | `882bf488e228b1f55ed3b636838825dec31ec20d` | `014e726b9da964dba6316e523a72a2e94f96f909` | `2f43ffe69f7f98f2abe4537a8b561a6f5bc66331` | 2021-06-16 | Document spelling guidelines |
| M20 | `M20-guava-fix` | `0232f388fbe4d45deea2f31a9c6e2f7283662fd5` | `8bc402e8f32453cfd2260ea3f23a92e6a3dcccef` | `9eb72d3730bd10d92d062c912b673efed0ae2dc0` | 2025-04-14 | Optimize `SetView#equals()` to avoid unnecessary iterations. Fixes #7716. |
| M20 | `M20-guava-parent` | `9eb72d3730bd10d92d062c912b673efed0ae2dc0` | `4183148126b44a69b2f253942574f08e504ca297` | `041f299986e5da0e43c4c2b740ad2c5d9c58c781` | 2025-04-14 | Remove JDK7 stylesheet. |

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` (`$J8` … `$J25`) | the installations of the earlier setups |
| Maven 3.10.0 | on `PATH` | the wrappers name 3.9.6 (M07), 3.9.11 (M08), 3.9.9 (M20); see each case |
| Gradle 8.14 (M01 Lucene) | `$O/tools/gradle-8.14` | zip sha256 `61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa` = services.gradle.org's |
| Gradle 9.6.1 (M03 RoaringBitmap) | `$O/tools/gradle-9.6.1` | zip sha256 `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` = published |
| Gradle 8.10 (M05 Solr) | `$O/tools/gradle-8.10` | zip sha256 `5b9c5eb3f9fc2c94abaea57d90bd78747ca117ddbbf96c859d3741181a12bf2a` = published |
| Gradle 8.5 (M10 ical4j, M14 Reactor) | `$O/tools/gradle-8.5` | zip sha256 `9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026` = published (copied from the earlier setup's checked zip) |
| Gradle 4.2.1 (M13 RxJava; needs JDK 8) | `$O/tools/gradle-4.2.1` | zip sha256 `b551cc04f2ca51c78dd14edb060621f0e5439bdfafa6fd167032a09ac708fbc0` = published (copied likewise) |
| Gradle 7.1-rc-2 (M19 JUnit) | `$O/tools/gradle-7.1-rc-2` | zip sha256 `caa8e323577de2fa421b47dded5278e7376c2bb6420221fbaf7908dfa9be8657` = published, and = the `distributionSha256Sum` in JUnit's wrapper properties |

The zips are kept in `$O/dl/gradle/` with the published `.sha256` files beside them.

Caches and files this work owns:
- `$O/m2`, the Maven local repository named by `$O/maven-settings.xml`; `$O/toolchains.xml` names JDKs 8, 11, 17, 21 and 25.
- `$O/gradle-home`, the `GRADLE_USER_HOME`.
- `$O/releases/NAME/`: release graphs resolved from Maven Central with `--strict-checksums` by `$O/scripts/resolve.sh NAME G:A:V...`
  (`lib/`, `sources/`, `tree.txt` and an ordered `classpath.txt`).
- `$O/artifacts/`: built and overlay jars. `$O/logs/`: build and test logs. `$O/notes/CASE.md`: each case's section as written.

Added by the per-case work (see each case):

| Tool | Where | Identity |
|---|---|---|
| Temurin 24.0.2+12 (M01: Lucene's pins need JDK 24 exactly) | `$O/tools/jdk-24.0.2+12` | tarball sha256 `aea1cc55e51cf651c85f2f00ad021603fe269c4bb6493fa97a321ad770c9b096` = Adoptium's; signature good, Adoptium key `3B04D753C9050D9A5D343F39843C48A565F8F04B` |
| AdoptOpenJDK 9.0.4+11 (M14: Reactor's multi-release jar toolchain) | `$O/tools/jdk9/jdk-9.0.4+11` (`$J9`) | tarball sha256 `aa4fc8bda11741facaf3b8537258a4497c6e0046b9f4931e31f713d183b951f1` = the GitHub release's `.sha256.txt` |
| AdoptOpenJDK 16.0.1+9 (M19: JUnit's toolchain language version 16) | `$O/tools/jdk16/jdk-16.0.1+9` (`$J16`) | tarball sha256 `7fdda042207efcedd30cd76d6295ed56b9c2e248cb3682c50898a560d4aa1c6f` = the GitHub release's `.sha256.txt` |
| Lucene's Gradle 8.14 wrapper jar (M01) | `$O/dl/gradle/lucene-gradle-wrapper-8.14.0.jar` | sha256 `7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172` = services.gradle.org's and the repository's `gradle-wrapper.jar.sha256` |

More shared files:
- `$O/mvnhome`: the `user.home` of every Guava Maven run (M20). Guava's toolchains plugin downloads JDKs into `${user.home}/.m2` whatever is
  configured; never run Guava's build without `-Duser.home=$O/mvnhome`.
- `$O/dl/m13-substitute-repo` and `$O/scripts/rxjava-jcenter-substitute.init.gradle` (M13), `$O/dl/m19-substitute-repo` and
  `$O/scripts/junit-plugin-repo.init.gradle` (M19): plugin-classpath modules that are gone from their original repositories, each checked
  by SHA-1 (see the cases). No upstream build file was edited in any case.
- Build helpers: `$O/scripts/forkA_mvn.sh` (M06, M08, M12, M15, M17), `m07_build.sh` (M07), `M14-gradle.sh`, `M19-gradle.sh`,
  `overlay_D.sh` and `overlay_test_D.sh` (overlays and their test runs, M01, M05, M16, M18, M20), `classdigests.sh`, `classdigests_C.sh`,
  `class_table_D.py`, `gradle_cp_C.sh`; job scripts `submit_B.py`, `submit_C.py`, `submit_D.py`.
- `$W/M19-junit-framework-{parent,fix}` are standalone depth-1 clones at the pinned commits, not linked worktrees (JUnit's build reads git
  metadata and failed in a linked worktree); their trees are the pinned trees (`014e726b9da964dba6316e523a72a2e94f96f909`,
  `610e33a9c050e989d977c2842661a1f87e58a68f`).

## Summary by case

"Release side" says which side of the PR a published release's changed source equals. "Landed tests" is fix's tests on the fix /
parent's own on the parent / fix's tests on the parent. Overlay runs put a side's changed classes over a release; they are not upstream runs.

| Case | Built | Release side | Landed tests | Upstream run |
|---|---|---|---|---|
| M01 Lucene #14732 | overlay over lucene-core 10.3.0; pins need JDK 24 | 10.3.0 = **fix** | overlay and pins alike: 22/22, 21/21, **1 fails** (`ClassCastException`) | job: passed |
| M02 JTS #1179 | source build, core + app, JDK 17 | none (no release after 1.20.0) | 12/12, 10/10, **1 error** `testProjectSegment` | inline |
| M03 RoaringBitmap #914 | source build, Gradle 9.6.1, JDK 21 | none (Central's 1.6.30 is an older tree) | 126/126, 124/124, **both new tests fail** (`ArrayStoreException`) | job: passed |
| M04 DataSketches #767 | source build, JDK 25 | 9.0.0 = parent, 9.1.0 = fix (class-identical) | 6/6, 3/3, **3 fail** | inline |
| M05 Solr #3158 | overlay over 9.8.0 | 9.8.0 = parent, 9.8.1 = fix | `TestJsonFacets` 30/30, 29/29, **1 fails** `testMultivalueEnumTypes` | job: passed |
| M06 Commons CSV #613 | source build, JDK 17 | none (newest 1.14.1 predates) | 168 pass, 166 pass, **2 errors** (`CharacterCodingException`) | inline |
| M07 Jackson CSV #625 | `javac` of each pin's csv sources over released jackson 3.2.0 (pinned SNAPSHOTs gone) | 3.1.1 = parent logic, 3.2.0 = fix logic + later | 5/5, 5/5, **2 fail** | not possible (SNAPSHOT parent gone) |
| M08 Woodstox #335 | source build, JDK 17 | 7.2.2 = parent, 7.3.0 = fix (writer class) | 11/11, 10/10, **3 fail** | inline |
| M09 Avro #3709 | source build avro + avro-idl, JDK 21 | 1.12.2 has the fix's file | 2/2, 2/2, **1 fails** `testToObject` | inline |
| M10 iCal4j #931 | Gradle 8.5, JDK 17 | 4.4.0 = parent | 11/11, 5/5, **7 of 11 fail** | inline |
| M11 HikariCP #2346 | source build, JDK 17, PostgreSQL 16 in Docker | 7.0.0 = parent, 7.0.1 = fix (source only) | 7/7, 6/6, **1 of 7 fails** `testSchema` | inline + job: passed |
| M12 Commons Pool #85 | source build, JDK 8 | none equal (2.10.0 before, 2.11.0 after) | 2/2, 16 `testEvict*` pass, **2 fail** | inline |
| M13 RxJava #6019 | Gradle 4.2.1, JDK 8, init script | 2.1.14 = parent, 2.1.15 = fix | 108/108, 60/60, **4 fail** | inline |
| M14 Reactor Core #3822 | Gradle 8.5, JDK 8 + toolchains 9, 21 | 3.6.10 has parent's `FluxBuffer`; 3.7.0 = fix | 84/84, 77/77, **3 fail** | inline |
| M15 Logback #862 | source build logback-core, JDK 21 | 1.5.8 ≈ parent (comments); **1.5.9 is not the fix** | 14/14, 13/13, **1 fails** | inline |
| M16 jOOQ #19875 | overlay over jooq 3.21.2 | 3.21.2 = parent, 3.21.3 = fix (comment aside) | reporter's H2 test: 2/2 fix, **1 of 2 fails** parent (overlays and pin jars alike) | job: passed |
| M17 jOOλ #418 | source build, both modules (JDK 17 / JDK 8) | none equal | 163/163, 162/162, **1 fails** (each module) | inline |
| M18 JDT Core #5380 | overlay over org.eclipse.jdt.core 3.47.0 (unsigned copy) | 3.47.0 = parent | `FormatterRegionTests` 4/4 fix, **2 of 4 fail** parent | none (Tycho build not attempted) |
| M19 JUnit #2646 | Gradle 7.1-rc-2, JDK 11 + 16, init script | 5.8.0-M1 = parent | `DisplayNameGenerationTests` 10/10, 8/8, **1 fails** | job: passed |
| M20 Guava #7784 | overlay over 33.4.8-jre/-android | 33.4.8 = parent | `SetViewTest` 2736/2736 fix, 2724/2724 parent (Android 2491/2491, 2479/2479); **fix's test doesn't compile on the parent** | job: passed |

## Cases

### M01 · Apache Lucene #14732 — INT index sort with an explicit missing value (overlay over Lucene 10.3.0; upstream build by job)

**Pins.** Parent `36ddc378eac62f931e98da0ed5cd3edbbddc920e`, fix `5c886602a8e8146203deb1a9c3c0121a4241108c` (squash, one parent = the brief's).
The pins are Lucene **11.0.0-SNAPSHOT** on `main` (`build.gradle` `baseVersion = '11.0.0'`) with `minJava = "24"` (`gradle/libs.versions.toml`);
the build files are identical at both pins (the diff is the PR's three files). Changed production file:
`lucene/core/src/java/org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery.java` (two `(long) missingValue` casts become
`((Number) missingValue).longValue()`); test `lucene/core/src/test/org/apache/lucene/search/TestIndexSortSortedNumericDocValuesRangeQuery.java`
(parent `1042f9f09727f00344fb8c35504d9c35d3f25b056aae25f89524d5bb70797379`, fix `c7396c15e193a0dd5694a7db487ca80e0c2ad558d4a3d11e2680e9d02d6ccbbb`;
the fix adds `testSameHitsAsPointRangeQueryIntSort`). The CHANGES entry was added under an old section, so it says nothing about the release.

**Build facts.** Gradle 8.14 through `./gradlew`. **The build needs JDK 24 exactly**: Gradle 8.14 cannot run on JDK 25 ("Unsupported class
file major version 69", log `$O/logs/M01-fix-probe-deps.log` first attempt) and Lucene's `WrapperDownloader` refuses any other version.
Temurin 24.0.2+12 is at `$O/tools/jdk-24.0.2+12` (tarball sha256 `aea1cc55e51cf651c85f2f00ad021603fe269c4bb6493fa97a321ad770c9b096` = Adoptium's API
and `.sha256.txt`; signature good by Adoptium key `3B04D753C9050D9A5D343F39843C48A565F8F04B`).
- Wrapper jar: `gradlew` downloads `gradle-wrapper.jar` 8.14.0 from raw.githubusercontent.com and checks it against `gradle/wrapper/gradle-wrapper.jar.sha256`:
  `7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172`, equal to services.gradle.org's `gradle-8.14-wrapper.jar.sha256`. A checked copy:
  `$O/dl/gradle/lucene-gradle-wrapper-8.14.0.jar`; the job copies it in place before each run.
- The 8.14 distribution zip (checked) is pre-placed at `$O/gradle-home/wrapper/dists/gradle-8.14-bin/38aieal9i53h9rfe7vjup95b9/`, so the wrapper does not download it.
- Inline check (77 s, online): `JAVA_HOME=$O/tools/jdk-24.0.2+12 ./gradlew --no-daemon --console=plain -Porg.gradle.java.installations.auto-download=false :lucene:core:dependencies --configuration testRuntimeClasspath`
  passed: build-infra compiled, test runtime graph randomizedtesting-runner 2.8.3, junit 4.13.2, hamcrest 3.0.
- Commands (from the worktree; `source $O/scripts/env.sh` first):
  `JAVA_HOME=$O/tools/jdk-24.0.2+12 ./gradlew --no-daemon --console=plain -Porg.gradle.java.installations.auto-download=false -Ptests.seed=DEADBEEF -Ptests.jvms=2 --max-workers=4 [--offline] :lucene:core:jar :lucene:core:test --rerun --tests TestIndexSortSortedNumericDocValuesRangeQuery`.
  The offline form is checked by the job.

**Release set.** Lucene releases are Java 21 (class major 65).

| Release | `IndexSortSortedNumericDocValuesRangeQuery.java` in its sources jar | side |
|---|---|---|
| 10.2.1 | `85b90b5f93f71168c0b022fdea9d8012b68946a1af40345fea8d1184a72eea00`, old casts | neither file (pre-fix, branch code) |
| 10.2.2 | `2b0d2d342b9aedbbcca4fa3653e067fe717045eeb62a1b99e146b9779b054d27`, has the `Number` casts | fix (backport, other differences) |
| **10.3.0** | `c3a6b3f39903451a5195aa523bfd9f55cbc2e384bc135447373921cd0bed0732` | **= the fix's file byte for byte** |

Parent file `2d717647c3f77977b164c2d852158a6ed7e9f2a2ae13f6bac6b86d8cf3cbf2f2`, fix file `c3a6b3f39903451a5195aa523bfd9f55cbc2e384bc135447373921cd0bed0732`.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `lucene-10.3.0` | `lucene-core-10.3.0.jar` | `9d70afe194568ca0328b7f762e64eb8094a5e5a76ea3a30b7182f0e7d5f0dd35` |
| `M01-testdeps` (overlay test run only) | `lucene-test-framework-10.3.0.jar` | `2befd6caadd920a9cb5883e5b62f8f19080d38e3debb32aae280a9d6eb033e68` |
|  | `lucene-codecs-10.3.0.jar` | `0628a26040706fea7a222a91c8ca339aef9ea8ceda6d24527a817dc7e0ad5c92` |
|  | `randomizedtesting-runner-2.8.1.jar` | `38302cf4c5a8ba4bf0ff2f707340dcd230657b3a766d9df6e3783cce19c5acb5` |
|  | `junit-4.13.1.jar` | `c30719db974d6452793fe191b3638a5777005485bae145924044530ffa5f6122` |
|  | `hamcrest-2.2.jar` | `5e62846a89f05cd78cd9c1a553f340d002458380c320455dd1f8fc5497a8a1c1` |
| `lucene-10.2.1`, `lucene-10.2.2` (comparison only) | `lucene-core-10.2.1.jar`, `lucene-core-10.2.2.jar` | `245395b58fc290c0630a0e2196afcf331bac4c74d80529d14b7b2553a8543bfd`, `9c219c702449a41c16ad60edc58d12f6d2f4989ef555e875e942904209e25029` |

Runtime classpath: `$O/releases/lucene-10.3.0/classpath.txt` (lucene-core alone; the brief's API is all in core).

**Overlay** (`$O/scripts/overlay_D.sh`, javac 25.0.5 `--release 21` over lucene-core 10.3.0; both sides compile unchanged; fixed entry dates, rebuilds identically):
- `$O/artifacts/M01-lucene-parent-overlay.jar`: `1df88bf58ee549e300e4eb50032f45fe798674d249221e5af2e889258a2b7f0c`
- `$O/artifacts/M01-lucene-fix-overlay.jar`: `24d11d57674a549e2d1c100c69a852a49f4e9dd2d23bc7afe0c3ac5032e595a3`

| Class | parent overlay | fix overlay |
|---|---|---|
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$1$1.class` | `c64629c80de2f0c4791bdad0a8ff7793c9d1cfb5b68aafe9d105852ef6d8292d` | the same |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$1.class` | `ffed0f331f1672ba1e91c3d72b57a6c0c4b9335729238a00a3569a98774418e1` | `82ddda2c32892eedc1ec8d47598c9637841ca78b66cf0ca48dce7f717f15a989` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$2.class` | `26c680ef18a93eb7e4f731eca22452e67b84f726a9e530f4c0d8850850c79591` | `dbece9400408c56333d1be95bfbb056c61cb8c37bd0ba220601aa187cdf4f590` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$3.class` | `b5a36b34c8ba53c6a269a8da038e3ba9a6fabdbb750ac90b85a9c1d9f5402ef6` | `0a6406db487812ae07d960a48c81f2e55411ca9734cec6745073827b3554e70d` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$BoundedDocIdSetIterator.class` | `c0361f266348c9a0c626cbaf6cfb4042e19f2cf0533aa4ad826cdd3b71369e5f` | `ea9aa1d86f68ef6aee9a5126558c61f4bda5e47c35737efbe0fb97da6985cdc9` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$IteratorAndCount.class` | `93783d54e0455020226ad548cf3bc737c9fdff8419a8c7eced51979b369551af` | `c47762a3cf2c60179ee4eca7738fa1030ddf44f361a7f5e0b962f466b34a4091` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$ValueAndDoc.class` | `d5043422e2d532631beab1bd1e636d7fe9a2c7032f04d6f31741c219b6517080` | `adbbd8fdadfba95e477502aa1e608a93834cfa2e615829140b661ddf284243ff` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$ValueComparator.class` | `bf64628ec15fc34aa287fd27bd452cb77381ece411553998ebdb1975db1efbe6` | the same |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery.class` | `a149b7a0ea7594c23650cf89d182de73695c49cdae9a7487936333968b40b861` | `288b728074973ae2f977bf2f6a0e363252fea9b7d753b0bc3f0dbe80d8d69fbb` |

(The inner classes differ between the sides only because the fix shifts line numbers.) Use: `java -cp $O/artifacts/M01-lucene-SIDE-overlay.jar:$(cat $O/releases/lucene-10.3.0/classpath.txt) ...`.
Since 10.3.0's file is the fix's, **lucene-core 10.3.0 alone is the fix side**, and the parent overlay over it is the parent side.

**Landed test over the overlays** (`$O/scripts/overlay_test_D.sh`, JUnitCore on JDK 25.0.5, `-Dtests.seed=DEADBEEF -ea`, classpath overlay + `M01-testdeps`; an overlay run, not an upstream run):

| Run | Result | Log |
|---|---|---|
| fix's test class on the fix overlay | 22/22 pass | `$O/logs/M01-overlaytest-fixtest-on-fix.log` |
| fix's test class on the parent overlay | **1 of 22 fails**: `testSameHitsAsPointRangeQueryIntSort`, `ClassCastException: Integer cannot be cast to Long` at `getDocIdSetIterator` (line 615) | `$O/logs/M01-overlaytest-fixtest-on-parent.log` |
| parent's own test class on the parent overlay | 21/21 pass | `$O/logs/M01-overlaytest-parenttest-on-parent.log` |

**Upstream build: job `20261125-071414-setup-build-lucene-core-at-both-14732-re`** (`$O/scripts/submit_D.py lucene`): on JDK 24.0.2,
lucene-core jar and the landed test class on the fix online, the parent's own offline, the parent with the fix's test transplanted (expected to fail
`testSameHitsAsPointRangeQueryIntSort`) offline, the fix again offline; jars to `$O/artifacts/M01-lucene-{fix,parent}-core.jar`; build trees removed.
**Passed** (5 steps, 3m55s, peak 1.6 GiB):

| Run (pins, upstream Gradle) | Result | Summary |
|---|---|---|
| fix, online | 22/22 pass | `$O/logs/M01-fix.online.{junit,gradle-log}.txt` |
| parent's own, offline | 21/21 pass | `$O/logs/M01-parent.offline.*` |
| fix's test class on the parent, offline | **1 of 22 fails**: `testSameHitsAsPointRangeQueryIntSort`, `ClassCastException: class java.lang.Integer cannot be cast to class java.lang.Long` | `$O/logs/M01-transplant.offline.*` |
| fix again, offline | 22/22 pass | `$O/logs/M01-fix.rerun.offline.*` |

Jars built from the pins (`lucene-core-11.0.0-SNAPSHOT.jar`): `$O/artifacts/M01-lucene-fix-core.jar`
`03a44560aea07027fb942544b3b824fab50703c3125ff517017a796850862e29`, `$O/artifacts/M01-lucene-parent-core.jar`
`c2b1f411e2ed235fe82238ceba2994b28d650ac00a5de1ea165a0f8ea991440e`. lucene-core has no runtime dependencies. Changed classes in them
(`$O/logs/M01-lucene-jobjar-classes.md`, written by `$O/scripts/class_table_jobjars.py`):

| Class | parent jar | fix jar |
|---|---|---|
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$1$1.class` | `8b6cbd7ae8b5fc8b1877bf7de87c31c4b162f12d74b1f8b0ef1afcd712a8873a` | the same |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$1.class` | `2d90b1798e3da00e39f37d8897449a209154da688038051494fba72b1ed09e35` | `56c395d5f19f48b0464321b021e31e31579a35ad8a38b2acc15f6c58966b8c86` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$2.class` | `0546842c2fe8f170341fa33d0574a5b6ce170543f1f86e5f7e884ff6e83526bd` | `7c89e1f2105102c3f85ff1391028befae8e0d3bb5789290f7a1606dc2ec203b2` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$3.class` | `ad68afa31a16da7724d4464c70406f530adab9ff39f529afb0651104f0960b92` | `055f1d1351a4901828af341dd38417219a28e8dd398ffa73c0a3ac5968a41f81` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$BoundedDocIdSetIterator.class` | `f6e1abd4b9278438571b2d477e7f5b1a1c3f5fa6ff40662503614ea2f0d57172` | `0a5ab35b3e60bc7e69da856a14a7aaf03f229e3d12c682b7f0741d418b570fd9` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$IteratorAndCount.class` | `7c795750b50b67a460be0d8cde0f76852090640945cde789f695b7f2ca4b2a5e` | `ffd2e680710dd089587d44823b7d0a0b4460a1cd31eebb67342994d7431f0a74` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$ValueAndDoc.class` | `b6cc0af3b5403d0d8b2528f280f79534eef0ef8d153bce877563cb335318f7ae` | `e755d7429e818ec20afa23ece67747933df8ff78091ada15b0ac929ddb083c22` |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery$ValueComparator.class` | `bb9db7f93a0863069a25def55356d1aa34acc6a8c064f15a7faa055e662a87ac` | the same |
| `org/apache/lucene/search/IndexSortSortedNumericDocValuesRangeQuery.class` | `a78fd619b54e0e4cff7b8eb40feb91d577dadd02e616aa1ec70fc08de67a26b8` | `eb35e64f3d99f746c287d6505683f58516408e6553a32e3508068d95593b4b15` |

**Signatures.** lucene-core, lucene-codecs and lucene-test-framework 10.3.0: Central `.asc` good, key `ED32423E166C9E2CFE66977FAF511F754FB8850B`, in
`https://downloads.apache.org/lucene/KEYS` (copy `$O/keys/lucene-KEYS`, sha256 `a789bed6c8dc675ca6f86c08bea3a2e2bb0b6a80651ef787ac283ea214ca2a32`), keyring `$O/gnupg-D`.

**For the domain agent**
- lucene-core 10.3.0 carries the fix's exact source; the parent overlay over it gives the parent side on a released classpath.
- The pins themselves need JDK 24 (`$O/tools/jdk-24.0.2+12`) to build; the overlays run on JDK 21 or 25.
- The landed test discriminates the sides (the transplant fails with the brief's `ClassCastException`).

### M02 · JTS #1179 — LineSegment.project onto a single endpoint (source build of jts-core and jts-app at both pins)

**Pins.** Parent `f1b596aabc664fd59d9028de10885e84b67febd8`, fix `ecb26e190e539ea1e4303d100f39f7f30ddeec3e` (squash, one parent = the brief's).
Worktrees `$W/M02-jts-parent`, `$W/M02-jts-fix`. Both are `1.20.1-SNAPSHOT`; no JTS release after `1.20.0` (2024-08-30) is on
Maven Central, so the source builds are the only artifacts of either side.

Changed files: production `modules/core/src/main/java/org/locationtech/jts/geom/LineSegment.java`
(parent sha256 `712a110ef1eda1d074d9a84359651d3d5592c9b98b2337aa800a241175380f6e`, fix `8c824b766ccb8c518344f288feefeda5bd7e7c10135c6dd8e79a7e8e8bd1a819`)
and `modules/app/src/main/java/org/locationtech/jtstest/function/LineSegmentFunctions.java`
(parent `f17887e44b2e8f7b756dbcbf918308223690153d7ae0a5784b5dd1c4c6358aa0`, fix `b724bb1a00f9e1270a38e753146959935dd690b565185174952cb451225aa964`;
the parent's file exists but has no `project` function); tests `modules/core/src/test/java/org/locationtech/jts/geom/LineSegmentTest.java`
and its helper `modules/core/src/test/java/test/jts/GeometryTestCase.java`. No build file differs between the pins.

**Build facts.** Maven, `maven.compiler.source/target` 1.8, built with JDK 17.0.21 (`$J17`). The root reactor has `build-tools` (the
shared checkstyle configuration) and `modules`. The checkstyle plugin, bound to `validate`, takes `org.locationtech.jts:build-tools:1.20.1-SNAPSHOT`
as a plugin dependency, which Maven cannot take from the reactor when the build is narrowed with `-pl`: the setup installed it into the
cache once (`$MVN -pl build-tools install`, from the fix worktree; build-tools is identical at both pins), giving
`$O/m2/org/locationtech/jts/build-tools/1.20.1-SNAPSHOT/build-tools-1.20.1-SNAPSHOT.jar`
sha256 `ef24c2a7eef271fe1a71245186e99b30be9426a8fa78cc596d9dfd5d4d002d9f`. Without it, `-pl modules/core` fails at `validate`
("build-tools-1.20.1-SNAPSHOT.jar NOT allowed from apache.snapshots"). `-Dcheckstyle.skip` does not help (plugin dependencies are resolved anyway).

**Commands** (from a worktree, after `source $O/scripts/env.sh; export JAVA_HOME=$J17`):
- jars: `$MVN -pl modules/core,modules/app -am package -DskipTests` (fix online 42 s; parent offline with `-o`, 19 s)
- landed test: `$MVN -pl modules/core test -Dtest=LineSegmentTest -DforkCount=1 -Dsurefire.failIfNoSpecifiedTests=false` (8 s)
- classpath: `$MVN -pl modules/app -am package -DskipTests dependency:build-classpath -Dmdep.outputFile=FILE -Dmdep.includeScope=runtime`
- **offline form works**: the same commands with `-o` (parent package, test and transplant all ran offline).

**Artifacts** (`$O/artifacts/`; built jars carry build timestamps, so bind the class digests below):

| Jar | sha256 |
|---|---|
| `M02-jts-fix-core.jar` | `5bfef8d88771cb028977705682e049a9f55629352c240aa5f064ad1f2deb0b39` |
| `M02-jts-fix-app.jar` | `7c1f2a6bbd9a1211080de63ace78a0c01295028531c1080373c22f176b9ad96c` |
| `M02-jts-fix-io-common.jar` | `3169ff6e210bc4e5ac1429112a38783bcd87ae1d286c9c40bfdd2462300adde9` |
| `M02-jts-fix-JTSTestRunner.jar` (jts-tests' shaded main artifact) | `f5d98be4423d8848dc8ea03a1c9666964f64e2c4edf0aaa172c41427d0b0473d` |
| `M02-jts-parent-core.jar` | `b7192026a7325bd35179ea41dc43924d2c0d1c24af0e01a8d63bb85acef9b4f1` |
| `M02-jts-parent-app.jar` | `a3633cc38210e99f3806c09311a3214b5893fe82e274a2972c746ba9258cdfc9` |
| `M02-jts-parent-io-common.jar` | `5451b8004ba04d978e94dbeffe9e27d83fe90fbca46e973cd17848969061b2a6` |
| `M02-jts-parent-JTSTestRunner.jar` | `e5efd6f5b97c1e7544f1bee20a9c6f5c4f0ef3be8b0aa58866d3de6e6e6312af` |

Runtime classpaths: `$O/artifacts/M02-jts-{fix,parent}-app.classpath.txt` (app, core, JTSTestRunner, commons-lang3 3.7, io-common,
json-simple 1.1.1, jdom2 2.0.6, junit 4.13.1, hamcrest-core 1.3; all paths under `$O`). jts-core alone has no runtime dependency.

| Class | parent | fix |
|---|---|---|
| `org/locationtech/jts/geom/LineSegment.class` | `12d19afc1b9d7f0ec4c6122a31e07945e95fd3555966e94d02b9f5ad8493b391` | `7e5ca1560d6921e1b70b03753e86135b2aa1241979f05002ac38ff379c230312` |
| `org/locationtech/jtstest/function/LineSegmentFunctions.class` | `67c47db5bfc905fcba85811d18f44dbb83eda3db81a7fb16b65dbbfd8c0b86e7` | `eedd80b315f5891ed6cf92bc571c6b19c13cdbe37540d635d8cb69f6c2170574` |

**Landed test** (`LineSegmentTest`, JUnit 4 via surefire, JDK 17.0.21; logs `$O/logs/M02-jts-{fix.test.online,parent.test.offline,parent.transplant.offline}.log`):

| Run | Result |
|---|---|
| fix's tests on the fix | 12/12 pass |
| parent's own tests on the parent | 10/10 pass |
| fix's `LineSegmentTest` + `GeometryTestCase` transplanted onto the parent | 12 run, **1 error: `testProjectSegment`** (`java.util.MissingFormatArgumentException: Format specifier '%s'`, raised while the fix's helper prints its failure line `FAIL - LINESTRING (8.0 0.0, 8.0 0.0): Expected = null -- Actual = `, i.e. the parent's `project` result differed from the expected zero-length segment) |

The parent worktree was restored clean after the transplant; build trees were removed (`git clean -fdx`).

**Signatures.** None: the pins are unreleased snapshots built from GitHub commits; dependencies came from Maven Central into `$O/m2`
with Maven's default checksum checks.

**For the domain agent**
- No released artifact carries either side; use the built jars above (JDK 8 bytecode, built on JDK 17).
- `LineSegmentFunctions.project` exists only in the fix's app jar; the parent's `LineSegmentFunctions` has no such function.
- The transplanted landed test errors in the helper's failure printing rather than with an assertion message; the failing case is `testProjectSegment`.

### M03 · RoaringBitmap #914 — union through a subtype array (upstream Gradle 9.6.1 build at both pins; landed tests by job)

**Pins.** Parent `49e120dad9c21349c44f3aa3edfc9a6601e7a7b0`, fix `b4b0ba16e50d40688753a3cf057a47804773e233` (squash on `master`, parent = the brief's).
Worktrees `$W/M03-RoaringBitmap-parent`, `$W/M03-RoaringBitmap-fix`. Changed production files:
`roaringbitmap/src/main/java/org/roaringbitmap/FastAggregation.java` (+3/−1), `roaringbitmap/src/main/java/org/roaringbitmap/buffer/BufferFastAggregation.java` (+4/−1).
Tests: `roaringbitmap/src/test/java/org/roaringbitmap/TestFastAggregation.java` (+13), `roaringbitmap/src/test/java/org/roaringbitmap/buffer/TestFastAggregation.java` (+15).

**Build facts.** Gradle 9.6.1 (`$O/tools/gradle-9.6.1`, the wrapper's version, zip checked). The repository's `gradle-wrapper.jar`
`7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172` (both pins) equals services.gradle.org's published wrapper jar for Gradle 8.14.3
(`$O/dl/gradle/wrapper-C/gradle-8.14.3-wrapper.jar.sha256`), not 9.6.1's; the setup ran the distribution directly. Version label `1.6.30`
(`gradle.properties`), so the jars are `roaringbitmap-1.6.30.jar` (see the release note below: Central's 1.6.30 is a different, earlier tree).
Main classes compile with `--release 8` (module-info with 9 via `org.javamodularity.moduleplugin`, a `java11` multi-release source set with
`--release 9`). Repositories: Central and the Plugin Portal only. The `roaringbitmap` module has **no runtime dependencies**.
The test task uses the JUnit Platform (Jupiter 5.12.2), runs on `max(current JDK, 11)` (here JDK 21.0.13, `$J21`), `failFast = true`, and
a fixed **2 GB test heap** (`minHeapSize`/`maxHeapSize`) — why the test runs are a job. Spotless is configured with `ratchetFrom("origin/master")`,
which the shallow worktrees lack; only the `spotless*` tasks would need it.

Commands (compile online once, 49 s; offline 15 s, checked at the parent):

```bash
source ~/.cache/in-the-loop/merged-pr-links/scripts/env.sh; export JAVA_HOME=$J21
cd $W/M03-RoaringBitmap-fix   # or M03-RoaringBitmap-parent
$O/tools/gradle-9.6.1/bin/gradle --no-daemon --offline --console=plain --max-workers=2 -Dorg.gradle.jvmargs=-Xmx1536m \
  -Porg.gradle.java.installations.auto-download=false :roaringbitmap:jar :roaringbitmap:cleanTest :roaringbitmap:test \
  --tests org.roaringbitmap.TestFastAggregation --tests org.roaringbitmap.buffer.TestFastAggregation
python3 -I $O/scripts/junit_summary.py roaringbitmap/build/test-results/test
```

**Artifacts** (Gradle 9 jars are reproducible by default, but bind the class digests):
- `$O/artifacts/M03-RoaringBitmap-parent-roaringbitmap.jar`: `3cb7d2f26074f9cdfebb90382f445c598f4779dedab860bdc7788f9c8221de9c`
- `$O/artifacts/M03-RoaringBitmap-fix-roaringbitmap.jar`: `0b0888e57c72d942f64d5569d44fffadecfc9394ec0ea5c1c904a0769291782a`

| Class (`org/roaringbitmap/…`) | parent | fix |
|---|---|---|
| `FastAggregation.class` | `80379c2894b0bab97cebe695298a7d339d65b18430cd05d5f6fceef3d80239bd` | `4a91f23fc6ae1da1b2de4bb0506c8588851aae702dcd9ac3c376694c3e6280c3` |
| `FastAggregation$1.class` | `70b35d044c47b635c6d3d1a0993d96b0fd2d307e5a55fbfdd52a703ded2f5ba8` | the same |
| `FastAggregation$2.class` | `a02a24ea737cba00ec6f0f35f8e51cbabc325abbd34f3a8cd83137c56a2b2bfc` | `ee8cbc1753107782ad64d877cb4e5b34177e26d7194f68b7298a3643b676c432` |
| `FastAggregation$3.class` | `07ddb113dd63a915abfec4d9797f6ac9d8d5c265d6bdc7dc7d26c4ba2e8727c8` | `087afff50ead124d4abc410452841ec4f518bad4fe2d0215fb076e0376d868cf` |
| `buffer/BufferFastAggregation.class` | `0fbce9ee1935b7e0df7f57b60d2d25396fbc0e5478ee7f8f9e644ab7cd6a9c5c` | `79c8978c6dcf4b07c60d1006ac5883605310148f6b54b6dfa3e6d8cb7cb0d107` |
| `buffer/BufferFastAggregation$1.class` | `a1ef5181cec7360b6cdf87e830bc8cf4782d36638998aa429cf03e1825b158f7` | the same |
| `buffer/BufferFastAggregation$2.class` | `fc33054c7589c808c173d5e840e50c0b299232339734d6f74b546353a7bde1d5` | `ea3fd24e990a0834211b99847195ea023fbf3dfba34fe339aaa24f173ce3fd57` |
| `buffer/BufferFastAggregation$3.class` | `5613be9a609ce662419a6df7ea5ddaec3e6727fe7436b4df53269d981ec176e0` | `9ae2a875fef919dcc5df16afed3959c1ecfd7e1014e0a5b91dec53182675cc21` |
| `buffer/BufferFastAggregation$4.class` | `a880593b4841a37234b1bc56f16eb77fe066474d020bc85016705af3a50dde4d` | `a4183410fbd0641cad5c747cfbe65ccb61572607784a3fca520542c551d6b0e3` |

(The anonymous classes differ by line numbers.) Runtime classpath: the jar alone.

**Landed tests: job `20261125-072322-setup-run-roaringbitmap-914-s-landed-fas`** (`$O/scripts/submit_C.py m03`): both
`TestFastAggregation` classes on the fix online then offline, the parent's own copies offline, and the fix's two test files transplanted onto
the parent (new tests expected to fail; `failFast` stops the run at the first failure); then the build trees are removed.
**Passed** (5 steps, 1m11s, peak 710 MiB). Logs: `$O/logs/M03-{fix.test-online,fix.test-offline,parent.test-offline,parent.transplanted.test-offline}.{junit.txt,gradle-log.txt}`.

| Run | Result |
|---|---|
| fix, online and again offline | 126/126 pass each time |
| parent's own, offline | 124/124 pass |
| fix's two test files on the parent, offline | **2 fail** (56 run, 2 skipped by `failFast`): `priorityQueueOrAcceptsSubtypeArray()` in the heap class (`ArrayStoreException: org.roaringbitmap.RoaringBitmap`) and in the buffer class (`ArrayStoreException: org.roaringbitmap.buffer.MutableRoaringBitmap`) |

**Release.** `org.roaringbitmap:RoaringBitmap:1.6.30` on Central (metadata last updated 2026-11-14, before the merge on 2026-11-23;
`$O/releases/roaringbitmap-1.6.30`, strict checksums, signature good): `RoaringBitmap-1.6.30.jar`
`e61685ec9ff1a66350b3ddfadcdf0cab28be9ffabfea438fd50582e48f6577fb`. Its two changed files equal **neither side**: in place of the parent's
`bitmaps.clone()` (both `priorityqueue_or` overloads) it has the older `Arrays.copyOf(bitmaps, bitmaps.length)` — the two-argument form the
brief says the PR description cites — and `BufferFastAggregation` also differs in a third spot (`System.arraycopy` into a new
`ImmutableRoaringBitmap[]` where the parent has `Arrays.copyOf(array, array.length, ImmutableRoaringBitmap[].class)`).
Source digests: release `FastAggregation.java` `dfee84822ccec60412a1191044122ebaabb5899ef1ad144e8f87c35fca75c075`, `BufferFastAggregation.java`
`357eb2f885920a1f986b1adf39726ad8cd7205d50cf80937feed065edb588931`; parent `a5798927853a39ea58889d8a06d6c4f995811e12916f19be1d223a8d25bba525`,
`62f1a61ef44d3182a1bf20dd204afecbee842cf5ce0cf92b0a4643ad989210f6`; fix `8c92fede226acfefaabe63f2f0d031756a1c3a9d5cc2a127b30a0c0011dfeab5`,
`cf414decfdf2574dfb1e6882811075bbb2dcb3de99eae20b5eeba9c170da0b48`. (The lowercase coordinate `org.roaringbitmap:roaringbitmap` stops at 1.6.8.)

**For the domain agent**
- Use the pin jars `$O/artifacts/M03-RoaringBitmap-{parent,fix}-roaringbitmap.jar` (no dependencies). Central's `RoaringBitmap:1.6.30` is an older tree, not the parent, despite the same version label.
- The brief's claim scenarios were not run.

### M04 · Apache DataSketches #767 — KLL items sorted flag across serialization (source build at both pins; releases 9.0.0 = parent, 9.1.0 = fix, class-identical)

**Pins.** Parent `3857c0cca71a9f5bd462d92e6208d0e0a1c1ac52`, fix `7b4068860c3d50da28f3dd734e14f74cd6c5657d` (two-parent merge; first parent = the brief's).
Worktrees `$W/M04-datasketches-java-{parent,fix}`. Version `9.1.0-SNAPSHOT`, Maven, `maven.compiler.release` 25, single module, **no runtime
dependency** (TestNG 7.12.0 and slf4j-simple for tests only). The POM requires Maven `[3.9.12,4.0.0)` (3.10.0 passes) and a JDK 25 toolchain
(`-t $O/toolchains.xml`). Changed: production `src/main/java/org/apache/datasketches/kll/KllItemsSketch.java`
(parent sha256 `ba851bef32ea2e3eb02f3669e95b4e13f4a3ad6e0264e088aba7806b811df206`, fix `83a383f8675dc96c510e74985bdbe025af172430f5f893b109f7d42164375d35`);
test `src/test/java/org/apache/datasketches/kll/KllItemsSketchSerDeTest.java`.

**Commands** (from a worktree, `source $O/scripts/env.sh; export JAVA_HOME=$J25`;
`SK="-Dmaven.javadoc.skip -Dgpg.skip -Drat.skip -Djacoco.skip -Dmaven.gitcommitid.skip=true"`):
- jar: `$MVN $SK package -DskipTests` (13 s online on the fix)
- landed test: `$MVN $SK test -Dtest=KllItemsSketchSerDeTest -DforkCount=1 -Dsurefire.failIfNoSpecifiedTests=false` (4 s)
- **`-Dmaven.gitcommitid.skip=true` is required**: the git-commit-id plugin fails on the shallow worktree ("Missing unknown 7b4068860c3d50da28f3dd734e14f74cd6c5657d").
- TestNG reports land in `target/test-output/<timestamp>/TEST-*.xml`, not `target/surefire-reports`.
- **Offline form works**: the parent's package, test and transplant all ran with `-o`.

**Artifacts.** The builds are reproducible (`project.build.outputTimestamp` 2026-01-01), and the changed classes are byte-identical to the releases':

| Jar | sha256 |
|---|---|
| `$O/artifacts/M04-datasketches-java-parent.jar` | `eda511113435941bbc778eb8005339f795c1b5889767477cc00698c9d1c73437` |
| `$O/artifacts/M04-datasketches-java-fix.jar` | `f8630263b59497f7585f26bdd4d525e2cbab840a33b1f5923eaecae9646df052` |
| `$O/releases/datasketches-java-9.0.0/lib/datasketches-java-9.0.0.jar` | `da5ad11655341a90e6464bca40e5995e24441d446d6706ffe0d152251e2dff2d` |
| `$O/releases/datasketches-java-9.1.0/lib/datasketches-java-9.1.0.jar` | `af95dbbccf4a98c36b2821a86e3dc9fef7d5cdb7f02efbc313ac74ac3289d9f4` |

| Class | parent build = 9.0.0 | fix build = 9.1.0 |
|---|---|---|
| `org/apache/datasketches/kll/KllItemsSketch.class` | `e80d1103a5ec96770c4ed0e89173313f253d5f427add4e6bc46a873d5fe5ecde` | `b34353b4f9b491c771890198f8a6eba88480af4266899deaf17efa58cffd8e6e` |
| `org/apache/datasketches/kll/KllItemsSketch$CreateSortedView.class` | `268beb88e0865b0837880f2f360731c7f4c9c9f7c6f931d7c1df507aa26610d4` | `3fba3ab51f94bb279ca4c0577f905c237db404d5447c2850307447c0add0ae10` |
| `org/apache/datasketches/kll/KllItemsSketchIterator.class` | `71f610d95a782cc18cbe78a2672a6206e07c70739ae70b4636810c5cadef4077` | the same |

Class file version 69 (Java SE 25) in all four jars. The `KllItemsSketch.java` in `datasketches-java-9.0.0-sources.jar` equals the parent's
(`ba851bef32ea2e3eb02f3669e95b4e13f4a3ad6e0264e088aba7806b811df206`) and in `9.1.0-sources.jar` the fix's (`83a383f8675dc96c510e74985bdbe025af172430f5f893b109f7d42164375d35`). Runtime classpath: the jar alone
(`$O/releases/datasketches-java-9.{0,1}.0/classpath.txt`). 9.1.0 also carries changes after the fix elsewhere.

**Landed test** (TestNG via surefire, JDK 25.0.5; logs `$O/logs/M04-datasketches-{fix.test.online,parent.test.offline,parent.transplant.offline}.log`):

| Run | Result |
|---|---|
| fix's `KllItemsSketchSerDeTest` on the fix | 6/6 pass |
| parent's own on the parent | 3/3 pass |
| fix's test file transplanted onto the parent | 6 run, **3 fail**: `serializeDeserializeAfterQueryHeapifyMatches` and `serializeDeserializeAfterQueryWithCompaction` (`expected [false] but found [true]`), `serializeDeserializeAfterQueryWrapMatches` (`Arrays do not have the same size:6 != 4`) |

Worktrees restored clean; build trees removed.

**Signatures.** `datasketches-java-9.0.0.jar.asc` and `9.1.0.jar.asc` from Maven Central verified against
`https://downloads.apache.org/datasketches/KEYS` (saved `$O/keys/datasketches-KEYS`, sha256 `f76a47b6d3d20d2204739a15dabc394d95cba5aae6a00ad29d54ee0e73384923`)
in the keyring `$O/gnupg-B` (agent stopped): 9.0.0 good signature by `82DF4C90F72D57E36CB8355B05F2FA8F8CD4A902` (N Lee Rhodes), 9.1.0 by
`8B374472FAD328E17F479863B379691FC6E298DD` (Zili Chen). Signatures in `$O/dl/sig-B/`.

**For the domain agent**
- The released pair 9.0.0 / 9.1.0 is class-identical to parent / fix for the KLL items classes and signed; either the builds or the releases serve.
- JDK 25 is required to run any of these jars (class version 69).
- The brief's `MemorySegment`-based `heapify`/`wrap` API needs no extra dependency (no datasketches-memory).

### M05 · Apache Solr #3158 — multivalued enum facets (overlay over Solr 9.8.0; release pair 9.8.0/9.8.1; upstream build by job)

**Pins.** Parent `c367cb75ac453bb3cd642c46649455e2b4b018b3`, fix `f66aa9ed07fa76b5db45186073a9b2ac20c01fd4` (squash of 4 PR commits, one parent = the brief's).
The pins are Solr **10.0.0-SNAPSHOT** on `main` (`build.gradle` `baseVersion = '10.0.0'`) on Lucene 9.12.1 (`gradle/libs.versions.toml`); build
files identical at both pins. Changed production files (`solr/core/src/java/org/apache/solr/search/facet/`): `FacetField.java`, `FieldUtil.java`, and
`FacetFieldProcessorByArrayDV.java` (**javadoc only**: its class is byte-identical in both overlays). Test side: `TestJsonFacets.java` adds
`testMultivalueEnumTypes` (parent `088e46cd6610c79d7181803fe3926b14bf8035bdd38fb5cca546bafa19678325`, fix `2863738210bb606216935c0369f161098670994eddceb12245b3c4afa7e6bfdd`);
`solr/core/src/test-files/solr/collection1/conf/schema_latest.xml` adds the `severityType` field type and the `severity_mv` field (parent
`18a00fd8e7164da78547e4eaaf86fdf19f19bdfa4bfffcaa38a9480ded554268`, fix `5b4f1c90c6a809cda58a236575e07dd7286bc11e939f03ebdd890f73b07a985b`), so **the parent's
schema has no `severity_mv`** (`enumsConfig.xml` exists at both pins); `TestRawTransformer` copies `enumsConfig.xml` too. CHANGES lists SOLR-17649 under 9.9.0.

**Build facts.** Gradle 8.10 through `./gradlew`; Solr's `WrapperDownloader` wants **JDK 21–23** (use `$J21`). Wrapper jar 8.10.2
(`gradle/wrapper/gradle-wrapper.jar.version`) = `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`, equal to services.gradle.org's
`gradle-8.10.2-wrapper.jar.sha256`; checked copy `$O/dl/gradle/solr-gradle-wrapper-8.10.2.jar`. The 8.10 distribution zip (checked) is pre-placed at
`$O/gradle-home/wrapper/dists/gradle-8.10-bin/deqhafrv1ntovfmgh0nh3npr9/`. Command (from the worktree):
`JAVA_HOME=$J21 ./gradlew --no-daemon --console=plain -Porg.gradle.java.installations.auto-download=false -Ptests.seed=DEADBEEF -Ptests.jvms=2 --max-workers=4 [--offline] :solr:core:jar :solr:core:test --rerun --tests org.apache.solr.search.facet.TestJsonFacets`
(not run inline: over a minute; the job runs it, and checks the offline form).

**Which release is which side.** Sources jars from Central (sha1 checked, `$O/dl/central/solr-core-{9.8.0,9.8.1,9.9.0}-sources.jar`):

| File | parent | fix | 9.8.0 | 9.8.1 / 9.9.0 |
|---|---|---|---|---|
| `FacetField.java` | `9d7db4a7643258af965be696bbfdc351065d6dce5a17db8f44d778c432634022` | `e932faee992881785ad074a783f72d0b00a5b6d3bb56480413ab38468bd4bf03` | = parent | = fix |
| `FieldUtil.java` | `b9b4148122b5473899cc70fcde5f0beb022cca19803162df04632989e3db4888` | `99b1fcb948221b9333314f7f6da2738f426207c7fe2fc1e04d56756c77947083` | `7e56d898b17e6c734bb1446d7d27f874db4e68137c738879a66634228acb8f1a` | `5152f339db9d3eacf52b0bb22e65461c277fe21c4fe5b83ffe4f6cd2549d11c1` |
| `FacetFieldProcessorByArrayDV.java` | `bf5b69e7564668e3f362cc1762451f9a82986fc3dbf1be8a89ca5f1ff456f9b7` | `f3585c5368edc3d9e90298d20dd13612d3a08bf079ca7c2804f67be05a75545d` | `b113bce879b6874e8e14500bfa852971c16e4bc7e0626449d219236a20d9ac2b` | `0de7abe37d8d618318c35eb7115f36f74702c629a182ffc2ce7a7ec54c492d4c` |

The `FieldUtil` and `FacetFieldProcessorByArrayDV` differences of 9.8.0 from the parent, and of 9.8.1 from the fix, are only the branch_9x spelling of
`instanceof FieldCacheImpl.SortedDocValuesImpl.Iter` without a pattern variable (`diff` shown in the session). So **9.8.0 is the parent side and 9.8.1 the fix
side** of the three files; other changes between 9.8.0 and 9.8.1 exist and were not examined. Solr 9.8.x's POM declares **Lucene 9.11.1** (the pins use 9.12.1).

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `solr-9.8.0` (125 jars, `classpath.txt`) | `solr-core-9.8.0.jar` | `c70902e5d02eada6100999e6a718bde88ed5d3aa47afff45c2141123564ed747` |
|  | `solr-solrj-9.8.0.jar` | `795127f79762ec3dee9b5956300c5bcef2f9d6dc8bf6c6783229fb12bab679c1` |
|  | `lucene-core-9.11.1.jar` | `cb7a9b121bce4ce054ab690ab43ac13ee11ae516d6cef67650130066beee7c9b` |
| `solr-9.8.1` (125 jars) | `solr-core-9.8.1.jar` | `f14dee96490f5e7282a05a534ecfac1c228d308b62d27374b61b72b13ecf1846` |
|  | `solr-solrj-9.8.1.jar` | `fe257a0b46cbcb4492ee9b2f5c997ebdaa34bd6e57f0cddec6ea254bdc8b082f` |
| `M05-testdeps` (139 jars; `solr-test-framework:9.8.0`) | `solr-test-framework-9.8.0.jar` | `2c6521aa006c6906e1eb21a056bf6d694b19e8fd81c1be289b84e418cf32e8a7` |
|  | `lucene-test-framework-9.11.1.jar` | `4a395a7e2a037c49ca869dd9e98693d91ea190c1390de626ccaf83e3afed0811` |

**Overlay** (javac 21.0.13 `--release 21` over `$O/releases/solr-9.8.0/classpath.txt`; the pins' main-branch sources compile against 9.8.0 unchanged):
- `$O/artifacts/M05-solr-parent-overlay.jar`: `44163aa96c8e43dd6206458a39ad7364af30b84407b7aea8a26748b4791d1e98`
- `$O/artifacts/M05-solr-fix-overlay.jar`: `17f7cc07d85409c58ca66b17d17e6c7b04601a76771605464f15fa15dbe34e81`

| Class | parent overlay | fix overlay |
|---|---|---|
| `org/apache/solr/search/facet/FacetField$FacetMethod.class` | `463046bf2a0d008670e41db616479c4604f10e12279d99cf6aa75b031155c1d7` | the same |
| `org/apache/solr/search/facet/FacetField.class` | `6061ddf87ae5e80fb3c6ab62fdb01feca210cd5c158ffcaece959438f881d7b5` | `a00fb7657a485b8618510413f84c5e406da970e77af510a660a9d177798226dc` |
| `org/apache/solr/search/facet/FacetFieldProcessorByArrayDV.class` | `922d859982c5f1842aab772b0c710bb1bad567ab40625bf1bc27a89b2dfdb8cb` | the same |
| `org/apache/solr/search/facet/FieldUtil$DVOrdValues.class` | `2aa315eb7caca2d7c20beaf508a2345e6995f3f9743af60831eb4fd380814b02` | `2381c525481b413bb7878975c0047a5adf990063fe610ea401aecbc9c32c7bc7` |
| `org/apache/solr/search/facet/FieldUtil$FCOrdValues.class` | `483b73a6632b8322ffa6052274eeb1e1493fe0fe022e8b119f2efd1645274080` | `f3271fa32f52eb639a4584baab79dd0046762926a6b591569c5de771faba0056` |
| `org/apache/solr/search/facet/FieldUtil$OrdFunc.class` | `192db2420df4cf566aad71a5f8de6844aba906818992aa1624b1b58a395f879a` | the same |
| `org/apache/solr/search/facet/FieldUtil$OrdValues.class` | `e6f913530f3050e1561fb66d6bb9a0d9428b3524d58c0370f51ffb8b9c546894` | `fa2ae8f393c970ccc2bcd09540146ac55fd20f3ab1629e75bfd7891be26054fc` |
| `org/apache/solr/search/facet/FieldUtil.class` | `3015946a5c6e6cbcdc527265fb73c8c153d8eb3aa5b3bc7a945c4faafa19af64` | `0b6702ba545fb7ec13d3b13fbdd74275ef8adf4bc7a4191b4d59d5a0879653fc` |

**Landed test over the overlay: could not run.** The fix's `TestJsonFacets` compiles over the fix overlay + `M05-testdeps` (`$O/overlays/M05/test-fix/`), and was run
with JUnitCore on JDK 21, `-Dtests.seed=DEADBEEF -Dtests.method=testMultivalueEnumTypes`, the fix's `solr/core/src/test-files` on the classpath. On **both** overlays
the core does not start: `SolrCoreInitializationException ... RAMDirectory can only be used with the 'single' lock factory type` (also with
`-Dsolr.tests.lockType=single`). The main-branch test configuration (`solrconfig-tlog.xml` with an `xi:include` of
`solrconfig.snippet.randomindexconfig.xml`) does not take under the 9.8.0 test framework; this is an environment mismatch, not a result. Logs
`$O/logs/M05-overlaytest-fixtest-on-{fix,parent}.log`, `$O/logs/M05-overlaytest-fixtest-on-fix.try2.log`. Not pursued further (a 9.8.x test-files tree would
need the release tag's sources).

**Upstream build: job `20261125-071415-setup-build-solr-core-at-both-3158-revis`** (`$O/scripts/submit_D.py solr`): JDK 21, the whole `TestJsonFacets`
class on the fix online (must include and pass `testMultivalueEnumTypes`), on the parent (own copy) offline, on the parent with the fix's
`TestJsonFacets.java` and `schema_latest.xml` transplanted (expected to fail `testMultivalueEnumTypes`), the fix again offline; jars to
`$O/artifacts/M05-solr-{fix,parent}-core.jar`. This job is the landed test's only run. **Passed** (5 steps, 7m16s, peak 3.8 GiB):

| Run (pins, upstream Gradle) | Result | Summary |
|---|---|---|
| fix, online | 30/30 pass (incl. `testMultivalueEnumTypes`) | `$O/logs/M05-fix.online.{junit,gradle-log}.txt` |
| parent's own, offline | 29/29 pass | `$O/logs/M05-parent.offline.*` |
| fix's `TestJsonFacets.java` and `schema_latest.xml` on the parent, offline | **1 of 30 fails**: `testMultivalueEnumTypes {p0=STREAM}`, `RuntimeException: List size mismatch @ facets/f/buckets` | `$O/logs/M05-transplant.offline.*` |
| fix again, offline | 30/30 pass | `$O/logs/M05-fix.rerun.offline.*` |

Every run prints three `java.security.policy: error adding Permission, java.net.URLPermission` / `Locale provider adapter "CLDR" cannot be
instantiated` warnings from the test security policy on JDK 21; they appear in passing runs too and do not fail anything.
Jars built from the pins (`solr-core-10.0.0-SNAPSHOT.jar`): `$O/artifacts/M05-solr-fix-core.jar`
`90b5fe4838cfe66cafab2876970b34ada9c1a433d53ecbe56ad202517afa319a`, `$O/artifacts/M05-solr-parent-core.jar`
`c1f562d68829d915ec8d3a7f9fd2349dc68ff15866b777d33c2923d15c30d528`. Their Gradle runtime classpath was not exported (the overlays'
9.8.0 classpath is above). Changed classes in them (`$O/logs/M05-solr-jobjar-classes.md`):

| Class | parent jar | fix jar |
|---|---|---|
| `org/apache/solr/search/facet/FacetField$FacetMethod.class` | `c91de87ccb6d139064d8240b146c85c35128af87d93233e35b3b668d2b3861cc` | the same |
| `org/apache/solr/search/facet/FacetField.class` | `988eca65f2a919e3d96b6fbedfa7596bc5765bbe1b3800b205ec2429846874ad` | `1a7a133a27a8add429acc4cdf3de1913637074621915102a2a51091049141aa7` |
| `org/apache/solr/search/facet/FacetFieldProcessorByArrayDV.class` | `cb3db70c5c0b6d760899994ffd9860c3abca12bdd82c5c4c5d180e564419b397` | the same |
| `org/apache/solr/search/facet/FieldUtil$DVOrdValues.class` | `838323a35b2691406824a0113d0c4708c8734de65e438ac4a26dc60acfbb2356` | `dc3829ac670e192eb199e31960e623e9dbaad78b464528dbd4866d6ff3bcbc6c` |
| `org/apache/solr/search/facet/FieldUtil$FCOrdValues.class` | `00313bda80102005ec73fb93274f1aa3401abd848e086a4df6d55ba8c1b0500f` | `40c581d1095864e9436f0cdc31949e27f8294eef31820346d1086ffbc2e0e0d4` |
| `org/apache/solr/search/facet/FieldUtil$OrdFunc.class` | `192db2420df4cf566aad71a5f8de6844aba906818992aa1624b1b58a395f879a` | the same |
| `org/apache/solr/search/facet/FieldUtil$OrdValues.class` | `caf036378150ad0650021b9a65c11c7c0ab862e897798df76cafce76ab9a4a65` | `4fae31335d00e09ffc626675d90cd4f82fb3bfe4674c98f67fda943e27d5d02f` |
| `org/apache/solr/search/facet/FieldUtil.class` | `a2dd1053dd03b069275920770424b1dcb5a6e4549f3c0bfa826de2fab689e02e` | `b9a75af5809045e73d767f404654d4d8a80b140887d103fa0fbc80901c230c4a` |

**Signatures** (keyring `$O/gnupg-D`; `$O/keys/solr-KEYS` sha256 `ad17d9f81c5f63f1175af8e7d5451f8aed25aa2869543bfda3c01cc0f4930a69`, `$O/keys/lucene-KEYS`):
- `solr-core-9.8.1.jar`: good, key `50E3EE1C91C7E0CB4DFB007B369424FC98F3F6EC`.
- `solr-core-9.8.0.jar`, `solr-solrj-9.8.0.jar`, `solr-test-framework-9.8.0.jar`: cryptographically good signatures (made 2025-01-14) by the release manager's key
  `EDF961FF03E647F9CA8A9C2C758051CCA3A13A7F` (Anshum Gupta), which **had expired** (KEYS copy: 2019-01-23; keyserver.ubuntu.com copy: 2024-08-13): gpg reports
  `EXPKEYSIG`. Central's sha1 matches. Recorded, not resolved.

**For the domain agent**
- Release pair: **9.8.0 = parent side, 9.8.1 = fix side** for the changed files (pattern-variable spelling aside); the overlays put both pins' exact sources over 9.8.0.
- The brief's schema fixture is the fix's `schema_latest.xml` (`severity_mv`); the parent pin has no such field, so a parent-side run needs it supplied.
- The landed test discriminates the sides on the pins (job above); there is no overlay run of it (the pins' test config needs the 10.0 test framework).

### M06 · Apache Commons CSV #613 — byte positions after a supplementary-character delimiter (pinned source build)

**Pins.** Parent `d8e12423b47109c76196bbae454726a114cf7c07`, fix `871f7457b9373c8668a2324f4d662b18e74d63d3` (two-parent merge; first parent = the brief's).
Worktrees `$W/M06-commons-csv-parent`, `$W/M06-commons-csv-fix`. Changed production file: `src/main/java/org/apache/commons/csv/ExtendedBufferedReader.java`.
Changed tests: `CSVParserTest` (new `testGetBytePositionMultiCharacterDelimiterWithSupplementaryCharacter`) and `ExtendedBufferedReaderTest`
(new `testReadingSupplementaryCharacterTracksBytes`); also `src/changes/changes.xml`.

**Build facts.** Maven, single module, `commons-csv` **1.15.0-SNAPSHOT**, parent `org.apache.commons:commons-parent:102`, compiler source/target 1.8.
`pom.xml` is identical at both pins. Built with Maven 3.10.0 on **JDK 17.0.21** (`$J17`). Runtime dependencies (compile scope, not optional):
`commons-io:commons-io:2.22.0` and `commons-codec:commons-codec:1.22.0`; test: JUnit Jupiter (via commons-parent), mockito, h2 2.2.224 etc.
No release contains either pin: Central's newest is `1.14.1` (older than the parent). No release graph was resolved.

**Commands** (from the worktree; `$SK` = `-Drat.skip -Djapicmp.skip -Dcheckstyle.skip -Dpmd.skip -Dcpd.skip -Dspotbugs.skip -Djacoco.skip -Danimal.sniffer.skip -Dmaven.javadoc.skip -Dcyclonedx.skip -Dspdx.skip -Dmoditect.skip -Dbuildnumber.skip -Dlicense.skip -Denforcer.skip -Dforbiddenapis.skip`;
only report/lint plugins are skipped). Wrapped in `$O/scripts/forkA_mvn.sh WT MODDIR TAG JDK TESTS [online] [args]`.
- online (first resolution, 44 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -DforkCount=1 -Dtest=CSVParserTest,ExtendedBufferedReaderTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 5–8 s, also from a clean tree on the parent)**: the same with `-o` in place of the thread setting.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests):

| File | sha256 |
|---|---|
| `M06-commons-csv-parent.jar` | `5e37bfd494c4e8757ae128a36620196b2ca88f35f61f1d2da5727f6c8bf38b31` |
| `M06-commons-csv-fix.jar` | `84f132f20da47f5344adb51b777ebc987718836b935e6137b51e346e2420bb8a` |
| `org/apache/commons/csv/ExtendedBufferedReader.class` (parent) | `69b066ecc2d0273e8e5acfe4e0fdb1e15ad5611f4d69b67d71354634ad6028e7` |
| `org/apache/commons/csv/ExtendedBufferedReader.class` (fix) | `5c18fd168371e2125ae8e67ac43f95cb55fc8368fb2e948303fea851cbd08c34` |
| `commons-io-2.22.0.jar` | `2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758` |
| `commons-codec-1.22.0.jar` | `d164fe79f262c32d9b18a0b5b2d317d1c27653d5e98fd2b998c24bf901c72ce4` |

Runtime classpath (same at both pins): `$O/artifacts/M06-commons-csv-fix.runtime-classpath.txt`; test classpath `$O/artifacts/M06-commons-csv-fix.test-classpath.txt`.
Use: `java -cp $O/artifacts/M06-commons-csv-ROLE.jar:$(cat $O/artifacts/M06-commons-csv-fix.runtime-classpath.txt) ...`.

**Landed tests** (`CSVParserTest` + `ExtendedBufferedReaderTest`, upstream Maven build, JDK 17; logs `$O/logs/M06-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own tests (online, then offline) | 168 run, 0 failures, 0 errors, 4 skipped (both times) |
| parent, its own tests (offline) | 166 run, 0 failures, 0 errors, 4 skipped |
| fix's two test files on the parent (offline) | 168 run, **2 errors**: both new tests, `java.nio.charset.CharacterCodingException` (`CSVParserTest:683`, `ExtendedBufferedReaderTest:113`) |

**Signatures.** `commons-io-2.22.0.jar` and `commons-codec-1.22.0.jar`: `.asc` from Central verified against `https://downloads.apache.org/commons/KEYS`
(saved `$O/keys/commons-KEYS`, sha256 `f154a693df7d01290487b3bf4c045481cdde6bd310b9eeb37b7a533b03b3299a`): good signatures by
`F4DD59C90148BDC52BEB90A4530AA5F25C25011F` (Gary Gregory), keyring `$O/gnupg-A` (agent stopped).

**Jobs.** None: every build and test run took under a minute inline.

**For the domain agent**
- JDK 17 (`$J17`) built and ran it; the bytecode is Java 8. The jars are the pins' own builds, not releases.
- The landed tests use `nextRecord()` and the reader directly; the parent's failure is a `CharacterCodingException` from the decoder.

### M07 · Jackson dataformats-text #625 — schema-less MappingIterator end detection (javac build of the csv module at both pins against released Jackson 3.2.0; pinned SNAPSHOT parent gone)

**Pins.** Parent `fa7e1968282c288589a10af35c45709b01c35421`, fix `1600e2068acdb983ace981ff943aa4cdd0a2ac81` (squash on `3.x`, one parent = the brief's).
Worktrees `$W/M07-jackson-dataformats-text-{parent,fix}`. Changed: production `csv/src/main/java/tools/jackson/dataformat/csv/CsvParser.java`
(parent sha256 `fb96016edba3889f3c53663f17ac8be4e369e7212fabb5a14ad13c0c16c05f5f`, fix `552456f1e46b8d54b8d50931002895f7e04430069e51872f4840874f27bd884c`:
at the end of an array, `_state = STATE_NEXT_ENTRY` becomes `STATE_UNNAMED_VALUE` when `_columnCount == 0`); tests: `MappingIteratorEnd9Test`
moved from `csv/.../csv/tofix/` (where it carried `@JacksonTestFailureExpected`) to `csv/.../csv/deser/`, and `deser/TestParserQuotes.java`
(the commented-out exhaustion assertion enabled); `release-notes/VERSION`.

**Unstable input: the pinned build cannot be run as it is.** Both pins are `3.2.0-SNAPSHOT` with parent `tools.jackson:jackson-base:3.2.0-SNAPSHOT`
from `https://central.sonatype.com/repository/maven-snapshots` (declared in the root POM). On 2026-11-25 that repository has no `3.2.0-SNAPSHOT`
of `jackson-base`, `jackson-core` or `jackson-databind` (404 on their metadata; it lists 3.1.8–3.1.10, 3.2.4–3.2.5, 3.3.0–3.3.1 and 3.4.0 snapshots only),
and 3.2.0 itself is released. `mvn -pl csv validate` fails: "Non-resolvable parent POM … tools.jackson:jackson-base:pom:3.2.0-SNAPSHOT (absent)"
(`$O/logs/M07-fix.maven-validate.log`). The exact March 2026 snapshot dependencies are therefore not recoverable.

**Substitution (recorded, upstream files unchanged).** `$O/scripts/m07_build.sh ROLE` compiles the csv module's `src/main/java` of the pin with
`javac --release 17` (JDK 17.0.21) against the **released** `jackson-core-3.2.0`, `jackson-databind-3.2.0` and `jackson-annotations-2.22`
(the versions `jackson-base:3.2.0` manages), generates `PackageVersion.java` from `PackageVersion.java.in` (version `3.2.0-SNAPSHOT`), copies
`src/main/resources/META-INF`, and packs a jar with fixed entry dates (rebuilding gives the identical jar). **`module-info.java` is left out** (classpath
build): the jar has 38 classes where the 3.2.0 release has 39 (the release's extra is `module-info.class`). It then compiles the pin's whole
`src/test/java` (minus its `module-info.java`) against JUnit Jupiter 6.0.3 and AssertJ 3.27.7, the versions `jackson-base:3.2.0` manages
(resolved by a throwaway POM with that parent, `$O/resolve/M07-testdeps/pom.xml`; the March snapshot parent's own test versions are unknown). Both
pins' main and test trees compiled without errors against these.

| Set | Jar | sha256 |
|---|---|---|
| `$O/releases/M07-testdeps/lib` (runtime part) | `jackson-core-3.2.0.jar` | `5e353ce53c6901105dfcbf183e3220c17072e334e552b818a4bb1b99decea596` |
|  | `jackson-databind-3.2.0.jar` | `3ef94a3dddeafc247c50230fad0315981b2ce4ae6e91cfb4368a86f328904e4f` |
|  | `jackson-annotations-2.22.jar` | `21ddb598807d3a51a876704eb979d9296e1c6a6f47ab1826ff88c6d6a127a2d0` |
| (test part) | `junit-jupiter-api-6.0.3.jar` | `d655d7e6f0c7ae07f10a2f3bbaaebb6d30e9b26204a068ad9e9b3950aa28792c` |
|  | `junit-jupiter-engine-6.0.3.jar` | `1e2fab61ad27ea08fc7c70dd9677cf8c6d1ae5434d42dcfdd633b12c7e7c04d0` |
|  | `junit-jupiter-params-6.0.3.jar` | `cf2947e2302b9f8c8a059259a277881c1cadae8fbc2514c16a925cfeb7beb2e5` |
|  | `assertj-core-3.27.7.jar` | `c4a445426c3c2861666863b842cc4ec7bbb1c4226fefd370b6d2fe83d6c4ff0f` |
| `$O/releases/junit-console-6.0.3/lib` | `junit-platform-console-standalone-6.0.3.jar` | `3ba0d6150af79214a1411f9ea2fbef864eef68b68c89a17f672c0b89bff9d3a2` |

All resolved from Maven Central with `--strict-checksums` (full list with digests: `sha256sum $O/releases/M07-testdeps/lib/*`).

**Built artifacts** (`$O/artifacts/`):

| Jar | sha256 |
|---|---|
| `M07-jackson-dataformat-csv-parent.jar` | `9744118d5b27be99ef5b0dfc091659ee12648e4d217fa3e307792c746b1aaed3` |
| `M07-jackson-dataformat-csv-fix.jar` | `58581df4868f9ce67c241a5669f72277df271c46d5c7d7b389963e456863480e` |

| Class | parent | fix |
|---|---|---|
| `tools/jackson/dataformat/csv/CsvParser.class` | `8fef7d993b7a756d6b161741f70880d68b2cc38394949cba7ac121efb2653234` | `fac7a0cdc18ffdd5c4debb8ac627bb7d83caec9ee40547db66bfe0d18e7a8cd9` |

Runtime classpaths: `$O/artifacts/M07-jackson-dataformat-csv-{parent,fix}.classpath.txt` (the jar, then core 3.2.0, databind 3.2.0, annotations 2.22).

**Releases compared** (`$O/releases/jackson-dataformat-csv-{3.1.1,3.2.0}/`, with their runtime graphs):

| Release | `CsvParser.java` in `-sources.jar` sha256 | relation |
|---|---|---|
| `tools.jackson.dataformat:jackson-dataformat-csv:3.1.1` (27-Mar-2026) | `26a2a1be1e246c0b2e07d11b83e9fc0f3138b42b5b23b4cccdcb48adc8286bab` | the parent's file minus one 3.2 API override (`willInternPropertyNames()`); the changed end-of-array logic is the **parent's** |
| `...:3.2.0` | `6b69bd41d58e42618a91662ca8f2a7311f46801f8c03b68ad77c55f25535330d` | has the **fix's** logic plus later 3.2 features (#634 name-length checks, #327 duplicate-header option, `EMPTY_STRING_AS_MISSING`) |

| Jar | sha256 |
|---|---|
| `jackson-dataformat-csv-3.1.1.jar` | `729df0d36ad2e0ca2a562648f2a7514a47d723b0c561debaed0b86cb87e71783` |
| `jackson-dataformat-csv-3.2.0.jar` | `b9c56b2646882d36db036cd2d33dfe14ce6e9446d6b21216acdbd6d04412e05b` |
| `jackson-core-3.1.1.jar` | `4cd270bee1a1aa34be18da78268f3879355b6ea09154beff496831785b6194c9` |
| `jackson-databind-3.1.1.jar` | `a80302c80cb02803e33d7b3301a0d619146d3191d285e6bbd39fa17d3aa5f24a` |
| `jackson-annotations-2.21.jar` | `53ca085f4a150f703f49e1aabd935bd03b43e1ea3d55d135438292af22cef56b` |

**Landed tests** (JUnit console 6.0.3 on JDK 17.0.21, `--select-class` the two classes; logs and XML `$O/logs/M07-{fix-fix,parent-own,parent-transplant}{.log,-reports/}`):

| Run | Result |
|---|---|
| fix's `deser.MappingIteratorEnd9Test` + `deser.TestParserQuotes` on the fix build | 5/5 pass |
| parent's own `tofix.MappingIteratorEnd9Test` (failure expected, so it passes) + `deser.TestParserQuotes` on the parent build | 5/5 pass |
| fix's two test files transplanted onto the parent (tofix copy removed) | 5 run, **2 fail**: `MappingIteratorEnd9Test.testDefaultSimpleQuotes` and `TestParserQuotes.testDefaultSimpleQuotes`, each `expected: <false> but was: <true>` |

Command (from `$O`, after `m07_build.sh ROLE`, whose trees in `$O/tmp/m07-ROLE` were then removed; rerun the script to get them back):
`$J17/bin/java -jar $O/releases/junit-console-6.0.3/lib/junit-platform-console-standalone-6.0.3.jar execute -cp $O/tmp/m07-ROLE/test-classes:$O/tmp/m07-ROLE/classes:$(ls $O/releases/M07-testdeps/lib/*.jar | tr '\n' ':') --select-class tools.jackson.dataformat.csv.deser.MappingIteratorEnd9Test --select-class tools.jackson.dataformat.csv.deser.TestParserQuotes`.
Works offline (no network use after resolution). The parent worktree was restored clean after the transplant.

**Signatures.** None checked: Jackson is not an Apache project with a KEYS file; Central's checksums were enforced (`--strict-checksums`).

**For the domain agent**
- The pins' own Maven build cannot run (the `3.2.0-SNAPSHOT` parent and dependencies are gone); the built jars are the pins' csv sources over released 3.2.0 core/databind, without `module-info`.
- Release `3.1.1` has the parent's end-of-array logic; release `3.2.0` has the fix's, plus later changes in the same class.
- Jackson 3 needs JDK 17+; the builds are `--release 17`.

### M08 · Woodstox #335 — CDATA validation within the caller's array slice (pinned source build)

**Pins.** Parent `0b527e25180a7a8634bee3a3d923322a10a096ba`, fix `dbc439f112e45147e15954d9bbfc63c6fe1114b2` (squash; parent = the brief's).
Changed production file: `src/main/java/com/ctc/wstx/sw/BufferingXmlWriter.java`. Changed test: `src/test/java/wstxtest/wstream/TestContentValidation.java`
(new `testCDataCheckingIndexWithReplacedChars`; `testCDataChecking` and `testCDataFixing` gain a third input type, a slice not at array start,
and `testCDataChecking` now checks the reported index). Also `release-notes/CREDITS`, `release-notes/VERSION`.

**Build facts.** Maven, single module, `com.fasterxml.woodstox:woodstox-core` **7.3.0-SNAPSHOT** (packaging `bundle`), parent
`com.fasterxml:oss-parent:79`, `javac.src.version` 1.8. `pom.xml` identical at both pins. The wrapper names Maven 3.9.11
(`.mvn/wrapper/maven-wrapper.properties`, only-script); **Maven 3.10.0 on `PATH` was used instead and works** (the wrapper was not run).
Built on **JDK 17.0.21**. Runtime dependency: `org.codehaus.woodstox:stax2-api:4.3.1`; `msv-core`, `xsdlib` 2022.7, `isorelax`, `relaxngDatatype`
are optional (tree in `$O/logs/M08-woodstox-fix.tree.txt`). The build shades msv into the main jar (1094 entries; the unshaded
`original-…` jar has 244); Central's `woodstox-core-7.3.0.jar` is likewise shaded (1095 entries).

**Commands** (`$SK` as in M06; `$O/scripts/forkA_mvn.sh`):
- online: `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -DforkCount=1 -Dtest=TestContentValidation -Dsurefire.failIfNoSpecifiedTests=false package` (19 s)
- **offline (checked, 5–6 s)**: the same with `-o`.

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M08-woodstox-parent.jar` (shaded, as published) | `e1a2e77b070558d1d76bc92adec282f7e6c70baf261aa1b85316b1b4eec71bb7` |
| `M08-woodstox-parent-original.jar` (unshaded) | `270e973336bcdb7e1acd973d5b30feba2bf0544b27428ac5b29ea779671cc4bc` |
| `M08-woodstox-fix.jar` (shaded) | `314c309d97fe3b27f87ac27d6859c7e1b7684f4c79929562934ef235dd89b92c` |
| `M08-woodstox-fix-original.jar` (unshaded) | `c38a0cce9cec455da485b206b32b1328f51e7b50f8de0b8f81c6504574b5f16a` |
| `com/ctc/wstx/sw/BufferingXmlWriter.class` (parent) | `c3a70d1009242f4804150299c729e1506391d41cfcc46b21a95605fead2784fc` |
| `com/ctc/wstx/sw/BufferingXmlWriter.class` (fix) | `b9e4fe17201735731f46117722f84b6ae4770582d2d315e69d35c2e3e9d6be8a` |
| `stax2-api-4.3.1.jar` | `1953d9d443149769c8418fd4fb69284ba2f98adbbed304e9a050c360e28541c6` |

Runtime classpath of the fix build (stax2-api first, then the optional msv jars): `$O/artifacts/M08-woodstox-fix.runtime-classpath.txt`.
The shaded jar plus `stax2-api-4.3.1.jar` is enough for the writer.

**Releases** (`$O/releases/woodstox-core-{7.2.2,7.3.0}/`, `--strict-checksums`): `BufferingXmlWriter.java` in **7.2.2 equals the parent's**
(sha256 `05d7471d6b51d858feebde2618dbd1fa84c31d864771779655003bb8e3497850`) and in **7.3.0 equals the fix's**
(`31d286d30ef13915553a5f021049b55308795ef304969ce613fbf2d9f21ae8c8`). 7.2.2 depends on stax2-api 4.3.0, 7.3.0 on 4.3.1.

| Jar | sha256 |
|---|---|
| `woodstox-core-7.2.2.jar` | `3bd35f778fb15cd517fae51961ba7a9388eae8e4a836fac1166c7f70740e55cd` |
| `woodstox-core-7.3.0.jar` | `246cb4845991ab52196ef90ee8a361164512b5cc7ec0547c9fab8f3db75f2679` |

**Landed tests** (`TestContentValidation`, upstream Maven build, JDK 17; logs `$O/logs/M08-*.log`):

| Run | Result |
|---|---|
| fix, its own (online, then offline) | 11/11 pass |
| parent, its own (offline) | 10/10 pass |
| fix's test file on the parent (offline) | **3 failures**: `testCDataChecking:177` (no exception for type 0, itype 2, the offset slice), `testCDataFixing:248` (output `CData_in:_<![CDATA[text`, 23 chars, for the slice), `testCDataCheckingIndexWithReplacedChars:279` (message says `(index 24)`, test expects `(index 34)`) |

**Signatures.** `stax2-api-4.3.1.jar`, `woodstox-core-7.2.2.jar`, `woodstox-core-7.3.0.jar`: Central `.asc` verified, good signatures by
`28118C070CB22A0175A2E8D43D12CA2AC19F3181` (Tatu Saloranta). The key was fetched from keyserver.ubuntu.com by key id
(`$O/keys/key-3D12CA2AC19F3181.asc`); there is no trust path to it beyond that.

**Jobs.** None.

**For the domain agent**
- 7.2.2 (parent's writer) and 7.3.0 (fix's writer) are signed published stand-ins for the two sides' changed class; the pins' own jars are in `$O/artifacts/`.
- The `StringWriter` route the brief names selects `BufferingXmlWriter`; the landed test also covers the stream-based routes (`createWriter(f, enc, …)`).

### M09 · Apache Avro #3709 — union default of a later branch (source build of avro and avro-idl at both pins; release 1.12.2 carries the fix's file)

**Pins.** Parent `d28279dace6ffd2deaf6a66e5e82f81a582c3252`, fix `4c29cfb234c6ca0d9df8a572ca04b65ccc7c21e4` (squash, one parent = the brief's).
Worktrees `$W/M09-avro-{parent,fix}`. Version `1.13.0-SNAPSHOT`; Maven from the repository root (`avro-toplevel`, parent `org.apache:apache:38`),
`maven.compiler.release` 11, **the enforcer requires JDK 21** to build. Changed: production
`lang/java/avro/src/main/java/org/apache/avro/util/internal/JacksonUtils.java` (parent sha256
`ed3c4cd58c3a91b158e1200ae2c0198561100759b7d1229c04cf6dd5ce5625c7`, fix `576864cce9f3d7858857c3e31877287f99ad75945e8081de6a8ed314240ce55d`);
test `lang/java/avro/src/test/java/org/apache/avro/util/internal/TestJacksonUtils.java`. Nothing in `idl` changed.

**Commands** (from the worktree root, `source $O/scripts/env.sh; export JAVA_HOME=$J21`;
`SK="-Dmaven.build.cache.enabled=false -Drat.skip -Dspotless.check.skip=true -Dspotless.apply.skip=true -Dmaven.javadoc.skip -Dgpg.skip -Djacoco.skip"`):
- jars: `$MVN $SK -pl lang/java/avro,lang/java/idl -am package -DskipTests` (31 s online on the fix)
- landed test: `$MVN $SK -pl lang/java/avro test -Dtest=TestJacksonUtils -DforkCount=1 -Dsurefire.failIfNoSpecifiedTests=false` (6 s; the avro
  module's surefire has three executions, default, `test-with-custom-coders` and `test-without-fast-reader`, so the class runs three times)
- classpath: `$MVN $SK -pl lang/java/idl -am package -DskipTests dependency:build-classpath -Dmdep.outputFile=FILE -Dmdep.includeScope=runtime`
- **`-Dmaven.build.cache.enabled=false` is needed**: `.mvn/extensions.xml` loads `maven-build-cache-extension` 1.0.1, which otherwise skips
  surefire as "cached" (no tests run) and keeps a cache beside the local repository (`$O/build-cache`, removed after setup).
- **Offline form works**: the parent's package, test, transplant and classpath ran with `-o`.

**Artifacts** (`$O/artifacts/`; the builds use a fixed output timestamp: the two idl jars are identical):

| Jar | sha256 |
|---|---|
| `M09-avro-parent-avro.jar` | `c7dd3a958fb225ab01775bdf74b747981c06592432b27402f039534c72931f9b` |
| `M09-avro-fix-avro.jar` | `714489b85ac58cfa18de7e8a1aa778b34c164e8d4af252dd760adb3c85f32ca5` |
| `M09-avro-parent-idl.jar` | `dca35f88215184be1beaab8c375b7713daabf8ffed30c2a0598a618346797806` |
| `M09-avro-fix-idl.jar` | `dca35f88215184be1beaab8c375b7713daabf8ffed30c2a0598a618346797806` |

| Class | parent | fix |
|---|---|---|
| `org/apache/avro/util/internal/JacksonUtils.class` | `ce14a93f05112c5a5c35414ce9245ab91642e694881f4fb4d556938ffc58f80c` | `d3a35b453c1b162a7f4b3189c98b8655fa221c0dbf4fbf7dbff347d5bbe6b33b` |

Runtime classpaths `$O/artifacts/M09-avro-{parent,fix}-idl.classpath.txt` (idl jar, avro jar, then from `$O/m2`: jackson-core/databind 2.21.3,
jackson-annotations 2.21, commons-compress 1.28.0, commons-codec 1.19.0, commons-io 2.20.0, antlr4-runtime 4.13.2, commons-text 1.15.0,
commons-lang3 3.20.0, slf4j-api/simple 2.0.17, and JUnit 5.14.4/4.13.2 jars, which the build's parent declares in a non-test scope).
The external parts are the same at both pins.

**Release** `org.apache.avro:avro:1.12.2` and `avro-idl:1.12.2` (`$O/releases/avro-1.12.2/`, signed, 2026-08): its `JacksonUtils.java` is
**byte-identical to the fix's** (`576864cce9f3d7858857c3e31877287f99ad75945e8081de6a8ed314240ce55d`). No release carries the parent's file
(1.12.1 predates the PR; not resolved).

| Jar | sha256 |
|---|---|
| `avro-1.12.2.jar` | `6522e2a146b859ad158bb024dcc3b0bc826680794a2523b0881dafcbd59ce2df` |
| `avro-idl-1.12.2.jar` | `b4b44005c8d7a5ff0f7a4602d9fca2517efb3c282b28c5ba03b44e8eebfff7ec` |
| `jackson-core-2.22.1.jar` | `941ff029bcdb93e83d209ce516c1a7fb8bbac07d0a2fa122f5bf194b2cd7b4f4` |
| `jackson-databind-2.22.1.jar` | `7dcd7e53bec1f56c7ad278bd1ca0840bebcc595d61ce44d6a8439abb75b965b2` |

(the rest of that graph: `sha256sum $O/releases/avro-1.12.2/lib/*`; ordered classpath `$O/releases/avro-1.12.2/classpath.txt`).

**Landed test** (JUnit 5 via surefire, JDK 21.0.13; logs `$O/logs/M09-avro-{fix.test.online,parent.test.offline,parent.transplant.offline}.log`):

| Run | Result |
|---|---|
| fix's `TestJacksonUtils` on the fix | 2/2 pass (in each of the three surefire executions) |
| parent's own on the parent | 2/2 pass |
| fix's test file transplanted onto the parent | 2 run, **1 fails**: `testToObject` at line 104, `expected: <1> but was: <null>` |

Worktrees restored clean; build trees removed.

**Signatures.** `avro-1.12.2.jar.asc` and `avro-idl-1.12.2.jar.asc` from Maven Central verified against `https://downloads.apache.org/avro/KEYS`
(saved `$O/keys/avro-KEYS`, sha256 `235ffb2aff646b2aee1538c3f2bc6ee637908666f4d3fc0766f277de94c2a39d`) in `$O/gnupg-B` (agent stopped): good
signatures by `FDEB0769F816CBDFD194CBBEBD463DB5B0CCBDD6` (Ryan Skraba).

**For the domain agent**
- The built pair is the exact PR pair; 1.12.2 is a signed release with the fix's `JacksonUtils.java` (other files differ from the 1.13.0-SNAPSHOT pins).
- The IDL writer (`avro-idl`) is unchanged by the PR and its jar is identical at both pins; only `avro`'s `JacksonUtils` differs.
- Build on JDK 21 (enforcer); the jars are release 11 bytecode.

### M10 · iCal4j #931 — override recurrences in ComponentGroup (upstream Gradle build at both pins, inline)

**Pins.** Parent `a63eeb542d33dfd4302d6e169a0190cfa7da3f8e`, fix `ca6f39764affcc6cacb8845bb66054dee7c04c26` (a two-parent merge into `develop`;
first parent = the brief's before pin). Worktrees `$W/M10-ical4j-parent`, `$W/M10-ical4j-fix`.
Changed production file: `src/main/java/net/fortuna/ical4j/model/ComponentGroup.java` (+49/−5). Test: the Spock specification
`src/test/groovy/net/fortuna/ical4j/model/ComponentGroupTest.groovy` (+166/−2). The rest are `openspec/changes/component-group-override-recurrences/*` documents.

**Build facts.** Gradle 8.5 (the wrapper's version; the setup ran the checked distribution `$O/tools/gradle-8.5` directly). The repository's
`gradle/wrapper/gradle-wrapper.jar` is `76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3` at both pins, equal to services.gradle.org's
published wrapper jar for Gradle 9.1.0 (`$O/dl/gradle/wrapper-C/gradle-9.1.0-wrapper.jar.sha256`), not 8.5's; it is not used.
`sourceCompatibility`/`targetCompatibility` 11; Error Prone (NullAway) on `compileJava` needs **JDK 17+** to compile: the setup used JDK 17.0.21 (`$J17`).
Repositories: `mavenLocal()`, `mavenCentral()` and the Plugin Portal; nothing dead. The `axion-release` plugin takes the version from git tags; the
shallow worktrees have none, so the built jar is labelled `ical4j-0.1.0-SNAPSHOT.jar`. Tests run on the JUnit Platform (Spock 2.4-M7-groovy-3.0,
Groovy 3.0.25). `test` is finalized by JaCoCo; its coverage rule (0.2 < 0.7) prints a violation that does not fail the build.
The `test` task looks for a Podman or Docker socket (`/var/run/docker.sock` exists here) only for Testcontainers tests, which `ComponentGroupTest` doesn't use.

Commands (online once, then offline; each run 10–25 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links/scripts/env.sh; export JAVA_HOME=$J17
cd $W/M10-ical4j-fix   # or M10-ical4j-parent
$O/tools/gradle-8.5/bin/gradle --no-daemon --offline --console=plain --max-workers=2 -Dorg.gradle.jvmargs=-Xmx1536m \
  -Porg.gradle.java.installations.auto-download=false jar test --tests net.fortuna.ical4j.model.ComponentGroupTest
python3 -I $O/scripts/junit_summary.py build/test-results/test
git clean -fdxq   # afterwards
```

The offline form works (every run after the first was offline; the first, online, resolved everything into `$O/gradle-home`).

**Landed test** (JDK 17.0.21, host locale `en_US.UTF-8`, default time zone of the host):

| Run | Result |
|---|---|
| fix, `ComponentGroupTest` (online, then again offline) | 11/11 pass |
| parent, its own `ComponentGroupTest` (offline) | 5/5 pass |
| fix's `ComponentGroupTest.groovy` transplanted onto the parent (offline, restored after) | **7 of 11 fail**: `CalculateRecurrenceSetWithException` (expects 3 periods, the parent gives 4), both rows of `rescheduled override with a bare RECURRENCE-ID replaces the master instance` (`RECURRENCE-ID:20210715T000000Z` and `RECURRENCE-ID;TZID=UTC:20210715T000000`), `override that keeps its start but changes its duration replaces the master instance`, `override moved outside the query period removes the master instance and adds nothing`, `recurrence properties on an override do not generate extra occurrences`, `RECURRENCE-ID matches a zoned master instance by instant` |

Logs: `$O/logs/M10-ical4j-fix.{compile-online,test-online,test-offline}.log`, `$O/logs/M10-ical4j-parent.{test-offline,transplanted.test-offline}.log`,
summaries `$O/logs/M10-ical4j-{fix,parent,parent.transplanted}.junit.txt`. Worktrees restored and cleaned (`git clean -fdxq`).

**Artifacts** (Gradle 8.5 jars keep file timestamps, so the jar digests are of these copies; the class digests are the stable binding):
- `$O/artifacts/M10-ical4j-parent-ical4j.jar`: `83d4485d99ff7c2926db41a0b9a767ba301b59e075de7107aa62513b4c21297d`
- `$O/artifacts/M10-ical4j-fix-ical4j.jar`: `ca6b3670828a7cf11c385fad8f31174b9bc92418c51ee8700c5f4ced2e7fc55c`

| Class | parent | fix |
|---|---|---|
| `net/fortuna/ical4j/model/ComponentGroup.class` | `cdce39f0238a18ba7af38674c9ed53269de2105166985d51e5dcdcb863461d94` | `69174b8a0a680b903f425ff07848ab62ecf48bf47235d7564184b1fe2f3d314e` |

**Runtime classpath of the pin jars** (`runtimeClasspath` at the fix, the same graph at the parent): `$O/releases/M10-ical4j-pin-runtime/classpath.txt`,
jars from `$O/gradle-home`, digests in `classpath.txt.sha256`: slf4j-api 2.0.12, commons-codec 1.17.0, commons-lang3 3.18.0, threeten-extra 1.8.0,
caffeine 3.1.8 (`7dd15f9df1be238ffaa367ce6f556737a88031de4294dad18eef57c474ddf1d3`), jparsec 3.1 (`8c0dbeb70b57cea4da22df5e7f08c04e3004a7615391a03f01b38f7311719152`),
groovy 3.0.25 (`ad009e985dd84e4f524f4ed1751866da5bef816b691851bfbcefa48a01180a07`). The last three's SHA-1 equal Central's `.sha1`; the first four
are the jars of the strict-checksum release set below.

**Release.** The latest ical4j on Central is 4.4.0 (metadata last modified 2026-10-02, before the merge on 2026-10-08). `$O/releases/ical4j-4.4.0`
(`resolve.sh`, strict checksums): `ical4j-4.4.0.jar` `f4cac5c4a16d8c0f2228ad0e3221b90d069ae0efea73402b51888468e86405f9`, with slf4j-api 2.0.12,
commons-codec 1.17.0, commons-lang3 3.18.0 and threeten-extra 1.8.0. Its `ComponentGroup.java` is byte-identical to the **parent**'s
(`82f4deed6234c1616f0512517d001bc8440ea7d65d28da1af7b28aaf08a99fa9`; fix `4be01f8140589b8d05a71a456de1d9d267975496e8808077867f6629c37a990d`).
No release carries the fix.

**For the domain agent**
- Use `$O/artifacts/M10-ical4j-{parent,fix}-ical4j.jar` with `$O/releases/M10-ical4j-pin-runtime/classpath.txt`; 4.4.0 is the parent side.
- The landed spec's July 2021 fixture is in `ComponentGroupTest.groovy` at the fix; the brief's claims were not run.
- Error Prone needs JDK 17+ to compile ical4j; the bytecode targets Java 11.

### M11 · HikariCP #2346 — restore the configured schema between borrowers (source build at both pins; releases 7.0.0 = parent, 7.0.1 = fix by source; PostgreSQL via Testcontainers)

**Pins.** Parent `ee5328d209e32d43365538db4d5a2f5ae1361967`, fix `b81bbc9d438ffac5ef7be4609121d76bb8a31564` (squash on `dev`, one parent = the brief's).
Worktrees `$W/M11-HikariCP-{parent,fix}`. Version `7.0.1-SNAPSHOT`, Maven, single module, `source/target` 11; built on JDK 17.0.21.
Changed: production `src/main/java/com/zaxxer/hikari/pool/ProxyConnection.java` (parent sha256
`c36ad6ea39c6ac6a8da016196140fe1c2b96750f62229fab92f9223ee905fcb9`, fix `949de5ff9b490a9e9006f99296d70028c0eda6096ea0aa26c19f293c810427ef`);
test `src/test/java/com/zaxxer/hikari/pool/PostgresTest.java` (adds `testSchema`, line 141–166 at the fix) and the new
`src/test/resources/postgres_init_script.sql` (`CREATE SCHEMA IF NOT EXISTS test;`). POM pins PostgreSQL JDBC 42.7.7, Testcontainers 1.20.3, slf4j 2.0.17.

**Commands** (from a worktree, `source $O/scripts/env.sh; export JAVA_HOME=$J17 MAVEN_OPTS=-Xmx1g`):
- jar: `$MVN -Dmaven.javadoc.skip -Dgpg.skip package -DskipTests` (19 s online)
- landed test: `$MVN -o -Dmaven.javadoc.skip -Dgpg.skip test -Dtest='PostgresTest#testSchema' -DforkCount=1 -Dsurefire.failIfNoSpecifiedTests=false '-DsureFireOptions11=--add-modules=ALL-MODULE-PATH -Dapi.version=1.44'`
  (8 s for `testSchema` alone; the whole class, `-Dtest=PostgresTest`, about 2 minutes: one container per test method)
- Don't skip JaCoCo: the surefire `argLine` is `${surefireArgLine} ${sureFireOptions11}` and `surefireArgLine` comes from JaCoCo's `prepare-agent`.
- **Offline form works** (`-o`): the fix's full class, both `testSchema` runs and the parent's package ran offline.

**Docker.** Docker 29.9.3 (server API 1.56, minimum 1.40). **Testcontainers 1.20.3 asks for API 1.32 and is refused**: every test errors with
"Could not find a valid Docker environment"; the debug log shows `Status 400: client version 1.32 is too old. Minimum supported API version is 1.40`
(`$O/logs/M11-HikariCP-fix.test.online.log`). Passing docker-java's `api.version` system property to the test JVM fixes it, through the POM's own
`sureFireOptions11` property on the command line as above (no upstream file changed, no `~/.testcontainers.properties` written).
Images (pulled plainly from Docker Hub; no containers left running):

| Image | RepoDigest |
|---|---|
| `postgres:16` | `postgres@sha256:07abc3f43c9395b0bdbbab36bc25ddb0e8d83cd4fcafb5fb7d6abe14ff156dd8` |
| `testcontainers/ryuk:0.9.0` (pulled by Testcontainers itself) | `testcontainers/ryuk@sha256:448beed1b3fd18e9411dd4b6a26a04f3aa0fccf229502c9665ebe8d628c7d2c5` |

`postgres:16` is a moving tag: this is what it named on 2026-11-25.

**Artifacts.**

| Jar | sha256 |
|---|---|
| `$O/artifacts/M11-HikariCP-parent.jar` | `8956048495adbbf71c4ccb25364be2837a113d74081eea80d4b1682f96565292` |
| `$O/artifacts/M11-HikariCP-fix.jar` | `60608c139c2af9175eee10e844b372c6f34e36b8179dd21be989cd87a694cd70` |
| `$O/releases/HikariCP-7.0.0/lib/HikariCP-7.0.0.jar` | `46001fe1877630269d5a3a0479b650f53b7484abe2e627921f118be5f388bf57` |
| `$O/releases/HikariCP-7.0.1/lib/HikariCP-7.0.1.jar` | `980753e639467d0c2476ef40c306593088f9652ad111aba74ce92126472a0c86` |
| `slf4j-api-2.0.17.jar` (both release sets) | `7b751d952061954d5abfed7181c1f645d336091b679891591d63329c622eb832` |
| `$O/releases/M11-postgres-testcontainers/lib/postgresql-42.7.7.jar` | `157963d60ae66d607e09466e8c0cdf8087e9cb20d0159899ffca96bca2528460` |
| `.../testcontainers-1.20.3.jar` | `e1d89a13d93337e1b14000d6c7c3e8e047fe244db63231134e52fbc1c0ffc5f7` |
| `.../postgresql-1.20.3.jar` (Testcontainers module) | `8c665cd08d156e1df1e44077f3d210ed724a4481a01df282b48628a79baeb9ed` |
| `.../jdbc-1.20.3.jar` | `7bf2bea7503a9fab6165c49f97f81076e8d6a2ab023b2911a3499f40cb7c0b97` |

`ProxyConnection.java` in `HikariCP-7.0.0-sources.jar` equals the **parent's**, in `7.0.1-sources.jar` the **fix's** (digests above). The class
bytes differ from the builds (different compiler), so the releases are equal by source only:

| Class | parent build | fix build | 7.0.0 | 7.0.1 |
|---|---|---|---|---|
| `com/zaxxer/hikari/pool/ProxyConnection.class` | `049a9a9f4104bf7404104b1a5568966bb096f64cfcf4ad20390681f705b0761e` | `3d93d63b71972d16d0a92e5110b7559ecc2f67db4e22d9f5088b6b94faf18b40` | `72b03f1d0bc14f29596cb7a9b8e948431c12d52cf3176215f11beeb975497cd1` | `b2fd004ff55bd008df92cd2ee915e5d0efea0d2d25e97f0c81cd22f7d0ce9e96` |
| `com/zaxxer/hikari/pool/ProxyConnection$ClosedConnection.class` | `20bbae09ed04739df10b5cb5550a8507fd8904d64dd434f68084ceb4f937be63` | `e30d5f7006f27bb12b16bcbcba39678ee0b3aedf7ab4cdaa922136d822c8c813` | `df5a7422a55d9567be850b1dba9c068b1273c707999d118d6929db2fb364d04e` | `beb5623b902f365323a54995e28aa3257c6e802b6795f8677621eec33558a865` |

Runtime classpaths `$O/artifacts/M11-HikariCP-{parent,fix}.classpath.txt` (the jar, slf4j-api 2.0.17, PostgreSQL JDBC 42.7.7). The Testcontainers
graph for a fixture is `$O/releases/M11-postgres-testcontainers/classpath.txt` (it brings slf4j-api 1.7.36; put 2.0.17 first).

**Landed test** (JUnit 4 via surefire; logs `$O/logs/M11-HikariCP-*.log`):

| Run | Result |
|---|---|
| fix's whole `PostgresTest` on the fix (offline, with `api.version`) | 7/7 pass (122 s) |
| fix's `testSchema` alone on the fix | 1/1 pass |
| fix's `PostgresTest` + init script transplanted onto the parent, `testSchema` alone | **fails**: `PostgresTest.testSchema:162 expected:<test> but was:<null>` (the second borrow) |
| parent's own `PostgresTest`, offline (job) | 6/6 pass |
| fix's whole `PostgresTest` + init script on the parent, offline (job) | **1 of 7 fails**: `testSchema`, `expected:<test> but was:<null>` |
| fix's whole `PostgresTest` on the fix again, offline (job) | 7/7 pass |

Worktrees restored clean; build trees removed.

**Job** `20261125-071708-setup-run-hikaricp-s-landed-postgrestest` (`verification/jobs/2026/11/25/20261125-071708-setup-run-hikaricp-s-landed-postgrestest.json`,
written by `$O/scripts/submit_B.py`): offline, JDK 17, the whole `PostgresTest` on the fix (7/7 expected), the parent's own (6 tests), and transplanted onto
the parent (only `testSchema` may fail); summaries `$O/logs/M11-{fix,parent,transplant}-PostgresTest.junit.txt`. **Passed** (3 steps, 7m02s,
peak 724 MiB); every step used `postgres@sha256:07abc3f43c9395b0bdbbab36bc25ddb0e8d83cd4fcafb5fb7d6abe14ff156dd8`. Results in the table above.

**Signatures.** None checked (HikariCP publishes no KEYS file to check a Central signature against); Central checksums were enforced (`--strict-checksums`).

**For the domain agent**
- Any Testcontainers 1.20.3 run on this machine needs `-Dapi.version=1.44` (or another API ≥ 1.40) in the JVM that starts the container.
- Released 7.0.0 / 7.0.1 match parent / fix by `ProxyConnection.java` source; the built jars are the exact pins.
- `postgres:16` resolved to the digest above; pin it by digest for repeatable runs.

### M12 · Apache Commons Pool #85 — destroy an idle object whose validation throws during eviction (pinned source build)

**Pins.** Parent `e405182e6eaabc7422dfd6f65511b7883443b1e9`, fix `1fe14bbb2ea23c98abcfac3019d1daf34568d5ea` (squash; parent = the brief's).
Changed production files: `src/main/java/org/apache/commons/pool2/impl/GenericObjectPool.java`, `.../GenericKeyedObjectPool.java`.
Changed tests: `TestGenericObjectPool` and `TestGenericKeyedObjectPool`, each with one new method `testExceptionInValidationDuringEviction`.

**Build facts.** Maven, single module, `commons-pool2` **2.11.0-SNAPSHOT**, parent `org.apache.commons:commons-parent:52`, source/target 1.8.
`pom.xml` identical at both pins. Built on **JDK 8u512** (`$J8`) with Maven 3.10.0. Runtime dependencies: none required
(`cglib:cglib:3.3.0`, `org.ow2.asm:asm-util:9.1` and their deps are optional; tree in `$O/logs/M12-commons-pool-fix.tree.txt`).

**Commands** (`$SK` as in M06; `$O/scripts/forkA_mvn.sh`):
- online: `JAVA_HOME=$J8 $MVN -Daether.connector.basic.threads=1 $SK -DforkCount=1 -Dtest='TestGenericObjectPool#testExceptionInValidationDuringEviction,TestGenericKeyedObjectPool#testExceptionInValidationDuringEviction' -Dsurefire.failIfNoSpecifiedTests=false package` (25 s)
- **offline (checked; 3–45 s)**: the same with `-o`.
- The full classes were not run: they are long timing suites. The parent's own `testEvict*` methods (16) were run as a sanity check of the offline build.

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M12-commons-pool-parent.jar` | `bca9b8d0445f48009cd4de2bc2997ad6ee3ae467ddaa75e8779d1d62a5668720` |
| `M12-commons-pool-fix.jar` | `b403efa88c1913db335822aab4ee8d84a90a04d08db31268e307c5e3dc05bcf3` |

| Class | parent | fix |
|---|---|---|
| `org/apache/commons/pool2/impl/GenericObjectPool.class` | `9911707da62dd3d3534654cffc01b05a7532774fdbe0d106ef93c8fc9418e94b` | `6a0f94031e3b8315aad2bda30fd0e005e7cdd6f656700db064df40b009aaf654` |
| `org/apache/commons/pool2/impl/GenericKeyedObjectPool.class` | `464be9df3900df51e5b3102115455a8e7011628d9bf61c9ff5a9d59149c468bc` | `de5a79541577befe263283bb43f273d32e104425c5de7466656a85d850201137` |
| `org/apache/commons/pool2/impl/GenericKeyedObjectPool$ObjectDeque.class` | `2bb2a16ef4fb7f33ee50559c9c16b8ea3949fa23469ed62d9418341ae0cf79bb` | the same |

**Releases** (`$O/releases/commons-pool2-{2.10.0,2.11.0}/`, resolved with `--strict-checksums`): neither release's source equals either pin byte for
byte (other changes landed around them). By content: **2.10.0 lacks the eviction fix** (one `validationThrowable = t` site per pool, as the parent),
**2.11.0 has it** (two per pool, as the fix).

| Jar | sha256 |
|---|---|
| `commons-pool2-2.10.0.jar` | `d80021de162f9570252b281ddf6f5e2ad876f0c196f4d1dbe85ab0a5b0dca554` |
| `commons-pool2-2.11.0.jar` | `31af2abdeb99828136a020c7352c1f47711dae70b8470069978d6ce31ff6bcf6` |

**Landed tests** (upstream Maven build, JDK 8; logs `$O/logs/M12-*.log`):

| Run | Result |
|---|---|
| fix, the two new methods (online, then offline) | 2/2 pass |
| parent, its own `testEvict*` methods (offline) | 16/16 pass |
| fix's two test files on the parent, the two new methods (offline) | **2 failures**: `TestGenericObjectPool:1733` and `TestGenericKeyedObjectPool:1580`, `getNumIdle()` expected `<0>` but was `<1>` |

**Signatures.** Both release jars: Central `.asc` verified against the Commons KEYS (`$O/keys/commons-KEYS`): good signatures by
`2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory, code signing key; the POM's `commons.releaseManagerKey` `86fdc7e2a11262cb`).

**Jobs.** None.

**For the domain agent**
- JDK 8 builds it; the pins' jars are in `$O/artifacts/` and need no other jar at run time.
- The parent's landed failure is the stranded idle object (idle count 1 after the exception), as in POOL-396.

### M13 · RxJava #6019 — dispose the other subscription in Single/Maybe takeUntil (upstream Gradle 4.2.1 build at both pins, inline; one init script for four jcenter-only plugin dependencies)

**Pins.** Parent `b9f5ef81237b16cb3d30d404740fb3ebf0511ed3`, fix `07e126f030a34d25b23c476fdb24384deb028c63` (squash on `2.x`, parent = the brief's).
Worktrees `$W/M13-RxJava-parent`, `$W/M13-RxJava-fix`. Changed production files (one line each):
`src/main/java/io/reactivex/internal/operators/single/SingleTakeUntil.java`, `src/main/java/io/reactivex/internal/operators/maybe/MaybeTakeUntilPublisher.java`.
Changed tests (`src/test/java/io/reactivex/internal/operators/…`): `single/SingleTakeUntilTest`, `maybe/MaybeTakeUntilTest`,
`completable/CompletableAmbTest`, `flowable/FlowableTakeUntilTest`, `observable/ObservableTakeUntilTest`.

**Build facts.** Gradle 4.2.1 (`$O/tools/gradle-4.2.1`, the wrapper's version; zip checked, see the toolchain table). The repository's
`gradle-wrapper.jar` `53aa048fef3c06a8442c6a44df5edd2e8c791ee883e42ded6189c7eed112095d` (both pins) equals services.gradle.org's published wrapper jar
for Gradle 4.2 (`$O/dl/gradle/wrapper-C/gradle-4.2-wrapper.jar.sha256`). **JDK 8** (`$J8`, 8u512): Gradle 4.2.1 does not run on later JDKs.
`sourceCompatibility`/`targetCompatibility` 1.6. Version `2.2.0-SNAPSHOT` (`gradle.properties`), so the jars are `rxjava-2.2.0-SNAPSHOT.jar`.
Runtime dependency: `org.reactivestreams:reactive-streams:1.0.2` only. Tests: JUnit 4.12, Mockito 2.1.0, `maxHeapSize = "1200m"`; without the `CI`
environment variable the build forks `availableProcessors/2` test JVMs, so the commands set `CI=true` (one fork).

**Substitution (build-script classpath only).** The build script's repositories are `jcenter()`, `mavenCentral()` and the Plugin Portal.
jcenter.bintray.com no longer serves four transitive dependencies of the publishing plugins (`gradle-bintray-plugin:1.7.3`,
`build-info-extractor-gradle:4.5.2`), and neither Central nor the Plugin Portal has them. The setup copied the **same coordinates** from JFrog's public
jcenter mirror (`https://releases.jfrog.io/artifactory/jcenter`) into the file repository `$O/dl/m13-substitute-repo`, each pom and jar checked
against the mirror's `.sha1` (`$O/scripts/m13_add_module.sh`, log `$O/logs/M13-substitute-repo.txt`), and the two first jars also against a second
source. `$O/scripts/rxjava-jcenter-substitute.init.gradle` adds that file repository to the build-script repositories; the upstream build files are
unchanged. (Adding the JFrog mirror itself as a repository failed: it answers 401 for jars it has not cached, such as `jackson-annotations-2.8.0.jar`.)

| Module | jar SHA-1 (= published) | jar sha256 | Second source |
|---|---|---|---|
| `org.codehaus.groovy.modules.http-builder:http-builder:0.7.2` | `323092cd786480311c1cf693770f9e6fc20a8bef` | `cbd0fa43ebc62cb548e17f78b92b745220d9b1904f255c5916ef5a592b11e090` | repo.grails.org `.sha1` equal |
| `org.jfrog.buildinfo:build-info-extractor:2.8.2` | `81999cbb9550b22bab79672c3d3b4bb1da98fa81` | `2d9be3f328a266d224f2bd7c294a71598f1276a305489855d194611844042878` | releases.jfrog.io `oss-release-local` `.sha1` equal |
| `org.jfrog.buildinfo:build-info-client:2.8.2` | `cf64685e65904b39c28ac31554bcc63471f43aad` | `27b035bdf38d88dd7c302e4e431d399b5c369a49fbed4e3aba0e38a024e98d8b` | — |
| `org.jfrog.buildinfo:build-info-api:2.8.2` | `09ade14380d2e088250c4bca8fe4a5d3cb3753f0` | `1018f511fd2303a1f9bb006a787c5e9ecd05f34ee44c2c64674ba3b556f239b0` | — |

They are only on the build-script classpath of publishing plugins; nothing compiled or tested uses them.

Commands (the first run online, which also fetched `org.jacoco.agent:0.8.0` for `test`; every later run offline; each under 15 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links/scripts/env.sh; export JAVA_HOME=$J8 CI=true
cd $W/M13-RxJava-fix   # or M13-RxJava-parent
$O/tools/gradle-4.2.1/bin/gradle --no-daemon --offline --console=plain --max-workers=2 -Dorg.gradle.jvmargs=-Xmx1536m \
  -I $O/scripts/rxjava-jcenter-substitute.init.gradle jar cleanTest test $(cat $O/scripts/M13-tests.txt)
python3 -I $O/scripts/junit_summary.py build/test-results/test
git clean -fdxq   # afterwards
```

`$O/scripts/M13-tests.txt` holds the five `--tests` filters (the five changed test classes).

**Landed tests** (JDK 8u512):

| Run | Result |
|---|---|
| fix, the five changed test classes (online, then offline) | 108/108 pass |
| parent, its own copies (offline) | 60/60 pass |
| the fix's five test files transplanted onto the parent (offline, restored after) | **4 of 108 fail**: `SingleTakeUntilTest#untilPublisherDispose`, `SingleTakeUntilTest#untilSingleDispose`, `SingleTakeUntilTest#untilCompletableDispose`, `MaybeTakeUntilTest#untilPublisherOtherOnNext` |

Logs: `$O/logs/M13-RxJava-fix.{jar-online,testClasses-online,test-online,test-offline}.log`, `$O/logs/M13-RxJava-parent.{test-offline,transplanted.test-offline}.log`;
summaries `$O/logs/M13-RxJava-{fix,parent,parent.transplanted}.junit.txt`. Worktrees restored and cleaned.

**Artifacts** (Gradle 4 jars carry timestamps: bind the class digests):
- `$O/artifacts/M13-RxJava-parent-rxjava.jar`: `c5002ea239fe1f681783364ed769008b4349631bdc878f9aef705995592d079e`
- `$O/artifacts/M13-RxJava-fix-rxjava.jar`: `b776a89151ed5abd2e123cf160819af6d7eee0ef98780ccb034724da28409f47`

| Class (`io/reactivex/internal/operators/…`) | parent | fix |
|---|---|---|
| `single/SingleTakeUntil.class` | `0ca4472364afcb8d6786f3fa115c00dad9704a8573652835078ca1b11e36a751` | the same |
| `single/SingleTakeUntil$TakeUntilMainObserver.class` | `c2764b46d50e5f804d347e3010086c303179a56a29896d12f59bb3d0d652ef85` | `657e9ae1e995e9b7e8ab29afd73fd4f856c81bc9c3b91ad9878939d860fd035d` |
| `single/SingleTakeUntil$TakeUntilOtherSubscriber.class` | `98ad953c1a284e6bc8bb11e5ce50e34dc2d7a003924d1711ff0fe2732e0db2f0` | `a787d94ff27edbcd02a3d4b3665cb3fec8f20105c06d5f4b0a2f2013f51b0680` |
| `maybe/MaybeTakeUntilPublisher.class` | `f5a942d53b64176dd99c522a4f072d5759328eafafd0f660ad3019f1bfaae1f7` | the same |
| `maybe/MaybeTakeUntilPublisher$TakeUntilMainMaybeObserver.class` | `e316a9a5d69468805ec108df4b23a3d3a194be2697edaf9e08c07ea9690ac54f` | the same |
| `maybe/MaybeTakeUntilPublisher$TakeUntilMainMaybeObserver$TakeUntilOtherMaybeObserver.class` | `f41a18aba0db24cee6eb9a3513f2e1d0546146f2b841571ba33d236723fa90c4` | `00e506b38445b7dbb0c0088995d37be96cea9f34ae305a7788076114912fa035` |

Runtime classpath of either pin jar: `reactive-streams-1.0.2.jar` (`cc09ab0b140e0d0496c2165d4b32ce24f4d6446c0a26c5dc77b06bdf99ee8fae`, in either release set below).

**Releases** (`resolve.sh`, strict checksums). Both changed files compared by sha256 with each side:

| Set (`$O/releases/…`) | Jar sha256 | Changed sources equal |
|---|---|---|
| `rxjava-2.1.14` | `rxjava-2.1.14.jar` `19714a1d644f01f2d4175a02e92ad8494faa5eb35d696695adf3b3d1251c1857` | **parent** (`SingleTakeUntil.java` `5e4d1ac9e1d529811fa0e6e5444f1152e791f4b223db7aeed85f0838bb223226`, `MaybeTakeUntilPublisher.java` `d60c9103cf6b3559be6be92bb4033a91849902affe68b0a8c688ce5a9cf81ab7`) |
| `rxjava-2.1.15` | `rxjava-2.1.15.jar` `52aa61ba6f08cf06c500c6d2cfd6dff91d5b185bfd9d17778835552f902337bf` | **fix** (`79d0e51b38fe270bb8673e9530d5a9d229d5bfb3d0e3a04dcd28042a69a7b017`, `06b567bb759a7dfb1e7d98b68da27ad28127b7bb1bd5e74c33d365f0621a7ade`) |

Each set's `classpath.txt` is the rxjava jar and reactive-streams 1.0.2. Only the two changed files were compared; the releases differ from the pins elsewhere.

**For the domain agent**
- Pin jars: `$O/artifacts/M13-RxJava-{parent,fix}-rxjava.jar` plus reactive-streams 1.0.2. Releases 2.1.14 (parent side) and 2.1.15 (fix side) are a published pair for the two changed files.
- Gradle 4.2.1 needs JDK 8 and the init script; set `CI=true` or the test task forks 15 JVMs.
- The brief's claim scenarios were not run.

### M14 · Reactor Core #3822 — exact Set buffers under bounded demand (upstream Gradle 8.5 build at both pins, inline; JDK 9.0.4 fetched for the multi-release jar)

**Pins.** Parent `6b71ff09efba7acc06feffe7dca2d80f1538b024`, fix `e58658d16daa89f521a6b0b78f0d1ce6fbabd238` (squash of 11 PR commits on `main`, parent = the brief's).
Worktrees `$W/M14-reactor-core-parent`, `$W/M14-reactor-core-fix`. Changed production files:
`reactor-core/src/main/java/reactor/core/publisher/FluxBuffer.java` (+9/−6) and `reactor-core/src/main/java/reactor/core/publisher/Flux.java` (+7, Javadoc only).
Test: `reactor-core/src/test/java/reactor/core/publisher/FluxBufferTest.java` (+37/−1). Nothing under `reactor-test/` differs between the pins.

**Build facts.** Version `3.7.0-SNAPSHOT`. Gradle 8.5 (`$O/tools/gradle-8.5`, the wrapper's version); the repository's `gradle-wrapper.jar`
`d3b261c2820e9e3d8d639ed084900f11f4a86050a8f83342ade7b6bc9b0d2bdd` (both pins) equals services.gradle.org's published wrapper jar for 8.5
(`$O/dl/gradle/wrapper-C/gradle-8.5-wrapper.jar.sha256`). `reactor-core` is a multi-release jar (`me.champeau.mrjar`, `targetVersions 8, 9, 21`),
so the build needs **Java toolchains 8, 9 and 21**. Upstream CI (`.github/workflows/ci.yml`) runs Gradle on Temurin 8 after installing
AdoptOpenJDK `OpenJDK9U-jdk_x64_linux_hotspot_9.0.4_11.tar.gz` and Temurin 21; the setup does the same:
- JDK 9.0.4+11 fetched from AdoptOpenJDK's GitHub release `jdk-9.0.4+11` (`AdoptOpenJDK/openjdk9-binaries`), sha256
  `aa4fc8bda11741facaf3b8537258a4497c6e0046b9f4931e31f713d183b951f1` = the release's `.sha256.txt`; tarball in `$O/dl/jdk9/`, unpacked at
  `$O/tools/jdk9/jdk-9.0.4+11` (`$J9` in `env.sh`).
- The settings apply the foojay toolchain resolver; the commands turn auto-download and auto-detection off and name the cache's JDKs.

Repositories: Central and the Plugin Portal serve everything the build and `FluxBufferTest` need. The build also lists `repo.spring.io`
(`plugins-release`, `release`, `snapshot`, `milestone`) and `oss.sonatype.org`; none of them was needed, so no substitution was made.

Commands (`$O/scripts/M14-gradle.sh` wraps Gradle 8.5 with `JAVA_HOME=$J8`, `--no-daemon --console=plain --max-workers=2`,
`-Dorg.gradle.jvmargs=-Xmx1536m`, `org.gradle.java.installations.auto-download=false`, `auto-detect=false` and
`org.gradle.java.installations.paths=$J8,$J9,$J11,$J17,$J21,$J25`). The first `jar`, `testClasses` and `test` ran online; every later run offline,
each 10–30 s:

```bash
cd ~/.cache/in-the-loop/merged-pr-links/worktrees/M14-reactor-core-fix   # or M14-reactor-core-parent
~/.cache/in-the-loop/merged-pr-links/scripts/M14-gradle.sh --offline :reactor-core:jar :reactor-test:jar \
  :reactor-core:cleanTest :reactor-core:test --tests reactor.core.publisher.FluxBufferTest
python3 -I ~/.cache/in-the-loop/merged-pr-links/scripts/junit_summary.py reactor-core/build/test-results/test
git clean -fdxq   # afterwards
```

**Landed test** (JUnit Jupiter on the Gradle JVM, JDK 8u512):

| Run | Result |
|---|---|
| fix, `FluxBufferTest` (online, then offline) | 84/84 pass |
| parent, its own `FluxBufferTest` (offline) | 77/77 pass |
| fix's `FluxBufferTest.java` transplanted onto the parent (offline, restored after) | **3 of 84 fail**, all rows of the new `bufferExactSupplierUsesSet(String, String, String)`: `[2] input=1\|1\|1, output=1, discard=1\|1`, `[3] input=1\|1\|2, output=1\|2, discard=1`, `[6] input=1\|1\|2\|3, output=1\|2;3, discard=1` |

Logs: `$O/logs/M14-reactor-core-fix.{jar-online,testClasses-online,test-online,test-offline}.log`, `$O/logs/M14-reactor-core-parent.{test-offline,transplanted.test-offline}.log`;
summaries `$O/logs/M14-reactor-core-{fix,parent,parent.transplanted}.junit.txt`. Worktrees restored and cleaned.

**Artifacts** (Gradle 8.5 jars keep timestamps: bind the class digests):
- `$O/artifacts/M14-reactor-core-parent-reactor-core.jar`: `4bb1b9161898d3ffb6898e380089d99357b849dc17732e7e1d51107f85b6a74f`
- `$O/artifacts/M14-reactor-core-fix-reactor-core.jar`: `232ed5d351231bda8573a14cc600f0594bf938bf0e64cdf062c429e267bda575` (multi-release: 19 `META-INF/versions` entries)
- `$O/artifacts/M14-reactor-core-fix-reactor-test.jar`: `e85a43384fced8fd520359c72a6259fdf59fba148c63def7a96af8febe3d0cb7` (reactor-test 3.7.0-SNAPSHOT built at the fix; its sources are identical at the parent)

| Class (`reactor/core/publisher/…`) | parent | fix |
|---|---|---|
| `FluxBuffer.class` | `747313fa2e69341a81916796efc375154f51d852a696db9364cd20e0fd7defa8` | the same |
| `FluxBuffer$BufferExactSubscriber.class` | `bbf002da0486ff7c6ec049531a683a5dda9e5e41c0418bc0afe04726e1e6f4b2` | `761658bc35209057fa64e5859cf5585af253f826e049be5b3dea0428ccf651aa` |
| `FluxBuffer$BufferOverlappingSubscriber.class` | `f1d424471bf7794912bc51f7e7dc5760e8fd72d47b718ac3f0cb6bbdcc619106` | `f74c60c26187d365efbe66f680a9903ee46d102d2024a432f5c720f389759d95` |
| `FluxBuffer$BufferSkipSubscriber.class` | `220b2056d62fa3a517da988cf5336f8cc0caa8d0aab0cf6d6cef3a12a71be633` | `dfb71c02df9d0e4477787cda75a01913f4a0e7a1f29c21f91b9e5d4e50517135` |
| `Flux.class` | `faae00597a3ccb96eddb7778335207d2ee505b1a038a71a119a534f975966a4b` | `550f74daeec20bc9a7f64253dade239c905806080fd216caff743e75fd1b3fca` |
| `Flux$1.class` | `8dccd342a66e432f2b0d22bc6fd0d38304b1eeb3fbef56cff4293094fa4989b8` | the same |
| `Flux$2.class` | `470315362497466123b15a10b105e52227d0ec59bc4da1e622c8a75b3f72b9c5` | `e89bea5186c21f56f806928ae9ed152e0c086c9d717ebc10cb2f705e31f6e379` |
| `Flux$3.class` | `38f323de9c831eaf2d7bc9a89e05b6941b4f8c3fe257d0292b687fdc0033e265` | `0fd090f95d42ed2fa5ddf98724a986e58197b6e382334a8b7936739fe2c73f30` |
| `Flux$4.class` | `dffb1bccb7047fedf262fa3b7d5e8ef9a830c64c8bce2403955fb60d85091a7c` | `b0731e09dfd9312feb3f486e03994c77173849f022aee64bd3696a24874efb36` |
| `Flux$5.class` | `b2abc9bc304d2d2f818f2eb32710d0465d51476851ca17563966e90d3867b835` | `19e3fe6b749ad6cfa30b4362fcabc5e5fa27230d6f841e2c8426695f03494c05` |

(`Flux` and its anonymous classes differ only through line numbers: the `Flux.java` change is Javadoc.)
Runtime classpath of the pin jars: `org.reactivestreams:reactive-streams:1.0.4` only (`reactive-streams-1.0.4.jar`
`f75ca597789b3dac58f61857b9ac2e1034a68fa672db35055a8fb4509e325f28`, in the release sets below).

**Releases** (`resolve.sh`, strict checksums). The 3.7.0 milestones (M5–M7) are not on Maven Central (they were on repo.spring.io/milestone).

| Set (`$O/releases/…`) | Jar sha256 | Changed sources equal |
|---|---|---|
| `reactor-core-3.6.10` | `reactor-core-3.6.10.jar` `b1b447164454508b0382def6921492247484c5dfc044094c1eb9735e97a1ba33` | `FluxBuffer.java` = **parent** (`78f9f5a04f28ed00e0004914caf3716b4759863f1b9867cee090b3cd8663e9c1`); `Flux.java` neither (3.6.x line) |
| `reactor-core-3.7.0` | `reactor-core-3.7.0.jar` `14aebad4882def1f88389656cf9b46177f6b090bb00a0707025d76aeacaaead2` | both = **fix** (`FluxBuffer.java` `bc7b742462ba549590f288e40600ac42a0170e5d7467efa152080ab5ba40db6e`, `Flux.java` `21f63227dcffa72f91bc222a4db67f345443c022deeecead2f8d4d22530d31dc`) |
| `reactor-test-3.7.0` | `reactor-test-3.7.0.jar` `55d44ca4746a0622bd30988a2e3d23f18188d4cdf27d2d9e73e26ee25e7e59ec` (+ reactor-core 3.7.0, reactive-streams 1.0.4) | — (`StepVerifier`) |

**For the domain agent**
- Pin jars: `$O/artifacts/M14-reactor-core-{parent,fix}-reactor-core.jar`, with reactive-streams 1.0.4 and, for `StepVerifier`,
  `$O/artifacts/M14-reactor-core-fix-reactor-test.jar` (valid with either side). 3.7.0 is a published fix-side release; no published release has the parent's two files exactly.
- A rebuild needs JDK 9 (`$J9`) and 21 as toolchains: use `$O/scripts/M14-gradle.sh`.
- The brief's claim scenarios were not run.

### M15 · Logback #862 — write the header to each file opened by rollover (pinned source build of `logback-core`)

**Pins.** Parent `91961ad72a1416185abe260c4d56a0762a452223`, fix `42caff87ae6eb553dcbf77e25ba87a9d340357ee` (squash; parent = the brief's).
Changed production file: `logback-core/src/main/java/ch/qos/logback/core/OutputStreamAppender.java` (`setOutputStream` now calls `encoderInit()`).
Changed test: `logback-core/src/test/java/ch/qos/logback/core/rolling/RollingFileAppenderTest.java` (new `testHeaderFooterWritten`).

**Build facts.** Maven multi-module, `ch.qos.logback` **1.5.9-SNAPSHOT**, `jdk.version` 11 (`maven.compiler.release` 11), but `logback-core` also
has a `java21-compile` execution (multi-release jar, `META-INF/versions/21/`), so **the build needs JDK 21** (`$J21`; JDK 17 fails with
"release version 21 not supported"). Root and `logback-core` POMs identical at both pins. Surefire 3.0.0-M7, configured with
`--add-opens …testUtil=java.naming --add-reads ch.qos.logback.core=ALL-UNNAMED`, `parallel=classes`, `forkCount=5`.
`logback-core` has no required runtime dependency (janino 3.1.8, commons-compiler, jansi 2.4.0, jakarta.mail-api 2.1.0, jakarta.servlet-api 5.0.0
are all optional; tree `$O/logs/M15-logback-core-fix.tree.txt`; their paths in `$O/artifacts/M15-logback-core-fix.runtime-classpath.txt`).
Jar entries carry the fixed date 2024-09-07 (`project.build.outputTimestamp`).

**Commands** (run in `logback-core/`; `$SK` as in M06; `$O/scripts/forkA_mvn.sh WT logback-core …`):
- online: `JAVA_HOME=$J21 $MVN -Daether.connector.basic.threads=1 $SK -DforkCount=1 -Dtest=RollingFileAppenderTest -Dsurefire.failIfNoSpecifiedTests=false -Dsurefire.useModulePath=false package` (9 s)
- **offline (checked, 4–6 s)**: the same with `-o`.
- **`-Dsurefire.useModulePath=false` matters**: with the module path (surefire's default here) the three methods `RollingFileAppenderTest`
  inherits from `AbstractAppenderTest` (`testConfiguredAppender`, `testNoStart`, `testNewAppender`) error on **both** pins with
  `InaccessibleObjectException` (module `ch.qos.logback.core` does not open `ch.qos.logback.core.appender`). That is environmental, the same at both
  pins; on the class path all of them pass. Both forms' logs are kept (`M15-*.offline.log` and `M15-*.offline.nomodulepath.log`).

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M15-logback-core-parent.jar` | `df9d9a586a4f1535400e9e4e6ad3b966abed3150c8ea81b822294231ddab166a` |
| `M15-logback-core-fix.jar` | `6c840cf26564c0a454f4f383a3af0e481e3061f376cfeda2b895373cb503b804` |
| `ch/qos/logback/core/OutputStreamAppender.class` (parent) | `1c6cb25106edec490bd180073bc09539539b6e106958176e37f65f5332462e1f` |
| `ch/qos/logback/core/OutputStreamAppender.class` (fix) | `db289ec0a6d610f77649fa7a71ffbe02a4cb9702dabe7ba7c9d4160093966a63` |

**Releases** (`$O/releases/logback-core-{1.5.8,1.5.9}/`, `--strict-checksums`; the release sources have CRLF line ends, so compare with
`diff --strip-trailing-cr`):
- **1.5.8 `OutputStreamAppender.java` = the parent's code**, differing only in two comments.
- **1.5.9 is not the fix**: it guards the new call, `if(isStarted()) { encoderInit(); }`, where the fix calls `encoderInit()` unconditionally.
  So 1.5.9 is a later variant of the change, not a stand-in for the fix pin.

| Jar | sha256 |
|---|---|
| `logback-core-1.5.8.jar` | `a698e4cff3eac45eec9b2755df93bb7a9725d853f7938030654ce5430b37c41d` |
| `logback-core-1.5.9.jar` | `270be5e97720665d09c60bde038ff0a1e711019a71d6582f85a90dd33711aba7` |

**Landed tests** (`RollingFileAppenderTest`, upstream Maven build, JDK 21; logs `$O/logs/M15-*.log`):

| Run | class path (`useModulePath=false`) | module path (default) |
|---|---|---|
| fix, its own (online/offline) | 14/14 pass | 14 run, 3 errors (the inherited three, above) |
| parent, its own (offline) | 13/13 pass | 13 run, 3 errors (the same three) |
| fix's test file on the parent (offline) | 14 run, **1 failure**: `testHeaderFooterWritten` ("At least 2 lines per file are expected in target/test-output/header-0.log", `RollingFileAppenderTest.java:317`) | 14 run, the same failure plus the inherited three |

**Signatures.** Both release jars: Central `.asc` verified, good signatures by `60200AC4AE761F1614D6C46766D68DAA073BE985` (Ceki Gulcu), key fetched
from keyserver.ubuntu.com by key id (`$O/keys/key-66D68DAA073BE985.asc`), no further trust path.

**Jobs.** None.

**For the domain agent**
- JDK 21 to build; run with `java -cp $O/artifacts/M15-logback-core-ROLE.jar ...` (no other jar needed for `RollingFileAppender` with a custom encoder).
- Don't take 1.5.9 for the fix: its `setOutputStream` differs (the `isStarted()` guard), which bears on the brief's remark about `headerBytes()` before start.

### M16 · jOOQ #19875 — Loader static-statement batches (overlay over jOOQ 3.21.2; release pair 3.21.2/3.21.3; upstream build by job)

**Pins.** Parent `fe798c2c9296d13d32e469f60b26778ebc1ac1c4`, fix `1a3575be9bf33f3e3f022226d7fd6869a8874e63` (two-parent merge; first parent = the brief's).
Also pinned: `5a98d74deb44ca78838d4b62e376dbc4a704cc0f`, the reporter's separate commit with `jOOQ/src/test/java/org/jooq/impl/LoaderBatchStaticStatementTest.java`
(sha256 `8f428aca1a63d12b13e3f7466e0d463339eccab7f6d140e8dc25727c97510c0e`; worktree `$W/M16-jOOQ-reporter-test`); that commit's `jOOQ/pom.xml` adds an H2 test dependency,
`${h2.version}` = **2.4.240**, and JUnit is 4.13.2. The pins are **3.22.0-SNAPSHOT**, `<java.version>21`; `pom.xml` and `jOOQ/pom.xml` are identical at both pins and
declare no H2. Changed: `jOOQ/src/main/java/org/jooq/impl/LoaderImpl.java` (parent `da807b98283439b3f93101ac272607b5365fafb625dd10343e3a362e8aef0f52`, fix
`4ac0f2a6db414c477ac8156c72e1010e145e4dfc2a4fece874cac1331d4f04a1`; the batch bind now collects values with `new ParamCollector(ctx.configuration(), true)`) and a credit line
in `META-INF/ABOUT.txt`. **The PR adds no test.**

**Release set.** `org.jooq:jooq` 3.21.0–3.21.10 exist on Central. `LoaderImpl.java` in the sources jars (sha1 checked, `$O/dl/central/jooq-3.21.{1,2,3}-sources.jar`):
3.21.1 and **3.21.2 = the parent's file byte for byte**; **3.21.3** (`44183ab042c59e98f6acf69af3bf3b9272c7d41c863222a7261c6f48a2054394`) = the fix's code with a different
two-line comment. `ParamCollector.java` in 3.21.2 equals the fix pin's.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `jooq-3.21.2` | `jooq-3.21.2.jar` (class major 65) | `3f48acd1cb53cefeac0c006749dd4086510b863df669b973f762e6949761524c` |
|  | `r2dbc-spi-1.0.0.RELEASE.jar` | `a5846c59fea336431a4ae72ca14edbf5299b78486fa308eafb383f4ae0ea74e5` |
|  | `reactive-streams-1.0.3.jar` | `1dee0481072d19c929b623e155e14d2f6085dc011529a0a0dbefc84cf571d865` |
| `M16-testdeps` | `h2-2.4.240.jar` | `29b70e427cc1c40cdc376283adbb0cc62853073797bb5fe5761f81fe73d57ce0` |
|  | `junit-4.13.2.jar` | `8e495b634469d64fb8acfa3495a065cbacc8a0fff55ce1e31007be4c16dc57d3` |
|  | `hamcrest-core-1.3.jar` | `66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9` |
| `M16-compile-only` (overlay compile only) | `annotations-26.0.2.jar` (org.jetbrains, the pins' `jetbrains.annotations.version`) | `2037be378980d3ba9333e97955f3b2cde392aa124d04ca73ce2eee6657199297` |

**Overlay** (javac 21.0.13 `--release 21` over `jooq-3.21.2` + `M16-compile-only`; both sides compile unchanged):
- `$O/artifacts/M16-jOOQ-parent-overlay.jar`: `3fb579331a2215c942e3a174de7e0bfd8297afaf32a2cd1a5c522b60e4f83f0e`
- `$O/artifacts/M16-jOOQ-fix-overlay.jar`: `57c12e79948b9a75501f333c2b4f18660b5809956841c9856ae677d8b8ef8f74`

| Class | parent overlay | fix overlay |
|---|---|---|
| `org/jooq/impl/LoaderImpl$1.class` | `7c7ecaa2cde314645c1f1bccc9fd57f7243e5e48422847dcf2189a4661b83c83` | the same |
| `org/jooq/impl/LoaderImpl$CachedPS.class` | `6f980775a39b8a5cb0d8cafec717485964b5afe98c45c66892fdd0b7befb27bb` | the same |
| `org/jooq/impl/LoaderImpl$CachedPSListener.class` | `0556da75867d05c628895d79bc7ee7b995ee408dfc83a0b49dbeee81a95f6963` | the same |
| `org/jooq/impl/LoaderImpl$DefaultLoaderContext.class` | `450740e5ccb64162a8919c66d7b3311408adfd1c36d623fdb5836d7bc475a4fc` | `85c4b8d20aa2db2261a0631013832bea4aa4e03b52323d92092e402cd23db680` |
| `org/jooq/impl/LoaderImpl.class` | `eff333790ceab113a446cd27215538b04a66f51fce547c374fbc0bf3bf7e2fab` | `c1efbad904011290e5c51c67ba64626b3b51a94f2c34efcc6796a7ead4359161` |

Use: `java -cp $O/artifacts/M16-jOOQ-SIDE-overlay.jar:$(cat $O/releases/jooq-3.21.2/classpath.txt):$(cat $O/releases/M16-testdeps/classpath.txt) ...`.

**Reporter's test over the overlays** (JUnitCore on JDK 21.0.13; an overlay run):

| Run | Result | Log |
|---|---|---|
| on the fix overlay | 2/2 pass | `$O/logs/M16-overlaytest-reportertest-on-fix.log` |
| on the parent overlay | **1 of 2 fails**: `testLoaderBatchAllWithStaticStatement`, `AssertionError: Expected Bob, got: [Alice, Alice, Alice]`; the PREPARED_STATEMENT test passes | `$O/logs/M16-overlaytest-reportertest-on-parent.log` |
| on jooq 3.21.2 alone (no overlay) | same as the parent overlay | `$O/logs/M16-overlaytest-reportertest-on-3.21.2.log` |

**Upstream build: job `20261125-071415-setup-build-jooq-at-both-19875-revisions`** (`$O/scripts/submit_D.py jooq`). Per pin, from the worktree on JDK 21 with
`MAVEN_OPTS='-Xmx2g -Duser.home=$O/mvnhome'`: `$MVN [-o] -Daether.connector.basic.threads=1 -pl jOOQ -DskipTests -Dmaven.javadoc.skip=true package`, then
`$MVN [-o] -q -pl jOOQ dependency:build-classpath -Dmdep.includeScope=runtime -Dmdep.outputFile=…`, then the reporter's test compiled and run against
`jOOQ/target/jooq-3.22.0-SNAPSHOT.jar` + that classpath + `M16-testdeps` (outside Maven, since the upstream POM has no H2 and is left unchanged). Fix online,
parent offline (expected 1 failure), fix again offline; jars to `$O/artifacts/M16-jOOQ-{fix,parent}-jooq.jar`. Inline only `-pl jOOQ validate` ran (2 s, passed).
**Passed** (4 steps, 2m41s, peak 1.2 GiB):

| Run (pin jars) | Result | Summary |
|---|---|---|
| reporter's test over the fix jar, online build | 2/2 pass | `$O/logs/M16-fix.online.{junit,mvn-log}.txt` |
| over the parent jar, offline build | **1 of 2 fails**: `testLoaderBatchAllWithStaticStatement`, `AssertionError: Expected Bob, got: [Alice, Alice, Alice]` | `$O/logs/M16-parent.offline.*` |
| over the fix jar rebuilt offline | 2/2 pass | `$O/logs/M16-fix.rerun.offline.*` |

Jars (`jooq-3.22.0-SNAPSHOT.jar`): `$O/artifacts/M16-jOOQ-parent-jooq.jar` `36675677bc26e1c638038c090d32f061bfe7b9107464afc219b77800318ff73d`,
`$O/artifacts/M16-jOOQ-fix-jooq.jar` `a2b8068040468c84e5ddefe4057b62d793c943ca58bb2c656f77f9e54d8bc09a` (the offline rebuild, which
replaced the online build's `41af58aa3104800426832508d586e184dd2508a9da19cf20a37c8d5aa5a0993a`: the jOOQ jar is **not byte-reproducible**
between builds of one pin, so compare classes, not jars). Runtime classpath, identical for both pins:
`$O/logs/M16-{fix,parent}-runtime-classpath.txt` (sha256 `7b92a648130e42b34080a0ba6e234ba6aebaf529cab97e50cf11a626f9f34ee0`), plus
`M16-testdeps` for the test. Changed classes in the jars (`$O/logs/M16-jOOQ-jobjar-classes.md`):

| Class | parent jar | fix jar |
|---|---|---|
| `org/jooq/impl/LoaderImpl$1.class` | `1fa8e9c3862d4f8cd1aca10d556cc62783342e53b38327756285994db87c409d` | the same |
| `org/jooq/impl/LoaderImpl$CachedPS.class` | `691b014e04f32f570275761c44545ed468efa39aa6d8b5371df42361326d3fe1` | the same |
| `org/jooq/impl/LoaderImpl$CachedPSListener.class` | `fc81364bf228fe77d4e5ac8e3089a7fd8ce06ddccc7bb9f6dcf0259d7902be7d` | the same |
| `org/jooq/impl/LoaderImpl$DefaultLoaderContext.class` | `4f65eea46931bcb1b880ffb0f9d0f7883af08406c91945667530e59f5fc5e5df` | `6fb227c598979de41f53c650d46aea462f8fb3821b2da48edd39f8b3467b2d72` |
| `org/jooq/impl/LoaderImpl.class` | `98491ac97202e70e1f0ceaa3acb10fdc46201d6edb83102aa1c3779b342069ee` | `2dd6d58e4e0fb09f373e3e6c425c8daee8c5981667261790964901d154102d8d` |

**Signatures** (keyring `$O/gnupg-D`, keys from keyserver.ubuntu.com): `jooq-3.21.2.jar` good, key `7C7271B83AAE727A2941690666F8E4860BF74983` (datageekery);
`h2-2.4.240.jar` good, `CF6FCDD747FD9C32304B180B58BD11D32974088F` (Thomas Mueller Graf); `junit-4.13.2.jar` good, `FF6E2C001948C5F2F38B0CC385911F425EC61B51` (Marc Philipp);
`annotations-26.0.2.jar` good, `33FD4BFD33554634053D73C0C2148900BCD3C2AF` (JetBrains).

**For the domain agent**
- jOOQ 3.21.2 is the parent side exactly (`LoaderImpl.java` identical); 3.21.3 is the fix side (comment aside). The overlays put both pins' `LoaderImpl` over 3.21.2.
- The only regression on a JVM is the reporter's test (names only, via `contains`); it discriminates the sides. The brief's ID/name pairs, `batchAfter(2)` and the PostgreSQL result are not run here.

### M17 · jOOλ #418 — window endpoints when the frame covers the whole partition (pinned source build, both modules)

**Pins.** Parent `5ef86d6525374c6cc412a5a2d996d3d6457cb59c`, fix `d1e06969ff748049aa8d1a9bf5d7f96dee7dc201` (squash; parent = the brief's).
Changed production files: `jOOL/src/main/java/org/jooq/lambda/WindowImpl.java` and `jOOL-java-8/src/main/java/org/jooq/lambda/WindowImpl.java`.
Changed tests: `SeqTest` in both modules (new `testWindowFunctionFirstValueAndLastValueWithFramesExceedingThePartition`).

**Build facts.** No root POM: two independent Maven modules, each with parent `org.sonatype.oss:oss-parent:7`, both versioned **0.9.15** at both pins:
`jOOL/` → `org.jooq:jool` (`<release>11</release>`, built on **JDK 17**), `jOOL-java-8/` → `org.jooq:jool-java-8` (source/target 1.8, built on **JDK 8**).
POMs identical at both pins. No runtime dependencies (JUnit 4.13.1 + hamcrest-core 1.3, test scope). Run each module from its own folder.

**Commands** (`$SK` as in M06; `$O/scripts/forkA_mvn.sh WT jOOL|jOOL-java-8 …`):
- online: `cd jOOL && JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -DforkCount=1 -Dtest=SeqTest -Dsurefire.failIfNoSpecifiedTests=false package` (15 s);
  `cd jOOL-java-8 && JAVA_HOME=$J8 $MVN …same…` (17 s)
- **offline (checked, 3–17 s)**: the same with `-o`.

**Artifacts** (`$O/artifacts/`):

| File | sha256 |
|---|---|
| `M17-jool-parent.jar` | `db4ef5a69bc373ad12a5720b8be4bfd5f031eeba9f16c4344e1c62fb048f552e` |
| `M17-jool-fix.jar` | `cc018f313a315dea624582901278e2d8efa0f99913a8a7244f29f9c66012fc08` |
| `M17-jool-java-8-parent.jar` | `26d5315b0f3f6ea33f04b198d88061038c9a7bea02a115415b5eac9e4b33351b` |
| `M17-jool-java-8-fix.jar` | `db4c33c8ed67775947b674cfb94e52bd6492a95cbecd874aefd2f922b6a69d75` |

| Class `org/jooq/lambda/WindowImpl.class` | parent | fix |
|---|---|---|
| `jool` | `9ff1f4286cee3430bb6c13bad4cb45f252b88b225caa2a6c58c785b0ca531c53` | `d3de6c47c0c499ef3ae8ef8c1b4541f6af76ea14518382ba3339322eab111ecb` |
| `jool-java-8` | `c388caf818948a24a14a9f414af91ac5fe2e6ed09562ea17b2e1d714883a9b64` | `05c63834eae3eea3432b7233c4ff647a2b5ab75fdbc58bb9c90604f76656e188` |

**Releases** (`$O/releases/{jool,jool-java-8}-{0.9.15,0.9.16}/`, `--strict-checksums`). As the brief says, the version label does not identify the code:
- **0.9.15** (2023) is older than the parent: its `WindowImpl` lacks the parent's #415 change (the `cacheIf(...).toList()` wrapping), so it is neither side.
- **0.9.16** (signed 2026-10-29) contains the PR's three hunks unchanged, plus later changes to `window()` (empty frames before/after the partition),
  `percentRank()`, `ntile()` and one more line; it is **not byte-equal to the fix**.

| Jar | sha256 |
|---|---|
| `jool-0.9.15.jar` | `a30d96719099eb4de87b08152f97adb0ba3cfef997dadcace8b2e4dcdc197f84` |
| `jool-0.9.16.jar` | `725e055835c5445396f41a012086ad73aa02fc7748bc5618cc184eec71121fa9` |
| `jool-java-8-0.9.15.jar` | `f53e0bba588d36e0ca06a5bc7754b868eb3b1e718f723243f003b6a3081f0573` |
| `jool-java-8-0.9.16.jar` | `9f5628ce7fc18ff32cf896284d29beec2c829507f743bab9755f61535f4dad3e` |

**Landed tests** (`SeqTest`, upstream Maven builds; logs `$O/logs/M17-jool*-*.log`):

| Run | `jool` (JDK 17) | `jool-java-8` (JDK 8) |
|---|---|---|
| fix, its own (online, then offline) | 163/163 pass | 163/163 pass |
| parent, its own (offline) | 162/162 pass | 162/162 pass |
| fix's `SeqTest` on the parent (offline) | **1 failure**: the new test, `SeqTest:2472` expected `[Optional[1], Optional[1], Optional[1]]` but was `[Optional.empty, Optional.empty, Optional.empty]` | **1 failure**: the same test |

**Signatures.** 0.9.15 jars: good signatures by `028B243C8B90B03809C4541E715698ABCBC3A313` (Lukas Eder); 0.9.16 jars: by
`7C7271B83AAE727A2941690666F8E4860BF74983` (datageekery). Keys fetched from keyserver.ubuntu.com by key id (`$O/keys/key-*.asc`), no further trust path.

**Jobs.** None.

**For the domain agent**
- Use the pins' own jars for both sides; neither release equals a pin.
- `jool` needs Java 11+ at run time, `jool-java-8` runs on Java 8.

### M18 · Eclipse JDT Core #5380 — empty first formatter region (overlay over org.eclipse.jdt.core 3.47.0; no upstream build)

**Pins.** Parent `1b3a126e2d26e53aeb79796ec1c881aff66424cd`, fix `2008a7280a5a72807ace4cba42c22211f58165b5` (squash of 3 PR commits, one parent = the brief's).
Bundle `org.eclipse.jdt.core` **3.48.0-SNAPSHOT** (parent POM 4.42.0-SNAPSHOT, Tycho build), `Bundle-RequiredExecutionEnvironment: JavaSE-17`. Changed production file:
`org.eclipse.jdt.core/formatter/org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator.java` (one line: `previousRegionEnd = Math.max(0, region.getOffset() + region.getLength() - 1)`;
parent `972c22c2bd0f7f8470ec4f3733cb7d7e8070a8720506765d464eade03f3a6509`, fix `c16b736500b17b75fa927882bcce2ae63bcd359d9af6eee8bf6cd36ef702f4f9`). Landed test:
`org.eclipse.jdt.core.tests.model/src/org/eclipse/jdt/core/tests/formatter/FormatterRegionTests.java` (new; sha256 `8bf539f325d6fe02e92fc02cb1414522f6c0efa8a7f48d93553a8a86868ce86b`),
added to `RunFormatterTests`. **It is a plain JUnit 3 `TestCase`** (no workbench, no OSGi harness) that constructs internal `DefaultCodeFormatter` directly; 4 tests.

**Release set.** Central has `org.eclipse.jdt:org.eclipse.jdt.core` up to **3.47.0** (`Bundle-Version: 3.47.0.v20260828-1141`, metadata lastUpdated 2026-09-07);
3.48.0 (Eclipse 4.42) is not released. **3.47.0's `WrapPreparator.java` = the parent's byte for byte** (sources jar sha1 checked).

| Set (`$O/releases/jdt-core-3.47.0`, 19 jars, `classpath.txt`) | sha256 |
|---|---|
| `org.eclipse.jdt.core-3.47.0.jar` (signed jar, class major 61) | `723e30be1e841516c388ebb32017cb8b36662808f46be5265b78cc06bd4fe71c` |
| `org.eclipse.text-3.14.800.jar` | `14814c1f1a737fde0a2d56c47a2f02cf4c8c5dee748756c4763e674cae214250` |
| `org.eclipse.core.runtime-3.35.0.jar` | `5b0c2794e9fe1785360dec920cc802f3388a0eb72ee25b89054b79ff3e2f07c9` |
| `org.eclipse.core.resources-3.24.100.jar` | `946851cf5902cd3b002920063a30b169e5710088b6c1ad7dd05bdd3be4fbfff4` |
| `org.eclipse.equinox.common-3.21.0.jar` | `2545ed27d408f19882695703097e5998bf25652bd0dac76a8e6d1391ec228ab7` |
| `org.eclipse.osgi-3.24.300.jar` | `4a770aa4a78df653af871073c8b4ddd56884895f5fc71d10c40b4289ac7c8b9f` |
| `ecj-3.46.100.jar` (also in the graph; keep jdt.core before it) | `74c93172475fee0cd4e6eefb44233516dd40525642da35d009146d97ea598229` |

(The other 12 jars and their digests: `cd $O/releases/jdt-core-3.47.0/lib && sha256sum *.jar`.)

**The release jar is signed** (Eclipse Foundation code-signing certificate; `jarsigner -verify`: "jar verified"). An unsigned overlay class in the same package is refused
(`SecurityException: ... signer information does not match`, log of the first attempt overwritten). So the overlay runs use an **unsigned copy**:
`$O/artifacts/M18-org.eclipse.jdt.core-3.47.0-unsigned.jar` = the release jar with `META-INF/ECLIPSE_.SF` and `META-INF/ECLIPSE_.RSA` deleted (`zip -d`), same class
list, sha256 `8b2c9d22bfdf5160e15d43044840f3d239aa400acd6c576bb574fb7c16387d34`. Classpath for overlay runs:
`$O/artifacts/M18-eclipse.jdt.core-SIDE-overlay.jar:$O/artifacts/M18-org.eclipse.jdt.core-3.47.0-unsigned.jar:` + the rest of `$O/releases/jdt-core-3.47.0/classpath.txt` without the signed jar.

**Overlay** (javac 21.0.13 `--release 17` over the 3.47.0 classpath; Eclipse builds with ECJ, so these classes are javac's, not byte-comparable with the release):
- `$O/artifacts/M18-eclipse.jdt.core-parent-overlay.jar`: `a6f8812c14580e7479de2ce3293fd46410d8f706d9805264b4c2e508125c1e77`
- `$O/artifacts/M18-eclipse.jdt.core-fix-overlay.jar`: `02d3cb39fad733bff7e816896c44f7eab681ce8b85aae04d243188f8f43c58ab`

| Class | parent overlay | fix overlay |
|---|---|---|
| `org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator$1.class` | `7f98b06f97652d298d74232e1c0f1d8832dff0d7627f8b53fdf505bcfcde7bf9` | the same |
| `org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator$2.class` | `985fc286f966ab812bc366fcdb476b576d89d190387f2c60edc378e925e9a87f` | the same |
| `org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator$3.class` | `234c7c082b5e3a4bdacd47ed0e018002dbf98d57fbbfc4a39809e7d0e1b6dc38` | the same |
| `org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator$FieldAccessAdapter.class` | `784c8c8c79ebe1390d20b3f73528ab89f426667a2c285d811c9911c55bb84586` | the same |
| `org/eclipse/jdt/internal/formatter/linewrap/WrapPreparator.class` | `c8797ec39aaf8fe435d0474ffb159d6020a56965b30d603984f922082eb48788` | `5a34ba1cab64e18a1ed1aec8134d11deffbab41aade4f39130a81d3870135b44` |

**Landed test over the overlays** (JUnitCore 4.13.2 on JDK 21.0.13, classpath above + `M16-testdeps` for JUnit; an overlay run):

| Run | Result | Log |
|---|---|---|
| `FormatterRegionTests` on the fix overlay | 4/4 pass | `$O/logs/M18-overlaytest-fixtest-on-fix.log` |
| on the parent overlay | **2 of 4 fail**: `testEmptyFirstRegionAtDocumentStart` and `...WithCrLf`, `StringIndexOutOfBoundsException: Index -1 out of bounds for length 31` (33 with CRLF) | `$O/logs/M18-overlaytest-fixtest-on-parent.log` |
| on unsigned 3.47.0 alone | same as the parent overlay | `$O/logs/M18-overlaytest-fixtest-on-3.47.0.log` |

The two single-region controls pass on every side.

**No upstream build.** A Tycho build of `org.eclipse.jdt.core` and `org.eclipse.jdt.core.tests.model` needs the Eclipse p2 target platform (large downloads from
download.eclipse.org) and the OSGi test runtime; it was not attempted, and no job was queued, because the landed test is plain JUnit and ran over the overlays.

**Signatures** (keyring `$O/gnupg-D`, keys from keyserver.ubuntu.com): `org.eclipse.jdt.core-3.47.0.jar` Central `.asc` good, key `3E07544E2175A6B3608C515A5FEC689CA7E7B6BD`
(Eclipse JDT Project); `org.eclipse.text-3.14.800.jar` good, `9E3044071B758EBCB7E45673700E4F39BC05364B` (Eclipse Platform Project); plus the jar signature above.

**For the domain agent**
- 3.47.0 is the parent side exactly; the fix overlay is the fix side. Use the **unsigned** copy of the release jar under any overlay.
- The landed test needed no OSGi runtime (it builds `DefaultCodeFormatter` itself). Whether the brief's public route, `ToolFactory.createCodeFormatter`, works on a plain classpath (it looks up a formatter extension) was **not** tried by the setup.

### M19 · JUnit Jupiter #2646 — indicative display names start at the annotated class (upstream Gradle 7.1-rc-2 build at both pins; landed tests by job)

**Pins.** Parent `882bf488e228b1f55ed3b636838825dec31ec20d`, fix `694efb6dbd8506d623d5c117d1df39f9260f72df` (squash of 5 PR commits on `main`, parent = the brief's).
Changed production files: `junit-jupiter-api/src/main/java/org/junit/jupiter/api/DisplayNameGenerator.java` (+123/−72),
`junit-jupiter-api/src/main/java/org/junit/jupiter/api/IndicativeSentencesGeneration.java` (+19/−7),
`junit-jupiter-engine/src/main/java/org/junit/jupiter/engine/descriptor/DisplayNameUtils.java` (+3/−2: imports and Javadoc only; its class is byte-identical at both pins).
Tests (`junit-jupiter-engine/src/test/java/org/junit/jupiter/api/`): `DisplayNameGenerationTests.java` (changed), new fixtures
`IndicativeSentencesNestedTestCase.java` and `IndicativeSentencesTopLevelTestCase.java`. Also the 5.8.0-M2 release notes.

**Checkouts.** `$W/M19-junit-framework-parent` and `$W/M19-junit-framework-fix` are **standalone depth-1 clones** of the mirror (fetched from
`refs/pins/ROLE-SHA`, each with its own `.git/shallow`), not linked worktrees like the other cases: the build's `net.nemerosa.versioning`
plugin reads git history with JGit, which in a linked worktree of the shallow bare mirror found neither the objects nor the shallow boundary
(`MissingObjectException: Missing commit 694efb6d…`, then `…2f43ffe6…` with the objects added). Trees: parent `014e726b9da964dba6316e523a72a2e94f96f909`,
fix `610e33a9c050e989d977c2842661a1f87e58a68f`, as in `$O/logs/pins-parents.tsv`.

**Build facts.** Gradle 7.1-rc-2 (`$O/tools/gradle-7.1-rc-2`; zip sha256 `caa8e323577de2fa421b47dded5278e7376c2bb6420221fbaf7908dfa9be8657` =
services.gradle.org's = the wrapper's `distributionSha256Sum`). The repository's `gradle-wrapper.jar`
`e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637` (both pins) equals the published wrapper jar of Gradle 7.0.2
(`$O/dl/gradle/wrapper-C/gradle-7.0.2-wrapper.jar.sha256`). Versions `5.8.0-SNAPSHOT` / platform `1.8.0-SNAPSHOT`.
As in upstream CI (`.github/workflows/main.yml`): Gradle runs on **JDK 11** (`$J11`), compiles and tests with a **JDK 16 toolchain**
(`java-toolchain-conventions`: default language version 16), and `JDK8` is set. The setup fetched AdoptOpenJDK 16.0.1+9
(`OpenJDK16U-jdk_x64_linux_hotspot_16.0.1_9.tar.gz`, from the GitHub release `jdk-16.0.1+9` of `AdoptOpenJDK/openjdk16-binaries`, sha256
`7fdda042207efcedd30cd76d6295ed56b9c2e248cb3682c50898a560d4aa1c6f` = the release's `.sha256.txt`; tarball `$O/dl/jdk16/`, unpacked at
`$O/tools/jdk16/jdk-16.0.1+9`, `$J16` in `env.sh`).

`$O/scripts/M19-gradle.sh` runs it all: `JAVA_HOME=$J11 JDK8=$J8 JDK16=$J16`, `--no-daemon --console=plain --max-workers=2`,
**`--no-build-cache`** (the build's remote cache is `https://ge.junit.org/cache/`: nothing is taken from it) and **`--no-scan`**,
`-Dorg.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=512m`, `-Pkotlin.compiler.execution.strategy=in-process`, toolchain auto-download and
auto-detection off with `org.gradle.java.installations.paths=$J8,$J11,$J16,$J17`, and `-I $O/scripts/junit-plugin-repo.init.gradle`.
The Gradle Enterprise plugin still prints "A build scan was not published as you have not authenticated with server 'ge.junit.org'" at the end.
The tests use the `org.gradle.test-retry` plugin (2 retries by default); the job passes `-Pretries=0`.

**Substitutions (plugin and build-script classpath only)**, in `$O/scripts/junit-plugin-repo.init.gradle`; the upstream build files are unchanged:
- `com.gradle.enterprise.test-distribution` **2.1.1-rc-1**: the build's repository `https://repo.gradle.org/gradle/enterprise-libs-release-candidates-local/`
  no longer has it; Gradle's `https://repo.gradle.org/gradle/enterprise-libs-release-candidates/` serves the same coordinates, added as a plugin
  repository. Plugin jar `com.gradle.enterprise:test-distribution-gradle-plugin:2.1.1-rc-1` SHA-1 `4d3d2db5869b997862f0ca209860b767dda9689f` = that
  repository's `.sha1`; sha256 `c67ed4c22f94788e69615b0ee10419aed18377502cbc3e80a0e36139b728af8b`.
- `org.ajoberstar.grgit:grgit-core:4.0.1` (needed by `net.nemerosa.versioning` 2.14.0) was only on jcenter: not on Central, the Plugin Portal or
  repo.gradle.org, and JFrog's mirror answers 401. `https://repo.grails.org/grails/core` serves it; the setup copied that pom and jar into the
  file repository `$O/dl/m19-substitute-repo` (`$O/scripts/add_module_C.sh`, log `$O/logs/M19-substitute-repo.txt`): jar SHA-1
  `27f6484efea89c746e4e68fe2f2ee32a80c58f89` = grails' `.sha1`, sha256 `5a7d4595c1f6d150fcc18a6e5253428f114be92cb4e3f9569ac671244e072a57`
  (pom sha256 `85d21418d48d67e9928bb50550ce80677545d97d3bede5985c1794a2693d1d4e`). No second source was found.

Commands (the jars: online at the fix, 49 s; offline at both, under 30 s):

```bash
cd ~/.cache/in-the-loop/merged-pr-links/worktrees/M19-junit-framework-fix   # or -parent
~/.cache/in-the-loop/merged-pr-links/scripts/M19-gradle.sh --offline -Pretries=0 :junit-jupiter-engine:jar :junit-platform-launcher:jar \
  :junit-jupiter-engine:test --tests org.junit.jupiter.api.DisplayNameGenerationTests
python3 -I ~/.cache/in-the-loop/merged-pr-links/scripts/junit_summary.py junit-jupiter-engine/build/test-results/test
```

(The test part is the job's; its first run resolves the test dependencies online.)

**Artifacts** (built offline at each pin; bind the class digests):

| Jar (`$O/artifacts/…`) | parent sha256 | fix sha256 |
|---|---|---|
| `M19-junit-framework-ROLE-junit-jupiter-api.jar` | `0be8b45ad73af9a8b8e9e411650fe68ce7a848a1659274fe12babfc87a534fa3` | `732561ee89987b5907c519076382acf3a53849a689fac86a0da41251482e30b8` |
| `M19-junit-framework-ROLE-junit-jupiter-engine.jar` | `9e6bcc860ba9289f966f2620a674c0e65711ed84508df371c49a919d3c0c22da` | `8617b14e51c59813508f5f9035a598234c5be3c7738c7bd0ef1f7f84b36212cd` |
| `M19-junit-framework-ROLE-junit-platform-commons.jar` | `4d3ff38351acfd3694c3abc80939176c191b5a49b76b244d43a267f143de17ea` | `fa5fcb27e2e235392d7941e235de26ef4cf3f1a373f0bdb906b9e97a0e70907c` |
| `M19-junit-framework-ROLE-junit-platform-engine.jar` | `230828e46376ec725db2cf565ad772816fb6a457c0d9632d4f8448170927f7d7` | `dd89e8f3f811f312cfb565fb0acd2cadb039bb0539a4f1182064f32b8831a500` |
| `M19-junit-framework-ROLE-junit-platform-launcher.jar` | `d06b3eba9bba190a3124b3e61acd2756cc806263b0de7a3e6d2087a3edb24baa` | `b8064b9860d178affadc4b588b9c4482f1c9f1075e840de344473203d8e8fc5a` |

Only the two `junit-jupiter-api` files changed; the other jars differ by build timestamps and manifests. External runtime dependencies:
`org.apiguardian:apiguardian-api:1.1.1` and `org.opentest4j:opentest4j:1.2.0` (in `$O/releases/junit-5.8.0-M1/lib/`, strict checksums).

| Class | parent | fix |
|---|---|---|
| `org/junit/jupiter/api/DisplayNameGenerator.class` | `ad6ae01f1467ee67cf67c5a58c719484d08e47b75add5fdf9f6da9f647e66bf8` | `02f6967c15320131f1bdb0795f276b81d6c6c16aaa0a556ed9d66df6e026a09b` |
| `org/junit/jupiter/api/DisplayNameGenerator$IndicativeSentences.class` | `b642284fc058923f3d2f37664929acb5a5753df3d82d0ccc21b3b065e3eedfb5` | `b72d8f96b10600563229ecb78dc70fa275b18fd741723afd57d9542b19b65cde` |
| `org/junit/jupiter/api/DisplayNameGenerator$ReplaceUnderscores.class` | `390545e8ef93b74ba1567ee629f74e6f2132910f5bbbd4b63eb685c183edcbd5` | `7f9e681ede10825b5993c59b59f6710a1a7a6c7f46dde0bd2817fb530983257a` |
| `org/junit/jupiter/api/DisplayNameGenerator$Simple.class` | `f67843e185bbd1611a15a3c430948c5aa66fdeb099361a4defd3b2cc3ae2a9e0` | `1fe2710e2e6796306197197df547b4fc2d8fce88dc1fa63c28c221b695dc2b64` |
| `org/junit/jupiter/api/DisplayNameGenerator$Standard.class` | `4305d89de2a43267a31ffb50861bf7a018649ec5198626dbbfd5b9e8f321a2cd` | `90e25bfd1ac6c96ad574cf9bf74b7ea1803f4635e7804177013b6add49a67ad1` |
| `org/junit/jupiter/api/IndicativeSentencesGeneration.class` | `5c3446c89e7e1486ca20c3be4972f165f5eeb297cf4d7a42bf8e8baca68dc6ab` | `c125a9f075a71a250d6a19504e5c3ec006dbdc6e2c285c368b4ba910c13de21d` |
| `org/junit/jupiter/engine/descriptor/DisplayNameUtils.class` | `8f778974ffe70d5b36899673296c5072c7ccfe55c08f87140d7e968d1bdddb46` | the same |

**Landed tests: job `20261125-072322-setup-run-junit-2646-s-landed-displaynam`** (`$O/scripts/submit_C.py m19`): compiles the
`junit-jupiter-engine` tests and runs `DisplayNameGenerationTests` (`-Pretries=0`) on the fix online then offline, the parent's own copy offline,
and the fix's test plus its two new fixture classes transplanted onto the parent (expected to fail, or not to compile; the step prints
`TRANSPLANT-FAILS-AS-EXPECTED` or `TRANSPLANT-DOES-NOT-COMPILE`); then the checkouts are cleaned.
**Passed** (5 steps, 3m50s, peak 2.2 GiB). Logs: `$O/logs/M19-{fix.test-online,fix.test-offline,parent.test-offline,parent.transplanted.test-offline}.{junit.txt,gradle-log.txt}`.

| Run | Result |
|---|---|
| fix, online and again offline | 10/10 pass each time |
| parent's own, offline | 8/8 pass |
| fix's test and two new fixtures on the parent, offline | compiles; **1 of 10 fails** (`TRANSPLANT-FAILS-AS-EXPECTED`): `indicativeSentencesGeneratorOnNestedClass()`, `AssertionFailedError: expected line #1 doesn't match actual line #1`, expected `CONTAINER: A year is a leap year` |

**Releases** (`resolve.sh`, strict checksums, signatures good), compared on the three changed files:

| Set (`$O/releases/…`) | Main jars sha256 | Changed sources equal |
|---|---|---|
| `junit-5.8.0-M1` (Central, 2021-02-11) | `junit-jupiter-api-5.8.0-M1.jar` `e6e697b9d51e976b520a0d8934e5cd08395eba98cc19e8ac78882298a3f51bc1`, `junit-jupiter-engine-5.8.0-M1.jar` `398c4c72c9c2e45e44bfbc434daba2696485bcc8fbd40e5c241562a0346bdbbb`, `junit-platform-launcher-1.8.0-M1.jar` `f31f466bc2da83e9e8639bc13dbcc29d20a1c63c6f0f59b47f2d29ae0ade216b` | all three = **parent** (`DisplayNameGenerator.java` `b80725495a4e77e569ce2b892cebf860a07008e1cc73500638ce6bd059ccebef`, `IndicativeSentencesGeneration.java` `2a1e00fffbdae261b88eec2f5fe91f085c12b183f36d01e45fc6052e7d2a3ca1`, `DisplayNameUtils.java` `289f16d94ae91cc3b3bd2ed68e15c5396551fedb5271a83c2131f9f0928f151a`) |
| `junit-5.8.0-RC1` (Central, 2021-08-17) | `junit-jupiter-api-5.8.0-RC1.jar` `5fd7ace3de7cd506f73a9b6cd2f8b4c37355f30814b21439a7c2575602df03ba`, `junit-jupiter-engine-5.8.0-RC1.jar` `b781291244b3fdccc9ee48e556824684bfa421ff520405507622f3cdd9b3a20a`, `junit-platform-launcher-1.8.0-RC1.jar` `caf348f7aff1b13af61e7f338525b7c50cc28f201e3c59c7fb52dc51a8da1e47` | **neither** (later changes on top of the fix) |

Fix-side sources for reference: `74babeb7ca680e1c8a73b98b2bf3a5add7f344e5be01312e9861bc806b1fc675`, `0476f4789818150c68cbb306b5cd5b36dd3cbaeddc30f54a89756d04a6bf1de8`,
`346c8fd7ed58fcafa7be703af46523df34b498d2b3bf4c2cf287f14119b3b595`. No 5.8.0-M2 is on Central, though the pins' release notes are for M2.
The 5.8.0-M1 set's POM pulls Kotlin stdlib 1.4.20 and `annotations-13.0` onto the runtime classpath; the pins' engine needs only apiguardian and opentest4j.

**For the domain agent**
- Pin jars: the five `$O/artifacts/M19-junit-framework-{parent,fix}-*.jar` plus apiguardian 1.1.1 and opentest4j 1.2.0. 5.8.0-M1 is a published parent-side set for the changed files; there is no published fix-side set.
- Rebuilds need `$O/scripts/M19-gradle.sh` (JDK 11 + 16, init script, no remote cache) and the standalone checkouts.
- The brief's claim scenarios (Launcher `TestPlan` labels) were not run.

### M20 · Guava #7784 — SetView equality by cardinality bounds (overlay over Guava 33.4.8; upstream build by job)

**Pins.** Parent `9eb72d3730bd10d92d062c912b673efed0ae2dc0`, fix `0232f388fbe4d45deea2f31a9c6e2f7283662fd5` (one parent = the brief's). Version
**999.0.0-HEAD-jre-SNAPSHOT** (Android: `-android-`); build files identical at both pins. Changed: `guava/src/com/google/common/collect/Sets.java` and
`android/guava/src/com/google/common/collect/Sets.java` (+112/−19 each; adds package-private `SetView.minSize()`/`maxSize()` and overrides `equals`), and
`SetViewTest.java` in `guava-tests/test` and `android/guava-tests/test` (both flavours identical: parent `169394c3635757429dfae6eb126787e9a63080402d286604b33b437afb369b82`,
fix `4a15e7cc69a248eb280f3c21a3c62de45b674f869d3128582792d29287f93a90`).
`Sets.java`: parent JRE `78229408860dcf1af0b18420d477878bec132279d02f089b53324a7572b1dc3a`, fix JRE `58e02666c73fea817823f4c0fe21ed81aa2a40e1b5f76d05013b3c3170c0703d`,
parent Android `a099a5a3130fc1970cb6d79a366dd0a774919d4146516e159ab024a21cb57988`, fix Android `485a6cd29f148ae82af6adebd9cb1901d2d6a465c52291b5c2350aa4b32966e4`.

**Build facts.** Maven; the wrapper names Maven 3.9.9 (`distributionSha256Sum=4ec3f26fb1a692473aea0235c300bd20f0f9fe741947c82c1234cefd76ac3a3c`), Maven 3.10.0 on
`PATH` was used. Guava compiles with a **JDK 24 toolchain** and tests on a JDK of `${java.specification.version}`, through two plugins:
`maven-toolchains-plugin` and `org.mvnsearch:toolchains-maven-plugin:4.5.0`. **The latter downloads Temurin JDKs into `${user.home}/.m2/jdks` and rewrites
`${user.home}/.m2/toolchains.xml` even when a matching toolchain is offered.** So every Guava Maven command here runs with
`MAVEN_OPTS='-Duser.home=$O/mvnhome'` and `-t $O/mvnhome/.m2/toolchains.xml`. An inline `-pl guava validate` (15 s) let the plugin install, inside
`$O/mvnhome/.m2/jdks/`, **Temurin 24.0.2+12** (tree identical, `diff -r`, to `$O/tools/jdk-24.0.2+12`, whose tarball is checked: see M01) and **Temurin 21.0.13.1+2**
(tree identical to the tarball `OpenJDK21U-jdk_x64_linux_hotspot_21.0.13.1_2.tar.gz`, sha256 `bb8a93f9ae6e7a693b2b721e85dbeff26ae1a77447985a8d7afcdd9c7cf6222e` = Adoptium's,
signature good by `3B04D753C9050D9A5D343F39843C48A565F8F04B`). `$O/mvnhome/.m2/toolchains.xml` now lists both; later runs find them and download nothing.
The user's `~/.m2` does not exist and was not created (the job checks `$HOME/.m2/jdks` stays absent).
Command (from the worktree, or its `android/`; `source $O/scripts/env.sh`):
`JAVA_HOME=$J21 MAVEN_OPTS='-Xmx1g -Duser.home='$O/mvnhome $MVN -t $O/mvnhome/.m2/toolchains.xml [-o] -Dmaven.javadoc.skip=true -Danimal.sniffer.skip=true -Dtest=SetViewTest -Dsurefire.failIfNoSpecifiedTests=false -pl guava-tests -am package`.

**Release set.** Guava 33.4.6/33.4.7-jre carry an older `Sets.java` (`b276005ce81936a8eb54f6251371a3b58ad30d50c11cb05f540fa6ffe8c211fb`); **33.4.8-jre's = the parent's byte for byte**;
33.4.8-android's (`3734c272e006b3e9b5d8f29dd1a92d4cd9d1f9bc6618fae2f6493f75d0e33c34`) = the parent's Android file plus one `@SuppressWarnings("Java7ApiChecker")` line;
33.5.0-jre (`0254e5af5d200ccfcb0af706b60bf3e71403ae490067ee7df9d0b0ccf3b526f0`) has the fix among many later changes. Sources jars sha1 checked in `$O/dl/central/`.

| Set (`$O/releases/…`) | Jar | sha256 |
|---|---|---|
| `guava-33.4.8-jre` | `guava-33.4.8-jre.jar` (class major 52) | `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed` |
|  | `failureaccess-1.0.3.jar` | `cbfc3906b19b8f55dd7cfd6dfe0aa4532e834250d7f080bd8d211a3e246b59cb` |
|  | `jspecify-1.0.0.jar` | `1fad6e6be7557781e4d33729d49ae1cdc8fdda6fe477bb0cc68ce351eafdfbab` |
|  | `error_prone_annotations-2.36.0.jar` | `77440e270b0bc9a249903c5a076c36a722c4886ca4f42675f2903a1c53ed61a5` |
|  | `j2objc-annotations-3.0.0.jar` | `88241573467ddca44ffd4d74aa04c2bbfd11bf7c17e0c342c94c9de7a70a7c64` |
|  | `listenablefuture-9999.0-empty-to-avoid-conflict-with-guava.jar` | `b372a037d4230aa57fbeffdef30fd6123f9c0c2db85d0aced00c91b974f33f99` |
| `guava-33.4.8-android` (same five dependencies) | `guava-33.4.8-android.jar` | `a1f8a4bafe5a77232d333356843e194599b30837574a7f4be1063daaaaab102c` |
| `M20-testdeps` (overlay test run only) | `guava-testlib-33.4.8-jre.jar` | `a58a38746f97e02ae3d067b74a25ad2b136650227baa7124ce03fa3bce4e8576` |
|  | `truth-1.4.4.jar` | `52c86cddadc31bc8457c1e15689fc6b75e2e97ce2a83d8b54b795d556d489f8c` |
|  | `junit-4.13.2.jar` | `8e495b634469d64fb8acfa3495a065cbacc8a0fff55ce1e31007be4c16dc57d3` |

**Overlays** (javac 21.0.13 `--release 8`; both sides compile over 33.4.8 unchanged; rebuilt once and identical):
- JRE over `guava-33.4.8-jre`: `$O/artifacts/M20-guava-parent-overlay.jar` `1b0d27c14e8db53fb918f49d9f2f14fea06df05b708dbda14223a3a000e06a97`, `$O/artifacts/M20-guava-fix-overlay.jar` `d8303c3d08614e14d105492596c2a470bc5e8385bc974b90f1c44286ff7520c7`
- Android over `guava-33.4.8-android`: `$O/artifacts/M20-guava-android-parent-overlay.jar` `48635f0b38f167f270f1371522a35f5e6dd7832bebb3ebb36ea8871983a2912f`, `$O/artifacts/M20-guava-android-fix-overlay.jar` `2a3e81d2d40f29900650744064e8f1c4277c6b5870ba4a6552d81687f266903c`

JRE class digests (Android: `$O/overlays/M20/guava-android-{parent,fix}/class-sha256.txt`):

| Class | parent overlay | fix overlay |
|---|---|---|
| `com/google/common/collect/Sets$1$1.class` | `31f8e143dac1b62f6706823bf09d76e722dc91a885af4315b542d80e5d2ac421` | `a5ea484f2e6e9253651f4e237813a8144bcef7da3c639a15e7e2f6ddd33629de` |
| `com/google/common/collect/Sets$1.class` | `292ed464a0ab46bf27c20183954d52a59bf174259dbc79396d54f9755d6b9b8e` | `de27315965ecb6c5c7efc491eb90eed35b924d855d866929c7a98a8ea775d42a` |
| `com/google/common/collect/Sets$2$1.class` | `1bb45c1ed6c04a6e20f35e5de6421fe3073705b6606e29f9c8aa5b116742de2d` | `16080a81601828fcadd0acc40107b5b8f797f0bbc93203d4ec2d7ac6c12d9960` |
| `com/google/common/collect/Sets$2.class` | `87368e961bdf3334f226256bb028b684bf206109664f4de2eba245d6dbdb1d59` | `418135f0ca6d29f7b0d94ca140c127ae5ed5d2427d7e2e1eef385ed13484f818` |
| `com/google/common/collect/Sets$3$1.class` | `4ffd00608c467d0ab2ffca35f140ec5b0ba29b3ffbbdbdf2d10dfc01e7672296` | `7b216c6ffb030c2337737f74260f611230fe6f2ba2709a5cb4d72ef511755536` |
| `com/google/common/collect/Sets$3.class` | `9472f9fa6220b050dcbb8b677a36a86cb73d8f556a330effd30cd57aa27094cc` | `47e1502693e2d56952fe71c43450d5f859240fe227207d5e01709750a1abd66e` |
| `com/google/common/collect/Sets$4$1.class` | `cd805c27a32dde509ba07f5fb9ee8e8831dadf9166c9d406c41efa8ca8d7e483` | `af8dae788ce5bc54f756bd19eca574fcc88932cd04a3ad855795796eab39abb4` |
| `com/google/common/collect/Sets$4.class` | `77bbf50427d5629cc3f9b1419d24aff92f80a955d62c67f272572b5e67ac96c1` | `bc56c684ed0e7f88064b5f588244eb712c05ce006941ca0ac2683b2f5e3bdd74` |
| `com/google/common/collect/Sets$5$1$1$1.class` | `976573943dfcaf274be22c72b74d2f30f5f26e8491b71190cf239b9ea7d0701d` | `ba27d94432e66f7bd858d32df4495c13fd4951a3a075f70743f91666419a952d` |
| `com/google/common/collect/Sets$5$1$1.class` | `2ed72a415ee51aae759d090d0d8e64588af1118fe988d36c1a26254c8c51f4e6` | `e946492b073634c023d1b82598ee8cb12c90e01827b0005dc3cb24b31d9407bb` |
| `com/google/common/collect/Sets$5$1.class` | `9c38627a0fec95388a4a296cd630a65c8d74de0151f9c2fba6fdf47fafa1e9cd` | `ff3d7a55e09cd147b61647bd1cce80ab8ec570a18bcfd347ab16490fa0aa16a8` |
| `com/google/common/collect/Sets$5.class` | `eee933287c9a8806ae6a2a703236d7d73f3ed56e827ce910f3af464422160ba5` | `d0b467b90f12981014e0d4f7f7ef8101a297d0e4471196378aa70be9e27f31f2` |
| `com/google/common/collect/Sets$CartesianSet$1.class` | `9d5f4faca86c81d15833f9bbbbc8d5726d3a6469014f1f2042cfc37aca61975e` | `daea7e544752d075d9a4e9f17588d4cbf17af478775fef8334a7438e16b50a49` |
| `com/google/common/collect/Sets$CartesianSet.class` | `74c835b09dbad0ec9609c9997ebae17d181c07e5ae914ede2a5b5b095be51b80` | `def164e3fd1c2f7af0a8bdd1eaa89d47409434e5bd246e5c9a4b75aef9d716e6` |
| `com/google/common/collect/Sets$DescendingSet.class` | `7f88c56542cf68a18d49bf3b88ea15541f6fc358e375f83595a469e7c4a88253` | `8966b8d625629ee4331925f9e67001214d1adae5576d04ce1962e31bf88e2d2e` |
| `com/google/common/collect/Sets$FilteredNavigableSet.class` | `0632bbff0c70034b38c18e7def07a6c8dc940d713312b66ee95bcb5402a65a88` | `d8672981b554d26d38034561fa8b5bb44bfdc459b4c2075c364dc6e2652ec2b5` |
| `com/google/common/collect/Sets$FilteredSet.class` | `7a31eaca81b17dde877e8f929d49755004a8c0042838ff3bd2a281bef7be717a` | `57c57094b5f75ba1a3b1a0ec27a7968f27c52a57a4cb0c5bf971e6cd9fc413f5` |
| `com/google/common/collect/Sets$FilteredSortedSet.class` | `42f08c625b18d47b640399904d9f83df054fb82cea7f5f714ca07749325e1f52` | `b7f389be06eedb9fbb2e0e6684035d587a99847dd889e1ee9693996e73a0a470` |
| `com/google/common/collect/Sets$ImprovedAbstractSet.class` | `47587a3f614cbbbb2b8e83f413b45bf905a274b9cc957a9b6b2f60521e675501` | `0f1e6f11b8a87660882b26969ad8f1f08ca76d28fc98833e9bfcc131ef93fd33` |
| `com/google/common/collect/Sets$PowerSet$1.class` | `dd335ad96ac568ffdfd930833453e1c13b49e17636d30f5d5f26caedc3f5b388` | `78e8f1135044b185645f52d80c9e828a323521d51eb1fa825dd92812f424f507` |
| `com/google/common/collect/Sets$PowerSet.class` | `f988766b53611281b1401170e91c6b87c04a66678dc61a1648ef0d706700b859` | `a5131155571abb9a1680a368087ed0214c1251e928b7cf94e982905a403eded9` |
| `com/google/common/collect/Sets$SetView.class` | `d9ae98f897b845bb72ebe1237231e1c2101b88dcaac27acb48d1cc44514979c3` | `b218b55d94482d52012fedf4bfae1899496acf673bd84351aff83a61c2426fda` |
| `com/google/common/collect/Sets$SubSet$1.class` | `61744929b7a5d6c4ee92c5f1b2e3da5408983b2683c4ba134086b627b347226b` | `d5b53efafae7303e11aa3d61bc1bfdab1c08abc5ed96052da9f69fadec2b99d3` |
| `com/google/common/collect/Sets$SubSet.class` | `29ffcd1a3722f2974b3c6ec3539f5e5c9b1dd95d6decff4bba4ccc21dbd225d1` | `04613e48248ce625e9a34a215aabaab44c82e8636e86dd01dcf93c9154371624` |
| `com/google/common/collect/Sets$UnmodifiableNavigableSet.class` | `336434dae74d4a47adbea4a3bf093510eb7be4f90f12633d26aaa091f7c9f669` | `126733273e6b45e1f758e1b96862338616647a978682bd7d99d9cd4d3e372c25` |
| `com/google/common/collect/Sets.class` | `285ea978354971c7b0a4e14a0604dc85f6c1f16fd507ec37f0502d1b143d25ee` | `5ed8ffaccfaef04a586c7aaffbb283154dbba6c221f93a9bb4e266314f5ac1cc` |

**Landed test over the JRE overlays** (JUnitCore on JDK 21.0.13, classpath overlay + `M20-testdeps`; helpers compiled from the worktree's `guava-tests/test`; an overlay run):

| Run | Result | Log |
|---|---|---|
| fix's `SetViewTest` on the fix overlay | 2736/2736 pass | `$O/logs/M20-overlaytest-fixtest-on-fix.log` |
| parent's own `SetViewTest` on the parent overlay | 2724/2724 pass | `$O/logs/M20-overlaytest-parenttest-on-parent.log` |
| fix's `SetViewTest` on the parent overlay | **does not compile**: it calls `SetView.minSize()`/`maxSize()`, which only the fix has (8 errors) | `$O/logs/M20-overlaytest-fixtest-on-parent.log` |

So the landed test cannot show a difference on the parent; it checks the fix's new bounds and equality, and the parent's old behaviour stays green.

**Upstream build: job `20261125-071415-setup-build-guava-jre-and-android-at-bot`** (`$O/scripts/submit_D.py guava`): the command above for the fix
(JRE, Android) online, the parent's own `SetViewTest` (JRE, Android) offline, the fix JRE again offline; jars to `$O/artifacts/M20-guava-{fix,parent}[-android]-guava.jar`.
No transplant (does not compile). **Passed** (6 steps, 7m27s, peak 1.8 GiB):

| Run (pins, upstream Maven) | Result | Summary |
|---|---|---|
| fix JRE, online | `SetViewTest` 2736/2736 | `$O/logs/M20-fix.jre.online.{junit,mvn-log}.txt` |
| fix Android, online | 2491/2491 | `$O/logs/M20-fix.android.online.*` |
| parent JRE (own test), offline | 2724/2724 | `$O/logs/M20-parent.jre.offline.*` |
| parent Android (own test), offline | 2479/2479 | `$O/logs/M20-parent.android.offline.*` |
| fix JRE again, offline | 2736/2736 | `$O/logs/M20-fix.jre.rerun.offline.*` |

Jars built from the pins: `$O/artifacts/M20-guava-fix-guava.jar` `614963be36b3cca413a3f42dc645f731d8d6e77a133ade6989965ea6cd5a9877`,
`$O/artifacts/M20-guava-parent-guava.jar` `fcc220662fa8e0769d6d122d4b833c95d1875b025f801602c30c9eee27bf9368`,
`$O/artifacts/M20-guava-fix-android-guava.jar` `dfe0725e0264b4f231111e39c5804cbdbfbbba7ff624a45c27677e1dce79da4a`,
`$O/artifacts/M20-guava-parent-android-guava.jar` `9388dba11702489680e4be376899eab28f32004292427cf644de1216d5b5a4b7`
(`guava-999.0.0-HEAD-{jre,android}-SNAPSHOT.jar`). Every `Sets*.class` differs between the sides; full tables in
`$O/logs/M20-guava-jobjar-classes.md` and `$O/logs/M20-guava-android-jobjar-classes.md`. The two that carry the change:

| Class | parent jar | fix jar |
|---|---|---|
| JRE `com/google/common/collect/Sets$SetView.class` | `a788db1ae4a8c775615e67d1838e01465efc691bf754cabcdb891915388525c6` | `51fd4c134b1436872d24b853e8db43443a173edaf1cc514457807b983991b3ad` |
| JRE `com/google/common/collect/Sets.class` | `a00e8108611d7a1f62ca52fbd7473b93166f6216ce96f998d581be231285a7a3` | `0d8d378f44ed98aa3b6e11ec7b21d406bb7ce61b1b5233e9f9698abf7d18c364` |
| Android `com/google/common/collect/Sets$SetView.class` | `6a0ceb37a12dca96772efed5d3bf2f8ce8e23df80bf8618e66578c413a15d83a` | `b4bcac1c619685416a54d3a43cb6fb5733625247b529deacdce46ac26a9bae58` |
| Android `com/google/common/collect/Sets.class` | `8b65552fcc91a75aabb3e3ea46471445885d62a916aca8d71a76b387864c8dd4` | `e8e85cfa77f0d12671f4eba615c74276925068c3f4225b8166ce93e0f016a38d` |

**Signatures** (keyring `$O/gnupg-D`, keys from keyserver.ubuntu.com): `guava-33.4.8-jre.jar`, `guava-33.4.8-android.jar`, `guava-testlib-33.4.8-jre.jar`, `truth-1.4.4.jar` good,
key `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (Christopher Povirk); `junit-4.13.2.jar` good, `FF6E2C001948C5F2F38B0CC385911F425EC61B51`.

**For the domain agent**
- Guava 33.4.8-jre is the parent side exactly; the fix overlay is the fix side, on the same classpath.
- The `SetView` subclasses the fix adds are all inside `Sets.java`, so the overlay replaces every class whose layout changed.
- The landed test does not discriminate; the iterator-count and equality observations of the brief are untested by the setup.
- Never run Guava's Maven build without `-Duser.home=$O/mvnhome`.

## Jobs

All seven were committed in `ulxnwtzsswoy` ("Queue the setup builds of the merged Java PR links brief (verification pending)") and
all seven **passed**; their results were recorded by the pipeline on the default line (`verification/results/2026/11/25/`, collected in
`ruyozwpyrzkz`, `mynnkymuytlp`, `ttuwqwvppors` and `omvqzwuyylsl`), and read from there for this record. "Passed" includes each expected-failure step: a transplant
step passes only when the named test fails.

| Job | Case | What it runs | Result |
|---|---|---|---|
| `20261125-071414-setup-build-lucene-core-at-both-14732-re` | M01 | JDK 24.0.2: lucene-core jar and `TestIndexSortSortedNumericDocValuesRangeQuery`, fix online, parent offline, fix's test on the parent offline (expected to fail `testSameHitsAsPointRangeQueryIntSort`), fix again offline | passed, 3m55s: 22/22, 21/21, transplant **1 fails** (`ClassCastException`), offline rerun 22/22 |
| `20261125-071415-setup-build-solr-core-at-both-3158-revis` | M05 | solr-core and the whole `TestJsonFacets` at both pins, fix's test and schema on the parent (expected to fail `testMultivalueEnumTypes`), offline rerun | passed, 7m16s: 30/30, 29/29, transplant **1 fails** `testMultivalueEnumTypes`, offline rerun 30/30 |
| `20261125-071415-setup-build-jooq-at-both-19875-revisions` | M16 | `-pl jOOQ package` at both pins, then the reporter's H2 `LoaderBatchStaticStatementTest` over each built jar | passed, 2m41s: 2/2 fix, **1 of 2 fails** parent, offline rebuild 2/2 |
| `20261125-071415-setup-build-guava-jre-and-android-at-bot` | M20 | Guava JRE and Android, `SetViewTest` at both pins | passed, 7m27s: JRE 2736/2736 and 2724/2724, Android 2491/2491 and 2479/2479, offline rerun 2736/2736 |
| `20261125-071708-setup-run-hikaricp-s-landed-postgrestest` | M11 | the whole `PostgresTest` on the fix, the parent's own on the parent, the fix's on the parent (only `testSchema` may fail) | passed, 7m02s: 7/7, 6/6, transplant **1 of 7 fails** `testSchema` |
| `20261125-072322-setup-run-junit-2646-s-landed-displaynam` | M19 | `DisplayNameGenerationTests` at both pins and the fix's test on the parent | passed, 3m50s: 10/10 online and offline, 8/8, transplant **1 of 10 fails** |
| `20261125-072322-setup-run-roaringbitmap-914-s-landed-fas` | M03 | both `TestFastAggregation` classes at both pins and the fix's on the parent | passed, 1m11s: 126/126 online and offline, 124/124, transplant **2 fail** (`ArrayStoreException`) |

## Signatures

Each case's section has its own signature paragraph; the keyrings are `$O/gnupg-A`, `-B`, `-C`, `-D` (one per fork), every agent stopped.
Keys were fetched one at a time (`$O/keys/`, `$O/keys-C/`). In short:
- **Good against the project's KEYS file:** Apache Commons (commons-io 2.22.0, commons-codec 1.22.0, commons-pool2 2.10.0, 2.11.0),
  DataSketches 9.0.0 and 9.1.0, Avro 1.12.2, Lucene 10.3.0 (core, codecs, test framework), Solr 9.8.1.
- **Good, key from a keyserver with nothing further vouching for it:** woodstox, stax2-api, logback, jOOλ, RoaringBitmap 1.6.30, ical4j
  4.4.0, reactor-core 3.6.10 and 3.7.0, reactor-test 3.7.0, JUnit 5.8.0-M1 and RC1 sets, jOOQ, H2, Guava, Truth, JDT core and
  org.eclipse.text (and the JDT jar's own jar signature).
- **Solr 9.8.0** (core, solrj, test framework): a good signature made 2025-01-14 by key `EDF961FF03E647F9CA8A9C2C758051CCA3A13A7F`, which had
  expired on 2024-08-13 (`EXPKEYSIG`). Recorded, not resolved.
- **RxJava 2.1.14 and 2.1.15: not verifiable.** keyserver.ubuntu.com has only a 2021 revocation of the signing key
  `1D9AA7F9E1E2824728B8CD1794B291AEF984A085` (reason "key compromised"); keys.openpgp.org's copy has no user ID and GnuPG refuses it. The jars
  rest on Central's checksums.
- **Not signed** (checked by sha256 or SHA-1 against the publisher instead): the Gradle distributions and wrapper jars, the three JDK
  tarballs above (Temurin 24 is also signed: good), the jcenter-era modules substituted for M13 and M19, HikariCP, Jackson and JTS (no KEYS
  file), the pins themselves (git commits fetched by SHA).
- Docker images (M11): `postgres:16` = `postgres@sha256:07abc3f43c9395b0bdbbab36bc25ddb0e8d83cd4fcafb5fb7d6abe14ff156dd8`,
  `testcontainers/ryuk:0.9.0` = `testcontainers/ryuk@sha256:448beed1b3fd18e9411dd4b6a26a04f3aa0fccf229502c9665ebe8d628c7d2c5`.

#### Signatures and checksums of fork C's cases (M03, M10, M13, M14, M19)

Keyring `$O/gnupg-C` (its agent stopped with `gpgconf --homedir $O/gnupg-C --kill gpg-agent`; none left running). Keys fetched one at a
time from keyserver.ubuntu.com (`$O/keys-C/KEYID.asc`); signatures from Maven Central (`$O/dl/sigs-C/*.asc`). Every jar below was also
resolved with Maven's `--strict-checksums` (`resolve.sh`).

| Artifact | Signer key (full fingerprint) | Result |
|---|---|---|
| `org.roaringbitmap:RoaringBitmap:1.6.30` jar and `-sources.jar` | `015479E1055341431B4545AB72475FD306B9CAB7` (Daniel Lemire) | good |
| `org.mnode.ical4j:ical4j:4.4.0` jar | `44C9BD32E7CB72F36F49DD0716968D251E760606` (Ben Fortuna) | good |
| `io.projectreactor:reactor-core:3.6.10` and `3.7.0`, jar and `-sources.jar`; `reactor-test:3.7.0` jar | `48B086A7D843CFA258E83286928FBF39003C0425` (Spring Builds JAR signing) | good |
| `org.junit.jupiter:junit-jupiter-api` and `junit-jupiter-engine` `5.8.0-M1` (jar and `-sources.jar`) and `5.8.0-RC1` (jar); `org.junit.platform:junit-platform-launcher` `1.8.0-M1`, `1.8.0-RC1` | `FF6E2C001948C5F2F38B0CC385911F425EC61B51` (Marc Philipp) | good |
| `io.reactivex.rxjava2:rxjava:2.1.14` and `2.1.15`, jar and `-sources.jar` | key id `94B291AEF984A085` (fingerprint `1D9AA7F9E1E2824728B8CD1794B291AEF984A085`) | **not verifiable**: keyserver.ubuntu.com returns only a revocation signature for this key (created 2021-04-17, reason 0x02 "key compromised", naming new key `E9CC3CD1AE59E851E4DB3FA350FFD7487D34B5B9`), and keys.openpgp.org returns the key without a user ID, which GnuPG refuses to import. The jars rest on Central's checksums alone. |

Not signed or not checked by signature: the Gradle distributions and wrapper jars (sha256 against services.gradle.org), the AdoptOpenJDK 9.0.4+11
and 16.0.1+9 tarballs (sha256 against each GitHub release's `.sha256.txt`), and the jcenter-era modules copied for M13 and M19 (SHA-1 against
the serving repository's `.sha1`).

## Disk

`$O` is 11 GB: worktrees 2.4 GB, `gradle-home` 3.3 GB, tools (Gradle, JDKs 9, 16, 24) 1.8 GB, `dl` 1.5 GB, `m2` 0.9 GB, `mvnhome`
(Guava's JDK downloads) 0.6 GB, release sets 0.5 GB, artifacts 61 MB. Build trees were deleted after their jars and digests were recorded,
including those of the seven jobs (each job removed its own at the end). The mirrors under `$M` hold only the pins (plus earlier setups' pins in the four shared mirrors).

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/merged-pr-links` (`$O`); `source $O/scripts/env.sh` gives `$O`, `$W`, `$MVN`, `GRADLE_USER_HOME`,
  `TMPDIR` and the JDK homes `$J8` `$J9` `$J11` `$J16` `$J17` `$J21` `$J25` (JDK 24 is `$O/tools/jdk-24.0.2+12`). The default `java` is 25.
- Both revisions of every case, at the brief's pins: `$W/MNN-MIRROR-parent` and `$W/MNN-MIRROR-fix` (full SHAs and trees in
  [Upstream revisions](#upstream-revisions); M16 also has `$W/M16-jOOQ-reporter-test`). Every PR's merge SHA is the brief's after pin, and
  every after pin's first parent is the brief's before pin.
- Built jars of both sides for every case in `$O/artifacts/`, named in each case's section with full sha256 and the digests of the changed
  classes. Built from the pins themselves: M02–M04, M06–M15, M17, M19. Overlays (each side's changed classes over a release, fixed entry
  dates): M01 (lucene-core 10.3.0), M05 (Solr 9.8.0), M16 (jOOQ 3.21.2), M18 (JDT core 3.47.0, unsigned copy), M20 (Guava 33.4.8 JRE and
  Android). Runtime classpaths are files named in each section (`$O/releases/NAME/classpath.txt` or `$O/artifacts/*classpath*.txt`).
- Release sets resolved with strict checksums in `$O/releases/`, and which side each equals: the "Release side" column of
  [Summary by case](#summary-by-case).
- Dependencies for the builds are in `$O/m2` and `$O/gradle-home`; the offline form (`$MVN -o`, `--offline`) was checked for M02, M03, M04,
  M01, M03, M05, M06, M08, M09, M10, M11, M12, M13, M14, M15, M16, M17, M19 and M20 (for M01, M03, M05, M16, M19 and M20 by the
jobs, which passed). Exact commands are in each case's section.

### What was verified on a JVM

- The landed regression passes on the fix and fails on the parent (the fix's test moved onto the parent) for M01 (overlay run, the brief's
  `ClassCastException`), M02, M04, M06, M07, M08, M09, M10, M11 (`testSchema`), M12, M13, M14, M15, M17 (both modules) and M18 (overlay run,
  `StringIndexOutOfBoundsException: Index -1`); for M16, the reporter's H2 test from `5a98d74deb44ca78838d4b62e376dbc4a704cc0f` passes on
  the fix overlay and fails on the parent's ("Expected Bob, got: [Alice, Alice, Alice]"). Counts per side are in the summary table.
- M20: the landed `SetViewTest` passes at both pins, but the fix's copy does not compile on the parent (`minSize()`/`maxSize()` are
  fix-only), so no landed test separates the sides.
- By the seven jobs, all passed (see [Jobs](#jobs)): M03 (both `priorityQueueOrAcceptsSubtypeArray()` tests fail on the parent with
  `ArrayStoreException`), M05 (`testMultivalueEnumTypes` fails on the parent: "List size mismatch @ facets/f/buckets"), M19
  (`indicativeSentencesGeneratorOnNestedClass()` fails on the parent), and the upstream builds of M01, M16 and M20 and the whole M11
  class, which agree with the overlay and inline runs above.
- So the landed (or, for M16, the reporter's) regression separates the sides in **19 of 20 cases**; M20 is the exception.
- **None of the brief's claim scenarios was run** in any case.

### What to know before starting

- **JDKs:** M01's pins build only on JDK 24 (its overlays run on 21 or 25); M04's jars need JDK 25 to run; M15 builds on 21; M12 and
  M13 on 8; Jackson 3 (M07) needs 17+; `jool` needs 11+, `jool-java-8` runs on 8; M14 needs toolchains 9 and 21 (`$O/scripts/M14-gradle.sh`),
  M19 JDK 11 plus 16 (`$O/scripts/M19-gradle.sh`).
- **M07, unstable input:** the pins' `3.2.0-SNAPSHOT` parent and dependencies are gone from the snapshot repository; the built jars are
  each pin's csv sources compiled over released jackson-core/databind 3.2.0, without `module-info` (`$O/scripts/m07_build.sh`).
- **M11:** Testcontainers 1.20.3 needs `-Dapi.version=1.44` on this Docker 29; pin `postgres:16` by its digest ([Signatures](#signatures)).
- **M05:** the parent's `schema_latest.xml` has no `severity_mv`; a parent-side run needs the field supplied. 9.8.0 = parent, 9.8.1 = fix.
- **M15:** logback 1.5.9 is **not** the fix (its `setOutputStream` keeps an `isStarted()` guard). Its tests need `-Dsurefire.useModulePath=false`.
- **M03:** Central's RoaringBitmap 1.6.30 has the pins' version label but is an older tree; use the built jars.
- **M18:** use the unsigned copy `$O/artifacts/M18-org.eclipse.jdt.core-3.47.0-unsigned.jar` under an overlay. Whether `ToolFactory.createCodeFormatter`
  (the brief's public route) works on a plain classpath was not tried.
- **M20:** run Guava's Maven build only with `-Duser.home=$O/mvnhome`.
- **M16:** jOOQ's upstream POM has no H2 dependency; the reporter's test runs outside Maven with H2 2.4.240 and checks names only.
- **M02:** the transplanted landed test errors inside the fix's failure-printing helper (`MissingFormatArgumentException`), not with an assertion.
- **M19:** `$W/M19-junit-framework-*` are standalone clones, not worktrees.
- **Signatures:** RxJava 2.1.14/2.1.15 cannot be verified (signing key revoked as compromised); Solr 9.8.0 is signed by an expired key.
  Plugin modules substituted for M13 and M19 rest on SHA-1 checks. See [Signatures](#signatures).
- **M16:** the jOOQ jar is not byte-reproducible between two builds of one pin; compare the class digests in its section.
- **M01, M05, M16, M20** have both overlay jars (over a release) and jars built from the pins in `$O/artifacts/`; the sections give both.
  The Solr pin jars' runtime classpath was not exported.
- The job results live on the default line (`verification/results/2026/11/25/`); this workspace's line does not contain them until it is merged.

### What is left for the domain work on purpose

- Every claim, example folder, example id, adapter, sidecar, observer and recipe; the brief's public scenarios and challenge histories
  (none was run or probed).
- Choosing, per case, whether the built pins, the overlays or a published release stand for each side.
- The PostgreSQL-side results the brief leaves open (M16), a Tycho build of JDT (M18), and the brief's `ToolFactory` route on a plain classpath.
