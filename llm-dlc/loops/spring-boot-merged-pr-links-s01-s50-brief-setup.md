# Setup for the Spring Boot merged PR links S01–S50 brief

Mechanical setup for [`spring-boot-merged-pr-links-s01-s50-brief.md`](spring-boot-merged-pr-links-s01-s50-brief.md), done on
2026-11-27 by a setup session (Claude Opus 5.5) before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

`$P` below is `~/.cache/in-the-loop/spring-boot-pr-links-s01-s50`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $P/scripts/env.sh` defines `$P`, `$M`, `$W` (= `$P/worktrees`), `TMPDIR` (= `$P/tmp`), `GRADLE_USER_HOME` (= `$P/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`)
and `$JG25` (GraalVM CE 25.5.5, with `native-image`), see [Toolchain](#toolchain).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `S01`–`S50` follow the brief's order (the same as the PR list
[`spring-boot-merged-pr-links-s01-s50.md`](spring-boot-merged-pr-links-s01-s50.md)). They are this record's labels only, not
example ids. The scripts are adapted from the Spring Framework Q01–Q30 setup's (`~/.cache/in-the-loop/spring-pr-links-q01-q30/scripts/`).

| Case | PR | Case | PR | Case | PR | Case | PR | Case | PR |
|---|---|---|---|---|---|---|---|---|---|
| S01 | #52125 | S02 | #51661 | S03 | #50773 | S04 | #50798 | S05 | #52207 |
| S06 | #52277 | S07 | #52666 | S08 | #52904 | S09 | #51855 | S10 | #50489 |
| S11 | #51867 | S12 | #52310 | S13 | #52309 | S14 | #52831 | S15 | #50886 |
| S16 | #9558 | S17 | #52251 | S18 | #52304 | S19 | #51173 | S20 | #52162 |
| S21 | #51410 | S22 | #50271 | S23 | #52824 | S24 | #51725 | S25 | #52190 |
| S26 | #51844 | S27 | #52832 | S28 | #52625 | S29 | #51940 | S30 | #51774 |
| S31 | #50296 | S32 | #52321 | S33 | #51470 | S34 | #51937 | S35 | #50734 |
| S36 | #50461 | S37 | #51959 | S38 | #51156 | S39 | #52477 | S40 | #52522 |
| S41 | #52593 | S42 | #52285 | S43 | #52280 | S44 | #52244 | S45 | #52402 |
| S46 | #51653 | S47 | #52530 | S48 | #51551 | S49 | #51372 | S50 | #50433 |

## Starting commit

Checkout at setup: `565921d754beb53bd54eb6bb1ebbb89ebc836bea` (`develop@origin`, "Queue the brief
spring-boot-merged-pr-links-s01-s50-brief").

## Upstream revisions

All 50 pull requests are in `spring-projects/spring-boot`. A new bare mirror `$M/spring-boot.git` (44 MB) holds only the pinned
commits, fetched by SHA at depth 1 from GitHub and kept under `refs/pins/s01-s50/CASE-ROLE-SHA` (`$P/scripts/pins.tsv`). Roles:
`parent` = the brief's *before* pin, `fix` = its *after* pin. The 100 pins are 97 distinct commits: three are shared, S12's fix =
S32's parent (`53328b76db4ffb107ee38ad82bf090ac1be59a9c`), S14's fix = S27's parent (`3a7a19b7c5b16d4cc6dd8f0c22ea88d206e90a9a`),
S28's fix = S41's parent (`a938beab5f1d370f63d62ce78f3ab029f868bd03`). S16's two intermediate commits are kept too
(`refs/pins/s01-s50/S16-mid-SHA`). Every 40-hex id in the brief is one of these 97, or one of the two commits of other
repositories under [Other repositories](#other-repositories). One detached worktree per case and role: `$W/CASE-ROLE` (100
worktrees, 9.6 GB checked out).

Checked mechanically (`$P/logs/prs.txt`, PR records `$P/upstream/prs/PR.json`, changed files `$P/upstream/prs/PR-files.tsv`, PR
commits `$P/upstream/prs/PR-commits.tsv`, commit records `$P/logs/commits-api.tsv`, parent structure `$P/logs/parent-structure.tsv`):

- **Every PR is merged and its `merge_commit_sha` equals the brief's after pin** (50 of 50).
- **49 after pins are two-parent merges whose first parent is the before pin and whose second parent is the PR's head**
  (`head.sha` of the PR record), as the brief's objective says. **S16** (#9558, 2017) landed by rebase as three commits, the PR's
  own three: `89af4a65cf1fa99df62a9fbcbe3c10ab9ab7c738 → 4ce726b1a04e318ff5d86c714a32970185ab3ffb (Auto-configure WebClient.Builder)
  → 64777204d8187ee101cbee21d5d0ce4ffd338774 (Apply codecs auto-configuration to WebFlux) → f2e77e46cd12a9eb5a7d701cb4612bdd41c613b0
  (Auto-configure codecs in WebTestClient)` (`$P/logs/S16-compare.txt`, GitHub compare: ahead 3, behind 0).
- **The diff before→after names exactly the PR's changed files** for all 50 (`$P/logs/CASE-landed-files.txt`, diffstats
  `$P/logs/CASE-landed-diffstat.txt`, comparison `$P/logs/landed-vs-pr-files.tsv`). S27 changes 33 files, S49 22, S36 18.
- **Trees**: each commit's tree id from GitHub equals the mirror's (99 of 99, the two S16 intermediates included).
- **Signatures** (`$P/logs/commits-local.tsv`): 98 of the 99 commits are unsigned. S49's fix `535d133bdaa0ed46bbfb7ce578c14261806f39ac`
  (Moritz Halbritter, "Merge pull request #51372") carries an SSH signature, which verifies (`Good "git" signature ... ED25519 key
  SHA256:fkadyCND612Zf0knDkZ/CX1/PIyMWDw/ASqDRfn/drk`) against his GitHub signing key (`gh api users/mhalbritter/ssh_signing_keys`,
  saved in `$P/keys/mhalbritter-ssh-signing-keys.tsv`, `$P/keys/allowed_signers`; the principal name there is this setup's label
  only); GitHub reports it `verified: true`.

PR base branches: `4.0.x` for 28, `main` for 18, `4.1.x` for S06, S21, S38 (and `master` for S16). Merged between 2017-07-03 (S16)
and 2026-11-26 (S08, S23).

| Case | PR | Role | Commit | Tree | Parents | Committed | Signature | Gradle | Version | Subject |
|---|---|---|---|---|---|---|---|---|---|---|
| S01 | #52125 | parent | `e664baa4001e2a12cfd292771f63d747d86b831f` | `f61bc3e81d807eae8094d128272fb6150717d3e6` | `3271125d0854046797a2855d287f55b543c9136d` | 2026-10-13 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Simplify source code headers |
| S01 | #52125 | fix | `d3c0359e0196e9d604a65e6ff677d114cc270a0f` | `88fc20e9536daee216c438b8ff4b5b952cd166e9` | `e664baa4001e2a12cfd292771f63d747d86b831f` `cfd4ce9b295e6e924d1561c7e68df054cb3e1c19` | 2026-10-14 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Merge pull request #52125 from ryujungkyun |
| S02 | #51661 | parent | `042c69a4f9c7e7bfb7be14dff6a5dd5af5ff3e72` | `367eee0d6fe7a813739a3027922351fa3e10e140` | `1dab448cc973b36e53ea967a735e60cf40ba71a6` `885720ae66a62f68af796f1ece219a1fc10b245b` | 2026-09-11 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S02 | #51661 | fix | `26b0e813b0b82e5683524d1ad817ca9b66228b4d` | `10b65893885e62151e144b4d018e859156e91bd9` | `042c69a4f9c7e7bfb7be14dff6a5dd5af5ff3e72` `b5dd5215f3e667d99dc6fbae10911ec2d015b81a` | 2026-09-11 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51661 from Wanbinyu |
| S03 | #50773 | parent | `f71e7977614682ced49221321a38bb5cb18bc938` | `56c381cb0b2f7930c62b6bc86ce1542353bbbbe5` | `2edca39504f8e9c2943262d3e60ba34b0e7751ac` `4b542efc0c3c6a5b753a7ec198b7162d2879b99e` | 2026-06-18 | unsigned | 9.5.0 | 4.1.1-SNAPSHOT | Merge branch '4.0.x' |
| S03 | #50773 | fix | `fe554ff822bf48ee9b04fbc511f54332aa2ca10b` | `62c60d082d4fa71e74004836cd1d8a27e24a3fef` | `f71e7977614682ced49221321a38bb5cb18bc938` `12eb46696aa65e0e8dc11ed305bd4685110c127b` | 2026-06-20 | unsigned | 9.5.0 | 4.1.1-SNAPSHOT | Merge pull request #50773 from xfocus3 |
| S04 | #50798 | parent | `3d280c4354a127e9f08bb1ea782b02165bbbfa7e` | `6616b74f2d27a3fd20cbf84f43e8b527a0ebd15f` | `58cb433cd0bf507948641d791f6fa9e8c9e25cea` `92bd807edd9130437c17d20c3983d016b35b618f` | 2026-06-24 | unsigned | 9.5.0 | 4.0.8-SNAPSHOT | Merge pull request #50418 from codingkiddo |
| S04 | #50798 | fix | `0836e3673a74e47a2e5eed3a8e8ad45cfa4a0ccf` | `1c92277e6417ca34cd24c48accfbff2ac37b4df8` | `3d280c4354a127e9f08bb1ea782b02165bbbfa7e` `249dab6d6fb655186966dfa0136dbcf0d8256e3d` | 2026-06-24 | unsigned | 9.5.0 | 4.0.8-SNAPSHOT | Merge pull request #50798 from xfocus3 |
| S05 | #52207 | parent | `6c0b7df312e0fb1eaeecab9967e676726ce29057` | `0551bd2bf0866abaeb4ac14fcd8fbb219c824ccd` | `bba5f11efc7f28ced96961d9e16dbc8862b06010` `e28f3b61027da41bbf3ddd9c45f1aa8cd9d63cba` | 2026-10-16 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Merge pull request #52249 from padosol |
| S05 | #52207 | fix | `42b182259cc6d4f9ed67bb2f387fed7e6b2c4979` | `ffa8f4ba897a9ca7451306e474cffa6d446fce60` | `6c0b7df312e0fb1eaeecab9967e676726ce29057` `3d2b416c171f2934f0fec119cade89576f6697a1` | 2026-10-16 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Merge pull request #52207 from zhoubiao188 |
| S06 | #52277 | parent | `5b40ad76e7cc2c05d8e9a816fdaf080a354667f9` | `a774eb57eea0a114614b0098bc7d6c69828472e6` | `609db2d4542a1238337ee0dc418f8e96267eb488` `8b9ab585d311d33cad27c3ae1b615b0609aea28e` | 2026-10-22 | unsigned | 9.8.1 | 4.1.3-SNAPSHOT | Merge branch '4.0.x' into 4.1.x |
| S06 | #52277 | fix | `c89f27ace1483333681b074c4f3d4924ba77f1ea` | `04b397314f12bac2fe24fdbb652dd5d15717cffa` | `5b40ad76e7cc2c05d8e9a816fdaf080a354667f9` `2a29a6af65ae59c29f0e88205bb15b3427dd82fd` | 2026-10-22 | unsigned | 9.8.1 | 4.1.3-SNAPSHOT | Merge pull request #52277 from challa |
| S07 | #52666 | parent | `5b88a2ad273ea810ae0aa56cf8819bac33521e95` | `cb6f0d603ea2c1490fcc66898c37b88d7ef8dbe2` | `92f6d6457f370388ad01ad7e7a6e803b6ae476b7` | 2026-11-11 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Test Gradle plugin against 8.14.7 |
| S07 | #52666 | fix | `aff28f4f77acc49c3f7d1bf4725d841a21ddf6e1` | `c28e51904c8a7e7f0621e01a15e5a8e3a100c451` | `5b88a2ad273ea810ae0aa56cf8819bac33521e95` `bbd8de8bec2ea4a8223bc227c6c45caca2c7288b` | 2026-11-12 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Merge pull request #52666 from eatmoreduck |
| S08 | #52904 | parent | `906029c2a9b33ef5052141a91eac5de8177ede9d` | `be56c793610132003a2a598f2129c2ca8540f941` | `79d3cc26509620e47d9f3db445795b4984b6f567` `1d70f25af666e57a1e6cac68c793e44a2efd33a7` | 2026-11-26 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52898 from sehyuk080101 |
| S08 | #52904 | fix | `cc44b73aca16f06ebac4f1d8692751a80b2b6615` | `235d7f10e08154c864437dec1682dcdefdccdba0` | `906029c2a9b33ef5052141a91eac5de8177ede9d` `d166563c84585b676487c93864ba5cc53ca01bbc` | 2026-11-26 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52904 from sonic8-8 |
| S09 | #51855 | parent | `789e06631baace79ffe874d54de269342f6b76c5` | `9234728d50a14fc6cf86e080e7ef355b0114c0c3` | `46ed0333338d72b75b20a29ce761743ba1504cfc` `caec174deef0d5e4a08464bfc01c5674dc60ff09` | 2026-09-25 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S09 | #51855 | fix | `ef67de058ed35c0f6246d47abdb09fbdd4ce5c1a` | `f0f02dadd80ebadb56105b578bba5b34c4ceb024` | `789e06631baace79ffe874d54de269342f6b76c5` `602a7e73e9d4f416d1b8dc58aeedad9329ddffbf` | 2026-09-25 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51855 from noojung |
| S10 | #50489 | parent | `01afdc8dc738d1c016bcbc572b2376d270dc3335` | `0b48c14eab11f2c292aeda80ac405ef2db05a3e1` | `56facf449c098604d0530763632fde03fb90fc4d` `b46fe745c0184f6b08cf4993582af6640fd882aa` | 2026-10-01 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51893 from scottfrederick |
| S10 | #50489 | fix | `47d4b222827148e780ea7e5118b88676659a753d` | `09b215a5f36075bd0e4b3bd7995602f7778d1908` | `01afdc8dc738d1c016bcbc572b2376d270dc3335` `8c457932e7343b135c7e7cf8005a2e8e05e73bd7` | 2026-10-01 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #50489 from galenzo17 |
| S11 | #51867 | parent | `ab8d5266fbf617b1462d60f5bba5ade2d0f6302d` | `3f2233f94d9e503062d70d2a63f3e78c25425bd0` | `a39d2a070042a38df2cbf562d14757b49b9c8861` `a5bc29468519ce56088ab11ab293d45bff32d447` | 2026-09-28 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S11 | #51867 | fix | `b00a873c002d3e5f6edf4cc58313030855ec86cd` | `01f0c7c21cc81de64fa008492f1013737a782954` | `ab8d5266fbf617b1462d60f5bba5ade2d0f6302d` `875efab7d52afea392a2680ab9f2bb785697c05f` | 2026-09-28 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51867 from aalsanie |
| S12 | #52310 | parent | `25adba2b4e3e69a49e2128fd5c0185ee1ea437a9` | `fb986f1f89bbcdd22f6c35d30917c6ce5542e726` | `64159c8bf691f6b15851d4076ef1eee6f109c3bc` `a77eb6d9ca1330c6aa7a88def2828edf0034ca5b` | 2026-10-26 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52308 from challa |
| S12 | #52310 | fix | `53328b76db4ffb107ee38ad82bf090ac1be59a9c` | `010ded640b38053b1013885d20264a2364abfeb9` | `25adba2b4e3e69a49e2128fd5c0185ee1ea437a9` `37d2750981f8cc48a95be402e8f75bb32ae52d35` | 2026-10-26 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52310 from challa |
| S13 | #52309 | parent | `aaca41eb4262b0570d610d97e30857fb3cb17089` | `4f30f96f862843641666e04f4a80d158e2c0be2f` | `6e3602f4a3d208d15e48e250d28653c85d324d76` `34e9a89fa99d95ef095115557a82cabe3d3f4076` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52282 from zhoubiao188 |
| S13 | #52309 | fix | `76246db920dbafc1e45441ef736f14d4548dc8d0` | `335141e3f582378c870d375e977a0c0a99aaa1d5` | `aaca41eb4262b0570d610d97e30857fb3cb17089` `63ccbab797e428956342dd0e4c69a5e768fa3ef8` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52309 from challa |
| S14 | #52831 | parent | `68f823ceabc77d1786ec0ff416bb128dc13ce93b` | `d3dbb7f30b5bd8d8276ba27b28755d55df31270d` | `095685d86c7e268ba3d2175df1001b8f406b25e4` `1c5467e3259086221cb6bf7cc73914831e463d1a` | 2026-11-20 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52828 from KamilPatora |
| S14 | #52831 | fix | `3a7a19b7c5b16d4cc6dd8f0c22ea88d206e90a9a` | `7b7057f203adba84b8c044881ec17dec4938ab7b` | `68f823ceabc77d1786ec0ff416bb128dc13ce93b` `304f9d7cec474ed35e411f9b9b82d071afd27338` | 2026-11-20 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52831 from DOKL57 |
| S15 | #50886 | parent | `39c87d595e24091a4966be36404c87d0dffab9a7` | `a70de6330dcf87240064eb8038fc1fc27584df60` | `2d896e25efca8a822cdc56447aac99bc11692894` `e5106ef9e9658dc631e1866a351a781b74f32210` | 2026-07-27 | unsigned | 9.6.1 | 4.0.8-SNAPSHOT | Merge pull request #51117 from wantaekchoi |
| S15 | #50886 | fix | `e1a1e1be824c1720aad9817388394fe55e89e189` | `b53f9aed9c74fc4a03fd71a23c4491c03cce3622` | `39c87d595e24091a4966be36404c87d0dffab9a7` `19153b69a4332bfd7ee1d2ef370b317b53a1d467` | 2026-07-28 | unsigned | 9.6.1 | 4.0.8-SNAPSHOT | Merge pull request #50886 from LordKay-sudo |
| S16 | #9558 | parent | `89af4a65cf1fa99df62a9fbcbe3c10ab9ab7c738` | `d7f3126aacdd822f7a8d03fe1c3b47e565994b37` | `535005da7bfbd6d48d3256b21c14ededb27e4a66` | 2017-07-02 | unsigned | Maven 3.5.0 wrapper | pom:2.0.0.BUILD-SNAPSHOT | Upgrade to Sqlite Jdbc 3.19.3 |
| S16 | #9558 | fix | `f2e77e46cd12a9eb5a7d701cb4612bdd41c613b0` | `b09d64ae79e5dd5ce1444a434eab7aad1b93240b` | `64777204d8187ee101cbee21d5d0ce4ffd338774` | 2017-07-03 | unsigned | Maven 3.5.0 wrapper | pom:2.0.0.BUILD-SNAPSHOT | Auto-configure codecs in WebTestClient |
| S17 | #52251 | parent | `54aa8e789e001ea43307d9ceb09eeb6f2031f2c4` | `69e523cb5380a8f1d5db37c2899af85d01aa0c96` | `07fc2a630ee9da4fa518f15d62b03d87a37588bc` `0766f51aad1c45dd774619eca0a391cecf6239fe` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52206 from zhoubiao188 |
| S17 | #52251 | fix | `2998c84ca55100f867b090706fe0426052e1491e` | `8a400725264498a651e8c79c5c6bd703eff6fe5c` | `54aa8e789e001ea43307d9ceb09eeb6f2031f2c4` `3038b80f6fe09dfea8ce57b0f01760473fce6683` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52251 from padosol |
| S18 | #52304 | parent | `a9bfca2346c74c2bb46e70aa4f61b162d36dee33` | `dcdd3818aee4f1514a734ed7254bcfef47a9400d` | `a11618b39a56b2142a0b30235b4c88c84bde6c07` `85b5dca9196b688222b24f1c15af427c1d480b21` | 2026-10-23 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52297 from manuel-umu |
| S18 | #52304 | fix | `f2ffba784085ae4c1f8fcd6ac7f9c850e722cecc` | `073fd44d86da85a36ca3f77b27163292269f7810` | `a9bfca2346c74c2bb46e70aa4f61b162d36dee33` `e4fbc7acd02010fc6794dd8295ee3e50fcbf0f68` | 2026-10-23 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52304 from dlwldnjs1009 |
| S19 | #51173 | parent | `a07c43466b7231a6bd8c84b638ce89fe6b78fcff` | `c12b29cd49af882dd54cdc76f02299910241cce4` | `57b44b05949404015d5935899cfd827665fdb093` `61275b0c643cd1017b9452af8a2a31d2c119b3ae` | 2026-09-07 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S19 | #51173 | fix | `d265e67685580d0b417b5bb192af1069eb12c5cf` | `cc42566f907a78ab48147e189446fbae00db5121` | `a07c43466b7231a6bd8c84b638ce89fe6b78fcff` `8924f1691c53e3e5aaf7e33b014ca81de7f3c616` | 2026-09-07 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51173 from basteez |
| S20 | #52162 | parent | `2ed46d765577c63e733fc8cc8a7de2c6f2102333` | `d83839ad762a7551ddd37157aaed2716acdb9324` | `5861f97b7a0d96f29b25092cd08b271df12fec4a` `aa2ae258a1a0d8f4a66b0583cd5197b2de16d97f` | 2026-10-29 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52437 from zhoubiao188 |
| S20 | #52162 | fix | `70b92fc5085090348ccf822d90178208d93be9d6` | `7c18ccc330b33efc3142fbc6c552b5b78afc8a69` | `2ed46d765577c63e733fc8cc8a7de2c6f2102333` `56789a69978057e145ec6700a011e32a7fcee236` | 2026-10-29 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52162 from challa |
| S21 | #51410 | parent | `4ee67a3f6b817bc8727069e083f0506bb8aefa33` | `dbbf843210e56493672167df7177806abaf2ac46` | `515810853fab732adc8d9c842187c5b21a1a72ad` `43d3cf57eb0273a46fed3ba731bc35a02be8bf93` | 2026-08-24 | unsigned | 9.7.0 | 4.1.2-SNAPSHOT | Merge branch '4.0.x' into 4.1.x |
| S21 | #51410 | fix | `cbaaa0fe45652d32ac5cc532cbfb5737e086769f` | `ec72f42bc0e62c3b7215ef55d8fbc46d61910194` | `4ee67a3f6b817bc8727069e083f0506bb8aefa33` `d5cec292dc1a3ad51f8b321253f9d8956ecf06eb` | 2026-08-24 | unsigned | 9.7.0 | 4.1.2-SNAPSHOT | Merge pull request #51410 from jjh75607 |
| S22 | #50271 | parent | `96a36cfc8c8d6f76df41c6ca17a38fa46c3d9689` | `4a3c1a3684377b784caca2dedc9e90b00dad6329` | `d7e49dc378630acf7358e9dbc3adef0327ea4e89` `2c1801257781a416772d204436859e283fcef7f3` | 2026-05-04 | unsigned | 9.5.0 | 4.1.0-SNAPSHOT | Merge branch '4.0.x' |
| S22 | #50271 | fix | `607e4bbe65e00bc401b3c33e9c1a615a9f1888aa` | `8912b65fcae87742892a9a4afda97f703c852ce6` | `96a36cfc8c8d6f76df41c6ca17a38fa46c3d9689` `627ac0451d9ad685d0e172959e330e4031e4a749` | 2026-05-04 | unsigned | 9.5.0 | 4.1.0-SNAPSHOT | Merge pull request #50271 from vpavic |
| S23 | #52824 | parent | `60bed32467b7391003fcf81c414d66c5835e66b0` | `483beefbb915b7855e2e31b33317b04d50988261` | `6d3dbdf48dbfadbb25188bfa1f113fd5e9b73ffb` | 2026-11-26 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Fix copy-paste error in RabbitUriTests |
| S23 | #52824 | fix | `79d3cc26509620e47d9f3db445795b4984b6f567` | `83d72ee0b730b5f7e9dff40ced87cfdfb6e73d87` | `60bed32467b7391003fcf81c414d66c5835e66b0` `b5d8a3a43c1fb991d39458299a4b9b5409268c09` | 2026-11-26 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52824 from Kazumi565 |
| S24 | #51725 | parent | `683d41b3232b98bb10d7b60705abe300af1c5e20` | `216ed1d98f9da46078e24733a54249ff39a6c786` | `3c1f0c4e543b3c20db34e224a0670e59f82dc767` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Start building against Spring HATEOAS 3.2.0-M2 snapshots |
| S24 | #51725 | fix | `32b09e479b78afd151577df37e800f47711db749` | `1b5fec6bdaa8d2d8b3595a629d50ccd9e79268bd` | `683d41b3232b98bb10d7b60705abe300af1c5e20` `d479a6a42f3e4a21f756cba27437ff9262d629c6` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51725 from quaff |
| S25 | #52190 | parent | `425bad9c72f10bdd03964c5ed0c0290a4678a663` | `d2f1475acb02d2d466df24907e31661fbf32c31e` | `ff4b7a2f6004207d08693c8115dacb47a9e1f758` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Use assertJ's asInstanceOf consistently |
| S25 | #52190 | fix | `ac1b357395ee443a87c6d20a4faf815f40550b88` | `7c82247a630b3726a45fe5fd60c3a9a6d56b6cf5` | `425bad9c72f10bdd03964c5ed0c0290a4678a663` `a0a090eea61e8eb9007878c4093f6c0c3b9f2ff3` | 2026-10-21 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52190 from CCCLL |
| S26 | #51844 | parent | `0eed305ce08b030f45a9dbcd5b1969926b36b7d8` | `7afa3d983d3f9172edd35fd23da1e08958b946fd` | `f4fb05920474541c58b66d92dc57c6b067d4ba96` `a2a08124f177553c649ef63b2d7edf36e2383d4e` | 2026-09-28 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S26 | #51844 | fix | `ed4d85df8032b6574c0912d80ffb8e7663aaa79e` | `5a93bebbc7a1a2d6baf3d63d01386b1c6e4c4f18` | `0eed305ce08b030f45a9dbcd5b1969926b36b7d8` `0fe97e3da2fdecb9e644bb1fbdfa1157dc030a4c` | 2026-09-28 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51844 from hunseonglee |
| S27 | #52832 | parent | `3a7a19b7c5b16d4cc6dd8f0c22ea88d206e90a9a` | `7b7057f203adba84b8c044881ec17dec4938ab7b` | `68f823ceabc77d1786ec0ff416bb128dc13ce93b` `304f9d7cec474ed35e411f9b9b82d071afd27338` | 2026-11-20 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52831 from DOKL57 |
| S27 | #52832 | fix | `05356df632d8bec937e55cc486377871a201f084` | `969d6f3520a3658f24134f5115bada8688b03e9c` | `3a7a19b7c5b16d4cc6dd8f0c22ea88d206e90a9a` `6ec1abce87e31b20577886990cee5df1c1359346` | 2026-11-20 | unsigned | 9.9.2 | 4.0.11-SNAPSHOT | Merge pull request #52832 from DOKL57 |
| S28 | #52625 | parent | `cb47b14cfdabdfae7f4372aa7b21661f57444bca` | `4a54efb5469a46fef5045ff48d8a8d669eab43a8` | `18ad89a650ed23b7dfd9b16809e45bd1361cb303` `9fe6beadd2b7e7fadfc4f4bebfbdf80272806ed9` | 2026-11-12 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Merge pull request #52644 from zhoubiao188 |
| S28 | #52625 | fix | `a938beab5f1d370f63d62ce78f3ab029f868bd03` | `a50cf897dfe0e6109f3aef621af7cb6946a5af7c` | `cb47b14cfdabdfae7f4372aa7b21661f57444bca` `da224e33a781f85032d88851fd6623b53f4185a4` | 2026-11-12 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Merge pull request #52625 from raunakpandey1 |
| S29 | #51940 | parent | `305b97344b2b7abb9173b0e63a8d2c01a96c9e06` | `db025cf3ddc221a62699b001de2fea283cde46b3` | `96d971a6e51bf56898755ddf48821689a867a508` `7cc4d880e7df8d8f27fb7692124227192c4b871c` | 2026-10-12 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #51938 from lavinhoque33 |
| S29 | #51940 | fix | `f2cc019fe5bd51ce405995f3c89c48e2003cd9e7` | `bb85c040c7f8d551beddcda6d8ece8db16f6d7e6` | `305b97344b2b7abb9173b0e63a8d2c01a96c9e06` `ac2abe29d03ce13de717621a902430806e0ef344` | 2026-10-12 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #51940 from lavinhoque33 |
| S30 | #51774 | parent | `d28fc5b5ffe3bb26d83960bb4b0fbd03a0b894f0` | `51614e72b6ab0f9ada972b2c131fef4639fa3564` | `f61d27d59cdcdeb37f04b613100e8e913d7243c7` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Upgrade to OpenTelemetry 1.65.0 |
| S30 | #51774 | fix | `3c1f0c4e543b3c20db34e224a0670e59f82dc767` | `288db1e03e1503e6c1b83d8048517a37565103ae` | `d28fc5b5ffe3bb26d83960bb4b0fbd03a0b894f0` `3c6f7a54d30e82c9a06b635bb79d9a4624fa6633` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51774 from nikita-kibitkin |
| S31 | #50296 | parent | `4b51d350ee77b98e038c14e8ba831c5c47e5bb80` | `b4c09e9543ca1ebedcebb025365928e0739d23df` | `b2ed9b6938a5bb64a9ff2d48b7f11d210e755604` `e402beb42db6ed1f6b2bb9dcfd876c7dc27db57d` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S31 | #50296 | fix | `c398259cb871da425bdbdf792a276c058a253213` | `cc90f3a554de56b61a1a6f8759508ae3f97aaf17` | `4b51d350ee77b98e038c14e8ba831c5c47e5bb80` `5a27fd928effd2c204c06364e8dc259a7b0b7f0d` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #50296 from htjworld |
| S32 | #52321 | parent | `53328b76db4ffb107ee38ad82bf090ac1be59a9c` | `010ded640b38053b1013885d20264a2364abfeb9` | `25adba2b4e3e69a49e2128fd5c0185ee1ea437a9` `37d2750981f8cc48a95be402e8f75bb32ae52d35` | 2026-10-26 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52310 from challa |
| S32 | #52321 | fix | `b50d0244ea95127b783868b24f8ad9d5b9ce5a4b` | `b80fae321e7314bc7df0b2f7fb25c41cc4889832` | `53328b76db4ffb107ee38ad82bf090ac1be59a9c` `ce54e1cc5d7343659d95b2d16916aeebfd995351` | 2026-10-26 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52321 from zhoubiao188 |
| S33 | #51470 | parent | `1f3209130d661a96626f3b545ae219762a8201f0` | `a3586b445204ff3568d8a08a204ecab28ab26efc` | `c96f146f2c16410e1e817429c63a8732b1c4a351` `6fe126afed1437dbf8e9840979cf94d3bd897dd8` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S33 | #51470 | fix | `333d336ca95b6fcf9b404152bad2323d762b467b` | `bc83629946e4e553a4ea49017b31c49dadc8549d` | `1f3209130d661a96626f3b545ae219762a8201f0` `3aa96f222957603ed7c3d86c0a03175a3ca97095` | 2026-09-16 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51470 from Wanbinyu |
| S34 | #51937 | parent | `fcc6d421578939b5a960deaa77f7ea1eef45cabe` | `d75f6f3d49212aa1a2528401f7b5636735eb8501` | `bf1987a23ea0aad5b5c5a44056f8aeb24f857759` | 2026-10-06 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Update Spring Data Bom's calendar name to align with repo changes |
| S34 | #51937 | fix | `3d7e61639c18d6858013257fd338c12ff8dd79f8` | `fedfaea0312a19e7ae02dffc71a514d5e933e899` | `fcc6d421578939b5a960deaa77f7ea1eef45cabe` `372bd7cb0965b878b8c70df9e6caf4e9e8bdf840` | 2026-10-06 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51937 from khopland |
| S35 | #50734 | parent | `790f66c37a6fe69ea6e40c0c09212fab007d345f` | `3261bfb56d7d02af6b7a00596ed8835e2163e7b4` | `65097a4652ec9e889e7429be8bbc1f865f6d7b82` `9d5c98b7e9540ca8941112d4098c2c97a3b31d39` | 2026-06-24 | unsigned | 9.5.0 | 4.0.8-SNAPSHOT | Merge pull request #50750 from quaff |
| S35 | #50734 | fix | `33bf9d3777eac3f6bc13909571b612d0d2702233` | `15154546b0ae1fa9b720592f3485fa5c9e37808b` | `790f66c37a6fe69ea6e40c0c09212fab007d345f` `019ea06a6aefc581d9a9a66c4fdb26ed358b6901` | 2026-06-24 | unsigned | 9.5.0 | 4.0.8-SNAPSHOT | Merge pull request #50734 from seonwooj0810 |
| S36 | #50461 | parent | `2051b60a1ad79b941fb97b0f886e0e59b0356bf1` | `d322b43bd5ec68b7e73b89809eabc655a26c0757` | `8588f4b2ea98d9cd69426157a05336aefddfe006` `cbaaa0fe45652d32ac5cc532cbfb5737e086769f` | 2026-08-24 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S36 | #50461 | fix | `d6940b260bba2c22133f2856c224e80fcf0b4d60` | `04cb014314208af198c683f5dcdeea2a20c07de7` | `2051b60a1ad79b941fb97b0f886e0e59b0356bf1` `6af1fb5c2684f9c88c846e27515f79ae39b7e2cd` | 2026-08-24 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #50461 from somiljain2006 |
| S37 | #51959 | parent | `6a8b2d04940b9be002d9ab0314eb8c7024aeecfb` | `f9dcb48604bdc78410e97063bd4e4ee6857dec30` | `f415e2dc65bce9ce1930a7b3b3626cbe6809ee0d` `eb0887085e487198896ccd1e5ecf282e51b95006` | 2026-10-07 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51939 from lavinhoque33 |
| S37 | #51959 | fix | `8a76a2dfef003fe0d02a9b7f451907a84cb8baba` | `3b603cb926cd3565ee543f42f1c4944e9f8a9f17` | `6a8b2d04940b9be002d9ab0314eb8c7024aeecfb` `5d720a2138c260348196a0184faadf929b726002` | 2026-10-07 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51959 from rvullriede |
| S38 | #51156 | parent | `175702174462775baa8a66f8b0e21542ed6807a8` | `054f8dd789d17a5a73e82dbdc7363942cfb2069e` | `f1d395fc58216d40472698480996eca27487e384` `ada7ac7c4847aaa02ffb30c9559ca70a7568865b` | 2026-08-11 | unsigned | 9.7.0 | 4.1.1-SNAPSHOT | Merge branch '4.0.x' into 4.1.x |
| S38 | #51156 | fix | `af69828ce6cbdc159c8847067ec9c85f22bcdb30` | `86383311e3b2d75fe099111c1d480a1e5447011c` | `175702174462775baa8a66f8b0e21542ed6807a8` `dafadea2ab85b50b4299046049cb56f1641610fc` | 2026-08-11 | unsigned | 9.7.0 | 4.1.1-SNAPSHOT | Merge pull request #51156 from skdas20 |
| S39 | #52477 | parent | `7814f5327a8ee30be2012969b579c64eb18d6355` | `c2dea8257c6d651bf25c8b41488541f64188d543` | `5b1c53df9816de2afbab721bcdbb6f7f092d5c0b` `e7ac48744ccbf2421c1391d9c9f2020f7cd495b3` | 2026-10-29 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52255 from zhoubiao188 |
| S39 | #52477 | fix | `873231a509e28f42b6b1f45ad6a43fe17bcf8692` | `34e549419bc77d5d57aff8689fb0436f5f98ca03` | `7814f5327a8ee30be2012969b579c64eb18d6355` `0bce5d0d9b48f5fa61f32c2520b172f9eefd63e6` | 2026-10-29 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52477 from b84330808 |
| S40 | #52522 | parent | `0b8c2a7ef227e008fdc3dc397f8987bf4c90f5f7` | `69b170c55a60705d97663b3bf8abbf6da4b68251` | `ada21161199a13bab8044c4898915f6f08af1ddc` `16b7159ca7ff39736c104638aa2f79a799ccb8ec` | 2026-11-02 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52507 from CCCLL |
| S40 | #52522 | fix | `430fa2b6891a6bbb82a92fed1f2e1c01fe709571` | `6771afbdbc5135d8e09315db2077fd5b33c5ba32` | `0b8c2a7ef227e008fdc3dc397f8987bf4c90f5f7` `4c876905971af7d5ba756ee036b5204594c83736` | 2026-11-02 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52522 from b84330808 |
| S41 | #52593 | parent | `a938beab5f1d370f63d62ce78f3ab029f868bd03` | `a50cf897dfe0e6109f3aef621af7cb6946a5af7c` | `cb47b14cfdabdfae7f4372aa7b21661f57444bca` `da224e33a781f85032d88851fd6623b53f4185a4` | 2026-11-12 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Merge pull request #52625 from raunakpandey1 |
| S41 | #52593 | fix | `979ccd4e9ff5d5a34f2552ff5973a2254dcebc4f` | `50fdc19399d45c8a840084b681e3bbd84ca51063` | `a938beab5f1d370f63d62ce78f3ab029f868bd03` `e284456373a9fd7d748632fe0aa8fa33ff55ee5a` | 2026-11-12 | unsigned | 9.9.1 | 4.0.10-SNAPSHOT | Merge pull request #52593 from zhoubiao188 |
| S42 | #52285 | parent | `1434d2112bb979f6464e283d7a17ab728bf40ce4` | `f6b42d24ebdebc37038e751344f446d9f843ba06` | `6d94aa43a2289d117055aed5fd4ee70a46eaf052` `868bba79c1bc06008009e72f21dc65c5081127b5` | 2026-10-18 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #52284 from janwaleed09 |
| S42 | #52285 | fix | `57a1ca37c36f3cf355211aa8dea8c500b2dd3a09` | `82a43801e20a429a0ad55064600d8261420008c0` | `1434d2112bb979f6464e283d7a17ab728bf40ce4` `d8bebfddebfda01498e82b59494447e20320e0f4` | 2026-10-18 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #52285 from janwaleed09 |
| S43 | #52280 | parent | `a2338765ea747b695f6cd95a471da85d52bc54bb` | `b0d523b2e4810a758b3265738a715273f57fe228` | `c971bdd38c5e24b51dbdfe66fba621586498cb7f` `7e96dff4c2f6e78b5053b8ec13d952d5c226a4e0` | 2026-10-17 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S43 | #52280 | fix | `1b2d2fc80900d849fef7b937385594d63ac3bef3` | `f074166776f8d1c4d764dda9fc2e0dd4602808ca` | `a2338765ea747b695f6cd95a471da85d52bc54bb` `dc53a64e3623fcbbf93b59a860450f48fedca76a` | 2026-10-17 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #52280 from challa |
| S44 | #52244 | parent | `d5b807d26efd1fc658e76b966e4a947ff829d439` | `6306c903e468ab1f49bb928c34f81c90e7016244` | `65a1f003cdb8919a7b6e7e5477d4547af8f5e677` | 2026-10-15 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Restore Android copyright headers |
| S44 | #52244 | fix | `bba5f11efc7f28ced96961d9e16dbc8862b06010` | `c6b7f7d158577e09b4ba626fb8590515ad59c140` | `d5b807d26efd1fc658e76b966e4a947ff829d439` `48cf3e0f65567ae00f7c742c8e09afbbde52cf6c` | 2026-10-16 | unsigned | 9.8.1 | 4.0.9-SNAPSHOT | Merge pull request #52244 from janwaleed09 |
| S45 | #52402 | parent | `70b0b134a7472dc634f43cc143a9d37416ad6bbb` | `a469a4d6d8345a7863d2a340ed8416ad93dc52f9` | `e0a8055ec12a74073598f24e516627dcd78cdde2` `2fc23e373f39da76428d47fcba8cf0429a99ac07` | 2026-10-26 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S45 | #52402 | fix | `9c0bef7f8e9ac00dce1b45d70ad172e76de91bb3` | `da4b6c09293214e7865e39a3cb39c642cf5636a6` | `70b0b134a7472dc634f43cc143a9d37416ad6bbb` `fed281d570d41bd10d71a6858ade7feb2f1794cd` | 2026-10-26 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #52402 from challa |
| S46 | #51653 | parent | `59379ae449f15a6d17a333f5505941f4165ab3b2` | `48f4f6698fd558d7fa7140608ba626dd66ec2534` | `95994a53864b911170268dd59dc4ed138cf2f1a5` `5b3631bfe90eb30078857f4a9978e09c708c1bf3` | 2026-09-09 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S46 | #51653 | fix | `c966eca3e7467c2524df980aa52bac517b59a40b` | `2dcaed9e03d079f66bc58f25f51d35dfbcd9bafb` | `59379ae449f15a6d17a333f5505941f4165ab3b2` `a0f0cf00b347297d2eff3f46c66f3f90b0c36e49` | 2026-09-10 | unsigned | 9.7.0 | 4.2.0-SNAPSHOT | Merge pull request #51653 from JunggiKim |
| S47 | #52530 | parent | `6529cc7f81a938953a6dfdf5d9ca3f1ce984bfed` | `dbaf2797b31801623159c32260c7783398641db0` | `8d31e830329266062361ed3b42315af9237893d8` `d0c0a2f1fbe25d892390361e642d24975e432327` | 2026-11-02 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52523 from zhoubiao188 |
| S47 | #52530 | fix | `4f67ceb843a890b56bf37cdcd0144729c1f553de` | `ee983257933829bd46c4668096b72b7887b49ebc` | `6529cc7f81a938953a6dfdf5d9ca3f1ce984bfed` `d818dcace70b07776427c5032712c04c0250cc9a` | 2026-11-02 | unsigned | 9.8.1 | 4.0.10-SNAPSHOT | Merge pull request #52530 from zhoubiao188 |
| S48 | #51551 | parent | `d34a479879d348a1758196b7d1c696ea4f8ea8f0` | `8e85c26118b695848d57a4cf2ab04a786cd28a97` | `abbb2980398e97616282aa4f272bbf7ed9d84c2d` `6823d37408347942f4d97cd75bbefed2edf7188c` | 2026-09-09 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51635 from noojung |
| S48 | #51551 | fix | `69ad59c413ec8dfbd884ba0e712e8ada89513d29` | `bfbac33ac31d3d333fb8edb66d3d5fe34d5ea74a` | `d34a479879d348a1758196b7d1c696ea4f8ea8f0` `007ca201e14d7f03def15c5209762eff81b4e91c` | 2026-09-09 | unsigned | 9.7.0 | 4.0.9-SNAPSHOT | Merge pull request #51551 from COBI-98 |
| S49 | #51372 | parent | `b1966933c60d136fed1c860445180f13f3d39db7` | `87486c6dfffda6efdb84aa2d34629273ddadb266` | `7dd40448353dff9d59ea2f30bbbb8e3293aa1773` `eb9d52d4d878ff79bd52cd721177363e8994aff5` | 2026-10-08 | unsigned | 9.8.1 | 4.2.0-SNAPSHOT | Merge branch '4.1.x' |
| S49 | #51372 | fix | `535d133bdaa0ed46bbfb7ce578c14261806f39ac` | `bdeb340059104d4437efb9efb03040da426fa88f` | `b1966933c60d136fed1c860445180f13f3d39db7` `1dd4bee51cff27fb4e649dbfc372a8b788f48b50` | 2026-10-08 | good SSH (mhalbritter's GitHub signing key) | 9.8.1 | 4.2.0-SNAPSHOT | Merge pull request #51372 from skdas20 |
| S50 | #50433 | parent | `f83576eb2954c007464c696d1dabc7a871a7becc` | `95727419e794b06830aa94e07ed35e837fd0eace` | `15bb54a41fd6975d9c8111183605645ea3fad633` | 2026-07-16 | unsigned | 9.6.1 | 4.0.8-SNAPSHOT | Order kotlinxJsonCodecCustomizer so user-provided customizer can go after it |
| S50 | #50433 | fix | `21cb821f9553c048566b9a1779729c78167439a0` | `d3758a23faa644027865edc0962e175a0e1d03cf` | `f83576eb2954c007464c696d1dabc7a871a7becc` `9f8f4da5631a259b4167445ac951e090238f0a39` | 2026-07-16 | unsigned | 9.6.1 | 4.0.8-SNAPSHOT | Merge pull request #50433 from DragonFSKY |

## Other repositories

The brief also links two commits outside Spring Boot. Both are fetched at depth 1 (refs `refs/pins/s01-s50/...`) for their sources;
no build of them is prepared.

| Repository | Commit | Tree (= GitHub's) | Signature | Why |
|---|---|---|---|---|
| `$M/spring-batch.git` (existing mirror) | `4534099f47dbce965e85203e5131f93a1247d6e7` | `e50647b873daa28261e8ba59284f90c32ed837a0` | good, Mahmoud Ben Hassine's key `852CE5C9E3F3AA8008770E0477445000B6E68A87` (subkey of `77445000B6E68A87`, from `https://github.com/fmbenhassine.gpg`, `$P/keys/fmbenhassine.gpg` sha256 `dd74379f56d4d56b99f971ded47e55c544945e40f82514b365f754f4bd07a39f`) | S24 "Spring Batch transaction contract change" (2026-09-13, "Allow to use Mongo JobRepository with any PlatformTransactionManager") |
| `$M/spring-kafka.git` (new) | `e7ef57db3e5546017ff3b3a0997167752d48e67e` | `c53188cf6d359a49256cf7959cfef50266191574` | good, GitHub web-flow key `B5690EEEBB952194` (`$P/keys/web-flow.gpg` sha256 `6e8af687f60cf3f403151c8fb1b26e95e6f9e424ca60cc8f3787bd4466a3ef84`) | S30 "Upstream shutdown and acknowledgement tests" (`spring-kafka/src/test/java/org/springframework/kafka/listener/AwaitAsyncResultsOnStopTests.java` is there; project version 4.2.0-SNAPSHOT) |

