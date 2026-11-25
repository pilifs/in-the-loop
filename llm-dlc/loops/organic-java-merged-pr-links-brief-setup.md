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
