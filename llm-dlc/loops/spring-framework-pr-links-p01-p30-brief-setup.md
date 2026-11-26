# Setup for the Spring Framework PR links P01–P30 brief

Mechanical setup for [`spring-framework-pr-links-p01-p30-brief.md`](spring-framework-pr-links-p01-p30-brief.md), done on
2026-11-26 by a setup session (Claude Opus 5.5) before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

`$P` below is `~/.cache/in-the-loop/spring-pr-links-p01-p30`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $P/scripts/env.sh` defines `$P`, `$M`, `$W` (= `$P/worktrees`), `TMPDIR` (= `$P/tmp`), `GRADLE_USER_HOME` (= `$P/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`,
the installations earlier setups used) and `$JL17` (BellSoft Liberica 17.0.21.1, fetched here, see [Toolchain](#toolchain)).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `P01`–`P30` follow the brief's order (the same as the PR list
[`spring-framework-merged-pr-links-p01-p30.md`](spring-framework-merged-pr-links-p01-p30.md)). They are this record's labels
only, not example ids.

| Case | PR | Case | PR | Case | PR |
|---|---|---|---|---|---|
| P01 | #37435 | P02 | #37349 | P03 | #36480 |
| P04 | #36207 | P05 | #21855 | P06 | #37351 |
| P07 | #36626 | P08 | #37596 | P09 | #1912 |
| P10 | #37531 | P11 | #1532 | P12 | #37559 |
| P13 | #37202 | P14 | #37059 | P15 | #37159 |
| P16 | #22392 | P17 | #37014 | P18 | #25305 |
| P19 | #23562 | P20 | #29703 | P21 | #33533 |
| P22 | #35627 | P23 | #22260 | P24 | #34723 |
| P25 | #32469 | P26 | #28322 | P27 | #30020 |
| P28 | #33470 | P29 | #36556 | P30 | #36865 |

## Starting commit

Checkout at setup: `96c16581507a38bd6ea5470ce705b2838d8b8236` (`develop@origin`, "Merge the single-agent run
spring-framework-pr-links-o01-o20-brief into the line").

## Upstream revisions

All 30 pull requests are in `spring-projects/spring-framework`. The shared bare mirror `$M/spring-framework.git` (it existed
already) gained every pinned commit, fetched by SHA at depth 1 from GitHub and kept under `refs/pins/p01-p30/CASE-ROLE-SHA`
(`$P/scripts/pins.tsv`, log `$P/logs/fetch.log`: 61 of 61, two of them already there). Roles: `parent` = the brief's *before*
pin, `fix` = its *after* pin, `later` = the one subsequent revision the brief links by commit (P29
`daa8c10031e35f1a447917474f203789e009d3b5`, "Subsequent maintainer revision"). The brief also mentions later polishing for P01,
P02, P07 and P08 without naming a commit; nothing was fetched for those. The intermediate commits of the four two-commit
landings were fetched too and kept as `refs/pins/p01-p30/CASE-mid-SHA` (table below). One detached worktree per pinned
revision: `$W/CASE-ROLE` (61 worktrees, 5.3 GB checked out).

Checked mechanically (`$P/logs/prs.txt`, `$P/logs/landed-vs-pr-files.txt`, `$P/logs/two-commit-landings.txt`, PR records
`$P/upstream/prs/PR.json`, changed files `$P/upstream/prs/PR-files.tsv`, PR commits `$P/upstream/prs/PR-commits.tsv`):

- **Every PR is merged and its `merge_commit_sha` equals the brief's after pin.**
- **For 26 cases the after pin's first parent is the before pin.** P11's after pin is a two-parent merge (second parent
  `b30f6fd991a2aaa91bf0c4f9f88b6e99fc66f2a2`, the PR's one commit "Ensure that JSON is written to response body"). P13, P15, P26
  and P30 land as two commits each, the intermediate commit's parent being the before pin:
  P13 `2028c54d… → 8f4fcb6cbc3b85ba0cdaae7fc2b1c552f7ef9715 (Emit multipart parts with empty bodies in PartGenerator) → 4c8c6409… (Polishing contribution)`,
  P15 `a041c993… → 66125a569e4d673bd3e23f2f2c9490ec625cf640 (Fix busy-spin in SubscriberInputStream await()) → fd44a6bd… (Polishing contribution)`,
  P26 `299a10ce… → 86d52a677a41caa70477725d764c3deb2736bcb0 (Regression test for duplicate firing of proxied application listeners) → 20c688e6… (Avoid duplicate application listeners (proxy vs. proxy target))`,
  P30 `2e653246… → cddc671a8c6eea118b1f7ef05f2b6d754e852f09 (Fix CronExpression day skip on midnight DST gap) → 6467fca0… (Polishing contribution)`
  (full ids of the outer pins in the table). P26's PR lists the same two commits under the ids they had before they were
  rebased (`5367d96e8dddb5365cb8b0443dace852f0489bed`, `0dba415171294487b642c84084ef0207cc60988d`). The brief's two-commit remark
  for P13 ("Both landed commits are included") and P30 ("Both landed commits cover…") matches. P01, P03, P07, P16, P17, P18
  and P29 have a two-parent merge as their **before** pin. PRs P03, P16, P20, P23 and P25 had 2–5 commits and landed squashed as one.
- **The diff before→after names exactly the PR's changed files** for all 30 (`$P/logs/CASE-landed-files.txt`, diffstats in
  `$P/logs/CASE-landed-diffstat.txt`). P24 changes 52 files (three of them docs).
- **Signatures**, checked in a keyring of this work's own (`GNUPGHOME=$P/gnupg`, agent stopped; keys in `$P/keys/`: GitHub's
  `web-flow.gpg`, and Sam Brannen's SSH signing key from `gh api users/sbrannen/ssh_signing_keys` in `$P/keys/allowed_signers`;
  the principal name in that file is this setup's label only). All 21 signed pins verify (`$P/logs/commit-signatures.txt`),
  P20's fix with a GitHub web-flow key that has expired since; the other 40 are unsigned.

| Case | Worktree | Commit | Tree | Parents | Date | Author | Signature | Subject |
|---|---|---|---|---|---|---|---|---|
| P01 | `P01-parent` | `bcb4fbf31ca15f88697da1281894281ba4d6324d` | `afcb9c13c8d0d5ff49092fedf0a31b4baeae4999` | `b5b961de1cf26d340edab6bdf57fc812f2b8f74c` `cd9a50a251bfc74cc17ab1555263c1ccb30a1a54` | 2026-10-10 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| P01 | `P01-fix` | `35584e498e249986fbdc50bf16e3bfa88d2f97e2` | `f03f95e568263e1b9895f6529dd7da6af8d698dd` | `bcb4fbf31ca15f88697da1281894281ba4d6324d` | 2026-10-11 | Esmaeil Chitgar | good, GitHub web-flow key B5690EEEBB952194 | Avoid splitting surrogate pairs in StringUtils.truncate |
| P02 | `P02-parent` | `4d3beb5c3bbdfd781a18f73693f97f8abac67154` | `f2e0bd3056b6d0e735222e86bbf39aa0c0d8fa74` | `1b4955e49f06a791a1b5f3f7333ab631cab5a293` | 2026-09-29 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Stop using Tomcat's deprecated addServletMappingDecoded() method |
| P02 | `P02-fix` | `6afb65b225df5211365647f68090fb10a02afbba` | `afee93efb3482a9cc237475d39d0acffa6d9f7dd` | `4d3beb5c3bbdfd781a18f73693f97f8abac67154` | 2026-09-30 | Chengang Guan | good, GitHub web-flow key B5690EEEBB952194 | Fix single-value adaptation for primitive array types in TypeMappedAnnotation |
| P03 | `P03-parent` | `a0dba60fa657088015be64e9987f68c179c76e08` | `a2f57238fc5eca1ab28645eb2a5b8be98f233125` | `63e01cf6b3d22529ce674c85651e610ec5490a74` `3a35c4dbd03d5aaee860b3235b1ba7aaca51b1a7` | 2026-03-21 | Juergen Hoeller | unsigned | Merge branch '7.0.x' |
| P03 | `P03-fix` | `c1e90d51ca6a8379a0366f30cd77e5c1be019447` | `ab9abc8bef7464f64382aa043cb316b7985cb95c` | `a0dba60fa657088015be64e9987f68c179c76e08` | 2026-03-21 | Paul Ngo (Do Not Bug) | good, GitHub web-flow key B5690EEEBB952194 | GenericTypeResolver.resolveType should resolve TypeVariable with nested ParameterizedType (#36480) |
| P04 | `P04-parent` | `611811d8fc8b96d7983cf2d3d261727c3c12f66b` | `87c1352ac29a6d0fb487aa6e88e7aebe2091c730` | `0c9f40b171bfca68ddd1622455aefd34e2e4bb92` | 2026-01-23 | Sébastien Deleuze | unsigned | Anticipate fixing Kotlin 2.3 compilation warning |
| P04 | `P04-fix` | `ab314aadd95e05318629943754a8e4c1dd0400be` | `c80ec87d02cfccda81fb2078c8eb61b2f062d80d` | `611811d8fc8b96d7983cf2d3d261727c3c12f66b` | 2026-01-24 | Phillip Webb | unsigned | Refine YamlProcessor to allow different empty values |
| P05 | `P05-parent` | `7b11c3b599c82782d3e48328715926c1296d921f` | `6c387e105c4a4c4ef6d13b2f0a43fb72041ea379` | `a11a592734b4518332239425973cf11cb4f80fcf` | 2019-03-30 | liguoxiong | unsigned | Transform the beanName in method isPrimary |
| P05 | `P05-fix` | `6899624155e9c450d5166577d8b40e9783d718f4` | `d3ec21d2ce81a308784a201bd5869c51a30e69ca` | `7b11c3b599c82782d3e48328715926c1296d921f` | 2019-01-11 | Matthias Kurz | unsigned | Correctly parse property name in path "map[key[foo]]" |
| P06 | `P06-parent` | `06c597ed6fa8bdde6b8155a9587a9250936dd402` | `356f3099e40da18d0d7a3934fd7869381e0a35b8` | `c39edeff15074988267a872c9a8455c88f53de15` | 2026-09-30 | Sébastien Deleuze | unsigned | Use equality check for value class KClass comparison |
| P06 | `P06-fix` | `1b4955e49f06a791a1b5f3f7333ab631cab5a293` | `8112f33e672416951fb87f1065251a5bf95a8109` | `06c597ed6fa8bdde6b8155a9587a9250936dd402` | 2026-09-30 | 김준형 | good, GitHub web-flow key B5690EEEBB952194 | Avoid phantom keys in LinkedCaseInsensitiveMap.computeIfAbsent |
| P07 | `P07-parent` | `e940a38014cfad78aaef39a77db128e778f2f9ae` | `1da7a0e6cb639862d0892052195263730fc700fe` | `623bdfb6774dc4c1ea71013ac74b71ae20946411` `18b8f871aad99a5ed3b08492e3cd4216f03c1f96` | 2026-04-08 | Sam Brannen | unsigned | Merge branch '7.0.x' |
| P07 | `P07-fix` | `4b0101a9dcdf7dbe1841dfc33992fa8eb27eaf2f` | `8cfb663789f3bc2165232e3f8d1fc4813c12222f` | `e940a38014cfad78aaef39a77db128e778f2f9ae` | 2026-04-08 | Junseo Bae | good, GitHub web-flow key B5690EEEBB952194 | Defensively copy sentDate in SimpleMailMessage |
| P08 | `P08-parent` | `dfbe36b4da5546752cd5914940a70671e5302f22` | `4d13fac89e4c6d10779f28f026a06ae55ac50e65` | `a13ae0678b35b4d676f47ce3b05c0acae8b38163` | 2026-10-28 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |
| P08 | `P08-fix` | `b98ad3cbe3943fbcb1d7300b3349bb0bcdafb9ba` | `8bf7db071ced50df01aa73eb87003a2dc46189ae` | `dfbe36b4da5546752cd5914940a70671e5302f22` | 2026-10-28 | Tanishq-Choudhary | good, GitHub web-flow key B5690EEEBB952194 | Copy includes and excludes in RetryPolicy.Builder |
| P09 | `P09-parent` | `0001f87d59c9a247838ce0090771f351607263ce` | `1cbdfb4006f53bd2f82e0c45d517a8b43ad4bedc` | `589b7048ecad8c7f0df734139a2ad1ba79dc9262` | 2018-08-01 | Juergen Hoeller | unsigned | Polishing |
| P09 | `P09-fix` | `70dbaf9751961fc9105241830fd206b873fb738c` | `b1f9d66e397c7f7627d8e0d67bd3ca06a8020aa6` | `0001f87d59c9a247838ce0090771f351607263ce` | 2018-08-01 | Vedran Pavic | unsigned | Publish binding event for replaced attributes in MockHttpSession |
| P10 | `P10-parent` | `a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3` | `3b147b87cfbf10df700d1d6c75f326dbb7ce0b7a` | `78276e4cd07d421063162c2b6164499331d4506c` | 2026-10-20 | lejuho | good, GitHub web-flow key B5690EEEBB952194 | Use SqlParameterSource as-is in SqlParameterSourceUtils.createBatch |
| P10 | `P10-fix` | `18860f5732ac4bccdd26bb4254f23ec57f4bd99c` | `9ee596ff9e568fac0330c2d0ef3319e2cff4db13` | `a38ebf4b7cffe5946e07d0fb8ef2d7dc0ec9bbe3` | 2026-10-21 | Seungtaek Lim | unsigned | Make in-memory multipart Part content repeatable |
| P11 | `P11-parent` | `15c82afc1cdedc95b453e8f4ca61fd72f4a3ae82` | `67794661931823bd81a71be13337d3008b403a37` | `ea01c4113af22099755de763e9fb1dddb7691c0b` | 2017-09-20 | Juergen Hoeller | unsigned | Consistent conversion of Optional array/list arrangements |
| P11 | `P11-fix` | `c9afdce54bb702a5f60da1a7d83152ed7f8b8e1b` | `b127056869a5e9f89d594fe2f6add7a6b4b38635` | `15c82afc1cdedc95b453e8f4ca61fd72f4a3ae82` `b30f6fd991a2aaa91bf0c4f9f88b6e99fc66f2a2` | 2017-09-21 | Juergen Hoeller | unsigned | Merge pull request #1532 from aahlenst/spr-15988 |
| P12 | `P12-parent` | `c2d3866b0a3e0459c27957782e9b4386744d5786` | `05f333f8732632bcbfbb6b3dc417f691c780ce18` | `d5d671b4742fb521b3a4c3f15bf3425b1cf7635b` | 2026-11-03 | Brian Clozel | unsigned | Switch to Micrometer 1.18.0 SNAPSHOTs |
| P12 | `P12-fix` | `a8b48a6042c80a66c6237b35d29db84c45c75bd2` | `14963694087b58e4f75bfa5e8c6bbfec1faf8185` | `c2d3866b0a3e0459c27957782e9b4386744d5786` | 2026-10-22 | SangHoon Han | unsigned | Add JSON Lines to ProtobufJsonEncoder media types |
| P13 | `P13-parent` | `2028c54d01de7fe15e29c1233b83170c3a05b591` | `77d1fae6384097689c530c33bd979b44a0ebea41` | `e06482ad519d1040a1d0a95e8e2f696cf89d7362` | 2026-09-07 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish TableMetaDataContextTests |
| P13 | `P13-fix` | `4c8c6409a27a62ab163d3b6196ad862b7c835440` | `1756b8361750c024e70e9618eb2e2b4fae36b1fd` | `8f4fcb6cbc3b85ba0cdaae7fc2b1c552f7ef9715` | 2026-09-07 | Brian Clozel | unsigned | Polishing contribution |
| P14 | `P14-parent` | `27aa9e46c5165adbb7d7d0384e25f702872f3720` | `1d4b41f58890e1ef489f8f11a3d62abd2bfbddbf` | `56d706d5912f77c120b95dc05a3a02b999a792fd` | 2026-05-14 | Dmitry Sulman | unsigned | Add awaitEntityWithRetry extension to WebClient.ResponseSpec |
| P14 | `P14-fix` | `a2feb9ffe6674b6a6d2b66c69382d779cce7dc8a` | `5b16bc8524c59d69785e219b1c3051a4c869cb66` | `27aa9e46c5165adbb7d7d0384e25f702872f3720` | 2026-07-16 | samlightfoot | unsigned | Release Jackson BufferRecycler to its pool in encoders |
| P15 | `P15-parent` | `a041c9932b0ec4a9cb51e33c403363066c279424` | `d739ad8b2f3b29dc407e653662e0d7cba82470e0` | `dcfc89bdbb3eeb8306e4c2c633a5f9b744b73c35` | 2026-10-21 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Revise contribution |
| P15 | `P15-fix` | `fd44a6bdd94b65312fbb02bc11a575b40fa1e772` | `5fe0f02c7a365c8e27b490803733c48a7806ed2c` | `66125a569e4d673bd3e23f2f2c9490ec625cf640` | 2026-10-21 | Brian Clozel | unsigned | Polishing contribution |
| P16 | `P16-parent` | `a698adf125c540206b2050d94655ddeb293d8757` | `abed2c5372507163302f16150d7dde6fd2c8f37b` | `cc740dfd93144bfd4b5fb9e96ed37a11ec67cf51` `50e43087797725c4e6fec5b1acca6cf3407e01f8` | 2019-02-08 | Stephane Nicoll | unsigned | Merge pull request #22382 from artembilan |
| P16 | `P16-fix` | `82dbde13b67ffbd6bbcbef9ecf01ef18c236271f` | `75b40e070f1b0e21aac88c39d0a1040c8da2927e` | `a698adf125c540206b2050d94655ddeb293d8757` | 2019-02-08 | Mansur Mustaquim | unsigned | Fix for ScriptUtils failure when '--' occurs inside a multi-line comment on the same line as '*/' (#22392) |
| P17 | `P17-parent` | `99f2ccc2ecce47bbe35c5c7552f2aa5b22ae606c` | `ed2ade67ea1aa31c368ea1e57bea6ad888a06d6f` | `1aedfa5d5a3c5b008f2e7defd5969a8baae7dc96` `4acd6d6a7e415f15d1982797239274ad12e2310a` | 2026-09-07 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| P17 | `P17-fix` | `e06482ad519d1040a1d0a95e8e2f696cf89d7362` | `3da90c22c93d85d32606cece7ba91987e2dc2b02` | `99f2ccc2ecce47bbe35c5c7552f2aa5b22ae606c` | 2026-09-07 | 김준형 | good, GitHub web-flow key B5690EEEBB952194 | Reject overlapping declared and generated key columns in SimpleJdbcInsert |
| P18 | `P18-parent` | `eee0b76ef3c468767ec938b4998a1dc96a5d877e` | `f80ec2f4085b86143518b8176b74486d32e9967a` | `837dfe285a1be47a16336a6fb5a6030070e637fb` `f0b8e638ad44263f7e08eac72a1770479334d282` | 2020-06-23 | Rossen Stoyanchev | unsigned | Merge branch '5.2.x' |
| P18 | `P18-fix` | `8eedd9d5cc6357a71663232b9601410e0c1a9793` | `64da571cb782306ee9c8dd6829230a4c09c7f1de` | `eee0b76ef3c468767ec938b4998a1dc96a5d877e` | 2020-06-23 | Marten Deinum | unsigned | Use JDBC 4 API for connection validation |
| P19 | `P19-parent` | `f0e160fc67d276d22b2908b6421351feeba7f492` | `b6a891cc8b5d2e47c0b51779c745714f965643f0` | `3603e0c448643fbb8408737af30c60256f19a7f1` | 2019-09-20 | Sam Brannen | unsigned | Execute WebClientDataBufferAllocatingTests during all builds |
| P19 | `P19-fix` | `393a81d4a9d206cb7c7ff5184475ca1907c9de3f` | `193f4f9db45b4f6c7f524f1f8737099a22142ac8` | `f0e160fc67d276d22b2908b6421351feeba7f492` | 2019-09-02 | Mark Paluch | unsigned | Omit cancellation of transactional Monos in TransactionOperator |
| P20 | `P20-parent` | `eff1a1a664582383a278224db7cc34fa1c02443d` | `8a3cbc7e267f26424e4ad60d5fba3ad44720bfc6` | `8838e0d82518aec0bbb789b4cd8c5994888ee47a` | 2023-02-03 | Brian Clozel | unsigned | Upgrade to Artifactory Resource 0.0.18 |
| P20 | `P20-fix` | `e050c37158634fcc49e0b11254bbfeea71d17b8f` | `1c27b1fc8d37287b764626d54cb35dbadfe3c902` | `eff1a1a664582383a278224db7cc34fa1c02443d` | 2023-02-04 | danu | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | Release R2DBC connection when cleanup fails in transaction |
| P21 | `P21-parent` | `159e23730c3a10a48d91bc5c0fdcbb95c528312e` | `1bc6dd0496d8f5961071e668fb688a22f3df6bfa` | `8931b75b958144b1496da1b163553acd03e11ebd` | 2024-09-20 | Johnny Lim | good, GitHub web-flow key B5690EEEBB952194 | Fix Javadoc @⁠since tags in JettyCoreRequestUpgradeStrategy |
| P21 | `P21-fix` | `24a8f1b26da5ea2ec086e4b8e82bb6e4bb459a52` | `2d9fdfc513f7acc77b9b4ad64b965f141419e374` | `159e23730c3a10a48d91bc5c0fdcbb95c528312e` | 2024-09-13 | Yanming Zhou | unsigned | AnnotatedBeanDefinitionReader should respect @Fallback qualifier analogous to @Primary |
| P22 | `P22-parent` | `05814f7a421508ad4c600780a641c3b3aa26f44b` | `ef6a17857ec0f39c4cc780816113eca9d00c32a7` | `ba2bb0858969aebfe6d83090ecfbcb8c10356486` | 2025-10-14 | rstoyanchev | unsigned | Polishing contribution |
| P22 | `P22-fix` | `df67c1cf2d4d477e78d8711c9a875608acf9d5e9` | `ddb6e90e005dc2a3b8a10b77992d99773c461674` | `05814f7a421508ad4c600780a641c3b3aa26f44b` | 2025-10-13 | Schäfer, H.H. (Hans Hosea) | unsigned | 35626: defaultCandidate for scoped proxies |
| P23 | `P23-parent` | `4c9ae6494f181967f5f28f06574f6d5f3ff7f9d8` | `5b87a663eaaa1972f136268fafadf52b9bae4721` | `1bf3b36ce8a1496a1bcd56c89f2f869e51d7707a` | 2019-02-05 | Juergen Hoeller | unsigned | Concurrency/nullability fine-tuning in MimeType(Utils) |
| P23 | `P23-fix` | `00855c4f5f4e0f028212268a98a23b3009c3f7d4` | `9083fe7e03bffbb19da820bf9457f3a99a0a432e` | `4c9ae6494f181967f5f28f06574f6d5f3ff7f9d8` | 2019-02-05 | Yoann Rodière | unsigned | Add tests for SpringBeanContainer (Hibernate ORM integration) and fix the behavior when requesting named beans (#22260) |
| P24 | `P24-parent` | `3afd5511743840dd2c97d7410362963dd0d9f3e2` | `57db9647933a13327a70d7e124745de42ebef9e4` | `ffd15155ee21cb166306d698c4dd4ea8e35d0c8c` | 2025-04-07 | Juergen Hoeller | unsigned | Add rejectTasksWhenLimitReached option for concurrency limit |
| P24 | `P24-fix` | `c168e1c2976267630d86c7114cf934a0f01aa8c9` | `097cf226771cb85d0647cd362776716794e9a451` | `3afd5511743840dd2c97d7410362963dd0d9f3e2` | 2025-04-10 | Sam Brannen | good, GitHub web-flow key B5690EEEBB952194 | Provide first-class support for Bean Overrides with @⁠ContextHierarchy |
| P25 | `P25-parent` | `bed36890019a1764f1ed846ec1c94325a2ac5c72` | `9228152c40c729eeeabf975c78d8e0a97cd7ce93` | `3d85ec23545f455d6d055c2e786c2ab0b4850f5f` | 2024-04-10 | Sam Brannen | unsigned | Polishing |
| P25 | `P25-fix` | `561583842fe49ba61152f96f30572ec02b36d443` | `8c61eb8470ecc52980cf9788ff4b5f8d30e88e6e` | `bed36890019a1764f1ed846ec1c94325a2ac5c72` | 2024-04-10 | Mikaël Francoeur | good, GitHub web-flow key B5690EEEBB952194 | Consistent handling of undeclared checked exceptions in CGLIB proxies (#32469) |
| P26 | `P26-parent` | `299a10ce2a909fab1c0fe810a9b7d84e01ffd7ef` | `36da9352b0c915c4172324ddc7c6fab84317bbae` | `e0ba42a80cf4bdb41d5b762dad5cd5376c2ca30f` | 2023-10-10 | Sébastien Deleuze | unsigned | Update `@Since` Java doc tags in ReactorResourceFactory |
| P26 | `P26-fix` | `20c688e68de2fe9db9dda95bb1b43c6147ae0007` | `d66fdbe46a8455aa18196573a5a70492af1623ec` | `86d52a677a41caa70477725d764c3deb2736bcb0` | 2022-04-11 | Alexander Kriegisch | unsigned | Avoid duplicate application listeners (proxy vs. proxy target) |
| P27 | `P27-parent` | `906c54faffc75721b98f9b9cf63d35edd81f7b4f` | `c5ea1a332a70648f62c2e9695a1f769cdc39b02b` | `d3c3088c6ba27a5a6d7f458a76f5d91320aaf828` | 2023-02-27 | Simon Baslé | unsigned | Add SpEL support for registered MethodHandles |
| P27 | `P27-fix` | `b39e93d0d149459f28d61b19f3409d4b64165233` | `5b777be29fe38591bdb8fc2afb118c95ff6588c3` | `906c54faffc75721b98f9b9cf63d35edd81f7b4f` | 2023-02-23 | Simon Baslé | unsigned | Add test support to record async events, with Junit5 caveat |
| P28 | `P28-parent` | `e3cf23d15aae9bfd8fe5c5bbfc505942d3ea28fe` | `98d4b55a8eb430bb583d4aab0d26e2ac4ca19e59` | `07d281c6d824c6806680b416729908c31943f8c0` | 2024-09-26 | Tran Ngoc Nhan | unsigned | remove unused keyword |
| P28 | `P28-fix` | `cc3948e14cbca6ba9f40607fcc456da842b93279` | `5b7a2324e8c3b3469a6f8035d89085887e13f39e` | `e3cf23d15aae9bfd8fe5c5bbfc505942d3ea28fe` | 2024-09-03 | 오영택 | unsigned | feat: Implemented to throw a runtime error if a class has @Transactional |
| P29 | `P29-parent` | `a947f9bf7908f10a24aa98db68585fb5bbd0e2af` | `b7e639a427460aa9d266de7c9ef5ffea48f2ffbe` | `a13056f6af8db3c802516a66070ae61b4a435c47` `a4720ccf771211cabbd291385db1eef8ddd16a43` | 2026-08-18 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| P29 | `P29-fix` | `7da47f8c473e5b48939418adc9b2427b0890501f` | `06ee941a1fa38f486042e24d269abafc58ae535d` | `a947f9bf7908f10a24aa98db68585fb5bbd0e2af` | 2026-08-18 | Vedran Pavic | good, GitHub web-flow key B5690EEEBB952194 | Simplify programmatic scheduling of cron tasks with time zone |
| P30 | `P30-parent` | `2e653246b5f27dc0baa6aa09ae207512bed45899` | `53e1516123d8b77842075975337ea1abd0598e83` | `86a68a77c40bf33711c1bdb25296a12834791048` | 2026-06-03 | Juergen Hoeller | unsigned | Fix concurrency issue against shared cookie field in setLocaleContext |
| P30 | `P30-fix` | `6467fca05b874f3e44fbd9451a252f035abbeafc` | `b9c37e858cb7c3e3aa3816f0791275d9ea83ab30` | `cddc671a8c6eea118b1f7ef05f2b6d754e852f09` | 2026-06-04 | Brian Clozel | unsigned | Polishing contribution |
| P29 | `P29-later` | `daa8c10031e35f1a447917474f203789e009d3b5` | `cd805423e88c1669048bd273465678947644d070` | `7da47f8c473e5b48939418adc9b2427b0890501f` | 2026-08-18 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |

PR metadata (`gh api`): base branch `main` for 16, `7.0.x` for P02, P06, P14, P15, P30, `6.2.x` for P22, P24, `5.1.x` for P16,
and `master` for P05, P09, P11, P18, P19, P23. Merged between 2017-09-21 (P11) and 2026-11-03 (P12).

## Toolchain

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 17.0.21, 21.0.13, 25.0.5 (11 unused) | `~/.sdkman/candidates/java/` | earlier setups' installations |
| BellSoft Liberica JDK 17.0.21.1+5 | `$P/tools/jdk/jdk-17.0.21.1` (`$JL17`), from `https://github.com/bell-sw/Liberica/releases/download/17.0.21.1+5/bellsoft-jdk17.0.21.1+5-linux-amd64.tar.gz` (tarball deleted after unpacking) | sha1 `a44f40d665ddaa9e450a15e2b1f55d1a754630bb` = BellSoft's API (`$P/dl/jdk/liberica17-latest.json`); sha256 `add6f8c21289daf20eb38cd8fbd05bc374773038512cae655844e4e9a9a4f3d3` (the same tarball the O01–O20 setup took); no signature published. Needed by P21, P22, P24, P25, P26, P28: their `buildSrc` `JavaConventions` sets the toolchain to vendor `BELLSOFT`, language 17. |
| Gradle 4.1, 4.8.1, 4.10.3, 5.3.1, 5.6.2, 6.5, 7.6, 8.1.1, 8.4, 8.7, 8.9, 8.10.2, 8.13, 8.14.3, 9.3.0, 9.4.1, 9.5.1, 9.6.1, 9.7.0, 9.7.1, 9.8.0, 9.8.1, 9.8.2 | unpacked in `$P/tools/gradle-V` | zip sha256 = services.gradle.org's `.sha256`, all 23 ([digests](#gradle-distributions)) |
| Maven 3.10.0 | on `PATH` (sdkman), settings `$P/maven-settings.xml` (local repository `$P/m2`, plus `repo.spring.io/milestone`) | released artifacts only |