Keys were checked in this work's own keyring (`GNUPGHOME=$P/gnupg`), whose daemons were stopped afterwards.

## Toolchain

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 | `~/.sdkman/candidates/java/` | earlier setups' installations. The Boot 4 builds require JDK 25 to run (`JavaConventions.BUILD_JAVA_VERSION = 25`) and compile with `--release 17` (`RUNTIME_JAVA_VERSION`). S16's slices use JDK 8. |
| GraalVM CE 25.5.5+3 | `~/.sdkman/candidates/java/25.5.5.0+3-graalce` (`$JG25`) | an earlier installation, with `native-image`; not verified by this setup. For S50's native-image observations. |
| Gradle 9.5.0, 9.6.1, 9.7.0, 9.8.1, 9.9.1, 9.9.2 | unpacked in `$P/tools/gradle-V` | zip sha256 = services.gradle.org's `.sha256`, all six ([digests](#gradle-distributions)) |
| Maven 3.10.0 | on `PATH` (sdkman), settings `$P/maven-settings.xml` (local repository `$P/m2`, plus `repo.spring.io/milestone`) | released artifacts only |
| Docker 29.9.3 | the machine's daemon | images in [Docker images](#docker-images) |

The wrapper is not used: `$P/scripts/gradle_case.sh` runs the verified distribution each checkout's wrapper names, on JDK 25, with
toolchain detection limited to the five Temurins, no auto-download, no build cache and no build scan. None of the pins' wrapper
properties sets `distributionSha256Sum`. Every pin's `gradle/wrapper/gradle-wrapper.jar` equals the wrapper jar Gradle publishes for
that version (`wrapperChecksumUrl` of `https://services.gradle.org/versions/all`, `$P/logs/wrappers.txt`, `$P/logs/wrapper-published.txt`;
95 of 95 Gradle pins). S16 has a Maven wrapper (Maven 3.5.0 from Maven Central) and no Gradle.

