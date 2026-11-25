# Setup for the merged Java pull requests L01–L20 brief

Mechanical setup for [`organic-java-merged-pr-links-l01-l20-brief.md`](organic-java-merged-pr-links-l01-l20-brief.md), done on
2026-11-25 by a setup session (Claude Opus 5.5) and forks of it, before the domain work starts. The session writes
no claims, examples, sidecars, adapters or checker code, allocates no example ids, and runs neither the project
verifier nor JBMC. Everything fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/merged-pr-links-l01-l20`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR`, `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin, under `~/.sdkman/candidates/java/`) and `$MVN`
(Maven 3.10.0 with `-s $O/maven-settings.xml -t $O/toolchains.xml`, local repository `$O/m2`).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `L01`–`L20` follow the brief's order (and the order of the PR list
[`organic-java-merged-pr-links-l01-l20.md`](organic-java-merged-pr-links-l01-l20.md)). They are this record's labels only, not example ids.

## Starting commit

Checkout at setup: `5aaa66ad75a9aa2a4883f2c2ec650b5725a811a9` (`develop@origin`, "Queue the brief organic-java-merged-pr-links-r01-r50-brief").

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds the pinned commits (`refs/pins/ROLE-SHA`), fetched by SHA
(depth 1) from each project's GitHub repository, one request at a time (`$O/scripts/pins.tsv`, `$O/scripts/fetch.sh`,
log `$O/logs/fetch.log`: 40 of 40 fetched). Mirrors that already existed (`gson`, `commons-collections`, `junit-framework`, `jgrapht`,
`calcite`, `guava`, `ical4j`, `RxJava`) gained these pins beside earlier setups' ones. One worktree per revision, `$W/CASE-MIRROR-ROLE`
(`$O/scripts/worktrees.sh`; `parent` = the brief's before pin, `fix` = its after pin). Trees and parents were read from the commit
objects (`$O/logs/pins-parents.tsv`; shallow history hides them from `git log`).

- **Every PR is merged, and its `merge_commit_sha` (from `gh api`, `$O/upstream/prs/CASE-OWNER_REPO-N.json`) equals the
  brief's after revision.** Changed-file lists per PR are in `$O/upstream/prs/CASE-files.tsv`.
- **For 19 cases the after revision's first parent is the brief's before revision.** L04, L11, L12, L15 and L17 are two-parent merges
  (the brief's before pin is the first parent); the rest are squash or rebase commits with one parent.
- **L03 (picocli) is a rebase of three commits**, as the brief says: the after pin's parent is `e5ee68b51e4ccab2d8b6d624859c1458dad88b23`
  ("Renamed variables"), whose parent `db2da0543e774c3406b32770c260918cfbc10e6b` (the implementation) has the brief's before pin as its
  parent. The picocli mirror was deepened to 4 commits for this (`$O/logs/L03-landed-chain.txt`).
- The diff before→after of every case names exactly the PR's changed files (diffstats in `$O/logs/CASE-landed-diffstat.txt`).

| Case | Worktree | Commit | Tree | Parents | Date | Subject |
|---|---|---|---|---|---|---|
| L01 | `L01-gson-parent` | `961517decce0aa907c285c19d8b93d5c746ecdcb` | `cb5b88885c474058e883a4f01664546e7f9ea38a` | `e25d4fab7fd54f267c765d975acccddfdddc9cda` | 2026-07-23 | Fix URI type adapter to preserve identity for non-ASCII URIs (#3067) |
| L01 | `L01-gson-fix` | `5e277e42786ab6441b7dd6b1a8c34d545d132307` | `0c4b60829c7bb7908a9c070db9737f48135ed934` | `961517decce0aa907c285c19d8b93d5c746ecdcb` | 2026-07-23 | Fix JsonPrimitive.hashCode to honor the equals/hashCode contract (#992) (#3059) |
| L02 | `L02-commons-collections-parent` | `a70ffd614602fa07d2429d76f77abcd1816d0be9` | `9b07844763da614623f4e0c4d3a33fb382e1e57d` | `c119c75f6ae460ec152ea30ed2d1cffa09bfe738` | 2026-07-02 | Fix trailing whitespace |
| L02 | `L02-commons-collections-fix` | `e218502f9f82237404bbce8e8ba5f81ffb467198` | `d56966653251cdd6f29f88d7b0e0ae404b1b6434` | `a70ffd614602fa07d2429d76f77abcd1816d0be9` | 2026-07-03 | Fix stale size in AbstractMapMultiSet view iterator remove (#701) |
| L03 | `L03-picocli-parent` | `4090e3dd30f9a046a72a1450972848d55e656160` | `53678c040689098499b68dcbf280f2387b201003` | `2c7a0eb5aae758f7f72fcb76e52b9c7ff161e4a7` | 2022-02-04 | DOC document cron schedule string in codeql-analysis.yml |
| L03 | `L03-picocli-fix` | `edd902c0348d3548afac12096b0b16ab69f52a79` | `7c2ecd9468bb8b7a8e719759f33cf72e4b7cc355` | `e5ee68b51e4ccab2d8b6d624859c1458dad88b23` | 2022-02-07 | Added test Issue1528#testSubCommandAliasModification |
| L04 | `L04-java-diff-utils-parent` | `eb188a96eacff8e80877714d42fa9e2fd4fec32a` | `0f9215515dfffb4e35eb4e4ce453617fcfe21a78` | `5e2e5b981533964aaeb19e2ba56d0f53dbd8b2dc` `c11f205622bb6c49a8b597ee9cceb050d0c19491` | 2026-09-18 | Merge pull request #232 from youdie006/fix/verify-chunk-end-boundary |
| L04 | `L04-java-diff-utils-fix` | `6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b` | `e7207e8b8bf3d11fa84a8067a36a6a463818ed1f` | `eb188a96eacff8e80877714d42fa9e2fd4fec32a` `d072d124b6db71d0c482f652c94eeeb3cc2fc8b4` | 2026-09-18 | Merge pull request #233 from Chanakan5591/fix/equal-delta-diff-rows |
| L05 | `L05-junit-framework-parent` | `bbeb7900fa76b6fc00e36e0bea05747066b4a2ec` | `cdd5ae4e0e541af01c504a9a5f6162914d0f205b` | `090730b1dbcff423ba936c4634d0b3b80da5c6be` | 2026-10-02 | Update graalvm/setup-graalvm action to v1.6.7 (#6113) |
| L05 | `L05-junit-framework-fix` | `2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6` | `6165c70ffefa6eaaf77ef764f9d0d61f5427ae1e` | `bbeb7900fa76b6fc00e36e0bea05747066b4a2ec` | 2026-10-02 | Fix support for inherited same-name nested classes (#6104) |
| L06 | `L06-arrow-java-parent` | `46211fccf642d6dcfcebc31081817da1529d6a35` | `6da2a6fe2fdfbfb542e009d606527b28d68e5e90` | `32984435ed1ffbe6ce1578e075da6eeb012d6bbb` | 2026-02-17 | MINOR: Bump com.gradle:develocity-maven-extension from 2.3.1 to 2.3.3 (#1001) |
| L06 | `L06-arrow-java-fix` | `9fd4973d12abbd9e9d14098c2acd41d97a6c4407` | `fdb83088ccfe11e9da93bdd7a389d72a3d89cd00` | `46211fccf642d6dcfcebc31081817da1529d6a35` | 2026-02-17 | GH-470: [Vector] Fix ListViewVector.getElementEndIndex(index) method (#1019) |
| L07 | `L07-jgrapht-parent` | `e7ae7a506ca4c2943878247a6e02bf71abc9b2d4` | `3ebe514d373bd450f943cd834ffcb874a31d13aa` | `556981de1b9d13f057e0948f0a1dc6a94075c964` | 2019-06-08 | Credits for last merge. |
| L07 | `L07-jgrapht-fix` | `26630083eda568be7099c408638ce31c4d94b4a4` | `2eaac1fe7e49443c88fa7fe139a82801a4a60632` | `e7ae7a506ca4c2943878247a6e02bf71abc9b2d4` | 2019-06-13 | K disjoint paths null pointer bug fix v2 (#792) |
| L08 | `L08-commons-statistics-parent` | `bfcc6e62e2960512ff699809434d5d7774bf16dd` | `41bd0a3bede7a905b488dd2295704af402149b35` | `c8700034dfd9020c433bb3a2ce1b4aadf450c6b0` | 2026-10-31 | Bump org.apache.commons:commons-parent from 106 to 107 |
| L08 | `L08-commons-statistics-fix` | `2535c20ad85ce756c0d396151d83e7fc4e2c904c` | `097f1c10f9ee32f631dbfb5744e59670c5377094` | `bfcc6e62e2960512ff699809434d5d7774bf16dd` | 2026-11-06 | STATISTICS-102: Fix the Cauchy distribution quantile function in the tails (#140) |
| L09 | `L09-rdf4j-parent` | `c2c7a5265e6c40bc5dc2574260c96c3e10f9a87c` | `a66e09e46af8823299622e5867d4f5b326f1b98f` | `f0b1e96e04d3758534e72d375968d4321d70f4e3` `2eda91cb96c94e867b887b4d97fa4abc586a4557` | 2020-03-11 | Merge pull request #1991 from aschwarte10/issues/#1990-fix-fedx-initialization-order |
| L09 | `L09-rdf4j-fix` | `1767ceebe5d309238263bdca732b730cc47b3e45` | `dbe8c6a5da7a5261e5582647d4b4dc10d9d4f53c` | `c2c7a5265e6c40bc5dc2574260c96c3e10f9a87c` | 2020-03-13 | GH-1978 fix handling of empty results in grouping/aggregate |
| L10 | `L10-calcite-parent` | `b8ccec91b7670d8c62a5712e210bb25f396ade7e` | `1504f135fc021b3f1c4e2bb19c496fdbc9b838be` | `fdabee35b0ab2003c7c1352b83ef28667fcd51c7` | 2026-11-15 | [CALCITE-7883] RelToSqlConverter strips outer qualifier in visitAntiOrSemiJoin, so INTERSECT/EXCEPT  |
| L10 | `L10-calcite-fix` | `5f48eec8d5e3f25df641393c9440e086646868b7` | `f5465be82548360999021be1a9a4a5643d8d9cdc` | `b8ccec91b7670d8c62a5712e210bb25f396ade7e` | 2026-11-15 | [CALCITE-7909] `ProjectSetOpTransposeRule` returns wrong results for `EXCEPT ALL` and `INTERSECT ALL |
| L11 | `L11-commons-imaging-parent` | `4881f0b503d39e210b4fed29e25b26cbbefd5cd8` | `d797ad2fea369b2487bb887c0d893881eb65cfe7` | `50e3dc5a6a2b802de5c061afd493616a81bcfb68` `56f68144f1d74789b2f24e4f175cc8b76a5ac50a` | 2023-11-17 | Merge pull request #336 from apache/dependabot/github_actions/github/codeql-action-2.22.7 |
| L11 | `L11-commons-imaging-fix` | `cbdb978098a042cb5fd2a768f6d8575835c28278` | `d02e5b1ee51bb332495e7632914b87a972091f35` | `4881f0b503d39e210b4fed29e25b26cbbefd5cd8` `fd7e23527830b3469f9c1b8fb567694b8da5838d` | 2023-11-21 | Merge pull request #335 from gwlucastrig/Imaging194a |
| L12 | `L12-quartz-parent` | `dccb522cd8675894996a0dc206461a08f8cf9eaf` | `7003419d62de9a60793f60616c49b8e01f870031` | `3b43016d4de3667bb336f0ff991d8fb164be0c95` `89cc71d5d86aad2d43cbf86fdd010b6c7cec5958` | 2026-08-05 | Merge pull request #1493 from e210/fix/1464-informix-simprop-triggers-sql |
| L12 | `L12-quartz-fix` | `adeae66354ff66cc4c716dd3aaac09e1571f64fa` | `ac50ee9cd3fe42bce1590f1df6fe6e893beb97d9` | `dccb522cd8675894996a0dc206461a08f8cf9eaf` `0f0795e9d18dd3ab158d36e254fc1cac033d8bbd` | 2026-08-05 | Merge pull request #1496 from kalayciburak/fix/920-replace-trigger-type-change |
| L13 | `L13-maven-shade-plugin-parent` | `26b587384bb664daf59c30e72693ee1ae105fd71` | `376f1ae9b3a6f9558b2d118a903b0cf667ff8901` | `3994b11b02182db588aa76d928b9ecc949ef15c3` | 2022-09-05 | gha shared v3 |
| L13 | `L13-maven-shade-plugin-fix` | `ad2f6f8e7855860b69b950d14ca8ec627b099d6b` | `8fe6eab32e00c18743224c2efe9e6d229bb79fd6` | `26b587384bb664daf59c30e72693ee1ae105fd71` | 2022-09-05 | [MSHADE-425] Relocate services name before add to serviceEntries |
| L14 | `L14-iceberg-parent` | `4ca3f10832907540eee798236fa401eb07c7e7df` | `4563a5266de935e7de6405349c9a71f363d98b03` | `a654f3f91c770a96aa81c31f17274d9391d8f7fc` | 2025-05-19 | Flink: Backport fix watermark no pass in TaskResultAggregator to Flink 1.19 and 1.20 (#13085) |
| L14 | `L14-iceberg-fix` | `a7f3dc79a2f42a4875ac35eec2137ecff15204fc` | `95432fc9eea162e75c326a2d08eccbcab68e2039` | `4ca3f10832907540eee798236fa401eb07c7e7df` | 2025-05-19 | Core: Copy ByteBuffers when Copying GenericRecord(#12855) |
| L15 | `L15-gradle-parent` | `fda88b3fb300707d2ec2d2839f94184dabf6852c` | `159860416c2d0bb6c6ab59061cd97e6b0800c9c7` | `8121f97802af6aacba3327807781afbb4596c53f` `d7605dd5bb301ab7dfb67f5ecca34636bdda9bb2` | 2022-06-23 | Merge pull request #21086 Fix hashing for known implementation snapshots |
| L15 | `L15-gradle-fix` | `9e244e0ace2e7698374f5199570e09295950683a` | `28d5173f9ed130d271141cf6ea50bf91af13a347` | `fda88b3fb300707d2ec2d2839f94184dabf6852c` `9f063d91e40c2a0864ed3cc4a3ede214d7e86975` | 2022-06-23 | Merge pull request #21084 Fix up-to-date checks for named task actions |
| L16 | `L16-guava-parent` | `8c31d52687cf03346635e29b3c5529e183c3f6ee` | `fc1d515d7137bad52222e3f514d2f22289a000f1` | `19cfef214c62c42466cb067a949207794f837d36` | 2024-06-24 | Bump gradle/wrapper-validation-action in the github-actions  group |
| L16 | `L16-guava-fix` | `dc80e7e9f3844381aacc93ee1e043a711f1feffb` | `eec6346c9eae2572ee4cc7563ff3272041a19590` | `8c31d52687cf03346635e29b3c5529e183c3f6ee` | 2024-06-24 | Optimize Futures.allAsList handling of already completed Futures. Skips adding a listener on already |
| L17 | `L17-ical4j-parent` | `a0ba59c562e38ee4e0839069b58b1fec27d1e673` | `ff6c9aadd32f02a923e17a5fdd15668788475172` | `c493f62a82cf25eac80df9ba7e61a8033625c170` `c4a818b94e013abf1a4c796ef3bd8461af6e657b` | 2026-11-03 | Merge pull request #962 from Shrusti-pk/xproperty-value-line-breaks |
| L17 | `L17-ical4j-fix` | `5e2c93fce7835ad9c951a4e6e6d4469464d63805` | `e0cfa914efce0d37ac77771c4a1cccb30b4eaa4d` | `a0ba59c562e38ee4e0839069b58b1fec27d1e673` `754cc4f71b0673910154da6da27b349429dc8263` | 2026-11-03 | Merge pull request #947 from vera-rubin/fix/utc-exdate |
| L18 | `L18-RxJava-parent` | `f1a795da0d4cdfb3133206ad8e3887bdb8ba948b` | `93f72ebf75ba9af0549c963fd79b4d6b9295b0c0` | `b3516b2fbf76643d4fce2bb077de64deaf959f90` | 2020-01-28 | 3.x: Swap Maybe.flatMapSingle and Maybe.flatMapSingleElement (#6891) |
| L18 | `L18-RxJava-fix` | `5f6aafcbaa97f330ad2007f4ad02c5e33db8914b` | `1156d1214919b7a13c07255631fa862395677e9e` | `f1a795da0d4cdfb3133206ad8e3887bdb8ba948b` | 2020-01-29 | 3.x: Fix groupBy not requesting more if a group is cancelled w/ items (#6895) |
| L19 | `L19-kafka-parent` | `a4f7675db1a928e73c7a69eb906dd1e9ecd4a22a` | `159cc5a0b5b2548c0f6a2d266248ce39819c3fd5` | `b074173ea249ef028272c2c07358222550917d8c` | 2019-05-02 | KAFKA-8285: enable localized thread IDs in Kafka Streams (#6632) |
| L19 | `L19-kafka-fix` | `eab855541a4b776b150a849cecda9c758598cdca` | `833782f6d35b5f0a37e156e517fb896b1b35ead4` | `a4f7675db1a928e73c7a69eb906dd1e9ecd4a22a` | 2019-05-02 | KAFKA-8289: Fix Session Expiration and Suppression (#6654) |
| L20 | `L20-JSqlParser-parent` | `cf6c83ce8f3fac6393356c57baeb1a4a3dee7913` | `efe3da31249102020e2bb07742a100321813603a` | `eba50028184174bcdaebe2532fbdfaaccfe8a117` | 2026-10-13 | Allow `ERRORS` as an unquoted identifier (#2781) |
| L20 | `L20-JSqlParser-fix` | `0a7436a10301e118802a4b7effba056de22ee7f8` | `08045f2ccfa7f7ed38439ccd8b0080a4558c588b` | `cf6c83ce8f3fac6393356c57baeb1a4a3dee7913` | 2026-10-13 | Fix ALTER deparser dispatch for inactive column metadata (#2770) |