Each checkout's wrapper names its own Gradle (table in [Build facts](#build-facts-by-era)); every checkout's
`gradle-wrapper.jar` matches gradle.org's `gradle-V-wrapper.jar.sha256` except P11's (Gradle 4.1, both pins, sha256
`b9a5dd730fbe8b5ca7fd5dc1188d6f35e35098667fef9e5b52b7cfe74bebfbd4`, which matches none of the 39 Gradle 2.x–4.x releases that publish a wrapper checksum; `$P/logs/wrapper-jars.txt`, `$P/logs/P11-wrapper-jar-origin.txt`).
**The wrapper is not used**: `$P/scripts/gradle_case.sh` runs the verified distribution the wrapper names. None of the wrapper
properties sets `distributionSha256Sum`.

### Gradle distributions

zip sha256, each equal to services.gradle.org's `gradle-V-bin.zip.sha256` (`$P/logs/gradle-dists.txt`; the `.sha256` files are
kept in `$P/dl/gradle/`, the zips were deleted after unpacking):

| Gradle | zip sha256 | Gradle | zip sha256 |
|---|---|---|---|
| 4.1 | `d55dfa9cfb5a3da86a1c9e75bb0b9507f9a8c8c100793ccec7beb6e259f9ed43` | 4.8.1 | `af334d994b5e69e439ab55b5d2b7d086da5ea6763d78054f49f147b06370ed71` |
| 4.10.3 | `8626cbf206b4e201ade7b87779090690447054bc93f052954c78480fa6ed186e` | 5.3.1 | `1c59a17a054e9c82f0dd881871c9646e943ec4c71dd52ebc6137d17f82337436` |
| 5.6.2 | `32fce6628848f799b0ad3205ae8db67d0d828c10ffe62b748a7c0d9f4a5d9ee0` | 6.5 | `23e7d37e9bb4f8dabb8a3ea7fdee9dd0428b9b1a71d298aefd65b11dccea220f` |
| 7.6 | `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` | 8.1.1 | `e111cb9948407e26351227dabce49822fb88c37ee72f1d1582a69c68af2e702f` |
| 8.4 | `3e1af3ae886920c3ac87f7a91f816c0c7c436f276a6eefdb3da152100fef72ae` | 8.7 | `544c35d6bd849ae8a5ed0bcea39ba677dc40f49df7d1835561582da2009b961d` |
| 8.9 | `d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab` | 8.10.2 | `31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26` |
| 8.13 | `20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78` | 8.14.3 | `bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531` |
| 9.3.0 | `0d585f69da091fc5b2beced877feab55a3064d43b8a1d46aeb07996b0915e0e0` | 9.4.1 | `2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb` |
| 9.5.1 | `bafc141b619ad6350fd975fc903156dd5c151998cc8b058e8c1044ab5f7b031f` | 9.6.1 | `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` |
| 9.7.0 | `84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae` | 9.7.1 | `acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a` |
| 9.8.0 | `bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c` | 9.8.1 | `dce76f55f8e251a3a1f130eb120f30b3d271de2b76c9b0729d316b5a1b6dc01f` |
| 9.8.2 | `21bd5da2de49b642904077f38c0efdc7778e92b3ed0889392dca61b97e389607` |  | `` |