### Gradle distributions

zip sha256, each equal to services.gradle.org's `gradle-V-bin.zip.sha256` (`$P/logs/gradle-dists.txt`; the `.sha256` files are kept
in `$P/dl/gradle/`, the zips were deleted after unpacking):

| Gradle | zip sha256 | Pins (worktrees) |
|---|---|---|
| 9.5.0 | `553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746` | 8 |
| 9.6.1 | `9c0f7faeeb306cb14e4279a3e084ca6b596894089a0638e68a07c945a32c9e14` | 4 |
| 9.7.0 | `84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae` | 34 |
| 9.8.1 | `dce76f55f8e251a3a1f130eb120f30b3d271de2b76c9b0729d316b5a1b6dc01f` | 37 |
| 9.9.1 | `d8a18a7a841dd5df825d35a685fad6f2d7f12ac0c280e57b67c27b4a520ba228` | 5 |
| 9.9.2 | `971fcd7150ca4ba04852c0b2ca0d2d0ab9468e14b03473eab19528809914c76b` | 7 |

Published wrapper jar sha256: 9.5.0 and 9.6.1 `497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`, 9.7.0
`7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d`, 9.8.1 `3b8a25775a69158b5ad2b1d17a80a88dc7b40a352a73eb27d06c612a7ce68e98`,
9.9.1 and 9.9.2 `621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8`.

## Build facts

