# Setup for the Spring Framework PR links Q01–Q30 brief

Mechanical setup for [`spring-framework-pr-links-q01-q30-brief.md`](spring-framework-pr-links-q01-q30-brief.md), done on
2026-11-26 by a setup session (Claude Opus 5.5) before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

**Status: in progress.** Sections marked *pending* are filled in as the work goes on.

`$P` below is `~/.cache/in-the-loop/spring-pr-links-q01-q30`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $P/scripts/env.sh` defines `$P`, `$M`, `$W` (= `$P/worktrees`), `TMPDIR` (= `$P/tmp`), `GRADLE_USER_HOME` (= `$P/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`),
`$JL17` (BellSoft Liberica 17.0.21.1) and `$J24` (Temurin 24.0.2, fetched here), see [Toolchain](#toolchain).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `Q01`–`Q30` follow the brief's order (the same as the PR list
[`spring-framework-merged-pr-links-q01-q30.md`](spring-framework-merged-pr-links-q01-q30.md)). They are this record's labels
only, not example ids. The scripts are the P01–P30 setup's (`~/.cache/in-the-loop/spring-pr-links-p01-p30/scripts/`), copied
with their paths changed and extended where noted.

| Case | PR | Case | PR | Case | PR |
|---|---|---|---|---|---|
| Q01 | #36912 | Q02 | #36550 | Q03 | #37326 |
| Q04 | #2060 | Q05 | #35808 | Q06 | #37332 |
| Q07 | #37577 | Q08 | #37524 | Q09 | #26700 |
| Q10 | #25464 | Q11 | #27716 | Q12 | #27735 |
| Q13 | #34709 | Q14 | #37602 | Q15 | #37261 |
| Q16 | #37053 | Q17 | #1251 | Q18 | #1175 |
| Q19 | #374 | Q20 | #25656 | Q21 | #36602 |
| Q22 | #37096 | Q23 | #37601 | Q24 | #36162 |
| Q25 | #23784 | Q26 | #22881 | Q27 | #37525 |
| Q28 | #35140 | Q29 | #37465 | Q30 | #35732 |

## Starting commit

Checkout at setup: `32d3a22cfbae921d272649eaaae608d60ae89ecf` (`develop@origin`, "Merge the single-agent run
spring-framework-pr-links-p01-p30-brief into the line").

## Upstream revisions

All 30 pull requests are in `spring-projects/spring-framework`. The shared bare mirror `$M/spring-framework.git` (it existed
already) gained every pinned commit, fetched by SHA at depth 1 from GitHub and kept under `refs/pins/q01-q30/CASE-ROLE-SHA`
(`$P/scripts/pins.tsv`, log `$P/logs/fetch.log`: 61 of 61, two of them already there; two fetches raced another session's fetch
in the same mirror, "shallow file has changed", and succeeded on retry). Roles: `parent` = the brief's *before* pin, `fix` = its
*after* pin, `later` = the one subsequent revision the brief links by commit (Q23 `64861cb395e415bf1452d30f54f8e2c0ecc9cb46`,
"Subsequent revision named by the maintainer"). Every 40-hex id in the brief is one of these 61. The intermediate commits of the
two multi-commit landings were fetched too and kept as `refs/pins/q01-q30/CASE-mid-SHA`. One detached worktree per pinned revision:
`$W/CASE-ROLE` (61 worktrees, 5.2 GB checked out).

Checked mechanically (`$P/logs/prs.txt`, PR records `$P/upstream/prs/PR.json`, changed files `$P/upstream/prs/PR-files.tsv`, PR
commits `$P/upstream/prs/PR-commits.tsv`, commit records `$P/logs/commits-api.tsv`, chains `$P/logs/multi-commit-landings.txt`):

- **Every PR is merged and its `merge_commit_sha` equals the brief's after pin.**
- **For 28 cases the after pin's first parent is the before pin.** Q16's and Q19's after pins are two-parent merges (second
  parents `7f1966f5f575f033ba402660814e96d339549331` and `e04a7569687a4da98f1c39fbee1ff209715c3fdd`), which the brief says
  ("the first parent of the branch merge", "the merge commit and its first parent"). Two landings are chains of commits whose
  first commit's parent is the before pin:
  Q18 `1d46b8d7… → 55d6f88dcd4bfc2f3ca993d73bedbff3a9bd5dee (Add ResourceRegionEncoder) → a7a9e36ca024d52de74db0665c1102eec901b300 (Add ResourceRegionHttpMessageWriter) → 3596e720505745ef48678bfce17c8d036943852d (Add range requests support in ResourceWebHandler) → e3da8b5e… (Polish ResourceHttpRequestHandler, ResourceEncoder)`,
  Q26 `ec8689d1… → 9cff07ce35dcca7c1028885492d246b3f4735dfb (Fix doCleanupAfterCompletion invocation) → 83046531… (Replace signal materialization in TransactionalOperator with usingWhen)`
  (full ids of the outer pins in the table), matching the brief's "four consecutive commits" and "two landed commits". Q26's PR
  lists its two commits under their pre-rebase ids (`ffa73b13381827022136d3bc87da80feb6f9ba90`,
  `33bfe45b2926b83d31734ad47bbbe0657fd650ee`). Q02, Q03, Q05, Q10, Q16, Q19, Q23 and Q26 have a two-parent merge as their **before** pin. PRs Q04 (2
  commits), Q12 (11) and Q15 (4) landed squashed as one commit.
- **The diff before→after names exactly the PR's changed files** for all 30 (`$P/logs/CASE-landed-files.txt`, diffstats in
  `$P/logs/CASE-landed-diffstat.txt`). Q18 changes 14 files, Q05 10, Q10 8.
- **Signatures**, checked in a keyring of this work's own (`GNUPGHOME=$P/gnupg`; keys in `$P/keys/`: GitHub's `web-flow.gpg`,
  the same bytes as the P01–P30 setup's copy, and Sam Brannen's SSH signing key from `gh api users/sbrannen/ssh_signing_keys` in
  `$P/keys/allowed_signers`; the principal name in that file is this setup's label only). All 19 signed pins verify
  (`$P/logs/commit-signatures.txt`), Q12's fix with a GitHub web-flow key that has expired since; the other 42 are unsigned.
- Trees: each commit's tree id from GitHub equals the mirror's (`git rev-parse SHA^{tree}`).

| Case | Worktree | Commit | Tree | Parents | Date | Author | Signature | Subject |
|---|---|---|---|---|---|---|---|---|
| Q01 | `Q01-parent` | `85c8bb674cd7dbef46f172da8b7fc048f45f53be` | `935dddabe8d61d864d5129b287848fc5f4f76cb1` | `2d478f7d9b7afa47e625a19a4f27a3b63b6f434f` | 2026-09-03 | Tran Ngoc Nhan | unsigned | Handle zero readTimeout in JdkClientHttpRequestFactory |
| Q01 | `Q01-fix` | `2b5229ff8fa5c7b2b117e85f2c72f6f2f1e62f78` | `478b454c350ac8454844a74ac46e682d575c5702` | `85c8bb674cd7dbef46f172da8b7fc048f45f53be` | 2026-06-13 | junhyeong9812 | unsigned | Fix reserveMethodNames to reserve each supplied name |
| Q02 | `Q02-parent` | `2a1678f246fb34609440e07d723e09b780112842` | `74033f4ec1d33570a7676c86387fbfaf5248edf5` | `3806315e319f36266a76d8d2e4cf7b9dc6a8d898` `f5a8c321c00d4d8f66d263528169932e02ee7e7d` | 2026-04-07 | Sébastien Deleuze | unsigned | Merge branch '7.0.x' |
| Q02 | `Q02-fix` | `d37d7abb1768c3fe8a71ba291f2e24082b26c27e` | `0ef602e1a9c9e30b0258ceb60b58806147858561` | `2a1678f246fb34609440e07d723e09b780112842` | 2026-03-27 | daguimu | unsigned | Reject unbalanced parentheses in profile expressions |
| Q03 | `Q03-parent` | `9289f71ad78323b95c08106f17d2fa4c23d9b115` | `0713aca506f3eb919fde4522315cd38e14f9077b` | `9a87fa6d12ea4536e9bd72d813cac1859ab11759` `3a600481d27f6586c72df91296d0d28232f862e5` | 2026-09-30 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| Q03 | `Q03-fix` | `5e7630469c7b665dc272f820de9def70adb6fe56` | `5781f1177c62074f30925a8f03c55f8b85244689` | `9289f71ad78323b95c08106f17d2fa4c23d9b115` | 2026-09-30 | Chengang Guan | good, GitHub web-flow key B5690EEEBB952194 | Fix container detection in RepeatableContainers.standardRepeatables() |
| Q04 | `Q04-parent` | `3a42f1154d8c85bae1ece307ee286fb52e7bf160` | `62d94503482aa437e48138da87416bb3a5f31003` | `846ec31dfe13b9c013059831c84bec4aa032eb4e` | 2019-02-27 | Sam Brannen | unsigned | Polishing |
| Q04 | `Q04-fix` | `d77b36bf3b3689cc6dca999e432e3979fb49859a` | `e0b4d9cff483b7cce9ce9cf538e24e1a572d5089` | `3a42f1154d8c85bae1ece307ee286fb52e7bf160` | 2019-02-27 | Loïc Ledoyen | unsigned | Open parameter autowiring utility for external use (#2060) |
| Q05 | `Q05-parent` | `a5579614d9ff079560c321a6cc80ed7de2c72002` | `b65aa588a437d2bb5fd2cc7dc871d5c7f4a1fe0d` | `eca6d91532851c1c0111378f10238b25e6af107f` `a01dd1cd79b278ddf7ea8de367cbabae9c26b0fa` | 2026-03-23 | Juergen Hoeller | unsigned | Merge branch '7.0.x' |
| Q05 | `Q05-fix` | `0eba6f0da3fbd879326226c9310791ceb329bb82` | `b6b6f2bf4aa94409d6f2985004a07a6d59293686` | `a5579614d9ff079560c321a6cc80ed7de2c72002` | 2025-04-01 | Yanming Zhou | unsigned | Add typesafe method to get generic bean by name with type reference |
| Q06 | `Q06-parent` | `db4f57a54f6954b40cdb3062b8c904d422bb04ae` | `8fc458fb38d9c3796a8da3be23361c7915420a6b` | `912b0bce9d954bac6be190253d1e18dd85417a38` | 2026-10-02 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |
| Q06 | `Q06-fix` | `f5a71230440381427d7d652e94a44a8658357025` | `c0f9ed97a51e52e45031c6f9c8d9a03cdfb4c123` | `db4f57a54f6954b40cdb3062b8c904d422bb04ae` | 2026-10-02 | Yanming Zhou | good, GitHub web-flow key B5690EEEBB952194 | Honor `Collection.remove()` contract in `CompositeCollection` |
| Q07 | `Q07-parent` | `2934b2edb8e10e1dfa1d0665081e00990cbaabda` | `c4287c85dc7fe6d17fe0a310a288611fb9c22d59` | `e1708775dad05b44ba0fa7b7ed7c2bc20822ebd8` | 2026-10-25 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Upgrade to AspectJ 1.9.26 |
| Q07 | `Q07-fix` | `cb0da839a773a9957f8633d3b6b7a22d36bac40f` | `7481ac382ff5a1820209d9c2d747a649acbaef77` | `2934b2edb8e10e1dfa1d0665081e00990cbaabda` | 2026-10-25 | CCCLL | good, GitHub web-flow key B5690EEEBB952194 | Fix stale ConcurrentReferenceHashMap size after compute |
| Q08 | `Q08-parent` | `78276e4cd07d421063162c2b6164499331d4506c` | `1b205b808191ce2361dc187496ac4b573e47f3f7` | `776508c53be40f0d72478c335c85e72adb9b6d26` | 2026-10-19 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |
| Q08 | `Q08-fix` | `a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3` | `3b147b87cfbf10df700d1d6c75f326dbb7ce0b7a` | `78276e4cd07d421063162c2b6164499331d4506c` | 2026-10-20 | lejuho | good, GitHub web-flow key B5690EEEBB952194 | Use SqlParameterSource as-is in SqlParameterSourceUtils.createBatch |
| Q09 | `Q09-parent` | `564c6f7f86467e1f831d107d571ec34501104b18` | `05c5ce53305a258eb7f60dcb97f8c72b1871a3c9` | `a07c7865a5ad1a625231f1fb8506178e7d76a927` | 2021-06-25 | diguage | unsigned | improve the performance of iteration |
| Q09 | `Q09-fix` | `531174258c123920a36e183ce63946f38d07e45a` | `68ef1f36b5fd200207e18f7431bc39f0ea3302a7` | `564c6f7f86467e1f831d107d571ec34501104b18` | 2021-03-18 | Filip Hrisafov | unsigned | Apply dynamic changes in ThreadPoolTaskExecutor before setting local value |
| Q10 | `Q10-parent` | `c17f2047f62af92ac41ab419b2c3e027fd8ade25` | `948d936f1b3f5cb55e53e2c18d2ab36f45a31e09` | `d646e602d957ea31ea82b8d4b25bee91818402ca` `91d1383e931658754d69a53e0f6866641ffe0ddb` | 2020-08-03 | Sam Brannen | unsigned | Merge branch '5.2.x' |
| Q10 | `Q10-fix` | `87c3bb579739aa4892f3b647f8eef7e2dc16a7f5` | `b6ebb11c94c9fce0d453f3a682fb64485f35dd1f` | `c17f2047f62af92ac41ab419b2c3e027fd8ade25` | 2020-07-15 | Arjen Poutsma | unsigned | Introduce CronExpression |
| Q11 | `Q11-parent` | `aeff664cf9fd7817a2c699732b150e3691018f73` | `8e65404ec7740687bb6ad45e605e02aa365f6271` | `ba468a731fc49a383021d3243e6934d29aa1a802` | 2021-12-14 | Juergen Hoeller | unsigned | Polishing |
| Q11 | `Q11-fix` | `86eda279c82b79c7888558e7a2524db44c7ee108` | `643ed025ee6aa127353e5dd1b02ac4857bb1e406` | `aeff664cf9fd7817a2c699732b150e3691018f73` | 2021-11-22 | Anton Naydenov | unsigned | Support SQUARE brackets [] around NAMED parameter |
| Q12 | `Q12-parent` | `793581ebdeb875ebc13e5a485a0b887db9f5379d` | `80e03a0c53945317308093512cb434cc7dbf027c` | `cc7f3101b79a2d51369d74783839654d0f996b54` | 2023-07-13 | rstoyanchev | unsigned | Add ForwardedHeaderUtils |
| Q12 | `Q12-fix` | `4b80b0f490d43cbb449befa9d2cb8bdd45efee9d` | `54d9b362acd67ce3a0989e5ba0852a2aa9f0c930` | `793581ebdeb875ebc13e5a485a0b887db9f5379d` | 2023-07-14 | René Wittner | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | DataAccessUtils result accessors with Optional return value (#27735) |
| Q13 | `Q13-parent` | `d957f8bb5dee73c4fb2b00eb4596ce273e074b68` | `621eca625ebd06a2645087562f8890a61c6bedb7` | `14767d64b5a5ca98b70eb97f5d77adff59b1deeb` | 2025-07-07 | NeatGuyCoding | good, GitHub web-flow key B5690EEEBB952194 | Fix copy-n-paste errors in JmsClient Javadoc |
| Q13 | `Q13-fix` | `88257f7dfd686671036e0dd12862f27b57d4148c` | `b7161c59e7aab42108dd7a923e8000820d3f51a1` | `d957f8bb5dee73c4fb2b00eb4596ce273e074b68` | 2025-04-03 | Yanming Zhou | unsigned | Discard further rows once maxRows has been reached |
| Q14 | `Q14-parent` | `53783127de602eb41679cf6fdb6b1ff95e07dbad` | `2a927c1bba571f360776b97a2e05b3072d0fc9dd` | `67467f48fa4aef1a3bd227b8b45b11bb7925369b` | 2026-10-30 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |
| Q14 | `Q14-fix` | `610477de45ca9506415961a52b169f7f66079032` | `54f38a0ca34927e8964d4c2b9c5df235025733ee` | `53783127de602eb41679cf6fdb6b1ff95e07dbad` | 2026-10-30 | 김준형 | good, GitHub web-flow key B5690EEEBB952194 | Do not remap constructor properties in SimplePropertyRowMapper |
| Q15 | `Q15-parent` | `803517c0cb950e6647926ece40412ca4442eb8a7` | `909f8ec43ee6dbf1d216c7957668006222215de6` | `8a511726cd8df5bf1d900ac087a6f1e9c8eff6d1` | 2026-09-14 | Juergen Hoeller | unsigned | Upgrade to Tomcat 11.0.25, Jetty 12.1.13, Netty 4.2.18, Protobuf 4.36.1 |
| Q15 | `Q15-fix` | `d571c4097da575c1546a211d410caddefb38d060` | `0cede43986837bf33d80be5725d50c743989761f` | `803517c0cb950e6647926ece40412ca4442eb8a7` | 2026-09-14 | guanchengang | good, GitHub web-flow key B5690EEEBB952194 | Lazily handle setClientInfo/setNetworkTimeout in LazyConnectionDataSourceProxy |
| Q16 | `Q16-parent` | `c17b4ad7874a6e544d09ebaec32c543f1e755577` | `a80b81236e4088280fe537a66d9478e4575e184c` | `e8729d043887bf0d0baf91e062e909b56eb2b708` `b556766e1a103bae48f3baea24c9009711db469b` | 2026-08-05 | Brian Clozel | unsigned | Merge branch '7.0.x' |
| Q16 | `Q16-fix` | `4b5c92703c63966c3471242c621c4a63b382638d` | `0fca841165a6104bace136dc02308b0059609387` | `c17b4ad7874a6e544d09ebaec32c543f1e755577` `7f1966f5f575f033ba402660814e96d339549331` | 2026-08-05 | Brian Clozel | unsigned | Merge branch '7.0.x' |
| Q17 | `Q17-parent` | `8315a4033feea39f04a14c0b088e634b13fe774c` | `540ba8a357a423f72b03c1e6ee2a291f25396e0e` | `1b0e95d7d82435d7c532b597eab7cf86265fdbe1` | 2016-12-07 | bedrin | unsigned | Add consumes attribute to @⁠GetMapping |
| Q17 | `Q17-fix` | `2735cba4b353027ac649b592bc9eb38c473b4fa1` | `f29577fb73ba2e4f8241d6dd81d8f4bd2f52c463` | `8315a4033feea39f04a14c0b088e634b13fe774c` | 2016-11-30 | Sebastien Deleuze | unsigned | Append "data:" after line breaks for SSE JSON data fields |
| Q18 | `Q18-parent` | `1d46b8d7e1dc94b14d2cd913906f5f99054d112d` | `3a0a37c39b5c86821c9a4d80e8cfc73c16bb52a5` | `857e77eec2cc02ffd4b4f1f22808ccbe32351e3f` | 2016-09-20 | Sebastien Deleuze | unsigned | Polish |
| Q18 | `Q18-fix` | `e3da8b5e9cb96eb3cc007197c50d2dd6cc68d34f` | `ea7d0bafa3ccaeea49acb2acf0ebbe5f67e5e3c9` | `3596e720505745ef48678bfce17c8d036943852d` | 2016-09-12 | Brian Clozel | unsigned | Polish ResourceHttpRequestHandler, ResourceEncoder |
| Q19 | `Q19-parent` | `4ca7d89a9222f4e8d0dd4bd32425b33da1358563` | `5bf7d4ab5a3492f47bb1a0e7b4f43f775ce84caa` | `4bf5a0234c6c5c5d6591eb0fa52db3bf09573d9f` `6a323292d8675fb20006b0d12bfb14c329118c4c` | 2013-10-08 | Rossen Stoyanchev | unsigned | Revert resource handling changes |
| Q19 | `Q19-fix` | `e39400ba75438cde38a6022f1637d0613584c004` | `3ad4dd6ba657492966a2ad23f3ffcd0e967b201b` | `4ca7d89a9222f4e8d0dd4bd32425b33da1358563` `e04a7569687a4da98f1c39fbee1ff209715c3fdd` | 2013-10-08 | Brian Clozel | unsigned | Merge e04a7569687a4da98f1c39fbee1ff209715c3fdd into 4ca7d89a9222f4e8d0dd4bd32425b33da1358563 |
| Q20 | `Q20-parent` | `e34c8004676d6ed3caddd1ef8eef8608518175a9` | `3b092a4a26a4fb7903072789ff8a4000d8ede68a` | `c6b87b3ef4a9296131a9c6c478b4ce480ea4c5bd` | 2020-09-01 | Rossen Stoyanchev | unsigned | More updates to Web testing section |
| Q20 | `Q20-fix` | `603d7e93b9ec78d202d643a7c3c53b1e8fa06354` | `166832c63948289dd6c2ff85c221800c271c0654` | `e34c8004676d6ed3caddd1ef8eef8608518175a9` | 2020-08-28 | Johnny Lim | unsigned | Copy httpHandlerDecorator in copy constructor for WebHttpHandlerBuilder |
| Q21 | `Q21-parent` | `16ed0962237dc8245591490b2d4c2f65898b014f` | `4366cdcf1cc6a1e5489ad3af5ecbe98d032b4f17` | `be7874ef542428030d55bdd532cf50b0f45f5fd0` | 2026-10-13 | GeonHee Ryu | unsigned | Fix incorrect class names in WebFlux and MVC docs |
| Q21 | `Q21-fix` | `091097db7982ef04660aa63358d87fc6675b3238` | `9e69d2d8c9603eb430435ec922696125075270fc` | `16ed0962237dc8245591490b2d4c2f65898b014f` | 2026-04-05 | Renato Mameli | unsigned | Map version from @⁠HttpExchange to RequestMappingInfo |
| Q22 | `Q22-parent` | `6e5cf0ce451ad6fa6f65184b603154d85f817df1` | `f0b8e0b3ecceb43200dfe4919427b950b1b791bc` | `a99f4dd43c66cc8fed03b3d0cc216448673c5864` | 2026-08-12 | Hyunsik Kang | unsigned | Do not release body buffers already handed to the sink |
| Q22 | `Q22-fix` | `74a4b1a694f78bc1a04540c748cabe73c239b099` | `7279d29a086e20261315a99ba4a3bbee176606bc` | `6e5cf0ce451ad6fa6f65184b603154d85f817df1` | 2026-07-31 | Gimin Kim | unsigned | Preserve async API version resolver order |
| Q23 | `Q23-parent` | `74f0bcfef6a5eb7a47d71e046eca507d3a959142` | `6b8e814735e893a9e9c00a059ebc057dfabbd332` | `4892cf7a93ce3c679c92c00c383f0caf76645cb6` `d1d77e373a657f6bf16cf50767acf1fcb002078e` | 2026-10-29 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| Q23 | `Q23-fix` | `40c69ef5bb3a1a5fcc3aef63dba682a9ad971bed` | `7001a1ea528e0e72d87cfb46d8a293d141ead6c1` | `74f0bcfef6a5eb7a47d71e046eca507d3a959142` | 2026-10-29 | lejuho | good, GitHub web-flow key B5690EEEBB952194 | Copy builder lists in HttpServiceProxyFactory.Builder#build |
| Q23 | `Q23-later` | `64861cb395e415bf1452d30f54f8e2c0ecc9cb46` | `d94c7178d20bbcbc842aeb5ff7d23efbbae14fda` | `5710c4720b8509e83b61ab891001af81b5e53a82` | 2026-10-29 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |
| Q24 | `Q24-parent` | `2b96a61063f3008ce268271bc947272b178c3bf7` | `5b4e7a102383ae0526829654671793d9047c5414` | `c55351aa4a0d604180bbbfd16dfcbbe6962159c3` | 2026-01-16 | Juergen Hoeller | unsigned | Apply transactionIsolationLock in EclipseLinkConnectionHandle as well |
| Q24 | `Q24-fix` | `3f390d55f0434608d64d02a0478a17d80ed9eb8d` | `8a0454f12daea1e1bd75c58b15dee7d0a93a8983` | `2b96a61063f3008ce268271bc947272b178c3bf7` | 2026-01-16 | Michał Pisarski | unsigned | Add overloaded sendAndReceive methods to JmsOperations and JmsTemplate to use explicit response queue |
| Q25 | `Q25-parent` | `d494621ee3d2e0d6c706f401028b0bbd62491495` | `015e1bc50f9722434c78b20797483364a8017934` | `92efe95069c4fc5969e8f4f4f84ee09c426fba5c` | 2019-11-10 | GungnirLaevatain | unsigned | avoid store all bean name |
| Q25 | `Q25-fix` | `fc55e66d50041893def2490f8f97dbffc9066454` | `33b9a313ec33415487170542c797db8c5e9d287b` | `d494621ee3d2e0d6c706f401028b0bbd62491495` | 2019-10-11 | Steven Schlansker | unsigned | ApplicationListenerMethodAdapter: gracefully handle beans which are actually NullBean |
| Q26 | `Q26-parent` | `ec8689d1fc2dbc40bb345a256db988c312b15381` | `4f91901e6ee7f1d58dda777382934e50f7430088` | `fc8d5c068c67c50a6f9e17c52425ca308ac403c7` `84266d71e92701bf666c0ff1984288cc22056690` | 2019-05-03 | Juergen Hoeller | unsigned | Merge branch '5.1.x' |
| Q26 | `Q26-fix` | `83046531da12dde914fb677b65c2d2b449e039df` | `527181632c073d8a21239970aeb23833c7bfe786` | `9cff07ce35dcca7c1028885492d246b3f4735dfb` | 2019-05-03 | Mark Paluch | unsigned | Replace signal materialization in TransactionalOperator with usingWhen |
| Q27 | `Q27-parent` | `fe783a0efcd58a31fd0c185f0fff34658a4060c6` | `182580b643c94c8fe51fa73190ce315dd7f93274` | `40664f7ced3ab41b29d74ce61bdc8951ab69726d` | 2026-10-21 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Cancel source on write error in ChannelSendOperator |
| Q27 | `Q27-fix` | `76a800d9806b9af93ebeb0f9d3cf7500d9df939d` | `756c482cc34e998138b6c32239d9dfe4e249bc77` | `fe783a0efcd58a31fd0c185f0fff34658a4060c6` | 2026-10-21 | SeungTaek Lim | good, GitHub web-flow key B5690EEEBB952194 | Avoid overflow for default maxDelay with timeUnit |
| Q28 | `Q28-parent` | `eeedeb3b10d0a23eff39c9fb08ba990d94ce42ac` | `a35219d7b03926d579e613194fec0b54ff6d4880` | `60b19278c021d81d913cdce96dfca2cb328d3bfa` | 2025-07-01 | NeatGuyCoding | unsigned | Remove the duplicated “rss” assertion |
| Q28 | `Q28-fix` | `009b880e929f3267a99e8e0b66d8482696f0ba67` | `c8976d68b50f0e8f4d06d187cabdd4d1d420e3d2` | `eeedeb3b10d0a23eff39c9fb08ba990d94ce42ac` | 2025-07-01 | NeatGuyCoding | unsigned | Fix potentially loses precision and jitter is not well capped with unit tests |
| Q29 | `Q29-parent` | `1cdb78d2a64035bdd983919e173fcae0f1336e59` | `9076757392ac446a9273156b9730ae723600837f` | `ffae3af761b78ac8e65d566627c9637f85407b80` | 2026-10-13 | rstoyanchev | unsigned | ServletResponseHeadersAdapter#get optimization |
| Q29 | `Q29-fix` | `85a532dce455655aec8fd5a301b37c6c5ceda5bb` | `9188650fd01ebdcf25f54c5b8f3eff195ad4e4a3` | `1cdb78d2a64035bdd983919e173fcae0f1336e59` | 2026-10-13 | Chengang Guan | good, GitHub web-flow key B5690EEEBB952194 | Add RetryState-aware overloads for onRetrySuccess and onRetryFailure (#37465) |
| Q30 | `Q30-parent` | `f89737e398452f4e5c15f3d8d7ca52683a582845` | `e6a7706acf100a61f06b1c54655002308c10b266` | `ecdf069c5df46c5e15405a1437dcbee00e4f9057` | 2025-11-01 | Sam Brannen | unsigned | Upgrade to JUnit 5.14.1 |
| Q30 | `Q30-fix` | `97586b525f0d20836c6ab319d9d68d396218340e` | `caa497aaf051fe713b5ddeb54e106bb0b812c415` | `f89737e398452f4e5c15f3d8d7ca52683a582845` | 2025-10-31 | Artur Signell | unsigned | fix: Fix PathMatchingResourcePatternResolver to handle absolute paths in JAR manifests |

PR metadata (`gh api`): base branch `main` for 15, `7.0.x` for Q01, Q07, Q14, Q15, Q21, Q22, Q27, `6.2.x` for Q30, and `master`
for Q04, Q10, Q17, Q18, Q19, Q20, Q25, Q26. Merged between 2013-10-08 (Q19) and 2026-10-30 (Q14).

## Toolchain

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` | earlier setups' installations |
| Temurin 24.0.2+12 | `$P/tools/jdk/jdk-24.0.2+12` (`$J24`), from `https://github.com/adoptium/temurin24-binaries/releases/download/jdk-24.0.2%2B12/OpenJDK24U-jdk_x64_linux_hotspot_24.0.2_12.tar.gz` (tarball deleted after unpacking) | sha256 `aea1cc55e51cf651c85f2f00ad021603fe269c4bb6493fa97a321ad770c9b096` = the Adoptium API's and the release's `.sha256.txt` (`$P/dl/jdk/`); **good signature** by the Adoptium key `3B04D753C9050D9A5D343F39843C48A565F8F04B`. Needed by Q13 and Q28: their 7.0.0-SNAPSHOT `buildSrc` sets toolchain language 24. |
| BellSoft Liberica JDK 17.0.21.1+5 | `$P/tools/jdk/jdk-17.0.21.1` (`$JL17`), hard links to the P01–P30 setup's unpacked copy | that setup verified it: sha1 `a44f40d665ddaa9e450a15e2b1f55d1a754630bb` = BellSoft's API, sha256 `add6f8c21289daf20eb38cd8fbd05bc374773038512cae655844e4e9a9a4f3d3`; no signature published. Needed by Q30 (6.2.13-SNAPSHOT `buildSrc` asks for vendor `BELLSOFT`, 17). |
| Gradle 1.6, 3.0, 3.2.1, 4.10.3, 5.4.1, 5.6.4, 6.5.1, 6.6, 6.8.3, 7.3, 8.2, 8.14.2, 8.14.3, 9.3.0, 9.4.1, 9.6.1, 9.7.1, 9.8.0, 9.8.1, 9.8.2 | unpacked in `$P/tools/gradle-V` | zip sha256 = services.gradle.org's `.sha256`, all 20 ([digests](#gradle-distributions)); the ten the P01–P30 setup had verified are hard links to its copies |
| Maven 3.10.0 | on `PATH` (sdkman), settings `$P/maven-settings.xml` (local repository `$P/m2`, plus `repo.spring.io/milestone`) | released artifacts only |

