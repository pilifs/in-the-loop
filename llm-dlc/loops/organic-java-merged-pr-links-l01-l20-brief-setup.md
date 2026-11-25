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

## Toolchain and shared files

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` (`$J8` … `$J25`) | the installations of the earlier setups |
| Temurin 24.0.2+12 (L05's `JDK24` toolchain) | `~/.cache/in-the-loop/merged-pr-links/tools/jdk-24.0.2+12` | checked by the earlier setup (its record's toolchain table) |
| Maven 3.10.0 | on `PATH` | used for L01, L02, L04, L07, L08, L11, L13, L16, L20 |
| Maven 3.9.9 (L06, L09: Maven 3.10.0 cannot build them) | `$O/tools/apache-maven-3.9.9` | sha512 = Maven Central's `.sha512`, signature good (see the L06 section's Build facts) |

Caches and files this work owns:
- `$O/m2`, the Maven local repository named by `$O/maven-settings.xml`; `$O/toolchains.xml` names JDKs 8, 11, 17, 21 and 25.
- `$O/gradle-home`, the shared `GRADLE_USER_HOME`; `$O/gradle-home-L15` is L15's own.
- `$O/releases/NAME/`: release graphs resolved from Maven Central with `--strict-checksums` by `$O/scripts/resolve.sh NAME G:A:V...`
  (`lib/`, `sources/`, `tree.txt` and an ordered `classpath.txt`).
- `$O/artifacts/`: built jars, class digests and classpath files. `$O/logs/`: build and test logs. `$O/notes/CASE.md`: each case's section as written.
- `$O/upstream/prs/`: each PR's `gh api` record and changed-file list.
- Keyrings `$O/gnupg-A`, `-B`, `-C`, `-D` (one per fork of this session), every agent stopped; keys in `$O/keys-A/` … `$O/keys-D/`.
- Build helpers by fork: A `mvn_A.sh`, `submit_A.py`; B `notes_B.py`, `submit_B.py`; C `gradle_case_C.sh`, `L05-gradle.sh`, `printcp_C.init.gradle`,
  `classdiff_C.py`, `srccmp_C.py`, `rxjava3-jcenter-substitute.init.gradle`, `submit_C.py`; D `resolve-all.init.gradle`,
  `kafka-jcenter-substitute.init.gradle`, `cp_export_D.py`, `classdigests_D.sh`, `notes_D.py`, `submit_D.py` (all in `$O/scripts/`).
  `notes_B.py` and `notes_D.py` rewrite their cases' sections from the job logs once the jobs are back.
- Standalone depth-1 clones instead of linked worktrees (their builds read git metadata through JGit): `$W/L05-junit-framework-{parent,fix}` and
  `$W/L19-kafka-{parent,fix}`, at the pinned commits.

#### Gradle distributions and wrapper checksums added by fork C

Zips in `$O/dl/gradle-C/` with services.gradle.org's `.sha256` beside them, unpacked in `$O/tools/gradle-VERSION`. Fork D shares `$O/tools`.

| Gradle | Cases | zip sha256 (= services.gradle.org's `.sha256`) | Note |
|---|---|---|---|
| 7.3.3 | L03 | `b586e04868a22fd817c8971330fec37e298f3242eb85c374181b12d637f80302` |  |
| 9.8.0 | L05 | `bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c` | also = JUnit's `distributionSha256Sum` |
| 6.0.1 | L18 | `d364b7098b9f2e58579a3603dc0a12a1991353ac58ed339316e6762b21efba44` |  |
| 8.5 | L12, L17 | `9d926787066a081739e8200858338b4a69e837c3a821a33aca9db09dd4a41026` | copied from the earlier setup's checked zip, re-checked |

Wrapper jars in the repositories (not used; the distributions above run directly), against services.gradle.org's published wrapper-jar checksums:

| Case | `gradle-wrapper.jar` sha256 (both pins) | equals the published wrapper jar of |
|---|---|---|
| L03 | `33ad4583fd7ee156f533778736fa1b4940bd83b433934d1cc4e9f608e99a6a89` | 7.3.3 (`$O/dl/gradle-C/gradle-7.3.3-wrapper.jar.sha256`; the same jar was published for neighbouring versions) |
| L05 | `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d` | 9.7.1 (`$O/dl/gradle-C/gradle-9.7.1-wrapper.jar.sha256`; the same jar was published for neighbouring versions) |
| L12 | `91941f522fbfd4431cf57e445fc3d5200c85f957bda2de5251353cf11174f4b5` | 8.0.2 (`$O/dl/gradle-C/gradle-8.0.2-wrapper.jar.sha256`; the same jar was published for neighbouring versions) |
| L17 | `76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3` | 9.1.0 (the earlier setup's `~/.cache/in-the-loop/merged-pr-links/dl/gradle/wrapper-C/gradle-9.1.0-wrapper.jar.sha256`: equal) |
| L18 | `3dc39ad650d40f6c029bd8ff605c6d95865d657dbfdeacdb079db0ddfffedf9f` | 5.6.4 (`$O/dl/gradle-C/gradle-5.6.4-wrapper.jar.sha256`; the same jar was published for neighbouring versions) |

No JDK was added: L05 uses the earlier setup's checked Temurin 24.0.2+12 (`~/.cache/in-the-loop/merged-pr-links/tools/jdk-24.0.2+12`) as its `JDK24` installation; the rest use the sdkman Temurin 8, 11, 17, 25.

Other files of fork C: `$O/scripts/gradle_case_C.sh` (one Gradle run with log and JUnit summary), `L05-gradle.sh`, `printcp_C.init.gradle` (prints a configuration's files), `classdiff_C.py` (class digests that differ between two jars), `srccmp_C.py` (a source file in a sources jar against both pins), `sigs_C.sh` + `sigs_C.txt`, `l18_add_module.sh`, `rxjava3-jcenter-substitute.init.gradle`, `submit_C.py`; keyring `$O/gnupg-C` (agent stopped), keys `$O/keys-C/`, signatures `$O/dl/sigs-C/`, Central metadata read `$O/dl/meta-C/`.

| Tool (fork D) | Where | Identity |
|---|---|---|
| Gradle 8.14.4 (L10 Calcite) | `$O/tools/gradle-8.14.4` | zip sha256 `f1771298a70f6db5a29daf62378c4e18a17fc33c9ba6b14362e0cdf40610380d` = published `f1771298a70f6db5a29daf62378c4e18a17fc33c9ba6b14362e0cdf40610380d` = the wrapper's `distributionSha256Sum` |
| Gradle 8.14 (L14 Iceberg) | `$O/tools/gradle-8.14` | zip sha256 `61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa` = published `61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa` = the wrapper's `distributionSha256Sum` (zip copied from the earlier setup's checked copy) |
| Gradle 5.4.1 (L19 Kafka) | `$O/tools/gradle-5.4.1` | zip sha256 `7bdbad1e4f54f13c8a78abc00c26d44dd8709d4aedb704d913fb1bb78ac025dc` = published `7bdbad1e4f54f13c8a78abc00c26d44dd8709d4aedb704d913fb1bb78ac025dc` |
| Gradle 7.5.1 (L15: runs Gradle's own build; release without the fix) | `$O/tools/gradle-7.5.1` | zip sha256 `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4` = published `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4` |
| Gradle 7.6 (L15: release with the fix) | `$O/tools/gradle-7.6` | zip sha256 `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` = published `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` |
| Gradle 7.6 built from the L15 pins | `$O/tools/gradle-pin-L15-parent`, `$O/tools/gradle-pin-L15-fix` | built by job `20261125-172547-setup-build-gradle-distributions-at-both` |

The zips and published `.sha256` files are in `$O/dl/gradle-D/`. No JDK was added: L10 uses 21 and 25, L14 17, L15 11 (toolchains 8, 11, 17), L19 8.
Fork D's init scripts: `$O/scripts/resolve-all.init.gradle` (tasks `setupResolveAll`, `setupWriteClasspath`; adds tasks only),
`$O/scripts/kafka-jcenter-substitute.init.gradle` (L19), `$O/scripts/gradle-L15-openmbee-substitute.init.gradle` (L15). Helpers: `cp_export_D.py`, `classdigests_D.sh`, `sig_check_D.sh`, `add_module_D.sh`,
`notes_D.py` (writes these notes; re-run after the jobs), `submit_D.py` (the four jobs). Own `GRADLE_USER_HOME` for L15: `$O/gradle-home-L15`.


## Summary by case

"Release side" says which side of the PR a published release's changed source equals. "Landed tests" is fix's tests on the fix /
parent's own on the parent / fix's tests on the parent. L15 has no landed-test result: its build stopped before any test ([Jobs](#jobs)).

| Case | Built | Release side | Landed tests | Upstream run |
|---|---|---|---|---|
| L01 Gson #3059 | source build of gson module, JDK 17 | 2.14.0 = parent; 2.15.0 = fix logic (refactored hashCode) | 31/31, 30/30, 1 fails testEqualsAndHashCodeAcrossNumberTypes | inline |
| L02 Commons Collections #701 | source build, JDK 17 | 4.5.0 = parent iterator code (other diffs); 4.6.0 has fix + later changes | 214/214, 210/210, 3 fail (Hash, Predicated, Synchronized; expected 2 but was 5) | inline |
| L03 picocli #1529 | Gradle 7.3.3, JDK 11, root jar at both pins | 4.6.3 has the fix (+ later changes); 4.6.2 predates the parent | 1 f0 e0 s0 / no test at parent / FAILS 1 f1 e0 s0 (AssertionError Issue1528.java:42) | inline |
| L04 java-diff-utils #233 | source build of java-diff-utils module, JDK 17 | 4.17 = parent, 4.18 = fix (renderer file) | 6/6, 4/4, 2 fail (EQUAL vs CHANGE) | inline |
| L05 JUnit #6104 | Gradle 9.8.0, JDK 25 + toolchains 17/21/24/25, standalone clones; both sides' jars by job | 6.2.0-M1 = fix (3 changed files); 6.1.3 = parent resolver, NestedClassTestDescriptor differs | 56 f0 e0 s0 / 53 f0 e0 s0 / landed transplant does not compile (renamed constants); constant-mapped transplant: 56 run, 3 fail (nestedTestClassesWithSameName..., deeplyNestedInherited...ViaUniqueId, nestedClassTemplateIsInherited) | jobs 20261125-162622-setup-build-junit-6104-at-both-revisions (passed), 20261125-170100-setup-run-junit-6104-s-landed-nested-cla (passed) |
| L06 | source build -pl vector -am (Maven 3.9.9, JDK 17) | none = parent; 19.0.0 has the fix's file (+3 later files) | 64/64 fix, 56/56 parent, transplant 8 fail (4 new end-index tests x 2 allocators) | inline |
| L07 | source build jgrapht-core (JDK 8) | 1.3.1 = parent's three algorithm files; none = fix | 43/43 fix, 41/41 parent, transplant 2 errors (NullPointerException) | inline |
| L08 Commons Statistics #140 | source build of distribution module, JDK 17; commons-rng 1.8-SNAPSHOT dependency | 1.3 = parent quantile code (older NaN checks); no release has the fix | 58/58, 56/56, 2 fail (tail quantiles) | inline |
| L09 | source build evaluation -am (Maven 3.9.9, JDK 8); compliance by job | 3.1.2 = fix (sources of all 24 runtime modules, evaluation jar class-identical) | fix: MemoryComplexSPARQLQueryTest 81/81, SPARQL12QueryTest 2/2, GroupIteratorTest 9/9 (online and offline); parent's own: 78/78, 8/8; transplant: 5 fail (3 Max/Min/Sample empty-group, 'agg on empty set, explicit grouping', testMaxEmptySet_Grouped) | inline + jobs 20261125-162448-setup-run-rdf4j-1989-s-landed-empty-grou, 20261125-165913-setup-run-rdf4j-1989-s-landed-compliance |
| L10 Calcite #5378 | Gradle 8.14.4, JDK 21 + toolchain 25 (job) | none has the fix; 1.42.0 has the parent's rule source | junit tests=1006 failures=0 errors=0 skipped=4 / junit tests=1006 failures=0 errors=0 skipped=4 / junit tests=1007 failures=3 errors=0 skipped=4 | job 20261125-161916-setup-build-calcite-core-at-both-5378-re |
| L11 Commons Imaging #335 | source build, JDK 17 | none equals parent; 1.0.0-alpha4..6 carry the fix's limits | 2/2, 2/2, 2 errors (AIOOBE Index 64) | inline |
| L12 Quartz #1496 | Gradle 8.5 on JDK 17, toolchain 11, :quartz jar at both pins | none has the fix; 2.5.2 = parent logic (one unrelated line differs) | 38 f0 e0 s2 / 36 f0 e0 s2 / FAILS 38 f1 e0 s2 (JdbcJobStoreTest.testStoreTriggerReplaceChangesTriggerType) | inline |
| L13 | source build (JDK 11) | 3.4.0 = fix (all sources); 3.3.0 = parent except DefaultShader | 4/4 fix, 3/3 parent, transplant 1 error (ZipException duplicate entry) | inline |
| L14 Iceberg #12855 | Gradle 8.14, JDK 17 (job) | 1.9.2 = parent, 1.10.0 = fix (GenericRecord) | junit tests=48 failures=0 errors=0 skipped=1 / junit tests=39 failures=0 errors=0 skipped=1 / junit tests=48 failures=9 errors=0 skipped=1 | job 20261125-165654-setup-build-iceberg-api-core-data-parque |
| L15 Gradle #21084 | Gradle's build on Gradle 7.5.1 (pinned nightly gone), JDK 11; NOT built: pinned grolifant-0.16.1.jar gone, Central's fails the build's verification | none equal; 7.5.1 lacks fix, 7.6 has fix + later | **not run**: build failed first (':build-logic:cleanup:compileKotlin') / **not run**: build failed first (':build-logic:cleanup:compileKotlin') / **not run**: build failed first (':build-logic:binary-compatibility:compileGroovy') | job 20261125-172547-setup-build-gradle-distributions-at-both |
| L16 | source build JRE + Android by job (JDK 21) | 33.3.0 has the fix's file; 33.2.1-jre = parent's file minus an annotation | no landed test; FuturesTest 160/160 at both pins, JRE and Android (job) | job 20261125-162448-setup-build-guava-7277-s-two-revisions-j |
| L17 iCal4j #947 | Gradle 8.5, JDK 17, jar at both pins | none has the fix; 4.4.0 older than the parent, has its EXDATE line | 20 f0 e0 s0 / 19 f0 e0 s0 / FAILS 20 f1 e0 s0 (testCalculateRecurrenceSetWithUtcExDate) | inline |
| L18 RxJava #6895 | Gradle 6.0.1, JDK 8, init script for 4 jcenter-only build-script modules | 3.0.0-RC8 = parent, 3.0.0-RC9 = fix (FlowableGroupBy.java) | 67 f0 e0 s1 / 66 f0 e0 s1 / FAILS 67 f1 e0 s1 (cancelledGroupResumesRequesting) | inline |
| L19 Kafka #6654 | Gradle 5.4.1, JDK 8, grgit substitute (job) | 2.2.0 = parent logic, 2.2.1 = fix logic | junit tests=26 failures=0 errors=0 skipped=0 / junit tests=25 failures=0 errors=0 skipped=0 / junit tests=26 failures=6 errors=0 skipped=0 | job 20261125-161917-setup-build-kafka-streams-at-both-6654-r |
| L20 JSqlParser #2770 | source build, JDK 17 (fix inline; parent by job, passed) | none (5.4 predates) | 128/128, 107/107 (TablesNamesFinderTest), landed transplant does not compile (hasActiveColumnDefinitions); modified copy without those 6 lines: 16 fail | job 20261125-162151-setup-run-jsqlparser-2770-s-landed-alter |


## Cases

### L01 · Gson #3059 — numeric JsonPrimitive hash across number types (pinned source build of the `gson` module)

**Pins.** Parent `961517decce0aa907c285c19d8b93d5c746ecdcb`, fix `5e277e42786ab6441b7dd6b1a8c34d545d132307` (squash, one parent = the brief's). Worktrees `$W/L01-gson-parent`, `$W/L01-gson-fix`.
Changed production file: `gson/src/main/java/com/google/gson/JsonPrimitive.java` (`hashCode` of a numeric primitive: an integral
double value now hashes as its long). Changed test: `gson/src/test/java/com/google/gson/JsonPrimitiveTest.java` (new
`testEqualsAndHashCodeAcrossNumberTypes`).

**Build facts.** Maven, module `gson` of the root reactor, version **2.14.1-SNAPSHOT**, `maven.compiler.release` 8 (tests 11);
`gson/pom.xml` identical at both pins. Built with Maven 3.10.0 on **JDK 17.0.21** (`$J17`); classes are Java 8 bytecode (major 52).
The build runs bnd, proguard (shrinking-test jars), moditect and templating plugins as configured; none was skipped except lint/report.
Runtime dependency: `com.google.errorprone:error_prone_annotations:2.50.0` only (test: JUnit 4.13.2, Truth 1.4.5, guava-testlib 33.6.0-jre).

**Commands** (from `$W/L01-gson-ROLE/gson`; `$SK` = the lint/report skips of `$O/scripts/mvn_A.sh` (`-Drat.skip -Djapicmp.skip -Dcheckstyle.skip -Dpmd.skip -Dcpd.skip -Dspotbugs.skip -Djacoco.skip -Danimal.sniffer.skip -Dmaven.javadoc.skip -Dcyclonedx.skip -Dspdx.skip -Dmoditect.skip -Dbuildnumber.skip -Dlicense.skip -Denforcer.skip -Dforbiddenapis.skip -DforkCount=1`)), wrapped as `$O/scripts/mvn_A.sh WT gson TAG $J17 JsonPrimitiveTest [online]`:
- online (first resolution, 38 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=JsonPrimitiveTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 4–7 s on both pins)**: the same with `-o` in place of the thread setting.

**Artifacts** (`$O/artifacts/`; jars carry build timestamps, so bind the class digests):

| File | sha256 |
|---|---|
| `L01-gson-parent.jar` | `54cfe636c61ea051c395255ab5485eb26e7e9872ea59392f68883a26040ced79` |
| `L01-gson-fix.jar` | `1c38897c6e2720e38443c650d0c19ec6b389f59f9eebe2903c169b1f38f72c0e` |
| `com/google/gson/JsonPrimitive.class` (parent) | `517a13a0f3c5a8acfbd9ea0e37e40f84fbfb25edccfb6a78809cb0e6b67d4561` |
| `com/google/gson/JsonPrimitive.class` (fix) | `6f43f85d585d52f155627f20357339c383e89c4109be4fd0ead9c82fcb871c8e` |

Runtime classpath (same at both pins): `$O/artifacts/L01-gson-fix.runtime-classpath.txt`; test classpath `$O/artifacts/L01-gson-fix.test-classpath.txt`.
Use: `java -cp $O/artifacts/L01-gson-ROLE.jar:$(cat $O/artifacts/L01-gson-fix.runtime-classpath.txt) ...`.

**Landed tests** (`JsonPrimitiveTest`, upstream Maven build, JDK 17; logs `$O/logs/L01-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=31 failures=0 errors=0 skipped=0; offline tests=31 failures=0 errors=0 skipped=0 |
| parent, its own test (offline) | tests=30 failures=0 errors=0 skipped=0 |
| fix's test file on the parent (offline) | tests=31 failures=1 errors=0 skipped=0: **JsonPrimitiveTest#testEqualsAndHashCodeAcrossNumberTypes **(`JsonPrimitiveTest:310 expected:<42> but was:<1078263808>`) |