## Build facts by era

Both pins of every case have the same project version and the same Gradle.

| Era | Cases | Versions | Gradle | Launcher JDK | Compiles with |
|---|---|---|---|---|---|
| 7.x | P01, P03, P07, P08, P10, P12, P13, P17, P29 | 7.1.0-SNAPSHOT | 9.4.1 (P03, P07), 9.7.0 (P29), 9.7.1 (P13, P17), 9.8.1 (P01, P10), 9.8.2 (P08, P12) | 25.0.5 | toolchain 25, `release` 17 (`buildSrc` `JavaConventions`); Kotlin 2.3.20–2.4.21 |
| 7.x | P02, P04, P06, P14, P15, P30 | 7.0.4 (P04), 7.0.8 (P30), 7.0.9 (P14), 7.0.10 (P02, P06), 7.0.11 (P15) -SNAPSHOT | 9.3.0, 9.5.1, 9.6.1, 9.8.0, 9.8.2 | 25.0.5 | toolchain 25, release 17; Kotlin 2.2.21 |
| 6.2 | P21, P22, P24, P25, P28 | 6.2.0 (P21, P25, P28), 6.2.6 (P24), 6.2.12 (P22) -SNAPSHOT | 8.9, 8.14.3, 8.13, 8.7, 8.10.2 | 17.0.21 | **toolchain vendor BELLSOFT, 17** (`$JL17`); Kotlin 1.9.22–1.9.25 |
| 6.1 | P26, P27 | 6.1.0-SNAPSHOT | 8.4 (P26), 8.1.1 (P27) | 17.0.21 | P26 toolchain BELLSOFT 17; P27 the launcher JDK (17); Kotlin 1.9.10, 1.7.21 |
| 6.0 | P20 | 6.0.5-SNAPSHOT | 7.6 | 17.0.21 | the launcher JDK (17); Kotlin 1.7.21 |
| 5.x | P05, P09, P11, P16, P18, P19, P23 | 5.2.0.BUILD (P05, P19, P23), 5.1.0.BUILD (P09), 5.0.0.BUILD (P11), 5.1.5.BUILD (P16), 5.3.0 (P18) -SNAPSHOT | 5.3.1, 4.8.1, 4.1, 4.10.3, 6.5, 5.6.2, 4.10.3 | (8) | source 1.8 — **none configures**, see [The 5.x builds](#the-5x-builds-cannot-be-configured) |

**Runner.** `$P/scripts/gradle_case.sh DIR TAG RESULTDIRS ARGS...` runs, in DIR, `JAVA_HOME=LAUNCHER timeout 3000 [choom -n 500 --]
$P/tools/gradle-V/bin/gradle --no-daemon --console=plain --max-workers=4 --no-build-cache -Dorg.gradle.caching=false [--no-scan]
-Porg.gradle.java.installations.auto-detect=false -Porg.gradle.java.installations.auto-download=false
-Porg.gradle.java.installations.paths=$J8,$J11,$J17,$J21,$J25,$JL17 ARGS` with `GRADLE_USER_HOME=$P/gradle-home`, V read from DIR's
wrapper properties and the launcher by era (Gradle 9: 25; 7.6–8.x: 17; 4.x–6.x: 8; `GJ=PATH` overrides). `--no-scan` is passed from
Gradle 7 on. Log `$P/logs/TAG.log`, JUnit summary `$P/logs/TAG.junit.txt`. (`choom` is skipped when the process already runs at
OOM score 500 or more, as a pipeline job does.) The scripts are the O01–O20 setup's, with paths and case lists changed.

**Repositories the builds name**, checked anonymously on 2026-11-26: Maven Central and the Gradle Plugin Portal (all 6.x and 7.x
builds; resolve without the 401 repositories below); `repo.spring.io/milestone` and `repo.spring.io/snapshot` (200);
`repo.spring.io/libs-spring-framework-build` (reachable, answers 404 for what was probed); `repo.spring.io/release`,
`plugins-release` and `libs-release` (**401**).

**Online resolution** (inline, each Gradle run in a 6 GB scope; `$P/scripts/resolve_online.sh WORKTREE...`): two passes per
worktree, `-I $P/scripts/resolve-all.init.gradle setupResolveAll -PsetupResolve=Classpath,kotlin,Kotlin,annotationProcessor,AnnotationProcessor`
then `-PsetupResolve=ALL`, over **every project** of the build (the init script adds tasks `setupResolveAll` and
`setupWriteClasspath` to every project and changes no upstream file). Summaries: `$P/logs/resolve-7x.summary.txt`,
`$P/logs/resolve-6x.summary.txt`; logs `$P/logs/WORKTREE.resolve{1,2}.online.log`. All 47 worktrees of the 6.x and 7.x cases (P29's `later` included) resolved every configuration of pass 1 (513–564 per
worktree). Pass 2 (718–1,173 configurations) failed only on configurations no compile or test task uses: the Kotlin plugin's
IDE-only `*DependenciesMetadata` (122 per worktree at 7.0.x, none at 7.1, 70–85 at 6.x) and, at P20 (Gradle 7.6), the legacy
`default` configuration of eight projects, as in the O01–O20 setup.

## The 5.x builds cannot be configured

Seven cases are Spring 5.x checkouts: P05 (#21855), P09 (#1912), P11 (#1532), P16 (#22392), P18 (#25305), P19 (#23562),
P23 (#22260). Configuring each pin online (`gradle help`, Gradle and JDK 8 as above, logs `$P/logs/CASE-ROLE.help.online.log`,
summary `$P/logs/5x-configure.txt`) fails for both pins of all seven, before any project is evaluated, on build-script
artifacts that only the 401 repositories served:

| Cases | Gradle | Missing (first failure) |
|---|---|---|
| P05, P09, P16, P23 | 5.3.1, 4.8.1, 4.10.3, 4.10.3 | `io.spring.gradle:propdeps-plugin:0.0.9.RELEASE` (root `buildscript`, from `repo.spring.io/plugins-release` only) |
| P11 | 4.1 | `io.spring.gradle:propdeps-plugin:0.0.8`, `io.spring.gradle:docbook-reference-plugin:0.3.1`, `org.jetbrains.dokka:integration:0.9.15` |
| P19 | 5.6.2 | `io.spring.asciidoctor:spring-asciidoctor-extensions:0.1.3.RELEASE`; `org.jfrog.buildinfo:build-info-extractor:2.13.10` (for `com.jfrog.artifactory` 4.9.8) |
| P18 | 6.5 | settings plugin `io.spring.gradle-enterprise-conventions` 0.0.2 (marker `io.spring.gradle-enterprise-conventions.gradle.plugin:0.0.2`) |

Each missing `.pom` was looked for (`$P/scripts/probe.sh`, `$P/logs/probe-5x-plugins.txt`) at Maven Central, the Gradle Plugin
Portal, `repo.spring.io/milestone`, `snapshot` and `libs-spring-framework-build`, JCenter (`jcenter.bintray.com`, which still
serves, e.g. `dokka-gradle-plugin:0.9.17`), Grails core, Atlassian, JBoss, Red Hat, Jenkins, Alfresco, Sonatype OSS releases and
JitPack: **404 everywhere**, 401 at `repo.spring.io/release` and `plugins-release` (and JitPack for the two `io.spring.gradle`
ones). The one exception is `build-info-extractor:2.13.10`, which Grails core serves; P19 still lacks the asciidoctor
extensions. Without these the root build script does not compile, so no init script can route around the 401s, and nothing
was substituted. P18's build also imports `reactor-bom:2020.0.0-SNAPSHOT`, which `repo.spring.io/snapshot` serves only as its
last build (the O01–O20 setup found the same for its O14). The Gradle builds were not run; the pins' changed files are built and
their landed tests run on the [slice route](#the-5x-cases-on-the-slice-route) instead.

**Released artifacts whose changed sources match the pins.** For each case, the git blob id of the changed production file
in released `-sources.jar`s (Maven Central; milestones from `repo.spring.io/milestone`; jar sha1s equal the repositories'),
compared with the pins' blobs (`$P/scripts/release_blobs.sh`, `$P/logs/5x-pinned-blobs.txt`, `$P/logs/5x-release-blobs.txt`;
sources jars in `$P/dl/sources/`):

| Case | File | Parent pin blob = | Fix pin blob = |
|---|---|---|---|
| P05 | `spring-beans/.../beans/AbstractNestablePropertyAccessor.java` | **5.1.6.RELEASE** (`9790cf797873661c54d1eec32eff88988689f6c1`) | none: 5.2.0.M1 and M2 differ in comments, braces and one modifier (`private static int getPropertyNameKeyEnd` at the pin, `private int` in M1); 5.1.7.RELEASE does not have the fix (`$P/logs/5x-release-diffs.txt`) |
| P09 | `spring-test/.../mock/web/MockHttpSession.java` | **5.1.0.RC1** (`f8eb339bb96517069ac8bb602b7746384156390f`) | **5.1.0.RC2, RC3 and 5.1.0.RELEASE** (`3044e4748411951dfa2bced60743fde5b87caf9d`) |
| P11 | `spring-web/.../converter/protobuf/ProtobufHttpMessageConverter.java` | **5.0.0.RC3 and RC4** (`ecb87985d145622d66228be8acd1a800194612d3`; RC4 is the version the brief names) | **5.0.0.RELEASE and 5.0.1.RELEASE** (`76104fb625745c1b95b197cb6fa75fcd769505f9`) |
| P16 | `spring-jdbc/.../datasource/init/ScriptUtils.java` | **5.1.4.RELEASE** (`863280ede0baa8eb33d7a0bee4c737ecedfcfc27`) | none: 5.1.5.RELEASE (and 5.1.6, 5.2.0.M1) differ from the pin **only in comments, Javadoc and the indentation of two parameter lines** (code lines compared with comments removed) |
| P18 | `spring-jdbc/.../support/DatabaseStartupValidator.java` | **5.2.7.RELEASE and 5.2.8.RELEASE** (`cab49de32b4d7e64a1f5692d159d2edffa6f853d`) | none: 5.3.0-M1 (= M2 = RC1, `f518103d2e3ba1a3c3572df67d290a0b6714130c`) drops `@Deprecated` from the `validationQuery` field, rewords a debug message ("Validation check threw exception") and Javadoc |
| P19 | `spring-tx/.../reactive/TransactionalOperator.java` | **5.2.0.RC1 and RC2** (`a1e753500de7d54d96ab42a5770e88a699c42942`) | **5.2.0.RELEASE and 5.2.1.RELEASE** (`f31a74290462e7354d16ccfc508ba70d1390432d`) |
| P19 | `spring-tx/.../reactive/TransactionalOperatorImpl.java` | **5.2.0.RC2** (`3162525a4ea5dbf58c0dfb81ca2c16ffd506f9b0`) | none: 5.2.0.RELEASE differs in one line, the `Mono.usingWhen` call: `this.transactionManager::commit, (res, err) -> Mono.empty(), s -> Mono.empty())` against the pin's `this.transactionManager::commit, s -> Mono.empty())` |
| P23 | `spring-orm/.../hibernate5/SpringBeanContainer.java` | **5.1.4.RELEASE** (`9280d382309e77f5448fac7fa9ba1686344b7334`) | none exactly: 5.1.5.RELEASE differs **only in the copyright year and one blank line**; 5.1.6 and 5.2.0.M1/M2 add a fallback-producer `try`/`catch` |

The rest of each module (and of spring-core, spring-beans) moved between these releases and the pins; the slice route below
takes only the changed files from the pins. The source tree of each pin is in its worktree.

## The 5.x cases on the slice route

The route the first Spring setup (`spring-and-java-data-setup.md`, its A4) used for a 5.2 build that could not be configured, run
here as the user asked on 2026-11-26 ("stuff that cannot be built should be verified against pinned JARs"). For each case and
pin (`$P/scripts/slice_case.sh CASE`, table `$P/scripts/slices.tsv`, all seven in 30 s inline in the probe cap, log
`$P/logs/slices.txt`):

1. **Slice.** The pin's changed production files (`src/main/java` lines of `$P/logs/CASE-landed-files.txt`, nothing else) compiled
   by `javac` 1.8.0_512 (`$J8`, `-source 8 -target 8 -parameters -proc:none -implicit:none`) against the **base release**, the
   release whose copy of those files equals the parent pin's ([table above](#the-5x-builds-cannot-be-configured)), into
   `$P/slices/CASE-ROLE/main/`, jarred as `$P/slices/CASE-ROLE/CASE-ROLE-slice.jar`, class digests in
   `$P/slices/CASE-ROLE/main.SHA256SUMS` (identical over two runs). Both pins use the same base, so the two slices differ only in
   the changed files.
2. **Tests.** The landed test class compiled from the pin's own test tree (`-sourcepath` of the module's `src/test/java`, then the
   shared test sources the 5.x builds put on test classpaths: `spring-core`/`spring-beans` `src/test/java`, or `src/testFixtures`
   for P18), with the test libraries at the versions that pin's `build.gradle` declares (`$P/releases/tests-CASE/`, resolved with
   checksums like the other sets: JUnit 4.12 and Hamcrest 1.3 for the 5.0/5.1 pins, Jupiter 5.6.2 or 5.5.2 for P18 and P19, and
   their Mockito, AssertJ and Log4j), then run on JDK 8 with the JUnit Platform console launcher (1.6.2, P19 1.5.2; its vintage
   engine runs the JUnit 4 classes the 5.0/5.1 builds ran with Gradle's JUnit 4 runner). Classpath: slice, test classes, the
   module's `src/test/resources`, base release, test libraries. Results per run in `$P/slices/CASE-RUN/` (`junit.log` with every
   test, `reports/` JUnit XML, `javac-*.log`).
3. **Runs.** `fix`: the fix pin's tests on the fix slice. `parent`: the parent pin's own version of the test class on the parent
   slice (none where the class is new). `transplant`: the fix pin's tests on the parent slice. `release`: the fix pin's tests on
   the base release alone, without a slice (a control: there the parent's changed files are the release's own classes).

| Case | Base release (and extras) | Test classes | Fix | Parent | Transplant (fix tests on the parent slice) |
|---|---|---|---|---|---|
| P05 | spring-beans 5.1.6.RELEASE | `BeanWrapperTests`, `DirectFieldAccessorTests` (the two concrete subclasses of the landed abstract `AbstractPropertyAccessorTests`) | 197 pass, 2 aborted | 197 pass, 2 aborted | **fails**: 2 of 199, `getAndSetIndexedProperties` in both classes, "Invalid property 'map[key5[foo]' of bean class [org.springframework.tests.sample.beans.IndexedTestBean]: Value of nested property 'map[key5[foo]' is null" |
| P09 | spring-test 5.1.0.RC1, javax.servlet-api 4.0.1 | `MockHttpSessionTests` | 17 pass | 13 pass | **fails**: 2 of 17, `bindingListenerBindSameListenerTwice` (expected:<2> but was:<1>), `bindingListenerBindListenerOverwrite` (expected:<1> but was:<0>) |
| P11 | spring-web 5.0.0.RC4 with protobuf-java-util 3.4.0, and protobuf-java-format 1.4 (both optional in the pins' `spring-web.gradle`, so on its compile and test classpaths; the converter does not compile without the second) | `ProtobufHttpMessageConverterTests` | 11 pass | 9 pass | **fails**: 1 of 11, `writeJsonWithGoogleProtobuf`, "body is empty" |
| P16 | spring-jdbc 5.1.4.RELEASE | `ScriptUtilsUnitTests` | 10 pass | 9 pass | **fails**: 1 of 10, `readAndSplitScriptContainingMultiLineNestedComments`, "statement 2 not split correctly": the parent's statement 2 begins with the comment text `but it's still a single-line comment` |
| P18 | spring-jdbc 5.2.7.RELEASE | `DatabaseStartupValidatorTests` (new in the landing) | 6 pass | n/a | **fails**: 3 of 6, `shouldUseJdbc4IsValidByDefault`, `shouldCallValidatonTwiceWhenNotValid`, `shouldCallValidatonTwiceInCaseOfException`, "Property 'validationQuery' is required" |
| P19 | spring-tx 5.2.0.RC2 with reactor-core and reactor-test 3.3.0.RC1 | `TransactionalOperatorTests` | 5 pass | 4 pass | **fails**: 1 of 5, `monoSubscriptionNotCancelled` |
| P23 | spring-orm 5.1.4.RELEASE with spring-context 5.1.4, hibernate-core 5.4.1.Final, HSQLDB 2.4.1 | `HibernateNativeEntityManagerFactorySpringBeanContainerIntegrationTests` (new in the landing), plus the test-tree classes its Spring XML names (`org.springframework.orm.jpa.domain.*`, `PersistenceInjectionTests`) | 8 pass | n/a | **fails**: 4 of 8, `testCanRetrieveBeanByNameWithJpaCompliantOptions` (expected the application context, was `null`), `testCanRetrieveFallbackBeanByNameWithJpaCompliantOptions` (expected:<0> but was:<1>), `testCanRetrieveFallbackBeanByTypeWithJpaCompliantOptions` (expected:<1> but was:<0>), `testCanRetrieveFallbackBeanByNameWithNativeOptions` (expected:<0> but was:<1>) |

The two P05 aborts are `setPrimitiveArrayPropertyLargeMatching` in each class, which assumes test group `PERFORMANCE`, off by
default as in the upstream build. The `release` control gives exactly the transplant's failures for all seven cases. Two earlier
runs were set up wrongly and are superseded: P11 without protobuf-java-format (the converter did not compile) and P23 without the
XML-named test classes (`Could not find class [org.springframework.orm.jpa.domain.DriversLicense]`).

**Slice class digests (sha256).** Compiled from the pins' files, so they are what the domain work can compare. They are not the
released jars' bytes: those were compiled by another JDK.

| Case | Class | Parent pin | Fix pin |
|---|---|---|---|
| P05 | `org/springframework/beans/AbstractNestablePropertyAccessor.class` | `c62e29cc51fd53c0236bbb6497391b6f6b887e5fa1805586812c73c5d4ae63b8` | `52278528ce9897784d1b5ef8a6f2cbfa86db66afd9e47f755b9c7c7def39041c` |
| P05 | `…/AbstractNestablePropertyAccessor$PropertyHandler.class` | `3a2e9b2976ce7be4f5463b73f0e681b1e7b9c5386cc860f9c67f0e096538ea2a` | `27c93db10dfc2c4dc3ccf59c4134bac177753fd29748d595fbcabbacf96a7154` |
| P05 | `…/AbstractNestablePropertyAccessor$PropertyTokenHolder.class` | `dd2ee2425606d4ba5342788831b190ec4253690617ca2de8060de10b48d1c7af` | `d14de0d8419d4668106dbc34b67a0534ff1a64a428130d5d2ee368b4f9540cd3` |
| P09 | `org/springframework/mock/web/MockHttpSession.class` | `247f81a7ab626355a9395e395e0fa9eff574b31442f9185f8df4db7ced97d29f` | `29551a44bf2ab6c24a01af0a2b869852c1ad0777dc0d9c7e29b1f2fdbc122081` |
| P11 | `org/springframework/http/converter/protobuf/ProtobufHttpMessageConverter.class` | `a9838230279a078492dcbaa64c1cadb0da5bc808d78d05137c2b1dc93e8bb41f` | the same |
| P11 | `…/ProtobufHttpMessageConverter$ProtobufJavaUtilSupport.class` | `039eace814fc9291fe05d6d96be3d20ae90f185c3ed301469ad22068e2fa7d4e` | `3b3a46ea1f7e3c622c65133f23c71ce5113ad6f8817cde669f0513d8115a6b4d` (the only class the landing changes) |
| P11 | `…/ProtobufHttpMessageConverter$ProtobufJavaFormatSupport.class` | `2d6e9d84e5da9f130e64f5820b200850d35deca11e096be43c270493991937c2` | the same |
| P11 | `…/ProtobufHttpMessageConverter$ProtobufFormatSupport.class` | `92941c7a4b397f4bd157df1c020d85a3f53f37df6c8fab7158e499dd66f14ac3` | the same |
| P16 | `org/springframework/jdbc/datasource/init/ScriptUtils.class` | `6a98d2deafc602b2aca6073f872ff60a2a797ffe9aded2a09e33ca5fe1d121a9` | `3d9add8dcfedd58a2e027496c3c957de81890b5fd9970673a64e7e18e3d0c6a8` |
| P18 | `org/springframework/jdbc/support/DatabaseStartupValidator.class` | `2538bd6aa665dbe554ff6ddb06aa836d39df4900ea694b5d849225d5e84a4813` | `28f4e3424067adf63ecf5a3326cf3b733cb5b11fa95d5f6cfae09472884b0945` |
| P19 | `org/springframework/transaction/reactive/TransactionalOperator.class` | `d0858b8a685b905087ec427e4f7c377b231f1a35bfcbcdfa6d4ac3559e08f250` | `ac76908876452b9f3e9b5e0428e7a6d23259bf28cabc901a97e3bf6c6ba2427f` |
| P19 | `org/springframework/transaction/reactive/TransactionalOperatorImpl.class` | `7e5d0207ba512a62fc4cd4a10b823ba58894d18afda741a488adb6e7a93453ac` | `90ebcb8bad4b6c7aed5b0695fdef4ad612c1cb4bd8a71a7f5f0f5716627d6347` |
| P23 | `org/springframework/orm/hibernate5/SpringBeanContainer.class` | `40c924668c26b9de5d50cb69cbb088174eb487e2bd9e991c0ac7bc22bbf77b0e` | `740e7216f2e4c6b82d7b1d50a1873c36c2d8b90a1a7f202af1fa7dfb305b58c0` |
| P23 | `…/SpringBeanContainer$SpringContainedBean.class` | `0ae26807bce99441222a7158462792659a3df1cbd864de7ac265d7ef590ba50a` | `367d9cc4df368610715a6767fea86ac9ca1e554a0458781419e9fc9ee1a808c7` |

**What the slice route does not give.** Every other class of the module and its dependencies is the base release's, not the
pin's, so a test or scenario touching code that moved between that release and the pin sees the release. The fix slices of P05,
P16, P18, P19 and P23 are the only builds of their fix pins' changed files (no release equals them). Only the landed test classes
ran, not the module suites.

## Released artifacts

From Maven Central, or `repo.spring.io/milestone` for milestones and RCs, resolved with Maven into `$P/m2`
(`$P/scripts/release_set.sh SET "BOMS" "COORDS"`, a generated pom per set in `$P/releases/SET/pom.xml`, runtime scope); each set has
its jars in `$P/releases/SET/jars/` and a `:`-joined `classpath.txt` of `$P/m2` paths. Every jar's sha1 equals its repository's
`.sha1` (125 of 125); `.asc` signatures were fetched and checked in `$P/gnupg`, getting keys from keyserver.ubuntu.com /
keys.openpgp.org (`$P/scripts/verify_releases.sh`, results with sha256 in `$P/logs/release-verify.txt`). Spring's optional
dependencies are not in its 5.x poms, so the versions below come from the pins' or release tags' build files.

| Set | Why | Main jar sha256 | Signature |
|---|---|---|---|
| `spring-web-5.0.0.RC4` | P11 parent's converter; the version the brief names | `4c3cc9cc303497b9f6f2415a7bd2bf96b4e738b28a288e617fbfad054faa42b1` | milestone, no `.asc` |
| `spring-web-5.0.0.RELEASE` | P11 fix's converter | `7ab01ee538bfc6ed6f303bc9bbe5e823644fed59eb48c75e0c4cf2a17ec93d7b` | key `9A2C7A98E457C53D` not obtainable |
| (both P11 sets) | `com.google.protobuf:protobuf-java-util:3.4.0` (with protobuf-java 3.4.0, gson 2.7, guava 19.0), as the pins' `spring-web.gradle` declares | | protobuf jars: see the log |
| `protobuf-java-format-1.4` | the alternative provider the brief names, kept **apart** (the public constructor prefers it when present) | `80fd09b87c569f2ba76837dcd9096edbbca74246c00726b0e596ab474308eb3c` | good, `6239EDB70F8B00C7` |
| `spring-test-5.1.0.RC1`, `spring-test-5.1.0.RC2` | P09 parent and fix, with `javax.servlet-api:4.0.1` (the pins' `spring-test.gradle`) | RC1 `4870bb8719a8784dbb65b0309e2aca1e5754ca1eb7be7bf69603f38d22b5c692`, RC2 `e0fed2ff1ffc3a77eda5c148440feddbb64af5f3034429e02ecbbfb25b10a9d0` | milestones, no `.asc` |
| `spring-beans-5.1.6.RELEASE`, `spring-beans-5.2.0.M1` | P05 parent, nearest fix | 5.1.6 `230fc4bd94573bdd0fade9e492b218338a2260fc737b4ea853b877cc447be994`, M1 `c583d8355a691ad4dd3105bc328fed10530d1be9141407f090cd36a2b76b420e` | 5.1.6 unchecked (key), M1 no `.asc` |
| `spring-jdbc-5.1.4.RELEASE`, `spring-jdbc-5.1.5.RELEASE` | P16 parent and nearest fix, with h2 1.4.197, hsqldb 2.4.1 and derby 10.14.2.0 (the pins' optional `spring-jdbc` databases; the choice of one is the domain work's) | 5.1.4 `9a160283e380f6c60961901b64b31eb5f2d7a9375d6fbfc477f2438c2f8913b7`, 5.1.5 `6b30c02543ff33d165203d851feb03a48ee83b0331f8accea3928a98f9628e25` | unchecked (key) |
| `spring-jdbc-5.2.7.RELEASE`, `spring-jdbc-5.3.0-M1` | P18 parent and nearest fix | 5.2.7 `2532f26566ffaefe6a641f8bcb51983405543600ae0e79f18fc80442a051a27b`, M1 `1cc97fe183dbf7f12f0ee170ef5665dcd50312e307e57dfdf93c3ff614a5c235` | 5.2.7 unchecked (key), M1 no `.asc` |
| `spring-tx-5.2.0.RC2`, `spring-tx-5.2.0.RELEASE` | P19 parent and nearest fix, with reactor-core and reactor-test of `reactor-bom:Dysprosium-RC1` (3.3.0.RC1) and `Dysprosium-RELEASE` (3.3.0.RELEASE), as the `v5.2.0.RC2` and `v5.2.0.RELEASE` tags' `build.gradle` import | RC2 `e045a9ed06c4b7cb2c26294dff665281affe51f91a65159fb7c21fb950b8f456`, RELEASE `bedfa98661781e6835d32f90903dd0da9ac2c4f1f7e2b67f91e784fae50dfee1` | RC2 no `.asc`; RELEASE unchecked (key) |
| `spring-orm-5.1.4.RELEASE`, `spring-orm-5.1.5.RELEASE` | P23 parent and nearest fix, with spring-context of the same version, `hibernate-core:5.4.1.Final` (the version the brief and the pins' `spring-orm.gradle` name) and hsqldb 2.4.1 (the pins' test database) | 5.1.4 `12cd51b65b2781a6a35403dc82d7b261688706a0f8543c087ec483ddbf8ec77a`, 5.1.5 `cdc0ce57e0a1c76732e2ee2299ec78501a0c925ccebf9e856bf4066acc44f291` | unchecked (key) |
| `spring-context-5.3.18` | P26: the issue reports 5.3.18 or earlier; with aspectjweaver 1.9.7 (the `v5.3.18` tag's AspectJ) | `6f307ea6e140d7f6f7fcffc7bb8c1540dd244c1039d8f7e7b8f3ddec6c73f59c` | unchecked (key) |
| `jasync-r2dbc-mysql-2.1.19`, `jasync-r2dbc-mysql-2.1.20` | P20: the two driver versions the PR discussion names (2.1.20 carries the driver-side mitigation) | 2.1.19 `88f4af3755238104fe576e44fd72fee94caabdfc52c1477c766881f57ce31939`, 2.1.20 `9e755bbb5427f5e77bf940935a3d638449612c707e5f0fc3a2537d48a65ba659` | good, `36D4E9618F3ADAB5` |
| `tests-P05`, `tests-P09`, `tests-P11`, `tests-P16`, `tests-P18`, `tests-P19`, `tests-P23` | the [slice route](#the-5x-cases-on-the-slice-route)'s test libraries, at the versions each 5.x pin's `build.gradle` declares, with `junit-platform-console-standalone` 1.6.2 (P19: 1.5.2) | (68 jars, sha256 in the log) | 56 good, 2 by a key expired since (assertj-core 3.11.0 and 3.13.2, `E2B3D84202B812D9`), 10 by the revoked byte-buddy key below |


Signature summary over the first 125 jars: 44 carry Spring's (and Reactor's) key `9A2C7A98E457C53D`, which keyserver.ubuntu.com and
keys.openpgp.org return without a user id, so gpg cannot import it (unchecked; the O01–O20 setup could not get it either);
reactive-streams 1.0.3's key `1364C5E2DF3E99C5` likewise; 29 have no `.asc` (Spring milestones and RCs, Reactor RCs and some
Hibernate dependencies); byte-buddy 1.9.5 is signed by a key revoked since (`REVKEYSIG BB2914C1FA0811C3`); 50 are good
signatures (39, plus 11 by keys expired since). The jasync sets pull `r2dbc-spi:1.0.0.RELEASE`, Kotlin 1.6.21 and Netty 4.1.86.
With the test sets, 193 jars: every sha1 matches, 95 good signatures, 13 by keys expired since, 11 by a revoked key, 45 unchecked
(key not importable), 29 without `.asc` (`$P/logs/release-verify.txt`, rerun 2026-11-26 after the test sets were added).

## Snapshot dependencies

The 7.1.0-SNAPSHOT platforms import `reactor-bom:2026.0.0-SNAPSHOT` (reactor-core and reactor-test 3.9.0-SNAPSHOT,
reactor-netty 1.4.0-SNAPSHOT) and `micrometer-bom:1.18.0-SNAPSHOT`; their cached jars have the same digests as the O01–O20
setup's of 2026-11-25. P20 (6.0.5-SNAPSHOT) imports `reactor-bom:2022.0.3-SNAPSHOT` and `micrometer-bom:1.10.4-SNAPSHOT`, which
`repo.spring.io/snapshot` serves only as their last builds: reactor-core 3.5.3-SNAPSHOT `20230214.110429`, reactor-netty-http
1.1.3-SNAPSHOT `20230214.122029`, micrometer-observation 1.10.4-SNAPSHOT `20230213.230149`, ten days after P20's pins
(2023-02-03), not the builds of the pin's date. Both pins of a case read the same bytes; build `--offline` to keep them.

| Module | sha256 |
|---|---|
| `io.micrometer:micrometer-commons:1.10.4-SNAPSHOT` | `779baf6da3f9bee44bf7f1a67b655c472f477bd97a0c1759a73648ce9e42d2cc` |
| `io.micrometer:micrometer-commons:1.18.0-SNAPSHOT` | `1b3add3a081c9e9390fe3305dff43db944ea7a39b9a50a03acb1e3e65497eff9` |
| `io.micrometer:micrometer-core:1.18.0-SNAPSHOT` | `048dcfc51a98e344c22bc17720bceca999f65f7a5fd403a967b7aea296547fa6` |
| `io.micrometer:micrometer-jakarta9:1.18.0-SNAPSHOT` | `c5809b29a8458dd9128ff5e5f5beda7cdad73bbe72527f4b990a1c29a90fe6b1` |
| `io.micrometer:micrometer-observation:1.10.4-SNAPSHOT` | `e573abb99f25611417355b7370f801f51be019eb010ed444f97e26b0baa7f9b0` |
| `io.micrometer:micrometer-observation:1.18.0-SNAPSHOT` | `e1c8305e6b8e30563012c3aa6cea565a9367ba773202386e8015efa5a46e6964` |
| `io.micrometer:micrometer-observation-test:1.10.4-SNAPSHOT` | `79a770fe29e2a53b1fd418f8b9ce35a2019fd3fa2c855d2557d2d86be21ed384` |
| `io.micrometer:micrometer-observation-test:1.18.0-SNAPSHOT` | `d4e85b7504c8621ba20e56a11bf4c0ff062b03a0b553bfce6d9e24c6d37da742` |
| `io.projectreactor.netty:reactor-netty-core:1.1.3-SNAPSHOT` | `ba4ae81fe3650c3a2e25677d377f9fe15ca9c5de1fd99e31cd24624ddbe7f825` |
| `io.projectreactor.netty:reactor-netty-core:1.4.0-SNAPSHOT` | `eec27fecf961e887aa8ec1d1add4173556bf46d9ca87c429295ae93c2ebbba03` |
| `io.projectreactor.netty:reactor-netty-http:1.1.3-SNAPSHOT` | `95c6775b50d1b6df931b571ba8e5a41561790909dbd862e0bc5b9006bec8a2d6` |
| `io.projectreactor.netty:reactor-netty-http:1.4.0-SNAPSHOT` | `e28e59e57bb53e643b71f8ec5aa253db868cbb5190bcd4ea67509c9d44533e55` |
| `io.projectreactor:reactor-core:3.5.3-SNAPSHOT` | `3b5ae2f28f08a59d552e19132b5b2d816e0752aedd42c40ab899562a8a0cf693` |
| `io.projectreactor:reactor-core:3.9.0-SNAPSHOT` | `51436b9a3967185ee445d5db4053c5c43886465121383f6196d8f383a66bfc72` |
| `io.projectreactor:reactor-test:3.5.3-SNAPSHOT` | `939c3e79174c963835bfc4aadbc6247d3c2b56d1aa67f14166037d8905337ac5` |
| `io.projectreactor:reactor-test:3.9.0-SNAPSHOT` | `129ede5ed343d6996fa427f48ffb29d56d0b7a6814d006c00e3c644a985b44a3` |

## Jobs

One job per buildable case (23; the seven 5.x cases have none), each of four steps run by `$P/scripts/case_job.sh CASE STEP`
(table of modules and test classes: `$P/scripts/cases.tsv`, the landed `*Tests.java` files; submitted by
`$P/scripts/submit_case.sh`):

1. `fix`: in `$W/CASE-fix`, offline: `:M:jar` for the case's jar modules and `:M:test --tests CLASS` for each landed test class,
   with `-Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline --continue`; then keeps
   `$P/artifacts/CASE-fix/`: `jars/`, `SHA256SUMS` (jars, and every class compiled from a production source file the landing
   changed, nested classes included) and, per classpath module M, `M.runtimeClasspath.txt` and `M.testRuntimeClasspath.txt`
   (`:`-joined; the project outputs they name are copied under `tree/`, the rest are paths into `$P/gradle-home`; written by
   `-I $P/scripts/resolve-all.init.gradle :M:setupWriteClasspath -PsetupCpConf=CONF -PsetupCpOut=FILE`).
2. `parent`: the same in `$W/CASE-parent`, with those landed classes that exist at the parent.
3. `transplant`: `git archive` of the parent into `$P/build/CASE-parent-landed`, every changed file under `src/test` or
   `src/testFixtures` taken from the fix (and a changed module build file: only P27's `spring-test.gradle`, which adds
   `testImplementation("org.awaitility:awaitility")`), then the same test classes. Passes when they fail
   (`TRANSPLANT-FAILS-AS-EXPECTED`) or do not compile (`TRANSPLANT-DOES-NOT-COMPILE-AS-EXPECTED`).
4. `clean`: `git clean -fdxq` in both worktrees, transplant copy removed.

Jar and classpath modules are those with changed production sources, plus the test module; P22 adds spring-context (the
brief's scenario builds its proxies through `@Bean` in an `AnnotationConfigApplicationContext`). Before submitting,
`case_job.sh CASE dryrun` (offline `--dry-run` of both pins' task graphs, the classpath tasks included) configured for each
case (`$P/logs/dryrun-6x.txt`, `$P/logs/dryrun-7x.txt`; the first batch of 7.x dry-runs was stopped by a time limit after P07's fix pin and rerun from there). Logs per step: `$P/logs/CASE-ROLE.test.offline.{log,junit.txt,class.txt}`,
`$P/logs/CASE-parent-landed.test.offline.*`, `$P/logs/CASE-ROLE.cp-M-CONF.log`.

| Case | Job |
|---|---|
| P20 | `20261126-025058-setup-build-spring-framework-29703-p20-a` |
| P21 | `20261126-025059-setup-build-spring-framework-33533-p21-a` |
| P22 | `20261126-025059-setup-build-spring-framework-35627-p22-a` |
| P24 | `20261126-025059-setup-build-spring-framework-34723-p24-a` |
| P25 | `20261126-025059-setup-build-spring-framework-32469-p25-a` |
| P26 | `20261126-025059-setup-build-spring-framework-28322-p26-a` |
| P27 | `20261126-025059-setup-build-spring-framework-30020-p27-a` |
| P28 | `20261126-025059-setup-build-spring-framework-33470-p28-a` |
| P25 (rerun) | `20261126-032211-setup-build-spring-framework-32469-p25-a` |
| P01 | `20261126-032325-setup-build-spring-framework-37435-p01-a` |
| P02 | `20261126-032325-setup-build-spring-framework-37349-p02-a` |
| P03 | `20261126-032325-setup-build-spring-framework-36480-p03-a` |
| P04 | `20261126-032326-setup-build-spring-framework-36207-p04-a` |
| P06 | `20261126-032326-setup-build-spring-framework-37351-p06-a` |
| P07 | `20261126-032326-setup-build-spring-framework-36626-p07-a` |
| P08 | `20261126-032326-setup-build-spring-framework-37596-p08-a` |
| P10 | `20261126-032326-setup-build-spring-framework-37531-p10-a` |
| P12 | `20261126-032326-setup-build-spring-framework-37559-p12-a` |
| P13 | `20261126-032326-setup-build-spring-framework-37202-p13-a` |
| P14 | `20261126-032327-setup-build-spring-framework-37059-p14-a` |
| P15 | `20261126-032327-setup-build-spring-framework-37159-p15-a` |
| P17 | `20261126-032327-setup-build-spring-framework-37014-p17-a` |
| P29 | `20261126-032327-setup-build-spring-framework-36556-p29-a` |
| P30 | `20261126-032327-setup-build-spring-framework-36865-p30-a` |

The first P25 job (`…-025059-…-p25-a`) failed: its landed `ProxyExceptionHandlingTests` is abstract and its tests live in two
nested subclasses (`ObjenesisCglibAopProxyTests`, `JdkAopProxyTests`), which `--tests ProxyExceptionHandlingTests` does not select
("No tests found for given includes"), so the fix step ran no test and the transplant step had nothing to fail. `cases.tsv` now
names it `ProxyExceptionHandlingTests*`, `case_job.sh` strips the `*` when it looks for the source file and collects the nested
classes' results, and the transplant deletes a test file the landing removed (P25 removes `ClassWithConstructor.java`; before, the
copy kept it). No other case's landed test class is abstract.

## Job results

Read from the step logs in `$P/logs/` after the runner finished the jobs on 2026-11-26. The runner recorded the results on
another head, not in this record's commits: the 6.x jobs first in commit `a31e51b72c46`, all 24 now in commit `933de3d18d34`
(`python3 verification/pipeline.py status` lists them as "recorded on another head"). Fix and parent columns: the landed test classes at that pin (a
class the landing adds is absent at the parent, so that step builds the jars only). Transplant: the fix's changed test files on
a copy of the parent.

**Spring 7.x cases.** Fourteen jobs passed every step. P15's job (`20261126-032327-setup-build-spring-framework-37159-p15-a`)
is recorded as failed, at its transplant step only: fix, parent and clean passed.

| Case | Fix | Parent | Transplant |
|---|---|---|---|
| P01 | exit 0, 95 tests, 0 failures, 0 errors (127 s) | exit 0, 86 tests, 0 failures, 0 errors (67 s) | **fails**: 95 tests, 3 failures, 0 errors; `StringUtilsTests#[1]`, `StringUtilsTests#[7]`, `StringUtilsTests#[8]` |
| P02 | exit 0, 13 tests, 0 failures, 0 errors (67 s) | exit 0, 12 tests, 0 failures, 0 errors (61 s) | **fails**: 13 tests, 1 failures, 0 errors; `TypeMappedAnnotationTests#adaptFromSingleValueToArray()` |
| P03 | exit 0, 24 tests, 0 failures, 0 errors (127 s) | exit 0, 23 tests, 0 failures, 0 errors (59 s) | **fails**: 24 tests, 1 failures, 0 errors; `GenericTypeResolverTests#resolveTypeFromNestedParameterizedType()` |
| P04 | exit 0, 15 tests, 0 failures, 0 errors (133 s) | exit 0, 14 tests, 0 failures, 0 errors (73 s) | **does not compile**: `YamlProcessorTests.java:224` no suitable method found for getFlattenedMap(Map<String,Object>,boolean,Object); `YamlProcessorTests.java:224` no suitable method found for getFlattenedMap(Map<String,Object>,boolean,Object) |
| P06 | exit 0, 23 tests, 0 failures, 0 errors (66 s) | exit 0, 18 tests, 0 failures, 0 errors (63 s) | **fails**: 23 tests, 3 failures, 0 errors; `LinkedCaseInsensitiveMapTests#computeIfAbsentAfterNullComputedValueUsesGivenKey()`, `LinkedCaseInsensitiveMapTests#computeIfAbsentWithFailingMappingFunction()`, `LinkedCaseInsensitiveMapTests#computeIfAbsentWithNullComputedValue()` |
| P07 | exit 0, 10 tests, 0 failures, 0 errors (77 s) | exit 0, 6 tests, 0 failures, 0 errors (77 s) | **fails**: 10 tests, 4 failures, 0 errors; `SimpleMailMessageTests#copyConstructorCopiesSentDate()`, `SimpleMailMessageTests#copyToCopiesSentDate()`, `SimpleMailMessageTests#getSentDateReturnsACopy()`, `SimpleMailMessageTests#setSentDateStoresACopy()` |
| P08 | exit 0, 24 tests, 0 failures, 0 errors (68 s) | exit 0, 23 tests, 0 failures, 0 errors (72 s) | **fails**: 24 tests, 1 failures, 0 errors; `RetryPolicyTests$BuilderTests#includesAndExcludesNotChangedByBuilderAfterBuild()` |
| P10 | exit 0, 23 tests, 0 failures, 0 errors (124 s) | exit 0, 21 tests, 0 failures, 0 errors (120 s) | **fails**: 23 tests, 1 failures, 0 errors; `MultipartHttpMessageConverterTests$ReadingTests#[1]` |
| P12 | exit 0, 7 tests, 0 failures, 0 errors (118 s) | exit 0, 6 tests, 0 failures, 0 errors (114 s) | **fails**: 7 tests, 1 failures, 0 errors; `ProtobufJsonEncoderTests#canEncode()` |
| P13 | exit 0, 21 tests, 0 failures, 0 errors (126 s) | exit 0, 19 tests, 0 failures, 0 errors (109 s) | **fails**: 21 tests, 2 failures, 0 errors; `MultipartHttpMessageConverterTests$ReadingTests#readMultipartEmptyLastPart()`, `MultipartHttpMessageConverterTests$ReadingTests#readMultipartEmptyPart()` |
| P14 | exit 0, 18 tests, 0 failures, 0 errors (125 s) | exit 0, 17 tests, 0 failures, 0 errors (102 s) | **fails**: 18 tests, 1 failures, 0 errors; `JacksonJsonEncoderTests#releasesBufferRecyclerToPool()` |
| P15 | exit 0, 7 tests, 0 failures, 0 errors (121 s) | exit 0, 5 tests, 0 failures, 0 errors (93 s) | **fails, then hangs**: `SubscriberInputStreamTests > interruptWhileAwaitingData() FAILED`, `AssertionFailedError` at `SubscriberInputStreamTests.java:278`; the test task then made no progress until the step's 3000 s Gradle timeout (exit 124), so no JUnit XML was written and the job reports the step failed (see below) |
| P17 | exit 0, 5 tests, 0 failures, 0 errors (79 s) | exit 0, 2 tests, 0 failures, 0 errors (74 s) | **fails**: 5 tests, 2 failures, 0 errors; `TableMetaDataContextTests#overlappingDeclaredAndGeneratedKeyColumnsAreRejected()`, `TableMetaDataContextTests#overlappingDeclaredAndGeneratedKeyColumnsAreRejectedRegardlessOfCase()` |
| P29 | exit 0, 8 tests, 0 failures, 0 errors (92 s) | exit 0, 7 tests, 0 failures, 0 errors (82 s) | **does not compile**: `ScheduledTaskRegistrarTests.java:89` no suitable method found for addCronTask(Runnable,String,ZoneId); `ScheduledTaskRegistrarTests.java:89` no suitable method found for addCronTask(Runnable,String,ZoneId) |
| P30 | exit 0, 72 tests, 0 failures, 0 errors (117 s) | exit 0, 70 tests, 0 failures, 0 errors (89 s) | **fails**: 72 tests, 3 failures, 0 errors; `BitsCronFieldTests#nextOrSameWithGapAfterRollForward()`, `BitsCronFieldTests#nextOrSameWithMidnightGap()`, `CronExpressionTests#daylightSaving()` |

P04 and P29 do not compile on the parent: their landed tests call the signatures the landings add (the three-argument
`getFlattenedMap(Map, boolean, Object)` and `addCronTask(Runnable, String, ZoneId)`). P01's and P10's failures are parameterized
invocations, with these arguments (`$P/logs/CASE-parent-landed.test.offline.junit.txt`): P01 `truncateSurrogatePairs` `[1]`
text = "a😀b", threshold = 2, expected = "a (truncated)..."; `[7]` text = "😀b", threshold = 1, expected = " (truncated)...";
`[8]` the same as `[1]` with a `StringBuilder`; P10 `readMultipartFileContentMoreThanOnce` `[1]` maxInMemorySize = 262144 (the
in-memory case; `[2]`, maxInMemorySize = 1, passes on the parent). P15's hang on the parent is
the behaviour the PR describes (an interrupted read stays blocked until an upstream signal). No later test of that class reported
a result, so which test blocked is not recorded. A rerun with a per-test timeout, e.g.
`-Djunit.jupiter.execution.timeout.default=60s`, would name it; that was not queued. The timeout ended the Gradle processes and the
`clean` step removed `$P/build/P15-parent-landed`; no process or copy remained.

**Spring 6.x cases.** Seven jobs passed every step; P25's first job failed (above), and its rerun passed every step.

| Case | Fix | Parent | Transplant |
|---|---|---|---|
| P20 | exit 0, 14 tests, 0 failures, 0 errors (216 s) | exit 0, 13 tests, 0 failures, 0 errors (178 s) | **fails**: 14 tests, 1 failure; `R2dbcTransactionManagerUnitTests#testConnectionReleasedWhenRollbackFails()`, `AssertionError` at `R2dbcTransactionManagerUnitTests.java:348` |
| P21 | exit 0, 1 test, 0 failures, 0 errors (239 s) | jars only (the test class is new) (170 s) | **fails**: 1 test, 1 failure; `AnnotatedBeanDefinitionReaderTests#registerBeanWithQualifiers()`, `AssertionFailedError` at `AnnotatedBeanDefinitionReaderTests.java:46` |
| P22 | exit 0, 7 tests, 0 failures, 0 errors (123 s) | exit 0, 4 tests, 0 failures, 0 errors (64 s) | **fails**: 7 tests, 2 failures; `ScopedProxyUtilsTests#createScopedProxyTargetCleansAutowireSettingsInTargetDefinition()`, `#createScopedProxyTargetOvertakesAutowireSettingsToProxyBeanDefinition()` (`ScopedProxyUtilsTests.java:94`, `:137`) |
| P24 | exit 0, 63 tests, 0 failures, 0 errors (277 s) | exit 0, 35 tests, 0 failures, 0 errors (120 s) | **does not compile**: 35 errors, 31 of them `cannot find symbol: method contextName()` (the attribute the landing adds to `@TestBean`, `@MockitoBean`, `@MockitoSpyBean`), the rest `constructor BeanOverrideHandler ... cannot be applied to given types` (`BeanOverrideContextCustomizerTests.java:74`, `DummyBean.java:69`, `EasyMockBeanOverrideHandler.java:46`) |
| P25 | exit 0, 12 tests, 0 failures, 0 errors (123 s) | jars only (the test class is new) (53 s) | **fails**: 12 tests, 2 failures, 0 errors; `ProxyExceptionHandlingTests$WhenThereAreNoInterceptors#targetThrowsUndeclaredCheckedException()`, `ProxyExceptionHandlingTests$WhenThereIsOneInterceptor#targetThrowsUndeclaredCheckedException()` |
| P26 | exit 0, 32 tests, 0 failures, 0 errors (225 s) | exit 0, 31 tests, 0 failures, 0 errors (206 s) | **fails**: 32 tests, 1 failure; `ApplicationContextEventTests#eventForSelfInjectedProxiedListenerFiredOnlyOnce()`, `AssertionFailedError` at `ApplicationContextEventTests.java:293` |
| P27 | exit 0, 6 tests, 0 failures, 0 errors (242 s) | exit 0, 2 tests, 0 failures, 0 errors (209 s; the JUnit 4 and TestNG classes are new) | **fails**: 6 tests, 6 failures; `ParallelApplicationEventsIntegrationTests#executeTestsInParallelInstancePerMethod()`, `#rejectTestsInParallelWithInstancePerClassAndRecordApplicationEvents()`, `JUnit4ApplicationEventsAsyncIntegrationTests#asyncPublication`, `#asyncConsumption`, `TestNGApplicationEventsAsyncIntegrationTests#asyncPublication`, `#asyncConsumption` |
| P28 | exit 0, 15 tests, 0 failures, 0 errors (196 s) | exit 0, 11 tests, 0 failures, 0 errors (206 s) | **fails**: 15 tests, 1 failure; `TransactionalApplicationListenerMethodAdapterTests#withTransactionalAnnotationOnEnclosingClass()`, `AssertionError` at `TransactionalApplicationListenerMethodAdapterTests.java:165` |

P27's transplant compiled with the fix's `spring-test.gradle` (Awaitility); its failures are assertions and, in the JUnit 4 class,
an `IllegalStateException` at `JUnit4ApplicationEventsAsyncIntegrationTests.java:74`. P24's fix pin runs 63 tests across its 29
landed classes.

After all 24 jobs, none of the 61 worktrees (the 47 of the built cases, P29's `later` included, and the 14 of the 5.x cases)
has an untracked, ignored or modified file, and no `$P/build/` copy remains.

## Digests of the built artifacts

Each `$P/artifacts/CASE-ROLE/SHA256SUMS` lists the module jars (`jars/`), the project jars on the kept classpaths (`tree/…`) and
the class digests of every production source file the landing changed (nested classes included). Jar digests include build
timestamps in the 6.x builds; the 7.x builds write reproducible jars (entries dated 1980-02-01). The class digests are what
compare across builds. Rows from `python3 -I $P/scripts/digest_rows.py CASE...` (also in `$P/logs/digest-rows.md`); the 5.x slices'
class digests are in [their section](#the-5x-cases-on-the-slice-route).

| Case | Role | Module jar sha256 | Changed classes (sha256) |
|---|---|---|---|
| P01 | fix | `spring-core-7.1.0-SNAPSHOT.jar` `3d5e0896f4c86f0edbb264c12b3a74dd8ef3be06323f5a5e0e292354dc083cbd` | `StringUtils.class` `fe617940c4bb20abda81b21d638ee45b1744934d2e1bbfbd06346ede3217a279` |
| P01 | parent | `spring-core-7.1.0-SNAPSHOT.jar` `02bdefc275f29642200c81c91124b5815045e11b8b24395b011bf057726c39a7` | `e855027d0a12f8d21d3c78b92aac70d8d9ab73cfb83022a376e6ca57e0bcfb75` (same order) |
| P02 | fix | `spring-core-7.0.10-SNAPSHOT.jar` `07e4efa64779531f31abc7397bbc3ad7bf597e695704abb1eabf9eeee3fe096c` | `TypeMappedAnnotation.class` `20f9e8e7c50024361053048d63fac4dd4644d086928432b402a532190b5fcd78` |
| P02 | parent | `spring-core-7.0.10-SNAPSHOT.jar` `7224611050fbe55257b777856c5c4548ba6fd700519952a21c08dc9a6929b4fe` | `c4a82968d7f1aec16de2e038ffa2dc61adfcb4f22ca463c8f0c957d981ec9c14` (same order) |
| P03 | fix | `spring-core-7.1.0-SNAPSHOT.jar` `901efd0f96fe9cdadf5c95476291585689cd47434940c3e29ece3bf2312768aa` | `GenericTypeResolver.class` `b32cc5c8a4e059ee15c748a3b4d4dff2696e710ac72bf29f21a0f3bab72f8fa1` (+1 nested) |
| P03 | parent | `spring-core-7.1.0-SNAPSHOT.jar` `fd6696b2420c996412505dfbc531aae6cf7b3cb2adb6172f903a254b9c08bff5` | `b7af0edcded2c911da8bb520f56d29500f6ce374c561a4402b382afb44b7aca5` (same order) |
| P04 | fix | `spring-beans-7.0.4-SNAPSHOT.jar` `2d52f5c264bce95ee57f5e2adc765020797f6b73c4effec72271dafb5e2f073c` | `YamlProcessor.class` `9c0db1d6f43534f2290724398998e6a2f77aa7220765b55a0be872f35df71378` (+5 nested) |
| P04 | parent | `spring-beans-7.0.4-SNAPSHOT.jar` `5730b939595d97cea9fc65a460afd0529a7d1f9787a08d6143b78b73866efb34` | `44316441ba5b11854bade50e56f06ae8753f44ca18c1f41699611de8474226d8` (same order) |
| P06 | fix | `spring-core-7.0.10-SNAPSHOT.jar` `7224611050fbe55257b777856c5c4548ba6fd700519952a21c08dc9a6929b4fe` | `LinkedCaseInsensitiveMap.class` `b1a4e0cc6f2faaefcc0102010aa3918ec5e116bc771b15575b23c9f893e668ac` (+8 nested) |
| P06 | parent | `spring-core-7.0.10-SNAPSHOT.jar` `0657582c48cd2e4ac67d89021b4edda4a52e0f4b28712d358deca0d047cf6d48` | `d95ddb1b6a2b9e96161e5297d1e14b37bb240655c3eb6c9f4e202b2848fa76d7` (same order) |
| P07 | fix | `spring-context-support-7.1.0-SNAPSHOT.jar` `e88476a386b6f99d0b3b9da82a342d52ac8e6f6261baa3bae530856fa6c407f6` | `SimpleMailMessage.class` `9862522ea9c3357af09ecde9e76ca953e4db2d81b19d377dbf08aace73755c68` |
| P07 | parent | `spring-context-support-7.1.0-SNAPSHOT.jar` `d81270c6b324010ec58a76a7ffd87f13b37a8c12233cf1b7a82c7035351ff274` | `57e88c782e2f4175745ed66555f0eaf7c044b9fab69e1c675509367bbcf7fa57` (same order) |
| P08 | fix | `spring-core-7.1.0-SNAPSHOT.jar` `6abb58e66a4e45698cfd8a94a0a1a508e43e73c2db9f032e79848cc8f07db911` | `RetryPolicy.class` `9482539260e670593e00cf5f463dba653ea797d993277c68c83055978cfa5c58` (+1 nested) |
| P08 | parent | `spring-core-7.1.0-SNAPSHOT.jar` `c598e1829dcf34b172ea334dd2269074d95d133e5703a3d3a6032cf68309e06d` | `9482539260e670593e00cf5f463dba653ea797d993277c68c83055978cfa5c58` (same order) |
| P10 | fix | `spring-web-7.1.0-SNAPSHOT.jar` `089bc85060987cc92a18f766f2b1543c089beda2b99f4fd8df8ae4de542decc1` | `DefaultParts.class` `61d8e19964bad50744893fa8976a5442e3b5ed96121808b72023871fdf0c427c` (+7 nested), `PartGenerator.class` `382ca9a2b17c893822099042ee80b93101af26f5c20b9dc58f666d12f40b1fa7` (+5 nested) |
| P10 | parent | `spring-web-7.1.0-SNAPSHOT.jar` `7a852e35e0f26b50cb9a140ae1de40903916c1a5f3a288950d374ae0d27b8070` | `3b370c3a02382053a665e92f7308d98db36de3d2dabd36cc1ab50cf10bdf239b`, `f1ea4beececf7f301d8140aa72b27c9f930eb9745c21f0c11d90a0e1c5bfe07a` (same order) |
| P12 | fix | `spring-web-7.1.0-SNAPSHOT.jar` `29caadbbc6f0dc913ccd06bbeb495e791f126f388450bf190c6a8b6440f72401` | `ProtobufJsonEncoder.class` `18619b349caf353cc4fa0180bf510eff3813145411e61c81d785fff1afc995a3` (+1 nested) |
| P12 | parent | `spring-web-7.1.0-SNAPSHOT.jar` `ad136e9a1a6c10341b261c7be60c389e593f462b275c81e20a4facc3ef62680e` | `fc9a5b1bc4fa2c1e1b7eb806d5c804fb0fdaa417b310ccbc846a7c2a7d32eb3c` (same order) |
| P13 | fix | `spring-web-7.1.0-SNAPSHOT.jar` `9c39afa1509c97df49f6101412283e9dae97b20759915bca042123596483f9c4` | `PartGenerator.class` `f1ea4beececf7f301d8140aa72b27c9f930eb9745c21f0c11d90a0e1c5bfe07a` (+5 nested) |
| P13 | parent | `spring-web-7.1.0-SNAPSHOT.jar` `b1a579986995423b48e9f1e732234e7871e56ad5644ffa4a9bd0232c4c9dfb6c` | `42e17f6ac6717580d9baf1f1f8ab742912e77eb9ff66cc4add66e0bbf0e228ac` (same order) |
| P14 | fix | `spring-web-7.0.9-SNAPSHOT.jar` `e9cb8d3dac20d4e300a457ebaa21d3b7d4fdf39473589397532d44892505c47c` | `AbstractJacksonEncoder.class` `d945682935df8b9712e7fcebce262bee46f99c7250f7722d3ea728aba94338ac` (+1 nested), `AbstractJackson2Encoder.class` `c0e3fdb8f0242b86640c11a7613b50f3e905acd348542981928d5d34e7cac43b` (+1 nested) |
| P14 | parent | `spring-web-7.0.9-SNAPSHOT.jar` `51c64b5e8be5552d7b5213e32c28951b16e74ed805a04a445a2a27a2c722fa2e` | `3c09ab8bfcca56b144b2ad57da1e26dadfd8b4aad9c023a6258889439c418400`, `a5dfa807d7bfdf37e09a6e517d3cedcbc8371b9cde4d36e8a087c9c0d8a14138` (same order) |
| P15 | fix | `spring-core-7.0.11-SNAPSHOT.jar` `c6fcc56f311a947dd2044ed78e640637817518aa7141e5cec358f3cb96ee8deb`, `spring-web-7.0.11-SNAPSHOT.jar` `5d749ebf2d690bacf8fb7bafcdfcb7a5c1c810f97f50b7a247c1892129432256` | `spring-core SubscriberInputStream.class` `e3a49bcafe8df57e83bb32f9353e8d06592b8f33f4efb1eb075c12fdf4bf9641`, `spring-web SubscriberInputStream.class` `73c877171c6c226cfd6ac979b03d614da4f6e74718840afa255bfa4efc2cdf20` |
| P15 | parent | `spring-core-7.0.11-SNAPSHOT.jar` `c5c479ef500c19f64881867d3a87eefda335baa4f8963cc6ac5b2b7d1417759b`, `spring-web-7.0.11-SNAPSHOT.jar` `7ebbc777abea3893d4c0cf4107958d322fc27f9a657791eb21fc81bbca7780de` | `2a78db49ed8b674fc7842dfe46279bd493295ce8f36da6b210ff93f1848db40c`, `5665c81b93048bdf9fc2f5b15f734548e89c54f28d4df71ea25c1f6e8cda0f47` (same order) |
| P17 | fix | `spring-jdbc-7.1.0-SNAPSHOT.jar` `cf61f678e84ca0cea2400ded341d4b120b88bb025e895778894e08a19d761b7c` | `TableMetaDataContext.class` `9266a6161b951b83faa774f0605d89109fa36d103376fde5892a762e6873abf1` (+1 nested) |
| P17 | parent | `spring-jdbc-7.1.0-SNAPSHOT.jar` `4a215b93f79e65dd931c7ed8d28fd389ee48603aca9e91346521c51dd0ad019b` | `b575ff7dee1212c85afc8a8bd4493c6b180ba4a3faab908bc99ab8fa5784ffb6` (same order) |
| P20 | fix | `spring-r2dbc-6.0.5-SNAPSHOT.jar` `26a1379473cec763b0443b28827f1fb727794a459207d59b572f26b9173d2dca` | `R2dbcTransactionManager.class` `04c658722dda8488b0b1bc88c14b7235f0aefe056666692ac0a758a61cfec950` (+2 nested) |
| P20 | parent | `spring-r2dbc-6.0.5-SNAPSHOT.jar` `620746439f34da4db81645aa6ded4813579d024378c1ac07a960caa041526744` | `e7b097d6da2837c869956e9c96c71e81a480fcab71c8783726bc9afcc725cdf9` (same order) |
| P21 | fix | `spring-context-6.2.0-SNAPSHOT.jar` `e39ec9634537273119e1af02e8588cb8b1886b89aabcce845b8331929375067d` | `AnnotatedBeanDefinitionReader.class` `990587f4056e0de14e22f3f87e1c9fe9d1f83ab7ad4174a594b39cc7edca009d` |
| P21 | parent | `spring-context-6.2.0-SNAPSHOT.jar` `5277bf49833219ee8be153fbb9f516f42aa407eebc60ab00b1dc415f56f71114` | `7b7ebd1d3faa2631d780278deb89e3109900540eeb08b0b1ff188fb6d04fd8cd` (same order) |
| P22 | fix | `spring-aop-6.2.12-SNAPSHOT.jar` `bc86ca473d9c75074ff32bf53233a340904225ba7ea3de5fa2a120aa38b2b0f7`, `spring-context-6.2.12-SNAPSHOT.jar` `7f578906c49d82b29f7ce44958c3194c8a917bad0aa606d524ef947a2a5aad38` | `ScopedProxyUtils.class` `788428a1bcfc827148e2964711202125c174c2da2a5cb1332b36e0524b2996a0` |
| P22 | parent | `spring-aop-6.2.12-SNAPSHOT.jar` `6d5d7ea1bdb992e45a056f2ecce5516c4a277a6e47dd7a51fae6aba764a1527c`, `spring-context-6.2.12-SNAPSHOT.jar` `ac1081a5bec948c4ef0af37f2b8fe14e84f57ce0749b5b007b21a53b0062d543` | `d48757fe2db30b31ff6a528b733bc986d30a7b6e00feb9b65265b6bb976f298f` (same order) |
| P24 | fix | `spring-test-6.2.6-SNAPSHOT.jar` `820c60ad1a31fc1d0a09da4715f09ea1c276df2b43cbee0b37da9e0a804d79c8` | `ContextConfiguration.class` `ea2b05eefdd24a0629f770372e260b6c0ed5113471db28ca1807eb6c99a9f07e`, `ContextHierarchy.class` `55b8fdd76a90c479bd60f2f06fa86937d66621d65f452b16a45b3070873b40e0`, `BeanOverrideContextCustomizerFactory.class` `d94ccbc28e06f359c78bf793f2474c888833fc7262ecef9d93853c9703862147`, `BeanOverrideHandler.class` `bba8bcd85c5e24f1c8ac201ab4ae0a393c6237ea49e216ef99bf84124c360d06`, `BeanOverrideRegistry.class` `41bb048c0e4c17b9402e4b04a31016cbc2cfa2ea622772376cf5ba3b2ffd06ca`, `BeanOverrideTestExecutionListener.class` `924e91615a58e781ce7d961e451db84a48f3faa5bfe4fdaf7ae70aa7975a921c`, `TestBean.class` `500bcbf891ef99c7c6cdccba15fa315457245e398e493d2948915103e764dff2`, `TestBeanOverrideHandler.class` `cd025384929571e72d664de7c89512fb5d4a3c2b7320360feb775dc36c428806`, `TestBeanOverrideProcessor.class` `7a4c90fd37365290c7fc27d49b9f2ead3aa6930b838dbc1029f8b8b894c20e4d`, `AbstractMockitoBeanOverrideHandler.class` `cef6bd056d2a21391c1bad7adc1d934af4c4306af3108b72141f10e26d88017b`, `MockitoBean.class` `204a6e1c39095ff715c2b8fe00af965d8a78a86ba51c9148d3a57a8a60de6a6f`, `MockitoBeanOverrideHandler.class` `067b639053256118566837daf6e7cb3bebc6cfbd5b31f2638d11e4f4e26aba3b`, `MockitoSpyBean.class` `5639be826723881c30bc7d7ff4c8ed4b144cad7b8c7995e590b0b59ed377487f`, `MockitoSpyBeanOverrideHandler.class` `f9c314bc07a88d7b0708b93ffa9f3829c7422b7c80fd0ccafaec344cff92e268` (+1 nested) |
| P24 | parent | `spring-test-6.2.6-SNAPSHOT.jar` `ce1e6403b4f79e88665de1e07250000807ceeab5a53edc461516451a12b40e0d` | `ea2b05eefdd24a0629f770372e260b6c0ed5113471db28ca1807eb6c99a9f07e`, `55b8fdd76a90c479bd60f2f06fa86937d66621d65f452b16a45b3070873b40e0`, `7314a997702e1e42d28b0757ace2afd195edffee33e534cd8a2579911f83b51a`, `1034dd1cf0bbf8d845c7da8859af2dc9c14461e8048ce74c03a5d2b99ada61f2`, `ca77cdaaa88b1c71cea960d1efbeb4f94c2544bcd7ecb6099a502d451fd7db0f`, `3ae8a41272ad6e568eb8cd11053c86892e3edd6db6de07562115ff9cb8fa25ba`, `2647926d8e336d0893bc8c39f67892041781e5318342dc1db7a228cf822aa497`, `16a5d522c4324bcef5d3f6816f40398a935596236573071b6bad74a1e0dcb9e6`, `76b79e51d021174f234d6ba2c49891d1c9bf77528284f91da9bca5758fddd649`, `97c2fd6af8156d113cbbc27ab26490c795d1aa7e034ded84a60f843b4f69f004`, `88b6db03edbacb5d62e0c9ae8fefe76286b6975016112cbaf9ae1784b9d76422`, `088ff6b8dd52843b95fe126dd553272b103a58d38a5e473a6166e4eb6aef913e`, `ff4b6546dac216251415c1f5fa19fa95879a716ed0fd0dd1b6e7f06ada661500`, `5834780a61f6cf317d328739c143c0c79e9e68bf1259a57a8e1c54a6b59eba8b` (same order) |
| P25 | fix | `spring-aop-6.2.0-SNAPSHOT.jar` `f5485ec9040f62e4906e95bea50b7a4998c1fb02fc5961128e2fa1d55ada34f9`, `spring-core-6.2.0-SNAPSHOT.jar` `b6321db847ac24a25b399698fd7867468682262c2a7442b29af2c80dd36ff9f5` | `spring-aop CglibAopProxy.class` `b87b7d645f5538c0c130e5ab8bc4ee75261000beed2a16a290b4d7870a4e2f2e` (+13 nested), `spring-core ClassLoaderAwareGeneratorStrategy.class` `c7a6ec4b8ab9a40dedc1090b160c4a2294ff61023decd2aedbc3540d1f498550`, `spring-core UndeclaredThrowableTransformer.class` `61125e5e32d6edaa392324be859b7adc794b2c4c1447492d5e9262be2be8852e` (+1 nested) |
| P25 | parent | `spring-aop-6.2.0-SNAPSHOT.jar` `79e183e9d5ace65a07b00cb8750399ad048938081b71ecd0ee0e77e44e7d50bf`, `spring-core-6.2.0-SNAPSHOT.jar` `2c1769a0a15f17b79e080ac659ffd88e6b9738b9097eeb54d6687c022bcc339e` | `61d1a6adcd3ebe20135e57ca4dd68d2befe24a4b6b88550ecb4538a3acea658e`, `06b2112ac5c8b49adb6465ae6aa0b8d350871f93355e213d59cc50b83fa8f381`, `c0917db8de6d653597fbde6cfc912021df588891b4684dea0a177287dda90eb5` (same order) |
| P26 | fix | `spring-context-6.1.0-SNAPSHOT.jar` `a1e40e346fae2d9b801deb8aacc57a8f4348f4a8ee4742ed941a263391b35551` | `AbstractApplicationEventMulticaster.class` `98341caf544199f8cbdcf95aa847fd8c1f9c01863b6455f02b146c3f6322cf95` (+3 nested) |
| P26 | parent | `spring-context-6.1.0-SNAPSHOT.jar` `bea440658ef8616d16863041c96083dd710ee495e74fb6af16ed8bad0f565406` | `7d3229c8d82f6e41a1e4b12bb4235ff67d799b886cb4689c3dee1742586fcd75` (same order) |
| P27 | fix | `spring-test-6.1.0-SNAPSHOT.jar` `b071314be23db623623c1395cb919ed8638ddbb2b826f2d18a001ef80d9fa86e` | `ApplicationEventsHolder.class` `42a81c7eaf685366bd9e1cc724d159093fedf98c1671def8451ffb125554e5bc`, `DefaultApplicationEvents.class` `c4bcf52a844b80eb1f9e747d4cccb162ea333977498eae6ed0d339707fe0b539`, `SpringExtension.class` `6d79c4ea0dd1effb565527b7e55012c3d4382bbb12e3c2d08960ce50f244824f` |
| P27 | parent | `spring-test-6.1.0-SNAPSHOT.jar` `bbd2a2ef8c6f41e6c41640643c82b2b19fd0a8ec5e76cb1352f3a4cdbc56d877` | `e5a20c6ac5b9eddd55bb8ac9f7a4eb6b0315bb133159b90ee764efa96546af3a`, `5f0888ce4c51b8274f6836ac5d824b42562abb1613d59e793beff8ac3232b974`, `c794460a20f422b7e5aebc8554335644ae7b9143658730a16f9d4266596a30df` (same order) |
| P28 | fix | `spring-tx-6.2.0-SNAPSHOT.jar` `45579d181a53bb9f13e2733308c3b5253694b8dde6e96a2f5589f300c979a1da` | `RestrictedTransactionalEventListenerFactory.class` `12e3ba34092220d991941e1ef2cee00367ba471903a43672bb803ea60a268ad7` |
| P28 | parent | `spring-tx-6.2.0-SNAPSHOT.jar` `436a48b67a38f67fb00dbebafd238d2216890b6ec7098d3d8a1ac1d13910c480` | `49c205b9cbb66174ad655b9896cf2cbcea30f3adafdbec44c2d0c104e7c22aa9` (same order) |
| P29 | fix | `spring-context-7.1.0-SNAPSHOT.jar` `f96bbd001c050a1fbdba2127d1e35c82cf16d2762ddd016a3aa0750557e94b2c` | `ScheduledTaskRegistrar.class` `e6a78f7515fd5f94118263d1abb5bc3987b54d293c1d4a1a5ee98c5e56694b17` |
| P29 | parent | `spring-context-7.1.0-SNAPSHOT.jar` `3fba1194a07379a627fc4f4dba1ee200bcda743e259401fe68865c498f368cc7` | `13defb65bb0d1515d0bf918c73c12efa4941bfa9a1c530c9467f6b5ce439d21d` (same order) |
| P30 | fix | `spring-context-7.0.8-SNAPSHOT.jar` `07112b245a4c436eff2ffaab1e569fc0fddbe3babe2cc2cdac171e444e48dc8f` | `BitsCronField.class` `1db3066a3bf680fe8e6330721deece0b5df1e0aafd4fe541a2e5625743126870` |
| P30 | parent | `spring-context-7.0.8-SNAPSHOT.jar` `7e5b445af3373d774fe436c74f8225cf9c06f625bba874083e2422b2f63cdd88` | `daf70c5b5ae89b6dea34fefc6578dcd9bc1fd82f41c22e0b2e531b06e9439db9` (same order) |

**Classpath sizes** (entries in `$P/artifacts/CASE-ROLE/M.runtimeClasspath.txt` / `M.testRuntimeClasspath.txt`, the same at both
pins unless noted): spring-core 23 / 77 (P01, P02, P06, P08, P15), 23 / 78 (P03), 23 / 79 (P25); spring-beans 13 / 50 (P04);
spring-context-support 24 / 79 (P07); spring-web 106 / 202 (P10, P12, P13, P14, P15); spring-jdbc 22 / 56 (P17); spring-r2dbc
18 / 61 (P20); spring-context 34 / 110 (P21), 34 / 109 (P22), 33 / 97 (P26), 33 / 92 (P29, P30); spring-aop 14 / 64 (P22), 17 / 66
(P25); spring-test 122 / 257 (P24), 108 / 219 at the fix and 108 / 218 at the parent (P27, whose landing adds Awaitility); spring-tx
25 / 83 (P28).

## Commands for a rerun by hand

Every Gradle build below is over a minute, so outside a job it is a probe at most; the caches are filled, so all run
`--offline`. The slice route takes seconds and needs no network.

```bash
source ~/.cache/in-the-loop/spring-pr-links-p01-p30/scripts/env.sh
# one case's job steps (CASE in P01-P04, P06-P08, P10, P12-P15, P17, P20-P22, P24-P30; STEP fix | parent | transplant | clean | dryrun)
bash $P/scripts/case_job.sh CASE STEP
# any task in a worktree, with the Gradle and JDKs that worktree needs (log $P/logs/TAG.log)
$P/scripts/gradle_case.sh $W/P30-fix TAG "spring-context/build/test-results/test" \
  -Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline \
  :spring-context:test --tests org.springframework.scheduling.support.CronExpressionTests
# a classpath of any project and configuration, offline
$P/scripts/gradle_case.sh $W/P30-fix TAG "" --offline -I $P/scripts/resolve-all.init.gradle \
  :spring-context:setupWriteClasspath -PsetupCpConf=testRuntimeClasspath -PsetupCpOut=$TMPDIR/cp.txt
# a released set for the 5.x cases (':'-joined jar paths)
cat $P/releases/spring-jdbc-5.1.5.RELEASE/classpath.txt
# the slice route for a 5.x case (CASE in P05, P09, P11, P16, P18, P19, P23; about 5 s each, inline in the probe cap)
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300 $P/scripts/slice_case.sh CASE
# a 5.x pin's slice ahead of its base release, for a program of your own
$J8/bin/java -cp $P/slices/P16-fix/P16-fix-slice.jar:$(cat $P/releases/spring-jdbc-5.1.4.RELEASE/classpath.txt) ...
```

A worktree whose `clean` step ran has no `buildSrc/build`; the next offline run compiles `buildSrc` again (its dependencies are
cached). Every project's every configuration was resolved, so modules beyond the case's also build offline. `P29-later` was
resolved too but never built.

## What failed or was not done

- **The seven 5.x cases have no Gradle build** ([why](#the-5x-builds-cannot-be-configured)): their build scripts need
  `propdeps-plugin` 0.0.8 / 0.0.9.RELEASE, `docbook-reference-plugin` 0.3.1, dokka `integration` 0.9.15,
  `spring-asciidoctor-extensions` 0.1.3.RELEASE or `gradle-enterprise-conventions` 0.0.2, which are in no public repository.
  No substitute was put in. Their changed files are built and their landed tests run on the
  [slice route](#the-5x-cases-on-the-slice-route) against released jars instead; the rest of each module there is the release's.
- Refused by servers (401, anonymous): `repo.spring.io/release`, `plugins-release`, `libs-release`. Nothing the 6.x and 7.x
  builds needed was only there.
- Unchecked signatures: the Spring and Reactor release jars signed with `9A2C7A98E457C53D` and reactive-streams 1.0.3
  (`1364C5E2DF3E99C5`), keys not importable from keyserver.ubuntu.com or keys.openpgp.org; milestones and RCs publish no `.asc`.
  Their sha1s match the repositories'. Byte-buddy's key is revoked since. Liberica publishes a sha1 only. P11's wrapper jar matches
  no published checksum (unused).
- **P15's transplant hangs** after its one failure (`interruptWhileAwaitingData`), until the 3000 s timeout; which later test
  blocked is not recorded (a rerun with a JUnit per-test timeout would say; not queued).
- Not run: the `later` revision of P29 (fetched and resolved, never built); the brief's own scenarios and predictions; the whole
  module test suites (only the landed classes run).
- The first P25 job selected no test (abstract class with nested tests); its rerun passed. The first batch of 7.x dry-runs hit a
  time limit and was rerun from P07.

Disk after the jobs' `clean` steps: `$P` 25 GB (worktrees 5.3 GB, `gradle-home` 15 GB, Gradle distributions and the Liberica JDK
3.4 GB, kept artifacts 524 MB, release sets 196 MB and Maven repository 166 MB, slices 5.3 MB). The mirror
`~/.cache/in-the-loop/git-mirrors/spring-framework.git` is 392 MB (211 MB before). The Gradle zips were deleted after their digests
were recorded (the `.sha256` files stay).

## Setup Agent Notes

### What is ready, and where

- **Sources.** All 60 pins, plus the `later` revision P29 links (`daa8c10031e35f1a447917474f203789e009d3b5`), as worktrees
  `~/.cache/in-the-loop/spring-pr-links-p01-p30/worktrees/CASE-ROLE` (ROLE `parent` = before pin, `fix` = after pin), from the
  shared mirror `~/.cache/in-the-loop/git-mirrors/spring-framework.git`. Every PR's merge commit equals the after pin, every landed
  diff names exactly the PR's files, the 21 signed pins verify ([Upstream revisions](#upstream-revisions), full ids in its table).
  All worktrees are clean.
- **Offline builds for 23 cases** (all but the 5.x seven). Every configuration of every project is resolved into
  `$P/gradle-home`; `source $P/scripts/env.sh` then `$P/scripts/gradle_case.sh WORKTREE TAG "" --offline TASKS` picks the right
  Gradle (verified distributions in `$P/tools/`) and JDK ([Build facts](#build-facts-by-era), [Commands](#commands-for-a-rerun-by-hand)).
  `$P/scripts/case_job.sh CASE STEP` reruns a case's job steps.
- **Built jars, class digests and classpaths** for all 23 cases at both pins in `$P/artifacts/CASE-ROLE/` (`jars/`, `SHA256SUMS`,
  `M.runtimeClasspath.txt`, `M.testRuntimeClasspath.txt`, `:`-joined, project jars copied under `tree/`), digests in full in
  [Digests of the built artifacts](#digests-of-the-built-artifacts).
- **Slices for the seven 5.x cases** at both pins: `$P/slices/CASE-ROLE/CASE-ROLE-slice.jar` (the pin's changed production
  classes, JDK 8), to put ahead of the base release's `$P/releases/SET/classpath.txt`; `$P/scripts/slice_case.sh CASE` rebuilds
  them and reruns the landed tests in seconds ([slice route](#the-5x-cases-on-the-slice-route), class digests there).
- **Released artifacts for the 5.x cases and the versions the brief names** in `$P/releases/SET/` (`jars/`, `classpath.txt`):
  spring-web 5.0.0.RC4 and 5.0.0.RELEASE with protobuf-java-util 3.4.0, and protobuf-java-format 1.4 apart (P11); spring-test
  5.1.0.RC1 and RC2 (P09); spring-beans 5.1.6.RELEASE and 5.2.0.M1 (P05); spring-jdbc 5.1.4/5.1.5.RELEASE with H2, HSQLDB,
  Derby (P16) and 5.2.7.RELEASE/5.3.0-M1 (P18); spring-tx 5.2.0.RC2/5.2.0.RELEASE with their Reactor (P19); spring-orm
  5.1.4/5.1.5.RELEASE with hibernate-core 5.4.1.Final and HSQLDB (P23); spring-context 5.3.18 with AspectJ 1.9.7 (P26's reported
  version); jasync-r2dbc-mysql 2.1.19 and 2.1.20 (P20); and each 5.x pin's test libraries as `tests-CASE`
  ([Released artifacts](#released-artifacts), digests in `$P/logs/release-verify.txt`).

### What was verified on a JVM

- **All 30 cases' landed regressions pass at the fix and fail at the parent.**
  - 23 Gradle cases, by their jobs (results commit `933de3d18d34`): each landed test class passes at the fix pin, and its parent
    version (where one exists) passes at the parent. The fix's test files on a copy of the parent **fail** for P01, P02, P03, P06,
    P07, P08, P10, P12, P13, P14, P17, P20, P21, P22, P25, P26, P27, P28, P30. They **do not compile** for P04, P24 and P29, which
    use the API the landing adds. They **fail and then hang** for P15. Every failing test is named in [Job results](#job-results).
  - The seven 5.x cases, on the slice route: each landed test class passes on the fix slice, and the parent's own version passes
    on the parent slice (P18's and P23's classes are new). The fix's tests **fail** on the parent slice (P05 2, P09 2, P11 1, P16 1,
    P18 3, P19 1, P23 4 tests) and, identically, on the stock base release. Every failing test is named in
    [the section](#the-5x-cases-on-the-slice-route).
- No scenario or prediction of the brief was run anywhere.

### What to know before starting

- **P05, P09, P11, P16, P18, P19, P23 (Spring 5.x) have no historical build** ([why](#the-5x-builds-cannot-be-configured)). What
  exists is a slice per pin: that pin's changed classes ahead of the base release whose copy of those files equals the parent pin's
  (P05 spring-beans 5.1.6.RELEASE, P09 spring-test 5.1.0.RC1, P11 spring-web 5.0.0.RC4, P16 spring-jdbc 5.1.4.RELEASE, P18
  spring-jdbc 5.2.7.RELEASE, P19 spring-tx 5.2.0.RC2, P23 spring-orm 5.1.4.RELEASE). Every other class there is the release's, not
  the pin's. Released files also equal some fix pins (P09 fix = spring-test 5.1.0.RC2, P11 fix = spring-web 5.0.0.RELEASE).
  No release equals the fix pins of P05 (5.2.0.M1 differs in one `static` modifier and comments), P16 (5.1.5.RELEASE: comments
  and indentation only), P18 (5.3.0-M1 drops `@Deprecated` and rewords a debug log), P19's `TransactionalOperatorImpl`
  (5.2.0.RELEASE passes an extra `(res, err) -> Mono.empty()` to `usingWhen`) and P23 (5.1.5.RELEASE: copyright year and a blank
  line). In 5.2 there is no `spring-r2dbc`, which matters for P19's database claim.
- **P11's provider choice**: keep `$P/releases/protobuf-java-format-1.4` off the classpath for the Google JsonFormat path; the
  public constructor prefers it when present. The slice and the upstream test run have it on the classpath, because the converter
  class refers to it and the test chooses each provider through the package-visible constructor.
- **Snapshots.** The 7.1.0-SNAPSHOT builds take Reactor 3.9.0-SNAPSHOT, reactor-netty 1.4.0-SNAPSHOT and Micrometer 1.18.0-SNAPSHOT
  as cached on 2026-11-26 (same bytes as on 2026-11-25); P20 takes reactor-core 3.5.3-SNAPSHOT `20230214.110429` and Micrometer
  1.10.4-SNAPSHOT `20230213.230149`, ten days after its pins, the only builds still served. Digests in
  [Snapshot dependencies](#snapshot-dependencies). Build `--offline` to keep them.
- **P21, P22, P24, P25, P26, P28 need the Liberica JDK** (`$JL17`): their builds demand toolchain vendor BELLSOFT; `gradle_case.sh`
  passes it. Default `java` on `PATH` is 25.0.5. The 7.x builds compile on toolchain 25 with `release` 17; the 6.x builds on 17;
  the 5.x slices on JDK 8 (`$J8`).
- **P15 on the parent can block**: an interrupted read waits for an upstream signal. Give any run against the P15 parent a timeout.
- **Two-commit landings**: P13, P15, P26, P30 (intermediate commits `8f4fcb6cbc3b85ba0cdaae7fc2b1c552f7ef9715`,
  `66125a569e4d673bd3e23f2f2c9490ec625cf640`, `86d52a677a41caa70477725d764c3deb2736bcb0`, `cddc671a8c6eea118b1f7ef05f2b6d754e852f09`
  are in the mirror); the brief compares the outer pins. P11's after pin is a merge.
- **P25's landed test** `ProxyExceptionHandlingTests` is abstract; select its nested classes with `--tests 'org.springframework.aop.framework.ProxyExceptionHandlingTests*'`.
- **Databases are open**: the spring-jdbc test runtime classpaths have H2, HSQLDB and Derby (check
  `$P/artifacts/CASE-ROLE/M.testRuntimeClasspath.txt`), the P16 sets H2 1.4.197, HSQLDB 2.4.1 and Derby 10.14.2.0, the P23 sets
  HSQLDB 2.4.1; nothing else (no PostgreSQL or MySQL server, no R2DBC database for P19) was set up for this brief.
- Pins shared with the O01–O20 brief: P27's parent `906c54faffc75721b98f9b9cf63d35edd81f7b4f` is O05's fix, P30's fix
  `6467fca05b874f3e44fbd9451a252f035abbeafc` is O10's parent; P02's parent's parent is P06's fix. Their worktrees here are separate.

### What is left for the domain work on purpose

All claims, scenarios, fixtures and examples; whether a 5.x case's slice, a release, or neither stands in for its pins in a
claim; choosing databases, drivers and providers beyond what is fetched (P16, P17, P19, P20, P23); any run of the brief's own
scenarios or predictions; the P29 `later` revision; and example ids and folders.
