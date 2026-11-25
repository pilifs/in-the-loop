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

## Cases

Case sections follow as the forks of this session finish them.