The wrapper is not used: `$P/scripts/gradle_case.sh` runs the verified distribution each checkout's wrapper names, with the launcher
JDK by era (Gradle 9: 25; 7.x–8.x: 17; 1.x–6.x: 8) and only the options that Gradle version knows (no `--console`/`--max-workers`
for 1.x, no `--no-build-cache` for 1.x–3.x, `--no-scan` from 7 on).

### Gradle distributions

zip sha256, each equal to services.gradle.org's `gradle-V-bin.zip.sha256` (`$P/logs/gradle-dists.txt`; the `.sha256` files are
kept in `$P/dl/gradle/`, the zips were deleted after unpacking):

| Gradle | zip sha256 | Gradle | zip sha256 |
|---|---|---|---|
| 1.6 | `de3e89d2113923dcc2e0def62d69be0947ceac910abd38b75ec333230183fac4` | 3.0 | `39c906941a474444afbddc38144ed44166825acb0a57b0551dddb04bbf157f80` |
| 3.2.1 | `9843a3654d3e57dce54db06d05f18b664b95c22bf90c6becccb61fc63ce60689` | 4.10.3 | `8626cbf206b4e201ade7b87779090690447054bc93f052954c78480fa6ed186e` |
| 5.4.1 | `7bdbad1e4f54f13c8a78abc00c26d44dd8709d4aedb704d913fb1bb78ac025dc` | 5.6.4 | `1f3067073041bc44554d0efe5d402a33bc3d3c93cc39ab684f308586d732a80d` |
| 6.5.1 | `50a7d30529fa939721fe9268a0205142f3f2302bcac5fb45b27a3902e58db54a` | 6.6 | `e6f83508f0970452f56197f610d13c5f593baaf43c0e3c6a571e5967be754025` |
| 6.8.3 | `7faa7198769f872826c8ef4f1450f839ec27f0b4d5d1e51bade63667cbccd205` | 7.3 | `de8f52ad49bdc759164f72439a3bf56ddb1589c4cde802d3cec7d6ad0e0ee410` |
| 8.2 | `38f66cd6eef217b4c35855bb11ea4e9fbc53594ccccb5fb82dfd317ef8c2c5a3` | 8.14.2 | `7197a12f450794931532469d4ff21a59ea2c1cd59a3ec3f89c035c3c420a6999` |
| 8.14.3 | `bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531` | 9.3.0 | `0d585f69da091fc5b2beced877feab55a3064d43b8a1d46aeb07996b0915e0e0` |
| 9.4.1 | `2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb` | 9.6.1 | `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` |
| 9.7.1 | `acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a` | 9.8.0 | `bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c` |
| 9.8.1 | `dce76f55f8e251a3a1f130eb120f30b3d271de2b76c9b0729d316b5a1b6dc01f` | 9.8.2 | `21bd5da2de49b642904077f38c0efdc7778e92b3ed0889392dca61b97e389607` |