**Release side.** `gson 2.14.0`'s `JsonPrimitive.java` is the **parent's** byte for byte. `gson 2.15.0` has the **fix's logic**, its
`hashCode` rewritten as `(doubleValue == longValue) ? Long.hashCode(longValue) : Double.hashCode(doubleValue)` (the same values as the
fix's explicit shifts); otherwise the file equals the fix's. Both resolved with strict checksums: `$O/releases/gson-2.14.0/`,
`$O/releases/gson-2.15.0/` (`classpath.txt`, `lib/`, `sources/`, `tree.txt`); the only runtime dependency is error_prone_annotations
(2.48.0 and 2.50.0 respectively).

**Signatures** (keyring `$O/gnupg-A`, `.asc` from Central; key from keyserver.ubuntu.com, `$O/keys-A/`, nothing further vouching for it):

| Jar | Signer | Result |
|---|---|---|
| `gson-2.14.0.jar` | `C7BE5BCC9FEC15518CFDA882B0F3710FA64900E7` (amonn McManus) | GOODSIG |
| `gson-2.15.0.jar` | `C7BE5BCC9FEC15518CFDA882B0F3710FA64900E7` (amonn McManus) | GOODSIG |

(The signer is Éamonn McManus; the status line's non-ASCII letter is dropped above.)

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own builds. 2.14.0 stands for the parent's `JsonPrimitive` exactly; 2.15.0 for the fix's behaviour (refactored).
- The landed test checks equality and hashes only; no map history was run.

### L02 · Apache Commons Collections #701 — multiset size after removal through a view iterator (pinned source build)

**Pins.** Parent `a70ffd614602fa07d2429d76f77abcd1816d0be9`, fix `e218502f9f82237404bbce8e8ba5f81ffb467198` (squash, one parent = the brief's). Worktrees `$W/L02-commons-collections-parent`, `$W/L02-commons-collections-fix`.
Changed production file: `src/main/java/org/apache/commons/collections4/multiset/AbstractMapMultiSet.java` (`EntrySetIterator.remove` and
`UniqueSetIterator.remove` now subtract the removed key's count from `parent.size` and bump `modCount`). Changed test:
`AbstractMultiSetTest` (new `testMultiSetViewIteratorRemoveKeepsSizeConsistent`), an abstract class run through its concrete
subclasses `HashMultiSetTest`, `PredicatedMultiSetTest`, `SynchronizedMultiSetTest` and `UnmodifiableMultiSetTest`.

**Build facts.** Maven, single module, `commons-collections4` **4.6.0-SNAPSHOT**, parent `org.apache.commons:commons-parent:102`,
compiler source/target 1.8. Built with Maven 3.10.0 on **JDK 17.0.21** (`$J17`); Java 8 bytecode (major 52). `pom.xml` is the same at
both pins. Runtime classpath as Maven exports it: `commons-codec:commons-codec:1.22.0` (optional; `HashMultiSet` does not need it).

**Commands** (from the worktree root; `$SK` = the lint/report skips of `$O/scripts/mvn_A.sh`), wrapped as `$O/scripts/mvn_A.sh WT . TAG $J17 HashMultiSetTest,PredicatedMultiSetTest,SynchronizedMultiSetTest,UnmodifiableMultiSetTest [online]`:
- online (first resolution, 43 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=HashMultiSetTest,PredicatedMultiSetTest,SynchronizedMultiSetTest,UnmodifiableMultiSetTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 5–13 s on both pins)**: the same with `-o`.

**Artifacts:**

| File | sha256 |
|---|---|
| `L02-commons-collections-parent.jar` | `288135a599f3cec54d78aedab40e15d674473bc4b74f76bec5e942f682784c43` |
| `L02-commons-collections-fix.jar` | `661437079ef5f9ac7cdfba9a1c600e310285009cb60f2f9f8a2fdaac166d23ac` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$EntrySetIterator.class` (parent) | `46a839d028164abd9cd082d92e0efb054818a6937a867843c838571d117d90e0` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MapBasedMultiSetIterator.class` (parent) | `6f1a2052d7f07f1951e581fa4bb8baf373f47087a590fd0054ae38eb21c88110` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MultiSetEntry.class` (parent) | `b6e98d6c7a2fb599df77881174888e6940fd41396ebf08f142936d472f8cfc07` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MutableInteger.class` (parent) | `db25fabe6b16f0b21a11d8c3d5128eb092e6a44e15651449b2c09db44c640e9e` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$UniqueSetIterator.class` (parent) | `c8b820f3ae45e49c5654c5fa9b73a1b5a0611877eaf8e6715845fdf29d32dabf` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet.class` (parent) | `86d7bf8f3b02cb34dda8756cf03af3b7bde586088203a3284e60da26c49ba14d` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$EntrySetIterator.class` (fix) | `a51e4266f05c3364212c428761343bd34dced79bffe6a4cce99520b5b00b8aae` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MapBasedMultiSetIterator.class` (fix) | `8cca0a7585e1322be90b9a1c23a2022eeeb738d5d103241400e73e4d0175b647` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MultiSetEntry.class` (fix) | `320a545f1fac2a8fe586bba4cff14b08cbaf96cd075dc82934c4330c96289fb8` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$MutableInteger.class` (fix) | `0738efab7eef919a599b5f579dcb4c7fdb573c91d6e02eac94824c1378e20601` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet$UniqueSetIterator.class` (fix) | `98e336f02a7d927f68349e1b084ddb15fc1068f69549db434f305f4d83e368d6` |
| `org/apache/commons/collections4/multiset/AbstractMapMultiSet.class` (fix) | `4cec1f8ecacda05fd2ec2bd43a568be2406aceb14d1b8ebb6b352ee6d76d230b` |

Runtime classpath (same at both pins): `$O/artifacts/L02-commons-collections-fix.runtime-classpath.txt`; test classpath
`$O/artifacts/L02-commons-collections-fix.test-classpath.txt`.

**Landed tests** (the four concrete multiset test classes, JDK 17; logs `$O/logs/L02-*`):

| Run | Result |
|---|---|
| fix, its own tests (online, then offline) | tests=214 failures=0 errors=0 skipped=0; offline tests=214 failures=0 errors=0 skipped=0 |
| parent, its own tests (offline) | tests=210 failures=0 errors=0 skipped=0 |
| fix's `AbstractMultiSetTest` on the parent (offline) | tests=214 failures=3 errors=0 skipped=0: **HashMultiSetTest#testMultiSetViewIteratorRemoveKeepsSizeConsistent PredicatedMultiSetTest#testMultiSetViewIteratorRemoveKeepsSizeConsistent SynchronizedMultiSetTest#testMultiSetViewIteratorRemoveKeepsSizeConsistent **(each `AssertionFailedError: expected: <2> but was: <5>` at `AbstractMultiSetTest.java:587`). The unmodifiable subclass's copy does not fail (removal is unsupported there). |

**Release side.** No release equals either side's `AbstractMapMultiSet.java` byte for byte. `commons-collections4 4.5.0` has the
**parent's iterator code** (it differs from the parent only in comments and in `readObject`, where the parent added a check for a count below 1).
`4.6.0` **contains the fix** plus later changes to the same class: the total size became a `long` and `size()` saturates at
`Integer.MAX_VALUE`, `add` clamps a count at `Integer.MAX_VALUE`, and there is a new constructor taking an iterable. Both resolved:
`$O/releases/commons-collections4-4.5.0/`, `$O/releases/commons-collections4-4.6.0/` (no runtime dependencies).

**Signatures** (keyring `$O/gnupg-A`; keys from `https://downloads.apache.org/commons/KEYS`, saved `$O/dl/A-keys/commons-KEYS`, sha256
`f154a693df7d01290487b3bf4c045481cdde6bd310b9eeb37b7a533b03b3299a`):

| Jar | Signer | Result |
|---|---|---|
| `commons-collections4-4.5.0.jar` | `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory (Code signing key)) | GOODSIG |
| `commons-collections4-4.6.0.jar` | `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` (Gary Gregory) | GOODSIG |

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The jars are the pins' own builds. 4.5.0 ≈ parent for the iterator paths; 4.6.0 has the fix but a different size field.
- The landed test removes one key through each view; the brief's reinsertion history was not run.

### L03 · picocli #1529 — alias changes of a registered subcommand (upstream Gradle 7.3.3 build at both pins, inline)

**Pins.** Parent `4090e3dd30f9a046a72a1450972848d55e656160`, fix `edd902c0348d3548afac12096b0b16ab69f52a79`. The fix is a rebase of three commits on `master`
(implementation `db2da0543e774c3406b32770c260918cfbc10e6b` → rename `e5ee68b51e4ccab2d8b6d624859c1458dad88b23` → test = the fix pin;
`/home/filip/.cache/in-the-loop/merged-pr-links-l01-l20/logs/L03-landed-chain.txt`). Worktrees `$W/L03-picocli-parent`, `$W/L03-picocli-fix`. Changed production file:
`src/main/java/picocli/CommandLine.java` (+26/−3); new test `src/test/java/picocli/Issue1528.java` (one method, `testSubCommandAliasModification`).

**Build facts.** Gradle 7.3.3 (`$O/tools/gradle-7.3.3`, zip checked, see `/home/filip/.cache/in-the-loop/merged-pr-links-l01-l20/notes/C-tools.md`). The repository's `gradle-wrapper.jar`
`33ad4583fd7ee156f533778736fa1b4940bd83b433934d1cc4e9f608e99a6a89` (both pins) equals services.gradle.org's published wrapper jar for 7.3.3
(`$O/dl/gradle-C/gradle-7.3.3-wrapper.jar.sha256`). Built on **JDK 11** (`$J11`): the build picks `sourceCompatibility` 1.7 on JDK 11+
(1.5/1.6 on older JDKs), and Gradle 7.3.3 runs on at most JDK 17. Version `4.6.3-SNAPSHOT`; the jar is multi-release (`module-info` under
`META-INF/versions/9`). **No runtime dependencies.** Tests: JUnit 4.12. Repositories `repo.spring.io/libs-snapshot`, Central and the
Plugin Portal; nothing was missing. The `docs/*.html` files of both worktrees show as modified right after checkout (the repository's
`* text=auto` meets CRLF files in the commit); that is git's line-ending normalization, not the build.

Commands (online once, 38 s; offline 6–10 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/env.sh
$O/scripts/gradle_case_C.sh L03-picocli-fix 7.3.3 $J11 L03-picocli-fix.test-offline build/test-results/test \
  --offline :jar :test --tests picocli.Issue1528      # or L03-picocli-parent; first run without --offline
```

(`gradle_case_C.sh WT VERSION JDK TAG RESULTDIR ARGS...` runs `$O/tools/gradle-VERSION/bin/gradle --no-daemon --console=plain --max-workers=2
-Dorg.gradle.jvmargs=-Xmx1536m -Porg.gradle.java.installations.auto-download=false ARGS` in `$W/WT` under `choom -n 500`, logs to
`$O/logs/TAG.log` and the JUnit summary to `$O/logs/TAG.junit.txt`.)

**Artifacts** (built offline from each pin; Gradle keeps file timestamps, so bind the class digests):

| File | sha256 |
|---|---|
| `$O/artifacts/L03-picocli-parent.jar` | `16a09da038dd65c013aa1cebbc353a8b4f0b4fb6255540b84266901a371d02f9` |
| `$O/artifacts/L03-picocli-fix.jar` | `f466d3446a58ad67983ee1527e8bcd7687ffe4ea07abfbb64a41eef6ab33a9ea` |

| Class | parent | fix |
|---|---|---|
| `picocli/CommandLine.class` | `c09566dddedc7114dd2f9c67ea90f7ffded51e9accbdd7c76ea6642b94593503` | `bb5c98d4aabf3c0f127f7f93db4b7681f16bf002a41c002e0cc629808cc92a86` |
| `picocli/CommandLine$Model$CommandSpec.class` | `634579842ad7e988448fe5135ea6945f04f5c8071f70a59ff1ca55c1b84081f8` | `04f0f8f69f99427c61eb021c9ece99427ec05ed6c7c88ecc5144a2c6902f3621` |

All 225 classes of the jar differ between the sides, because every nested class of `CommandLine.java` carries the shifted line numbers;
the full table is `$O/logs/L03-classdiff.md`. The change itself: `CommandSpec.aliases(String...)` now, when the spec has a parent, adds the new aliases to and removes the dropped ones from the parent's `commands` map through two new `CommandSpec` methods, `addAlias` and `removeAlias` (the latter removes the map key whatever command it maps to).

**Runtime classpath.** The jar alone.

**Landed test** (JDK 11.0.33; logs `$O/logs/L03-picocli-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `Issue1528` (online, then offline) | tests=1 failures=0 errors=0 skipped=0; offline: tests=1 failures=0 errors=0 skipped=0 |
| parent | no `Issue1528` at the parent (the test is new) |
| fix's `Issue1528.java` copied onto the parent (offline, removed after) | **tests=1 failures=1 errors=0 skipped=0**: `testSubCommandAliasModification`, `java.lang.AssertionError` at `Issue1528.java:42` (`assertEquals(0, cl.execute("alias1"))` after `cs.aliases("alias1")`: the parent does not dispatch the new alias) |

**Release side** (`$O/releases/picocli-4.6.2`, `$O/releases/picocli-4.6.3`, resolved with strict checksums; sources compared with CRs stripped,
because the sources jars have CRLF line ends):
- **4.6.3 carries the fix**: all 26 lines the fix adds to `CommandLine.java` are in it and none of the 3 it removes; it also has later,
  unrelated changes (version string, `initFromAnnotatedMembers`, subcommand hierarchy handling; 32 differing lines against the fix).
  `picocli-4.6.3.jar` `b0a5159e926de8084ff066025142270443533656bc599b8bb31d14d11fd138a4`.
- **4.6.2 predates the parent** (318 differing lines against it) and has the 3 removed lines. `picocli-4.6.2.jar` `4754d96eaf5314f35a287da5c67848b285067868fca6d1f5121a74f67f065b61`.
- No release equals either pin.

**Signatures.** `picocli` 4.6.2 and 4.6.3, jar and `-sources.jar`: good, key `AA417737BD805456DB3CBDDE6601E5C08DCCBB96` (Popma Remko), from
keyserver.ubuntu.com with nothing further vouching for it (keyring `$O/gnupg-C`, log `$O/logs/sigs-C.txt`).

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- Use `$O/artifacts/L03-picocli-{parent,fix}.jar` alone on the classpath; the bytecode is Java 7 (built on JDK 11) and runs on any later JDK.
- 4.6.3 has the fix plus later changes; there is no release of the parent.
- The landed test checks distinct aliases only; the brief's primary-name challenge was not run.

### L04 · java-diff-utils #233 — equal deltas rendered as EQUAL rows (pinned source build of the `java-diff-utils` module)

**Pins.** Parent `eb188a96eacff8e80877714d42fa9e2fd4fec32a`, fix `6e0ec1e22d31013eedda0ca8a72d3d77d1abf98b` (two-parent merge; first parent = the brief's, second `d072d124b6db71d0c482f652c94eeeb3cc2fc8b4`). Worktrees `$W/L04-java-diff-utils-parent`,
`$W/L04-java-diff-utils-fix`. Changed production file: `java-diff-utils/src/main/java/com/github/difflib/text/DiffRowGenerator.java`
(6 added lines: an `EQUAL` delta becomes an equal row). Changed test: `DiffRowGeneratorEqualitiesTest` (two new tests).

**Build facts.** Maven, module `java-diff-utils` of the root reactor (`java-diff-utils-parent` **4.18-SNAPSHOT**), compiler
source/target 1.8. Built with Maven 3.10.0 on **JDK 17.0.21**; Java 8 bytecode (major 52). **No runtime dependencies** (the runtime
classpath file is empty); tests use JUnit Jupiter and AssertJ.

**Commands** (from `$W/L04-java-diff-utils-ROLE/java-diff-utils`), wrapped as `$O/scripts/mvn_A.sh WT java-diff-utils TAG $J17 DiffRowGeneratorEqualitiesTest [online]`:
- online (21 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=DiffRowGeneratorEqualitiesTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 6 s on both pins)**: the same with `-o`.

**Artifacts:**

| File | sha256 |
|---|---|
| `L04-java-diff-utils-parent.jar` | `8974ec624e4c9cf82eb33c4eb2371069717d9d0be2d39a9e96e6ec8a69114ae7` |
| `L04-java-diff-utils-fix.jar` | `885f632fe17b9cf632519bc7dda78bd79ebff6c46b77189373aecb91ec96ded8` |
| `com/github/difflib/text/DiffRowGenerator$1.class` (parent) | `d48358c50fc51b242583a5f2c5f87a6380e2079fe37fea98f13f36327e2e8c94` |
| `com/github/difflib/text/DiffRowGenerator$Builder.class` (parent) | `4a0e7511b10e6036be4e5e57c2cf7d931521cfe0f5c7468ab6881847807f98eb` |
| `com/github/difflib/text/DiffRowGenerator.class` (parent) | `e542f991aae0e92ef11122f3fc491473121cb8ba9b31c57bcc0c325574fd8264` |
| `com/github/difflib/text/DiffRowGenerator$1.class` (fix) | `c2c0cd1d3c8c55288399406a19b77421216943fca90072f1d9267e8e4c64f05f` |
| `com/github/difflib/text/DiffRowGenerator$Builder.class` (fix) | `0ad27d82846ab96082e2f8e7687a03935c96aacde0827bdb46eb8d09cc17795c` |
| `com/github/difflib/text/DiffRowGenerator.class` (fix) | `cb3f90867c94dcfb175df15aaa6c46fd20bbbd084279dc735d4215a27b7bd41a` |

Test classpath: `$O/artifacts/L04-java-diff-utils-fix.test-classpath.txt`. Use: `java -cp $O/artifacts/L04-java-diff-utils-ROLE.jar ...`.

**Landed tests** (`DiffRowGeneratorEqualitiesTest`, JDK 17):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=6 failures=0 errors=0 skipped=0; offline tests=6 failures=0 errors=0 skipped=0 |
| parent, its own test (offline) | tests=4 failures=0 errors=0 skipped=0 |
| fix's test file on the parent (offline) | tests=6 failures=2 errors=0 skipped=0: **DiffRowGeneratorEqualitiesTest#testEqualDeltaIsReportedAsEqualWithoutInlineDiffs DiffRowGeneratorEqualitiesTest#testEqualDeltaIsReportedAsEqualWithInlineDiffs **(`expected: <EQUAL> but was: <CHANGE>`, lines 105 and 120) |

**Release side.** `java-diff-utils 4.17`'s `DiffRowGenerator.java` is the **parent's**; `4.18`'s is the **fix's**, byte for byte. Of the
32 Java files in each sources jar, 4.17 differs from the parent pin in one other file (`com/github/difflib/patch/Chunk.java`) and 4.18 from
the fix pin in four (`Patch.java`, `UnifiedDiffReader.java`, `UnifiedDiffWriter.java`, `UnifiedDiffUtils.java`), none of them the renderer.
Resolved: `$O/releases/java-diff-utils-4.17/`, `$O/releases/java-diff-utils-4.18/` (no runtime dependencies).

**Signatures** (keyring `$O/gnupg-A`): good with the key in the repository's own `KEYS` file at the fix pin (saved
`$O/dl/A-keys/java-diff-utils-KEYS`, sha256 `68276e7a41a3f0d55039b57774f108ecd9175545afac98aca0d82ea206bc06df`), whose self-signature runs to 2028.
The copy on keyserver.ubuntu.com (`$O/keys-A/A6EA2E2BF22E0543.asc`) carries an older expiry (2022-11-01), under which GnuPG reports
`EXPKEYSIG` for the same signatures (made 2026-05-16 and 2026-10-18).

| Jar | Signer | Result |
|---|---|---|
| `java-diff-utils-4.17.jar` | `D477D51812E692011DB11E66A6EA2E2BF22E0543` (Tobias Warneke (for development purposes)) | GOODSIG |
| `java-diff-utils-4.18.jar` | `D477D51812E692011DB11E66A6EA2E2BF22E0543` (Tobias Warneke (for development purposes)) | GOODSIG |

**Jobs.** None.

**For the domain agent**
- 4.17 = parent and 4.18 = fix for the renderer; the built jars are the pins' own.
- The landed tests use the patch overload with explicit equal parts; the brief's implicit-equal control and `EQ-` processor history were not run.

### L05 · JUnit Jupiter #6104 — same-named nested classes inherited from a superclass (upstream Gradle 9.8.0 build at both pins; jars and landed tests by jobs)

**Pins.** Parent `bbeb7900fa76b6fc00e36e0bea05747066b4a2ec`, fix `2b484caa962ad9b0d9a6af5d2c25100b6a8f4ef6` (squash on `main`, one parent = the brief's).
Changed production files (all in `junit-jupiter-engine`): `discovery/ClassSelectorResolver.java` (+29/−15), `descriptor/NestedClassTestDescriptor.java`
(+2/−1), `descriptor/ClassTemplateTestDescriptor.java` (+2/−1). Tests (`jupiter-tests/src/test/java/org/junit/jupiter/engine/`):
`NestedTestClassesTests.java` (+92/−10), `ClassTemplateInvocationTests.java` (+57/−12), and the test fixture
`junit-jupiter-engine/src/testFixtures/java/org/junit/jupiter/engine/discovery/JupiterUniqueIdBuilder.java` (+2/−2). Also the 6.2.0-M1 release notes.

**Checkouts.** `$W/L05-junit-framework-parent` and `$W/L05-junit-framework-fix` are **standalone depth-1 clones** of the mirror (fetched from
`refs/pins/ROLE-SHA`), not linked worktrees, as for the earlier setup's M19: JUnit's build reads git metadata, which failed in a linked
worktree of the shallow bare mirror then. Trees: parent `cdd5ae4e0e541af01c504a9a5f6162914d0f205b`, fix `6165c70ffefa6eaaf77ef764f9d0d61f5427ae1e`,
as in the revisions table.

**Build facts.** Gradle 9.8.0 (`$O/tools/gradle-9.8.0`; zip sha256 = services.gradle.org's = the wrapper's `distributionSha256Sum`, see
`/home/filip/.cache/in-the-loop/merged-pr-links-l01-l20/notes/C-tools.md`). The repository's `gradle-wrapper.jar` `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d` (both pins)
equals services.gradle.org's published wrapper jar for 9.7.x (`$O/dl/gradle-C/gradle-9.7.1-wrapper.jar.sha256`); it is not used.
Version `6.2.0-SNAPSHOT` (`gradle.properties`), API baseline 6.1.3. The build's Java toolchain defaults to **25**
(`junitbuild.java-toolchain-conventions`), and `org.gradle.java.installations.fromEnv=JDK17,JDK21,JDK24,JDK25`.
`$O/scripts/L05-gradle.sh` runs it all: Gradle on JDK 25.0.5 (`$J25`) with `JDK17=$J17 JDK21=$J21 JDK25=$J25` and `JDK24` = the earlier setup's
checked Temurin 24.0.2 (`~/.cache/in-the-loop/merged-pr-links/tools/jdk-24.0.2+12`), `--no-daemon --console=plain --max-workers=2`,
**`--no-build-cache`** and **`--no-scan`**, `-Dorg.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=768m`,
`-Pkotlin.compiler.execution.strategy=in-process`, toolchain auto-download and auto-detection off with
`org.gradle.java.installations.paths=$J17,$J21,JDK24,$J25`, under `choom -n 500`. The tests' job adds `-Ptesting.retries=0` and
`-Pjunit.develocity.predictiveTestSelection.enabled=false` (predictive test selection defaults to on in the build parameters).
Repositories: Central and the Plugin Portal; nothing was missing and no substitution was needed.

Commands (inline: fix jars online, 4m18s; the dependency report offline, 28 s; everything else is the job's):

```bash
cd ~/.cache/in-the-loop/merged-pr-links-l01-l20/worktrees/L05-junit-framework-fix     # or -parent
~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/L05-gradle.sh --offline -Ptesting.retries=0 -Pjunit.develocity.predictiveTestSelection.enabled=false \
  :junit-jupiter-api:jar :junit-jupiter-engine:jar :junit-platform-commons:jar :junit-platform-engine:jar :junit-platform-launcher:jar \
  :jupiter-tests:test --tests org.junit.jupiter.engine.NestedTestClassesTests --tests org.junit.jupiter.engine.ClassTemplateInvocationTests
python3 -I ~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/junit_summary.py jupiter-tests/build/test-results/test
```

<!-- L05-art -->
**Artifacts.** Built by job `20261125-162622-setup-build-junit-6104-at-both-revisions` (passed) at both pins with the command above, copied to `$O/artifacts/` (the fix's replace the inline copies):

| `$O/artifacts/` file | sha256 |
|---|---|
| `L05-junit-framework-fix-junit-jupiter-api.jar` | `e192b4b1ec18760214b0a682b5893acb7549d86c191e5059d98d97e868a71e14` |
| `L05-junit-framework-fix-junit-jupiter-engine.jar` | `09b41b43a126f35e148b9c94b9db541235ecfaeac05dce548b344d84477a4761` |
| `L05-junit-framework-fix-junit-platform-commons.jar` | `a263eba7f9bd390454153024a22365b59f9bc8cd2e741148cbc9bbaaa3af77bd` |
| `L05-junit-framework-fix-junit-platform-engine.jar` | `d2ca8e2d38b691d7db449c61232d1c192415d5cb21ea3ca0379f9e402103c52d` |
| `L05-junit-framework-fix-junit-platform-launcher.jar` | `4ba3bd79072329d1b31e99d804b24f8fce836771cd7711ceaf20dbd80a1ecbd5` |
| `L05-junit-framework-parent-junit-jupiter-api.jar` | `f67bcbc098bd74ebd70f81ebf0e668c7aa0ec410e6bda49a3570a0082640f531` |
| `L05-junit-framework-parent-junit-jupiter-engine.jar` | `f3db9a9643296ec5a799c393a0bf0670b2648a6ac5214a45e58c19d372202362` |
| `L05-junit-framework-parent-junit-platform-commons.jar` | `dbfd0588dfcac0d8820407ff2cf2f91f59d985038a4054c4ea02dbf086459f53` |
| `L05-junit-framework-parent-junit-platform-engine.jar` | `f2d2161964e55fbcde6760aefa06e9011f4d46d59fb8e131e8c9824d0d7539d8` |
| `L05-junit-framework-parent-junit-platform-launcher.jar` | `0ac7c2939aa773ac1046fdf853f27476d616f862984d83ab795c51f292446640` |

Classes whose digests differ between the parent and fix jars (`$O/logs/L05-classdiff-*.md`): only `junit-jupiter-engine` has any; `junit-platform-launcher` and `junit-jupiter-api` are class-identical across the pins.

| Class | parent | fix |
|---|---|---|
| `org/junit/jupiter/engine/descriptor/ClassTemplateTestDescriptor$ClassTemplateExecutor.class` | `55e9c7b7ffb032139611a73da4830bda7d156dec7ed09a525d68e4fce107c249` | `8632569c63d2b1af9567a48b893a4d7c67d64a463cf60ae474a7e0a50e6665e6` |
| `org/junit/jupiter/engine/descriptor/ClassTemplateTestDescriptor.class` | `e54eb1c175ff35fd49a8dffe059cbae2c1ca630933313dbaa115663e2adbc4a7` | `4e6f8737782a4f6f81a92cf15578bad2dfc657102a03c03f6c0e581e60301a75` |
| `org/junit/jupiter/engine/descriptor/NestedClassTestDescriptor.class` | `db600175c4e97bd50e693595afd1e7a98a86919e0536f8441ce82583e9f4b1fc` | `2046517664586ee8b524ed409cc5b042cd5809f5a6a675333a295cb31b075e90` |
| `org/junit/jupiter/engine/discovery/ClassSelectorResolver$DummyClassTemplateInvocationContext.class` | `84aa265146b89300cd9eb75dd17af2e402cc0671c05d085b56e4b844586fef3d` | `cdfd9b7590e96f1eb1039a16c85fdde1f3c2ef5b3f8758f1bab19ab649bd3cbc` |
| `org/junit/jupiter/engine/discovery/ClassSelectorResolver.class` | `9e3ba7e79a3dc5e658691877ceacf4196a34ffa43429cb21663c3fdfd3d1861a` | `86c311162dadd5689ce841e656c8c5ad71cefe89c0b538801bdf52eb2ac526f5` |
<!-- 169 classes parent, 169 fix -->

External runtime dependency of the engine and launcher: `org.opentest4j:opentest4j:1.3.0` only (`$O/logs/L05-junit-framework-fix.deps.log`); `apiguardian-api` 1.1.2 and `jspecify` 1.0.1 are not on the pins' `runtimeClasspath`, but the release POMs declare them, so they are in the release sets.
<!-- /L05-art -->

<!-- L05-jobs -->
**Landed tests** (`NestedTestClassesTests` + `ClassTemplateInvocationTests` in `jupiter-tests`; logs `$O/logs/L05-*.gradle-log.txt`, summaries `$O/logs/L05-*.junit.txt`):

| Run | Result |
|---|---|
| fix, online (job `20261125-162622-setup-build-junit-6104-at-both-revisions`) | 56 run, 0 failures, 0 errors, 0 skipped |
| fix, offline (same job) | 56 run, 0 failures, 0 errors, 0 skipped |
| parent, its own copies, offline (same job) | 53 run, 0 failures, 0 errors, 0 skipped |
| the fix's two test classes and `JupiterUniqueIdBuilder` on the parent, offline (same job) | does not compile: `JupiterUniqueIdBuilder.java:40` cannot find symbol; `JupiterUniqueIdBuilder.java:41` cannot find symbol (the fixture uses the fix's renamed constants) |
| the fix's two test classes on the parent with constant names mapped, parent's `JupiterUniqueIdBuilder`, offline (job `20261125-170100-setup-run-junit-6104-s-landed-nested-cla`) | 56 run, 3 failures, 0 errors, 0 skipped; failing: `ClassTemplateInvocationTests#nestedClassTemplateIsInherited()`, `NestedTestClassesTests#nestedTestClassesWithSameNameAreCorrectlyDiscoveredAndExecuted()`, `NestedTestClassesTests#deeplyNestedInheritedMethodsAreExecutedWhenSelectedViaUniqueId()` |

The fix renames `NestedClassTestDescriptor.SEGMENT_TYPE` to `SIMPLE_NAME_SEGMENT_TYPE` and `ClassTemplateTestDescriptor.NESTED_CLASS_SEGMENT_TYPE` to `SIMPLE_NESTED_CLASS_SEGMENT_TYPE` (same values) and adds `FULLY_QUALIFIED_NAME_SEGMENT_TYPE = "fq-nested-class"` and `FULLY_QUALIFIED_NESTED_CLASS_SEGMENT_TYPE = "fq-nested-class-template"`. The second job's copies map those four references (to the parent's names, or to the same string literals) and change nothing else; the mapped files and their diffs against the fix's are in `$O/artifacts/L05-transplant-mapped/` (sha256 `ClassTemplateInvocationTests.java` `6498be950aeed8e885b9e58cf77c43e66eee01b0c5dd52263e91423f85255f8c`, `NestedTestClassesTests.java` `6d48cc63ff76ad23baa63ca746421aa65e0de510ceeed972064fb1c3198469e4`).
<!-- /L05-jobs -->

**Release side** (`$O/releases/junit-6.2.0-M1`, `$O/releases/junit-6.1.3`: engine and launcher with their runtime graphs, strict checksums). Central has
6.2.0-M1 (the release notes the fix edits are 6.2.0-M1's) and 6.1.3 as the newest 6.1.x. Changed files compared byte for byte with each sources jar:

| Sources jar | File | Equals |
|---|---|---|
| `junit-jupiter-engine-6.2.0-M1-sources.jar` | `org/junit/jupiter/engine/discovery/ClassSelectorResolver.java` | fix |
| `junit-jupiter-engine-6.2.0-M1-sources.jar` | `org/junit/jupiter/engine/descriptor/NestedClassTestDescriptor.java` | fix |
| `junit-jupiter-engine-6.2.0-M1-sources.jar` | `org/junit/jupiter/engine/descriptor/ClassTemplateTestDescriptor.java` | fix |
| `junit-jupiter-engine-6.1.3-sources.jar` | `org/junit/jupiter/engine/discovery/ClassSelectorResolver.java` | parent |
| `junit-jupiter-engine-6.1.3-sources.jar` | `org/junit/jupiter/engine/descriptor/NestedClassTestDescriptor.java` | neither |
| `junit-jupiter-engine-6.1.3-sources.jar` | `org/junit/jupiter/engine/descriptor/ClassTemplateTestDescriptor.java` | parent |

- **6.2.0-M1 carries the fix's three changed files.** Its other files were not compared, so it is "the fix plus whatever else 6.2.0-M1 has".
- **6.1.3 is not the parent**: `ClassSelectorResolver` and `ClassTemplateTestDescriptor` equal the parent's, but its `NestedClassTestDescriptor`
  differs from the parent's in one call (`instantiateTestClass(Optional.of(outerInstances), ...)` in 6.1.3, `instantiateTestClass(outerInstances, ...)`
  at the parent, a later refactor on `main`). For discovery of inherited nested classes it has the parent's resolver.
- Per tree, the launcher, Jupiter API and engine must come from the same build: the pin jars from `$O/artifacts`, or one release set whole.

| Release | Jar | sha256 |
|---|---|---|
| 6.2.0-M1 | `apiguardian-api-1.1.2.jar` | `b509448ac506d607319f182537f0b35d71007582ec741832a1f111e5b5b70b38` |
| 6.2.0-M1 | `jspecify-1.0.1.jar` | `070d75f261fe4c5b8202508366715f7f2d4660f88c8ef7e6d3575e48c9683b66` |
| 6.2.0-M1 | `junit-jupiter-api-6.2.0-M1.jar` | `5de5231e4882c1840ef0dcb17870db521593aa5fc0002856d5a0c899f4082209` |
| 6.2.0-M1 | `junit-jupiter-engine-6.2.0-M1.jar` | `bde6539525d03a080bc6c8580d7c417f84db5300be238bea54a7b4e002e10f9c` |
| 6.2.0-M1 | `junit-platform-commons-6.2.0-M1.jar` | `c6ecc0509f0159613e0b6768f3535bfcc3ae01a384384a0e2283601762585900` |
| 6.2.0-M1 | `junit-platform-engine-6.2.0-M1.jar` | `8c0fd8eb16d640597714ca8c82b80f108eef239f81e49b2ee1a54ac73189cf4c` |
| 6.2.0-M1 | `junit-platform-launcher-6.2.0-M1.jar` | `b1e03bf5946410a081b985d71c297e3652e36e0e75f455e866e69c6d11590c51` |
| 6.2.0-M1 | `opentest4j-1.3.0.jar` | `48e2df636cab6563ced64dcdff8abb2355627cb236ef0bf37598682ddf742f1b` |
| 6.1.3 | `apiguardian-api-1.1.2.jar` | `b509448ac506d607319f182537f0b35d71007582ec741832a1f111e5b5b70b38` |
| 6.1.3 | `jspecify-1.0.0.jar` | `1fad6e6be7557781e4d33729d49ae1cdc8fdda6fe477bb0cc68ce351eafdfbab` |
| 6.1.3 | `junit-jupiter-api-6.1.3.jar` | `555d6cf20fa1710884dd01b86cc5785397ba73e21ada2d4b784f5f1a14dcafc4` |
| 6.1.3 | `junit-jupiter-engine-6.1.3.jar` | `414559e78bbfa3bdb2eab009ac3ab1e22369ac31117c270a0bd666da115c5c6c` |
| 6.1.3 | `junit-platform-commons-6.1.3.jar` | `a4774ae923c109544034aeae7c762cf017fbcdd1342403ba90e0921984b608c3` |
| 6.1.3 | `junit-platform-engine-6.1.3.jar` | `21ad7ad3a35beda16387979317be1833a72a71d812f9a66ee4b9a7bafb56334c` |
| 6.1.3 | `junit-platform-launcher-6.1.3.jar` | `1dec64b1fc0b7c47a11302aa5b4d37d8160c041b396e27067709ce775601a7b6` |
| 6.1.3 | `opentest4j-1.3.0.jar` | `48e2df636cab6563ced64dcdff8abb2355627cb236ef0bf37598682ddf742f1b` |

**Signatures.** JUnit 6.2.0-M1 (`junit-jupiter-engine`, `-api`, `junit-platform-launcher`, `-engine`, `-commons`) and 6.1.3 (`junit-jupiter-engine`,
`junit-platform-launcher`), jar and `-sources.jar`, and `opentest4j-1.3.0`: good, key `FF6E2C001948C5F2F38B0CC385911F425EC61B51` (Marc Philipp),
from keyserver.ubuntu.com via the earlier setup's saved copy, nothing further vouching for it (`$O/logs/sigs-C.txt`). `apiguardian-api` and `jspecify`
rest on strict checksums.

**Jobs.** `20261125-162622-setup-build-junit-6104-at-both-revisions` (fork C, `$O/scripts/submit_C.py`): passed; built both sides and ran the tests above. `20261125-170100-setup-run-junit-6104-s-landed-nested-cla` (`$O/scripts/submit_L05b.py`): the mapped transplant (done).

**For the domain agent**
- Both sides' jars are in `$O/artifacts` (table above); 6.2.0-M1 stands for the fix side by its changed files. There is no
  release of the parent; 6.1.3 shares the parent's resolver but differs in `NestedClassTestDescriptor`.
- Build any JUnit tree only through `$O/scripts/L05-gradle.sh` (no build cache, no scan, retries 0, predictive test selection off).
- The brief's launcher scenarios (unique-ID reselection) were not run.

### L06 · Apache Arrow Java #1019 — list-view end index and hash interval (pinned source build of vector with -am; release 19.0.0 carries the fix's file)

**Pins.** Parent `46211fccf642d6dcfcebc31081817da1529d6a35`, fix `9fd4973d12abbd9e9d14098c2acd41d97a6c4407`. Worktrees `$W/L06-arrow-java-parent`, `$W/L06-arrow-java-fix`. Squash commit with one parent = the brief's.
Changed production file: `vector/src/main/java/org/apache/arrow/vector/complex/ListViewVector.java` (only). Changed test: `vector/src/test/java/org/apache/arrow/vector/TestListViewVector.java`.
`pom.xml`, `vector/pom.xml` and `memory/` are identical at both pins.

**Build facts.** Maven, root `arrow-java-root` **19.0.0-SNAPSHOT** (parent `org.apache:apache:35`), `maven.compiler.release` 11. The vector module needs, in the reactor,
`arrow-format`, `arrow-memory-core`, `arrow-memory-unsafe`, `arrow-memory-netty`, `arrow-memory-netty-buffer-patch` (the two allocators are test-scope
dependencies of `arrow-vector`; at runtime **one allocator module must be on the classpath**: `arrow-memory-unsafe`, or `arrow-memory-netty` with
`arrow-memory-netty-buffer-patch`, `netty-buffer` and `netty-common` 4.2.9.Final). Runtime dependencies: jackson 2.21.0 (core, annotations, databind,
jsr310), commons-codec 1.20.0, flatbuffers-java 25.2.10, slf4j-api 2.0.17. Tests run with `--add-opens=java.base/java.nio=org.apache.arrow.memory.core,ALL-UNNAMED`
(the root POM's `surefire.add-opens.argLine`); a plain-classpath JVM on 17+ needs `--add-opens=java.base/java.nio=ALL-UNNAMED`.
Built on **JDK 17.0.21** (`$J17`; CI uses 11, 17, 21, 23) with **Maven 3.9.9** (`$O/tools/apache-maven-3.9.9`, CI's version):
- **Maven 3.10.0 fails** at once: the project's `.mvn/extensions.xml` loads `com.gradle:develocity-maven-extension:2.3.4`, which throws a Guice
  `NullInjectedIntoNonNullable` in `afterProjectsRead` under 3.10.0. Maven 3.9.9: `apache-maven-3.9.9-bin.tar.gz` sha512 = Maven Central's `.sha512`,
  sha256 `7a9cdf674fc1703d6382f5f330b3d110ea1b512b51f1652846d9e4e8a588d766`; signature good, key `88BE34F94BDB2B5357044E2E3A387D43964143E3` (Tamas Cservenak) from
  `https://downloads.apache.org/maven/KEYS` (saved `$O/dl/maven-3.9.9/maven-KEYS`, sha256 `1e53a10e6b65c64ae0f5a241c8ef289c7578f1109d8a78512dff7de2b29117b3`).
- `-Ddevelocity.scan.disabled=true` (no build scan; the project's `develocity.xml` publishes only when authenticated anyway) and
  `-Dmaven.gitcommitid.skip=true` (git-commit-id-plugin fails in the shallow linked worktree: "Missing unknown <sha>").

**Commands** (`$O/scripts/arrow_B.sh WT TAG [online]`, from the worktree root):
- online (first resolution, 96 s): `JAVA_HOME=$J17 MAVEN_OPTS=-Xmx1g $O/tools/apache-maven-3.9.9/bin/mvn -B -s $O/maven-settings.xml -t $O/toolchains.xml -Daether.connector.basic.threads=1 -Dmaven.gitcommitid.skip=true -Ddevelocity.scan.disabled=true -Drat.skip -Dcheckstyle.skip -Dspotless.check.skip=true -Dspotless.apply.skip=true -Dmaven.javadoc.skip -Dcyclonedx.skip -Denforcer.skip -Danimal.sniffer.skip -Djacoco.skip -Dmaven.source.skip -DforkCount=1 -pl vector -am -Dtest=TestListViewVector -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false package`
- **offline (checked; 55 s from a clean tree on the parent, 7–11 s incremental)**: the same with `-o` in place of the thread setting.
The vector module runs its tests twice (surefire executions `default-test`, with `arrow-memory-unsafe` excluded, and `run-unsafe`, with netty excluded and
report suffix `netty`), so each count below is twice the class's test methods.

**Artifacts** (`$O/artifacts/L06-arrow-java-ROLE/`: the six reactor jars of each side; jars carry build timestamps, so bind the class digests).
`arrow-format`, `arrow-memory-core` and `arrow-memory-unsafe` are class-identical between the sides; the netty jars are byte-identical.

| File or class | Side | sha256 |
|---|---|---|
| `arrow-vector-19.0.0-SNAPSHOT.jar` | parent | `6582cc8ec100a8d3291b8afa8a39932cfef40b7e95fc4d795a105094882fc084` |
| `org/apache/arrow/vector/complex/ListViewVector$TransferImpl.class` | parent | `80f8e2ff25ede223c264fbe652b41c489f095f5e930d9927d929d517e50f427c` |
| `org/apache/arrow/vector/complex/ListViewVector.class` | parent | `d6b2ad6b7347bea1ab2173a5b090189e1366eb8aef21ab5215de9acd24e7d4f6` |
| `arrow-format-19.0.0-SNAPSHOT.jar` | parent | `9d8991d46d9922fe27f1b1000d280783762283be779a802249121db0bad01b00` |
| `arrow-memory-core-19.0.0-SNAPSHOT.jar` | parent | `9f3ec68c274c30881f2acac66d28220f99f518ff24bb6c7f52b3113a3e6798a4` |
| `arrow-memory-unsafe-19.0.0-SNAPSHOT.jar` | parent | `3c30df8e5096e76a703e7458906a4b9e222cc6df494e3e7fd48fdb8d52a8c828` |
| `arrow-memory-netty-19.0.0-SNAPSHOT.jar` | parent | `89c6eb75e766f0a0d0a56239f688c0622215f1fda0ce224dc4058ea93f4dab5c` |
| `arrow-memory-netty-buffer-patch-19.0.0-SNAPSHOT.jar` | parent | `2e81ab1475529395798dce01188f0efc959d4baac51808022da09330ee42c4d2` |
| `arrow-vector-19.0.0-SNAPSHOT.jar` | fix | `cf63d3fb34bbbd0039dc0808b4dae66066797e3c4a959367b9b4d8334676e97c` |
| `org/apache/arrow/vector/complex/ListViewVector$TransferImpl.class` | fix | `f5f25f6155b284f31399ffe68cd655ea3693c1ec76f34fcdaabfc3a2a80883c3` |
| `org/apache/arrow/vector/complex/ListViewVector.class` | fix | `38a9b11ace52cd8279477f00dd471223c320ea071ae98c8225d5193c689fa54a` |
| `arrow-format-19.0.0-SNAPSHOT.jar` | fix | `291fb7f2821c8801147c5cdc4f1eb9e831b2b7805129b04acf9ad494f0a79ff6` |
| `arrow-memory-core-19.0.0-SNAPSHOT.jar` | fix | `9a7a8c56b291afd255d9c034e01ec239683a9bc1f73c0c039b1a0663baab710a` |
| `arrow-memory-unsafe-19.0.0-SNAPSHOT.jar` | fix | `11242096cbb71bd4cdf13fb64f504bb302951e888390cfad81c9443c55099b6a` |
| `arrow-memory-netty-19.0.0-SNAPSHOT.jar` | fix | `89c6eb75e766f0a0d0a56239f688c0622215f1fda0ce224dc4058ea93f4dab5c` |
| `arrow-memory-netty-buffer-patch-19.0.0-SNAPSHOT.jar` | fix | `2e81ab1475529395798dce01188f0efc959d4baac51808022da09330ee42c4d2` |

**Runtime classpaths** (each side, every entry checked to exist; `ListViewVector`, `SmallIntVector`, `RootAllocator` and the allocator factory load on JDK 17 with
`$O/scripts/java/classes/ClassLoadCheck`): `$O/artifacts/L06-arrow-java-ROLE.runtime-classpath-unsafe.txt` (unsafe allocator) and
`$O/artifacts/L06-arrow-java-ROLE.runtime-classpath-netty.txt` (netty allocator). Use:
`$J17/bin/java --add-opens=java.base/java.nio=ALL-UNNAMED -cp CLASSES:$(cat $O/artifacts/L06-arrow-java-ROLE.runtime-classpath-unsafe.txt) ...`.

**Landed tests** (`TestListViewVector`, upstream Maven build, JDK 17; logs `$O/logs/L06-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, its own test, online | 64 run, 0 failures, 0 errors, 0 skipped (96 s) |
| fix, offline | 64 run, 0 failures, 0 errors, 0 skipped (7 s) |
| parent, its own test, offline (clean tree) | 56 run, 0 failures, 0 errors, 0 skipped (55 s) |
| fix's test file on the parent, offline | 64 run, 8 failures, 0 errors, 0 skipped (11 s); failing: `TestListViewVector(netty)#testGetElementStartIndexAndEndIndexOrderedOffsetsNoIntersection`, `TestListViewVector(netty)#testGetElementStartIndexAndEndIndexOrderedOffsetsAsInSpecification`, `TestListViewVector(netty)#testGetElementStartIndexAndEndIndexNotOrderedOffsetsNoIntersection`, `TestListViewVector(netty)#testGetElementStartIndexAndEndIndexOrderedOffsetsWithIntersection`, `TestListViewVector#testGetElementStartIndexAndEndIndexOrderedOffsetsNoIntersection`, `TestListViewVector#testGetElementStartIndexAndEndIndexOrderedOffsetsAsInSpecification`, `TestListViewVector#testGetElementStartIndexAndEndIndexNotOrderedOffsetsNoIntersection`, `TestListViewVector#testGetElementStartIndexAndEndIndexOrderedOffsetsWithIntersection` |

The four new end-index tests fail on the parent under both allocators, e.g. `testGetElementStartIndexAndEndIndexNotOrderedOffsetsNoIntersection:2219 expected: <6> but was: <2>`
and `testGetElementStartIndexAndEndIndexOrderedOffsetsAsInSpecification:2259 expected: <7> but was: <3>` (the old end = size). No landed test hashes a view.

**Release side.** Central has 18.3.0, 19.0.0, 20.0.0. `ListViewVector.java` in **19.0.0-sources equals the fix's**; 19.0.0's vector sources differ from the fix's in three
other files (`BaseLargeVariableWidthVector`, `BaseVariableWidthVector`, `VectorSchemaRoot`); from the parent's, in those and `ListViewVector`. 18.3.0 differs from the
parent in 34 files. So **no release equals the parent**; 19.0.0 contains the fix plus later changes. Resolved with strict checksums (`$O/releases/L06-arrow-vector-VERSION/`,
with `arrow-memory-unsafe`):

| Jar | sha256 |
|---|---|
| `$O/releases/L06-arrow-vector-18.3.0/lib/arrow-vector-18.3.0.jar` | `b37eda92daccaffc12abf5ed425db1d0bdb3edea150a6ca856f1cf4292442299` |
| `$O/releases/L06-arrow-vector-19.0.0/lib/arrow-vector-19.0.0.jar` | `113e70317945e780050f13d17027d862d4c5d1cebe06c9fd8a5e922945bb2f8c` |

**Signatures.** `arrow-vector`, `arrow-memory-core`, `arrow-memory-unsafe`, `arrow-format` 18.3.0: good, key `D7F359228AE6906022188C6D72A6333C8A461DF4` (Jean-Baptiste Onofré);
19.0.0: good, key `1AA8CF92D409A73393D0B736BFF2EE42C8282E76` (Gang Wu); both keys from `https://downloads.apache.org/arrow/KEYS`
(saved `$O/keys-B/arrow-KEYS`, sha256 `32aadf060e800bb95998cb08561939d7aebbaf5445097d814fb01af959e89501`). Keyring `$O/gnupg-B`, agent stopped.

**Jobs.** None: the offline build and test run takes under a minute.

**For the domain agent**
- Use the built jars of each side (no release equals the parent) with one allocator on the classpath; `--add-opens=java.base/java.nio=ALL-UNNAMED` on JDK 17+.
- Only `ListViewVector` (and its `TransferImpl`) differs between the sides' vector jars in changed source; every other module is class-identical.
- Build arrow-java with Maven 3.9.9, not 3.10.0 (Develocity extension).

### L07 · JGraphT #792 — three edge-disjoint paths after successive searches (pinned source build of jgrapht-core)

**Pins.** Parent `e7ae7a506ca4c2943878247a6e02bf71abc9b2d4`, fix `26630083eda568be7099c408638ce31c4d94b4a4`. Worktrees `$W/L07-jgrapht-parent`, `$W/L07-jgrapht-fix`. Squash commit with one parent = the brief's.
Changed production file: `jgrapht-core/src/main/java/org/jgrapht/alg/shortestpath/BaseKDisjointShortestPathsAlgorithm.java` (only; the Suurballe and Bhandari
classes are unchanged and inherit it). Changed test: `KDisjointShortestPathsTestCase.java` (abstract; run through `BhandariKDisjointShortestPathsTest` and
`SuurballeKDisjointShortestPathsTest`; new test `testThreeDisjointPathsWithMultiHitsOnEdge`).

**Build facts.** Maven, module `jgrapht-core` of `jgrapht` **1.3.2-SNAPSHOT** (parent `org.sonatype.oss:oss-parent:7`), compiler source/target 1.8.
`pom.xml` and `jgrapht-core/pom.xml` are identical at both pins. Built on **JDK 8u512** (`$J8`) with Maven 3.10.0. Runtime dependency: `org.jheaps:jheaps:0.11`
(sha256 `ea2fc1f299bfe85ebbc2f054d6a89eea17f06065192cfa31997f876536a7b383`); test: JUnit 4, junit-toolbox.

**Commands** (`$O/scripts/mvn_case.sh WT jgrapht-core TAG $J8 TESTS [online]`, i.e. from `jgrapht-core/`):
- online (first resolution, 30 s): `JAVA_HOME=$J8 MAVEN_OPTS=-Xmx1g $MVN -Daether.connector.basic.threads=1 $SK -Dtest=BhandariKDisjointShortestPathsTest,SuurballeKDisjointShortestPathsTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false package`
  (`$SK` as in `$O/scripts/mvn_case.sh`: only lint/report plugins skipped, `-DforkCount=1`)
- **offline (checked, 6–8 s)**: the same with `-o`.

**Artifacts** (`$O/artifacts/`):

| File or class | Side | sha256 |
|---|---|---|
| `L07-jgrapht-parent-core.jar` | parent | `6643e6bb68df48e5d0953eb504aaa3823a8a8d2b12ad0da0b2f84c147ca34fd8` |
| `org/jgrapht/alg/shortestpath/BaseKDisjointShortestPathsAlgorithm.class` | parent | `76027138e87ea1a5014be0111ffb08cd1279dd535666496522b836bcb94f9cde` |
| `L07-jgrapht-fix-core.jar` | fix | `d16ead94f75608791220518e2075940a4d865fea5e6bd6c692ea5cb274ffea50` |
| `org/jgrapht/alg/shortestpath/BaseKDisjointShortestPathsAlgorithm.class` | fix | `280a676b1cc3cf5ce755f7a9c9b210705655b8fdc552152868fbb5c91b3515e0` |

Runtime classpath (same at both pins): `$O/artifacts/L07-jgrapht-fix.runtime-classpath.txt` (jheaps only); test classpath `$O/artifacts/L07-jgrapht-fix.test-classpath.txt`.
Use `$J8/bin/java -cp $O/artifacts/L07-jgrapht-ROLE-core.jar:$(cat $O/artifacts/L07-jgrapht-fix.runtime-classpath.txt) ...` (the algorithm classes and
`SimpleDirectedWeightedGraph` load from it on JDK 8).

**Landed tests** (upstream Maven build, JDK 8; logs `$O/logs/L07-*.log`):

| Run | Result |
|---|---|
| fix, its own tests, online | 43 run, 0 failures, 0 errors, 0 skipped (30 s) |
| fix, offline | 43 run, 0 failures, 0 errors, 0 skipped (6 s) |
| parent, its own tests, offline | 41 run, 0 failures, 0 errors, 0 skipped (8 s) |
| fix's test case on the parent, offline | 43 run, 0 failures, 2 errors, 0 skipped (9 s); failing: `BhandariKDisjointShortestPathsTest#testThreeDisjointPathsWithMultiHitsOnEdge`, `SuurballeKDisjointShortestPathsTest#testThreeDisjointPathsWithMultiHitsOnEdge` |

On the parent the new test throws `NullPointerException` (reported at `KDisjointShortestPathsTestCase.testThreeDisjointPathsWithMultiHitsOnEdge:983`; this
surefire trims the stack, so the throwing frame inside the algorithm is not in the report) for both algorithms, as the PR says.

**Release side.** `BaseKDisjointShortestPathsAlgorithm.java`, `SuurballeKDisjointShortestPaths.java` and `BhandariKDisjointShortestPaths.java` in
**jgrapht-core 1.3.1-sources equal the parent's** (the issue's affected version); 1.4.0's three differ from both sides (later changes). No release equals the fix.
(Only these three files were compared, not the whole module.) Resolved with strict checksums (`$O/releases/L07-jgrapht-core-VERSION/`, with jheaps 0.10 / 0.11):

| Jar | sha256 |
|---|---|
| `$O/releases/L07-jgrapht-core-1.3.1/lib/jgrapht-core-1.3.1.jar` | `71dc44221c43ae89e59e42d024cce9d1dfaef844afb544ca1cdbf96a4bdf2736` |
| `$O/releases/L07-jgrapht-core-1.4.0/lib/jgrapht-core-1.4.0.jar` | `e6db18743ec01561623c4c6242f8778289da4bf990ac77fa659e09471690856f` |

**Signatures.** jgrapht-core 1.3.1 and 1.4.0: good, key `CFCFCC5AB00281118162F7EB0586E496D329C038` (Joris Kinable), from keyserver.ubuntu.com with nothing further
vouching for it (`$O/keys-B/fetch-*/`). jheaps not checked.

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- The built jars are the pins' own; 1.3.1 stands for the parent's three algorithm files but was not compared beyond them.
- The landed test checks counts and vertex sequences only; it reaches the parent's `NullPointerException`.

### L08 · Apache Commons Statistics #140 — Cauchy tail quantiles for tiny probabilities (pinned source build of `commons-statistics-distribution`)

**Pins.** Parent `bfcc6e62e2960512ff699809434d5d7774bf16dd`, fix `2535c20ad85ce756c0d396151d83e7fc4e2c904c` (squash, one parent = the brief's). Worktrees `$W/L08-commons-statistics-parent`, `$W/L08-commons-statistics-fix`.
Changed production file: `commons-statistics-distribution/src/main/java/org/apache/commons/statistics/distribution/CauchyDistribution.java`.
Changed test: `CauchyDistributionTest` (new `testInverseProbabilityTails`, `testInverseProbabilityTailsAreMonotonic`); also `src/changes/changes.xml`.

**Build facts.** Maven, module `commons-statistics-distribution` of the reactor `commons-statistics` **1.4-SNAPSHOT**, parent
`org.apache.commons:commons-parent:107`, compiler source/target 1.8. Built with Maven 3.10.0 on **JDK 17.0.21**; Java 8 bytecode (major 52).
Runtime dependencies (same at both pins): commons-numbers core, combinatorics, gamma, fraction, rootfinder **1.3**, and
**commons-rng-client-api and commons-rng-sampling 1.8-SNAPSHOT** (see the snapshot table below).

**Commands** (from `$W/L08-commons-statistics-ROLE/commons-statistics-distribution`), wrapped as
`$O/scripts/mvn_A.sh WT commons-statistics-distribution TAG $J17 CauchyDistributionTest [online]`:
- online (29 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=CauchyDistributionTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 5–8 s on both pins)**: the same with `-o`.

**Artifacts:**

| File | sha256 |
|---|---|
| `L08-commons-statistics-parent.jar` | `ab5ea4bc9fc8ca360f928327c28b5f04958919da4a5517827ed860099deb2729` |
| `L08-commons-statistics-fix.jar` | `dea3bcb814c41937b61f0964e85ab09c16c82bf6576198cf3f8861f18e1c441c` |
| `org/apache/commons/statistics/distribution/CauchyDistribution.class` (parent) | `5293262a529e92805ebe8f000328cfb003263875dff09a9bd859c25881dd7d16` |
| `org/apache/commons/statistics/distribution/CauchyDistribution.class` (fix) | `4b1d23035a4eda4f3d3348b4c4c4a3b663f7594a7be7c37a93f0f639a94e1846` |

Runtime classpath (same at both pins): `$O/artifacts/L08-commons-statistics-fix.runtime-classpath.txt`; test classpath
`$O/artifacts/L08-commons-statistics-fix.test-classpath.txt`.

**Unstable input: commons-rng 1.8-SNAPSHOT.** The pins' BOM import (`statistics.commons.rng.version`) names it, and the POM declares the
Apache snapshot repository. Resolved on 2026-11-25 as timestamp `20261125.125551`, build 64 (each jar's `.sha1` from the repository matches):

| Jar | sha256 | |
|---|---|---|
| `commons-rng-client-api-1.8-20261125.125551-64.jar` | `25bc4047437489dec1635db855aef83a110ddcb3df47f58fafa16a3aae2ed2d9` | sha1 file matches |
| `commons-rng-core-1.8-20261125.125551-64.jar` | `59ea39815898b4dbf56e26bfe7c78c54cc6fde63f7a171cbbf7e10fb1330ed20` | sha1 file matches |
| `commons-rng-simple-1.8-20261125.125551-64.jar` | `aa23bb68d5e46969964e0a2104540e781997d5b06b3b6180cd7c976488b7bfb9` | sha1 file matches |
| `commons-rng-sampling-1.8-20261125.125551-64.jar` | `14105cda9cc2f99476ef89fdf44b6140868046a7ccba56bdd9c2a91d1f94b3b2` | sha1 file matches |

A later online build may pick up a newer snapshot; the offline form uses these. Cauchy's quantile code does not call commons-rng
(only sampling does).

**Landed tests** (`CauchyDistributionTest`, JDK 17):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=58 failures=0 errors=0 skipped=0; offline tests=58 failures=0 errors=0 skipped=0 |
| parent, its own test (offline) | tests=56 failures=0 errors=0 skipped=0 |
| fix's test file on the parent (offline) | tests=58 failures=2 errors=0 skipped=0: **CauchyDistributionTest#testInverseProbabilityTailsAreMonotonic CauchyDistributionTest#testInverseProbabilityTails **(`icdf(1.0E-5) ==> expected: <-63661.47721581417> but was: <-63661.47721549608>` at line 85; `icdf(1.0E-18)` not monotonic at line 110) |

**Release side.** **No release has the fix** (newest is 1.3). `commons-statistics-distribution 1.3` has the **parent's quantile code**; its
`CauchyDistribution.java` differs from the parent only in the factory's argument checks (the parent also rejects a NaN scale and a NaN
location) and in comments. 1.2 differs further. Resolved: `$O/releases/commons-statistics-distribution-1.3/` (with commons-numbers 1.3 and
commons-rng 1.6 releases).

**Signatures** (keyring `$O/gnupg-A`; key `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` is in the Commons KEYS file, `$O/dl/A-keys/commons-KEYS`):

| Jar | Signer | Result |
|---|---|---|
| `commons-numbers-combinatorics-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-numbers-core-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-numbers-fraction-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-numbers-gamma-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-numbers-rootfinder-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-rng-client-api-1.6.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-rng-sampling-1.6.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |
| `commons-statistics-distribution-1.3.jar` | `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` (Alex Herbert (CODE SIGNING KEY)) | GOODSIG |

The snapshot jars are not signed (snapshots never are).

**Jobs.** None.

**For the domain agent**
- The jars are the pins' own builds; 1.3 stands for the parent's quantile formulas, with older NaN validation.
- The brief's challenge (`of(0, 2^-100)`, `p = 2^-1050`) and its intent/control values were not run.

### L09 · Eclipse RDF4J #1989 — empty input grouped by a variable gives zero rows (pinned build of the evaluation module; release 3.1.2 = fix; compliance tests by job)

**Pins.** Parent `c2c7a5265e6c40bc5dc2574260c96c3e10f9a87c`, fix `1767ceebe5d309238263bdca732b730cc47b3e45`. Worktrees `$W/L09-rdf4j-parent`, `$W/L09-rdf4j-fix`. Squash commit with one parent = the brief's.
Changed production file: `core/queryalgebra/evaluation/src/main/java/org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator.java` (only). The other 16
changed files are tests and test resources: `GroupIteratorTest` (new `testMaxEmptySet_Grouped`), `ComplexSPARQLQueryTest` in `testsuites/sparql` main code
(six new Max/Min/Sample empty-group tests, run against the memory store by `compliance/sparql`'s `MemoryComplexSPARQLQueryTest`), the new
`SPARQL12QueryTest` with `testcases-sparql-1.2/aggregates/agg-empty-group-{1,2}`, and the W3C SPARQL 1.1 manifest, where the PR disables `agg-empty-group`.

**Build facts.** Maven, `rdf4j` **3.1.2-SNAPSHOT**, Java 8 (`source`/`target` 8). Built on **JDK 8u512** (`$J8`) with **Maven 3.9.9** (`$O/tools/apache-maven-3.9.9`, see L06
for its checks): **Maven 3.10.0 refuses the build** ("'dependencies.dependency...' must be unique: rdf4j-repository-sail ... rdf4j-sail-memory" in
`compliance/repository/pom.xml`), where 3.9.9 only warns. Skipped: formatter, impsort and the usual lint/report plugins. `.mvn/maven.config` is `-V`.

**Commands** (`$O/scripts/rdf4j_B.sh WT TAG PL TESTS [online]`, from the worktree root):
- evaluation module, online (first resolution, 78 s): `JAVA_HOME=$J8 MAVEN_OPTS=-Xmx1g $O/tools/apache-maven-3.9.9/bin/mvn -B -s $O/maven-settings.xml -t $O/toolchains.xml -Daether.connector.basic.threads=1 -Dformatter.skip -Dimpsort.skip -Drat.skip -Dcheckstyle.skip -Dmaven.javadoc.skip -Denforcer.skip -Djacoco.skip -Danimal.sniffer.skip -Dspotbugs.skip -Dlicense.skip -Dmaven.source.skip -DforkCount=1 -pl core/queryalgebra/evaluation -am -Dtest=GroupIteratorTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false package`
- **offline (checked, 14–26 s)**: the same with `-o`.
- compliance tests: `compliance/sparql` sets surefire's `skipTests` and runs its `*Test` classes under **failsafe 2.19.1** in `integration-test`/`verify`.
  So they need `$O/scripts/rdf4j_verify.sh WT TAG compliance/sparql GroupIteratorTest MemoryComplexSPARQLQueryTest,SPARQL12QueryTest [online]`: `-pl compliance/sparql -am
  -Dtest=GroupIteratorTest -Dit.test=MemoryComplexSPARQLQueryTest,SPARQL12QueryTest -Dit.failIfNoSpecifiedTests=false verify` with `MAVEN_OPTS=-Xmx2g`.
  The `-am` chain includes the HTTP server war, hence the job. **The first job (`package` with `-Dtest=...`) ran only `GroupIteratorTest`**: every
  compliance module logged "No tests to run" or "Tests are skipped", so its rows below do not cover the compliance classes.

**Artifacts** (`$O/artifacts/`). The fix's evaluation jar is **class-identical to Central's `rdf4j-queryalgebra-evaluation-3.1.2.jar`** (237 of 237 classes);
the parent's differs from it in exactly the 11 `GroupIterator*` classes:

| File or class | Side | sha256 |
|---|---|---|
| `L09-rdf4j-parent-queryalgebra-evaluation.jar` | parent | `02492e6c152c75bad9322b29c7e0a4d385d0a4f3247620d17fc9381cdbb91792` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Aggregate.class` | parent | `f64f21d63dcb151550f9fa34b0b1bc266c0d153069468fcc32e51b327ce22fea` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$AvgAggregate.class` | parent | `d26a2c06b266d07b17d77480e6df93a49126766526186f86a33783cd411debaa` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$ConcatAggregate.class` | parent | `bb2237f6d5b8a65ea8ad2ac67e09c984eafbcb1d7a36c8ac6512f183ab9844c2` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$CountAggregate.class` | parent | `282a29783617b3bb03d96636cbafeb6e8521b5698ae7e53bddabe960515f0eb3` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Entry.class` | parent | `e2d2c5ab14f44429710f63f05fff0f89197e64a5b616fa08f0b95789baceac74` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Key.class` | parent | `52c7d61f319dd30092c1febb5e782d6d6af61d99f2815d774904eb03d784e826` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MaxAggregate.class` | parent | `f10fd144c8f58383d1d62a4803bd28781b0f33dadf7b403a34cc639641ac983a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MinAggregate.class` | parent | `c5db22351faea1e38eb24afa4db241105abf9a021f31ad7b5b053a30bf50254a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SampleAggregate.class` | parent | `f7c8df2590780b08d6ca69c35d1f2cbc36c0d2f82169bfa6d6bdc5e373d6bad4` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SumAggregate.class` | parent | `eb931d18708ef9b7ca8974341c43cd565de6a082c8578fc63993d9be1f30d8d1` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator.class` | parent | `e173f9776f902a8aefeb96b1237e0c632e4782b8063a5f3b4410a5a6b61f9599` |
| `L09-rdf4j-fix-queryalgebra-evaluation.jar` | fix | `a38d007adfb237661f8614137bef5cdd71319e1377789d7f13c24fb13451598a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Aggregate.class` | fix | `61c7f3b6ba8fae6092ae6cc62729e7ca54f6f379bc2ba85bff8a46b20e82eefb` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$AvgAggregate.class` | fix | `f12558e5657121e62dae51d4f9702bdd6ea3c3f7a590a3044531f7fea6109c3a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$ConcatAggregate.class` | fix | `98c4f77ee9049f45445a1cff15ed7e77601d45e2dd5ad08fb201cdbd91fab490` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$CountAggregate.class` | fix | `b92375a355aafa7eda1126f88eee9b21e49dbb6353c96490ca14293ae5c7a1aa` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Entry.class` | fix | `94c85a9754267f9a0ed619c4900fda280b4143f022fe60aba8735a0d9ec94847` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Key.class` | fix | `a94fb9a2758dcb679509d6334ce5ac98bd8a39e63c50ade7aa00fbe8f1cce335` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MaxAggregate.class` | fix | `225bd619fb535cfc56c23c652dac52fba1e303bd6f759d06d2725767070b6716` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MinAggregate.class` | fix | `5a6f2638b6e871e94d2fd78f81d449c0e19e5357a8b939b9424cc6e3fd0aa74f` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SampleAggregate.class` | fix | `85fe98dc73750d99a2e4c6dc3a19fd1ac2b5e60f4d22b6b10c13afbc5807fc96` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SumAggregate.class` | fix | `2d5fcbabce96f7945ba0e0a3083aeea90bb09f09bfe56747ca1ed86aaf49df5a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator.class` | fix | `0e6281a1a1a3572c6bf4ead8564fc0fbe3558cb108d9b8ac203425bfefcdf478` |
| `rdf4j-queryalgebra-evaluation-3.1.2.jar` | release-3.1.2 | `5aca113ed5e88bc2645c2738e50408bae892e7d4dfd7a8980cc3e4c398103db7` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Aggregate.class` | release-3.1.2 | `61c7f3b6ba8fae6092ae6cc62729e7ca54f6f379bc2ba85bff8a46b20e82eefb` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$AvgAggregate.class` | release-3.1.2 | `f12558e5657121e62dae51d4f9702bdd6ea3c3f7a590a3044531f7fea6109c3a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$ConcatAggregate.class` | release-3.1.2 | `98c4f77ee9049f45445a1cff15ed7e77601d45e2dd5ad08fb201cdbd91fab490` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$CountAggregate.class` | release-3.1.2 | `b92375a355aafa7eda1126f88eee9b21e49dbb6353c96490ca14293ae5c7a1aa` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Entry.class` | release-3.1.2 | `94c85a9754267f9a0ed619c4900fda280b4143f022fe60aba8735a0d9ec94847` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$Key.class` | release-3.1.2 | `a94fb9a2758dcb679509d6334ce5ac98bd8a39e63c50ade7aa00fbe8f1cce335` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MaxAggregate.class` | release-3.1.2 | `225bd619fb535cfc56c23c652dac52fba1e303bd6f759d06d2725767070b6716` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$MinAggregate.class` | release-3.1.2 | `5a6f2638b6e871e94d2fd78f81d449c0e19e5357a8b939b9424cc6e3fd0aa74f` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SampleAggregate.class` | release-3.1.2 | `85fe98dc73750d99a2e4c6dc3a19fd1ac2b5e60f4d22b6b10c13afbc5807fc96` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator$SumAggregate.class` | release-3.1.2 | `2d5fcbabce96f7945ba0e0a3083aeea90bb09f09bfe56747ca1ed86aaf49df5a` |
| `org/eclipse/rdf4j/query/algebra/evaluation/iterator/GroupIterator.class` | release-3.1.2 | `0e6281a1a1a3572c6bf4ead8564fc0fbe3558cb108d9b8ac203425bfefcdf478` |

**Runtime classpaths:** `$O/artifacts/L09-rdf4j-ROLE.runtime-classpath.txt` = that side's built evaluation jar followed by the resolved 3.1.2 set
(`rdf4j-queryalgebra-evaluation`, `-repository-sail`, `-sail-memory`, `-queryparser-sparql`, `-queryresultio-sparqlxml` and their runtime graph, 38 jars) without
3.1.2's own evaluation jar. `GroupIterator`, `SailRepository` and `MemoryStore` load from it on JDK 8. The job also copies every rdf4j module jar built at each pin
to `$O/artifacts/L09-rdf4j-ROLE-modules/` (sha256 lists `$O/logs/L09-rdf4j-ROLE-modules.sha256`, class comparison `$O/logs/L09-modules-parent-vs-fix.txt`).

**Landed tests** (logs `$O/logs/L09-*.log`):

| Run | Result |
|---|---|
| fix, `GroupIteratorTest`, online | 9 run, 0 failures, 0 errors, 0 skipped (78 s) |
| fix, offline | 9 run, 0 failures, 0 errors, 0 skipped (14 s) |
| parent, its own `GroupIteratorTest`, offline | 8 run, 0 failures, 0 errors, 0 skipped (26 s) |
| fix's `GroupIteratorTest` on the parent, offline | 9 run, 1 failures, 0 errors, 0 skipped (14 s); failing: `GroupIteratorTest#testMaxEmptySet_Grouped` |
| fix, `-pl compliance/sparql -am` to `package`, online (first job; only `GroupIteratorTest` ran) | 9 run, 0 failures, 0 errors, 0 skipped (143 s) |
| fix, the same, offline (first job; only `GroupIteratorTest` ran) | 9 run, 0 failures, 0 errors, 0 skipped (43 s) |
| parent, the same, offline (first job; only `GroupIteratorTest` ran) | 8 run, 0 failures, 0 errors, 0 skipped (75 s) |
| the PR's test-side files on the parent, offline (first job; only `GroupIteratorTest` ran) | 9 run, 1 failures, 0 errors, 0 skipped (38 s); failing: `GroupIteratorTest#testMaxEmptySet_Grouped` |
| fix, to `verify`: failsafe `MemoryComplexSPARQLQueryTest` + `SPARQL12QueryTest`, surefire `GroupIteratorTest`, online (second job) | 92 run, 0 failures, 0 errors, 0 skipped (90 s); MemoryComplexSPARQLQueryTest: Tests run: 81, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.574 sec - in org.eclipse.rdf4j.sail.memory.MemoryComplexSPARQLQueryTest; SPARQL12QueryTest: Tests run: 2, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.349 sec - in org.eclipse.rdf4j.query.parser.sparql.manifest.SPARQL12QueryTest; GroupIteratorTest: Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.113 s - in org.eclipse.rdf4j.query.algebra.evaluation.iterator.GroupIteratorTest |
| fix, the same, offline (second job) | 92 run, 0 failures, 0 errors, 0 skipped (37 s); MemoryComplexSPARQLQueryTest: Tests run: 81, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.525 sec - in org.eclipse.rdf4j.sail.memory.MemoryComplexSPARQLQueryTest; SPARQL12QueryTest: Tests run: 2, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.324 sec - in org.eclipse.rdf4j.query.parser.sparql.manifest.SPARQL12QueryTest; GroupIteratorTest: Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.098 s - in org.eclipse.rdf4j.query.algebra.evaluation.iterator.GroupIteratorTest |
| parent, its own `MemoryComplexSPARQLQueryTest` + `GroupIteratorTest`, offline (second job) | 86 run, 0 failures, 0 errors, 0 skipped (78 s); MemoryComplexSPARQLQueryTest: Tests run: 78, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.611 sec - in org.eclipse.rdf4j.sail.memory.MemoryComplexSPARQLQueryTest; GroupIteratorTest: Tests run: 8, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.105 s - in org.eclipse.rdf4j.query.algebra.evaluation.iterator.GroupIteratorTest |
| the PR's test-side files on the parent, offline (second job; expected to fail) | 92 run, 5 failures, 0 errors, 0 skipped (38 s); failing: `SPARQL12QueryTest#agg`, `MemoryComplexSPARQLQueryTest#testMinAggregateWithGroupEmptyResult`, `MemoryComplexSPARQLQueryTest#testSampleAggregateWithGroupEmptyResult`, `MemoryComplexSPARQLQueryTest#testMaxAggregateWithGroupEmptyResult`, `GroupIteratorTest#testMaxEmptySet_Grouped`; MemoryComplexSPARQLQueryTest: Tests run: 81, Failures: 3, Errors: 0, Skipped: 0, Time elapsed: 0.492 sec <<< FAILURE! - in org.eclipse.rdf4j.sail.memory.MemoryComplexSPARQLQueryTest; SPARQL12QueryTest: Tests run: 2, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.294 sec <<< FAILURE! - in org.eclipse.rdf4j.query.parser.sparql.manifest.SPARQL12QueryTest; GroupIteratorTest: Tests run: 9, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.12 s <<< FAILURE! - in org.eclipse.rdf4j.query.algebra.evaluation.iterator.GroupIteratorTest |

On the parent `testMaxEmptySet_Grouped:91` fails with `ComparisonFailure: expected:<[fals]e> but was:<[tru]e>` (the grouped iterator still has a row).

**Release side.** Central has 3.1.1, 3.1.2, 3.1.3, … **rdf4j 3.1.2 = the fix**: the sources jar of every one of the 24 rdf4j runtime modules resolved for
3.1.2 (model, query, queryalgebra-model/-evaluation, queryparser-sparql, repository-api/-sail, sail-api/-base/-memory, rio-*, queryresultio-*, http-*, util)
equals the fix tree's `src/main/java` file for file, and the evaluation jar is class-identical to the fix's build. The parent = 3.1.2 with the parent's
`GroupIterator` (an overlay is the parent's built evaluation jar, already on its classpath above). 3.1.1 differs from both sides in `GroupIterator` and
`SilentIteration`. Resolved with strict checksums (`$O/releases/L09-rdf4j-3.1.1/`, `$O/releases/L09-rdf4j-3.1.2/`):

| Jar | sha256 |
|---|---|
| `$O/releases/L09-rdf4j-3.1.2/lib/rdf4j-queryalgebra-evaluation-3.1.2.jar` | `5aca113ed5e88bc2645c2738e50408bae892e7d4dfd7a8980cc3e4c398103db7` |
| `$O/releases/L09-rdf4j-3.1.2/lib/rdf4j-sail-memory-3.1.2.jar` | `c6c3871f0feba12b5aa14524a2ff91c270ed3f01f6b75aae49d4286b7a96bf9a` |
| `$O/releases/L09-rdf4j-3.1.2/lib/rdf4j-repository-sail-3.1.2.jar` | `af571049b9f1271c3006691ea854aa2a98dca3997ea1fd8d89e3e07134ca7ac1` |
| `$O/releases/L09-rdf4j-3.1.2/lib/rdf4j-queryparser-sparql-3.1.2.jar` | `f5a51265a869be020f3a6cd618f15ce6d4b94d5ff6e9c8993ca7a47839f96d83` |

**Signatures.** rdf4j-queryalgebra-evaluation, -sail-memory, -repository-sail, -queryparser-sparql 3.1.2: good, key `568A177DC23736311CF73C987FAA78B1C3FFDD85`
("Eclipse RDF4J project"), from keyserver.ubuntu.com with nothing further vouching for it. The other 3.1.2 jars rest on Central's checksums.

**Jobs.** `20261125-162448-setup-run-rdf4j-1989-s-landed-empty-grou` (`$O/scripts/submit_B.py l09`): passed, but stopped at `package`, so of the three classes only
`GroupIteratorTest` ran (the same results as inline); it did copy the module jars of both sides and compare them. Its rows are kept above, labelled.
`20261125-165913-setup-run-rdf4j-1989-s-landed-compliance` (`$O/scripts/submit_L09b.py`): the same build to `verify`, so failsafe runs the compliance classes, on the
fix online and offline, the parent's own offline, and the PR's test-side files on the parent (production code unchanged): passed, and the rows above
come from it. All three classes ran in every step (the failsafe and surefire lines name them, and the transplant's failures are in all three). Two
faults in the setup's own tooling, neither of which changed what ran: `rdf4j_verify.sh`'s per-class pattern took the package as `[a-z.]*`, which
`rdf4j` does not match, so the as-run summaries said "NOT RUN" for every class; and the step guard meant to fail on "NOT RUN" did not take effect.
The pattern is fixed (`[a-z0-9.]*`) and the class lines in `$O/logs/L09-*.verify-*.junit.txt` were recomputed from the job's own `.log` files; the
as-run summaries are kept beside them as `*.junit.txt.as-run`.

**For the domain agent**
- For a JVM run, the 3.1.2 release set with each side's evaluation jar first is the simplest classpath; for the fix side, plain 3.1.2 is class-identical.
- The brief's public scenario (SailRepository over MemoryStore) needs `rdf4j-queryparser-sparql` and `rdf4j-queryresultio-*` at runtime; they are in the classpath files.
- Build rdf4j with Maven 3.9.9 and JDK 8.

### L10 · Apache Calcite #5378 — ProjectSetOpTransposeRule across EXCEPT ALL / INTERSECT ALL (upstream Gradle 8.14.4 build at both pins, by job)

**Pins.** parent `b8ccec91b7670d8c62a5712e210bb25f396ade7e` (tree `1504f135fc021b3f1c4e2bb19c496fdbc9b838be`); fix `5f48eec8d5e3f25df641393c9440e086646868b7` (tree `f5465be82548360999021be1a9a4a5643d8d9cdc`) (squash, one parent = the brief's). Worktrees `$W/L10-calcite-parent`, `$W/L10-calcite-fix`.
Changed production file: `core/src/main/java/org/apache/calcite/rel/rules/ProjectSetOpTransposeRule.java` (the rule now returns early for
EXCEPT ALL / INTERSECT ALL unless the project is a permutation). Changed tests: `core/src/test/resources/sql/planner.iq` (new CALCITE-7909
block, run by `CoreQuidemTest`) and `core/src/test/resources/org/apache/calcite/test/RelOptRulesTest.xml` (expected plan of the existing
`RelOptRulesTest.testMinusMergeRule` changes).

**Build facts.** Gradle 8.14.4 (wrapper `distributionSha256Sum` = published = `f1771298a70f6db5a29daf62378c4e18a17fc33c9ba6b14362e0cdf40610380d`), project version `1.43.0-SNAPSHOT`
(`calcite.version=1.43.0` in `gradle.properties`, snapshot unless released). The build compiles with a **JDK 25 toolchain**
(`jdkBuildVersion` default 25) at `--release 8`; Gradle itself runs on JDK 21 here (`$J21`), test JVMs on the Gradle JVM.
The build has a `buildSrc` (Kotlin, fmpp, javacc), the Develocity plugin (runs use `--no-scan`) and `org.gradle.caching=true` (local cache only).
Online resolution of core, linq4j and testkit (all `*Classpath` and `annotationProcessor` configurations) took 3m01s inline
(`$O/logs/L10-fix.resolve-online.log`), so the job's offline steps have what they need.

**Commands** (from the worktree; `$G10` = `JAVA_HOME=$J21 choom -n 500 -- $O/tools/gradle-8.14.4/bin/gradle --no-daemon --no-scan --console=plain
--max-workers=3 -Dorg.gradle.jvmargs=-Xmx2g -Porg.gradle.java.installations.auto-download=false -Porg.gradle.java.installations.paths=$J25,$J21`):
- build and landed tests: `$G10 [--offline] --continue :core:jar :core:test --tests org.apache.calcite.test.CoreQuidemTest --tests org.apache.calcite.test.RelOptRulesTest`
- a single Quidem file outside Gradle: `CoreQuidemTest.main` takes file names (`java ... org.apache.calcite.test.CoreQuidemTest sql/planner.iq`) on the test runtime classpath.
- runtime classpath export (the job): `$G10 --offline -I $O/scripts/resolve-all.init.gradle :core:setupWriteClasspath -PsetupCpConf=runtimeClasspath -PsetupCpOut=FILE`,
  then `$O/scripts/cp_export_D.py`.
The offline form is exercised by the job (steps 2–6); it was not run inline.

**Artifacts.** 

| File in `$O/artifacts/` | sha256 |
|---|---|
| `L10-calcite-fix-calcite-core-1.43.0-SNAPSHOT.jar` | `3a1461c8ff66e2aa831cfc71709de2021a3129c3a23c8d92e0db86099fd7e64d` |
| `L10-calcite-fix-calcite-linq4j-1.43.0-SNAPSHOT.jar` | `a2e3947f948dc7e0084a2fb66023c3094779a4d90411209e7c271c96025d667a` |
| `L10-calcite-parent-calcite-core-1.43.0-SNAPSHOT.jar` | `8834c2d897b98a3c5840356f0ba35018568a6881be6a61277c951cd1aa733c52` |
| `L10-calcite-parent-calcite-linq4j-1.43.0-SNAPSHOT.jar` | `a2e3947f948dc7e0084a2fb66023c3094779a4d90411209e7c271c96025d667a` |

Class digests (sha256 of each changed class, per side) are in `$O/artifacts/L10-*.class-digests.txt`; runtime classpaths in `$O/artifacts/L10-*-classpath.txt` (colon-separated; project jars point at the copies above).

Expected names: `L10-calcite-ROLE-calcite-core-1.43.0-SNAPSHOT.jar`, `L10-calcite-ROLE-calcite-linq4j-1.43.0-SNAPSHOT.jar`,
`L10-calcite-ROLE.core-runtime-classpath.txt`, `L10-calcite-ROLE-calcite-core-1.43.0-SNAPSHOT.class-digests.txt`.

**Landed tests.**

| Run | Result |
|---|---|
| fix, landed tests (first build, online) | junit tests=1006 failures=0 errors=0 skipped=4 |
| fix, again offline | junit tests=1006 failures=0 errors=0 skipped=4 |
| parent, its own tests (offline) | junit tests=1006 failures=0 errors=0 skipped=4 |
| fix's test files on the parent (offline; expected to fail) | junit tests=1007 failures=3 errors=0 skipped=4; junit failed CoreQuidemTest#[8] sql/planner.iq; junit failed RelOptRulesTest#testMinusMergeRule(); junit failed RelOptRulesTest#executionError |

Run by job `20261125-161916-setup-build-calcite-core-at-both-5378-re`; logs `$O/logs/L10-*.gradle-log.txt` and `*.junit.txt`.

**Release side.** No release has the fix: Central's newest `calcite-core` is 1.42.0. Its `ProjectSetOpTransposeRule.java` (tag `calcite-1.42.0`)
is byte-identical to the parent's; other core sources differ (1.42.0 is older than the parent). Release graph resolved with strict checksums:
`$O/releases/L10-calcite-core-1.42.0/` (`lib/`, `sources/`, `classpath.txt`, `tree.txt`).

| File | sha256 |
|---|---|
| `upstream/L10-tags/rule-1.42.0.java` | `96c82af34318e555a39b06d033bf1213d8557c3e2447419199e0c17ccaf1607e` |
| `upstream/L10-tags/rule-parent.java` | `96c82af34318e555a39b06d033bf1213d8557c3e2447419199e0c17ccaf1607e` |

**Signatures.** Keyring `$O/gnupg-D`, Calcite KEYS from downloads.apache.org (`$O/keys-D/calcite-KEYS`, sha256 `d5158d89e29ad32ede46c56404b9a6b66d1d57425363ba2ed67c37d0a5d7ffaa`).

| Jar (Maven Central) | sha256 | Signature | Signer key |
|---|---|---|---|
| `calcite-core-1.42.0.jar` | `2ed5489201baab842001c95f939a0829849cf3cdaed9cdbf4b9078633c35792b` | good | `04749577FD934674B9CD45C5D77C3383F1927570` |
| `calcite-linq4j-1.42.0.jar` | `6f54fa9f24a07ad961e0e1af499a58cfc2374a93ee280283beafe9035de3fa45` | good | `04749577FD934674B9CD45C5D77C3383F1927570` |

Wrapper jar (not used; the distribution is run directly): `gradle/wrapper/gradle-wrapper.jar` sha256 `498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17` (both pins) is **not**
8.14.4's (`7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172`); it equals Gradle 8.9's published wrapper checksum
(`498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17`, services.gradle.org) and the 8.9 entries of Gradle's own list (`gradle/actions` `wrapper-checksums.json`, sha256 `c5deb57f25df459bdd954a08338c685caf08b05b302afcd1fefd21c77c70f927`).

**Jobs.** `20261125-161916-setup-build-calcite-core-at-both-5378-re`.

**For the domain agent**
- No release carries the fix; use the pin jars from the job (1.42.0 has only the parent's rule source).
- The landed fixture enables the rule with Quidem's `!set planner-rules "+CoreRules.PROJECT_SET_OP_TRANSPOSE"` (in `planner.iq`); how a
  plain JDBC connection gets the same rule set was not looked into.
- Compile anything against the pins with `--release 8` or later; the jars need JDK 8+ to run.

### L11 · Apache Commons Imaging #335 — JPEG-in-TIFF decode clipped at the image edge (pinned source build)

**Pins.** Parent `4881f0b503d39e210b4fed29e25b26cbbefd5cd8`, fix `cbdb978098a042cb5fd2a768f6d8575835c28278` (two-parent merge; first parent = the brief's, second `fd7e23527830b3469f9c1b8fb567694b8da5838d`). Worktrees `$W/L11-commons-imaging-parent`,
`$W/L11-commons-imaging-fix`. Changed production file: `src/main/java/org/apache/commons/imaging/formats/jpeg/decoder/JpegDecoder.java`
(the loop limits `x2Limit`/`y2Limit` become `width - x1`/`height - y1`). Changed test: `TiffJpegTest`; added resources
`src/test/resources/data/images/tiff/14/TestJpegRgb127x127.tiff` and `TestSampleRgb127x127.tiff`.

**Build facts.** Maven, single module, `commons-imaging` **1.0-SNAPSHOT**, parent `org.apache.commons:commons-parent:64`, compiler
source/target 1.8. Built with Maven 3.10.0 on **JDK 17.0.21**; Java 8 bytecode (major 52). Runtime dependency: `commons-io:commons-io:2.15.0`.

**Commands** (from the worktree root), wrapped as `$O/scripts/mvn_A.sh WT . TAG $J17 TiffJpegTest [online]`:
- online (26 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=TiffJpegTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked, 7–10 s on both pins)**: the same with `-o`.

**Artifacts:**

| File | sha256 |
|---|---|
| `L11-commons-imaging-parent.jar` | `936307d4c6abb1337feb6cfa95b4b5e993a9a5b60848e511b91c5d309a44b96c` |
| `L11-commons-imaging-fix.jar` | `c5984b48756fd60b43f424c36723c3bcd82de097d79295de8c1b2f9cf55dcf6a` |
| `org/apache/commons/imaging/formats/jpeg/decoder/JpegDecoder.class` (parent) | `69a7bb6298e06e02704aa9d45ece45f6b6d81863fa465718ff70dfd79a416a5d` |
| `org/apache/commons/imaging/formats/jpeg/decoder/JpegDecoder.class` (fix) | `edebd4ad0a12b6b1b2a2c0f51dd6feab3be779636bda98f6619d8b388171f941` |

Runtime classpath (same at both pins): `$O/artifacts/L11-commons-imaging-fix.runtime-classpath.txt`; test classpath
`$O/artifacts/L11-commons-imaging-fix.test-classpath.txt`.

**Test images** (copied from the fix pin to `$O/artifacts/L11-resources/`; the two 127×127 files exist only from the fix pin on, the
264×264 pair of the brief's control is at both pins):

| File | sha256 | git blob at the fix pin | at the parent pin |
|---|---|---|---|
| `TestJpegRgb127x127.tiff` | `bf3355920a14c2d55e48b072efdc47f61fb3deb5cb5bfc372dff9e9d2d2032bb` | `1a651a87389b51914a9a759f64fb795d4db73d11` | no |
| `TestJpegTiles264x264.tiff` | `e48ca961837f2c0b7ec26731b3ce0c193d2dbbed205b0bc9382c3261d0a8d37b` | `77320015bab758f8527ac22b21e3f81c80cfa26e` | yes |
| `TestSample264x264.tiff` | `401d2b9c17a4c8e8edf797d4506f7181fd945ffe964223543ee6e5b1eb60c402` | `06d5fdd33675a5c8be8700c5c565325821e1b6f8` | yes |
| `TestSampleRgb127x127.tiff` | `76cf8c863391344a64c52b23051e8b40f18da75a983efff2dacd8a8b3ce79aa3` | `83d0881b03f05ff9aa8a4850b9df084d2e4f8d03` | no |

**Landed tests** (`TiffJpegTest`, JDK 17):

| Run | Result |
|---|---|
| fix, its own test (online, then offline) | tests=2 failures=0 errors=0 skipped=0; offline tests=2 failures=0 errors=0 skipped=0 |
| parent, its own test (offline) | tests=2 failures=0 errors=0 skipped=0 |
| fix's test file and the two new images on the parent (offline) | tests=2 failures=0 errors=2 skipped=0: **TiffJpegTest#testSubImage TiffJpegTest#testFullPixelMatch **(`ImagingException: Error parsing JPEG`, caused by `ArrayIndexOutOfBoundsException: Index 64 out of bounds for length 64`) |

**Release side.** **No release equals the parent.** `1.0-alpha3` predates this decoder code (its `JpegDecoder` has no such loop limits);
`1.0.0-alpha4`, `-alpha5` and `-alpha6` carry the **fix's** limits among other later changes to the file (none equals the fix byte for
byte). Resolved for reference: `$O/releases/commons-imaging-1.0.0-alpha4/` (with commons-io 2.16.0).

**Signatures** (keyring `$O/gnupg-A`; key `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` is in the Commons KEYS file):

| Jar | Signer | Result |
|---|---|---|
| `commons-imaging-1.0.0-alpha4.jar` | `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory (Code signing key)) | GOODSIG |
| `commons-io-2.15.0.jar` | `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory (Code signing key)) | GOODSIG |
| `commons-io-2.16.0.jar` | `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Gary David Gregory (Code signing key)) | GOODSIG |

**Jobs.** None.

**For the domain agent**
- Use the built jars for both sides; give the parent the 127×127 images from `$O/artifacts/L11-resources/` (they are not in its tree).
- The landed test compares luminance and alpha; the brief's six-pixel corner comparison was not run.

### L12 · Quartz #1496 — replacing a trigger with one of another type in the JDBC store (upstream Gradle 8.5 build at both pins, inline)

**Pins.** Parent `dccb522cd8675894996a0dc206461a08f8cf9eaf`, fix `adeae66354ff66cc4c716dd3aaac09e1571f64fa` (a two-parent merge into `main`; first parent = the brief's before pin).
Worktrees `$W/L12-quartz-parent`, `$W/L12-quartz-fix`. Changed production file:
`quartz/src/main/java/org/quartz/impl/jdbcjobstore/StdJDBCDelegate.java` (+9/−3). Test: `quartz/src/test/java/org/quartz/AbstractJobStoreTest.java`
(+49; new method `testStoreTriggerReplaceChangesTriggerType`), run through its subclasses `org.quartz.impl.jdbcjobstore.JdbcJobStoreTest`
(JobStoreTX on embedded Derby) and `org.quartz.simpl.RAMJobStoreTest`.

**Build facts.** Gradle 8.5 (`$O/tools/gradle-8.5`, zip checked). The repository's `gradle-wrapper.jar`
`91941f522fbfd4431cf57e445fc3d5200c85f957bda2de5251353cf11174f4b5` (both pins) equals services.gradle.org's published wrapper jar for 8.0.x
(`$O/dl/gradle-C/gradle-8.0.2-wrapper.jar.sha256`), not 8.5's; it is not used. Gradle runs on **JDK 17** (`$J17`); the build's Java
**toolchain is 11** (`build.gradle`: `JavaLanguageVersion.of(11)`), given as `$J11` with auto-detection and auto-download off.
Version `2.5.1-SNAPSHOT` (`gradle.properties`), so the jar is `quartz-2.5.1-SNAPSHOT.jar`. Projects: `quartz`, `quartz-jobs`,
`quartz-stubs`, `examples`; only `:quartz` was built. Repositories: Central and the Plugin Portal; nothing was missing.
Two tests of the run are skipped by the suite itself.

Commands (online once, 37 s; offline 16–21 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/env.sh
$O/scripts/gradle_case_C.sh L12-quartz-fix 8.5 $J17 L12-quartz-fix.test-offline quartz/build/test-results/test --offline \
  "-Porg.gradle.java.installations.paths=$J11,$J17" -Porg.gradle.java.installations.auto-detect=false \
  :quartz:jar :quartz:test --tests org.quartz.impl.jdbcjobstore.JdbcJobStoreTest --tests org.quartz.simpl.RAMJobStoreTest
```

**Artifacts** (built offline from each pin; bind the class digest):

| File | sha256 |
|---|---|
| `$O/artifacts/L12-quartz-parent.jar` | `765d5ba06ebd168c73887e5c299f269278a956ffaecdf1c16abe8b6d80557ce4` |
| `$O/artifacts/L12-quartz-fix.jar` | `26f099931c4803e41a6d18b20071df11f2a90b1a4e20595f3c7056c43f45dae4` |

| Class | parent | fix |
|---|---|---|
| `org/quartz/impl/jdbcjobstore/StdJDBCDelegate.class` | `f3447cc49cca53f89bd1599349da77ef87db9259ced2459b9365a7b4bfaef9e4` | `2a5c497add4fd5646d53d3c7100449489a3258aad22effb1b93e0aae2c71d11a` |

It is the only class that differs (296 classes each side; `$O/logs/L12-classdiff.md`).

**Classpaths** (same at both pins; jars in `$GRADLE_USER_HOME` = `$O/gradle-home`):
- runtime: `$O/artifacts/L12-quartz.runtime-classpath.txt` (one line, `:`-separated), digests `$O/artifacts/L12-quartz.runtime-classpath.sha256`:
  HikariCP-5.0.1.jar slf4j-reload4j-2.0.16.jar slf4j-api-2.0.16.jar c3p0-0.10.1.jar jakarta.xml.bind-api-4.0.5.jar mchange-commons-java-0.3.1.jar jakarta.activation-api-2.1.4.jar reload4j-1.2.22.jar 
- test (external jars only, includes Derby 10.15.2.0, JUnit 5.11.4, Testcontainers 1.21.3 and the JDBC drivers):
  `$O/artifacts/L12-quartz.test-classpath.txt`, digests `$O/artifacts/L12-quartz.test-classpath.sha256`. `derby-10.15.2.0.jar`
  `3afe424625f4caea05ff2f9022be2d98634be4d69dee3529697dab6d9fe1142f`, `derbyshared-10.15.2.0.jar` `55365ab97e698080c6ccec65dbf7b8c63e4b4b77ad08f794d11458b1f2ea272c`, `derbytools-10.15.2.0.jar` `45d6dc34af9790f7f8fafb9b15d8525f3b429950fca4b4051e7e4f81f9170cd9`.
- The Derby DDL Quartz ships is inside the jar, `org/quartz/impl/jdbcjobstore/tables_derby.sql`; the test fixture that creates the
  database is `quartz/src/test/java/org/quartz/impl/jdbcjobstore/JdbcQuartzTestUtilities.java`.

**Landed test** (Gradle on JDK 17.0.21, toolchain JDK 11.0.33; logs `$O/logs/L12-quartz-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `JdbcJobStoreTest` + `RAMJobStoreTest` (online, then offline) | tests=38 failures=0 errors=0 skipped=2; offline: tests=38 failures=0 errors=0 skipped=2 |
| parent, its own copies (offline) | tests=36 failures=0 errors=0 skipped=2 |
| fix's `AbstractJobStoreTest.java` copied onto the parent (offline, restored after) | **tests=38 failures=1 errors=0 skipped=2**: `JdbcJobStoreTest.testStoreTriggerReplaceChangesTriggerType`, `org.quartz.JobPersistenceException: Couldn't retrieve trigger: No record found for selection of Trigger with key: 'typeChangeGroup.typeChangeTrigger' and statement: SELECT * FROM QRTZ_CRON_TRIGGERS ...`; the RAM store's copy passes |

**Release side** (`$O/releases/quartz-2.5.1`, `$O/releases/quartz-2.5.2`, strict checksums). Central's newest is 2.5.2 (metadata last updated
2025-12-01, before the merge on 2026-08-05); the pins still say `2.5.1-SNAPSHOT`. **No release carries the fix.** 2.5.2's
`StdJDBCDelegate.java` differs from the parent's in one line only, unrelated to the change (line 1933: `getObjectFromBlob(rs, COL_BLOB)` in 2.5.2,
`getObjectFromBlob(rss, COL_BLOB)` at the parent); 2.5.1's differs more. So 2.5.2 has the parent's trigger-replacement logic.
`quartz-2.5.2.jar` `452e418739c0da1bff255f7c1343dd3a92e1fdd3ceb126b185939edae9922091`, `quartz-2.5.1.jar` `e83fffd3a173506eb053d6bf57f2a787c5d68a375e26332407c0da3cc910193e`.

**Signatures.** `quartz` 2.5.1 and 2.5.2, jar and `-sources.jar`: good, key `7FCE178313EAC3BDFC4A75A95E1D8523FE7EAC7B` ("Terracotta Release
Engineer 2"), from keyserver.ubuntu.com with nothing further vouching for it (`$O/logs/sigs-C.txt`). The pin jars' dependencies come from
Gradle's resolution (no signature check).

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- Use `$O/artifacts/L12-quartz-{parent,fix}.jar` with `$O/artifacts/L12-quartz.runtime-classpath.txt`, plus Derby from the test classpath file
  for a JDBC store. Bytecode is Java 11.
- The landed test calls `storeTrigger`/`retrieveTrigger` on the job store; the public `Scheduler` path and the direct table readback of the brief
  were not run.
- 2.5.2 stands for the parent's logic (one unrelated line apart); nothing released has the fix.
- Upstream also has `PostgresJdbcStoreTest`, `MariaDBJdbcStoreTest` and `MSSQLJdbcStoreTest` (Testcontainers, in the same test folder); none was run.

### L13 · Apache Maven Shade Plugin #150 — service descriptors merged under the relocated name (pinned source build; release 3.4.0 = fix)

**Pins.** Parent `26b587384bb664daf59c30e72693ee1ae105fd71`, fix `ad2f6f8e7855860b69b950d14ca8ec627b099d6b`. Worktrees `$W/L13-maven-shade-plugin-parent`, `$W/L13-maven-shade-plugin-fix`. Squash commit with one parent = the brief's.
Changed production file: `src/main/java/org/apache/maven/plugins/shade/resource/ServicesResourceTransformer.java` (only). Changed test:
`ServiceResourceTransformerTest.java` (new `mergeRelocatedFiles`).

**Build facts.** Maven plugin `org.apache.maven.plugins:maven-shade-plugin` **3.3.1-SNAPSHOT** (parent `maven-plugins:37`), `javaVersion` 8, `mavenVersion` 3.1.1,
ASM 9.3. `pom.xml` identical at both pins. Built on **JDK 11.0.33** (`$J11`) with Maven 3.10.0, invoker ITs skipped (`-Dinvoker.skip`).

**Commands** (`$O/scripts/mvn_case.sh WT . TAG $J11 ServiceResourceTransformerTest [online] -Dinvoker.skip`, from the worktree root):
- online (first resolution, 34 s): `JAVA_HOME=$J11 MAVEN_OPTS=-Xmx1g $MVN -Daether.connector.basic.threads=1 $SK -Dtest=ServiceResourceTransformerTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -Dinvoker.skip package`
- **offline (checked, 6–7 s)**: the same with `-o`. `dependency:build-classpath` needed one more online run (plugin 3.3.0 of the parent POM), then works offline.

**Artifacts** (`$O/artifacts/`):

| File or class | Side | sha256 |
|---|---|---|
| `L13-maven-shade-plugin-parent.jar` | parent | `77ed7e875e7c678c5c9eaa87c3e4885e17be7e6052c2a4216a07d675018b6c48` |
| `org/apache/maven/plugins/shade/resource/ServicesResourceTransformer.class` | parent | `0b4b8173a519eb0b562165f59920b72bd9860d43962497435a78d5772a162c64` |
| `L13-maven-shade-plugin-fix.jar` | fix | `5ec4ef3965343b7b060e2d658cc8130f0ac76277478259f3b7c7a539d0b562ca` |
| `org/apache/maven/plugins/shade/resource/ServicesResourceTransformer.class` | fix | `5014986195348927dcc2f17598769def5a133fb16928d8077f59dfbcdc2db734` |

Classpaths (same at both pins): `$O/artifacts/L13-maven-shade-plugin-fix.runtime-classpath.txt` (16 entries; Maven's own APIs are `provided` and absent),
`...compile-classpath.txt` (33, with the provided Maven APIs, enough to load the transformer and `DefaultShader` on JDK 11), `...test-classpath.txt` (52).

**Landed tests** (upstream Maven build, JDK 11; logs `$O/logs/L13-*.log`):

| Run | Result |
|---|---|
| fix, its own test, online | 4 run, 0 failures, 0 errors, 0 skipped (34 s) |
| fix, offline | 4 run, 0 failures, 0 errors, 0 skipped (6 s) |
| parent, its own test, offline | 3 run, 0 failures, 0 errors, 0 skipped (7 s) |
| fix's test file on the parent, offline | 4 run, 0 failures, 1 errors, 0 skipped (7 s); failing: `ServiceResourceTransformerTest#mergeRelocatedFiles` |

On the parent `mergeRelocatedFiles` throws `java.util.zip.ZipException: duplicate entry: META-INF/services/borg.foo.something.another` from
`ServicesResourceTransformer.modifyOutputStream(ServicesResourceTransformer.java:125)`: the brief's duplicate-entry failure.

**Release side.** **3.4.0 = the fix**: all 42 main sources in 3.4.0-sources equal the fix tree's (only the generated `HelpMojo` is extra), and 3.4.0's
`ServicesResourceTransformer.java` differs from the parent's. **3.3.0 = the parent except `DefaultShader.java`** (3.3.0's `ServicesResourceTransformer.java`
equals the parent's; `DefaultShader` changed between 3.3.0 and the parent pin). The class digests of the releases' transformer:

| `maven-shade-plugin-3.3.0.jar` | release-3.3.0 | `918b898d4a7754161532dd088ee70bc711546191eb80cf44653b214b7bc1b0c3` |
| `org/apache/maven/plugins/shade/resource/ServicesResourceTransformer.class` | release-3.3.0 | `c6306fa23eed48a13ad063175813d9e5e3e9c6671d1ae6d4f09f0fbe51fdb0f9` |
| `maven-shade-plugin-3.4.0.jar` | release-3.4.0 | `4cb98a20dc202259ffb9044e3cc7ee843bf790078008c6d4352224da1b63b8de` |
| `org/apache/maven/plugins/shade/resource/ServicesResourceTransformer.class` | release-3.4.0 | `02a82eebedea92e6006fadd319439162bc6e03432d388fe0fcc9cf82aab64960` |

| Jar | sha256 |
|---|---|
| `$O/releases/L13-maven-shade-plugin-3.3.0/lib/maven-shade-plugin-3.3.0.jar` | `918b898d4a7754161532dd088ee70bc711546191eb80cf44653b214b7bc1b0c3` |
| `$O/releases/L13-maven-shade-plugin-3.4.0/lib/maven-shade-plugin-3.4.0.jar` | `4cb98a20dc202259ffb9044e3cc7ee843bf790078008c6d4352224da1b63b8de` |

(`$O/releases/L13-maven-shade-plugin-VERSION/`, strict checksums.)

**Signatures.** maven-shade-plugin 3.3.0 (signed 2022-03-24) and 3.4.0 (signed 2022-09-11): good signatures by `AE9E53FC28FF2AB1012273D0BF1518E0160788A2`
(Karl Heinz Marbaise, ASF key, in `https://downloads.apache.org/maven/KEYS`), a key that **expired on 2024-08-15**, after both signatures were made
(`EXPKEYSIG`). Keyring `$O/gnupg-B`.

**Jobs.** None.

**For the domain agent**
- The brief's scenario runs the shade goal in a Maven build: the fix side can be the released plugin **3.4.0** (source-equal to the fix); the parent side
  has no equal release, so it needs the built `$O/artifacts/L13-maven-shade-plugin-parent.jar` installed under some coordinates of the domain's choosing
  (both pins are `3.3.1-SNAPSHOT`). Nothing was installed.
- The fixture JARs A and B of the brief were not built.

### L14 · Apache Iceberg #12855 — GenericRecord copies binary and nested values (upstream Gradle 8.14 build at both pins, by job)

**Pins.** parent `4ca3f10832907540eee798236fa401eb07c7e7df` (tree `4563a5266de935e7de6405349c9a71f363d98b03`); fix `a7f3dc79a2f42a4875ac35eec2137ecff15204fc` (tree `95432fc9eea162e75c326a2d08eccbcab68e2039`) (squash, one parent = the brief's). **`$W/L14-iceberg-parent` and `$W/L14-iceberg-fix` are standalone
depth-1 clones** of the bare mirror (fetched from `refs/pins/ROLE-SHA`, HEAD detached), not linked worktrees, as for L05 and L19: the first job
(`20261125-161917-setup-build-iceberg-api-core-data-parque`) failed in the build's `:generateGitProperties` (gradle-git-properties, JGit): "No Git repository found" in a linked worktree,
whose `.git` is a file. In the clones `:generateGitProperties --offline` passed inline (6 s; log `$O/logs/L14-fix.gitprops-check.gradle-log.txt`).
The first attempt's logs are kept in `$O/logs/attempt-1/`.
Changed production file: `core/src/main/java/org/apache/iceberg/data/GenericRecord.java` (copy constructor copies `ByteBuffer` and nested
`Record` values). Changed tests (data module): `DeleteReadTests` (abstract base), `TestGenericReaderDeletes`, `TestGenericRecord`.

**Build facts.** Gradle 8.14 (wrapper `distributionSha256Sum` = published = `61ad310d3c7d3e5da131b76bbf22b5a4c0786e9d892dae8c1658d4b484de3caa`; the repository has no `gradle-wrapper.jar`, its `gradlew`
downloads one). The build accepts only JDK 11, 17 or 21 (it throws otherwise); JDK 17 (`$J17`) here. The project version comes from git
(palantir git-version): `a7f3dc7` at the fix, so jars are named `iceberg-core-a7f3dc7.jar`,
and the parent's `iceberg-core-4ca3f10.jar`. Modules for the brief: `iceberg-api`, `iceberg-common`, `iceberg-core`, `iceberg-data`,
`iceberg-parquet`, `iceberg-bundled-guava` (shadow). Hadoop is `compileOnly` in data and parquet; the data module's test runtime brings
`hadoop-client` 3.4.1, parquet 1.15.2, avro 1.12.0. Online resolution of those modules took 71 s inline (`$O/logs/L14-fix.resolve-online.log`).

**Commands** (`$G14` = `JAVA_HOME=$J17 choom -n 500 -- $O/tools/gradle-8.14/bin/gradle --no-daemon --no-scan --console=plain --max-workers=3
-Dorg.gradle.jvmargs=-Xmx2g -Porg.gradle.java.installations.auto-download=false`):
- jars and landed tests: `$G14 [--offline] --continue :iceberg-api:jar :iceberg-common:jar :iceberg-core:jar :iceberg-data:jar :iceberg-parquet:jar
  :iceberg-bundled-guava:shadowJar :iceberg-data:test --tests org.apache.iceberg.data.TestGenericRecord --tests org.apache.iceberg.data.TestGenericReaderDeletes`
- classpath export: `$G14 --offline -I $O/scripts/resolve-all.init.gradle :iceberg-data:setupWriteClasspath -PsetupCpConf=runtimeClasspath|testRuntimeClasspath
  -PsetupCpOut=FILE` (and `:iceberg-parquet:` with `runtimeClasspath`), then `$O/scripts/cp_export_D.py`.
The offline form is exercised by the job.

**Artifacts.** 

| File in `$O/artifacts/` | sha256 |
|---|---|
| `L14-iceberg-fix-iceberg-api-a7f3dc7-tests.jar` | `18f33d3cad8f2ca84d71cd8175629fe525d59ef13cea0a89fd197637767874f4` |
| `L14-iceberg-fix-iceberg-api-a7f3dc7.jar` | `87c5f3dc51a21de8f458a974ab023cb8e3ffff509598d063839a5dd93ff69833` |
| `L14-iceberg-fix-iceberg-bundled-guava-a7f3dc7.jar` | `f97a0050d713ce4a17374ffdd0f2e96ce6356cbb7a33cf3a4d9be07d0d226086` |
| `L14-iceberg-fix-iceberg-common-a7f3dc7.jar` | `2345a89380ecbb3e4ee4420905ac4780b32512056b5753cc34131558269866f4` |
| `L14-iceberg-fix-iceberg-core-a7f3dc7-tests.jar` | `a56d80454ae294c6083b751833516fcb4ec71c4424abd2a5fad8edabe9427cba` |
| `L14-iceberg-fix-iceberg-core-a7f3dc7.jar` | `49f052897d791dfe091e3d606dfa5eb8dca8f74b6019da8dc7a6d0e457321cbc` |
| `L14-iceberg-fix-iceberg-data-a7f3dc7.jar` | `7a66a462b62be68bbf00d946cd662d249c3df4bf2beab7fc579881d7694198b6` |
| `L14-iceberg-fix-iceberg-orc-a7f3dc7.jar` | `b96c68ab6ea2a05505eb47499cacf57ab5b46997892a231d1f31afa039d190a2` |
| `L14-iceberg-fix-iceberg-parquet-a7f3dc7.jar` | `569e60d6fcaed51bcf97e603881c540c83a9ef51fc7319941ae959c969caa29e` |
| `L14-iceberg-parent-iceberg-api-4ca3f10-tests.jar` | `c6f3b753ab851fcc49867198a6b7280dc4411eaa9179531fe957b688c6762974` |
| `L14-iceberg-parent-iceberg-api-4ca3f10.jar` | `de7f07450c5aa3d6d33947b478a01979369e32ceafa32fd54a3d4b4d1dd2fdf0` |
| `L14-iceberg-parent-iceberg-bundled-guava-4ca3f10.jar` | `f97a0050d713ce4a17374ffdd0f2e96ce6356cbb7a33cf3a4d9be07d0d226086` |
| `L14-iceberg-parent-iceberg-common-4ca3f10.jar` | `a72b09845aeb080549b841a4d615ba86bc81064a5e4c5a72520846a0fd53da5a` |
| `L14-iceberg-parent-iceberg-core-4ca3f10-tests.jar` | `303faa3073663d354f6f6cab007607ba71aef93db992e82294eb58629e288ea8` |
| `L14-iceberg-parent-iceberg-core-4ca3f10.jar` | `708ac1a9c90503b377f5d22fe95fe6ea0b92664528e40f5af071ddad270c6224` |
| `L14-iceberg-parent-iceberg-data-4ca3f10.jar` | `05cd384e26528ae48f9440f4bc4f40c3bc2f9b08d67103db3319066bcfb6201a` |
| `L14-iceberg-parent-iceberg-orc-4ca3f10.jar` | `08ad00334c790de86e75908b9d66a02f6e3622bf30f1fc397d67f0f5f200b32c` |
| `L14-iceberg-parent-iceberg-parquet-4ca3f10.jar` | `13acd918c4e07b87f685a0d142644921196e8e97c428a76ee8af980b52d2d363` |

Class digests (sha256 of each changed class, per side) are in `$O/artifacts/L14-*.class-digests.txt`; runtime classpaths in `$O/artifacts/L14-*-classpath.txt` (colon-separated; project jars point at the copies above).

Expected: each side's api, common, core, data, parquet and bundled-guava jars (`L14-iceberg-ROLE-iceberg-*-VERSION.jar`), three classpath files
`L14-iceberg-ROLE.{data-runtime,parquet-runtime,data-test-runtime}-classpath.txt` (the last includes hadoop-client and the api/core test jars),
and class digests of `GenericRecord`, `BaseDeleteLoader` and `ByteBuffers`.

**Landed tests.**

| Run | Result |
|---|---|
| fix, landed tests (first build, online) | junit tests=48 failures=0 errors=0 skipped=1 |
| fix, again offline | junit tests=48 failures=0 errors=0 skipped=1 |
| parent, its own tests (offline) | junit tests=39 failures=0 errors=0 skipped=1 |
| fix's test files on the parent (offline; expected to fail) | junit tests=48 failures=9 errors=0 skipped=1; junit failed TestGenericReaderDeletes#fileFormat = PARQUET; junit failed TestGenericReaderDeletes#fileFormat = AVRO; junit failed TestGenericReaderDeletes#fileFormat = ORC; junit failed TestGenericReaderDeletes#fileFormat = PARQUET; junit failed TestGenericReaderDeletes#fileFormat = PARQUET; junit failed TestGenericReaderDeletes#fileFormat = AVRO; junit failed TestGenericReaderDeletes#fileFormat = ORC; junit failed TestGenericReaderDeletes#fileFormat = PARQUET; junit failed TestGenericRecord#testDeepCopyValues() |

Run by job `20261125-165654-setup-build-iceberg-api-core-data-parque`; logs `$O/logs/L14-*.gradle-log.txt` and `*.junit.txt`.

**Release side.** `GenericRecord.java` in 1.9.0, 1.9.1 and 1.9.2 equals the **parent**'s; in **1.10.0** it equals the **fix**'s (byte-identical
sources; both releases differ from the pins elsewhere). Resolved with strict checksums, each with `org.apache.hadoop:hadoop-common:3.4.1` added
for Parquet writing: `$O/releases/L14-iceberg-1.9.2/` (parquet 1.15.2) and `$O/releases/L14-iceberg-1.10.0/` (parquet 1.16.0).

| File | sha256 |
|---|---|
| `upstream/L14-tags/GenericRecord-apache-iceberg-1.10.0.java` | `90d67aff93378226cd48847c8ff535bda8568e89d02b40dfbf2372df4a2dddd8` |
| `upstream/L14-tags/GenericRecord-apache-iceberg-1.9.0.java` | `84f9826bbf0c30b68bd51b911ebfad7fd2d807b89cbacb9d873dbe3c3f51248f` |
| `upstream/L14-tags/GenericRecord-apache-iceberg-1.9.1.java` | `84f9826bbf0c30b68bd51b911ebfad7fd2d807b89cbacb9d873dbe3c3f51248f` |
| `upstream/L14-tags/GenericRecord-apache-iceberg-1.9.2.java` | `84f9826bbf0c30b68bd51b911ebfad7fd2d807b89cbacb9d873dbe3c3f51248f` |
| `upstream/L14-tags/GenericRecord-fix.java` | `90d67aff93378226cd48847c8ff535bda8568e89d02b40dfbf2372df4a2dddd8` |
| `upstream/L14-tags/GenericRecord-parent.java` | `84f9826bbf0c30b68bd51b911ebfad7fd2d807b89cbacb9d873dbe3c3f51248f` |

**Signatures.** Keyring `$O/gnupg-D`, Iceberg KEYS (`$O/keys-D/iceberg-KEYS`, sha256 `cdfc93f1615de04fb441012ec1b712545a1123bf70098b75d0e0370bba4b6bde`).

| Jar (Maven Central) | sha256 | Signature | Signer key |
|---|---|---|---|
| `iceberg-api-1.9.2.jar` | `698ba4cc86f4a36357b46e1b2c5a45a34a855139408c8f6e672bca20f68a4ed5` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-common-1.9.2.jar` | `9213b3d34881f0c7fe6476d09fe0a116b3c590af076c29946bd505743a24129f` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-core-1.9.2.jar` | `a619c25332f477604e5ee9363a4df9202a86ea4580a865e882ad9e8bc62682d5` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-data-1.9.2.jar` | `36ed39583f3690057a7d03eb93436dbe69552fa3425b7d81de241646f7903116` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-parquet-1.9.2.jar` | `a0d388c7e7c24ace4be2a3eb9fc161ab469fcc62c21c1fa073129a0d58aa5ebb` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-bundled-guava-1.9.2.jar` | `c1545656a3e4b4ff17f53629cc357c5d25ada492dab7964ad4cfbc387417c39d` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-api-1.10.0.jar` | `627061d401dba9d1a8cada2da6394640c2e803102bb676fb34e5f65503cf2c51` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-common-1.10.0.jar` | `5ce6ec8262b4c6f8151d9e36ebe013bd23ec0f310508173f72c43bc073d5f519` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-core-1.10.0.jar` | `54091489dbdcb31b5a4514372abfc908a7b0be69f76e785f1e82279be4fbd6cc` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-data-1.10.0.jar` | `7f78b66e6df32650ac6fc091d1d1b8aa5dc2f3063e98ead8a132a1e0a05f3f62` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-parquet-1.10.0.jar` | `aa48161029ab589f94acfa026eb9474f265a53ed241df27507efdaf05d2bca90` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |
| `iceberg-bundled-guava-1.10.0.jar` | `05b79072e19071b1bcf7a4e382d624b3b2ccad6eaf79627676219bb48e4e834d` | good | `AEAE3953E54CB1C8C7D338BA0EB5DEF0AE3E299A` |

Transitive jars (hadoop, parquet, ...) rest on Maven's `--strict-checksums`.

**Jobs.** `20261125-165654-setup-build-iceberg-api-core-data-parque` (second attempt, on the clones); the first, `20261125-161917-setup-build-iceberg-api-core-data-parque`, failed as above.

**For the domain agent**
- Release pair by the changed class: 1.9.2 = parent, 1.10.0 = fix; the pin jars come from the job.
- A local table needs Hadoop on the classpath (`hadoop-common` in the release sets, `hadoop-client` in the data test runtime classpath).
- Run on JDK 11, 17 or 21; the build's test JVMs add many `--add-opens` (see `build.gradle` lines 57–79 at the pins).

### L15 · Gradle #21084 — named Groovy task actions in up-to-date checks (Gradle's own build at both pins on Gradle 7.5.1, by job; releases 7.5.1 and 7.6)

**Pins.** parent `fda88b3fb300707d2ec2d2839f94184dabf6852c` (tree `159860416c2d0bb6c6ab59061cd97e6b0800c9c7`); fix `9e244e0ace2e7698374f5199570e09295950683a` (tree `28d5173f9ed130d271141cf6ea50bf91af13a347`) (two-parent merge; first parent = the brief's). Worktrees `$W/L15-gradle-parent`, `$W/L15-gradle-fix`.
Changed production file: `subprojects/core/src/main/java/org/gradle/api/internal/AbstractTask.java` (4 lines: an action that is a
`ConfigureUtil.WrappedConfigureAction` is converted from its closure, so its implementation is fingerprinted). Changed test:
`subprojects/core/src/integTest/groovy/org/gradle/api/tasks/IncrementalBuildIntegrationTest.groovy` (new unrolled feature
"task is not up-to-date when the implementation of a named #actionMethodName action changes", doFirst and doLast). The PR's milestone is 7.6 RC1.

**Build facts.**
- The pins' wrapper names the nightly `gradle-7.6-20220513164305+0000-bin.zip`; it is **gone**: services.gradle.org redirects to
  downloads.gradle.org, which answers 404, and repo.gradle.org has no copy either. Its predecessor as the line's wrapper (2022-05-12) was 7.5-rc-1.
  **Substitution:** the job runs Gradle's build with the released **Gradle 7.5.1** (zip sha256 `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4` = published `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4`). Upstream
  build files are unchanged.
- **Substitution (one library, `org.openmbee.junit:junit-xml-parser:1.0.0`):** it is no longer on Maven Central or the Gradle Plugin Portal
  (it came from jcenter), and the build needs it twice. The first job (`20261125-161917-setup-build-gradle-distributions-at-both`) failed resolving it for the root project's
  build-script `:classpath` (root settings: Plugin Portal only). The second (`20261125-165654-setup-build-gradle-distributions-at-both`), whose init script added the repository to
  build-script repositories only, got past that and failed after 45 s resolving it for `:build-logic:performance-testing:compileClasspath`
  (`build-logic/settings.gradle.kts` resolves from Central and the Portal, and declares `https://repo.gradle.org/gradle/public` only for
  `classycle:classycle`). The init script `$O/scripts/gradle-L15-openmbee-substitute.init.gradle` now adds `https://repo.gradle.org/gradle/public`,
  for the group `org.openmbee.junit` only, to every build's settings repositories (`beforeSettings`, which also reaches the included builds
  `build-logic` and `build-logic-commons`) and to every project's build-script repositories. Inline check (26 s, online, fix worktree):
  `$G15 -p build-logic :performance-testing:dependencies --configuration compileClasspath` resolved `junit-xml-parser -> 1.0.0` and printed the
  script's line for both included builds (`$O/logs/L15-init-check.build-logic-deps.gradle-log.txt`). The jar fetched once from there
  (`$O/dl/L15-junit-xml-parser-check/junit-xml-parser-1.0.0.jar`) has sha256 `ef5da0d3135e27372039e8b0251b40b100c48b4f1308ab8cc43531b208620049`; the pins' `gradle/verification-metadata.xml` pin
  `ef5da0d3135e27372039e8b0251b40b100c48b4f1308ab8cc43531b208620049` (parent) and `ef5da0d3135e27372039e8b0251b40b100c48b4f1308ab8cc43531b208620049` (fix), and Gradle's strict dependency verification checks it again in the build.
  The earlier attempts' logs are kept in `$O/logs/attempt-1/` and `$O/logs/attempt-2/` (with the second attempt's init script).
- **Stopped: the pinned `org.ysb33r.gradle:grolifant:0.16.1` jar is not available.** With the extended init script the third job
  (`20261125-172547-setup-build-gradle-distributions-at-both`) got past `junit-xml-parser` (every included build printed the script's line) and compiled `build-logic-settings` and
  `build-logic-commons`, then every Gradle step failed in **Gradle's own strict dependency verification**: `grolifant-0.16.1.jar` "from
  repository MavenRepo" failed verification (for `:build-logic:cleanup:compileClasspath` on the fix, and `kotlinCompilerClasspath` and
  `:build-logic:binary-compatibility:compileClasspath` on the parent). Both pins' `gradle/verification-metadata.xml` pin
  `362c450c9738834181fdfac1147fa11cf21cefd59d7a5368756e174f93567a43` (parent) and `362c450c9738834181fdfac1147fa11cf21cefd59d7a5368756e174f93567a43` (fix) for it, with origin "Artifact is not signed". The only copy served
  today has sha256 `a867e911d060a240b8aa111896b7379282fe61940dfb949e72600f7ca67cb92f` (`$O/dl/L15-grolifant-check/grolifant-0.16.1.jar`): the Plugin Portal and jcenter both redirect to Maven
  Central and gave byte-identical files, and `repo.gradle.org/gradle/public` answers 404 (`$O/dl/L15-grolifant-check/README.txt`). Central's
  copy carries a signature made 2022-11-08 by key id `54AC8E2D98CFEAC6`, after both pins (June 2022), so it is a later publication of the
  same coordinates, not the file the pins verified; its signature was not checked, as it would not change the mismatch. **Setup stops here
  for L15:** building on would need `--dependency-verification lenient` (or `off`), or an edit to the pins' verification metadata, which
  accepts a jar the upstream build rejects. That is a decision for a person or the domain work, not a setup step, and was not taken.
- The build: version `7.6` (`version.txt`), `build-logic` in Kotlin, compile toolchain JDK 11, dependency verification `strict`
  (`gradle/verification-metadata.xml`), configuration cache on. Its settings apply `com.gradle.enterprise` 3.10.2 and the
  `gradle-enterprise-conventions-plugin` 0.7.6, which point build scans and a remote build cache at Gradle's servers: every run here uses
  **`--no-scan --no-build-cache`**, so nothing is sent there and every output is built locally. It reads git through the command line
  (`BuildEnvironment.kt` says JGit does not work with worktrees), so the linked worktree is fine.
- Own `GRADLE_USER_HOME`: `$O/gradle-home-L15` (so its size can be recorded and cleared alone).
- Nothing was built inline: compiling `build-logic` alone is several minutes, so the whole build is the job.
- The parent is built **in the fix's worktree**, detached at the parent (`git checkout --detach fda88b3fb300707d2ec2d2839f94184dabf6852c`), so its build is
  incremental over the fix's; the job returns the worktree to the fix at the end. `$W/L15-gradle-parent` stays for reading the source.

**Commands** (`$G15` = `GRADLE_USER_HOME=$O/gradle-home-L15 JAVA_HOME=$J11 choom -n 500 -- $O/tools/gradle-7.5.1/bin/gradle --no-daemon --no-scan --no-build-cache
--console=plain --max-workers=4 "-Dorg.gradle.jvmargs=-Xmx3g -XX:MaxMetaspaceSize=768m" -Porg.gradle.java.installations.auto-download=false
-Porg.gradle.java.installations.paths=$J8,$J11,$J17 -I $O/scripts/gradle-L15-openmbee-substitute.init.gradle`):
- distribution and landed test: `$G15 [--offline] --continue install -Pgradle_installPath=$O/tools/gradle-pin-L15-ROLE :core:embeddedIntegTest --tests org.gradle.api.tasks.IncrementalBuildIntegrationTest`

**Artifacts.** The job installs the two distributions at **`$O/tools/gradle-pin-L15-fix`** and **`$O/tools/gradle-pin-L15-parent`** (each
`bin/gradle` runnable; they stay) and writes `$O/artifacts/L15-gradle-ROLE-AbstractTask.class-digests.txt`; the job log prints each
`lib/gradle-core-7.6.jar` sha256. **Not built**: no job got past `build-logic` (see Stopped above); neither folder exists.

**Landed tests.**

| Run | Result |
|---|---|
| fix, landed tests (first build, online) | **not run**: build failed first (':build-logic:cleanup:compileKotlin'); junit tests=0 failures=0 errors=0 skipped=0 |
| fix, again offline | **not run**: build failed first (':build-logic:cleanup:compileKotlin'); junit tests=0 failures=0 errors=0 skipped=0 |
| parent, its own tests (offline) | **not run**: build failed first (':build-logic:cleanup:compileKotlin'); junit tests=0 failures=0 errors=0 skipped=0 |
| fix's test files on the parent (offline; expected to fail) | **not run**: build failed first (':build-logic:binary-compatibility:compileGroovy'); junit tests=0 failures=0 errors=0 skipped=0 |

Run by job `20261125-172547-setup-build-gradle-distributions-at-both`; logs `$O/logs/L15-*.gradle-log.txt` and `*.junit.txt`.

**Release side.** Neither release equals a side. `v7.6.0` contains the fix (GitHub compare: the fix is behind 7.6.0) and its `AbstractTask.java`
has the fix's lines plus later changes (onlyIf reasons, `ScriptOriginUtil`). `v7.5.0`/`v7.5.1` are on the release branch, which diverged
before the merge: their `AbstractTask.java` lacks the fix **and** an earlier parent-side change (`getActionImplementation(Object, ...)` passing
the action to `ImplementationSnapshot.of`). Distributions fetched and checked (sha256 = services.gradle.org's `.sha256`), unpacked in `$O/tools/`:

| Distribution | Where | zip sha256 (= published) |
|---|---|---|
| Gradle 7.5.1 (no fix; also the runner of the pin builds) | `$O/tools/gradle-7.5.1` | `f6b8596b10cce501591e92f229816aa4046424f3b24d771751b06779d58c8ec4` |
| Gradle 7.6 (has the fix, plus later changes) | `$O/tools/gradle-7.6` | `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` |

| File | sha256 |
|---|---|
| `upstream/L15-tags/AbstractTask-fix.java` | `55c13652f9e1e8f512431887f3d2f4cbb51477cc7b9d0414f1a1e3bf6fe3397c` |
| `upstream/L15-tags/AbstractTask-parent.java` | `9a333507862547a761748e83ed623593be26cbd6d1705f62f99701ed02e1d297` |
| `upstream/L15-tags/AbstractTask-v7.5.0.java` | `3ba1b9f4b374412e2112e2ae99764369ac54f8df3726da6b25cc0a1945923694` |
| `upstream/L15-tags/AbstractTask-v7.5.1.java` | `3ba1b9f4b374412e2112e2ae99764369ac54f8df3726da6b25cc0a1945923694` |
| `upstream/L15-tags/AbstractTask-v7.6.0.java` | `d1d9ebb939e2aeb3215dfd920dec79a79b18597398cd2ced2ce89f974caa2098` |

**Signatures.** Gradle distributions are checked by sha256 only (no signatures). The pins' `gradle-wrapper.jar` (sha256 `b95314dbc8c92954d14d1b8e8c14eab50e7a599468fbb2e9fae81ec1f4fafc0a`) is not
in Gradle's published list of wrapper checksums (`wrapper-checksums.json`, sha256 `c5deb57f25df459bdd954a08338c685caf08b05b302afcd1fefd21c77c70f927`; releases only) and was not used.

**Jobs.** Three attempts, all failed before any test ran: `20261125-161917-setup-build-gradle-distributions-at-both` after 2m42s and `20261125-165654-setup-build-gradle-distributions-at-both` after 1m17s (both on
`junit-xml-parser`), and `20261125-172547-setup-build-gradle-distributions-at-both` (third, with the extended init script) after 1m43s on `grolifant` (4 Gradle steps exited 1; the
cleanup step passed). Logs: `$O/logs/attempt-1/`, `$O/logs/attempt-2/`, and the third's in `$O/logs/L15-*`. Not resubmitted.

**For the domain agent**
- **At setup completion, no pin distribution existed.** The later domain run recovered the checksum-matching artifact and verified it offline using both original Gradle policies. Its full-distribution job uses the recovered bytes. [Strict resolution and reproductions](../../examples/437-gradle-named-actions/README.md)
- The brief's scenario runs a Gradle distribution; the pins' own build stopped on `grolifant` during setup (above). What was
  ready: both pins' sources (worktrees), the released 7.5.1 (no fix) and 7.6 (fix plus later changes) distributions, which are only
  approximate sides, and `$O/gradle-home-L15` with everything resolved up to `build-logic`.
- Setup left the later Central JAR unused. The domain run’s checksum-matching JCenter copy preserves strict dependency verification.
- If they are built, they are built by Gradle 7.5.1, not the gone nightly, from the pins' sources.
- Use a fresh project dir and `--no-build-cache` per the brief; the daemon of each distribution keeps its own state under the `GRADLE_USER_HOME` you choose.

### L16 · Guava #7277 — allAsList reads a completed input without a listener (pinned source build, JRE and Android, by job)

**Pins.** Parent `8c31d52687cf03346635e29b3c5529e183c3f6ee`, fix `dc80e7e9f3844381aacc93ee1e043a711f1feffb`. Worktrees `$W/L16-guava-parent`, `$W/L16-guava-fix`. Squash commit with one parent = the brief's.
Changed: `guava/src/com/google/common/util/concurrent/AggregateFuture.java` and `android/guava/src/com/google/common/util/concurrent/AggregateFuture.java`
(+35/−24 each). **The PR adds no tests.** Every `*.xml` build file is identical at both pins.

**Build facts.** Maven, `guava-parent` **HEAD-jre-SNAPSHOT** (Android: `HEAD-android-SNAPSHOT`), bytecode 1.8; modules `guava`, `guava-testlib`,
`guava-tests` (and `guava-bom`, `guava-gwt`). At these pins there is **no toolchains plugin** (unlike later Guava, M20 of the earlier setup), but the job still
redirects `user.home` into `$O/mvnhome`. CI tests on JDK 8, 11, 17, 21; the job builds on **JDK 21** (`$J21`) with Maven 3.10.0 (the wrapper names 3.9.6).
`FuturesTest` (in `guava-tests`) is the existing test of `allAsList`, ordering and cancellation.

**Commands** (from the worktree, or its `android/`): `JAVA_HOME=$J21 MAVEN_OPTS='-Xmx2g -Duser.home='$O/mvnhome $MVN [-o | -Daether.connector.basic.threads=1] -Dmaven.javadoc.skip=true -Danimal.sniffer.skip=true -Dmaven.source.skip=true -Dtest=FuturesTest -Dsurefire.failIfNoSpecifiedTests=false -DfailIfNoTests=false -pl guava-tests -am package`
(compiling guava-testlib and guava-tests takes minutes: job).

**Jars** (copied by the job to `$O/artifacts/L16-guava-ROLE-FLAVOUR.jar`, with the digests of the `AggregateFuture*` classes):

| File or class | Side | sha256 |
|---|---|---|
| `L16-guava-parent-jre.jar` | parent-jre | `756a806f3d005d31395f6979fbe95ffa8631e6f5ac6d0ff7fd4374080e6882dc` |
| `com/google/common/util/concurrent/AggregateFuture$ReleaseResourcesReason.class` | parent-jre | `d045d53010e76c8a1eeaa929eb183783621881c6855966c729a29703b9673225` |
| `com/google/common/util/concurrent/AggregateFuture.class` | parent-jre | `84fee5ddc908efb74f785c2fcc608cf99e47f9276c594e7936cb3f9144bde26d` |
| `com/google/common/util/concurrent/AggregateFutureState$1.class` | parent-jre | `e878737e7f7ff9e735f3da01fdde564fb69ba151fb49da9e03b44729d272e777` |
| `com/google/common/util/concurrent/AggregateFutureState$AtomicHelper.class` | parent-jre | `8ad8f4c1c5a4ea4a1e2a1e3746d1ec701a0b3dbb8b35dd0621b81ed325b53f8c` |
| `com/google/common/util/concurrent/AggregateFutureState$SafeAtomicHelper.class` | parent-jre | `b3af620171a6da7939e2d4ea734c030d8c286f292728aa7fcb201ac00c08d3e5` |
| `com/google/common/util/concurrent/AggregateFutureState$SynchronizedAtomicHelper.class` | parent-jre | `645a877e8e82b0893910c6af736ab6ca91e53efada89e395a6c617ee9790a2b5` |
| `com/google/common/util/concurrent/AggregateFutureState.class` | parent-jre | `6754e59e357ed16481d6dbebcb6a0b51b364d03cef3088221171db6c00096e63` |
| `L16-guava-parent-android.jar` | parent-android | `96a53acef6570cb4d309ad5c626a4ae89de280405ad467a1081ac28477be210d` |
| `com/google/common/util/concurrent/AggregateFuture$ReleaseResourcesReason.class` | parent-android | `d045d53010e76c8a1eeaa929eb183783621881c6855966c729a29703b9673225` |
| `com/google/common/util/concurrent/AggregateFuture.class` | parent-android | `84fee5ddc908efb74f785c2fcc608cf99e47f9276c594e7936cb3f9144bde26d` |
| `com/google/common/util/concurrent/AggregateFutureState$1.class` | parent-android | `e878737e7f7ff9e735f3da01fdde564fb69ba151fb49da9e03b44729d272e777` |
| `com/google/common/util/concurrent/AggregateFutureState$AtomicHelper.class` | parent-android | `8ad8f4c1c5a4ea4a1e2a1e3746d1ec701a0b3dbb8b35dd0621b81ed325b53f8c` |
| `com/google/common/util/concurrent/AggregateFutureState$SafeAtomicHelper.class` | parent-android | `b3af620171a6da7939e2d4ea734c030d8c286f292728aa7fcb201ac00c08d3e5` |
| `com/google/common/util/concurrent/AggregateFutureState$SynchronizedAtomicHelper.class` | parent-android | `645a877e8e82b0893910c6af736ab6ca91e53efada89e395a6c617ee9790a2b5` |
| `com/google/common/util/concurrent/AggregateFutureState.class` | parent-android | `6754e59e357ed16481d6dbebcb6a0b51b364d03cef3088221171db6c00096e63` |
| `L16-guava-fix-jre.jar` | fix-jre | `d76cfec9ff5de1d4847d2acdb6a16134b0ec1fc791653c50e405724b71bfc075` |
| `com/google/common/util/concurrent/AggregateFuture$ReleaseResourcesReason.class` | fix-jre | `c791aa816bd896d715e4553a8b19c471fec347c24e4617553c745a2a682babb1` |
| `com/google/common/util/concurrent/AggregateFuture.class` | fix-jre | `0b935258c913e94befef889ee39639adeb6c8aef636dc81c0b19078eb1b5d306` |
| `com/google/common/util/concurrent/AggregateFutureState$1.class` | fix-jre | `e878737e7f7ff9e735f3da01fdde564fb69ba151fb49da9e03b44729d272e777` |
| `com/google/common/util/concurrent/AggregateFutureState$AtomicHelper.class` | fix-jre | `8ad8f4c1c5a4ea4a1e2a1e3746d1ec701a0b3dbb8b35dd0621b81ed325b53f8c` |
| `com/google/common/util/concurrent/AggregateFutureState$SafeAtomicHelper.class` | fix-jre | `b3af620171a6da7939e2d4ea734c030d8c286f292728aa7fcb201ac00c08d3e5` |
| `com/google/common/util/concurrent/AggregateFutureState$SynchronizedAtomicHelper.class` | fix-jre | `645a877e8e82b0893910c6af736ab6ca91e53efada89e395a6c617ee9790a2b5` |
| `com/google/common/util/concurrent/AggregateFutureState.class` | fix-jre | `6754e59e357ed16481d6dbebcb6a0b51b364d03cef3088221171db6c00096e63` |
| `L16-guava-fix-android.jar` | fix-android | `bb2558a1dc6ef991dba235325a67a02060d8078e746e821a5c31f59108bb72e8` |
| `com/google/common/util/concurrent/AggregateFuture$ReleaseResourcesReason.class` | fix-android | `c791aa816bd896d715e4553a8b19c471fec347c24e4617553c745a2a682babb1` |
| `com/google/common/util/concurrent/AggregateFuture.class` | fix-android | `0b935258c913e94befef889ee39639adeb6c8aef636dc81c0b19078eb1b5d306` |
| `com/google/common/util/concurrent/AggregateFutureState$1.class` | fix-android | `e878737e7f7ff9e735f3da01fdde564fb69ba151fb49da9e03b44729d272e777` |
| `com/google/common/util/concurrent/AggregateFutureState$AtomicHelper.class` | fix-android | `8ad8f4c1c5a4ea4a1e2a1e3746d1ec701a0b3dbb8b35dd0621b81ed325b53f8c` |
| `com/google/common/util/concurrent/AggregateFutureState$SafeAtomicHelper.class` | fix-android | `b3af620171a6da7939e2d4ea734c030d8c286f292728aa7fcb201ac00c08d3e5` |
| `com/google/common/util/concurrent/AggregateFutureState$SynchronizedAtomicHelper.class` | fix-android | `645a877e8e82b0893910c6af736ab6ca91e53efada89e395a6c617ee9790a2b5` |
| `com/google/common/util/concurrent/AggregateFutureState.class` | fix-android | `6754e59e357ed16481d6dbebcb6a0b51b364d03cef3088221171db6c00096e63` |

**Tests** (job; logs `$O/logs/L16-*.log`):

| Run | Result |
|---|---|
| fix JRE, `FuturesTest`, online | 160 run, 0 failures, 0 errors, 0 skipped (46 s) |
| fix Android, online | 160 run, 0 failures, 0 errors, 0 skipped (32 s) |
| parent JRE, offline | 160 run, 0 failures, 0 errors, 0 skipped (32 s) |
| parent Android, offline | 160 run, 0 failures, 0 errors, 0 skipped (34 s) |
| fix JRE again, offline | 160 run, 0 failures, 0 errors, 0 skipped (19 s) |

**Release side.** **33.3.0-jre and 33.3.0-android carry the fix's `AggregateFuture.java`** (byte-equal), among 62 other changed files in the JRE flavour.
**33.2.1-jre's `AggregateFuture.java` = the parent's minus one `@SuppressWarnings("ShortCircuitBoolean")` annotation** (no code difference); 33.2.1-android's
differs from the parent's Android file as well. No release equals either pin as a whole. Resolved with strict checksums (`$O/releases/L16-guava-VERSION/`):

| Jar | sha256 |
|---|---|
| `$O/releases/L16-guava-33.2.1-jre/lib/guava-33.2.1-jre.jar` | `452b2d9787b7d366fa8cf5ed9a1c40404542d05effa7a598da03bbbbb76d9f31` |
| `$O/releases/L16-guava-33.2.1-android/lib/guava-33.2.1-android.jar` | `6b55fbe6ffee621454c03df7bea720d189789e136391a524e29506ff40654180` |
| `$O/releases/L16-guava-33.3.0-jre/lib/guava-33.3.0-jre.jar` | `dfadc3bce3101eff1452aae47d7c833fee443b47bdf9ef13311b6c7cab663ddf` |
| `$O/releases/L16-guava-33.3.0-android/lib/guava-33.3.0-android.jar` | `710ece381387ba3e24b4d97155653de35ef82220a3f6690d06cc8a6a3c5a6085` |

**Signatures.** guava 33.2.1 and 33.3.0, JRE and Android: good, key `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (Christopher Povirk), from keyserver.ubuntu.com.

**Jobs.** `20261125-162448-setup-build-guava-7277-s-two-revisions-j` (`$O/scripts/submit_B.py l16`).

**For the domain agent**
- No landed test exists; `FuturesTest` passing on both sides is the only upstream check, and it does not count listener registrations.
- The JRE and Android changes are identical in shape; the brief names the JRE module.

### L17 · iCal4j #947 — removing a zoned occurrence with a UTC exception date (upstream Gradle 8.5 build at both pins, inline)

**Pins.** Parent `a0ba59c562e38ee4e0839069b58b1fec27d1e673`, fix `5e2c93fce7835ad9c951a4e6e6d4469464d63805` (a two-parent merge into `develop`; first parent = the brief's before pin).
Worktrees `$W/L17-ical4j-parent`, `$W/L17-ical4j-fix`. Changed production file: `src/main/java/net/fortuna/ical4j/model/RecurrenceSet.java`
(+2/−1: `removeIf(r -> exceptionDates.contains(r.getStart()))` becomes a `TemporalComparator.INSTANCE.compare(...) == 0` match).
Test: `src/test/java/net/fortuna/ical4j/model/component/VEventTest.java` (+16; new `testCalculateRecurrenceSetWithUtcExDate`).

**Build facts.** As the earlier setup's M10 (same repository): Gradle 8.5 (`$O/tools/gradle-8.5`, zip checked); the repository's
`gradle-wrapper.jar` `76805e32c009c0cf0dd5d206bddc9fb22ea42e84db904b764f3047de095493f3` (both pins) is services.gradle.org's wrapper jar for
Gradle 9.1.0, not 8.5's, and is not used. **JDK 17** (`$J17`): Error Prone (NullAway) on `compileJava` needs 17+; bytecode targets Java 11.
The `axion-release` plugin takes the version from git tags, which the shallow worktrees lack, so the jar is `ical4j-0.1.0-SNAPSHOT.jar`.
Tests on the JUnit Platform (Spock/Groovy 3 and JUnit Jupiter). Repositories: `mavenLocal()`, Central, Plugin Portal; nothing was missing.

Commands (online once, 64 s; offline 7–25 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/env.sh
$O/scripts/gradle_case_C.sh L17-ical4j-fix 8.5 $J17 L17-ical4j-fix.test-offline build/test-results/test \
  --offline jar test --tests net.fortuna.ical4j.model.component.VEventTest     # or L17-ical4j-parent
```

**Artifacts** (built offline from each pin; bind the class digest):

| File | sha256 |
|---|---|
| `$O/artifacts/L17-ical4j-parent.jar` | `e5eb0b38d482f939a60751673ae47b56853ec0b8b1e545a6a4f55e7febdce62c` |
| `$O/artifacts/L17-ical4j-fix.jar` | `3a3ba9a8f4fe34b36001f4426632542e44ec8ae1a6111e4fa35a967ddcc56623` |

| Class | parent | fix |
|---|---|---|
| `net/fortuna/ical4j/model/RecurrenceSet$Builder.class` | `fd74926fd175f58c199bbaa8e060c6733b4a6856b64867e10692f4922fc93188` | `422998a70ec9bb94f6f615b572f76c66e38b1b32e77c5e712345887f7dda5df3` |

It is the only class that differs (646 classes each side; `$O/logs/L17-classdiff.md`).

**Runtime classpath** (`runtimeClasspath`, the same at both pins): `$O/artifacts/L17-ical4j.runtime-classpath.txt` (one line, `:`-separated;
the jars are in `$O/gradle-home`), digests `$O/artifacts/L17-ical4j.runtime-classpath.sha256`:
slf4j-api-2.0.12.jar commons-codec-1.17.0.jar commons-lang3-3.18.0.jar threeten-extra-1.8.0.jar caffeine-3.1.8.jar jparsec-3.1.jar groovy-3.0.25.jar checker-qual-3.37.0.jar error_prone_annotations-2.21.1.jar 

**Landed test** (JDK 17.0.21, host locale and default time zone; logs `$O/logs/L17-ical4j-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `VEventTest` (online, then offline) | tests=20 failures=0 errors=0 skipped=0; offline: tests=20 failures=0 errors=0 skipped=0 |
| parent, its own `VEventTest` (offline) | tests=19 failures=0 errors=0 skipped=0 |
| fix's `VEventTest.java` copied onto the parent (offline, restored after) | **tests=20 failures=1 errors=0 skipped=0**: `testCalculateRecurrenceSetWithUtcExDate`, `AssertionFailedError` at `VEventTest.java:374`: expected `[20240101T090000/PT1H, 20240103T090000/PT1H]`, was `[20240101T090000/PT1H, 20240102T090000/PT1H, 20240103T090000/PT1H]` |

**Release side.** Central's newest ical4j is 4.4.0 (metadata last updated 2026-10-02, before the merge on 2026-11-03); `$O/releases/ical4j-4.4.0`
(strict checksums), `ical4j-4.4.0.jar` `f4cac5c4a16d8c0f2228ad0e3221b90d069ae0efea73402b51888468e86405f9`. Its `RecurrenceSet.java` (`6d9feaca62a5c73fdc776b3cd43b61ce22f6b8095a57125cdabcf6a395ebe61d`) equals neither pin: it
has the parent's exception-date line (`exceptionDates.contains(r.getStart())`), but the parent has later changes elsewhere in the builder
(bounds filtering, date-only periods; 71 diff lines). Its `TemporalComparator.java` equals both pins'. **No release carries the fix**, and 4.4.0
is older than the parent.

**Signatures.** `ical4j-4.4.0` jar and `-sources.jar`: good, key `44C9BD32E7CB72F36F49DD0716968D251E760606` (Ben Fortuna), from keyserver.ubuntu.com
via the earlier setup's saved copy, nothing further vouching for it (`$O/logs/sigs-C.txt`).

**Jobs.** None: every run took about a minute or less inline.

**For the domain agent**
- Use `$O/artifacts/L17-ical4j-{parent,fix}.jar` with `$O/artifacts/L17-ical4j.runtime-classpath.txt`; the brief's March daylight-saving history
  was not run.
- The landed test passed under the host's default time zone; it builds its zoned `DTSTART` with an explicit zone.

### L18 · RxJava #6895 — a cancelled group with unread items restores upstream demand (upstream Gradle 6.0.1 build at both pins, inline; one init script for jcenter-only plugin dependencies)

**Pins.** Parent `f1a795da0d4cdfb3133206ad8e3887bdb8ba948b`, fix `5f6aafcbaa97f330ad2007f4ad02c5e33db8914b` (squash on `3.x`, one parent = the brief's).
Worktrees `$W/L18-RxJava-parent`, `$W/L18-RxJava-fix`. Changed production file:
`src/main/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy.java` (+1). Test:
`src/test/java/io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupByTest.java` (+34; new `cancelledGroupResumesRequesting`).

**Build facts.** Gradle 6.0.1 (`$O/tools/gradle-6.0.1`, zip checked). The repository's `gradle-wrapper.jar`
`3dc39ad650d40f6c029bd8ff605c6d95865d657dbfdeacdb079db0ddfffedf9f` (both pins) equals services.gradle.org's published wrapper jar for 5.6.x
(`$O/dl/gradle-C/gradle-5.6.4-wrapper.jar.sha256`), not 6.0.1's; it is not used. **JDK 8** (`$J8`, as the project's CI of the time);
`sourceCompatibility`/`targetCompatibility` 1.8. Version `3.0.0-SNAPSHOT` (`gradle.properties` `release.version`), so the jar is
`rxjava-3.0.0-SNAPSHOT.jar`. Runtime dependency: `org.reactivestreams:reactive-streams:1.0.3` only. Tests: JUnit 4.13, `maxHeapSize = "1200m"`;
without the `CI` environment variable the build forks `availableProcessors/2` test JVMs, so the commands set `CI=true` (one fork).

**Substitution (build-script classpath only).** The build script's repositories are `jcenter()`, Central and the Plugin Portal.
jcenter.bintray.com no longer serves four build-script dependencies of the publishing plugins (`gradle-bintray-plugin:1.8.4`,
`build-info-extractor-gradle:4.13.0`), and Central has none of them. The setup put the **same coordinates** in the file repository
`$O/dl/l18-substitute-repo`: `http-builder:0.7.2` copied from the earlier setup's checked copy (M13), the three JFrog modules from JFrog's
public jcenter mirror `https://releases.jfrog.io/artifactory/jcenter` (`$O/scripts/l18_add_module.sh`), each pom and jar checked against the
serving repository's `.sha1` (log `$O/logs/L18-substitute-repo.txt`). `$O/scripts/rxjava3-jcenter-substitute.init.gradle` adds that
repository to the build-script repositories; the upstream build files are unchanged. A second source for the three 2.15.0 jars was looked for at
`releases.jfrog.io/artifactory/oss-release-local` and not found there. None of these modules is in the built jar or its runtime classpath.

| Module | jar SHA-1 (= the serving repository's `.sha1`) | jar sha256 |
|---|---|---|
| `org.codehaus.groovy.modules.http-builder:http-builder:0.7.2` | `323092cd786480311c1cf693770f9e6fc20a8bef` | `cbd0fa43ebc62cb548e17f78b92b745220d9b1904f255c5916ef5a592b11e090` |
| `org.jfrog.buildinfo:build-info-extractor:2.15.0` | `a8a12a807a7ea0b32b2688a952cd954863e1e38d` | `8805dd467775566641202b5f4396265190df06d8f2aeb1f9234eeae7bbfd5b5b` |
| `org.jfrog.buildinfo:build-info-client:2.15.0` | `c207059a39948cec76c46410aedb2a43f2da908b` | `7f8151387f6a16b97cb12f1ff485c79360dec2f4ac18cf666f8356a06efb15ca` |
| `org.jfrog.buildinfo:build-info-api:2.15.0` | `08f87bfe44ee69af5e7d6c56379ac770d224f49d` | `67d7f8889293df6088a0719217bb7f34ca77badb1b7376e396d3c0ebd8adb09b` |

Commands (online once, 36 s; offline 13–31 s):

```bash
source ~/.cache/in-the-loop/merged-pr-links-l01-l20/scripts/env.sh; export CI=true
$O/scripts/gradle_case_C.sh L18-RxJava-fix 6.0.1 $J8 L18-RxJava-fix.test-offline build/test-results/test --offline \
  -I $O/scripts/rxjava3-jcenter-substitute.init.gradle jar test \
  --tests io.reactivex.rxjava3.internal.operators.flowable.FlowableGroupByTest       # or L18-RxJava-parent
```

**Artifacts** (built offline from each pin; bind the class digest):

| File | sha256 |
|---|---|
| `$O/artifacts/L18-RxJava-parent.jar` | `46ddd698ed1875a951a4d8dff54a3403a491f0e30161b17731279cc3c2d7ed44` |
| `$O/artifacts/L18-RxJava-fix.jar` | `72b7b91f828f7cf8cd833dc81ec30c28ee2f62e3d9830444de9b319cb3a4bd84` |
| `reactive-streams-1.0.3.jar` (runtime dependency) | `1dee0481072d19c929b623e155e14d2f6085dc011529a0a0dbefc84cf571d865` |

| Class | parent | fix |
|---|---|---|
| `io/reactivex/rxjava3/internal/operators/flowable/FlowableGroupBy$State.class` | `7c0b21d59b8650888f2200214bdcb8b9d66a61be541f438932e05ce5fb5a3dbd` | `c6a8281b500525bed147e905649f347c016d252088b32927f4f49e854a47cfd0` |

It is the only class that differs (1741 classes each side; `$O/logs/L18-classdiff.md`).

**Runtime classpath:** `$O/artifacts/L18-RxJava.runtime-classpath.txt` (reactive-streams 1.0.3 in `$O/gradle-home`), the same at both pins.

**Landed test** (JDK 8u512, `CI=true`; logs `$O/logs/L18-RxJava-*.log`, summaries `*.junit.txt`):

| Run | Result |
|---|---|
| fix, `FlowableGroupByTest` (online, then offline) | tests=67 failures=0 errors=0 skipped=1; offline: tests=67 failures=0 errors=0 skipped=1 |
| parent, its own `FlowableGroupByTest` (offline) | tests=66 failures=0 errors=0 skipped=1 |
| fix's test file copied onto the parent (offline, restored after) | **tests=67 failures=1 errors=0 skipped=1**: `cancelledGroupResumesRequesting`, `java.lang.IndexOutOfBoundsException: Index: 0, Size: 0` from `ArrayList.remove` at `FlowableGroupByTest.java:2476` (the test subscribes each new group with zero demand and cancels the oldest until the source of 1000 completes; on the parent the source stalls with no group left to cancel, so the list is empty) |

The skipped test is `announce`, skipped by the class itself.

**Release side** (`$O/releases/rxjava-3.0.0-RC8`, `-RC9`, `-3.0.0`, strict checksums; `FlowableGroupBy.java` compared byte for byte):
- **3.0.0-RC8 = parent**: `rxjava-3.0.0-RC8.jar` `d68d3d2986d4ddc412f6b21fe36742bf5fb379a137364ddf557f8459e554fc14`.
- **3.0.0-RC9 = fix**: `rxjava-3.0.0-RC9.jar` `92bd6bb1a2a8c2e4fb95999a803f7130b08adb70c7ded88c7b9151c236aff258`; **3.0.0** also has the fix's file:
  `rxjava-3.0.0.jar` `dd1eebeb292ddc40429e5b3e72f6a61facbec21ad5493f9f54ffb2bdf254bf57`.
- Only the changed file was compared; the releases differ from the pins elsewhere.

**Signatures.** Not verifiable, as in the earlier setup's M13: the RxJava jars (RC8, RC9, 3.0.0, jar and `-sources.jar`) are signed by key id
`94B291AEF984A085` (fingerprint `1D9AA7F9E1E2824728B8CD1794B291AEF984A085`), for which keyserver.ubuntu.com has only a 2021 revocation ("key
compromised"). `reactive-streams-1.0.3` is signed by subkey `1364C5E2DF3E99C5`, which the key published on keyserver.ubuntu.com
(`E83AABBB95CA37431E20422043203BE58F49479D`, Viktor Klang) marks encryption-only, so GnuPG cannot check it. These jars rest on Central's
checksums (strict-checksum resolution) alone (`$O/logs/sigs-C.txt`).

**Jobs.** None: every run took under a minute inline.

**For the domain agent**
- Use `$O/artifacts/L18-RxJava-{parent,fix}.jar` with reactive-streams 1.0.3; or the releases 3.0.0-RC8 (parent side) and 3.0.0-RC9 (fix side).
- The landed test counts the source's emissions (`doOnNext`) while cancelling zero-demand groups of a single key; the brief's two-key traces were not run.

### L19 · Apache Kafka #6654 — session window expiry and final-result suppression (upstream Gradle 5.4.1 build at both pins, by job; releases 2.2.0 / 2.2.1)

**Pins.** parent `a4f7675db1a928e73c7a69eb906dd1e9ecd4a22a` (tree `159cc5a0b5b2548c0f6a2d266248ce39819c3fd5`); fix `eab855541a4b776b150a849cecda9c758598cdca` (tree `833782f6d35b5f0a37e156e517fb896b1b35ead4`) (squash, one parent = the brief's). **`$W/L19-kafka-parent` and `$W/L19-kafka-fix` are standalone
depth-1 clones** (from the bare mirror), not linked worktrees: the build applies grgit (JGit), which fails in a linked worktree with
"Bare Repository has neither a working tree, nor an index". Their HEADs: parent `a4f7675db1a928e73c7a69eb906dd1e9ecd4a22a`, fix `eab855541a4b776b150a849cecda9c758598cdca`.
Changed production files: `streams/.../kstream/internals/KStreamSessionWindowAggregate.java` and `.../kstream/internals/graph/GraphGraceSearchUtil.java`.
Changed tests: `KStreamSessionWindowAggregateProcessorTest`, `SuppressScenarioTest`, `graph/GraphGraceSearchUtilTest`.

**Build facts.** No wrapper in the repository (`wrapper.gradle` generates one); `gradle/dependencies.gradle` names **Gradle 5.4.1**
(zip sha256 `7bdbad1e4f54f13c8a78abc00c26d44dd8709d4aedb704d913fb1bb78ac025dc` = published `7bdbad1e4f54f13c8a78abc00c26d44dd8709d4aedb704d913fb1bb78ac025dc`). Version `2.3.0-SNAPSHOT`, Scala 2.12.8, **JDK 8** (`$J8`). The streams tests compile against
`:core` and its Scala test classes, so a test run compiles core (the reason it is a job).
**Substitution (build-script classpath only):** `org.ajoberstar.grgit:grgit-core:3.1.1` was only on jcenter; Central, the Plugin Portal and
the build's other repositories don't have it. The setup copied the same coordinates from `https://repo.grails.org/grails/core` into the file
repository `$O/dl/L19-substitute-repo` (`$O/scripts/add_module_D.sh`, log `$O/logs/L19-substitute-repo.txt`), each file's SHA-1 equal to
that repository's `.sha1`; no second source was found. `$O/scripts/kafka-jcenter-substitute.init.gradle` adds it to the build-script repositories.

| Module file | SHA-1 (= grails' `.sha1`) | sha256 |
|---|---|---|
| `org.ajoberstar.grgit:grgit-core:3.1.1` pom | `be6525ed35eb24ef6c186923af157556cd3ad9f9` | `fbd24391c06b3a1ccee66e8aba1dcae591a3425c6e9d326f1368f63572c6fadf` |
| `org.ajoberstar.grgit:grgit-core:3.1.1` jar | `454bd8e8ec492590bd900bcc3999697764eece1f` | `dcf13e4c8e4bac27c152b71c7335d61dd204744ca3ee4bb457baac8aecb6692f` |

Online resolution of clients, core, streams, streams:test-utils, connect:json and connect:api took 20 s inline
(`$O/logs/L19-fix.resolve-online.log`); an offline `:connect:api:setupWriteClasspath` (which built `kafka-clients`) took 10 s.

**Commands** (`$G19` = `JAVA_HOME=$J8 choom -n 500 -- $O/tools/gradle-5.4.1/bin/gradle --no-daemon --console=plain --max-workers=3
-Dorg.gradle.jvmargs=-Xmx2g -PmaxParallelForks=1 -I $O/scripts/kafka-jcenter-substitute.init.gradle`):
- jars and landed tests: `$G19 [--offline] --continue :streams:jar :streams:test-utils:jar :streams:test --tests org.apache.kafka.streams.kstream.internals.KStreamSessionWindowAggregateProcessorTest
  --tests org.apache.kafka.streams.kstream.internals.SuppressScenarioTest --tests org.apache.kafka.streams.kstream.internals.graph.GraphGraceSearchUtilTest`
- classpath export: `$G19 --offline -I $O/scripts/resolve-all.init.gradle :streams:test-utils:setupWriteClasspath -PsetupCpOut=FILE`, then `cp_export_D.py`.
Offline was checked inline for the small export above; the job runs the rest offline.

**Artifacts.** 

| File in `$O/artifacts/` | sha256 |
|---|---|
| `L19-kafka-fix-connect-api-2.3.0-SNAPSHOT.jar` | `5632a6a2a15a2a74c52299ad427c13902de3af8b8c317d28a21c457dee27d1a9` |
| `L19-kafka-fix-connect-json-2.3.0-SNAPSHOT.jar` | `f7a1a2806156e34a3581f93a8e942a1d48e20c078e1a4762e4437d1860593664` |
| `L19-kafka-fix-kafka-clients-2.3.0-SNAPSHOT.jar` | `632f646fbdf922990b917a91cf1f30f42f73d35412691dec3250642607797882` |
| `L19-kafka-fix-kafka-streams-2.3.0-SNAPSHOT.jar` | `2ddf98926010f6840cda988c5689989ab7cf224a373f53158bc6468082d96b71` |
| `L19-kafka-parent-connect-api-2.3.0-SNAPSHOT.jar` | `b1aaf37685d9b740588bcc2e94e92fccea1ccb722d7ded29072f5c25cdd2bc22` |
| `L19-kafka-parent-connect-json-2.3.0-SNAPSHOT.jar` | `d74d58a6cadb8c4d58e8dcb245184652ef3738ed76003215084274bb2e3f9da4` |
| `L19-kafka-parent-kafka-clients-2.3.0-SNAPSHOT.jar` | `0d29a91e8c6dae9ba2c59a5e1b7bc032be0516ee74394da0fcac64e83fad6aa7` |
| `L19-kafka-parent-kafka-streams-2.3.0-SNAPSHOT.jar` | `4d8ac54e9c5b4023b651ff0cf588d2226c5b3f802c00aa62e78b9dce3fcd089e` |

Class digests (sha256 of each changed class, per side) are in `$O/artifacts/L19-*.class-digests.txt`; runtime classpaths in `$O/artifacts/L19-*-classpath.txt` (colon-separated; project jars point at the copies above).

Expected: `L19-kafka-ROLE-kafka-streams-2.3.0-SNAPSHOT.jar`, the test-utils runtime classpath `L19-kafka-ROLE.streams-test-utils-runtime-classpath.txt`
(kafka-streams, streams-test-utils, kafka-clients, connect-json, connect-api copied as `L19-kafka-ROLE-*.jar`) and class digests of the two changed classes.

**Landed tests.**

| Run | Result |
|---|---|
| fix, landed tests (first build, online) | junit tests=26 failures=0 errors=0 skipped=0 |
| fix, again offline | junit tests=26 failures=0 errors=0 skipped=0 |
| parent, its own tests (offline) | junit tests=25 failures=0 errors=0 skipped=0 |
| fix's test files on the parent (offline; expected to fail) | junit tests=26 failures=6 errors=0 skipped=0; junit failed KStreamSessionWindowAggregateProcessorTest#shouldLogAndMeterWhenSkippingLateRecordWithZeroGrace; junit failed KStreamSessionWindowAggregateProcessorTest#shouldLogAndMeterWhenSkippingLateRecordWithNonzeroGrace; junit failed SuppressScenarioTest#shouldSupportFinalResultsForSessionWindows; junit failed GraphGraceSearchUtilTest#shouldExtractGraceFromSessionAncestorThroughStatefulParent; junit failed GraphGraceSearchUtilTest#shouldExtractGraceFromSessionAncestorThroughStatelessParent; junit failed GraphGraceSearchUtilTest#shouldExtractGraceFromKStreamSessionWindowAggregateNode |

Run by job `20261125-161917-setup-build-kafka-streams-at-both-6654-r`; logs `$O/logs/L19-*.gradle-log.txt` and `*.junit.txt`.

**Release side.** KAFKA-8289 was released in 2.2.1 and 2.3.0. `GraphGraceSearchUtil.java`: 2.2.0 = **parent**, 2.2.1 and 2.3.0 = **fix**
(byte-identical). `KStreamSessionWindowAggregate.java`: 2.2.0 differs from the parent only by a reformatted log message (the parent's adds
`streamTime`) and an explicit `<K, V>`; **2.2.1 differs from the fix only by that explicit `<K, V>`**; 2.3.0 has later changes
(`SessionTupleForwarder`, `ValueAndTimestamp`). So 2.2.0 / 2.2.1 is the release pair for this logic. Resolved with strict checksums:
`$O/releases/L19-kafka-streams-2.2.0/` and `$O/releases/L19-kafka-streams-2.2.1/` (kafka-streams + kafka-streams-test-utils; `TopologyTestDriver`
is in test-utils).

| File | sha256 |
|---|---|
| `upstream/L19-tags/GraphGraceSearchUtil-2.2.0.java` | `7d726648b6558fa301787b42dab41b4d860ddf30fea3d9239b5ccd15cc75c7b2` |
| `upstream/L19-tags/GraphGraceSearchUtil-2.2.1.java` | `083a4a5822c5aec7f35b1d8a38e1dcd9f3f8b579a12833df0ce533274e03e750` |
| `upstream/L19-tags/GraphGraceSearchUtil-2.3.0.java` | `083a4a5822c5aec7f35b1d8a38e1dcd9f3f8b579a12833df0ce533274e03e750` |
| `upstream/L19-tags/GraphGraceSearchUtil-fix.java` | `083a4a5822c5aec7f35b1d8a38e1dcd9f3f8b579a12833df0ce533274e03e750` |
| `upstream/L19-tags/GraphGraceSearchUtil-parent.java` | `7d726648b6558fa301787b42dab41b4d860ddf30fea3d9239b5ccd15cc75c7b2` |
| `upstream/L19-tags/KStreamSessionWindowAggregate-2.2.0.java` | `a444a583c3733f0ea79e2eafb90d0d4addc6706f79847e0fe486b3f1060824cb` |
| `upstream/L19-tags/KStreamSessionWindowAggregate-2.2.1.java` | `eb23c5f10aa26a16617de1552c1ada81d6278693508d05d662d7458a356f16c6` |
| `upstream/L19-tags/KStreamSessionWindowAggregate-2.3.0.java` | `f7bd24403c265201bb9e6429c7677c331183a0e2412f29d9cdddf01e76ee8fdc` |
| `upstream/L19-tags/KStreamSessionWindowAggregate-fix.java` | `bf2ea4865ba7ab44e4b09a9e9a504f300e156ca9d07406d07830ed3376762c17` |
| `upstream/L19-tags/KStreamSessionWindowAggregate-parent.java` | `de5ae4a4711fabafe9448f2fd84c0f10f8a2c6316d447fac0ddbc32c8cea47ad` |

**Signatures.** Keyring `$O/gnupg-D`, Kafka KEYS (`$O/keys-D/kafka-KEYS`, sha256 `08b259d827917f0ae34e6fdadb34fb8417c27a2a27b0d5cddad0dad3e5ce9eea`). The 2.2.1 jars carry a good signature
made 2019-05-13 by a key that expired on 2021-05-02 (valid when it signed).

| Jar (Maven Central) | sha256 | Signature | Signer key |
|---|---|---|---|
| `kafka-streams-2.2.0.jar` | `9d4e66ef6c842b826f8473893470057db9c00315eeff750310da86c24bf9f0aa` | good | `F2B4C5FFE57C6265C741BF58638DD2A63F3A0F00` |
| `kafka-streams-test-utils-2.2.0.jar` | `261ab85833519bdc89ef5a2fe8a5daa86abe592eca6daea3700160c0ac03e3ff` | good | `F2B4C5FFE57C6265C741BF58638DD2A63F3A0F00` |
| `kafka-clients-2.2.0.jar` | `cc819c61aeb40906d38d862d2c645bc960ac3274eb57b89ba2153b60e562f2a2` | good | `F2B4C5FFE57C6265C741BF58638DD2A63F3A0F00` |
| `connect-json-2.2.0.jar` | `7b64077f934a28536a9a5d918aa720c38d82caede150616a2c9867e60b6b55a5` | good | `F2B4C5FFE57C6265C741BF58638DD2A63F3A0F00` |
| `connect-api-2.2.0.jar` | `b988c034c2c324d0881b0923bda86c819627e127d96de8efd40bd68010e40dee` | good | `F2B4C5FFE57C6265C741BF58638DD2A63F3A0F00` |
| `kafka-streams-2.2.1.jar` | `6daa68caa5c8c9d2ef5d89043e86bbaad27a4dc5bea8d808a3d13b652eee2af7` | good, key since expired | `F6627F0663D0CE710A29F8203674A03EDC7C2868` |
| `kafka-streams-test-utils-2.2.1.jar` | `5fe9d9b519a98421c0c2a90b5779d202f12e697fa0264b9ceb285d8b73f61b91` | good, key since expired | `F6627F0663D0CE710A29F8203674A03EDC7C2868` |
| `kafka-clients-2.2.1.jar` | `3a2f707ec1e6804a27e647d78b1c9a3eff1f84b5eedb0d454aca41c7d34c1992` | good, key since expired | `F6627F0663D0CE710A29F8203674A03EDC7C2868` |
| `connect-json-2.2.1.jar` | `7ed5c6a47704d57890183e91623d40cdc22a853be77790436f2fe9228c11e41d` | good, key since expired | `F6627F0663D0CE710A29F8203674A03EDC7C2868` |
| `connect-api-2.2.1.jar` | `1ca37aff07ae99dfd3b554212f20970bee05c11910b789f99ee8a85cd43807df` | good, key since expired | `F6627F0663D0CE710A29F8203674A03EDC7C2868` |

**Jobs.** `20261125-161917-setup-build-kafka-streams-at-both-6654-r`.

**For the domain agent**
- Release pair: kafka-streams + test-utils **2.2.0 = parent logic, 2.2.1 = fix logic** (other 2.2.0→2.2.1 changes exist); the pin jars come from the job.
- JDK 8 builds and runs the pins; the 2.2.x jars run on 8 or 11.
- 2.2.x test-utils has the pre-2.4 API: `TopologyTestDriver(Topology, Properties[, long])`, `pipeInput(ConsumerRecord)`, `readOutput(topic, deserializers)` and `org.apache.kafka.streams.test.ConsumerRecordFactory`; no `TestInputTopic` (checked with `javap` on 2.2.1 and the jar listings of both).

### L20 · JSqlParser #2770 — ALTER deparser dispatch with inactive column metadata (pinned source build; parent side by job, done)

**Pins.** Parent `cf6c83ce8f3fac6393356c57baeb1a4a3dee7913`, fix `0a7436a10301e118802a4b7effba056de22ee7f8` (squash, one parent = the brief's). Worktrees `$W/L20-JSqlParser-parent`, `$W/L20-JSqlParser-fix`.
Changed production files: `AlterExpression.java` and eleven other classes in `src/main/java/net/sf/jsqlparser/statement/alter/` (new
`hasActiveColumnDefinitions()` and protected `usesColumnActionBody()`/`hasColumnDefinitionPayload()` hooks), and
`util/deparser/AlterDeParser.java` (one line); also `src/site/sphinx/usage.rst`. Changed tests: new
`src/test/java/net/sf/jsqlparser/statement/alter/AlterRendererDispatchTest.java`, modified `util/TablesNamesFinderTest.java`.

**Build facts.** The repository has both Gradle and Maven builds; this setup used **Maven** (`pom.xml`, identical at both pins),
`com.github.jsqlparser:jsqlparser` **5.5-SNAPSHOT**, `maven.compiler.release` 11, JavaCC 8 via `javacc-maven-plugin` 3.8.0 (the
generator `com.manticore-projects.jsqlformatter:javacc-java:8.1.4.1944`), 694 sources. Built with Maven 3.10.0 on **JDK 17.0.21**; bytecode
Java 11 (major 55). **No runtime dependencies** (the runtime classpath file is empty). A build takes about 80 s even offline, so the parent
side runs as a job.

**Commands** (from the worktree root), wrapped as `$O/scripts/mvn_A.sh WT . TAG $J17 AlterRendererDispatchTest,TablesNamesFinderTest [online]`:
- online (92 s): `JAVA_HOME=$J17 $MVN -Daether.connector.basic.threads=1 $SK -Dtest=AlterRendererDispatchTest,TablesNamesFinderTest -Dsurefire.failIfNoSpecifiedTests=false package`
- **offline (checked on the fix, 81 s)**: the same with `-o`. The parent's offline runs are the job's (same `pom.xml`).
- The JavaCC plugin warns "No dependent jar found for resource 'META-INF/maven/org.javacc/core'" and "Non existing or badly extracted jar";
  the build succeeds regardless.

**Artifacts** (the fix built inline; the parent by job `20261125-162151-setup-run-jsqlparser-2770-s-landed-alter`, `$O/scripts/L20_job.sh parent`; class digests of every changed class of both sides in `$O/notes/A-L20-digests.md`, written by the job):

| File | sha256 |
|---|---|
| `L20-JSqlParser-parent.jar` | `ab1d2eb2fabe4a742e30c8cecdd18073af9a05c109538d1ed16fdf378936e47a` |
| `L20-JSqlParser-fix.jar` | `e6620d35a0d60d5d92f265d3bb5fda8ca8640ca24ad3218b55473d9b283ab397` |

Test classpaths: `$O/artifacts/L20-JSqlParser-{parent,fix}.test-classpath.txt` (runtime classpaths empty). Use: `java -cp $O/artifacts/L20-JSqlParser-ROLE.jar ...`.

**Landed tests** (JDK 17):

| Run | Result |
|---|---|
| fix, `AlterRendererDispatchTest` + `TablesNamesFinderTest` (online, then offline) | tests=128 failures=0 errors=0 skipped=0; offline tests=128 failures=0 errors=0 skipped=0 |
| parent, its own `TablesNamesFinderTest` (offline; job) | tests=107 failures=0 errors=0 skipped=0 |
| fix's two test files on the parent (offline; job) | **does not compile**, as expected: `cannot find symbol` at `AlterRendererDispatchTest.java` lines 53, 76, 137, 147, 193, 212; `AlterRendererDispatchTest` asserts `action.hasActiveColumnDefinitions()` (lines 53, 76, 137, 147, 193, 212), a method only the fix has |
| the same with those six lines deleted (a **modified** copy: `grep -v 'hasActiveColumnDefinitions()'` over both files, 6 lines; offline; job) | tests=128 failures=16 errors=0 skipped=0; failing (16): `AlterRendererDispatchTest#baseBodyPrecedencePreventsInactiveColumnExpressionsFromBeingRendered`, `AlterRendererDispatchTest#dropFallbackKeepsIdentityBodyInsteadOfInactiveDefaultMetadata`, `AlterRendererDispatchTest#dropFallbackStillRewritesItsActiveColumnExpressionAndAppendsTailOnce`, `AlterRendererDispatchTest#specializedBodiesIgnoreUnrelatedDefaultAndColumnMetadata` (parameterized cases counted) |

**Release side.** **None.** The newest release, `5.4` (2026-09-13), predates the parent (2026-10-13); its alter classes differ from both pins.
No release was resolved.

**Signatures.** None checked: no release is used, and the build's plugins and test libraries rest on Central's checksums.

**Jobs.** `20261125-162151-setup-run-jsqlparser-2770-s-landed-alter` (fork A): passed: parent's own test, parent jar and digests, the landed
transplant (does not compile), the modified transplant (16 failures), then both build trees removed.

**For the domain agent**
- Both jars are the pins' own builds (`$O/artifacts/L20-JSqlParser-{parent,fix}.jar`).
- A plain landed-test transplant cannot separate the sides (it does not compile on the parent); the modified copy (six `hasActiveColumnDefinitions()` assertions deleted) does, with 16 failures on the parent.
- The brief's challenge reparses under `Dialect.POSTGRESQL`; nothing of it was run.

## Jobs

Eight jobs were queued by the forks with `$O/scripts/submit_{A,B,C,D}.py` and committed with the start of this record; four more followed
when their results came back (`submit_D.py l14 l15` again, `submit_L09b.py`, `submit_L05b.py`), and a third L15 attempt after those
(`submit_D.py l15`). Each resolves online first (one connector
thread) and runs its later steps offline; each copies its jars, digests and classpaths to `$O/artifacts/` and ends by removing its build
trees. A transplant step passes only when the named test fails (or, where noted, when the landed test does not compile). The first attempts'
logs for L14 and L15 are kept in `$O/logs/attempt-1/`, the second L15 attempt's (with its init script) in `$O/logs/attempt-2/`; the third
L15 attempt's are `$O/logs/L15-*`. L15 was not submitted a fourth time: see its row and [What to know](#what-to-know-before-starting).

| Job | Case | What it runs | Estimate | Result |
|---|---|---|---|---|
| `20261125-161916-setup-build-calcite-core-at-both-5378-re` | L10 | Calcite core at both pins; `CoreQuidemTest` (`planner.iq`) and `RelOptRulesTest`; the fix's test resources on the parent | 3 CPU, 6G, 45m | **passed** (8m36s): fix 1006 tests, 0 failures, online and offline; parent 1006, 0 failures; transplant 3 failures (`CoreQuidemTest#[8] sql/planner.iq`, `RelOptRulesTest#testMinusMergeRule()`, `RelOptRulesTest#executionError`) |
| `20261125-161917-setup-build-gradle-distributions-at-both` | L15 | Gradle's own build on Gradle 7.5.1: both pin distributions and `IncrementalBuildIntegrationTest` | 4 CPU, 10G, 150m | **failed** (2m42s) configuring the root project: `org.openmbee.junit:junit-xml-parser:1.0.0` is no longer on the Plugin Portal. Rerun below |
| `20261125-161917-setup-build-iceberg-api-core-data-parque` | L14 | Iceberg api/core/data/parquet at both pins; `TestGenericRecord`, `TestGenericReaderDeletes`; transplant | 3 CPU, 6G, 40m | **failed** (3m20s) in `:generateGitProperties`: JGit finds no repository in a linked worktree. Rerun below on clones |
| `20261125-161917-setup-build-kafka-streams-at-both-6654-r` | L19 | Kafka streams at both pins (Gradle 5.4.1, JDK 8); the three landed test classes; transplant | 3 CPU, 6G, 45m | **passed** (4m04s): fix 26/26 online and offline; parent 25/25; transplant 6 failures (L19's section names them) |
| `20261125-162151-setup-run-jsqlparser-2770-s-landed-alter` | L20 | the parent's own `TablesNamesFinderTest`, parent jar and digests; the landed test on the parent; a copy with the six fix-only calls removed | 2 CPU, 3G, 8m | **passed** (5m12s): parent 107/107; landed transplant does not compile (`hasActiveColumnDefinitions()`); modified copy 128 tests, 16 failures |
| `20261125-162448-setup-build-guava-7277-s-two-revisions-j` | L16 | Guava JRE and Android at both pins, `FuturesTest` (the PR adds no tests) | 4 CPU, 5G, 30m | **passed** (2m46s): `FuturesTest` 160/160 on each of fix JRE, fix Android, parent JRE, parent Android, and fix JRE offline |
| `20261125-162448-setup-run-rdf4j-1989-s-landed-empty-grou` | L09 | meant: rdf4j compliance tests at both pins and the transplant | 3 CPU, 5G, 25m | **passed, but did not run the compliance classes**: it stopped at `package`, and `compliance/sparql` runs its tests under failsafe in `verify`. Only `GroupIteratorTest` ran (as inline). It did copy and compare the module jars of both sides. Rerun below |
| `20261125-162622-setup-build-junit-6104-at-both-revisions` | L05 | JUnit jars at both pins; `NestedTestClassesTests`, `ClassTemplateInvocationTests` on the fix, the parent, and the fix's tests on the parent | 2 CPU, 6G, 30m | **passed** (5m49s): fix 56/56 online and offline; parent 53/53; landed transplant does not compile (the fixture uses the fix's renamed constants). Follow-up below |
| `20261125-165654-setup-build-iceberg-api-core-data-parque` | L14 | second attempt, on standalone clones (`:generateGitProperties` checked inline) | 3 CPU, 6G, 40m | **passed**: fix 48 run, 0 failures, 1 skipped, online and offline; parent's own 39 run, 0 failures, 1 skipped; transplant 9 failures (8 `TestGenericReaderDeletes` parameterizations, `TestGenericRecord#testDeepCopyValues()`); jars, class digests and classpaths of both sides copied |
| `20261125-165654-setup-build-gradle-distributions-at-both` | L15 | second attempt, with `$O/scripts/gradle-L15-openmbee-substitute.init.gradle` | 4 CPU, 10G, 150m | **failed** (1m17s): every Gradle step exited 1 configuring the root project; `junit-xml-parser` was still not found, now for `:build-logic:performance-testing:compileClasspath`, which resolves from `build-logic`'s settings repositories (the script reached build-script repositories only). No test ran. Rerun below |
| `20261125-165913-setup-run-rdf4j-1989-s-landed-compliance` | L09 | the compliance build to `verify` (`$O/scripts/rdf4j_verify.sh`): failsafe `MemoryComplexSPARQLQueryTest`, `SPARQL12QueryTest`, surefire `GroupIteratorTest`, at both pins and the PR's test-side files on the parent; each step was meant to fail if a named class did not run | 3 CPU, 5G, 30m | **passed**: fix `MemoryComplexSPARQLQueryTest` 81/81, `SPARQL12QueryTest` 2/2, `GroupIteratorTest` 9/9, online and offline; parent's own 78/78 and 8/8; transplant 5 failures (`testMax/Min/SampleAggregateWithGroupEmptyResult`, `agg on empty set, explicit grouping`, `testMaxEmptySet_Grouped`). Its per-class lines wrongly said "NOT RUN" (a pattern fault in the setup's script, and the guard did not take effect); recomputed from its logs, as L09's section explains |
| `20261125-170100-setup-run-junit-6104-s-landed-nested-cla` | L05 | the fix's two test classes on the parent with only four constant references mapped to the parent's names or the same string values; the parent's own fixture | 2 CPU, 6G, 15m | **passed** (2m52s): production code and fixtures unchanged; 56 run, 3 failures (`NestedTestClassesTests#nestedTestClassesWithSameNameAreCorrectlyDiscoveredAndExecuted()`, `NestedTestClassesTests#deeplyNestedInheritedMethodsAreExecutedWhenSelectedViaUniqueId()`, `ClassTemplateInvocationTests#nestedClassTemplateIsInherited()`) |
| `20261125-172547-setup-build-gradle-distributions-at-both` | L15 | third attempt: the init script now also adds the repository to every build's settings repositories (`build-logic`'s resolution checked inline, 26 s) | 4 CPU, 10G, 150m | **failed** (1m43s, peak 3.5 GiB): past `junit-xml-parser` (the init script took effect in every included build), then every Gradle step stopped in Gradle's own strict dependency verification: `org.ysb33r.gradle:grolifant:0.16.1`'s jar from Maven Central does not match the sha256 both pins' `gradle/verification-metadata.xml` record, and the pinned jar is no longer served anywhere checked (L15's section has both digests). No test ran; the cleanup step passed. **Not resubmitted**: going on needs a decision to accept a different jar |

## Signatures

Each case's section has its own signature table. In short:
- **Good against a project KEYS file:** Apache Commons (Collections, Statistics, Imaging and their dependencies), Arrow, Maven 3.9.9, Calcite 1.42.0,
  Iceberg 1.9.2 and 1.10.0 (six jars each), Kafka 2.2.0; java-diff-utils 4.17/4.18 only with the key from the repository's own KEYS file (the
  keyserver's copy has expired: `EXPKEYSIG`).
- **Good, key from keyserver.ubuntu.com with nothing further vouching for it:** gson, picocli, JUnit and opentest4j, jgrapht, rdf4j, Guava,
  Quartz, iCal4j.
- **Good but by an expired key, signed before it expired:** maven-shade-plugin 3.3.0 and 3.4.0 (key expired 2024-08-15, signed 2022);
  Kafka 2.2.1 (key expired 2021).
- **Not verifiable:** RxJava 3.0.0-RC8/RC9 (the signing key has only a "key compromised" revocation on the keyserver), reactive-streams 1.0.3
  (signed by a subkey the published key marks encryption-only). They rest on Central's checksums.
- **Not signed, checked by checksum instead:** the Gradle distributions and wrapper jars (sha256 against services.gradle.org; tables above),
  the pins themselves (git commits fetched by SHA), and the jcenter-era build-script modules substituted for L18 (`build-info-extractor`,
  `-client`, `-api` 2.15.0 from JFrog's public jcenter mirror, `http-builder` 0.7.2) and L19 (`grgit-core` 3.1.1 from repo.grails.org), each
  by SHA-1 against the serving repository, with no second source.
- **L15's `grolifant-0.16.1.jar`:** the copy served today (Maven Central; the Plugin Portal and jcenter redirect there) fails the sha256
  both pins record, and was not used for anything. Its `.asc` names key id `54AC8E2D98CFEAC6` and a signing date of 2022-11-08, after
  both pins; the signature was not checked (`$O/dl/L15-grolifant-check/README.txt`).
- **L15's substitute library** `org.openmbee.junit:junit-xml-parser:1.0.0` (from `https://repo.gradle.org/gradle/public`, which the
  upstream `build-logic` declares): its sha256 equals the one both pins' `gradle/verification-metadata.xml` pin (L15's section has both), and
  Gradle's strict dependency verification checks it again in the build.

## Disk

`$O` is 11 GB: `gradle-home` 3.9 GB, `gradle-home-L15` 0.9 GB, worktrees and clones 2.0 GB, tools (Gradle distributions, Maven 3.9.9) 1.2 GB,
`dl` 1.1 GB, `m2` 1.2 GB, release sets 0.5 GB, artifacts 79 MB. Inline build trees were deleted after their jars and digests were recorded;
the jobs remove theirs. The mirrors under `$M` hold only the pins (plus earlier setups' pins in the eight shared mirrors, and picocli's three
landed commits).

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/merged-pr-links-l01-l20` (`$O`); `source $O/scripts/env.sh` gives `$O`, `$W`, `$MVN`,
  `GRADLE_USER_HOME`, `TMPDIR` and the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25`. The default `java` is 25.
- Both revisions of every case at the brief's pins: `$W/LNN-MIRROR-parent` and `$W/LNN-MIRROR-fix` (full SHAs, trees and parents in
  [Upstream revisions](#upstream-revisions)). Every PR's merge SHA is the brief's after pin; every after pin's first parent is the before pin,
  except L03, whose three rebased commits lead from the before pin to the after pin as the brief says.
- Built jars of both sides in `$O/artifacts/`, named in each case's section with full sha256 and the digests of the changed classes, and
  runtime classpath files beside them: L01–L04, L06–L08, L11–L13, L17, L18 inline; L20 (fix inline, parent by job); L05, L10, L14, L16,
  L19 by job; L09's evaluation module inline, and every rdf4j module of both sides by job (`$O/artifacts/L09-rdf4j-ROLE-modules/`).
  **Not built, and setup stopped there:** L15's two pin distributions (`$O/tools/gradle-pin-L15-ROLE`). Three jobs failed in Gradle's own
  `build-logic`; the last on a pinned jar (`grolifant-0.16.1.jar`) that is gone, whose only public copy fails the build's verification (see
  [What to know](#what-to-know-before-starting)). For L15, the pins' sources, the releases 7.5.1 and 7.6, and `$O/gradle-home-L15`
  (resolved up to `build-logic`) are ready.
- Release sets resolved with strict checksums in `$O/releases/`, and which side each equals: the "Release side" column of
  [Summary by case](#summary-by-case).
- Dependencies are in `$O/m2` and `$O/gradle-home`; the offline form (`$MVN -o`, `--offline`) was checked for every case built inline, and
  the jobs run offline after their first step. Exact commands are in each case's section.

### What was verified on a JVM

- The landed regression passes on the fix and fails on the parent (the fix's test moved onto the parent) for L01, L02, L03, L04, L06, L07,
  L08, L09 (`GroupIteratorTest#testMaxEmptySet_Grouped`), L11, L12 (`JdbcJobStoreTest`, Derby), L13, L17 and L18: 13 cases, counts and
  failing tests in the summary table.
- By job, the same holds for **L10** (`planner.iq` and two `RelOptRulesTest` entries fail on the parent with the fix's resources), **L14**
  (9 of 48: eight `TestGenericReaderDeletes` parameterizations and `TestGenericRecord#testDeepCopyValues()`) and **L19** (6 of the 26 landed
  tests fail on the parent): 16 cases in all.
- **L05, with a mapped transplant:** the landed tests pass on the fix (56) and the parent's own on the parent (53). The fix's tests do not
  compile on the parent as they are (the fixture uses constants the fix renames); with only four constant references mapped (to the parent's
  names, or the same string values) and nothing else changed, 3 of 56 fail on the parent, the two `NestedTestClassesTests` cases of the PR
  and `ClassTemplateInvocationTests#nestedClassTemplateIsInherited()`. The mapped files and their diffs are in `$O/artifacts/L05-transplant-mapped/`.
- **L20's landed test does not compile on the parent** (it calls the fix-only `hasActiveColumnDefinitions()`); a copy with those six lines
  deleted, labelled as modified, compiles and has 16 failures on the parent.
- **L16 has no landed test** (the PR adds none); `FuturesTest` passes at both pins, JRE and Android (160 each), and cannot separate the sides.
- **L09:** besides `GroupIteratorTest#testMaxEmptySet_Grouped` (inline), the compliance classes ran under failsafe by job: on the fix
  `MemoryComplexSPARQLQueryTest` 81/81 and `SPARQL12QueryTest` 2/2; on the parent its own 78/78; with the PR's test-side files on the parent,
  the three `...AggregateWithGroupEmptyResult` tests and `agg on empty set, explicit grouping` fail.
- **L15: nothing verified on a JVM.** No pin build or landed test ran; the third job (`20261125-172547-setup-build-gradle-distributions-at-both`)
  stopped on `grolifant` as described above. No job is pending.
- **None of the brief's claim scenarios was run** in any case.

### What to know before starting

- **Build tools:** Maven 3.9.9 (`$O/tools/apache-maven-3.9.9`) for L06 (Arrow) and L09 (rdf4j); 3.10.0 fails on both. Gradle versions per
  case are in `$O/tools/gradle-*` (tables above); run the distributions directly, not `./gradlew`.
- **JDKs:** L07 and L09 build on JDK 8, L18 and L19 on 8, L03 and L13 on 11, L15's Gradle build on 11, L05 on 25 with toolchains 17/21/24/25,
  L10 on 21 with a 25 compile toolchain; the rest on 17. L06 needs `--add-opens=java.base/java.nio=ALL-UNNAMED` on 17+ and one allocator
  module on the classpath.
- **L15, substitution and unstable input:** the pins' wrapper names a nightly (`gradle-7.6-20220513164305+0000`) that is gone everywhere;
  the pin distributions are built by released Gradle 7.5.1 with `--no-scan --no-build-cache`. No release equals either side (7.5.1 lacks the
  fix and an earlier parent-side change; 7.6 has the fix plus later changes).
- **L08, unstable input:** commons-statistics depends on `commons-rng` **1.8-SNAPSHOT**; the build pinned the snapshot timestamp recorded in
  L08's section (`$O/notes/A-L08-snapshots.md`).
- **L18 and L19, substitutions:** build-script modules gone from jcenter were taken from public mirrors by SHA-1, through init scripts in
  `$O/scripts/`; no upstream build file was edited.
- **L19:** the release pair 2.2.0 (parent logic) / 2.2.1 (fix logic) also differs in other changes; 2.2.x test-utils has the pre-2.4
  `TopologyTestDriver` API (no `TestInputTopic`).
- **L13:** the brief's scenario runs the shade goal in a Maven build. 3.4.0 is source-equal to the fix; the parent has no equal release and
  its built jar is not installed anywhere (both pins say `3.3.1-SNAPSHOT`). The fixture JARs A and B were not built.
- **L11:** the parent's tree lacks the 127×127 images; copies are in `$O/artifacts/L11-resources/`.
- **L10:** the landed fixture enables the rule with Quidem's `!set planner-rules "+CoreRules.PROJECT_SET_OP_TRANSPOSE"`; how a plain JDBC
  connection gets the same rule set was not looked into.
- **L05, L14, L19:** `$W/L05-junit-framework-*`, `$W/L14-iceberg-*` and `$W/L19-kafka-*` are standalone depth-1 clones, not worktrees,
  because their builds read git through JGit (L14's `gradle-git-properties` failed in a worktree); build JUnit only through
  `$O/scripts/L05-gradle.sh`.
- **L15 is blocked on `org.ysb33r.gradle:grolifant:0.16.1`.** Gradle's build verifies dependencies strictly, and both pins record a
  sha256 for this jar (origin "Artifact is not signed") that no public copy has now: the Plugin Portal and jcenter redirect to Maven Central,
  whose jar differs and was signed on 2022-11-08, after the pins, and `repo.gradle.org/gradle/public` answers 404. Digests and URLs:
  L15's section and `$O/dl/L15-grolifant-check/`. Going on needs someone to decide to accept Central's jar, e.g. by adding
  `--dependency-verification lenient` to the job's Gradle commands (`submit_D.py l15`), which reports the mismatch and carries on, or to
  find the original jar elsewhere. Setup took neither step. Until then, the releases 7.5.1 and 7.6 are the only Gradle distributions here,
  and neither equals a side.
- **L15, second substitution:** `org.openmbee.junit:junit-xml-parser:1.0.0` is no longer on Central or the Plugin Portal, and Gradle's build
  needs it for the root build-script classpath and for `build-logic`'s compile classpath; `$O/scripts/gradle-L15-openmbee-substitute.init.gradle`
  adds `https://repo.gradle.org/gradle/public` (which `build-logic` already declares for another module) for that one group, to every
  build's settings repositories and every project's build-script repositories. Pass it with `-I` on every L15 Gradle run.
- **L09:** `compliance/sparql` skips surefire and runs its tests under failsafe; run them with `$O/scripts/rdf4j_verify.sh` (`verify`,
  `-Dit.test=...`), not with `-Dtest` and `package`. Its per-class lines were fixed after the job; read counts from the Maven log if in doubt.
- **Signatures:** RxJava 3.0.0-RC8/RC9 and reactive-streams 1.0.3 cannot be verified; shade 3.3.0/3.4.0 and Kafka 2.2.1 are signed by keys
  that have since expired. See [Signatures](#signatures).
- Jars built from pins carry build timestamps: compare the class digests in each section, not the jar digests.

### What is left for the domain work on purpose

- Every claim, example folder, example id, adapter, sidecar, observer and recipe; the brief's public scenarios and challenge histories
  (none was run or probed).
- Choosing, per case, whether the built pins or a published release stand for each side.
- L15: whether to build Gradle's pins with Central's `grolifant-0.16.1.jar` in place of the pinned one (lenient dependency verification),
  or to work from the releases 7.5.1 and 7.6, which only approximate the sides.
- L13's fixture JARs and the coordinates under which a parent-side shade plugin would be installed; L10's JDBC route to the rule set; the
  Quartz databases other than Derby (L12).