Both pins of every case have the same Gradle version and the same project version (`$P/logs/build-facts.tsv`; the Gradle column of the revision table). Project
versions: 4.0.8- to 4.0.11-SNAPSHOT (the `4.0.x` PRs), 4.1.0- to 4.1.3-SNAPSHOT (`4.1.x`), 4.2.0-SNAPSHOT (`main`), and
2.0.0.BUILD-SNAPSHOT for S16 (Maven). The Boot 4 builds import Spring Framework, Micrometer, Reactor and other Spring
projects at snapshot versions from `repo.spring.io/snapshot` ([Snapshot dependencies](#snapshot-dependencies)).

`help` on a fresh worktree takes about 2 minutes, most of it `buildSrc`'s own `check` (its tests, checkstyle and format check run
when the build configures). Every command here skips those with `-x :buildSrc:test -x :buildSrc:checkstyleMain -x
:buildSrc:checkstyleTest -x :buildSrc:checkFormat`, which leaves 20–60 s of configuration (buildSrc and `gradle/plugins` still compile).

## S16: the 2017 Maven build and its slice route

S16 (#9558) is Boot 2.0.0.BUILD-SNAPSHOT, built with Maven (wrapper: Maven 3.5.0), JDK 8. Its POMs import Spring Framework
`5.0.0.BUILD-SNAPSHOT`, Reactor `Bismuth-BUILD-SNAPSHOT`, Spring Data `Kay-BUILD-SNAPSHOT`, Spring Security and Session snapshots
from `repo.spring.io/snapshot`. That repository still answers for them, but it serves each snapshot only as its newest build:
Framework 5.0.0.BUILD-SNAPSHOT is the build of **2017-09-28** (`5.0.0.BUILD-20170928.094955-624`) and Reactor Bismuth-BUILD-SNAPSHOT
one of **2019-11-15**, not the builds of 2017-07-03 the pins compiled against. So the pins' own build cannot be reproduced from
public sources, and no Maven build of them was attempted. The slice route is prepared instead (the user's standing decision,
2026-11-26).

**Releases compared** (`repo.spring.io/milestone`; Boot milestones are not on Maven Central; every jar's sha1 equals the
repository's `.sha1`, no `.asc` is published, `$P/logs/s16-releases.txt`, files in `$P/releases/s16/`): Boot **2.0.0.M2**
(2017-06-14, before both pins, Framework 5.0.0.RC2) and **2.0.0.M3** (2017-07-26, after both, Framework 5.0.0.RC3 of 2017-07-24).
Git blob ids of the pins' changed production files against the copies in the releases' `-sources.jar` (`$P/logs/s16-blobs.txt`):

| Changed file | Parent | Fix | 2.0.0.M2 | 2.0.0.M3 |
|---|---|---|---|---|
| `spring-boot-autoconfigure/.../http/codec/CodecsAutoConfiguration.java` | absent | `ec4b000516e619733004581ba39ad7e105842ed9` | absent | `69794cf30f506c401793b200828ae276c47db808` |
| `spring-boot-autoconfigure/.../http/codec/package-info.java` | absent | `b734b106b5d3578d745f2746d846eff115c8bd0b` | absent | = fix |
| `spring-boot-autoconfigure/.../web/reactive/function/client/WebClientAutoConfiguration.java` | absent | `fd77faaa0e39307574b833c9de8adf86739d62cc` | absent | `1fd7a5997bbf7cab38c68cef58e69b441eef5e5d` |
| `spring-boot-autoconfigure/.../web/reactive/function/client/WebClientCodecCustomizer.java` | absent | `877cd78d4029bef40545ae64e8957b63352deff3` | absent | `f42d8efc21ee8db7bf9de67d7fc8ca4ff08e599a` |
| `spring-boot-autoconfigure/.../web/reactive/WebFluxAutoConfiguration.java` | `6e35f2527c22a9fab246b2b43b1f93cda2b107d0` | `b5a50c07d7517fd22f0f34d4b9b8a8f042f308e6` | = parent | `95d48ea61bcf5d45597886fecf40829a6801d661` |
| `spring-boot-autoconfigure/src/main/resources/META-INF/spring.factories` | `81a43a9aa2aacab8e246fcfc623ab57d1ae0f329` | `21846af9f0474619f3f5807e28ae738fa2f03084` | = parent | = fix |
| `spring-boot/.../web/codec/CodecCustomizer.java` | absent | `0f8edbef119cd45804c7282d6c34c4148e811e7f` | absent | `3c8392d888c1c258e8fcdef4bb0bcd816ef1bc6b` |
| `spring-boot/.../web/reactive/function/client/WebClientCustomizer.java` | absent | `3c4e90cd5c76358807c695b2e271634672920d8e` | absent | `e4b65cef22b29bac5950092be90916a22960d9be` |
| `spring-boot-test-autoconfigure/.../web/reactive/WebTestClientAutoConfiguration.java` | `7d7a7ba769c1dd712dfe20a22f589c5fb217533b` | `a4184e49cef3e0b8428d4c4cd2b9131c3885307f` | = parent | `51cc7b83b088bb4861258e252883c0a42734d8ee` |
| `spring-boot-test-autoconfigure/src/main/resources/META-INF/spring.factories` | `08255a6c2c7ccc20a88b91bb28fb2563630caf38` | `0d335481a5545cfe6f7dd98ff0faaa64291b84a6` | `e1727a9bd11b81daa23bd9ef0f68fadc9ed65005` | = fix |
| `spring-boot-test/.../test/web/reactive/WebTestClientContextCustomizer.java` | `e0a6b71108a0ed1a6059db38b600f2c7b822af93` | `ac4c1fc2502d6eaaac3b3e8ac5ca8df340d2ca7f` | = parent | `081c28acecf67df10782b2711eb9053d56f75ad4` |

So **2.0.0.M2 matches the parent** in every changed file the parent has, except `spring-boot-test-autoconfigure`'s
`spring.factories` (a resource; the slice carries the pin's copy). **No release matches the fix.** M3 differs from it in every
changed Java file but `package-info.java`; the differences are formatting and Javadoc (`$P/logs/s16-fix-vs-m3.diff`, 12 lines a file
at most), plus one API rename in `CodecsAutoConfiguration`: the fix calls `defaults.jackson2Decoder(...)` / `jackson2Encoder(...)`,
M3 `jackson2JsonDecoder(...)` / `jackson2JsonEncoder(...)`.

**The fix's changed files compile against no released Framework**: against 5.0.0.RC2 (M2's) `WebClient.Builder.clone()` and
`ExchangeStrategies.Builder.codecs(...)` / `WebTestClient.Builder...codecs(...)` do not exist (4 errors), and against 5.0.0.RC3 the
`CodecConfigurer.DefaultCodecs.jackson2Decoder/jackson2Encoder` methods are already renamed (2 errors, `$P/slices/S16-fix-*/javac-main.log`).
The Framework the fix used existed only in the July 2017 snapshots, which are gone. Nothing was edited to make it compile.

**Sets** (`$P/releases/SET/`, `jars/` and a `:`-joined `classpath.txt` of `$P/m2` paths): `boot-2.0.0.M2-s16` (spring-boot,
-autoconfigure, -test, -test-autoconfigure, -starter-webflux, -starter-json 2.0.0.M2 under its own BOM: Framework 5.0.0.RC2, Reactor
3.1.0.M2, reactor-netty 0.6.4, Jackson 2.9.0.pr3), `boot-2.0.0.M2-fwRC3-s16` (the same Boot jars with Framework 5.0.0.RC3 and Reactor
Bismuth-M3 imported first), `boot-2.0.0.M3-s16` (the same artifacts at 2.0.0.M3: Framework RC3, Reactor 3.1.0.M3), and the test
libraries `tests-S16-m2`, `tests-S16`, `tests-S16-m3` (spring-boot-starter-test, JUnit 4.12, AssertJ 3.8.0, Mockito 2.8.9, spring-test,
reactor-test, spring-webmvc, servlet API 3.1.0, joda-time, Hibernate Validator, tomcat-embed-el, each under the matching BOM).

**Runs** (`$P/scripts/slice_s16.sh`, JDK 8, seconds each, inline; `$P/logs/slices-s16.txt`, logs and classes under `$P/slices/S16-*`):

| Step | Result |
|---|---|
| parent slice on `boot-2.0.0.M2-s16` | compiles: 3 files, 10 classes, `$P/slices/S16-parent-boot-2.0.0.M2-s16/S16-parent-boot-2.0.0.M2-s16-slice.jar` (digests below) |
| fix slice on `boot-2.0.0.M2-s16` | does not compile (4 errors, RC2 lacks the APIs above) |
| fix slice on `boot-2.0.0.M2-fwRC3-s16` | does not compile (2 errors, the RC3 rename) |
| parent's `WebFluxAutoConfigurationTests` on the parent slice | **OK (15 tests)**; `WebClientAutoConfigurationTests` and `WebTestClientAutoConfigurationTests` are new in the landing |
| fix's three test classes on the parent slice (transplant) | **does not compile** (25 errors): `org.springframework.boot.web.codec` and `...web.reactive.function.client` (`CodecCustomizer`, `WebClientCustomizer`) do not exist there, as expected of the parent |
| fix's three test classes on Boot 2.0.0.M2 alone | does not compile (the same 25 errors) |
| fix's three test classes on **Boot 2.0.0.M3** alone (nearest release with the feature, *not the pin*) | 21 tests, **1 failure**: `WebClientAutoConfigurationTests#shouldGetPrototypeScopedBean`, `IllegalStateException: The underlying HTTP client completed without emitting a response.` (thrown from `DefaultWebClient`; the test's mocked connector answers with nothing, and RC3's `WebClient` treats that as an error); the other 20 pass |
| parent's `WebFluxAutoConfigurationTests` on Boot 2.0.0.M3 alone | OK (15 tests) |

Parent slice class digests (sha256, `$P/slices/S16-parent-boot-2.0.0.M2-s16/main.SHA256SUMS`): `WebFluxAutoConfiguration.class`
`43b6928e560d91e6e735aa628e9357dcfa2a0b4a5a14d43c2c0a227cbcab16d2` (+6 nested), `WebTestClientAutoConfiguration.class`
`059a2225e56b0257a95195f991f7e1da1e4fc9359f9b371568c0f565e57ec443`, `WebTestClientContextCustomizer.class`
`2ddd8abc6c76812f711814d7f0c53797a8418054f5bde2c30b87c82ea47082a5` (+1 nested); the two `spring.factories` copied beside them
(`resources/MODULE/META-INF/spring.factories`): autoconfigure `39aa97be130059b347820a0c2986fc7d532c511d96dc1d82ddd1255164178bfd`,
test-autoconfigure `ec59bc3a80098e89ee75dc2945474052d0bf38049bebc51a13d5abad728a4c29`.

Release jar digests (sha256): spring-boot 2.0.0.M2 `d30071828885c2c9e300dc226a090d904d37e05427e3d45ae49da3dd686d8da4`, M3
`f21cb486b400fead221f740cc87e2ef37a10604ebec4cac864d1b7d408716ad9`; spring-boot-autoconfigure M2
`b4a37cc0643d3185376c5cd4dd5355d906538f0a36b73d272d2f6b9ffd9204e9`, M3 `3e50fc340ec5acbaa50ffe13123b4fa7082bd1bf342c560f0f689e8e27db0330`;
spring-boot-test M2 `bc6c5986c660bd0ff9a09b9a8118b661691ab77b5dc7b6686a07a9d33a2ff9ca`, M3
`4a563fca924d11b7ad869539b9f5dc7242c777255d38d38de3c36986a77a9a16`; spring-boot-test-autoconfigure M2
`b4a7f5591084e4fa0363630b083ae01589e93f88b2f84d770c9ff1aecda42e5f`, M3 `0be70f8f422fc4f8cbd52ae11ada9f8aa597e2456963f0f3d8bf718aaa0fad50`.

## Released artifacts

From Maven Central (or `repo.spring.io/milestone` for the 2017 milestones), resolved with Maven into `$P/m2`
(`$P/scripts/release_set.sh SET "BOMS" "COORDS"`, a generated pom per set in `$P/releases/SET/pom.xml`, runtime scope); each set has
its jars in `$P/releases/SET/jars/` and a `:`-joined `classpath.txt` of `$P/m2` paths. Every jar of every set has the sha1 of its repository's `.sha1` (277 of 277), and each `.asc` was checked in `$P/gnupg` with keys from keyserver.ubuntu.com / keys.openpgp.org (`$P/scripts/verify_releases.sh`, results with sha256 in `$P/logs/release-verify.txt`): 193 good signatures, 30 good by a key that has expired since (Jackson's Tatu Saloranta `C9FBAA83A8753994` ×14, Oracle Maven ×4, datasource-decorator 2.0.1 by Arthur Gavlyukovskiy `A2516E15D05E16DE`, and others), 3 good by a revoked key (byte-buddy and byte-buddy-agent 1.6.14 of the S16 test libraries, Rafael Winterhalter `BB2914C1FA0811C3`; plexus-build-api 0.0.7, Sonatype `0374CF2E8DD1BDFD`), 1 not checkable (openjson 1.0.13 of the GraalVM build tools set, key `CF776DADF519DEE3` not on either keyserver), and 50 with no `.asc` published (the 2017 milestones of `repo.spring.io/milestone`, and javax.inject 1, validation-api 1.1.0.Final, hibernate-validator 5.4.1.Final, jboss-logging 3.3.1.Final). Spring's jars are signed by "Spring Builds" `928FBF39003C0425`.

| Set | Why (brief) | Main jars (sha256) |
|---|---|---|
| `boot-4.0.6` | S15 (Framework issue #36737 upgraded to 4.0.6), S50 (issue #50422 on 4.0.6) | spring-boot-micrometer-metrics 4.0.6 `a21e1e415c1e6ab3252b3745110f0717e602cb6b1ffa59d2f2a29bc3ab45bdb0`, spring-boot-flyway 4.0.6 `a2a6884d3ef606523777cec431c5c2b5032d3056599d8b6a18887100c5b0bafe`, spring-boot 4.0.6 `163d0c77cc7e8b6a2d523e5d0ebc3afe838d33dc89162c613a75a63bc197b9e6` (Framework 7.0.7, Flyway 11.14.1) |
| `boot-4.0.7` | S38 (issue #51154 on 4.1.0 and 4.0.7) | spring-boot 4.0.7 `edb984d0bc80d209bed271e6d334fbfbfcf11cc4c1ef5059adc31c5bde7b1d7c` (Framework 7.0.8) |
| `boot-4.1.0` | S04 (upgrade to 4.1.0), S38, S49 (Boot 4.1.0 executable WAR) | spring-boot 4.1.0 `b23951a3a7f867e38db4729b8594e1b72374516f386b1dd9cf4d5317d6d3f91f`, spring-boot-jarmode-tools `20b66fc7cffe830b51ce2cc36df77a0dd695cf197828902503e04492087c84b6`, spring-boot-loader-tools `5bdd6efb13eb216e4e099f83d165b09ffc3338e3f21a8135c91dd8ca8940a17a`, spring-boot-loader `bbe479f00a26c1a13fa69db3d99f570a8fdc656551e4b306a32bc2941a2409b1`, spring-boot-maven-plugin `7f1eeff2bb35c91bcedb89c7b1e4269e2cdedf4dc281692c66cba07dc967f25f` (Framework 7.0.8) |
| `boot-4.1.1`, `framework-7.0.9` | S37 (issue #51958: Boot 4.1.1 with Framework 7.0.9) | spring-boot 4.1.1 `0d92b532b1d4020640e72d78c31af175c23db8e0ddd45b81855b7fdf4c9c70f0`, spring-boot-test 4.1.1 `c16efcceaf7c0f7fff6c2cbac5ba1e7e47ee68bacc6a446f8adfe07ffe4ea579`; spring-test 7.0.9 `6ce8fc116f5d309b9ac50a6738bd1b15ea4012a4a5563c0ee89b795bfc9af0dc`, spring-context 7.0.9 `7552a2fcfa30cea53eb14d7a65a7a8e1b1dd82e832a7164fb7e6fb105f438858` (Boot 4.1.1's BOM manages Framework 7.0.9 too) |
| `boot-4.2.0-RC1` | S45 (failure reported on 4.2.0-RC1) | spring-boot-loader 4.2.0-RC1 `95b0035b33a3572c0ccf7002ee2d2d0e975ba99d9c520df7be6463928a956e2b` (on Central) |
| `boot-3.5.14` | S15 (upgrade from 3.5.14) | spring-boot-actuator-autoconfigure 3.5.14 `97e8056deea80c96a0919e4910e474099761f272cf20e9759fc3bf3813381010`, spring-boot 3.5.14 `3f1d94101be1ad63fbd067432280e3ffd7fc6549cce43d11c87609843d46ed56` (Framework 6.2.18) |
| `tomcat-11.0.24` | S19 (the PR's Tomcat 11.0.24 probe) | tomcat-embed-core 11.0.24 `e7b966dcaac8c5ffa4f10e44031ebf5b71f2123560c08ac8b7120028615aea08` |
| `decorator-2.0.1` | S21 (spring-boot-data-source-decorator 2.0.1) | `com.github.gavlyukovskiy:datasource-proxy-spring-boot-starter:2.0.1` `ab0339863276b63955072b0c3b96354b937ef4800266c9eb8ff8f479cbf1668b`, datasource-decorator-spring-boot-autoconfigure 2.0.1 `a751fc919bfef81871d48fd6c5e189bf5e063945e6b565baeb23d9415a1e68ab` (it pulls Boot 4.0.6) |
| `graalvm-buildtools-0.11.5` | S50 (native-image builds; the pins' `nativeBuildToolsVersion`) | `org.graalvm.buildtools:native-gradle-plugin:0.11.5`, `native-maven-plugin:0.11.5` (digests in `$P/logs/release-verify.txt`) |
| `maven-war-plugin-3.5.1` | S49 (the report's Maven WAR Plugin 3.5.1) | maven-war-plugin 3.5.1 `0b5c90b3684df5aba537eb7e500b91c1381f2e0c6e6e403f16c925889ce0de3b` |

## Docker images

Pulled for the claims that need a service and for S29's `dockerTest` (`$P/logs/docker-images.txt`). The versions are those of the
pins' `test-support/spring-boot-docker-test-support/.../TestImage.java` (S29's fix), or the one the brief names.

| Image | Digest | Created | For |
|---|---|---|---|
| `rabbitmq:4.2-management` | `sha256:a3afd4d8dcae7d2baccc92500da74516057ed3babb7d37cf405715bb7c798660` | 2026-11-24 | S29 (the pins' `TestImage.RABBITMQ`; a floating tag, newer than the pins) |
| `redis:7.0.11` | `sha256:1008c73f08e9f913868e2fa2e843212b62ea5bf3c66435d87bc7a6207bc0f1b4` | 2023-07-04 | S27 (`TestImage.REDIS`) |
| `redis:8.6.2` | `sha256:832d7785830f3f4b559300e6191fc914b15642c1935252338825cf4332200148` | 2026-04-22 | S25's three-node cluster (the PR's Redis 8.6.2) |
| `mongo:5.0.17` | `sha256:ee514514754ffdb13597a894bdae90fdabbe4c0926bf96b40a84d1233782bcc1` | 2023-05-03 | S24 (`TestImage.MONGODB`; transactions need a replica set) |
| `apache/kafka:3.7.0` | `sha256:41c20d65b0a2180b9deca056d47540771752e69fe9225d5748dd65a25a9675d7` | 2024-02-09 | S30 (`TestImage.APACHE_KAFKA`) |
| `postgres:17` | `sha256:97fb53376be3e4fb1a8a61421daa69dcc3bf2fa39bda3259f5245f9a455af1a9` | 2026-11-24 | S28 (the brief's `postgres:17`; a floating tag: the pull replaced the machine's older `postgres:17`, image `0d938e975177`, which is still there by id) |
| `testcontainers/ryuk:0.14.0` | `sha256:7c1a8a9a47c780ed0f983770a662f80deb115d95cce3e2daa3d12115b8cd28f0` | 2025-09-26 | the reaper Testcontainers 2.0.5 (the pins' version) starts |

## Online resolution

`$P/scripts/resolve_case.sh CASE-ROLE` (inline, each Gradle run in a 6 GB scope): one online run per worktree that configures
the whole build (buildSrc and `gradle/plugins` compile, their dependencies and plugins resolve) and resolves **every
configuration of the case's classpath projects** (column 4 of `$P/scripts/cases.tsv`) through the init script
`$P/scripts/resolve-all.init.gradle` (task `setupResolveAll -PsetupResolve=ALL`; no upstream file changes). That first pass did
**not** resolve the configurations of the projects those depend on (the second pass below does). `GRADLE_USER_HOME` is
`$P/gradle-home`, new for this work (11 GB after the first pass, 12 GB after the second); nothing was copied from another setup's
cache. All 98 Gradle worktrees exited 0 (`$P/logs/resolve.summary.all.txt`, logs
`$P/logs/CASE-ROLE.resolve.online.log`): 2,440 configurations, of which the only failures are the Kotlin plugin's IDE-only
`*DependenciesMetadata` configurations (no compile or test task uses them) and, at first, S30's test classpaths
([below](#s30-substitutes-spring-kafka-420-m2)). Four resolutions at once on the one home stalled for minutes on Gradle's
cross-process cache locks; the pass then ran one at a time and in two lanes (`$P/scripts/resolve_lane.sh`).

Then `case_job.sh CASE dryrun` (offline `--dry-run` of both pins' task graphs, the classpath-writing tasks included) configured
for all 49 Gradle cases, 98 of 98 exit 0 (`$P/logs/dryrun.summary.txt`). A dry-run resolves no compile classpath, so it did not
show the gap: in the first run of the jobs 38 of the 49 cases failed offline, every one on `No cached version of … available for
offline mode` for a configuration of a project the case's projects depend on, nearly always
`:test-support:spring-boot-test-support:compileClasspath` (its optional `org.apache.cassandra:java-driver-core`,
`spring-data-redis` and the like) ([Job results](#job-results)).

**Second pass, the project closure** (`$P/scripts/resolve_closure.sh CASE-ROLE`, lanes `$P/scripts/closure_lane.sh`): the same
online resolution of every configuration, now of the case's projects **and every project they reach through project dependencies
in any configuration, transitively** (`$P/scripts/resolve-closure.init.gradle`, root task `setupResolveClosure
-PsetupClosureOf=:a,:b`, which prints the closure; between 4 and 71 projects a worktree). It keeps snapshot builds already in the
cache (`cacheChangingModulesFor 30 days`, so it fetched only what was missing; no inventoried snapshot jar changed, see
[Snapshot dependencies](#snapshot-dependencies)); S30 ran with its Spring Kafka substitution. 98 of 98 worktrees resolved: 24,888
configuration resolutions, the only failures again the Kotlin `*DependenciesMetadata` configurations (`$P/logs/resolve.closure.summary.txt`,
logs `$P/logs/CASE-ROLE.resolve.closure.log`). Four runs (S06 at both pins, S44's parent, S49's fix) hit intermittent DNS failures for `repo.spring.io` (`Could not HEAD …`,
the repository then disabled for the run) and were rerun until clean (the `retry` lines). **Then the same closure resolution
`--offline`** (`$P/scripts/closure_offline_lane.sh`, logs `$P/logs/CASE-ROLE.resolve.closure.offline.log`, summary
`$P/logs/resolve.closure.offline.summary.txt`): 98 of 98 exit 0, every closure configuration resolved from the cache, the only
failures the same Kotlin metadata configurations.

## Snapshot dependencies

Every Boot 4 pin but S02–S04 imports Spring snapshots (`$P/logs/snapshot-versions-by-case.txt`: Framework 7.0.9- to 7.1.0-SNAPSHOT,
Micrometer, Reactor, Spring Data, Security, Kafka, AMQP, Batch, Integration and others). **Both pins of every case import the same
snapshot versions**, so both read the same bytes. `repo.spring.io/snapshot` serves each snapshot only as its newest build, so that
is what the cache holds: every one of the 222 cached snapshot jars has the sha1 of the newest build's `.sha1`
(`$P/scripts/snapshots.sh`, checked again after the second resolution pass; sha256 per jar in `$P/logs/snapshots.txt`, the
first pass's 107 in `$P/logs/snapshots.first-pass.txt`, none of which changed; table by `$P/scripts/snapshot_table.py`). Most of those builds are dated after the pins they serve
(the pins are of 2026-05 to 2026-11, the builds mostly of 2026-10 to 2026-11); a snapshot version still served at all is one not yet
released. Build `--offline` to keep these bytes: an online build may fetch a newer build.

| Group | Version | Newest build (= the cached bytes) | Modules cached |
|---|---|---|---|
| `io.micrometer` | 1.6.8-SNAPSHOT | `1.6.8-20261015.212202-17` | micrometer-tracing |
| `io.micrometer` | 1.6.9-SNAPSHOT | `1.6.9-20261113.010600-5` | micrometer-tracing |
| `io.micrometer` | 1.8.0-SNAPSHOT | `1.8.0-20261113.011313-131` | micrometer-tracing |
| `io.micrometer` | 1.16.8-SNAPSHOT | `1.16.8-20261015.224611-45`, `1.16.8-20261015.224611-46` | micrometer-commons, micrometer-core, micrometer-jakarta9, micrometer-java21, micrometer-observation, micrometer-observation-test, micrometer-registry-appoptics, micrometer-registry-atlas, micrometer-registry-datadog, micrometer-registry-dynatrace, micrometer-registry-elastic, micrometer-registry-ganglia, micrometer-registry-graphite, micrometer-registry-humio, micrometer-registry-influx, micrometer-registry-jmx, micrometer-registry-kairos, micrometer-registry-new-relic, micrometer-registry-otlp, micrometer-registry-prometheus, micrometer-registry-prometheus-simpleclient, micrometer-registry-stackdriver, micrometer-registry-statsd |
| `io.micrometer` | 1.16.9-SNAPSHOT | `1.16.9-20261113.010950-9` | micrometer-commons, micrometer-core, micrometer-jakarta9, micrometer-java21, micrometer-observation, micrometer-observation-test, micrometer-registry-appoptics, micrometer-registry-atlas, micrometer-registry-datadog, micrometer-registry-dynatrace, micrometer-registry-elastic, micrometer-registry-ganglia, micrometer-registry-graphite, micrometer-registry-humio, micrometer-registry-influx, micrometer-registry-jmx, micrometer-registry-kairos, micrometer-registry-new-relic, micrometer-registry-otlp, micrometer-registry-prometheus, micrometer-registry-prometheus-simpleclient, micrometer-registry-stackdriver, micrometer-registry-statsd |
| `io.micrometer` | 1.17.1-SNAPSHOT | `1.17.1-20260812.180937-42` | micrometer-commons, micrometer-observation |
| `io.micrometer` | 1.17.2-SNAPSHOT | `1.17.2-20261015.224856-41` | micrometer-commons, micrometer-observation |
| `io.micrometer` | 1.18.0-SNAPSHOT | `1.18.0-20261116.155816-313`, `1.18.0-20261116.155816-314`, `1.18.0-20261116.155816-315` | micrometer-commons, micrometer-core, micrometer-jakarta9, micrometer-java21, micrometer-observation, micrometer-observation-test, micrometer-registry-appoptics, micrometer-registry-atlas, micrometer-registry-datadog, micrometer-registry-dynatrace, micrometer-registry-elastic, micrometer-registry-ganglia, micrometer-registry-graphite, micrometer-registry-humio, micrometer-registry-influx, micrometer-registry-jmx, micrometer-registry-kairos, micrometer-registry-new-relic, micrometer-registry-otlp, micrometer-registry-prometheus, micrometer-registry-prometheus-simpleclient, micrometer-registry-stackdriver, micrometer-registry-statsd |
| `io.projectreactor` | 3.8.7-SNAPSHOT | `3.8.7-20260807.084400-41`, `3.8.7-20260807.084400-42` | reactor-core, reactor-test |
| `io.projectreactor` | 3.8.8-SNAPSHOT | `3.8.8-20261016.063046-44`, `3.8.8-20261016.063046-46` | reactor-core, reactor-test |
| `io.projectreactor` | 3.8.9-SNAPSHOT | `3.8.9-20261110.081734-21` | reactor-core, reactor-test |
| `io.projectreactor` | 3.9.0-SNAPSHOT | `3.9.0-20261110.081737-23`, `3.9.0-20261110.081737-24` | reactor-core, reactor-test |
| `io.projectreactor.netty` | 1.3.7-SNAPSHOT | `1.3.7-20260810.152616-80` | reactor-netty-core, reactor-netty-http |
| `io.projectreactor.netty` | 1.3.8-SNAPSHOT | `1.3.8-20261022.061939-75` | reactor-netty-core, reactor-netty-http |
| `io.projectreactor.netty` | 1.3.9-SNAPSHOT | `1.3.9-20261113.130042-44` | reactor-netty-core, reactor-netty-http |
| `io.projectreactor.netty` | 1.4.0-SNAPSHOT | `1.4.0-20261113.130354-169`, `1.4.0-20261113.130354-170` | reactor-netty-core, reactor-netty-http |
| `org.springframework` | 7.0.9-SNAPSHOT | `7.0.9-20260813.170400-53` | spring-aop, spring-beans, spring-context, spring-context-support, spring-core, spring-core-test, spring-expression, spring-jdbc, spring-oxm, spring-r2dbc, spring-test, spring-tx, spring-web |
| `org.springframework` | 7.0.10-SNAPSHOT | `7.0.10-20261016.104357-125` | spring-aop, spring-aspects, spring-beans, spring-context, spring-context-support, spring-core, spring-core-test, spring-expression, spring-jdbc, spring-messaging, spring-orm, spring-oxm, spring-r2dbc, spring-test, spring-tx, spring-web, spring-webflux, spring-webmvc |
| `org.springframework` | 7.0.11-SNAPSHOT | `7.0.11-20261112.162258-46` | spring-aop, spring-aspects, spring-beans, spring-context, spring-context-support, spring-core, spring-core-test, spring-expression, spring-jdbc, spring-messaging, spring-orm, spring-oxm, spring-r2dbc, spring-test, spring-tx, spring-web, spring-webflux, spring-webmvc |
| `org.springframework` | 7.1.0-SNAPSHOT | `7.1.0-20261113.124602-603` | spring-aop, spring-aspects, spring-beans, spring-context, spring-context-support, spring-core, spring-core-test, spring-expression, spring-jdbc, spring-messaging, spring-orm, spring-oxm, spring-r2dbc, spring-test, spring-tx, spring-web, spring-webflux, spring-webmvc |
| `org.springframework.amqp` | 4.2.0-SNAPSHOT | `4.2.0-20261119.051643-219` | spring-amqp, spring-rabbit, spring-rabbit-stream, spring-rabbitmq-client |
| `org.springframework.batch` | 6.1.0-SNAPSHOT | `6.1.0-20261119.172345-140` | spring-batch-core, spring-batch-infrastructure |
| `org.springframework.data` | 4.0.8-SNAPSHOT | `4.0.8-20261014.082734-8`, `4.0.8-20261014.082740-8`, `4.0.8-20261015.080402-19`, `4.0.8-20261015.100000-21` | spring-data-commons, spring-data-jdbc, spring-data-keyvalue, spring-data-r2dbc, spring-data-redis, spring-data-relational |
| `org.springframework.data` | 4.0.9-SNAPSHOT | `4.0.9-20261113.094844-11`, `4.0.9-20261113.094849-4`, `4.0.9-20261113.094856-8`, `4.0.9-20261113.101053-6` | spring-data-commons, spring-data-keyvalue, spring-data-r2dbc, spring-data-redis, spring-data-relational |
| `org.springframework.data` | 4.1.1-SNAPSHOT | `4.1.1-20260813.071920-11`, `4.1.1-20260813.071929-12`, `4.1.1-20260813.071929-21`, `4.1.1-20260813.071937-21` | spring-data-commons, spring-data-keyvalue, spring-data-r2dbc, spring-data-redis, spring-data-relational |
| `org.springframework.data` | 4.1.2-SNAPSHOT | `4.1.2-20261014.082734-18`, `4.1.2-20261014.082737-11`, `4.1.2-20261015.080407-23`, `4.1.2-20261015.095958-25` | spring-data-commons, spring-data-keyvalue, spring-data-r2dbc, spring-data-redis, spring-data-relational |
| `org.springframework.data` | 4.2.0-SNAPSHOT | `4.2.0-20261113.094852-31`, `4.2.0-20261113.094903-64`, `4.2.0-20261113.101051-58`, `4.2.0-20261117.141558-53` | spring-data-commons, spring-data-jdbc, spring-data-keyvalue, spring-data-r2dbc, spring-data-redis, spring-data-relational |
| `org.springframework.data` | 5.0.8-SNAPSHOT | `5.0.8-20261014.082750-10`, `5.0.8-20261014.083944-9` | spring-data-mongodb, spring-data-rest-core, spring-data-rest-webmvc |
| `org.springframework.data` | 5.0.9-SNAPSHOT | `5.0.9-20261113.094908-6` | spring-data-mongodb |
| `org.springframework.data` | 5.2.0-SNAPSHOT | `5.2.0-20261113.094853-40`, `5.2.0-20261113.094917-46` | spring-data-mongodb, spring-data-rest-core, spring-data-rest-webmvc |
| `org.springframework.data` | 8.0.8-SNAPSHOT | `8.0.8-20261016.072018-7` | spring-data-neo4j |
| `org.springframework.data` | 8.0.9-SNAPSHOT | `8.0.9-20261113.094844-7` | spring-data-neo4j |
| `org.springframework.data` | 8.2.0-SNAPSHOT | `8.2.0-20261113.094854-49` | spring-data-neo4j |
| `org.springframework.graphql` | 2.0.6-SNAPSHOT | `2.0.6-20261016.102023-19` | spring-graphql |
| `org.springframework.graphql` | 2.0.7-SNAPSHOT | `2.0.7-20261110.131650-4` | spring-graphql |
| `org.springframework.graphql` | 2.1.0-SNAPSHOT | `2.1.0-20261110.131205-44` | spring-graphql |
| `org.springframework.hateoas` | 3.0.6-SNAPSHOT | `3.0.6-20261013.200322-9` | spring-hateoas |
| `org.springframework.hateoas` | 3.2.0-SNAPSHOT | `3.2.0-20261109.103826-36` | spring-hateoas |
| `org.springframework.kafka` | 4.2.0-SNAPSHOT | `4.2.0-20261119.052259-227` | spring-kafka, spring-kafka-test |
| `org.springframework.plugin` | 4.2.0-SNAPSHOT | `4.2.0-20261113.113009-22` | spring-plugin-core |
| `org.springframework.security` | 7.0.8-SNAPSHOT | `7.0.8-20261014.180739-2`, `7.0.8-20261014.180739-31` | spring-security-config, spring-security-core, spring-security-crypto, spring-security-web |
| `org.springframework.security` | 7.0.9-SNAPSHOT | `7.0.9-20261113.053915-49` | spring-security-config, spring-security-core, spring-security-crypto, spring-security-web |
| `org.springframework.security` | 7.2.0-SNAPSHOT | `7.2.0-20261113.100953-212`, `7.2.0-20261113.100953-213` | spring-security-config, spring-security-core, spring-security-crypto, spring-security-web |

## S30 substitutes Spring Kafka 4.2.0-M2

S30's pins (2026-09-16) manage Spring Kafka `4.2.0-SNAPSHOT` with Kafka `4.3.1`. The only build of that snapshot still served is of
2026-11-19 (`4.2.0-20261119.052259-227`); its `spring-kafka-test` POM requires `org.apache.kafka:kafka-clients:4.4.0` with classifiers
`test` and `test-fixtures`, and under the pins' Kafka 4.3.1 the `test-fixtures` jar does not exist (Maven Central publishes
`kafka-clients-4.3.1-test.jar` only), so `:module:spring-boot-kafka:testCompileClasspath` and `testRuntimeClasspath` failed to
resolve at both pins. Released Spring Kafka 4.2 versions (Maven Central): 4.2.0-M1 (2026-08-20, Kafka 4.3.1, **no**
`ContainerProperties#setAwaitAsyncResultsOnStop`), **4.2.0-M2** (2026-09-24, Kafka 4.3.1, has it), 4.2.0-RC1 (2026-10-22) and 4.2.0
(2026-11-19), both on Kafka 4.4.0. `$P/scripts/subst-spring-kafka.init.gradle` substitutes `spring-kafka` and `spring-kafka-test`
4.2.0-M2 in every configuration; `case_job.sh` passes it for S30 only, and with it both pins resolve (`$P/logs/S30-ROLE.resolve.online.log`)
and dry-run. The brief's technical note asks for "a compatible dependency exposing the method on both sides"; M2 is the first
release that does, eight days after the pins. Jars (`$P/logs/subst-spring-kafka.txt`): spring-kafka-4.2.0-M2.jar sha256
`808bd76ab42f49a11d1fc7e71b4ae21a9e089d12d57e47c116517e15b5f9704d`, spring-kafka-test-4.2.0-M2.jar
`0be953f86673cdde861aba1d258a31393e41b19926ad0eb59e4decce1cad41a4`, sha1 = Central's, good signatures by Spring Builds
`928FBF39003C0425`. No other case substitutes anything.

## Jobs

One job per Gradle case (49; S16 has none, it is on its slice route), each of four steps run by `$P/scripts/case_job.sh CASE STEP`
(table of projects and test classes: `$P/scripts/cases.tsv`; submitted by `$P/scripts/submit_case.sh`):

1. `fix`: in `$W/CASE-fix`: `:P:jar` for the jar projects and `:P:SOURCESET --tests CLASS` for each landed test class, with
   `-Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline --continue`, buildSrc's own checks skipped,
   and `$P/scripts/setup-tests.init.gradle` (a `--tests` filter that matches nothing is not an error); then keeps
   `$P/artifacts/CASE-fix/`: `jars/`, `SHA256SUMS` (jars, and every class compiled from a production source file the landing changed,
   nested classes included) and, per classpath project P (`:` as `_` in the name), `P.runtimeClasspath.txt` and `P.testRuntimeClasspath.txt`
   (`:`-joined; the project outputs they name are copied under `tree/`, Gradle's `gradle-api` and `gradle-test-kit` jars, which
   Gradle generates in the job's own home, under `gradle-home/` (the first run rejected them: S10, S47, S49), the rest are paths
   into `$P/gradle-home`). `$P/logs/CASE-ROLE.test.offline.class.txt` has the JUnit counts of each landed class alone, found by the XML's `<testsuite
   name>` (`$P/scripts/class_counts.py`, from the third run on). Earlier runs looked the class up by file name and report
   `no-result` for classes without nested classes (first run, before about 09:40) and for long class names (Gradle 9 hashes
   those file names).
2. `parent`: the same in `$W/CASE-parent`, with those landed classes that exist at the parent.
3. `transplant`: `git archive` of the parent into `$P/build/CASE-parent-landed`, every changed file under `src/test`, `src/testFixtures`,
   `src/intTest` or `src/dockerTest` (and a changed module `build.gradle`: S09, S37) taken from the fix, then the same test classes.
   Passes when they fail (`TRANSPLANT-FAILS-AS-EXPECTED`) or do not compile (`TRANSPLANT-DOES-NOT-COMPILE-AS-EXPECTED`).
4. `clean`: `git clean -fdxq` in both worktrees, transplant copy and the case's Gradle home removed.

Each case runs with a Gradle home of its own, `$P/gradle-homes/CASE`, and reads every dependency from `$P/gradle-home/caches` as
Gradle's read-only dependency cache (`GRADLE_RO_DEP_CACHE`), so jobs side by side share no writable cache; checked with the S01 and
S30 dry-runs. Choices in `cases.tsv`: the test classes are the landed `*Tests` files, except **S19** (the two Tomcat tests and the
OAuth2 client smoke test the brief cites; the other seven changed smoke tests are not run), **S20** (only the landed fixture
methods `givenARestartedServer*` of the four Tomcat and Jetty servlet and reactive factory test classes; the full classes are
hundreds of server tests), **S27** (jars of `:core:spring-boot-docker-compose` and `:module:spring-boot-data-redis` and the two core
tests; the other 16 changed modules are not built), **S33** (also the three consumers of the changed test fixture: the WebMvc,
WebFlux and Jersey `*HealthEndpointAdditionalPathIntegrationTests`), **S48** (loader-tools' `RepackagerTests`, a concrete
`AbstractPackagerTests`, and the Maven plugin's `WarIntegrationTests` from `intTest`).

**Two jobs need the network at test time**, so their steps run without `--offline`: **S10** (`JavaPluginActionIntegrationTests` is a
`@GradleCompatibility` TestKit test; on JDK 25 it runs Gradle 9.0.0 and the current version, which TestKit downloads from
services.gradle.org into the build directory) and **S48** (`WarIntegrationTests` runs Maven builds whose local repository is
`build/local-maven-repository` and whose plugins come from Maven Central). **S29** runs `dockerTest` and needs Docker (`docker compose`
v5.7.0 is installed; images in [Docker images](#docker-images)).

**First run and rerun.** The 49 jobs ran from 09:18 to 10:19 UTC on 2026-11-27. Seven passed every step, and S46 passed all
but the transplant, whose result stands ([Job results](#job-results)). The other 41 failed for setup reasons: 38 on offline misses
in projects outside the first resolution pass, S47 and S49 on the generated-jar check above, and S10 on both that check and a
`NoRouteToHostException` in one TestKit test. After the second resolution pass and both script fixes, all 41 were resubmitted
(`pipeline.py resubmit`, each superseding its first job; list in `$P/logs/jobs.resubmit.txt`). That second run (11:11 to 12:08
UTC) passed 36. S11 and S12 failed only on their transplant, and those results stand. S24, S30 and S32 failed for setup reasons:
the Micrometer snapshot's deprecation under `-Werror`, and an abstract test class. Five passing cases lost their per-class counts
to Gradle's hashed XML names. After the fixes ([Job results](#job-results)), eight were resubmitted at 12:18 UTC
(`$P/tmp/resubmit2.txt`, column "Third run" below).

| Case | First job | Rerun (after the second resolution pass) | Third run (12:18 UTC) | Jar projects | Landed test classes (source set) | Network |
|---|---|---|---|---|---|---|
| S01 | `20261127-091100-setup-build-spring-boot-52125-s01-at-bot` | `20261127-110819-setup-build-spring-boot-52125-s01-at-bot` | — | `:core:spring-boot-test` | `TestPropertyValuesTests` | offline |
| S02 | `20261127-091100-setup-build-spring-boot-51661-s02-at-bot` | `20261127-110819-setup-build-spring-boot-51661-s02-at-bot` | — | `:core:spring-boot` | `ValueObjectBinderTests`, `ConfigurationPropertiesTests` | offline |
| S03 | `20261127-091101-setup-build-spring-boot-50773-s03-at-bot` | `20261127-110819-setup-build-spring-boot-50773-s03-at-bot` | — | `:core:spring-boot` | `MapBinderTests` | offline |
| S04 | `20261127-091101-setup-build-spring-boot-50798-s04-at-bot` | `20261127-110819-setup-build-spring-boot-50798-s04-at-bot` | — | `:core:spring-boot` | `ValidationBindHandlerTests` | offline |
| S05 | `20261127-091101-setup-build-spring-boot-52207-s05-at-bot` | `20261127-110820-setup-build-spring-boot-52207-s05-at-bot` | — | `:core:spring-boot` | `OriginTrackedPropertiesLoaderTests` | offline |
| S06 | `20261127-091101-setup-build-spring-boot-52277-s06-at-bot` | `20261127-110820-setup-build-spring-boot-52277-s06-at-bot` | — | `:core:spring-boot` | `FileHintTests`, `StandardConfigDataLocationResolverTests` | offline |
| S07 | `20261127-091101-setup-build-spring-boot-52666-s07-at-bot` | `20261127-110820-setup-build-spring-boot-52666-s07-at-bot` | — | `:core:spring-boot` | `ConfigTreePropertySourceTests` | offline |
| S08 | `20261127-091101-setup-build-spring-boot-52904-s08-at-bot` | `20261127-110820-setup-build-spring-boot-52904-s08-at-bot` | — | `:core:spring-boot-autoconfigure` | `MessageSourceAutoConfigurationTests` | offline |
| S09 | `20261127-091101-setup-build-spring-boot-51855-s09-at-bot` | `20261127-110819-setup-build-spring-boot-51855-s09-at-bot` | — | `:core:spring-boot-properties-migrator` | `PropertiesMigrationListenerTests` | offline |
| S10 | `20261127-091101-setup-build-spring-boot-50489-s10-at-bot` | `20261127-110802-setup-build-spring-boot-50489-s10-at-bot` | — | `:build-plugin:spring-boot-gradle-plugin`, `:configuration-metadata:spring-boot-configuration-processor` | `JavaPluginActionIntegrationTests`, `DescriptionCacheTests` | online |
| S11 | `20261127-091101-setup-build-spring-boot-51867-s11-at-bot` | `20261127-110820-setup-build-spring-boot-51867-s11-at-bot` | — | `:core:spring-boot-autoconfigure` | `AutoConfigurationSorterTests` | offline |
| S12 | `20261127-091102-setup-build-spring-boot-52310-s12-at-bot` | `20261127-110821-setup-build-spring-boot-52310-s12-at-bot` | — | `:core:spring-boot` | `SpringApplicationTests` | offline |
| S13 | `20261127-091102-setup-build-spring-boot-52309-s13-at-bot` | `20261127-110821-setup-build-spring-boot-52309-s13-at-bot` | — | `:core:spring-boot` | `SpringApplicationTests` | offline |
| S14 | `20261127-091102-setup-build-spring-boot-52831-s14-at-bot` | `20261127-110821-setup-build-spring-boot-52831-s14-at-bot` | — | `:core:spring-boot-autoconfigure` | `MessageSourceAutoConfigurationTests` | offline |
| S15 | `20261127-091102-setup-build-spring-boot-50886-s15-at-bot` | `20261127-110820-setup-build-spring-boot-50886-s15-at-bot` | — | `:module:spring-boot-micrometer-metrics` | `MeterRegistryCloserTests`, `MeterRegistryPostProcessorTests`, `MetricsAutoConfigurationTests` | offline |
| S17 | `20261127-091102-setup-build-spring-boot-52251-s17-at-bot` | `20261127-110821-setup-build-spring-boot-52251-s17-at-bot` | — | `:module:spring-boot-http-converter` | `HttpMessageConvertersAutoConfigurationTests` | offline |
| S18 | `20261127-091102-setup-build-spring-boot-52304-s18-at-bot` | `20261127-110821-setup-build-spring-boot-52304-s18-at-bot` | — | `:module:spring-boot-http-converter` | `HttpMessageConvertersAutoConfigurationTests` | offline |
| S19 | `20261127-091102-setup-build-spring-boot-51173-s19-at-bot` | `20261127-110820-setup-build-spring-boot-51173-s19-at-bot` | `20261127-121807-setup-build-spring-boot-51173-s19-at-bot` | `:module:spring-boot-tomcat` | `TomcatServletWebServerFactoryCustomizerTests`, `TomcatServerPropertiesTests`, `SampleOAuth2ClientApplicationTests` | offline |
| S20 | `20261127-091102-setup-build-spring-boot-52162-s20-at-bot` | `20261127-110821-setup-build-spring-boot-52162-s20-at-bot` | — | `:module:spring-boot-jetty`, `:module:spring-boot-tomcat` | `TomcatServletWebServerFactoryTests.givenARestartedServer*`, `TomcatReactiveWebServerFactoryTests.givenARestartedServer*`, `JettyServletWebServerFactoryTests.givenARestartedServer*`, `JettyReactiveWebServerFactoryTests.givenARestartedServer*` | offline |
| S21 | `20261127-091103-setup-build-spring-boot-51410-s21-at-bot` | `20261127-110821-setup-build-spring-boot-51410-s21-at-bot` | — | `:module:spring-boot-jdbc` | `DataSourceUnwrapperTests` | offline |
| S22 | `20261127-091103-setup-build-spring-boot-50271-s22-at-bot` | `20261127-110821-setup-build-spring-boot-50271-s22-at-bot` | — | `:module:spring-boot-jdbc` | `DataSourceBuilderTests`, `DataSourceUnwrapperTests`, `LiquibaseAutoConfigurationTests` | offline |
| S23 | `20261127-091103-setup-build-spring-boot-52824-s23-at-bot` | `20261127-110822-setup-build-spring-boot-52824-s23-at-bot` | — | `:module:spring-boot-hibernate` | `HibernateJpaAutoConfigurationTests` | offline |
| S24 | `20261127-091103-setup-build-spring-boot-51725-s24-at-bot` | `20261127-110821-setup-build-spring-boot-51725-s24-at-bot` | `20261127-121807-setup-build-spring-boot-51725-s24-at-bot` | `:module:spring-boot-batch-data-mongodb` | `BatchDataMongoAutoConfigurationTests` | offline |
| S25 | `20261127-091103-setup-build-spring-boot-52190-s25-at-bot` | `20261127-110822-setup-build-spring-boot-52190-s25-at-bot` | — | `:module:spring-boot-data-redis` | `DataRedisAutoConfigurationTests` | offline |
| S26 | `20261127-091103-setup-build-spring-boot-51844-s26-at-bot` | `20261127-110822-setup-build-spring-boot-51844-s26-at-bot` | — | `:module:spring-boot-cache` | `CacheAutoConfigurationTests` | offline |
| S27 | `20261127-091103-setup-build-spring-boot-52832-s27-at-bot` | `20261127-110822-setup-build-spring-boot-52832-s27-at-bot` | — | `:core:spring-boot-docker-compose`, `:module:spring-boot-data-redis` | `DefaultConnectionPortsTests`, `DefaultRunningServiceTests` | offline |
| S28 | `20261127-091103-setup-build-spring-boot-52625-s28-at-bot` | `20261127-110822-setup-build-spring-boot-52625-s28-at-bot` | — | `:module:spring-boot-jdbc` | `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests` | offline |
| S29 | `20261127-091103-setup-build-spring-boot-51940-s29-at-bot` | `20261127-110822-setup-build-spring-boot-51940-s29-at-bot` | `20261127-121807-setup-build-spring-boot-51940-s29-at-bot` | `:module:spring-boot-amqp-rabbitmq`, `:module:spring-boot-rabbitmq` | `AmqpRabbitMqDockerComposeConnectionDetailsFactoryIntegrationTests` (dockerTest), `RabbitEnvironmentTests`, `RabbitMqDockerComposeConnectionDetailsFactoryIntegrationTests` (dockerTest), `RabbitMqStreamDockerComposeConnectionDetailsFactoryIntegrationTests` (dockerTest), `RabbitMqEnvironmentTests` | offline |
| S30 | `20261127-091104-setup-build-spring-boot-51774-s30-at-bot` | `20261127-110823-setup-build-spring-boot-51774-s30-at-bot` | `20261127-121808-setup-build-spring-boot-51774-s30-at-bot` | `:module:spring-boot-kafka` | `KafkaAutoConfigurationTests` | offline |
| S31 | `20261127-091104-setup-build-spring-boot-50296-s31-at-bot` | `20261127-110822-setup-build-spring-boot-50296-s31-at-bot` | `20261127-121808-setup-build-spring-boot-50296-s31-at-bot` | `:module:spring-boot-health` | `AvailabilityProbesHealthEndpointGroupsPostProcessorTests`, `AvailabilityProbesHealthEndpointGroupsTests`, `DelegatingAvailabilityProbesHealthEndpointGroupTests` | offline |
| S32 | `20261127-091104-setup-build-spring-boot-52321-s32-at-bot` | `20261127-110823-setup-build-spring-boot-52321-s32-at-bot` | `20261127-121808-setup-build-spring-boot-52321-s32-at-bot` | `:module:spring-boot-health` | `HealthEndpointSupportTests` (abstract; third run: its subclasses `HealthEndpointTests`, `HealthEndpointWebExtensionTests`, `ReactiveHealthEndpointWebExtensionTests`) | offline |
| S33 | `20261127-091104-setup-build-spring-boot-51470-s33-at-bot` | `20261127-110823-setup-build-spring-boot-51470-s33-at-bot` | `20261127-121808-setup-build-spring-boot-51470-s33-at-bot` | `:module:spring-boot-health`, `:module:spring-boot-webmvc` | `AdditionalHealthEndpointPathTests`, `HealthEndpointSupportTests` (abstract; third run: its subclasses `HealthEndpointTests`, `HealthEndpointWebExtensionTests`, `ReactiveHealthEndpointWebExtensionTests`), `WebMvcHealthEndpointAdditionalPathIntegrationTests`, `WebFluxHealthEndpointAdditionalPathIntegrationTests`, `JerseyHealthEndpointAdditionalPathIntegrationTests` | offline |
| S34 | `20261127-091104-setup-build-spring-boot-51937-s34-at-bot` | `20261127-110823-setup-build-spring-boot-51937-s34-at-bot` | — | `:module:spring-boot-jersey` | `JerseyEndpointIntegrationTests` | offline |
| S35 | `20261127-091104-setup-build-spring-boot-50734-s35-at-bot` | (none: this run stands) | — | `:module:spring-boot-mongodb` | `MongoHealthIndicatorTests`, `MongoReactiveHealthIndicatorTests` | offline |
| S36 | `20261127-091104-setup-build-spring-boot-50461-s36-at-bot` | `20261127-110822-setup-build-spring-boot-50461-s36-at-bot` | `20261127-121808-setup-build-spring-boot-50461-s36-at-bot` | `:module:spring-boot-micrometer-metrics`, `:module:spring-boot-micrometer-tracing-opentelemetry`, `:module:spring-boot-opentelemetry` | `OtlpMetricsExportAutoConfigurationTests`, `OtlpMetricsPropertiesConfigAdapterTests`, `OtlpMetricsPropertiesTests`, `OpenTelemetryTracingAutoConfigurationTests`, `OtlpTracingAutoConfigurationIntegrationTests`, `OpenTelemetryLoggingAutoConfigurationTests`, `OtlpLoggingAutoConfigurationIntegrationTests`, `OtlpLoggingAutoConfigurationTests` | offline |
| S37 | `20261127-091104-setup-build-spring-boot-51959-s37-at-bot` | (none: this run stands) | — | `:core:spring-boot` | `LoggingApplicationListenerWithContextPausingTests` | offline |
| S38 | `20261127-091105-setup-build-spring-boot-51156-s38-at-bot` | `20261127-110823-setup-build-spring-boot-51156-s38-at-bot` | — | `:core:spring-boot` | `AppendableByteArrayTests` | offline |
| S39 | `20261127-091105-setup-build-spring-boot-52477-s39-at-bot` | (none: this run stands) | — | `:core:spring-boot` | `JsonValueWriterTests` | offline |
| S40 | `20261127-091105-setup-build-spring-boot-52522-s40-at-bot` | (none: this run stands) | — | `:core:spring-boot` | `JsonWriterTests` | offline |
| S41 | `20261127-091105-setup-build-spring-boot-52593-s41-at-bot` | `20261127-110824-setup-build-spring-boot-52593-s41-at-bot` | — | `:buildpack:spring-boot-buildpack-platform` | `InspectedContentTests` | offline |
| S42 | `20261127-091105-setup-build-spring-boot-52285-s42-at-bot` | `20261127-110823-setup-build-spring-boot-52285-s42-at-bot` | — | `:loader:spring-boot-loader` | `NestedJarFileTests` | offline |
| S43 | `20261127-091105-setup-build-spring-boot-52280-s43-at-bot` | `20261127-110823-setup-build-spring-boot-52280-s43-at-bot` | — | `:loader:spring-boot-loader` | `JarUrlClassLoaderTests`, `UrlEncoderTests` | offline |
| S44 | `20261127-091105-setup-build-spring-boot-52244-s44-at-bot` | (none: this run stands) | — | `:loader:spring-boot-loader` | `JarUrlClassLoaderTests` | offline |
| S45 | `20261127-091105-setup-build-spring-boot-52402-s45-at-bot` | `20261127-110823-setup-build-spring-boot-52402-s45-at-bot` | — | `:loader:spring-boot-loader` | `JarUrlClassLoaderTests` | offline |
| S46 | `20261127-091105-setup-build-spring-boot-51653-s46-at-bot` | (none: this run stands) | — | `:loader:spring-boot-jarmode-tools` | `IndexedLayersTests` | offline |
| S47 | `20261127-091106-setup-build-spring-boot-52530-s47-at-bot` | `20261127-110824-setup-build-spring-boot-52530-s47-at-bot` | — | `:build-plugin:spring-boot-gradle-plugin` | `LayeredSpecTests` | offline |
| S48 | `20261127-091106-setup-build-spring-boot-51551-s48-at-bot` | (none: this run stands) | — | `:loader:spring-boot-loader-tools` | `RepackagerTests`, `WarIntegrationTests` (intTest) | online |
| S49 | `20261127-091106-setup-build-spring-boot-51372-s49-at-bot` | `20261127-110824-setup-build-spring-boot-51372-s49-at-bot` | — | `:build-plugin:spring-boot-gradle-plugin`, `:loader:spring-boot-jarmode-tools`, `:loader:spring-boot-loader-tools` | `BootJarTests`, `BootWarTests`, `ExtractCommandTests`, `IndexedJarStructureTests` | offline |
| S50 | `20261127-091106-setup-build-spring-boot-50433-s50-at-bot` | (none: this run stands) | — | `:module:spring-boot-flyway` | `NativeImageResourceProviderTests` | offline |

## Commands for a rerun by hand

```bash
source ~/.cache/in-the-loop/spring-boot-pr-links-s01-s50/scripts/env.sh
# one case's job steps (CASE in S01-S50 but S16; STEP fix | parent | transplant | dryrun | clean); builds over a minute are jobs
bash $P/scripts/case_job.sh CASE STEP
# any task in a worktree, with the Gradle its wrapper names, on JDK 25 (log $P/logs/TAG.log; JUnit summary of RESULTDIRS in $P/logs/TAG.junit.txt)
$P/scripts/gradle_case.sh $W/CASE-ROLE TAG "RESULTDIRS" --offline -x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x :buildSrc:checkFormat :core:spring-boot:test --tests 'org.springframework.boot.json.JsonWriterTests'
# a classpath of any project and configuration, offline (one path per line)
$P/scripts/gradle_case.sh $W/CASE-ROLE TAG "" --offline -x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x :buildSrc:checkFormat -I $P/scripts/resolve-all.init.gradle :PROJECT:setupWriteClasspath -PsetupCpConf=testRuntimeClasspath -PsetupCpOut=FILE
# more of a project's configurations into the cache: online once (resolve_case.sh resolves column 4 of cases.tsv), then offline
RESOLVE_PAT=ALL $P/scripts/resolve_case.sh CASE-ROLE
# ... and of every project they reach through project dependencies (what an offline build of them needs), then the offline check
$P/scripts/resolve_closure.sh CASE-ROLE; RESOLVE_ARGS=--offline RESOLVE_TAG=resolve.closure.offline $P/scripts/resolve_closure.sh CASE-ROLE
# a detached configuration of given coordinates, with their transitive dependencies (online once, then --offline)
$P/scripts/gradle_case.sh $W/CASE-ROLE TAG "" -I $P/scripts/resolve-all.init.gradle :PROJECT:setupResolveCoords -PsetupCoords=G:A:V,G:A:V -x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x :buildSrc:checkFormat
# one landed class's JUnit counts in a result folder, by <testsuite name> (Gradle 9 hashes long XML file names)
python3 -I $P/scripts/class_counts.py $W/CASE-ROLE/PROJECT-DIR/build/test-results/test org.springframework.boot.SomeTests
# S24 and S30 at either pin: add -I $P/scripts/no-werror-micrometer-metrics.init.gradle to any run that compiles :module:spring-boot-micrometer-metrics
# S16's slice route (seconds, JDK 8)
bash $P/scripts/slice_s16.sh
# a released set (':'-joined jar paths in $P/m2)
cat $P/releases/SET/classpath.txt
# more released coordinates into $P/m2 (Maven Central and repo.spring.io/milestone), then check them
$P/scripts/release_set.sh SET "BOM-G:A:V ..." "G:A:V ..."; $P/scripts/verify_releases.sh
```

`gradle_case.sh` runs under `choom -n 500` and a `timeout` of 50 minutes (`GRADLE_TIMEOUT`); wrap inline runs in
`systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0`. Two Gradle runs at once share `$P/gradle-home` fine; four at
once stalled for minutes on its cross-process locks during the first resolution pass, so the resolution ran in two lanes.

## What failed or was not done

- **S16's fix cannot be built as pinned.** Its Framework (5.0.0 snapshots of July 2017) is not served any more, and its changed
  files compile against neither 5.0.0.RC2 nor RC3 ([S16](#s16-the-2017-maven-build-and-its-slice-route)). Nothing was edited to make
  them compile. The parent is on its slice; Boot 2.0.0.M3 is the nearest release with the feature, which is not the pin.
- **Snapshot inputs are the newest builds**, not those of the pins' dates ([Snapshot dependencies](#snapshot-dependencies)); S30's
  Spring Kafka snapshot no longer resolves at all and is substituted ([S30](#s30-substitutes-spring-kafka-420-m2)).
- **Not built**: the other 16 changed modules of S27, the other seven changed smoke tests of S19, S09's changed buildSrc file
  (`DocumentConfigurationProperties`, a docs task), and the documentation builds named in the brief's sources (`spring-boot-docs`).
  Their configurations were not resolved either.
- **Not prepared**: a Redis cluster (S25.3), a Kafka broker (S30.3), a transaction-capable Mongo replica set (S24), a RabbitMQ stream
  setup (S29.3) and a native image (S50): only their images, GraalVM and the build tools are here.
- **The first run of the jobs failed for 41 of 49 cases** on gaps in this setup: the first resolution pass missed the
  dependencies' projects, and `keep()` rejected Gradle's generated API jars. Both are fixed and the 41 are rerun ([Jobs](#jobs)).
  S10's first fix run also lost one TestKit test to a `NoRouteToHostException` (network).
- **The second run left three setup faults**, now fixed and rerun:
  - S24 and S30: the served Micrometer `1.18.0-SNAPSHOT` deprecates AppOptics, so a dependency project fails under `-Werror`.
  - S32: `--tests` named an abstract class, so its tests never ran.
  The second run also reported `no-result` per class for long class names in five passing cases; they are rerun for their counts.
- **S11, S12 and S46: the landed tests do not separate the pins in this build** (they pass on the parent too). This is a
  result, not a fault, and nothing was changed to alter it.
- The pull of `postgres:17` moved the machine's tag to the current image ([Docker images](#docker-images)).
- No verifier, no claims, no examples.

## Job results

**Three runs** of the 49 jobs of [Jobs](#jobs), all on 2026-11-27, collected by the runner on its own line
(`verification/results/2026/11/27/JOB-ID/`, not merged into this one when this was written; the copies this record was made from
are in `$P/tmp/results-current/`). The step logs the table reads are `$P/logs/CASE-ROLE.test.offline.{log,junit.txt,class.txt}`
and `$P/logs/CASE-parent-landed.test.offline.*` (`.test.*` for S10 and S48, which run online).

1. **First run**, 09:18 to 10:19 UTC: 8 cases completed (S35, S37, S39, S40, S44, S46, S48, S50); 41 failed for setup reasons
   ([Jobs](#jobs)) and were resubmitted.
2. **Second run** of those 41, 11:11 to 12:08 UTC: 36 passed every step; 5 failed. **S11 and S12** failed only because their
   transplant did not fail (results, below). **S24 and S30** failed to compile a project their tests need, and **S32**'s job ran no
   test at all: setup faults, fixed and resubmitted.
3. **Third run**, queued 12:18 UTC, **pending at this revision**: S24, S30 and S32 after their fixes, and S19, S29, S31, S33 and
   S36, whose second run passed but whose per-class counts were lost (below).

Status per case, the latest finished run of each (for the eight in the third run, their second run):

| Case | Job | Status | Fix: landed classes | Parent: those that exist there | Transplant: the fix's tests on the parent |
|---|---|---|---|---|---|
| S01 | `20261127-110819-setup-build-spring-boot-52125-s01-at-bot` | passed | 21 tests, 0 failed, 0 errors | 20 tests, 0 failed, 0 errors | fails: `TestPropertyValuesTests#applyToSystemPropertiesShouldRestoreEmptySystemProperty()` |
| S02 | `20261127-110819-setup-build-spring-boot-51661-s02-at-bot` | passed | 163 tests, 0 failed, 0 errors | 157 tests, 0 failed, 0 errors | fails: `ConfigurationPropertiesTests#loadWhenDefaultValuesContainPlaceholdersShouldResolveAndConvert()`, `ConfigurationPropertiesTests#loadWhenDefaultValuesContainPlaceholdersShouldUsePlaceholderDefaults()`, `ValueObjectBinderTests#createWithDefaultValuePlaceholderResolvingToNonStringShouldConvert()` |
| S03 | `20261127-110819-setup-build-spring-boot-50773-s03-at-bot` | passed | 47 tests, 0 failed, 0 errors | 45 tests, 0 failed, 0 errors | fails: `MapBinderTests#bindToMapWhenEmptyStringShouldReturnEmptyMap()`, `MapBinderTests#nestedMapsWhenEmptyStringShouldReturnEmptyMap()` |
| S04 | `20261127-110819-setup-build-spring-boot-50798-s04-at-bot` | passed | 17 tests, 0 failed, 0 errors | 16 tests, 0 failed, 0 errors | fails: `ValidationBindHandlerTests#bindShouldValidateMapWithWildcardValue()` |
| S05 | `20261127-110820-setup-build-spring-boot-52207-s05-at-bot` | passed | 40 tests, 0 failed, 0 errors | 39 tests, 0 failed, 0 errors | fails: `OriginTrackedPropertiesLoaderTests#compareToJavaProperties()`, `OriginTrackedPropertiesLoaderTests#getPropertyWithEscapedCommentPrefixCharacter()` |
| S06 | `20261127-110820-setup-build-spring-boot-52277-s06-at-bot` | passed | 53 tests, 0 failed, 0 errors | 32 tests, 0 failed, 0 errors | fails: `FileHintTests#[1] value = "foo[a]/bar.yaml"`, `FileHintTests#[2] value = "foo[1].yaml"`, `FileHintTests#[2] value = "foo[a]/bar[.yaml]", expected = "foo[a]/bar"`, `FileHintTests#[3] value = "file:/tmp/team[a]/app[1].yaml"`, `FileHintTests#[4] value = "a[b]c[.yaml]d"`, `FileHintTests#[4] value = "foo[a]bar[b]", expected = "foo[a]bar"`, `FileHintTests#[5] value = "foo[.yaml]/"`, `FileHintTests#[7] value = "foo[a]]"`, `FileHintTests#[9] value = "foo[[x]", expected = "foo["`, `FileHintTests#shouldParseTrailingHintWhenValueContainsOtherBrackets()`, `StandardConfigDataLocationResolverTests#resolveWhenLocationContainsBracketsResolves()` |
| S07 | `20261127-110820-setup-build-spring-boot-52666-s07-at-bot` | passed | 26 tests, 0 failed, 0 errors | 25 tests, 0 failed, 0 errors | fails: `ConfigTreePropertySourceTests#getPropertyNamesWhenSourceDirectoryIsReferencedViaDotDotReturnsPropertyNames()` |
| S08 | `20261127-110820-setup-build-spring-boot-52904-s08-at-bot` | passed | 23 tests, 0 failed, 0 errors, 1 skipped | 22 tests, 0 failed, 0 errors, 1 skipped | fails: `MessageSourceAutoConfigurationTests#testMultipleMessageSourceCreatedWithIndexedBasename()` |
| S09 | `20261127-110819-setup-build-spring-boot-51855-s09-at-bot` | passed | 7 tests, 0 failed, 0 errors | 1 tests, 0 failed, 0 errors | fails: `PropertiesMigrationListenerTests#failOnErrorWithUnsupportedKeyFails()`, `PropertiesMigrationListenerTests#failOnWarningWithRenamedKeyFails()`, `PropertiesMigrationListenerTests#failOnWarningWithUnsupportedKeyFails()` |
| S10 | `20261127-110802-setup-build-spring-boot-50489-s10-at-bot` | passed | 98 tests, 0 failed, 0 errors | 87 tests, 0 failed, 0 errors | fails: `JavaPluginActionIntegrationTests#Gradle 9.0.0` ×2, `JavaPluginActionIntegrationTests#Gradle 9.7.0` ×2, `JavaPluginActionIntegrationTests#Gradle 9.7.0 --configuration-cache` ×2; does not compile (`:configuration-metadata:spring-boot-configuration-processor:compileTestJava`; first error: `DescriptionCacheTests.java`: cannot find symbol) |
| S11 | `20261127-110820-setup-build-spring-boot-51867-s11-at-bot` | failed | 23 tests, 0 failed, 0 errors | 18 tests, 0 failed, 0 errors | **does not fail** (23 tests, 0 failed, 0 errors, gradle-exit=0) |
| S12 | `20261127-110821-setup-build-spring-boot-52310-s12-at-bot` | failed | 107 tests, 0 failed, 0 errors, 2 skipped | 104 tests, 0 failed, 0 errors, 2 skipped | **does not fail** (107 tests, 0 failed, 0 errors, 2 skipped, gradle-exit=0) |
| S13 | `20261127-110821-setup-build-spring-boot-52309-s13-at-bot` | passed | 104 tests, 0 failed, 0 errors, 2 skipped | 103 tests, 0 failed, 0 errors, 2 skipped | fails: `SpringApplicationTests#shouldNotStopKeepAliveThreadIfChildContextIsClosed()` |
| S14 | `20261127-110821-setup-build-spring-boot-52831-s14-at-bot` | passed | 21 tests, 0 failed, 0 errors, 1 skipped | 20 tests, 0 failed, 0 errors, 1 skipped | fails: `MessageSourceAutoConfigurationTests#propertiesBundleIsDetectedAfterPreviousContextCouldNotLoadIt()` |
| S15 | `20261127-110820-setup-build-spring-boot-50886-s15-at-bot` | passed | 33 tests, 0 failed, 0 errors | 26 tests, 0 failed, 0 errors | does not compile (`:module:spring-boot-micrometer-metrics:compileTestJava`; first error: `MeterRegistryPostProcessorTests.java`: cannot find symbol) |
| S17 | `20261127-110821-setup-build-spring-boot-52251-s17-at-bot` | passed | 40 tests, 0 failed, 0 errors | 38 tests, 0 failed, 0 errors | fails: `HttpMessageConvertersAutoConfigurationTests#stringConvertersCustomizerHasOrderZero()`, `HttpMessageConvertersAutoConfigurationTests#stringCustomConverterWithCustomizer()` |
| S18 | `20261127-110821-setup-build-spring-boot-52304-s18-at-bot` | passed | 43 tests, 0 failed, 0 errors | 40 tests, 0 failed, 0 errors | fails: `HttpMessageConvertersAutoConfigurationTests#kotlinSerializationUsesLimitedPredicateWhenOnlyJsonbApiIsAvailable()`, `HttpMessageConvertersAutoConfigurationTests#kotlinSerializationUsesLimitedPredicateWhenOnlyJsonbIsAvailable()` |
| S19 | `20261127-110820-setup-build-spring-boot-51173-s19-at-bot` | passed | 36 tests, 0 failed, 0 errors | 34 tests, 0 failed, 0 errors | fails: `SampleOAuth2ClientApplicationTests#everythingShouldRedirectToLogin()`, `TomcatServerPropertiesTests#tomcatUseRelativeRedirectsDefaultsToTrue()`, `TomcatServerPropertiesTests#tomcatUseRelativeRedirectsMatchesDefault()`, `TomcatServletWebServerFactoryCustomizerTests#useRelativeRedirectsDefaultsToTrue()` |
| S20 | `20261127-110821-setup-build-spring-boot-52162-s20-at-bot` | passed | 4 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | fails: `JettyReactiveWebServerFactoryTests#givenARestartedServerWhenARequestRemainsInFlightThenShutDownGracefullyDoesNotInvokeCallbackUntilTheRequestCompletes()`, `JettyServletWebServerFactoryTests#givenARestartedServerWhenARequestRemainsInFlightThenShutDownGracefullyDoesNotInvokeCallbackUntilTheRequestCompletes()`, `TomcatReactiveWebServerFactoryTests#givenARestartedServerWhenARequestRemainsInFlightThenShutDownGracefullyDoesNotInvokeCallbackUntilTheRequestCompletes()`, `TomcatServletWebServerFactoryTests#givenARestartedServerWhenARequestRemainsInFlightThenShutDownGracefullyDoesNotInvokeCallbackUntilTheRequestCompletes()` |
| S21 | `20261127-110821-setup-build-spring-boot-51410-s21-at-bot` | passed | 17 tests, 0 failed, 0 errors | 15 tests, 0 failed, 0 errors | fails: `DataSourceUnwrapperTests#unwrapRootWithDelegateWrappingSelfReturningWrapper()` |
| S22 | `20261127-110821-setup-build-spring-boot-50271-s22-at-bot` | passed | 98 tests, 0 failed, 0 errors | 91 tests, 0 failed, 0 errors | fails: `LiquibaseAutoConfigurationTests#lazyConnectionDataSource()`; does not compile (`:module:spring-boot-jdbc:compileTestJava`; first error: `DataSourceUnwrapperTests.java`: cannot find symbol) |
| S23 | `20261127-110822-setup-build-spring-boot-52824-s23-at-bot` | passed | 69 tests, 0 failed, 0 errors, 3 skipped | 67 tests, 0 failed, 0 errors, 3 skipped | fails: `HibernateJpaAutoConfigurationTests#providerDisablesAutoCommitIsConfiguredWhenBuilderDataSourceHasAutoCommitDisabled()`, `HibernateJpaAutoConfigurationTests#providerDisablesAutoCommitIsNotConfiguredWhenBuilderDataSourceHasAutoCommitEnabled()` |
| S24 | `20261127-110821-setup-build-spring-boot-51725-s24-at-bot` | failed | 0 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | **does not fail** (0 tests, 0 failed, 0 errors, gradle-exit=1) |
| S25 | `20261127-110822-setup-build-spring-boot-52190-s25-at-bot` | passed | 58 tests, 0 failed, 0 errors | 56 tests, 0 failed, 0 errors | fails: `DataRedisAutoConfigurationTests#testRedisConfigurationWithClusterRefreshPeriodAndClusterConfigurationBean()`, `DataRedisAutoConfigurationTests#testRedisConfigurationWithClusterRefreshPeriodAndCustomConnectionDetails()` |
| S26 | `20261127-110822-setup-build-spring-boot-51844-s26-at-bot` | passed | 61 tests, 0 failed, 0 errors | 59 tests, 0 failed, 0 errors | fails: `CacheAutoConfigurationTests#caffeineCacheWithAsyncCacheMode()` |
| S27 | `20261127-110822-setup-build-spring-boot-52832-s27-at-bot` | passed | 21 tests, 0 failed, 0 errors | 15 tests, 0 failed, 0 errors | does not compile (`:core:spring-boot-docker-compose:compileTestJava`; first error: `DefaultRunningServiceTests.java`: cannot find symbol) |
| S28 | `20261127-110822-setup-build-spring-boot-52625-s28-at-bot` | passed | 13 tests, 0 failed, 0 errors | 6 tests, 0 failed, 0 errors | fails: `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests#[1] database = "my+db"`, `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests#[2] database = "my?db"`, `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests#[3] database = "my/db"`, `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests#[4] database = "my%db"`, `PostgresJdbcDockerComposeConnectionDetailsFactoryConnectionDetailsTests#[5] database = "my%db"` |
| S29 | `20261127-110822-setup-build-spring-boot-51940-s29-at-bot` | passed | 35 tests, 0 failed, 0 errors | 24 tests, 0 failed, 0 errors | does not compile (`:module:spring-boot-amqp-rabbitmq:compileTestJava`, `:module:spring-boot-rabbitmq:compileTestJava`; first error: `RabbitEnvironmentTests.java`: cannot find symbol) |
| S30 | `20261127-110823-setup-build-spring-boot-51774-s30-at-bot` | failed | 0 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | **does not fail** (0 tests, 0 failed, 0 errors, gradle-exit=1) |
| S31 | `20261127-110822-setup-build-spring-boot-50296-s31-at-bot` | passed | 26 tests, 0 failed, 0 errors | 20 tests, 0 failed, 0 errors | does not compile (`:module:spring-boot-health:compileTestJava`; first error: `AvailabilityProbesHealthEndpointGroupsPostProcessorTests.java`: constructor AvailabilityProbesHealthEndpointGroupsPostProcessor in class AvailabilityProbesHealthEndpointGroupsPostProcessor cannot be applied to given types;) |
| S32 | `20261127-110823-setup-build-spring-boot-52321-s32-at-bot` | failed | 0 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | **does not fail** (0 tests, 0 failed, 0 errors, gradle-exit=0) |
| S33 | `20261127-110823-setup-build-spring-boot-51470-s33-at-bot` | passed | 45 tests, 0 failed, 0 errors | 39 tests, 0 failed, 0 errors | fails: `AdditionalHealthEndpointPathTests#fromPathWithMultipleSegmentsNotStartingWithSlashShouldCreatePath()`, `AdditionalHealthEndpointPathTests#fromPathWithMultipleSegmentsShouldCreatePath()`, `AdditionalHealthEndpointPathTests#ofWithMultipleSegmentValueShouldCreatePath()`, `JerseyHealthEndpointAdditionalPathIntegrationTests#groupIsAvailableAtAdditionalPathWithMultipleSegments()`, `JerseyHealthEndpointAdditionalPathIntegrationTests#healthComponentIsAvailableWhenMultiSegmentAdditionalPathIsConfigured()`, `WebFluxHealthEndpointAdditionalPathIntegrationTests#groupIsAvailableAtAdditionalPathWithMultipleSegments()`, `WebFluxHealthEndpointAdditionalPathIntegrationTests#healthComponentIsAvailableWhenMultiSegmentAdditionalPathIsConfigured()`, `WebMvcHealthEndpointAdditionalPathIntegrationTests#groupIsAvailableAtAdditionalPathWithMultipleSegments()`, `WebMvcHealthEndpointAdditionalPathIntegrationTests#healthComponentIsAvailableWhenMultiSegmentAdditionalPathIsConfigured()` |
| S34 | `20261127-110823-setup-build-spring-boot-51937-s34-at-bot` | passed | 5 tests, 0 failed, 0 errors | 4 tests, 0 failed, 0 errors | fails: `JerseyEndpointIntegrationTests#[2] separateManagementPort = true` |
| S35 | `20261127-091104-setup-build-spring-boot-50734-s35-at-bot` | passed | 6 tests, 0 failed, 0 errors | 4 tests, 0 failed, 0 errors | fails: `MongoHealthIndicatorTests#mongoIsUp()`, `MongoReactiveHealthIndicatorTests#mongoIsUp()` |
| S36 | `20261127-110822-setup-build-spring-boot-50461-s36-at-bot` | passed | 148 tests, 0 failed, 0 errors | 126 tests, 0 failed, 0 errors | fails: `OpenTelemetryTracingAutoConfigurationTests#shouldAppendTracesPathToCommonEndpoint()`, `OpenTelemetryTracingAutoConfigurationTests#shouldMergeCommonAndSignalSpecificHeadersForTracing()`, `OtlpTracingAutoConfigurationIntegrationTests#httpSpanExporterFallsBackToCommonCompressionWhenSignalSpecificCompressionIsNotSet()`; does not compile (`:module:spring-boot-micrometer-metrics:compileTestJava`, `:module:spring-boot-opentelemetry:compileTestJava`; first error: `OtlpLoggingAutoConfigurationTests.java`: cannot find symbol) |
| S37 | `20261127-091104-setup-build-spring-boot-51959-s37-at-bot` | passed | 3 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | fails: `LoggingApplicationListenerWithContextPausingTests$ReuseContextOne#test(CapturedOutput)` |
| S38 | `20261127-110823-setup-build-spring-boot-51156-s38-at-bot` | passed | 5 tests, 0 failed, 0 errors | 4 tests, 0 failed, 0 errors | does not compile (`:core:spring-boot:compileTestJava`; first error: `AppendableByteArrayTests.java`: method toByteArray in class AppendableByteArray cannot be applied to given types;) |
| S39 | `20261127-091105-setup-build-spring-boot-52477-s39-at-bot` | passed | 36 tests, 0 failed, 0 errors, 1 skipped | 33 tests, 0 failed, 0 errors, 1 skipped | fails: `JsonValueWriterTests#writeWhenNegativeInfinity()`, `JsonValueWriterTests#writeWhenNotANumber()`, `JsonValueWriterTests#writeWhenPositiveInfinity()` |
| S40 | `20261127-091105-setup-build-spring-boot-52522-s40-at-bot` | passed | 87 tests, 0 failed, 0 errors | 86 tests, 0 failed, 0 errors | fails: `JsonWriterTests$MembersTest#usingPairsWithName()` |
| S41 | `20261127-110824-setup-build-spring-boot-52593-s41-at-bot` | passed | 10 tests, 0 failed, 0 errors | 8 tests, 0 failed, 0 errors | fails: `InspectedContentTests#ofWritingRangeShouldWork()`, `InspectedContentTests#ofWritingRangesThatExceedMemoryLimitShouldWork()` |
| S42 | `20261127-110823-setup-build-spring-boot-52285-s42-at-bot` | passed | 36 tests, 0 failed, 0 errors | 34 tests, 0 failed, 0 errors | fails: `NestedJarFileTests#readAllBytesAfterReadingStoredContentReturnsRemainingContent()` |
| S43 | `20261127-110823-setup-build-spring-boot-52280-s43-at-bot` | passed | 20 tests, 0 failed, 0 errors | 17 tests, 0 failed, 0 errors | fails: `JarUrlClassLoaderTests#resolveFromNestedWhenNameNeedsEncoding()`, `UrlEncoderTests#encodeWhenHasSingleByteEncodedCharacters()` |
| S44 | `20261127-091105-setup-build-spring-boot-52244-s44-at-bot` | passed | 8 tests, 0 failed, 0 errors | 7 tests, 0 failed, 0 errors | fails: `JarUrlClassLoaderTests#loadClassFromNestedWhenJarHasNoDirectoryEntriesDefinesPackageFromManifest()` |
| S45 | `20261127-110823-setup-build-spring-boot-52402-s45-at-bot` | passed | 16 tests, 0 failed, 0 errors | 14 tests, 0 failed, 0 errors | fails: `JarUrlClassLoaderTests#resolveRootPathFromNested()`, `JarUrlClassLoaderTests#resolveRootResourcesFromNested()` |
| S46 | `20261127-091105-setup-build-spring-boot-51653-s46-at-bot` | failed | 9 tests, 0 failed, 0 errors | 8 tests, 0 failed, 0 errors | **does not fail** (9 tests, 0 failed, 0 errors, gradle-exit=0) |
| S47 | `20261127-110824-setup-build-spring-boot-52530-s47-at-bot` | passed | 4 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | fails: `LayeredSpecTests#excludeExcludesApplicationContent()`, `LayeredSpecTests#excludeExcludesDependencies()`, `LayeredSpecTests#includeAndExcludeSelectApplicationContent()`, `LayeredSpecTests#includeAndExcludeSelectDependencies()` |
| S48 | `20261127-091106-setup-build-spring-boot-51551-s48-at-bot` | passed | 81 tests, 0 failed, 0 errors | 78 tests, 0 failed, 0 errors | fails: `RepackagerTests#sbomManifestEntriesAreWrittenForWar()`, `WarIntegrationTests#apache-maven-3.6.3`, `WarIntegrationTests#apache-maven-3.9.13` |
| S49 | `20261127-110824-setup-build-spring-boot-51372-s49-at-bot` | passed | 127 tests, 0 failed, 0 errors | 114 tests, 0 failed, 0 errors | fails: `BootWarTests#basicArchiveCreation()`; does not compile (`:loader:spring-boot-jarmode-tools:compileTestJava`; first error: `IndexedJarStructureTests.java`: cannot find symbol) |
| S50 | `20261127-091106-setup-build-spring-boot-50433-s50-at-bot` | passed | 1 tests, 0 failed, 0 errors | 0 tests, 0 failed, 0 errors | fails: `NativeImageResourceProviderTests#nativeImageResourceProviderShouldReadNestedMigrations()` |

A **passed** job means the landed tests pass at the fix, the parent's versions pass at the parent, and the fix's tests fail on a
copy of the parent in the methods named, or do not compile there (the task and the first error are given). A parent count of 0
means the landed classes or methods are new (S20, S37, S47, S50).

**43 cases are complete** (7 from the first run, 36 from the second); S19, S29, S31, S33 and S36 among them are rerun only for
their per-class counts, and their verdicts stand.

**Three cases whose transplant does not fail.** These are results of the build, not setup faults, and were not rerun:

- **S46**: the fix's `IndexedLayersTests` (9 tests) pass on the parent. The PR is a lookup optimisation whose landed test repeats
  identical candidates; passing on the parent is consistent with the brief's account.
- **S11**: the fix's `AutoConfigurationSorterTests` (23 tests; the parent's own version has 18) pass on the parent. The PR is a sorting optimisation,
  and every claim of the brief for S11 expects the same result on both revisions.
- **S12**: the fix's `SpringApplicationTests` (107 tests, 2 skipped) pass on the parent, including the three landed tests
  `runnersAreCalledOnceWhenContextIsRefreshed`, `runnersAreNotCalledWhenContextIsClosedImmediatelyAfterRefresh` and
  `runnersAreNotCalledWhenContextIsClosedWhileHandlingApplicationStartedEvent`. These are the tests whose parent failures the
  brief cites from the PR. The tests ran on the parent's own `SpringApplication` (a `git archive` of the parent with only the test
  file replaced). One known difference from the PR author's run: the pins import Spring Framework `7.0.10-SNAPSHOT`, and that
  snapshot is today's build ([Snapshot dependencies](#snapshot-dependencies)). This setup did not look further.

**Three setup faults, fixed for the third run:**

- **S24 and S30**: both pins import Micrometer `1.18.0-SNAPSHOT`, and the only build of it still served deprecates the AppOptics
  registry (`io.micrometer.appoptics.AppOpticsMeterRegistry`, `AppOpticsConfig`). Boot compiles with `-Werror -Xlint:deprecation`,
  so `:module:spring-boot-micrometer-metrics:compileJava`, which both cases' tests need, failed at both pins with `warnings found
  and -Werror specified` and no other error. The other cases on that snapshot (S29, S42, S43, S49) do not compile that project.
  `$P/scripts/no-werror-micrometer-metrics.init.gradle` removes `-Werror` from that one project's Java compile tasks.
  `case_job.sh` adds it for S24 and S30, and it prints the remaining arguments in the log. `-Werror` only turns warnings into a
  failure: the class files are the same, and the warnings stay in the log.
- **S32**: its landed class `HealthEndpointSupportTests` is abstract (the PR's shared fixture). A `--tests` filter on an abstract
  class matches nothing, so the fix and the parent "passed" with 0 tests. The third run names the three concrete subclasses that
  run its tests (`HealthEndpointTests`, `HealthEndpointWebExtensionTests`, `ReactiveHealthEndpointWebExtensionTests`, all present
  at both pins), and the transplant still takes the fix's changed `HealthEndpointSupportTests.java`. S33 names the same abstract
  class beside its other four, so its third run adds the subclasses as well. No other landed class in `cases.tsv` is abstract.

**Per-class counts.** `CASE-ROLE.test*.class.txt` should give each landed class's own JUnit counts. In the second run it reported
`no-result` for classes that did run. Gradle 9 writes `TEST-CLASS.xml` only while that name fits 120 bytes
(`org.gradle.internal.SafeFileLocationUtils`), and it shortens longer names with a hash; the lookup was by file name. The step
totals and the pass and fail verdicts were not affected: they count every XML file, and for S31, for example, the total of 26 is
exactly the three classes' 9 + 14 + 3 tests. `$P/scripts/class_counts.py` now finds each class by the XML's `<testsuite name>`.
S28 and S37 have one landed class each, so their totals are the class's counts (S28: 13 at the fix, 6 at the parent; S37: 3 at the
fix, absent at the parent). Their `class.txt` files still say `no-result` (S37's is from the first run's earlier bug) and were not
rerun.

**Digests of the built artifacts** for the 41 cases that are final (sha256 in full; `$P/artifacts/CASE-ROLE/SHA256SUMS` has every
jar on the classpaths and each nested class). Each row gives the case's jars and the top-level classes compiled from each
production source the landing changed (fix), with the parent's digests of the same classes in the same order (`(absent)`: the
class is new at the fix). S37 and S40 have the same top-level class digest at both pins; their changes are in nested classes:

- S37: `LoggingApplicationListener$Lifecycle.class`, fix `063d900d6a62f5004c344f087f6f3b621f6e6619daecf1df78cef16bb1853800`,
  parent `d9ce29568a5bf327dcf09711e5b8b7191c28170acb28a1f83d8b197557cc8aa8`.
- S40: seven nested classes of `JsonWriter`, among them `JsonWriter$Member.class`, fix
  `503542587b00fad13319bf131f51a9b5c822ef22aa07c1ba0d163a4454e67379`, parent `f435b2c5864d4ab66e258ac0a68b570d55969c76395324ccfa6e745b029aa679`.

The other eight cases' digests come with the third run.

| Case | Role | Jar (sha256) | Changed classes (sha256) |
|---|---|---|---|
| S01 | fix | `spring-boot-test-4.0.9-SNAPSHOT.jar` `e79ab518b957878312752fc2c2e2b55da146b0e7051127412e2f01fef82a974e` | `TestPropertyValues.class` `09ace1438755879de3fca560e55a14e939f9501c5353cf4d22dbe93d5a1a89a4` (+3 nested) |
| S01 | parent | `spring-boot-test-4.0.9-SNAPSHOT.jar` `d2e917c2f291687b210e4fbd6a20c2517966a4ea9c5860c97d9b0210dae4c60d` | `09ace1438755879de3fca560e55a14e939f9501c5353cf4d22dbe93d5a1a89a4` (same order) |
| S02 | fix | `spring-boot-4.2.0-SNAPSHOT.jar` `49dcb19167e3fc3afbba246f5ed86f79cf813f0ff01309fd8fe947eeb67ba936` | `DefaultValue.class` `4ace1ad78fd398dd3672a80472db983f97a4b271dba9fa8cf6351b3926ef156e`, `ValueObjectBinder.class` `8bddd06d025b635323b56524974ea5cc16173aede865f461b833a67d271e0a5d` (+6 nested) |
| S02 | parent | `spring-boot-4.2.0-SNAPSHOT.jar` `4ec3cb0a2f098da14eaec38687cd90cccf289019015eae24510eeae2b7bd27ba` | `4ace1ad78fd398dd3672a80472db983f97a4b271dba9fa8cf6351b3926ef156e`, `823c94cf914f757a15c3da77c3886e5ef69a92d88295a113f01a8c6d87a56eef` (same order) |
| S03 | fix | `spring-boot-4.1.1-SNAPSHOT.jar` `35efd24550a31a66213321c493b91a885c92b56b3ef5b00ba437e0dc18bc1c36` | `MapBinder.class` `f49f6a234a7710c63c54f89407713b22ac615f25c6d2cb1b752e50e76de850d4` (+1 nested) |
| S03 | parent | `spring-boot-4.1.1-SNAPSHOT.jar` `b3d2713ade2a50accb3fffaa54ce5a8869bf0ea9224fbaa9c4f6ddcede6dffdf` | `ba8302f753e8cfe0b26ea839090f2bc19b0893ac43944c74b0424ad852c0952b` (same order) |
| S04 | fix | `spring-boot-4.0.8-SNAPSHOT.jar` `0e110526273a0485ba90ee90b00a0ef0abdf316ba1f475afc2cfa69cf6fd660e` | `ValidationBindHandler.class` `cead9c00c77d2c099c5fe5e89660a57c1e2d91e6f50b97792c2710e15c242938` (+1 nested) |
| S04 | parent | `spring-boot-4.0.8-SNAPSHOT.jar` `96867950a33284521a16435e5becb25b1ea37ac90b4eb3d1a283c809113e367b` | `382affd4278dbdfe91f13c65eed7d8d327f3cf85caf0316b352d024c875ccce2` (same order) |
| S05 | fix | `spring-boot-4.0.9-SNAPSHOT.jar` `e1ac163d9fcf3c604dc532026b03d5adf8f48ba28873701f906945b50c13108a` | `OriginTrackedPropertiesLoader.class` `f4503250b4797447dcb3b87df189c52d496fa37910f9c3d22f280a0a395c761f` (+2 nested) |
| S05 | parent | `spring-boot-4.0.9-SNAPSHOT.jar` `5a46f304aa9d5a5e24934583b1656d3be3573e90d0884a98536f88664228e0a6` | `f4503250b4797447dcb3b87df189c52d496fa37910f9c3d22f280a0a395c761f` (same order) |
| S06 | fix | `spring-boot-4.1.3-SNAPSHOT.jar` `d12aa41d068e91352992f44583af4a08db5f982b0927aa43a8c02c9c800ccaad` | `FileHint.class` `ab4b23479d7141c48b1d9e8bf486ae6b78b50939f610ae7a151f9e4a0fe35075` |
| S06 | parent | `spring-boot-4.1.3-SNAPSHOT.jar` `ac1ac86049c3be27a6eb04bfe34a1502c5c998a7e1c300a1e14165fc4c6c8b64` | `5ea2ee9adafe3c9781899ca074c545123178e1c1ae40b9d39d8ed8a04ea603da` (same order) |
| S07 | fix | `spring-boot-4.0.10-SNAPSHOT.jar` `22d12d73dfc086e418a5f4d9b5a8efe1ed28f01d8800434845f8365a0efa54ef` | `ConfigTreePropertySource.class` `2d4a377838b70c1b346c534f644c7061f3332a1713a39edee14f3b4044581087` (+4 nested) |
| S07 | parent | `spring-boot-4.0.10-SNAPSHOT.jar` `519d5271e5da50b23adfd880896e3b25077df6dc83ec41042637e4c2a1615fad` | `346f93ebfcda6e0572403d945909efb33db4127b2bfa4ccc3d62d27635f9ed46` (same order) |
| S08 | fix | `spring-boot-autoconfigure-4.0.11-SNAPSHOT.jar` `16938e4391a3e66bf989786aa98661984a3bfa396d60aad98b3717bcd40795d1` | `MessageSourceAutoConfiguration.class` `d7751b66b35a3643d98b87561a8beecdbd818d3d0b999bf49b579e94af82a363` (+3 nested) |
| S08 | parent | `spring-boot-autoconfigure-4.0.11-SNAPSHOT.jar` `1ed144a23455f3680f2085988edcf630a4c80d7b943a9cb1513b3d4227d05168` | `2d0c6727fe477547484642eeae0c0b20daf6d1271070ff04d15347648b4189c4` (same order) |
| S09 | fix | `spring-boot-properties-migrator-4.2.0-SNAPSHOT.jar` `1e9d937038cf142f779f436213b7dea54f4b46c3877d6a7d9d73de09f8dc3045` | `PropertiesMigrationListener.class` `7e71e02f0bf45f2af9a6bb401bd9b4578e96768b4fde6703ebbd6eabae66493a` (+1 nested) |
| S09 | parent | `spring-boot-properties-migrator-4.2.0-SNAPSHOT.jar` `fbd2f3b24d2716d1e092667318bcbe5f523de505dc498b011f615a8489b2f15b` | `a277ce74777a4fbd20fafccc234e41e5846a91f1058bc34e09bbf7f0aded3308` (same order) |
| S10 | fix | `spring-boot-configuration-processor-4.0.9-SNAPSHOT.jar` `48c6cd37b11e23664181b9051de2a6b3d4266ef21007033aefd519dd4619cef5`, `spring-boot-gradle-plugin-4.0.9-SNAPSHOT.jar` `79e1b6bfc1145d097c2f6fe15b84e244bcc8ff2595c685158871f3f1dc8cc2d3` | `spring-boot-configuration-processor ConfigurationMetadataAnnotationProcessor.class` `d80a951193508f43579ae7ceaecb1a5f2f8da0ee9efda17d1e13c2ed743a0241`, `spring-boot-configuration-processor DescriptionCache.class` `98771c7f072e5479a12c3e2234ef76ec0822ef4d11d837db7f8b9353c9dfec2e`, `spring-boot-configuration-processor MetadataGenerationEnvironment.class` `7f597a5d94af1078e96487c26fae032fc49929dfb974e5c335d54f3926badf7b`, `spring-boot-configuration-processor FieldValuesParser.class` `d814a0550f5a2635195cb6f384e383cbac0772d899e5311c32c4777226524053` (+1 nested), `spring-boot-configuration-processor JavaCompilerFieldValuesParser.class` `ff7bbd26b05a44ea8c6e25530222f578257a7c79ba5dd07a3e55bfb4eb4b1b53` (+1 nested), `spring-boot-gradle-plugin JavaPluginAction.class` `9656815268331987e5fc14d65bf52fed5f5a19507954d1c8fd081ce47f37f36a` (+1 nested) |
| S10 | parent | `spring-boot-configuration-processor-4.0.9-SNAPSHOT.jar` `bb181d6418208516fa9b0ede51410942bb3c96132d7568bf0b7ce6ff3a137a76`, `spring-boot-gradle-plugin-4.0.9-SNAPSHOT.jar` `b937fad8c95a9cc17f88205e14516b6c99ab5bd7edbb6b09fe79473cd43c1ffe` | `c50702ccea62b9412d1fe318392ef05fc761c41cce470a943661ffe0a3d2fa65`, (absent), `b383b6be04761bb0071b55dad0a54cd3a6fee96548e2b33a2be7d9bc5455c8ff`, `42ff079909a4b6e4fb13acc24080b95a87a5486f90b5595ef100d7ca01adb248`, `d9516e0229aa9b3f9df793e35c3691f29254a3692ae66fc3fa2818c63cc40165`, `4b0c04d35faf7819af7ac3883a572eaf34fea1f8546d6a563c9a00a08181fbaf` (same order) |
| S11 | fix | `spring-boot-autoconfigure-4.2.0-SNAPSHOT.jar` `5ea05160c059a44a683954ebc904933a20433c79d8967e0828dbe1fad4ba43c5` | `AutoConfigurationSorter.class` `f190efd3a4ee29f510f5cff586a03ec4297bd95a4552eb441ba2b3e66179ea68` (+2 nested) |
| S11 | parent | `spring-boot-autoconfigure-4.2.0-SNAPSHOT.jar` `d068765653fface12faa91dcd9ffedd5a0d16047b5d944ebfd84f51c661dcdfd` | `7770c07578a8c2caac41eae42177b76e8339e17091c01a065961edd92767a31a` (same order) |
| S12 | fix | `spring-boot-4.0.10-SNAPSHOT.jar` `a86c700b31df5810f760fabf4330d6a3eae67457ebe54f0266fb78775ccdc9b5` | `SpringApplication.class` `cc5a15990668abfb14f053953c65b2feb6e570aa71342b5cb55b08448ebdc52b` (+12 nested), `SpringApplicationRunListeners.class` `bcb1feecef3f58f83873071c506b3d4c658ba053a4b67508b12fa93f30b7bd76` |
| S12 | parent | `spring-boot-4.0.10-SNAPSHOT.jar` `99dc776393a774199604a6c9e9e19aee915f7bb2c96da76d62004fb068b2f83e` | `5d5088d40368fce7c16eada15c8bf199366d2fcf3bade0138c6e505e2fca7d89`, `ca5820e2ace96ad45a3349b898c3cf1fc65a73572c09921cf39ab58cd48c7520` (same order) |
| S13 | fix | `spring-boot-4.0.10-SNAPSHOT.jar` `d5d6e6e357b9ca63f26152b880fe5bafff04224876831a9b142bb8d503846cf6` | `SpringApplication.class` `5d5088d40368fce7c16eada15c8bf199366d2fcf3bade0138c6e505e2fca7d89` (+12 nested) |
| S13 | parent | `spring-boot-4.0.10-SNAPSHOT.jar` `afce47c45984ddd9b7c7629ca292d73710d56fc2e44437352503676d7ceb2fb2` | `1605c4096ee2a929c44199657df13bfa977105698b19feead6f2882728bc709a` (same order) |
| S14 | fix | `spring-boot-autoconfigure-4.0.11-SNAPSHOT.jar` `0e95b45f54c2d46e9dce6f42a85382184cc7786f03fcb4910af8d587abeba6da` | `MessageSourceAutoConfiguration.class` `2d0c6727fe477547484642eeae0c0b20daf6d1271070ff04d15347648b4189c4` (+3 nested) |
| S14 | parent | `spring-boot-autoconfigure-4.0.11-SNAPSHOT.jar` `1c7a5f8ae6d7186011815ef4f139a936e24cd42b3a25465469458e0dee6edcf9` | `0879fd74a31034fa4a2a9d5c8ecc94548667f8109699ea2b6bf00a1c11a28069` (same order) |
| S15 | fix | `spring-boot-micrometer-metrics-4.0.8-SNAPSHOT.jar` `e55c521a9bd878f34e9d664279f50526203cbf14ace729990750b7e37646154d` | `MeterRegistryCloser.class` `84ae8bee5477a2066ad42c4dcd69f1d3fca36fd738fd50f73279098a6e06f9ff`, `MeterRegistryPostProcessor.class` `dd736cf01d35e2e3cf5a3a02a1bdf146fac13a3886721ee25f598f4a3c113841` (+1 nested), `MetricsAutoConfiguration.class` `262f634a604136ccf428703e7e09f8f20cfb4b3562c69604aec9b86b28abfffc` |
| S15 | parent | `spring-boot-micrometer-metrics-4.0.8-SNAPSHOT.jar` `d9fde5aa9e4d5d0667fc70460d935b948d59d457d2fbe07d1ec1058c7ffc03e2` | (absent), `dac4c4ce8130ba105fd00167d42626915c934644613dc2f09d8b87a9698b95be`, `a557ccc16f1742bdcd03916a557730e2e33ab223fb0f0b90accbde0e0ba3cb4a` (same order) |
| S17 | fix | `spring-boot-http-converter-4.0.10-SNAPSHOT.jar` `e82d397be044b1c03d5f0c384b70a17973703c2cfa1d4d3d0ca7187c457882a1` | `HttpMessageConvertersAutoConfiguration.class` `b8182d82f4cf517a499a832f2fba4212e8f06e585f9fda51bb950397aae78630` (+4 nested) |
| S17 | parent | `spring-boot-http-converter-4.0.10-SNAPSHOT.jar` `1b53fe6cd434ff27db0dab0ef38ce3d1a3ded32800e11e15a90ceefb3b5d2d9b` | `b8182d82f4cf517a499a832f2fba4212e8f06e585f9fda51bb950397aae78630` (same order) |
| S18 | fix | `spring-boot-http-converter-4.0.10-SNAPSHOT.jar` `67dd4371841ed3dd8c7864a538f9f1099d158729052fe18921e586c88470bcea` | `KotlinSerializationHttpMessageConvertersConfiguration.class` `a7de43bfee1559545dd4fa89c2bed816aac30ca2e9a415f95ecd6786a6eb8b80` (+1 nested) |
| S18 | parent | `spring-boot-http-converter-4.0.10-SNAPSHOT.jar` `e82d397be044b1c03d5f0c384b70a17973703c2cfa1d4d3d0ca7187c457882a1` | `a7de43bfee1559545dd4fa89c2bed816aac30ca2e9a415f95ecd6786a6eb8b80` (same order) |
| S20 | fix | `spring-boot-jetty-4.0.10-SNAPSHOT.jar` `8ab09a2fd46fa0e14c65e52c9250bfbddd3101a536253f0b98ff344196410c71`, `spring-boot-tomcat-4.0.10-SNAPSHOT.jar` `6b3e986499dc331ca74b453feb6177dc9d17c35c0af76d92993013ec2c765fbf` | `spring-boot-jetty GracefulShutdown.class` `2e696c203ca0d556916607c8f2714c1cdf9d0e943a0cd420e53110fa13b78912`, `spring-boot-jetty JettyWebServer.class` `ef0677e5898aca5f580ee06039427ea8debf922ddca38ab39bf436e7c61da756`, `spring-boot-tomcat GracefulShutdown.class` `bb27587f09aec8fdbf3780523d60ce6c419ee09afbf442ad1689de38d5a7019c`, `spring-boot-tomcat TomcatWebServer.class` `95707faf071a7a66ce99380c068e34ad54ccf1a15fa0c261f496e3fbc95fb896` (+1 nested) |
| S20 | parent | `spring-boot-jetty-4.0.10-SNAPSHOT.jar` `3563cdc81b9f9a1ef493d08faafe956aae31f6ffc6a451949118fa788c6fe3a7`, `spring-boot-tomcat-4.0.10-SNAPSHOT.jar` `944dc742324eddfd7fcec1ba91bd09b4680c7856975c7dcfd40ca66dced6c79a` | `a4f007b64467ebd4f2d7fdc17760b67e70c1a76d9e6ef63a95cc7efebdcb0b8e`, `80c23d89f7b4d84d9fe7ed6c81be4d624fd7d363f1003a0d06f040351e7b2f64`, `4d0b62206bf5a099a8fe11a5523d55e6fc2704d9632176749a033a221708e3bf`, `c45a1dbde9c9d6645ec7bcedc0c4f4712b4d3f1013868274e6f98528248f2298` (same order) |
| S21 | fix | `spring-boot-jdbc-4.1.2-SNAPSHOT.jar` `e0e2e55d763b7e63a47bcfa03ad30c5a7acaf05419d55d0a2132b225ad4d4868` | `DataSourceUnwrapper.class` `34615163c439903272c827e7fbb4201509560576f87f26499f0069d73b8020fb` (+1 nested) |
| S21 | parent | `spring-boot-jdbc-4.1.2-SNAPSHOT.jar` `01eda88c7a0b68b1266c0e48c3842ff12e7e17586378115cd0ccf8141a1fe895` | `665e332e4b5b2583cbddcc79851eebcc04ff144e1459d0c123c6ca1b52f5885f` (same order) |
| S22 | fix | `spring-boot-jdbc-4.1.0-SNAPSHOT.jar` `d84d0b6ba77896feb4e2cfa0a6b91290701820fdf066823d145f90c2a31fa7f0` | `DataSourceBuilder.class` `581c71ac69d6c1b4083536ce9d2c4e311b1736f0032fb859fca3a1427223a347` (+17 nested), `DataSourceUnwrapper.class` `665e332e4b5b2583cbddcc79851eebcc04ff144e1459d0c123c6ca1b52f5885f` (+1 nested) |
| S22 | parent | `spring-boot-jdbc-4.1.0-SNAPSHOT.jar` `7c6c0083608fa959926e14c30d60eb520987d102bf11f9c50af9539624cab110` | `17525efe25f1fa6453ac3eec2c88922d113a7196b84721789479749337ceee8f`, `36a6a04272697a269c151f8412995c723374af808d26ccf176da857278d6ed43` (same order) |
| S23 | fix | `spring-boot-hibernate-4.0.11-SNAPSHOT.jar` `2b3f97cefbe26bcca8a28682a75b22cf2a150d8635946011f5245aa13debb70d` | `HibernateJpaConfiguration.class` `14d40b9902219f231e84c0e65de43e1f1797cb4965323670ea5f602ef5ab52a9` (+2 nested) |
| S23 | parent | `spring-boot-hibernate-4.0.11-SNAPSHOT.jar` `c05291cb2f8703f6535c5bf7ab3fce0d482688ca7c763713b009a48aaf6e68ab` | `c9428dd563bff28ed59d236fac675480e6bbdff8df0bf8d2fce945310bbfa0ae` (same order) |
| S25 | fix | `spring-boot-data-redis-4.0.10-SNAPSHOT.jar` `1f112a1e41ad3b5b4e0ea4d1f5b65963a4a8b3b27cdc59e90071991bc76eefbc` | `LettuceConnectionConfiguration.class` `30080fea4c622586ed32f291c4f930736852ae9a815225dea3a8cb9435228cbe` (+2 nested) |
| S25 | parent | `spring-boot-data-redis-4.0.10-SNAPSHOT.jar` `e05734526a34f2c69f305a5fdd43c407175c3c09edbee2a198ddf1f96f9a99bf` | `b48f2638d59e28b61ef7eb14691d80900ff2ccc6daa2d5fd77e5c11f3839ef74` (same order) |
| S26 | fix | `spring-boot-cache-4.2.0-SNAPSHOT.jar` `dc9e1253f1fce4f3dde3ea01d4c79aeb1f86a3700653c35dad5be583965476dc` | `CacheProperties.class` `a05b2ac73073602c5542ba46c0738624ba38b37bab963ae2061e0bab0855ffd0` (+6 nested), `CaffeineCacheConfiguration.class` `2194f40c8974118770fbda64e8473912c990344903f877f32eeb44e404305e58` |
| S26 | parent | `spring-boot-cache-4.2.0-SNAPSHOT.jar` `279e94fc008e34c5995aca0c9eac046eebd05db02b57edf3fb3e28939a8c1758` | `7937963e43a56d0bb4c599d805c65a921dc66f81402d8e93ff39b37c4adbd167`, `24a4af0b48a9175a8a6f972e866a8bf1ceef1891e4bfa9e6fef075011f26fdbd` (same order) |
| S27 | fix | `spring-boot-data-redis-4.0.11-SNAPSHOT.jar` `c7fb8dc9e4c3c133a4a0fa1f0c495ef59597813eef8e8cf205c241caa5407f83`, `spring-boot-docker-compose-4.0.11-SNAPSHOT.jar` `054812b7f6de9e2e8f6ee4e89dc417924cbb500dca159fe71b398e7fbfbcbc75` | `spring-boot-data-redis RedisDockerComposeConnectionDetailsFactory.class` `6bef861cb104dd8ade26230358a64b892d262173457ff2c3f808f6c3e6fe65f3` (+1 nested), `spring-boot-docker-compose ConnectionPorts.class` `0e295219adc45c6247a6ea7a5439058fed63b92aab32645a0db8968eabd40544`, `spring-boot-docker-compose DefaultConnectionPorts.class` `810baee2c73051c5d889e94286e3f3ed3dbb22fe1337f99dfd607c042a4d3fe8` (+1 nested) |
| S27 | parent | `spring-boot-data-redis-4.0.11-SNAPSHOT.jar` `765952e2bc3b21333b2e3f0ca54a2c84619643957a12dd46576f1d5bdb7f91f0`, `spring-boot-docker-compose-4.0.11-SNAPSHOT.jar` `ec3417692a87d470cee6c222c3df1caa9eb1729bf02e24b56f0c3233b24079d5` | `6bef861cb104dd8ade26230358a64b892d262173457ff2c3f808f6c3e6fe65f3`, `6fcab3d78317c52dbad38ac9e4bf85aa9abc5cf30373c18d6183326bb3b50565`, `62fbc308c8ba1cfea90a534b6d6dc5dc89cc77192aab794f8738102b51a86e45` (same order) |
| S28 | fix | `spring-boot-jdbc-4.0.10-SNAPSHOT.jar` `f855f8c64cea74787c6a5dc74f754b575b1cbba9975e946a4737d646349eaf51` | `PostgresJdbcDockerComposeConnectionDetailsFactory.class` `4a74db2829ac685f425988cb568d6d4998551fd7e9570c80fc5c47f4dc92986a` (+1 nested) |
| S28 | parent | `spring-boot-jdbc-4.0.10-SNAPSHOT.jar` `736e43c5f70c1dee9c3d4f570ee6877f26412f5cd393e158e811ae46d8997224` | `5460209d53d2ade1666a5e44061fc75fdbe99dca6f47dfe5de76447f2966b5a3` (same order) |
| S34 | fix | `spring-boot-jersey-4.0.9-SNAPSHOT.jar` `2809d47028f7ebbe3c72234d2184360d1dd4544ec5b1e8295b4f083dc4e37f8b` | `JerseyWebEndpointManagementContextConfiguration.class` `0dfcf01793e0e771eff9a694ac88d30955d65e62b206a40d9d24404038173559` (+4 nested) |
| S34 | parent | `spring-boot-jersey-4.0.9-SNAPSHOT.jar` `cc213865389c18c427b861dcf399f6a5152ec1158bf91c3b62dedac96e5098bf` | `1d2000c37a5e33d095b96d0f955a87a4bf6df02cf5200c41263be46f7611ac75` (same order) |
| S35 | fix | `spring-boot-mongodb-4.0.8-SNAPSHOT.jar` `764ec81d6bc96891d232919d6a3333f00072597f4eb92bb23e3b5706edf017b8` | `MongoHealthIndicator.class` `c512839f6eb2a0ddc511cf2f4f9751bd0af2eea433fe0c001885e2b4e18a3289`, `MongoReactiveHealthIndicator.class` `c645847af61a2414be263f988ed42949bdbea759a3b11ab59a4b5cb9b844913d` |
| S35 | parent | `spring-boot-mongodb-4.0.8-SNAPSHOT.jar` `3880ce589013b433dc3864fca1875100d2b04446e6f202c466e0df8f208a5f23` | `ad31580f174e48afeaa6688834f2eb7cb32ac580f930b855782995f1095ae051`, `c0d541fb2656c377a5d7c972f1dc99f59fd514cffc81462be390e6d6eb91b5c5` (same order) |
| S37 | fix | `spring-boot-4.0.9-SNAPSHOT.jar` `f0e7a89aeb6752d30f4beb5056b32f1ff5734672e63f07c30fde8588be25840d` | `LoggingApplicationListener.class` `32af430d5978fc5364a8987663f70039370fdcb3964a118713371d0c3051671b` (+1 nested) |
| S37 | parent | `spring-boot-4.0.9-SNAPSHOT.jar` `661058a4662116adf7c26df2d0e4e0af6f42ca9998c399d65f9f298b9fc138ff` | `32af430d5978fc5364a8987663f70039370fdcb3964a118713371d0c3051671b` (same order) |
| S38 | fix | `spring-boot-4.1.1-SNAPSHOT.jar` `c11970f4170e8a4ada64035a438c92f2e92b7d1cc4a74cfeebc22235c335cd8a` | `AppendableByteArray.class` `fec4defbe6b07608fa19f6e99cb128fffeb6b2b2aee3bcc729c4661c3055db2f`, `WritableJson.class` `d1778c7ce8b15acbc6a75362ef37642b93961d25f18ab00d15529b071dff0d66` (+1 nested) |
| S38 | parent | `spring-boot-4.1.1-SNAPSHOT.jar` `c969ba334a3db0ee7fbd136e557500a87cfb00df575a0a7bb26fe2322ebe559b` | `06216e1fe93f9a81c2c2c301db5736409255dfa02984787971b152c32bf6f6ec`, `281db625ad75f38faef3ae3fb548c9cbd2b646f299831c12bab23177660cce21` (same order) |
| S39 | fix | `spring-boot-4.0.10-SNAPSHOT.jar` `2eba7265a56b1b763769db70ccd31e65cf5aa0b7d3217565443445291f0715b2` | `JsonValueWriter.class` `d235fdca6511d20cb656e82effd54124c88a28238ae53ada3689339dd7c5b1d7` (+2 nested) |
| S39 | parent | `spring-boot-4.0.10-SNAPSHOT.jar` `e60c1ce9cec8d0908b3d20da870ae387d3266234cf7301d4deb0a6b307c42e45` | `9f7e269ad625e7dfd10cba7af2403ffb904a2276c5cc61d9c773b77c44a26eff` (same order) |
| S40 | fix | `spring-boot-4.0.10-SNAPSHOT.jar` `3cbbffb2548b25e59ef5fef33ea7a3e033bfb00a685910f18a3cd3122660838d` | `JsonWriter.class` `a8826336823bc059619ada7214b70cbe3e968069ff59f0d34f90b620192539ad` (+9 nested) |
| S40 | parent | `spring-boot-4.0.10-SNAPSHOT.jar` `57463126ca7b854e7fe7b7df6668492121222300fe86c4af96172655752743c4` | `a8826336823bc059619ada7214b70cbe3e968069ff59f0d34f90b620192539ad` (same order) |
| S41 | fix | `spring-boot-buildpack-platform-4.0.10-SNAPSHOT.jar` `7d1f134db90a75167359ebc169528384cddc5207245c4196d3165287f21ddb34` | `InspectedContent.class` `e2ada71208b0b37f3cd334ff870e89e0f5a61bce6941205888f662789faa1049` (+2 nested) |
| S41 | parent | `spring-boot-buildpack-platform-4.0.10-SNAPSHOT.jar` `7466a893469b4821f0c23a88eab9c2801b2bd0da124242c4a11b42cf27dbdc34` | `e2ada71208b0b37f3cd334ff870e89e0f5a61bce6941205888f662789faa1049` (same order) |
| S42 | fix | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `3d9595c819ac5882899bb3abdab6975d2b38a9a11e20b0c9786852075c126dab` | `NestedJarFile.class` `f5f00db8ac03c65d3bba7fcf26dff69e739336bb69404f3d5e97b58813fd16f7` (+6 nested), `ZipInflaterInputStream.class` `848baaa86e04607a46fd509a8cb92563d5a93d963fc364062d7c0ed4601eba6d` |
| S42 | parent | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `76394fa14f9aa2be6aed953cb8c490313e7cddebf78eb9146c034db4989c5999` | `f5f00db8ac03c65d3bba7fcf26dff69e739336bb69404f3d5e97b58813fd16f7`, `88bff081d28852fc886cdc2d511ddb1dd476150ef70d2af063cfd9e8d392da82` (same order) |
| S43 | fix | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `ed366c3ab7a8faa55c83846ef4572ca01ac8783ea72c3c5ddafd21dad73f92da` | `UrlEncoder.class` `8fe851da482d438b828c2f1dc4da4df595a293b786d27f98ab2e5d8011ca8d1c` |
| S43 | parent | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `4d6403ff434ea34f9bb770d5d07884e8906610ef8d377d0378fc32582c64fdc8` | `6ddfabf0b536aff92910940d4dacf10a965843052b68f3c7ad05bf441a028b24` (same order) |
| S44 | fix | `spring-boot-loader-4.0.9-SNAPSHOT.jar` `7ddd960c6592a19fff37db230fed2166aeafc5b8247d14186d6f897e7f4b4210` | `JarUrlClassLoader.class` `1b7a4eed352242b34ff1af8d036ca9f53528b93cecbfbf9a69b657ee04e72102` (+1 nested) |
| S44 | parent | `spring-boot-loader-4.0.9-SNAPSHOT.jar` `1a7e634cfd62759ee6aec9b1bb56b34e85c78c2925a47d1f5e1c0dd8135bf31a` | `bb3e22f0aecd4d33726118edd84e3cf047c359a482351b34fdd1ae494642355a` (same order) |
| S45 | fix | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `c5bdb4a5c215170a58c968a5f5678890dcc72d97ce37e190dff2067f0a667bf6` | `JarUrlClassLoader.class` `f96328af0d437348a066ebeb14af039617384536fec04907de7b4ae94afc7b7b` (+2 nested) |
| S45 | parent | `spring-boot-loader-4.2.0-SNAPSHOT.jar` `217f1895c8df9adb6b9c72af6cbab2c24836a984131eac85bf64e931e591ce2f` | `f96328af0d437348a066ebeb14af039617384536fec04907de7b4ae94afc7b7b` (same order) |
| S46 | fix | `spring-boot-jarmode-tools-4.2.0-SNAPSHOT.jar` `38c1227d60c661fa5936808dfc505923a4ed9308b08445f9ee4e0b4538f1d3b4` | `IndexedLayers.class` `346df1d0910991db583f0364ef7d8102a5073d52dbcab46c88e2ad9aad090e05` |
| S46 | parent | `spring-boot-jarmode-tools-4.2.0-SNAPSHOT.jar` `b5df1e2f029bddc27b6ec158b6368f4e1dbd913f6ea392dc4a082fd2bd2263b0` | `9cb215d1725fbb18dd4ec84d42d1335af87e3275f2ad738b4cff32861998fe76` (same order) |
| S47 | fix | `spring-boot-gradle-plugin-4.0.10-SNAPSHOT.jar` `5105654f3969b598938d5efb9706e7bf50668ceb9aa08f1a8d0665e39a9d8d89` | `LayeredSpec.class` `13f5e96370db47012cce0a2d49d51b0f9a51e80afa2702bbffc72db47209c203` (+7 nested) |
| S47 | parent | `spring-boot-gradle-plugin-4.0.10-SNAPSHOT.jar` `86796434210cd2429f81bfebc1c43c9a6816d8794c7e6ffaf6ee802fa5a3b289` | `13f5e96370db47012cce0a2d49d51b0f9a51e80afa2702bbffc72db47209c203` (same order) |
| S48 | fix | `spring-boot-loader-tools-4.0.9-SNAPSHOT.jar` `2b5ea57830a9aefd35c52c3d35b9a985a5ac7c15d1f5ab54091486a1b2a8cd53` | `Packager.class` `20f85a8e7878f66a8fa2fed7812cc5a89452d18813e8a54ad69a2ac78a361f46` (+4 nested) |
| S48 | parent | `spring-boot-loader-tools-4.0.9-SNAPSHOT.jar` `327cb8097f9ca7a2e150f4652e2fff06c898459552b8ec2424607496ef08a1f4` | `54b15e65939b7ff284c6ddcc359c541265d1dcd0f06642ed7b5380d367479d0e` (same order) |
| S49 | fix | `spring-boot-gradle-plugin-4.2.0-SNAPSHOT.jar` `1817f9296edf4b3bbdb868dbb3f4531123e25d84718272d87b28d465270716b9`, `spring-boot-jarmode-tools-4.2.0-SNAPSHOT.jar` `27b6be8a0cf848a870d6f8f777c323b976f1ace07971a991e3612e0d6ae753fe`, `spring-boot-loader-tools-4.2.0-SNAPSHOT.jar` `39129147994afbf6dae620ce2f0475f22a8bd24e270b9dabe8f1825e0174930d` | `spring-boot-gradle-plugin BootArchiveSupport.class` `b363c2233dd3039def8b110226aee579f0e0cdcd460d9de157e76cc3839200f3`, `spring-boot-gradle-plugin BootJar.class` `c508a7e19d6ef40e1ca99e56260ef36c29d7ab6d4a7de838557d4ff8b8ea33f8` (+2 nested), `spring-boot-gradle-plugin BootWar.class` `b2b5d97608cbd642a61ed5fa2a0eb79db4dd7e586b380ad0fe35a9a576151097` (+2 nested), `spring-boot-jarmode-tools ArchiveType.class` `60bf937bd1cb4207028a6bd15b6e70060f0f433385cd9c8d48b5498bbff341ee`, `spring-boot-jarmode-tools ExtractCommand.class` `3329d7df6d1eafb74592cf31c059a5ac34b1a48d72ef1682533ad7cd6f5bfe23` (+6 nested), `spring-boot-jarmode-tools IndexedJarStructure.class` `69814d3b628d884c181cdb7ded420f3c54ad8d82d116b73448d4029f3c2a0f8e`, `spring-boot-jarmode-tools JarStructure.class` `d5a9b5e2647f76da49e535429ec3ea5b5521d18baee8a17b10910163315855e5` (+2 nested), `spring-boot-loader-tools Packager.class` `53fb6ad0519faf3cdb37e7838b14ecac74c71d339d33c61b1dae67a58d92f2db` (+4 nested) |
| S49 | parent | `spring-boot-gradle-plugin-4.2.0-SNAPSHOT.jar` `0156b01e803df4ad3f7e9bd8e4807cf6d55e3d5eff1b9793722e1ed35cce2502`, `spring-boot-jarmode-tools-4.2.0-SNAPSHOT.jar` `9dcb48713b28480dc3ab0a8cb1a075d995aee13baec5b9473e08de91b7aa1426`, `spring-boot-loader-tools-4.2.0-SNAPSHOT.jar` `e45968b5cae64df15aee65c9d7e98b8f9f71628676d45042c8c3a7ab70588f69` | `36d472c7170968e8a81c47191a58ffe981863d4850c2529058e027136725ea6f`, `cc585ac56beaa3b5a9458b97320482aeb43944edd37b6c63bfe054001b326ca1`, `22e1bf914bc79f6c0fb78884b572863330d9397e899f6141dc1a305f06f51499`, (absent), `db04e2ae0e210e128a13527ec0ba47177a1d7ae091ee777415f7e85c01b11343`, `800bd4b0624d4bb4485eaa8ec194c6dc7fe05b941498d4b81156c724a3ea0a03`, `d5a9b5e2647f76da49e535429ec3ea5b5521d18baee8a17b10910163315855e5`, `03915f3e8cb3cc32c98aed9a6c2b07fc483bb03d47ce768af0965d9bbed5dc20` (same order) |
| S50 | fix | `spring-boot-flyway-4.0.8-SNAPSHOT.jar` `d8c95c8b682d498e466787e1094ec16ceacf5cf02cafb686cdb14af56e37c962` | `NativeImageResourceProvider.class` `79d329e2a25ff2422ed36495778071d2bd6d794cd8b7c6d767107d3d70c2d5ff` (+1 nested) |
| S50 | parent | `spring-boot-flyway-4.0.8-SNAPSHOT.jar` `6b318ac6cd216c55fd0821dea87aa172d60513c1885a05699d1f562ecf029ba5` | `b42abbccb1d7d56370588e1a6598e4bcb9f79a75e23ad7e7fb4c343b5d1b3c71` (same order) |

## Setup Agent Notes

### What is ready, and where

- `source ~/.cache/in-the-loop/spring-boot-pr-links-s01-s50/scripts/env.sh` (`$P`, `$W`, `$M`, `TMPDIR`, `GRADLE_USER_HOME`, JDKs
  `$J8`…`$J25`, GraalVM `$JG25`). The default `java` is JDK 25; the Boot 4 builds need it.
- **Every pin checked out**: `$W/CASE-parent` and `$W/CASE-fix` for S01–S50 (100 worktrees, full commit ids in the revision table of
  [Upstream revisions](#upstream-revisions); `CASE` labels are this record's, not example ids). Mirror `$M/spring-boot.git`, refs
  `refs/pins/s01-s50/*`. S16's intermediate commits and the two foreign commits (Spring Batch for S24, Spring Kafka's
  `AwaitAsyncResultsOnStopTests` for S30) are in [Upstream revisions](#upstream-revisions) and [Other repositories](#other-repositories).
- **Dependencies resolved** for every configuration of each case's projects (`cases.tsv` column 4) **and of every project they
  reach through project dependencies**, at both pins, in `$P/gradle-home`; that resolution was repeated `--offline` and resolves
  from the cache for all 98 worktrees ([Online resolution](#online-resolution)). Run Gradle with `$P/scripts/gradle_case.sh` (the
  pins' own Gradle, verified) and `--offline`; the [Commands](#commands-for-a-rerun-by-hand) section has the forms for a task, a
  classpath file, and resolving more.
- **Built artifacts**: `$P/artifacts/CASE-ROLE/` with `jars/`, `SHA256SUMS`, and `PROJECT.runtimeClasspath.txt` /
  `PROJECT.testRuntimeClasspath.txt` (`:`-joined, ready for `java -cp`; project outputs under `tree/`, Gradle's generated API
  jars under `gradle-home/`). Complete for 41 cases ([Job results](#job-results) has their digests). For S19, S24, S29, S30,
  S31, S32, S33 and S36 the third run rewrites the folder; until it finishes, S24's and S30's folders are partial.
- **Released versions the brief names** in `$P/releases/SET/` (`jars/`, `classpath.txt`): Boot 4.0.6, 4.0.7, 4.1.0, 4.1.1, 4.2.0-RC1,
  3.5.14, Framework 7.0.9, Tomcat 11.0.24, datasource-decorator 2.0.1, maven-war-plugin 3.5.1, GraalVM build tools 0.11.5
  ([Released artifacts](#released-artifacts) has the row per set).
- **Docker images** for the service claims: `rabbitmq:4.2-management`, `redis:7.0.11`, `redis:8.6.2`, `mongo:5.0.17`,
  `apache/kafka:3.7.0`, `postgres:17`, `testcontainers/ryuk:0.14.0` (digests in [Docker images](#docker-images)).
- **S16** (2017): `bash $P/scripts/slice_s16.sh`, the parent's slice jar `$P/slices/S16-parent-boot-2.0.0.M2-s16/S16-parent-boot-2.0.0.M2-s16-slice.jar`,
  and the sets `boot-2.0.0.M2-s16`, `boot-2.0.0.M2-fwRC3-s16`, `boot-2.0.0.M3-s16`, `tests-S16-m2`, `tests-S16`, `tests-S16-m3`.

### What was verified on a JVM

- **43 Gradle cases** (jobs, JDK 25, offline except S10 and S48): the landed tests pass at the fix, the parent's versions pass at
  the parent, and the fix's tests fail on a copy of the parent (or do not compile there). The methods, or the task and first
  error, are in [Job results](#job-results): S01–S10, S13–S15, S17–S23, S25–S29, S31, S33–S45 and S47–S50.
- **S11, S12, S46**: the landed tests pass at the fix and the parent's at the parent, but the fix's tests **also pass on the
  parent** (S11 23, S12 107 with the three landed runner tests, S46 9). No landed regression separates the two pins of these
  three in this build; see [Job results](#job-results) for S12's snapshot caveat.
- **S24, S30, S32: not yet.** Their second run failed for setup reasons (the Micrometer snapshot's deprecation under `-Werror`; an
  abstract test class); the third run is queued (`$P/tmp/resubmit2.txt`).
- S16 (slice route, JDK 8): the parent's `WebFluxAutoConfigurationTests` pass on the parent slice over Boot 2.0.0.M2 (15 tests); the
  fix's three landed test classes do not compile on the parent slice (`CodecCustomizer`, `WebClientCustomizer` absent); on the
  release Boot 2.0.0.M3 they run 21 tests with 1 failure (`WebClientAutoConfigurationTests#shouldGetPrototypeScopedBean`, RC3's
  `WebClient` rejects the test's empty mocked response). The fix pin itself was not run (see below).

### What to know before starting

- **Snapshots are today's newest builds**, the same bytes for both pins of a case, mostly dated after the pins
  ([Snapshot dependencies](#snapshot-dependencies), 222 jars, per-jar sha256 in `$P/logs/snapshots.txt`). Stay `--offline`, or a
  build may fetch a newer one.
- **A `--dry-run` proves nothing about offline resolution**; resolve what you add with `resolve_closure.sh` (online, then the
  same with `RESOLVE_ARGS=--offline RESOLVE_TAG=…`). `repo.spring.io` had intermittent DNS failures on 2026-11-27: an online
  run that prints `Could not HEAD 'https://repo.spring.io/…'` is to be rerun, not believed.
- **S30 substitutes Spring Kafka 4.2.0-M2** for the pins' `4.2.0-SNAPSHOT` (`-I $P/scripts/subst-spring-kafka.init.gradle`, which
  `case_job.sh` adds; add it yourself for any other S30 build). Label S30 evidence as built against 4.2.0-M2.
- **S24 and S30 build `:module:spring-boot-micrometer-metrics` without `-Werror`**
  (`-I $P/scripts/no-werror-micrometer-metrics.init.gradle`, which `case_job.sh` adds). The only Micrometer `1.18.0-SNAPSHOT`
  still served deprecates the AppOptics registry, which that project uses. Add the script to any other build at these pins that
  compiles that project.
- **Name concrete test classes in `--tests`**: a filter on an abstract class (S32's `HealthEndpointSupportTests`) matches nothing,
  and Gradle reports success with 0 tests. Gradle 9 also hashes the XML file name of a class whose `TEST-CLASS.xml` passes 120
  bytes, so find results by `<testsuite name>` (`$P/scripts/class_counts.py RESULTDIR CLASS`), not by file name.
- **S16's fix compiles against no released Framework**: its `CodecsAutoConfiguration` calls `jackson2Decoder/jackson2Encoder`, which
  RC3 renamed `jackson2JsonDecoder/jackson2JsonEncoder`, and RC2 lacks `WebClient.Builder.clone()` and `codecs(...)`. Boot 2.0.0.M3
  matches the fix apart from formatting, Javadoc and that rename (`$P/logs/s16-fix-vs-m3.diff`). Label any M3 evidence as the
  nearest release, not the pin. M2 matches the parent's changed files except test-autoconfigure's `spring.factories`, which the
  slice carries; release `spring.factories` files still load beside the slice's.
- **S10 and S48's landed tests need the network** (TestKit downloads Gradle 9.0.0 and the current Gradle; the Maven integration test
  fetches Maven plugins from Central). S29's `dockerTest` needs Docker.
- Skip buildSrc's own checks on every Gradle run (`-x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x
  :buildSrc:checkFormat`): they cost about 90 s a fresh worktree. At most two Gradle runs on `$P/gradle-home` at once, or give each
  run its own home over the read-only cache as `case_job.sh` does (`SETUP_GRADLE_HOME=$P/gradle-homes/NAME`,
  `GRADLE_RO_DEP_CACHE=$P/gradle-home/caches`).
- `rabbitmq:4.2-management` and `postgres:17` are floating tags pulled on 2026-11-27, newer than the pins.
- The three shared commits (S12 fix = S32 parent, S14 fix = S27 parent, S28 fix = S41 parent) each have two worktrees with the same
  tree.

### What is left for the domain work on purpose

- Every claim: the fixtures, the before/after observations, controls and challenges, and examples, sidecars and adapters.
- How to treat S16 (the parent's slice, M3 as a labelled stand-in, or neither) and whether the S30 substitution is acceptable evidence.
- The service fixtures the claims describe (Compose files, a Redis cluster, a Kafka broker, a Mongo replica set, a native image for
  S50) and the HTTP clients and parsers used to observe them.
- Any build of a module this setup did not resolve (the other changed modules of S27, S19's other smoke tests, the docs build).