## Build facts by era

Both pins of every case have the same project version and the same Gradle (`$P/logs/build-facts.txt`).

| Era | Cases | Versions | Gradle | Launcher JDK | Compiles with |
|---|---|---|---|---|---|
| 7.1 | Q02, Q03, Q05, Q06, Q08, Q16, Q23, Q29 | 7.1.0-SNAPSHOT | 9.4.1 (Q02, Q05), 9.6.1 (Q16), 9.8.0 (Q03, Q06), 9.8.1 (Q08, Q29), 9.8.2 (Q23) | 25.0.5 | toolchain 25, `release` 17 |
| 7.0.x | Q01, Q07, Q14, Q15, Q21, Q22, Q24, Q27 | 7.0.4 (Q24), 7.0.10 (Q01, Q15, Q21, Q22), 7.0.11 (Q07, Q14, Q27) -SNAPSHOT | 9.3.0, 9.7.1, 9.8.1, 9.8.2 | 25.0.5 | toolchain 25, `release` 17 |
| 7.0 before GA | Q13, Q28 | 7.0.0-SNAPSHOT | 8.14.3 (Q13), 8.14.2 (Q28) | 17.0.21 | **toolchain 24** (`$J24`), `release` 17 |
| 6.2 | Q30 | 6.2.13-SNAPSHOT | 8.14.3 | 17.0.21 | **toolchain vendor BELLSOFT, 17** (`$JL17`) |
| 6.1 | Q12 | 6.1.0-SNAPSHOT | 8.2 | 17.0.21 | toolchain 17 |
| 6.0 | Q11 | 6.0.0-SNAPSHOT | 7.3 | 17.0.21 | the launcher JDK (17) |
| 5.3 | Q09 | 5.3.9-SNAPSHOT | 6.8.3 | 8 | the launcher JDK (8); **configures only with one repository substitution** ([below](#q09-configures-with-one-substitution)) |
| 5.x, 4.0 | Q04, Q10, Q17, Q18, Q19, Q20, Q25, Q26 | 5.2.0.BUILD (Q04, Q26), 5.3.0 (Q10, Q20), 5.0.0.BUILD (Q17, Q18), 4.0.0.BUILD (Q19), 5.2.2.BUILD (Q25) -SNAPSHOT | 4.10.3, 6.5.1, 3.2.1, 3.0, 1.6, 6.6, 5.6.4, 5.4.1 | (8) | **none configures**, see [below](#the-old-builds-that-cannot-be-configured) |

**Repositories.** Maven Central and the Gradle Plugin Portal serve everything the 6.x and 7.x builds need. `repo.spring.io/release` and
`plugins-release` answer **401** to anonymous requests, as the P01–P30 setup found; `milestone` and `snapshot` answer.

**Online resolution** (inline, each Gradle run in a 6 GB scope; `$P/scripts/resolve_online.sh WORKTREE...`): two passes per
worktree, `-I $P/scripts/resolve-all.init.gradle setupResolveAll -PsetupResolve=Classpath,kotlin,Kotlin,annotationProcessor,AnnotationProcessor`
then `-PsetupResolve=ALL`, over every project of the build (the init script adds tasks `setupResolveAll` and `setupWriteClasspath` to
every project and changes no upstream file). `GRADLE_USER_HOME` was first seeded with a copy of the P01–P30 setup's
`caches/modules-2` (4.1 GB, copied while no Gradle ran there), so most artifacts and that setup's snapshot builds were already
cached. Summaries `$P/logs/resolve-7x.summary.txt`, `$P/logs/resolve-6x.summary.txt`, `$P/logs/resolve-q09.summary.txt`; logs
`$P/logs/WORKTREE.resolve{1,2}.online.log`. All 45 worktrees of the 22 Gradle cases (Q23's `later` included) resolved every configuration of pass 1 (492–559 per worktree).
Pass 2 (718–1,172 configurations) failed only on configurations no compile or test task uses: the Kotlin plugin's IDE-only
`*DependenciesMetadata` (122 per worktree at 7.0.x and 7.0.0, 117 at Q13/Q28, 70 at Q30, 68 at Q12, none at 7.1) and, at Q09 and Q11,
the docs build's `asciidoctorExt` (`io.spring.asciidoctor` extensions, from the 401 repository), as in the P01–P30 setup.

## Q09 configures with one substitution

Q09's root `plugins {}` block (Gradle 6.8.3) takes `org.asciidoctor.jvm.convert` / `.pdf` 3.1.0, which depend on
`org.ysb33r.gradle:grolifant:0.14`, served only by `repo.spring.io/plugins-release` (401). The same coordinates are at
`https://repo.grails.org/grails/core` (`$P/scripts/probe.sh`: 404 at Maven Central, the Plugin Portal, JCenter and the others the
P01–P30 setup probed). `$P/scripts/subst-grails.init.gradle` adds that repository to plugin and build-script resolution, limited
to group `org.ysb33r.gradle`; no upstream file changes. What it fetched (`$P/logs/subst-grolifant.txt`): `grolifant-0.14.jar` sha1
`949573c7de7b18ba84eee03d023834b6133fa238` = Grails core's `.sha1` (sha256 `0b6f7e97e02f57797f4a07d2081dad81b2448a1ba88c81e85951fae4b1898880`), `grolifant-0.14.pom`
sha1 `6fb2a775c2c86bff3560e527edea95ab9d63e8ca` = the repository's; no `.asc` is published. With it both pins configure
(`$P/logs/Q09-parent.help.subst.online.log`) and resolve; `case_job.sh` passes it for Q09. The plugin serves the docs build only.

## The old builds that cannot be configured

Eight cases fail to configure online at both pins, before any project is evaluated, on build-script artifacts that only the 401
repositories served (`$P/scripts/configure_probe.sh`, `$P/logs/old-configure.txt`, logs `$P/logs/CASE-parent.help.online.log`):

| Cases | Gradle | Missing |
|---|---|---|
| Q04, Q26 | 4.10.3, 5.4.1 | `io.spring.gradle:propdeps-plugin:0.0.9.RELEASE` |
| Q25 | 5.6.4 | `io.spring.asciidoctor:spring-asciidoctor-extensions:0.1.3.RELEASE`; `org.jfrog.buildinfo:build-info-extractor:2.13.10` |
| Q10, Q20 | 6.5.1, 6.6 | settings plugin `io.spring.gradle-enterprise-conventions` 0.0.2 |
| Q17, Q18 | 3.2.1, 3.0 | `io.spring.gradle:docbook-reference-plugin:0.3.1`, `org.springframework.build.gradle:propdeps-plugin:0.0.7` |
| Q19 | 1.6 | `org.springframework.build.gradle:propdeps-plugin:0.0.4`, `org.springframework.build.gradle:docbook-reference-plugin:0.2.7` |

The P01–P30 setup looked for the first three rows' coordinates in 16 public repositories and found them nowhere (only
`build-info-extractor:2.13.10` at Grails core, which does not help Q25 without the asciidoctor extensions). The last two rows'
coordinates were looked for here the same way (`$P/logs/probe-old-plugins.txt`): 404 everywhere, 401 at `repo.spring.io/release`,
`plugins-release` (and JitPack). Nothing was substituted. Their changed files are built and their landed tests run on the
[slice route](#the-slice-route) instead.

## The slice route

The route the P01–P30 setup used for its 5.x cases, as the user decided on 2026-11-26: the released jars whose changed source
files match the pin's, and the pin's own changed files compiled against them. For each case and pin
(`$P/scripts/slice_case.sh CASE`, table `$P/scripts/slices.tsv`, all eight in under a minute each, inline in the probe cap, log
`$P/logs/slices.txt`):

1. **Slice.** The pin's changed production files (`src/main/java` lines of `$P/logs/CASE-landed-files.txt`) compiled by `javac`
   1.8.0_512 (`$J8`, `-source 8 -target 8 -parameters -proc:none -implicit:none`) against the **base release** set and the test
   libraries, into `$P/slices/CASE-ROLE/main/`, jarred as `$P/slices/CASE-ROLE/CASE-ROLE-slice.jar`, class digests in
   `$P/slices/CASE-ROLE/main.SHA256SUMS`. Two cases also take one **unchanged** production file of the same pin
   (`slices.tsv` column 9), because the base release changed that API afterwards: Q17 `spring-web/.../http/ReactiveHttpOutputMessage.java`
   (the pins' test mocks implement `writeWith(Publisher<? extends DataBuffer>)`; 5.0.0.M3 declares `Publisher<DataBuffer>`, the same
   erasure), Q18 `spring-web/.../http/codec/AbstractServerHttpMessageWriter.java` (5.0.0.M2 adds the abstract `resolveWriteHints`
   the fix's `ResourceHttpMessageWriter` does not implement). Both pins of a case use the same base and the same extra file.
2. **Tests.** The landed test classes compiled from the pin's own test tree (`-sourcepath` over the test and test-fixture dirs of
   `slices.tsv` column 5, so the helpers they use come from the same pin), with the test libraries at the versions that pin's build
   declares (`$P/releases/tests-CASE/`), then run on JDK 8 with the JUnit Platform console launcher (JUnit 4 classes through the
   vintage engine). Classpath: slice, test classes, the module's test resources, base release, test libraries. Results per run in
   `$P/slices/CASE-RUN/` (`junit.log` with every test, `reports/` JUnit XML, `javac-*.log`).
3. **Runs.** `fix`: the fix pin's tests on the fix slice. `parent`: the parent pin's own versions of those classes that exist there,
   on the parent slice. `transplant`: the fix pin's tests on the parent slice. `release`: the fix pin's tests on the base release
   alone, without a slice. `$P/scripts/slice_one.sh CASE SLICEROLE TESTROLE TAG CLASS...` runs chosen classes only; it was used
   where the whole transplant does not compile because other landed tests use API the landing adds.

**Which release matches which pin** (git blob ids of the changed files in released `-sources.jar`s, Maven Central or
`repo.spring.io/milestone`, jar sha1 = the repository's; `$P/scripts/release_compare.sh`, `$P/logs/CASE-release-blobs.txt`; where no
blob matches, the number of differing code lines with comments and blank lines removed, `$P/scripts/release_codediff.sh`,
`$P/logs/old-release-codediffs.txt`). Two sources jars (spring-web 5.0.0.M4 and M5) hold some entries twice with the same bytes;
the blob script reads one copy and checks they are equal.

| Case | Changed production files | Parent pin = | Fix pin = | Base release set |
|---|---|---|---|---|
| Q04 | spring-beans `AutowireUtils`, spring-test `SpringExtension`, `ParameterAutowireUtils` (deleted by the fix) | no release exactly: `AutowireUtils` = 5.2.0.M1 in code (comments only differ); `SpringExtension` 4 code lines from 5.1.5/5.1.6, 10 from 5.2.0.M1; `ParameterAutowireUtils` 8 from 5.1.5 | **none, and the landed API never shipped**: the fix's `public` `AutowireUtils.isAutowirable`/`resolveDependency` are absent from 5.2.0.M1 to 5.2.0.RELEASE, where `AutowireUtils` is package-private again and the feature is `org.springframework.beans.factory.annotation.ParameterResolutionDelegate` (fix `AutowireUtils` 68 code lines from 5.2.0.M1) | `spring-5.2.0.M1-q04` (spring-beans, spring-context, spring-test 5.2.0.M1) |
| Q10 | spring-context `CronTrigger`, `CronSequenceGenerator`, new `CronExpression`, `CronField` | **5.3.0-M1 and 5.2.8.RELEASE** (both files, exact blobs) | `CronTrigger`, `CronSequenceGenerator` = **5.3.0-M2, RC1, 5.3.0** exactly; `CronExpression` 27 and `CronField` 156 code lines from 5.3.0-M2 (reworked after the landing) | `spring-context-5.3.0-M1` |
| Q17 | spring-web `Jackson2JsonEncoder`, `ServerSentEventHttpMessageWriter`, `AbstractJackson2HttpMessageConverter` | **5.0.0.M3** (all three, exact) | `Jackson2JsonEncoder`, `AbstractJackson2HttpMessageConverter` = **5.0.0.M4** exactly; `ServerSentEventHttpMessageWriter` = 5.0.0.M4 in code | `spring-web-5.0.0.M3-q17` (with jackson-databind 2.8.5 and reactor-core 3.0.3.RELEASE, the pins' versions) |
| Q18 | spring-core `ResourceEncoder`, new `ResourceRegionEncoder`, `DataBufferUtils`, `ResourceUtils`; spring-webmvc `ResourceHttpRequestHandler`; spring-web-reactive `ResourceWebHandler`; spring-web `ResourceHttpMessageWriter`, new `ResourceRegionHttpMessageWriter` | **none**: 5.0.0.M1 has no `ResourceWebHandler` (and no `org.springframework.web.reactive.resource`); `ResourceUtils` = M1–M3 exactly; the rest 2–82 code lines away | **none**: `ResourceEncoder`, `DataBufferUtils` = **5.0.0.M2** exactly, `ResourceHttpRequestHandler` = M2 in code; `ResourceWebHandler` 5, `ResourceRegionEncoder` 14, `ResourceRegionHttpMessageWriter` 13, `ResourceHttpMessageWriter` 37 code lines from M2; `ResourceUtils` 14 from every release | `spring-5.0.0.M2-q18` (spring-core, -web, -webmvc, -web-reactive 5.0.0.M2, reactor-core 3.0.2.RELEASE, jackson 2.8.3, servlet-api 3.1.0): the nearest release, which already contains part of the fix |
| Q19 | spring-test-mvc `MockMvcResultMatchers` (published inside `spring-test`) | **4.0.0.M3** exactly | none: 14 code lines from 4.0.0.RC1, 26 from 3.2.5 | `spring-test-4.0.0.M3-q19` (spring-test, spring-webmvc 4.0.0.M3, servlet-api 3.0.1, hamcrest 1.3) |
| Q20 | spring-web `WebHttpHandlerBuilder` | none: 1 code line from 5.3.0-RC1, exactly the fix's `this.httpHandlerDecorator = other.httpHandlerDecorator;`; 13 from 5.3.0-M2 and 5.2.8/5.2.9 | **5.3.0-RC1** in code | `spring-web-5.3.0-RC1-q20` (spring-web, spring-context 5.3.0-RC1, reactor-core 3.4.0-M2 of the pins' `reactor-bom:2020.0.0-M2`) |
| Q25 | spring-context `ApplicationListenerMethodAdapter` | **5.2.1.RELEASE** exactly | **5.2.2.RELEASE** in code (the parent differs from it by the fix's `if (bean.equals(null)) { return null; }`) | `spring-context-5.2.1.RELEASE-q25` (with reactor-core 3.3.0.RELEASE, javax.inject 1, validation-api 1.1.0.Final, hibernate-validator 5.4.3.Final, javax.el 3.0.1-b08: the optional and test-runtime libraries the pins' `spring-context.gradle` declares) |
| Q26 | spring-tx `AbstractReactiveTransactionManager`, `TransactionalOperatorImpl` | **none** (5.2.0.M1 has neither file; M2 41 and 13 code lines away) | **none** (M2 32 and 6 code lines away) | `spring-tx-5.2.0.M2-q26` with reactor-core and reactor-test **3.3.0.M1** (`reactor-bom:Dysprosium-M1`, what the `v5.2.0.M2` tag imports) |

**Results** (`$P/logs/slices.txt`):

| Case | Test classes | Fix (fix tests on fix slice) | Parent (parent tests on parent slice) | Transplant (fix tests on parent slice) | Release control (fix tests, base release alone) |
|---|---|---|---|---|---|
| Q04 | `AutowireUtilsTests` | 4 pass | 1 pass | **does not compile**: `AutowireUtilsTests.java:106`, `:116`, cannot find the new `public` `AutowireUtils` methods | does not compile (same) |
| Q10 | `CronTriggerTests`, `CronExpressionTests`, `CronFieldTests` (the last two new) | 148 pass | 112 pass (`CronTriggerTests`) | **does not compile** (`CronExpressionTests.java:41`: the new `CronExpression`); the fix's `CronTriggerTests` alone (`slice_one.sh`, run `Q10-transplant-trigger`) **fails** 2 of 112: `testNonExistentSpecificDate` [1] (PST) and [2] (CET), `IllegalArgumentException: Invalid cron expression "0 0 0 31 6 *" led to runaway search for next trigger` | does not compile |
| Q17 | `ServerSentEventHttpMessageWriterTests`, `MappingJackson2HttpMessageConverterTests` | 69 pass | 62 pass | **fails** 7 of 69: `MappingJackson2HttpMessageConverterTests#prettyPrintWithSse` and `ServerSentEventHttpMessageWriterTests#encodePojoWithPrettyPrint` under each of its six buffer factories (Netty unpooled and pooled, direct and heap; `DefaultDataBufferFactory` direct and heap), each `expected:<{` (the indented continuation lines lack their `data:` prefix) | does not compile: the pins' test mocks need the pins' `ReactiveHttpOutputMessage` |
| Q18 | `ResourceRegionEncoderTests`, `ResourceHttpMessageWriterTests`, `ResourceRegionHttpMessageWriterTests` (new), `DataBufferUtilsTests`, `ResourceWebHandlerTests` | 88 pass, **6 fail** (below) | 43 pass, the same **6 fail**; 7 skipped: the parent's own `ResourceWebHandlerTests` has its seven `partialContent*` tests `@Ignore`d | **does not compile** (`DataBufferUtilsTests.java:108`: new `skipUntilByteCount`; `ResourceHttpMessageWriterTests.java:84`: new `write` signature); the fix's `ResourceWebHandlerTests` alone (run `Q18-transplant-handler`) **fails** 13 of 32: the 7 range tests `partialContentByteRange`, `partialContentByteRangeNoEnd`, `partialContentByteRangeLargeEnd`, `partialContentSuffixRange`, `partialContentSuffixRangeLargeSuffix`, `partialContentInvalidRangeHeader`, `partialContentMultipleByteRanges`, and the same 6 | 86 pass, 8 fail (the 6, `ResourceHttpMessageWriterTests#shouldThrowErrorInvalidRange`, `ResourceWebHandlerTests#partialContentInvalidRangeHeader`) |
| Q19 | `MockMvcResultMatchersTests` (new), `UrlAssertionTests` | 10 pass | 2 pass | **does not compile**: `UrlAssertionTests.java:21`, `:23` and `MockMvcResultMatchersTests.java:35`: no `redirectedUrlPattern` / `forwardedUrlPattern` | does not compile |
| Q20 | `WebHttpHandlerBuilderTests` | 6 pass | 6 pass | **6 pass**: the landed test does not detect the parent (it never calls `clone()`, as the brief says) | 6 pass |
| Q25 | `AnnotationDrivenEventListenerTests` | 35 pass, 1 skipped | 34 pass, 1 skipped | **fails** 1 of 35: `missingBeanDoesntCrash`, `IllegalStateException: The event listener method class '...AnnotationDrivenEventListenerTests$MyEventListener' is not an instance of the actual bean class 'org.springframework.beans.factory.support.NullBean'` | fails the same 1 |
| Q26 | `ReactiveTransactionSupportTests`, `TransactionalOperatorTests` | 14 pass | 14 pass | **fails** 5 of 14: `ReactiveTransactionSupportTests#commitWithoutExistingTransaction`, `#rollbackWithoutExistingTransaction`, `#rollbackOnlyWithoutExistingTransaction`, `#transactionTemplate`, `#transactionTemplateWithException` | 14 pass (5.2.0.M2 already has the cleanup subscription) |

The skipped Q25 test is `listenersReceiveEarlyEvents`, `@Disabled` upstream. Q18's six failures on both slices are
`ResourceWebHandlerTests#getResource`, `#getResourceHttpHeader`, `#getResourceFromSubDirectory`, `#getResourceFromAlternatePath`,
`#getResourceFromSubDirectoryOfAlternatePath` (expected `text/css` or `text/javascript`, got `application/octet-stream` or no
content type) and `#directoryInJarFile` (expected no status, got 404): media-type lookup and a jar-directory case that depend on the
rest of 5.0.0.M2, not on the landing; none of them is a range test.

**Substitutions in the test libraries** (each recorded in `slices.tsv` and the sets' `pom.xml`): Q19's pins declare JUnit 4.11, but the
console launcher's vintage engine refuses anything older than 4.12, so `tests-Q19` has 4.12. Q17 and Q18 add `netty-buffer` (4.1.6.Final,
4.1.5.Final, the pins' `nettyVersion`) for the shared `AbstractDataBufferAllocatingTestCase`. The console launcher is
`junit-platform-console-standalone` at the pin's platform version where it has one (1.4.0, 1.4.2, 1.5.2, 1.6.2, 1.7.0-RC1) and 1.6.2
for the JUnit 4-only pins.

**What the slice route does not give.** Every other class of the modules and their dependencies is the base release's, not the pin's,
so a test or scenario touching code that moved between that release and the pin sees the release. Where no release equals a pin,
the slice is the only build of that pin's changed files. Only the landed test classes ran.

**Slice class digests (sha256)** of the top-level classes; nested classes are in `$P/slices/CASE-ROLE/main.SHA256SUMS`. They are compiled
from the pins' files by JDK 8, not the released jars' bytes.

| Case | Class | Parent pin | Fix pin |
|---|---|---|---|
| Q04 | `AutowireUtils.class` | `3f858196b01392f563cafc0669142accc28caefc906a0295ff65ab8d890ab3de` | `beb75068fbe2374ea053eeae18da2bc374c3103ebd311762debbc6abbf8de690` |
| Q04 | `ParameterAutowireUtils.class` | `a7dca0557360b4339bdbbb3c73e4adb0da26ef5d6f45dc34f554482581377fa1` | absent |
| Q04 | `SpringExtension.class` | `645b90f30931f4cc052c70c5d3c3f2e78cef239c8779242109097a334c0671e6` | `197854124fff0ab6f1e6f7802188aa54daf1fedfac6cfd40527aa0e129b118e8` |
| Q10 | `CronExpression.class` | absent | `0d90c35f66468bae45bcc295dd9553bd47185f94f54bea5e4b16908bedd9e54a` |
| Q10 | `CronField.class` | absent | `fe1b1073ac22e9dbf96b6bc43ee1325b9ebf76242fa94671667af747670e7e58` |
| Q10 | `CronSequenceGenerator.class` | `7ea9ba64911624dcbf08f1b0431d9b996f88df454cdc29dd746a86cc120ebf9b` | `c19275b75359f444eed24f8827065db0040c7d851aa5abdc3aeba036e1f71ecf` |
| Q10 | `CronTrigger.class` | `8cf63d232f2bcce5e34eda4be4ea18b1570d688fd383a30625638d26e315ddee` | `f5facb1e59076acfa8df854104217f7f7efc4d244e82e5ced16fd0b99ca32c80` |
| Q17 | `ReactiveHttpOutputMessage.class` | `cbaef1650b61501d9eea130e83a0578c66ba02b94c0fef674981a089e6d9b9fc` | the same |
| Q17 | `ServerSentEventHttpMessageWriter.class` | `a5f07e8639576a734c0cc6843eda186c8120f2473d9900fc4664473193c9fff5` | `c4eda64255f5b6761127b31c69ec6c45d740a3e471e50e89ab03c33120367d00` |
| Q17 | `Jackson2JsonEncoder.class` | `7c4a67be4943ed088e7ddb9ab6bfe5fa8aa685099df69ff2a1f2a2f3f796f99e` | `e323262edfa19cabee4306092f1da60bc547b588c8417914e2aef435b99aa022` |
| Q17 | `AbstractJackson2HttpMessageConverter.class` | `0991c45c52599ef8839bbc9bbaa5fe43f1b38714d1c0d2dad3398211694eface` | `86f26f11618d17ccd6749fc1a48a6232f76573e85a090093012b800681fb2e67` |
| Q18 | `ResourceEncoder.class` | `938723aabc8d6d52056cda85360e859a4fb71f3af5e9cfbcdd7541d7c2d80724` | `8886ca1500e238e1165c6449ad5f6b1b020bcaa26ecba478ceb3f2993af2b5a5` |
| Q18 | `ResourceRegionEncoder.class` | absent | `60be009b7320f9d6889c7972d3b76e5b93040caadaf0b574144d302c76013674` |
| Q18 | `DataBufferUtils.class` | `0c613ce31d1cf20a0b48b905fef6aaf7629d0b002360e6fafd35394590402732` | `d1e342f2d1ddcc0890cb47a4b36305a424d9552f8de68e266cc5b375e064e027` |
| Q18 | `AbstractServerHttpMessageWriter.class` | `41d01d68d911990c8b7c6364c4a793ec2eace2e5f1fb55c0773fdaabb0d34dce` | the same |
| Q18 | `ResourceHttpMessageWriter.class` | `98a2447a3a752e0933cf85482bfff56876be23b032bf4aef1e8c1842fe11cbd8` | `1dbaf5dc625e2977dcc01fef66c53ad0ad38cce70e6208ea34872960ec5f8c00` |
| Q18 | `ResourceRegionHttpMessageWriter.class` | absent | `310367bbc78bc5cab5a597627f53263cc72b163a9c7ec970da9e2117d47ac45a` |
| Q18 | `ResourceUtils.class` | `6b11f41420ed15a1fd65d4af5b0a12d9baa7495f92a278cbfa26fc88f56e73bb` | `a87e110b3679be00876123abb168464d75c7e98504c1e78abf70acab195845e0` |
| Q18 | `ResourceWebHandler.class` | `1c8c3ca5eefbc13ec1b86ae83c0a0f4da9f8a27975b64831a8495221faef6eea` | `cb55455db8d2b84019c405cc4a9dd630d20e2b617856bf48e3070283eb2c6056` |
| Q18 | `ResourceHttpRequestHandler.class` | `e20a0ca319abc7bef7eddcc8fe59b14aa0780f7a5ae63bfaf2d7eb8ade65ae6a` | the same |
| Q19 | `MockMvcResultMatchers.class` | `242f843207f3ef41830c09ba260465deed55d63fe9abe197e05876e3a5205e20` | `cc02d98eef790fbcfa9863dd38fcffacd482338bfc590dc767dc7fb9a4625982` |
| Q20 | `WebHttpHandlerBuilder.class` | `e194325ebe7834c46217de92a676595946dd30412db710c42428453822848c14` | `b19f2da0410c0c3e33a37cdcc62c0a43b3c67ac8706844c92766d149d5b23905` |
| Q25 | `ApplicationListenerMethodAdapter.class` | `0d5c8c9a04dba9b2baa4e9f0aad976852f2d11e8181b6e9ea1e84603a696333a` | `5532a9e70b284fe0c77e301566341a28cc67059a27f79abc001c339c073be581` |
| Q26 | `AbstractReactiveTransactionManager.class` | `ce05936b569ad0c79253c403d3735bffec9d780ccf299b3b1b365535842e9b4d` | `e6c7d1806562db45e143c065c23ea8fee7f55968b95c94661e9d785854fff651` |
| Q26 | `TransactionalOperatorImpl.class` | `58d327d3b3592dcee913891f1f7c93f13133c65efe849e29b47b84a1527b4ad1` | `0b2e43050e8c0c4018ef1ae8a885d28710a784de44f747b9056764a39de48dca` |

## Released artifacts

From Maven Central, or `repo.spring.io/milestone` for milestones and RCs, resolved with Maven into `$P/m2`
(`$P/scripts/release_set.sh SET "BOMS" "COORDS"`, a generated pom per set in `$P/releases/SET/pom.xml`, runtime scope); each set has
its jars in `$P/releases/SET/jars/` and a `:`-joined `classpath.txt` of `$P/m2` paths. Every jar's sha1 equals its repository's
`.sha1` (192 of 192); `.asc` signatures were fetched and checked in `$P/gnupg`, getting keys from keyserver.ubuntu.com /
keys.openpgp.org (`$P/scripts/verify_releases.sh`, results with sha256 in `$P/logs/release-verify.txt`). Spring's optional
dependencies are not in its 5.x poms, so their versions come from the pins' build files. Sources jars for the blob comparisons are
in `$P/dl/sources/` (sha1 checked against the repositories').

| Set | Why | Main jar sha256 | Signature |
|---|---|---|---|
| `spring-5.2.0.M1-q04`, `tests-Q04` | Q04 slice base and test libraries (JUnit 4.12, Jupiter 5.4.0, Mockito 2.24.0, Hamcrest 1.3) | spring-beans `c583d8355a691ad4dd3105bc328fed10530d1be9141407f090cd36a2b76b420e`, spring-test `9cdcd7032469a4b40108bb19300587808e2ddcb9972cfc13c271aa56ad99bbad` | milestone, no `.asc` |
| `spring-context-5.3.0-M1`, `tests-Q10` | Q10 slice base (= parent's files); Jupiter 5.6.2, AssertJ 3.16.1, joda-time 2.10.6 | `3b112145c57a1e2dadb95dac6f32d3d91db159557a502417594ae46ff8545157` | milestone, no `.asc` |
| `spring-web-5.0.0.M3-q17`, `tests-Q17` | Q17 slice base (= parent's files), with jackson-databind 2.8.5 (the version the brief names) and reactor-core 3.0.3.RELEASE; JUnit 4.12, Mockito 2.2.11, reactor-test, xmlunit 2.2.1, netty-buffer 4.1.6.Final | `c258810782b292d5bcdb9e52449db63ab1bff2fffc273094e5ea894d78584f95` | key `23EF3D2F93185045` not obtainable |
| `spring-web-5.0.0.M4-q17` | Q17's nearest fix release (two files exactly, one in code), not used by the slices | `68edf41b5c2abe03823504e7d98cfb8b02920d3fe4e9b6c438ae18adefa297ed` | key `23EF3D2F93185045` not obtainable |
| `spring-5.0.0.M2-q18`, `tests-Q18` | Q18 slice base: spring-core `b29650492532bb99d1ff572adaaf8f84f09205de261e1b1cfcfd8d0e66d1e0ae`, spring-web `c1b0683824f9fdf85e7e96577304e64d3e4845cde40be1b1c55c3fbc608a0c99`, spring-webmvc `bf90c3ff17c141e5f5819d15cc659a32f24e1bf6c370f1e7eca89eebcea67745`, spring-web-reactive `5fd937dcc1faf305caca982bfdc6393511d04a983328083458345df582199da9`; JUnit 4.12, Mockito 1.10.19, netty-buffer 4.1.5.Final | (left) | key `23EF3D2F93185045` not obtainable |
| `spring-test-4.0.0.M3-q19`, `tests-Q19` | Q19 slice base (= parent's file), with spring-webmvc 4.0.0.M3 and servlet-api 3.0.1; JUnit 4.12 (see the substitution above) | `95d0054a3de3b848ef51da9c3a72357230fa82c491f18eefde345018a5646d50` | key `23EF3D2F93185045` not obtainable |
| `spring-web-5.3.0-RC1-q20`, `tests-Q20` | Q20 slice base (= fix's file in code), with spring-context 5.3.0-RC1, reactor-core 3.4.0-M2; Jupiter 5.7.0-RC1, AssertJ 3.17.1, reactor-test | `01dfbc1a93ad9f8ce20c7971feb287975bbef71bb5af549d14672fae014f5703` | RC, no `.asc` |
| `spring-context-5.2.1.RELEASE-q25`, `tests-Q25` | Q25 slice base (= parent's file); Jupiter 5.5.2, AssertJ 3.14.0 | `6cb3857655efecdb28ab57ca31f53d8607fb119dc4e0d1ab4c7754aebcf005a5` | key `9A2C7A98E457C53D` not importable |
| `spring-tx-5.2.0.M2-q26`, `tests-Q26` | Q26 slice base with reactor-core/reactor-test 3.3.0.M1; JUnit 4.12, Mockito 2.27.0, AssertJ 3.12.2 | `4151f80c1517d5578e3d1c0b642d98ad4b4dde925ec7f96af4d4910c5a75bb82` | milestone, no `.asc` |
| `spring-core-6.2.13` | Q07: the PR reports the failure in 6.2.13 | `c4d1fb7e1f7016f41ead5b615d9cf42f7f48cbb84b7e20b581025d326e2bc5f8` | good, `928FBF39003C0425` (Spring Builds) |
| `spring-context-7.0.9` | Q27: reported with Framework 7.0.9 (Spring Boot 4.0.8 not fetched: the brief's scenario does not use Boot) | `7552a2fcfa30cea53eb14d7a65a7a8e1b1dd82e832a7164fb7e6fb105f438858` | good, `928FBF39003C0425` |
| `spring-jms-7.0.4` | Q24: issue #36321 reports intermittent loss in 7.0.4; with jakarta.jms-api 3.1.0 | `645ffd3487f80643650ec6bbdde717a915cec9028b4994fbf5331098cbf504d3` | good, `928FBF39003C0425` |
| `spring-webmvc-4.3.3.RELEASE` | Q17: SPR-14899 reports the servlet `SseEmitter` failure on 4.3.3; with jackson-databind 2.8.3 (the `v4.3.3.RELEASE` era's) and servlet-api 3.1.0 | `aaf64539b560ba27077cd7722016dca7b5d7efb8292ccc0df23ad12ae0815365` | key `9A2C7A98E457C53D` not importable |
| `r2dbc-postgresql-arabba-sr10` | Q11: the PostgreSQL R2DBC driver that the pins' own `io.r2dbc:r2dbc-bom:Arabba-SR10` manages, `io.r2dbc:r2dbc-postgresql:0.8.8.RELEASE` (with r2dbc-spi 0.8.5.RELEASE, the pins' SPI, and **reactor-netty 0.9.20 / reactor-core 3.3.17**, the Reactor 2020.0 line's predecessor) | `53ad277b5398440be1077cca7cc6fa6b5ef64e36c9a867638f1c93de218d4565` | good, `4406B84C1661DCD1` (Mark Paluch) |

Signature summary over the 192 jars: 90 good signatures, 9 good by keys expired since (Jackson 2.8 `C9FBAA83A8753994`, AssertJ
`E2B3D84202B812D9`, classmate and jackson-annotations `9CD8549ACF9BD0CE`, reactive-streams 1.0.2 `11509ED50EC155E6`), 6 by a key
revoked since (byte-buddy `BB2914C1FA0811C3`), 48 unchecked because the key cannot be imported (Spring's and Reactor's
`9A2C7A98E457C53D`, which keyservers return without a user id, 19; the 4.0 and 5.0 milestones' `23EF3D2F93185045`, 28;
reactive-streams 1.0.3's `1364C5E2DF3E99C5`, 1), and 39 without an `.asc` (Spring 5.2/5.3 milestones and RCs, Reactor milestones,
JUnit 5.7.0-RC1, and a few others). Their sha1s match the repositories'.

**A PostgreSQL server for Q11** was not set up: choosing one is the domain work's. Docker 29.9.3 answers for this user and already
holds the images `postgres:16` (`07abc3f43c93`) and `postgres:17` (`0d938e975177`), pulled by other work; nothing was pulled here.

## Snapshot dependencies

Five pin pairs import snapshot BOMs (`$P/logs/snapshot-boms.txt`): Q08, Q16, Q29 (7.1.0-SNAPSHOT) `reactor-bom:2026.0.0-SNAPSHOT` and
`micrometer-bom:1.18.0-SNAPSHOT`; Q21, Q27 (7.0.10/7.0.11-SNAPSHOT) `reactor-bom:2025.0.8-SNAPSHOT` and `micrometer-bom:1.16.8-SNAPSHOT`;
Q11 (6.0.0-SNAPSHOT) `reactor-bom:2020.0.14-SNAPSHOT` (Q10's `2020.0.0-SNAPSHOT` and `rsocket-bom:1.1.0-SNAPSHOT` are moot: its build
does not configure). `repo.spring.io/snapshot` serves each snapshot only as its newest build, so that is what the cache holds: every
cached snapshot jar's sha1 equals the newest build's `.sha1` (`$P/scripts/snapshots.sh`, `$P/logs/snapshots.txt`). Those builds are
dated after the pins for the 7.1 cases (Reactor 3.9.0-SNAPSHOT `20261110.081737`, Micrometer 1.18.0-SNAPSHOT `20261116.155816`;
the pins are from 2026-08-05 to 2026-10-20) and for Q21 (Reactor 3.8.8-SNAPSHOT `20261016.063046`, Micrometer 1.16.8-SNAPSHOT
`20261015.224611`; Q21's pins are of 2026-10-13), before Q27's pins (2026-10-21), and for Q11 two days before its merge (Reactor
3.4.13-SNAPSHOT `20211212.180947`, reactor-netty 1.0.14-SNAPSHOT `20211214.094426`; merged 2021-12-14T10:24). Both pins of a case read
the same bytes. The 7.1 and 7.0.x snapshot jars came with the cache seeded from the P01–P30 setup and are the same bytes it recorded.
Build `--offline` to keep them.

| Module | Build | sha256 |
|---|---|---|
| `io.micrometer:micrometer-commons:1.16.8-SNAPSHOT` | `1.16.8-20261015.224611-46` | `8896390e5230d3590160cb9475fb8d0c667135457b4c18ad3271e9aa96ea94ee` |
| `io.micrometer:micrometer-commons:1.18.0-SNAPSHOT` | `1.18.0-20261116.155816-314` | `1b3add3a081c9e9390fe3305dff43db944ea7a39b9a50a03acb1e3e65497eff9` |
| `io.micrometer:micrometer-core:1.16.8-SNAPSHOT` | `1.16.8-20261015.224611-46` | `dc733af940f3a820a2e9625adfc67f9759f64266761fbfdd2f5342a9b3a463c0` |
| `io.micrometer:micrometer-core:1.18.0-SNAPSHOT` | `1.18.0-20261116.155816-313` | `048dcfc51a98e344c22bc17720bceca999f65f7a5fd403a967b7aea296547fa6` |
| `io.micrometer:micrometer-jakarta9:1.16.8-SNAPSHOT` | `1.16.8-20261015.224611-46` | `5dbc34bd1643579b6e969cabc683034c645e983f577950aa65e54e8503a6f558` |
| `io.micrometer:micrometer-jakarta9:1.18.0-SNAPSHOT` | `1.18.0-20261116.155816-315` | `c5809b29a8458dd9128ff5e5f5beda7cdad73bbe72527f4b990a1c29a90fe6b1` |
| `io.micrometer:micrometer-observation:1.16.8-SNAPSHOT` | `1.16.8-20261015.224611-45` | `7769f0658e3edb9c3c43c2bbced067f91c83f952d6b427085e3c1b961be0b08a` |
| `io.micrometer:micrometer-observation:1.18.0-SNAPSHOT` | `1.18.0-20261116.155816-315` | `e1c8305e6b8e30563012c3aa6cea565a9367ba773202386e8015efa5a46e6964` |
| `io.micrometer:micrometer-observation-test:1.16.8-SNAPSHOT` | `1.16.8-20261015.224611-45` | `86f3f8440c40b4059e5475f1075e24d04c395643722c57dfbb0d95c6532b9e8e` |
| `io.micrometer:micrometer-observation-test:1.18.0-SNAPSHOT` | `1.18.0-20261116.155816-315` | `d4e85b7504c8621ba20e56a11bf4c0ff062b03a0b553bfce6d9e24c6d37da742` |
| `io.projectreactor.netty:reactor-netty-core:1.0.14-SNAPSHOT` | `1.0.14-20211214.094426-54` | `04094a9ae1adeb4352160bf68997d6aea5998e5501413dcdba11c95054fdd704` |
| `io.projectreactor.netty:reactor-netty-core:1.3.8-SNAPSHOT` | `1.3.8-20261022.061939-75` | `ac7cd43ce95945d47e8ae09edd61593b481264559d265d3a351461138731d08a` |
| `io.projectreactor.netty:reactor-netty-core:1.4.0-SNAPSHOT` | `1.4.0-20261113.130354-170` | `eec27fecf961e887aa8ec1d1add4173556bf46d9ca87c429295ae93c2ebbba03` |
| `io.projectreactor.netty:reactor-netty-http:1.0.14-SNAPSHOT` | `1.0.14-20211214.094426-54` | `42b394ca13d77a953788fe143156399913b1b900b577abe0cefe9a3d061ed6a6` |
| `io.projectreactor.netty:reactor-netty-http:1.3.8-SNAPSHOT` | `1.3.8-20261022.061939-75` | `9dc96a3224eea8672f4911e4916ad302e32b63a8b3e29b623b4db49516a0196f` |
| `io.projectreactor.netty:reactor-netty-http:1.4.0-SNAPSHOT` | `1.4.0-20261113.130354-169` | `e28e59e57bb53e643b71f8ec5aa253db868cbb5190bcd4ea67509c9d44533e55` |
| `io.projectreactor:reactor-core:3.4.13-SNAPSHOT` | `3.4.13-20211212.180947-6` | `14aa5a047ca92267422176482176c255db19bf570fae78e4ff67794f193a6546` |
| `io.projectreactor:reactor-core:3.8.8-SNAPSHOT` | `3.8.8-20261016.063046-46` | `dd6f6961fb3ec2148e3c8c7e0be6d2d534a5edb0d125797ee01e65cacdaadfa5` |
| `io.projectreactor:reactor-core:3.9.0-SNAPSHOT` | `3.9.0-20261110.081737-24` | `51436b9a3967185ee445d5db4053c5c43886465121383f6196d8f383a66bfc72` |
| `io.projectreactor:reactor-test:3.4.13-SNAPSHOT` | `3.4.13-20211212.180947-6` | `f92ff8d74d43f1b47ef40658dc4d5a3228c1cee35ddbc98e7b049d0aab5ea1c0` |
| `io.projectreactor:reactor-test:3.8.8-SNAPSHOT` | `3.8.8-20261016.063046-44` | `7875d014ee565d139a5001c128054e5e89124588518f66b0f5befdad76577bd5` |
| `io.projectreactor:reactor-test:3.9.0-SNAPSHOT` | `3.9.0-20261110.081737-23` | `129ede5ed343d6996fa427f48ffb29d56d0b7a6814d006c00e3c644a985b44a3` |

The cache also holds the snapshot builds of the P01–P30 setup's 6.0.5 pins (Reactor 3.5.3, reactor-netty 1.1.3, Micrometer 1.10.4), which no Q pin uses.

## Jobs

One job per Gradle case (22: the eight old cases have none), each of four steps run by `$P/scripts/case_job.sh CASE STEP`
(table of modules and test classes: `$P/scripts/cases.tsv`, the landed `*Tests` files; submitted by `$P/scripts/submit_case.sh`):

1. `fix`: in `$W/CASE-fix`, offline: `:M:jar` for the case's jar modules and `:M:test --tests CLASS` for each landed test class,
   with `-Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline --continue`; then keeps
   `$P/artifacts/CASE-fix/`: `jars/`, `SHA256SUMS` (jars, and every class compiled from a production source file the landing
   changed, nested classes included; a Kotlin file `F.kt` as `FKt.class`) and, per classpath module M, `M.runtimeClasspath.txt` and
   `M.testRuntimeClasspath.txt` (`:`-joined; the project outputs they name are copied under `tree/`, the rest are paths into
   `$P/gradle-home`).
2. `parent`: the same in `$W/CASE-parent`, with those landed classes that exist at the parent.
3. `transplant`: `git archive` of the parent into `$P/build/CASE-parent-landed`, every changed file under `src/test` or
   `src/testFixtures` taken from the fix, then the same test classes. Passes when they fail (`TRANSPLANT-FAILS-AS-EXPECTED`) or do
   not compile (`TRANSPLANT-DOES-NOT-COMPILE-AS-EXPECTED`).
4. `clean`: `git clean -fdxq` in both worktrees, transplant copy removed.

Jar and classpath modules are those with changed production sources, plus the test module; Q02 adds spring-context (the brief's
`@Profile` path). Before submitting, `case_job.sh CASE dryrun` (offline `--dry-run` of both pins' task graphs, the classpath tasks
included) configured for each case (`$P/logs/dryrun-6x.txt`, `$P/logs/dryrun-7x.txt`).

| Case | Job |
|---|---|
| Q01 | `20261126-144024-setup-build-spring-framework-36912-q01-a` |
| Q02 | `20261126-144024-setup-build-spring-framework-36550-q02-a` |
| Q03 | `20261126-144024-setup-build-spring-framework-37326-q03-a` |
| Q05 | `20261126-144024-setup-build-spring-framework-35808-q05-a` |
| Q06 | `20261126-144025-setup-build-spring-framework-37332-q06-a` |
| Q07 | `20261126-144025-setup-build-spring-framework-37577-q07-a` |
| Q08 | `20261126-144025-setup-build-spring-framework-37524-q08-a` |
| Q09 | `20261126-141555-setup-build-spring-framework-26700-q09-a` |
| Q11 | `20261126-141555-setup-build-spring-framework-27716-q11-a` |
| Q12 | `20261126-141555-setup-build-spring-framework-27735-q12-a` |
| Q13 | `20261126-141555-setup-build-spring-framework-34709-q13-a` |
| Q14 | `20261126-144025-setup-build-spring-framework-37602-q14-a` |
| Q15 | `20261126-144025-setup-build-spring-framework-37261-q15-a` |
| Q16 | `20261126-144025-setup-build-spring-framework-37053-q16-a` |
| Q21 | `20261126-144025-setup-build-spring-framework-36602-q21-a` |
| Q22 | `20261126-144025-setup-build-spring-framework-37096-q22-a` |
| Q23 | `20261126-144026-setup-build-spring-framework-37601-q23-a` |
| Q24 | `20261126-144026-setup-build-spring-framework-36162-q24-a` |
| Q27 | `20261126-144026-setup-build-spring-framework-37525-q27-a` |
| Q28 | `20261126-141555-setup-build-spring-framework-35140-q28-a` |
| Q29 | `20261126-144026-setup-build-spring-framework-37465-q29-a` |
| Q30 | `20261126-141555-setup-build-spring-framework-35732-q30-a` |

## Job results

*Pending.*

## Digests of the built artifacts

*Pending.*

## Commands for a rerun by hand

Every Gradle build below is over a minute, so outside a job it is a probe at most; the caches are filled, so all run
`--offline`. The slice route takes seconds and needs no network.

```bash
source ~/.cache/in-the-loop/spring-pr-links-q01-q30/scripts/env.sh
# one case's job steps (CASE in Q01-Q03, Q05-Q09, Q11-Q16, Q21-Q24, Q27-Q30; STEP fix | parent | transplant | clean | dryrun)
bash $P/scripts/case_job.sh CASE STEP
# any task in a worktree, with the Gradle and JDKs that worktree needs (log $P/logs/TAG.log)
$P/scripts/gradle_case.sh $W/Q07-fix TAG "spring-core/build/test-results/test" \
  -Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline \
  :spring-core:test --tests org.springframework.util.ConcurrentReferenceHashMapTests
# Q09 needs the substitution on every run, offline too
SETUP_INIT="-I $P/scripts/subst-grails.init.gradle" $P/scripts/gradle_case.sh $W/Q09-fix TAG "" --offline :spring-context:jar
# a classpath of any project and configuration, offline
$P/scripts/gradle_case.sh $W/Q30-fix TAG "" --offline -I $P/scripts/resolve-all.init.gradle \
  :spring-core:setupWriteClasspath -PsetupCpConf=testRuntimeClasspath -PsetupCpOut=$TMPDIR/cp.txt
# the slice route for an old case (CASE in Q04, Q10, Q17, Q18, Q19, Q20, Q25, Q26; seconds each, inline in the probe cap)
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300 $P/scripts/slice_case.sh CASE
# chosen test classes of a pin on a slice (after slice_case.sh): CASE SLICEROLE TESTROLE TAG CLASS...
$P/scripts/slice_one.sh Q10 parent fix transplant-trigger org.springframework.scheduling.support.CronTriggerTests
# a slice ahead of its base release, for a program of your own (base set name in slices.tsv column 2)
$J8/bin/java -cp $P/slices/Q25-fix/Q25-fix-slice.jar:$(cat $P/releases/spring-context-5.2.1.RELEASE-q25/classpath.txt) ...
# a released set (':'-joined jar paths)
cat $P/releases/spring-jms-7.0.4/classpath.txt
```

A worktree whose `clean` step ran has no `buildSrc/build`; the next offline run compiles `buildSrc` again (its dependencies are
cached). Every project's every compile and test configuration was resolved, so modules beyond the case's also build offline.
`Q23-later` was resolved too but never built.

## What failed or was not done

- **Eight old cases have no Gradle build** ([why](#the-old-builds-that-cannot-be-configured)): Q04, Q10, Q17, Q18, Q19, Q20, Q25 and
  Q26 need build plugins that only `repo.spring.io/plugins-release` served (`propdeps-plugin` 0.0.4, 0.0.7, 0.0.9.RELEASE,
  `docbook-reference-plugin` 0.2.7, 0.3.1, `spring-asciidoctor-extensions` 0.1.3.RELEASE, `gradle-enterprise-conventions` 0.0.2), found
  in no public repository. No substitute was put in. Their changed files are built and their landed tests run on the
  [slice route](#the-slice-route) against released jars instead; the rest of each module there is the release's.
- **No release equals some pins**: Q04 (both; the fix's public `AutowireUtils` API never shipped), Q18 (both), Q19's fix, Q20's
  parent, Q26 (both), Q10's new `CronExpression`/`CronField`. The slices are the only builds of those files.
- **Q17 and Q18 slices take one unchanged pin file each** (`ReactiveHttpOutputMessage`, `AbstractServerHttpMessageWriter`), because
  the base release changed that API afterwards. Q19's tests use JUnit 4.12, not the pins' 4.11 (the vintage engine refuses 4.11).
- **Q18 has 6 failures at both pins** on the slice route (`ResourceWebHandlerTests` media-type and jar-directory tests), from the
  5.0.0.M2 base, not from the landing.
- **Q20's landed test does not detect the parent**: it passes on both slices, as the brief says (it never calls `clone()`).
- Refused by servers (401, anonymous): `repo.spring.io/release`, `plugins-release`. Nothing the Gradle 6–9 builds needed was only
  there, except Q09's `grolifant:0.14`, taken from Grails core with its sha1 checked.
- Unchecked signatures: Spring's and Reactor's release key `9A2C7A98E457C53D` and the 4.0/5.0 milestones' `23EF3D2F93185045` cannot be
  imported from keyserver.ubuntu.com or keys.openpgp.org; the 5.2/5.3 milestones and RCs publish no `.asc`. Their sha1s match the
  repositories'. Byte-buddy's key is revoked since. Grails core publishes no `.asc` for grolifant.
- Snapshot dependencies are the newest builds, not the builds of the pins' dates ([Snapshot dependencies](#snapshot-dependencies)).
- Not fetched: Spring Boot 4.0.8 (Q27's report; the scenario uses Framework only); a PostgreSQL server for Q11 and a RabbitMQ or other
  JMS broker beyond the embedded Artemis on spring-jms's test classpath for Q24 (choices for the domain work).
- Not run: the `later` revision of Q23 (fetched and resolved, never built); the brief's own scenarios and predictions; the whole
  module test suites (only the landed classes run).

## Setup Agent Notes

### What is ready, and where

- **Sources.** All 60 pins, plus the `later` revision Q23 links (`64861cb395e415bf1452d30f54f8e2c0ecc9cb46`), as worktrees
  `~/.cache/in-the-loop/spring-pr-links-q01-q30/worktrees/CASE-ROLE` (ROLE `parent` = before pin, `fix` = after pin), from the
  shared mirror `~/.cache/in-the-loop/git-mirrors/spring-framework.git`. Every PR's merge commit equals the after pin, every landed
  diff names exactly the PR's files, the 19 signed pins verify ([Upstream revisions](#upstream-revisions), full ids in its table).
  Q18 and Q26 land as chains of four and two commits, whose intermediate commits are in the mirror. All worktrees are clean.
- **Offline builds for 22 cases** (all but the eight old ones). Every configuration a compile or test task uses is resolved into
  `$P/gradle-home`; `source $P/scripts/env.sh` then `$P/scripts/gradle_case.sh WORKTREE TAG "" --offline TASKS` picks the right
  Gradle (verified distributions in `$P/tools/`) and JDK ([Build facts](#build-facts-by-era), [Commands](#commands-for-a-rerun-by-hand)).
  `$P/scripts/case_job.sh CASE STEP` reruns a case's job steps. Q09 needs `SETUP_INIT="-I $P/scripts/subst-grails.init.gradle"`.
- **Built jars, class digests and classpaths** for the 22 cases at both pins in `$P/artifacts/CASE-ROLE/` (`jars/`, `SHA256SUMS`,
  `M.runtimeClasspath.txt`, `M.testRuntimeClasspath.txt`, `:`-joined, project jars copied under `tree/`), once their jobs ran;
  digests in full in [Digests of the built artifacts](#digests-of-the-built-artifacts).
- **Slices for the eight old cases** at both pins: `$P/slices/CASE-ROLE/CASE-ROLE-slice.jar` (the pin's changed production classes,
  JDK 8), to put ahead of the base release's `$P/releases/SET/classpath.txt` (set per case in [the slice route](#the-slice-route));
  `$P/scripts/slice_case.sh CASE` rebuilds them and reruns the landed tests in seconds.
- **Released artifacts** in `$P/releases/SET/` (`jars/`, `classpath.txt`): the slices' bases and test libraries, and the versions
  the brief names: spring-core 6.2.13 (Q07), spring-context 7.0.9 (Q27), spring-jms 7.0.4 (Q24), spring-webmvc 4.3.3.RELEASE with
  jackson-databind 2.8.3 (Q17's servlet report), and Q11's PostgreSQL R2DBC driver as the pins' BOM manages it,
  `io.r2dbc:r2dbc-postgresql:0.8.8.RELEASE` ([Released artifacts](#released-artifacts), digests in `$P/logs/release-verify.txt`).
- **JDKs**: Temurin 24.0.2 (`$J24`) for Q13 and Q28, Liberica 17 (`$JL17`) for Q30, JDK 8 (`$J8`) for the slices and Q09.

### What was verified on a JVM

- **The eight old cases, on the slice route**: each landed test class passes on the fix slice and its parent version passes on the
  parent slice (Q18's six base-release failures aside). The fix's tests **fail** on the parent slice for Q17 (7), Q25 (1), Q26 (5),
  Q10 (`CronTriggerTests` alone, 2) and Q18 (`ResourceWebHandlerTests` alone, the 7 range tests); they **do not compile** there for Q04
  and Q19 (API the landing adds); Q20's landed test passes on both. Every failing test is named in [the slice route](#the-slice-route).
- **The 22 Gradle cases**: jobs queued, results pending ([Jobs](#jobs)).
- No scenario or prediction of the brief was run anywhere.

### What to know before starting

- **Q04, Q10, Q17, Q18, Q19, Q20, Q25, Q26 have no historical build** ([why](#the-old-builds-that-cannot-be-configured)). What exists
  is a slice per pin: that pin's changed classes ahead of a base release (Q04 5.2.0.M1, Q10 spring-context 5.3.0-M1, Q17 spring-web
  5.0.0.M3, Q18 5.0.0.M2, Q19 spring-test 4.0.0.M3, Q20 spring-web 5.3.0-RC1, Q25 spring-context 5.2.1.RELEASE, Q26 spring-tx
  5.2.0.M2). Every other class there is the release's, not the pin's. Releases equal to pins: Q10 parent = 5.3.0-M1 (and its
  `CronTrigger` fix = 5.3.0-M2), Q17 parent = 5.0.0.M3 and fix ≈ 5.0.0.M4, Q19 parent = 4.0.0.M3, Q20 fix ≈ 5.3.0-RC1, Q25 parent =
  5.2.1.RELEASE and fix ≈ 5.2.2.RELEASE (≈: equal in code, comments differ). No release equals Q04, Q18 or Q26 at either pin
  ([table](#the-slice-route)).
- **Q04's API never shipped.** The fix pin's `public` `AutowireUtils.isAutowirable(Parameter, int)` and `resolveDependency(...)` exist
  only at that pin and in its slice; from 5.2.0.M1 on, `AutowireUtils` is package-private again and the feature is
  `org.springframework.beans.factory.annotation.ParameterResolutionDelegate`. An "external consumer" of the pin's signatures compiles
  only against `$P/slices/Q04-fix/Q04-fix-slice.jar`.
- **Q18's base release already contains part of the fix** (5.0.0.M2 has the fix's `ResourceEncoder` and `DataBufferUtils`), and six
  `ResourceWebHandlerTests` (media types, a jar directory) fail on both slices for reasons of the base, not the landing. The seven
  `partialContent*` tests pass on the fix slice and fail on the parent slice; the parent's own copies of them are `@Ignore`d.
- **Q17 and Q18 slices include one unchanged pin file each** (`ReactiveHttpOutputMessage`, `AbstractServerHttpMessageWriter`), and
  Q26's slices run on Reactor 3.3.0.M1: the pins name `Dysprosium-BUILD-SNAPSHOT`, whose builds of that time are gone (the snapshot
  repository keeps 3.3.0.BUILD-SNAPSHOT builds of 2019-09-20 and 2019-09-24 only).
- **Snapshots.** Q08, Q16, Q29 (7.1) take Reactor 3.9.0-SNAPSHOT and Micrometer 1.18.0-SNAPSHOT, Q21 and Q27 Reactor 3.8.8-SNAPSHOT and
  Micrometer 1.16.8-SNAPSHOT, Q11 Reactor 3.4.13-SNAPSHOT and reactor-netty 1.0.14-SNAPSHOT, each the newest build the repository
  serves, mostly dated after the pins ([Snapshot dependencies](#snapshot-dependencies), digests there). Build `--offline` to keep them.
- **JDKs.** Q13 and Q28 compile with toolchain 24 (`$J24`), Q30 with Liberica 17 (`$JL17`), the other 7.x builds with toolchain 25 and
  `release` 17, Q11/Q12 with 17, Q09 and the slices with JDK 8. Default `java` on `PATH` is 25.0.5.
- **Q09** configures only with `$P/scripts/subst-grails.init.gradle` (grolifant 0.14 from Grails core); `case_job.sh` passes it.
- **Databases and brokers**: spring-jdbc's test runtime classpaths have H2, HSQLDB and Derby (check
  `$P/artifacts/CASE-ROLE/spring-jdbc.testRuntimeClasspath.txt`); spring-r2dbc's has r2dbc-h2. No PostgreSQL server was set up for
  Q11: Docker answers and already holds `postgres:16` and `postgres:17` images from other work; the R2DBC driver is in
  `$P/releases/r2dbc-postgresql-arabba-sr10` (it brings reactor-core 3.3.17 and reactor-netty 0.9.20, older than the pins' Reactor
  2020.0.14-SNAPSHOT line). Q24's spring-jms test classpath has the embedded Artemis broker the module's tests use.
- **Pins shared with other briefs**: Q08's fix `a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3` is the P01–P30 brief's P10 parent; its
  worktrees here are separate.
- **Q23's `later` revision** (`64861cb395e415bf1452d30f54f8e2c0ecc9cb46`) is checked out and resolved, not built.

### What is left for the domain work on purpose

All claims, scenarios, fixtures and examples; whether a slice, a release, or neither stands in for an old case's pins in a claim;
choosing databases, drivers, brokers and servers beyond what is fetched (Q08, Q11, Q14, Q15, Q24); the Kotlin side of Q05 beyond its
landed test; any run of the brief's own scenarios or predictions; the Q23 `later` revision; and example ids and folders.
