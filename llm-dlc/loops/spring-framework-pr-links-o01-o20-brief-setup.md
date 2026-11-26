# Setup for the Spring Framework PR links O01–O20 brief

Mechanical setup for [`spring-framework-pr-links-o01-o20-brief.md`](spring-framework-pr-links-o01-o20-brief.md), done on
2026-11-25/26 by a setup session (Claude Opus 5.5) before the domain work starts. The session writes no claims, examples,
sidecars, adapters or checker code, allocates no example ids, and runs neither the project verifier nor JBMC. Everything
fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/spring-pr-links-o01-o20`, and `$M` is `~/.cache/in-the-loop/git-mirrors`.
`source $O/scripts/env.sh` defines `$O`, `$M`, `$W` (= `$O/worktrees`), `TMPDIR` (= `$O/tmp`), `GRADLE_USER_HOME` (= `$O/gradle-home`),
the JDK homes `$J8` `$J11` `$J17` `$J21` `$J25` (Temurin 8u512, 11.0.33, 17.0.21, 21.0.13, 25.0.5 under `~/.sdkman/candidates/java/`,
the installations earlier setups used) and `$JL17` (BellSoft Liberica 17.0.21.1, fetched here, see [Toolchain](#toolchain)).
**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

Case ids `O01`–`O20` follow the brief's order (the same as the PR list
[`spring-framework-merged-pr-links-o01-o20.md`](spring-framework-merged-pr-links-o01-o20.md)). They are this record's labels
only, not example ids.

## Starting commit

Checkout at setup: `6ca945ed2dbc4bef78ade55362fc6af7d2255250` (`develop@origin`, "Merge the single-agent run
organic-java-merged-pr-links-n01-n05-brief into the line").

## Upstream revisions

All 20 pull requests are in `spring-projects/spring-framework`. The shared bare mirror `$M/spring-framework.git` (it existed
already) gained every pinned commit, fetched by SHA at depth 1 from GitHub and kept under `refs/pins/o01-o20/CASE-ROLE-SHA`
(`$O/scripts/pins.tsv`, log `$O/logs/fetch.log`: 43 of 43). Roles: `parent` = the brief's *before* pin, `fix` = its *after*
pin, `later` = a subsequent revision the brief names but leaves outside the comparison (O01 `cb98dd33…`, O17 `dabd6377…`,
O20 `53783127…`; full ids in the table). The intermediate commits of the two two-commit landings were fetched too
(`8ab533263994e92f9660c9917a07cd3d8f8e769b` for O08, `d8bc54d2e7d09d115dfb78381fbbac1ac0c90ab0` for O10). One detached worktree
per pinned revision: `$W/CASE-ROLE` (43 worktrees, 3.8 GB checked out).

Checked mechanically (`$O/logs/prs.txt`, `$O/logs/landed-vs-pr-files.txt`, PR records `$O/upstream/prs/PR.json`, changed files
`$O/upstream/prs/PR-files.tsv`):

- **Every PR is merged and its `merge_commit_sha` equals the brief's after pin.**
- **For 18 cases the after pin's first parent is the before pin.** O08 and O10 land as two commits each:
  O08 `749aa1f6… → 8ab53326… (Honor If-Range for resource range requests) → 05619fe6… (Polishing contribution)`,
  O10 `6467fca0… → d8bc54d2… (Fix data loss in DataBufferUtils synchronous write) → 80534f9d… (Polishing contribution)`,
  as the brief says ("covers both submitted commits"). O03, O04, O08, O09, O11, O14 and O17 have a two-parent merge as
  their **before** pin, and O11's after pin is itself a merge (second parent `e3afd35c0d2c9ddc48b041b84f1dad89ac302987`, the PR head).
- **The diff before→after names exactly the PR's changed files** for all 20 (`$O/logs/CASE-landed-files.txt`, diffstats in
  `$O/logs/CASE-landed-diffstat.txt`).
- **Signatures**, checked in a keyring of this work's own (`GNUPGHOME=$O/gnupg`, agent stopped; keys in `$O/keys/`: GitHub's
  `web-flow.gpg`, and Sam Brannen's SSH signing key from `gh api users/sbrannen/ssh_signing_keys` in `$O/keys/allowed_signers`;
  the principal name in that file is this setup's label only). All 21 signed pins verify (`$O/logs/commit-signatures.txt`);
  the rest are unsigned.

| Case | Worktree | Commit | Tree | Parents | Date | Author | Signature | Subject |
|---|---|---|---|---|---|---|---|---|
| O01 | `O01-parent` | `2c5c6b580f90ce77973d16d24bce4c5dce00b558` | `64dae15cf57f82b20023b9e17fa6e5699ec70c58` | `0e46a26837f635d5647170d7e186887d780de157` | 2026-10-09 | Brian Clozel | unsigned | Register default converters in RestClient.Builder |
| O01 | `O01-fix` | `3e05e8872f529c5f843e68fb6a82250349b9f019` | `59f29d64d54bc8fc5828c76ce341e7352a2ef508` | `2c5c6b580f90ce77973d16d24bce4c5dce00b558` | 2026-10-10 | Esmaeil Chitgar | good, GitHub web-flow key B5690EEEBB952194 | Support positive hexadecimal values in NumberUtils |
| O02 | `O02-parent` | `7ff9e3d0314766984efb20b6cbf2cfe6e19e378d` | `58461f0004a7e1cfd473a0e74537f0f0e4cbb49c` | `d1c8abb208b033d04e53038c876095566b041550` | 2026-11-12 | Brian Clozel | unsigned | Ignore empty root mapping in YamlProcessor flattening |
| O02 | `O02-fix` | `1f083db2da6fe35908f1365f177c2091f5c0a26a` | `067896a3e48cca5978ccaec5d2c4eb4f413c3525` | `7ff9e3d0314766984efb20b6cbf2cfe6e19e378d` | 2026-11-12 | Jialin Chen | unsigned | Fix SUN-SUN day-of-week range in CronExpression |
| O03 | `O03-parent` | `f0eb43a6af37df784cd2f0367022c5dba4273bf0` | `51f4e974246db5097bbe1a6deed351274a8752e2` | `69c8f8e9c7387d71ec1d08fb9d0b993f5b889866` `6c8ebc7f7e61b878fd7b53b944ff2625d832b7b1` | 2023-04-04 | Arjen Poutsma | unsigned | Merge pull request #30157 from srivatsa-cfp:main |
| O03 | `O03-fix` | `95883b9eb7228dfeafc227de9d2ccfbd22e90ce8` | `7cf346b499987baa4b394c2e91c0a3222e323308` | `f0eb43a6af37df784cd2f0367022c5dba4273bf0` | 2023-04-04 | Simon Baslé | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | Rename MockMVC matcher methods to prevent regression in user tests |
| O04 | `O04-parent` | `bcfa6c3c4fc9133229bcf252827989555ec009a7` | `78c170c5f96e921af931bcdff801f133f0cad18d` | `74b6a5ba3ee5645cd2f5f99fa9c1cefeea95c9f1` `0acdf8083072868e84d73f20469293fb64d25a7d` | 2026-08-20 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| O04 | `O04-fix` | `af466ccf63bc55f82961b6627fe0c97c43a54632` | `2361b052f9a844aee15641baaccbc1ee56711035` | `bcfa6c3c4fc9133229bcf252827989555ec009a7` | 2026-08-20 | 김준형 | good, GitHub web-flow key B5690EEEBB952194 | Fix `OptionalToObjectConverter` applicability check |
| O05 | `O05-parent` | `d3c3088c6ba27a5a6d7f458a76f5d91320aaf828` | `fff5f9c61bc3ae4a41f22caf121ecd49141b6590` | `f2c0b3064156e0159e8c20d59ea4f654aaaaa7d9` | 2023-05-05 | Simon Baslé | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | Clarify behavior of the Elvis SpEL operator in documentation (#30352) |
| O05 | `O05-fix` | `906c54faffc75721b98f9b9cf63d35edd81f7b4f` | `c5ea1a332a70648f62c2e9695a1f769cdc39b02b` | `d3c3088c6ba27a5a6d7f458a76f5d91320aaf828` | 2023-05-05 | Simon Baslé | unsigned | Add SpEL support for registered MethodHandles |
| O06 | `O06-parent` | `0c575d443dbdff69349a2369f40491c002dc2c96` | `2b68ce36e84e22e3e021b19d49ded5de6b253e58` | `e499653a4085bd3abbd5199d45fde8320dbb0aa4` | 2026-10-22 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Make PropertySource.toString() independent of log level |
| O06 | `O06-fix` | `4cf6335372556d4f6ccc3a0166318c5f19037e8f` | `0dd1dbffbfb1d578546e94dd7dce9abe5d193f28` | `0c575d443dbdff69349a2369f40491c002dc2c96` | 2026-10-22 | Christian Aurich Zanettini Martins | unsigned | Deep copy default headers, cookies in client builders |
| O07 | `O07-parent` | `d5a7fc9a9ce32a94176620be4d9d6b070a260b9c` | `ccf1e44e9b48a4520e436059eb519fdb39044961` | `c377da58d9ecaa3454e1cd6ea00519ee47ecfe60` | 2026-10-03 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Update exception message in HttpMessageNotReadableException |
| O07 | `O07-fix` | `f03b76a53dfd87e53db0c4c72f37e2a87c94f7c2` | `02e8a89dd7e7d75177ecc1c47ee14ad5af4f8557` | `d5a7fc9a9ce32a94176620be4d9d6b070a260b9c` | 2026-10-03 | Hyunwoo Jung | good, GitHub web-flow key B5690EEEBB952194 | Copy cookies in RenderingResponse.from() |
| O08 | `O08-parent` | `749aa1f6a9bd70b637f01b0e2dceb1103cd1c5f1` | `783b52567e792f848d82fd510b26fc2b2d9e463c` | `00145f98ed8255d2646cf5df27d4a86ef3abbb66` `fd44a6bdd94b65312fbb02bc11a575b40fa1e772` | 2026-10-21 | Brian Clozel | unsigned | Merge branch '7.0.x' |
| O08 | `O08-fix` | `05619fe624cd410736848b3bf4f83d632cfe54f5` | `65a6efed90c0f0cb6fa8aa323c2311c7dbe419f5` | `8ab533263994e92f9660c9917a07cd3d8f8e769b` | 2026-10-22 | Brian Clozel | unsigned | Polishing contribution |
| O09 | `O09-parent` | `60b9f4cd3a491a84e1dfe294005729cf49ed36e5` | `92420c69c0fa5d9f01983ed229eb4b0026b5520a` | `aa655718a807344f8c46df0c281431ca1d0fd505` `d3d8e05fa9d4fefa3961154eaaa210268750ec68` | 2026-09-09 | Brian Clozel | unsigned | Merge branch '7.0.x' |
| O09 | `O09-fix` | `adbc8ceeab6e004ad8664c2ff5639449c18f2396` | `f488f59913a5ae016dce38b8945df06a5d71c9e1` | `60b9f4cd3a491a84e1dfe294005729cf49ed36e5` | 2026-09-09 | Artyom Tsvirko | unsigned | Ignore invalid SSE retry field |
| O10 | `O10-parent` | `6467fca05b874f3e44fbd9451a252f035abbeafc` | `b9c37e858cb7c3e3aa3816f0791275d9ea83ab30` | `cddc671a8c6eea118b1f7ef05f2b6d754e852f09` | 2026-06-04 | Brian Clozel | unsigned | Polishing contribution |
| O10 | `O10-fix` | `80534f9df6aaa6b155ef3fb8494c057b0d4f268f` | `ba57c3d556671c9c65d2502e1152498837850cda` | `d8bc54d2e7d09d115dfb78381fbbac1ac0c90ab0` | 2026-06-04 | Brian Clozel | unsigned | Polishing contribution |
| O11 | `O11-parent` | `f78bc953f47cd05ca8f686bce963349ccc79df51` | `8803128b04e4bee8c206fe9dab5c571d876d8dc2` | `b4530e19fc3df0b96e3cc828ef5f102cbdf8305e` `26101892c1b9fa5fe92a20a6bb3661ffada9f650` | 2017-03-27 | Stephane Nicoll | unsigned | Merge pull request #1354 from QBNemo:master |
| O11 | `O11-fix` | `0ddcce4169dd9c885b02cba1180d49d1d5c366e0` | `c74008481d2df7011b21dd718cb58cbbcfe48b83` | `f78bc953f47cd05ca8f686bce963349ccc79df51` `e3afd35c0d2c9ddc48b041b84f1dad89ac302987` | 2017-03-27 | Juergen Hoeller | unsigned | Merge pull request #1366 from arturgspb/master |
| O12 | `O12-parent` | `5772133ba7c65e5b7e738d33add0ffed6102f62b` | `4de82806684861b7a904cc6d9c4a40e43d15068e` | `f12a47acc9c5c985ee3e511c8507b22ddc2ecb97` | 2026-09-21 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polishing |
| O12 | `O12-fix` | `6e5efdc89ba269b8dd7aedf3f894387f5b6cc50a` | `d6b75b0b4b7517611f8efb2d679188ded48651d0` | `5772133ba7c65e5b7e738d33add0ffed6102f62b` | 2026-09-21 | Yanming Zhou | good, GitHub web-flow key B5690EEEBB952194 | Set first batch args once while executing batch with generated keys |
| O13 | `O13-parent` | `9332b3f69084081d181dd8fb4051cedf1aad859d` | `d5f49d1d61fcf860b43f831358d37d5e36a4bd72` | `5f13b2b35b5ea191007997e7c4593281f8aba0d6` | 2023-05-25 | Simon Baslé | unsigned | Have ReactiveTypeHandler consider +x-ndjson suffix as streaming |
| O13 | `O13-fix` | `5977bb05ca737ba8b0516d7ee42e005b7c591868` | `638fe2fde0dbf586264f2b864acf583c5fb982d6` | `9332b3f69084081d181dd8fb4051cedf1aad859d` | 2023-05-25 | Simon Baslé | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | Port BeanPropertyRowMapper and DataClassRowMapper for r2dbc |
| O14 | `O14-parent` | `8853f4b883822e0ccb13e3ef6c6aba01f280f77a` | `79465e5ebef750acb1cea382984d8dbdf3dbd5fc` | `775d99ac7855b86ee359d71eafa9f2f976e4ed92` `d51abe462e1bfc320506606650ca13db8bfb5d3b` | 2020-06-17 | Sam Brannen | unsigned | Merge branch '5.2.x' |
| O14 | `O14-fix` | `217b6e37a64b2df7f7265cfff1adf52361872469` | `e78636165c0981917f22c31d88312495ea58bc45` | `8853f4b883822e0ccb13e3ef6c6aba01f280f77a` | 2020-06-17 | Mark Paluch | unsigned | Rollback reactive transaction on cancel |
| O15 | `O15-parent` | `5c7bf0c2fec41d91be510003f00d8ecebe308b5b` | `afebc760703e03362b22d775f5c28f1738b2bba0` | `4aeeacb4c2cdd52289a3bd666d1608c20733de71` | 2023-09-11 | Sam Brannen | unsigned | Add tests for MethodInvoker behavior in the TestContext framework |
| O15 | `O15-fix` | `8d4ea72e4e2f01e37bca46db8662fae133595d6b` | `a18ae2ba41bdf597f59d951b932e2917deb0e145` | `5c7bf0c2fec41d91be510003f00d8ecebe308b5b` | 2023-09-11 | christophejan | unsigned | Skip release connection after nested with existing transaction |
| O16 | `O16-parent` | `4a6c3e8f5dda538c07d41f424e6f15a51c410ada` | `b39888a8051f508dfb7a0a65ae5658ee6e95d8d0` | `f77713b7e0402c7747877ca2d6d0f7f0ea9b146b` | 2023-11-30 | Juergen Hoeller | unsigned | Fix reactive retrieval of cached null value for empty Mono |
| O16 | `O16-fix` | `feef98b73ce4f86779075298debf6614f01b47c9` | `18b2d83229eefa632ac84e82bf258530e0803e3b` | `4a6c3e8f5dda538c07d41f424e6f15a51c410ada` | 2023-11-30 | Yanming Zhou | unsigned | Correct conversion from Resource[] with length 1 to Collection<Resource> |
| O17 | `O17-parent` | `05a1075b69053eb8e0c24c748fc9064d6ad2a1a2` | `74b4d612d9efc571bfbff38bd2dc5914ef9e1f1e` | `9f8a476f94923f8ff8cfa83ca832ed9f6d2a121f` `4898ed3ad8c8caf119fadc5ca25f498d61ddf9ed` | 2026-09-14 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Merge branch '7.0.x' |
| O17 | `O17-fix` | `74a6c1c328e75c696b2833a7b284414c6c7083ce` | `7ca5f6b31a774db58c44f04f5af561b19c0ca2be` | `05a1075b69053eb8e0c24c748fc9064d6ad2a1a2` | 2026-09-14 | Yanming Zhou | good, GitHub web-flow key B5690EEEBB952194 | Fix BeanFactory.getBean(String, ParameterizedTypeReference) to respect AOP proxy |
| O18 | `O18-parent` | `b1cf832c28473518240a91afed17bd51f95fbf9a` | `e6f33bfe0c100f5e12cbbe556f7b5f8d45f22614` | `34e5ce9360ed6c0fe83678a904d5e70064765db6` | 2023-02-28 | Sam Brannen | unsigned | Apply "instanceof pattern matching" in spring-tx |
| O18 | `O18-fix` | `4cc02fe3bcbfcafe824a9ca130e47bfaa79cb522` | `2a85e678f3ba06a34e3c62573b3e4f7ba52a1020` | `b1cf832c28473518240a91afed17bd51f95fbf9a` | 2023-02-28 | Radek Kraus | good, GitHub web-flow key 4AEE18F83AFDEB23 (expired since) | Protect JMS connection creation against prepareConnection errors |
| O19 | `O19-parent` | `3709672494e0e6582a28e0378c0e8a339d6545e9` | `dbda20b7b0d8e0073309d3086f1d3d961093c9cf` | `2e478e52d85450bb9bcd42e3fe6cdf6b2f8a5569` | 2026-10-06 | Tran Ngoc Nhan | good, GitHub web-flow key B5690EEEBB952194 | Fix Kotlin examples in the reference manual |
| O19 | `O19-fix` | `440139fec1e61b275ea152da8293e7647ab9b917` | `8860d9be14a78656d471328b95145f6d7f467cdd` | `3709672494e0e6582a28e0378c0e8a339d6545e9` | 2026-10-06 | Hyunwoo Jung | good, GitHub web-flow key B5690EEEBB952194 | Fix Flux resubscription in reactive caching |
| O20 | `O20-parent` | `bed8682544f942ecb9e398fe4106f16a56185c63` | `caf06632ea5802985eb32972266236b082682e68` | `d1d77e373a657f6bf16cf50767acf1fcb002078e` | 2026-10-29 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polishing |
| O20 | `O20-fix` | `67467f48fa4aef1a3bd227b8b45b11bb7925369b` | `a4b72edba4e47781ff86c599f52288f7fd9a05a9` | `bed8682544f942ecb9e398fe4106f16a56185c63` | 2026-10-30 | Adrian Pulbere | good, GitHub web-flow key B5690EEEBB952194 | Propagate Reactor Context for Flux in reactive caching |
| O01 | `O01-later` | `cb98dd335255f9f6bb7773fd718249faec27101e` | `e1424d4ee1ea40e2c9fa147e7586873ffc8fa2df` | `3e05e8872f529c5f843e68fb6a82250349b9f019` | 2026-10-10 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Revise contribution |
| O17 | `O17-later` | `dabd63770ffba2f0cc19c4c29dda1205fc8b348b` | `a961bc0b05610edfe4ea9290a0f138ec25030e6a` | `fe2617582a7201f9e96d56d9f77a00cd6ce077f4` | 2026-09-14 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Add dedicated unit test for getBean(String, ParameterizedTypeReference) |
| O20 | `O20-later` | `53783127de602eb41679cf6fdb6b1ff95e07dbad` | `2a927c1bba571f360776b97a2e05b3072d0fc9dd` | `67467f48fa4aef1a3bd227b8b45b11bb7925369b` | 2026-10-30 | Sam Brannen | good SSH, sbrannen's GitHub signing key SHA256:PzPcZfc83Q9gHMDNz8xUseZrxdUqA5vkIbr3l5yLetQ | Polish contribution |

PR metadata (`gh api`): base branch `main` except O02, O07, O10, O19, O20 (`7.0.x`) and O11, O14 (`master`). Merged
between 2017-03-27 (O11) and 2026-11-12 (O02).

## Toolchain

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512, 17.0.21, 21.0.13, 25.0.5 (11 unused) | `~/.sdkman/candidates/java/` | earlier setups' installations |
| BellSoft Liberica JDK 17.0.21.1+5 | `$O/tools/jdk/jdk-17.0.21.1` (`$JL17`), tarball `$O/dl/jdk/bellsoft-jdk17.0.21.1+5-linux-amd64.tar.gz` | sha1 `a44f40d665ddaa9e450a15e2b1f55d1a754630bb` = BellSoft's API (`$O/dl/jdk/liberica17-latest.json`); sha256 `add6f8c21289daf20eb38cd8fbd05bc374773038512cae655844e4e9a9a4f3d3`; no signature published. Needed by O16 only: its `buildSrc` `JavaConventions` sets the toolchain to vendor `BELLSOFT`, language 17. |
| Gradle 3.4, 6.5, 7.6, 8.0.2, 8.1.1, 8.3, 8.4, 9.5.1, 9.7.1, 9.8.0, 9.8.1, 9.8.2, 9.9.0 | unpacked in `$O/tools/gradle-V` | zip sha256 = services.gradle.org's `.sha256`, all 13 ([digests](#gradle-distributions)) |
| Maven 3.10.0 | on `PATH` (sdkman), settings `$O/maven-settings.xml` (local repository `$O/m2`, plus `repo.spring.io/milestone`) | released artifacts only |
| Docker image `postgres:17` | local Docker | `postgres@sha256:0d938e975177bef9f1f61f3f9dbcf2e0aa0a139568f66d3415ed8892eb97f6ac`, PostgreSQL 17.12 (Debian 17.12-1.pgdg13+1), created 2026-11-12; already on the machine |

Each checkout's wrapper names its own Gradle (table in [Build facts](#build-facts-by-era)); every checkout's
`gradle-wrapper.jar` matches gradle.org's `gradle-V-wrapper.jar.sha256` except Gradle 3.4's (O11), for which gradle.org
publishes no wrapper checksum (`$O/logs/wrapper-jars.txt`). **The wrapper is not used**: `$O/scripts/gradle_case.sh` runs the
verified distribution the wrapper names. None of the wrapper properties sets `distributionSha256Sum`.

### Gradle distributions

zip sha256 (each equal to services.gradle.org's `gradle-V-bin.zip.sha256`, `$O/logs/gradle-dists.txt`; the `.sha256` files
are kept beside the zips in `$O/dl/gradle/`):

| Gradle | zip sha256 | checkouts' `gradle-wrapper.jar` sha256 |
|---|---|---|
| 3.4 | `72d0cd4dcdd5e3be165eb7cd7bbd25cf8968baf400323d9ab1bba622c3f72205` | `64e2fc1bb83222fd216e98d9f69496035d340ce45a3a7097e6cd0d6df2a5237b` (no published checksum) |
| 6.5 | `23e7d37e9bb4f8dabb8a3ea7fdee9dd0428b9b1a71d298aefd65b11dccea220f` | `70239e6ca1f0d5e3b2808ef6d82390cf9ad58d3a3a0d271677a51d1b89475857` |
| 7.6 | `7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b` | `c5a643cf80162e665cc228f7b16f343fef868e47d3a4836f62e18b7e17ac018a` |
| 8.0.2 | `ff7bf6a86f09b9b2c40bb8f48b25fc19cf2b2664fd1d220cd7ab833ec758d0d7` | `91941f522fbfd4431cf57e445fc3d5200c85f957bda2de5251353cf11174f4b5` |
| 8.1.1 | `e111cb9948407e26351227dabce49822fb88c37ee72f1d1582a69c68af2e702f` | `ed2c26eba7cfb93cc2b7785d05e534f07b5b48b5e7fc941921cd098628abca58` |
| 8.3 | `591855b517fc635b9e04de1d05d5e76ada3f89f5fc76f87978d1b245b4f69225` | `0336f591bc0ec9aa0c9988929b93ecc916b3c1d52aed202c7381db144aa0ef15` |
| 8.4 | `3e1af3ae886920c3ac87f7a91f816c0c7c436f276a6eefdb3da152100fef72ae` | `0336f591bc0ec9aa0c9988929b93ecc916b3c1d52aed202c7381db144aa0ef15` |
| 9.5.1 | `bafc141b619ad6350fd975fc903156dd5c151998cc8b058e8c1044ab5f7b031f` | `497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7` |
| 9.7.1 | `acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a` | `7a9ce74cff467ca1bf60a4fcd9f05185acceda4d0f382434d393e17864262c5d` |
| 9.8.0 | `bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c` | `238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5` |
| 9.8.1 | `dce76f55f8e251a3a1f130eb120f30b3d271de2b76c9b0729d316b5a1b6dc01f` | `3b8a25775a69158b5ad2b1d17a80a88dc7b40a352a73eb27d06c612a7ce68e98` |
| 9.8.2 | `21bd5da2de49b642904077f38c0efdc7778e92b3ed0889392dca61b97e389607` | `3b8a25775a69158b5ad2b1d17a80a88dc7b40a352a73eb27d06c612a7ce68e98` |
| 9.9.0 | `0b00b0ffe07c4d4789c12d4935a44a7057d55774b7540bd4a3f76f336deb177a` | `621008afc4f5d59357fcf06ffa644dd5aade5e091bdc363742710445f73cdaf8` |

## Build facts by era

Both pins of every case have the same project version and the same Gradle.

| Cases | Version | Gradle | Launcher JDK | Compiles with | Kotlin |
|---|---|---|---|---|---|
| O01 | 7.1.0-SNAPSHOT | 9.8.1 | 25.0.5 | toolchain 25, `release` 17 (`buildSrc` `JavaConventions`) | 2.4.20 |
| O02, O20 | 7.0.11-SNAPSHOT | 9.9.0 (O02), 9.8.2 (O20) | 25.0.5 | toolchain 25, release 17 | 2.2.21 |
| O04, O09 | 7.1.0-SNAPSHOT | 9.7.1 | 25.0.5 | toolchain 25, release 17 | 2.4.10 |
| O06, O08 | 7.1.0-SNAPSHOT | 9.8.2 | 25.0.5 | toolchain 25, release 17 | 2.4.21 |
| O12, O17 | 7.1.0-SNAPSHOT | 9.7.1 | 25.0.5 | toolchain 25, release 17 | 2.4.20 |
| O07, O19 | 7.0.10-SNAPSHOT | 9.8.0 | 25.0.5 | toolchain 25, release 17 | 2.2.21 |
| O10 | 7.0.8-SNAPSHOT | 9.5.1 | 25.0.5 | toolchain 25, release 17 | 2.2.21 |
| O03 | 6.0.8-SNAPSHOT | 8.0.2 | 17.0.21 | the launcher JDK (17) | 1.7.21 |
| O18 | 6.0.6-SNAPSHOT | 7.6 | 17.0.21 | the launcher JDK (17) | 1.7.21 |
| O05, O13 | 6.1.0-SNAPSHOT | 8.1.1 | 17.0.21 | the launcher JDK (17) | 1.7.21 (O05), 1.8.21 (O13) |
| O15 | 6.1.0-SNAPSHOT | 8.3 | 17.0.21 | the launcher JDK (17) | 1.9.10 |
| O16 | 6.1.2-SNAPSHOT | 8.4 | 17.0.21 | **toolchain vendor BELLSOFT, 17** (Liberica, `$JL17`); spring-core's multi-release jar also compiles for 21 (Temurin 21) | 1.9.21 |
| O14 | 5.3.0-SNAPSHOT | 6.5 | (8) | source 1.8 | **1.4-M2** — not buildable, see [O11 and O14](#o11-and-o14-the-historical-builds-cannot-be-configured) |
| O11 | 5.0.0.BUILD-SNAPSHOT | 3.4 | (8) | source 1.8 | 1.1.1 — not buildable, same section |

**Runner.** `$O/scripts/gradle_case.sh DIR TAG RESULTDIRS ARGS...` runs, in DIR, `JAVA_HOME=LAUNCHER timeout 3000 [choom -n 500 --]
$O/tools/gradle-V/bin/gradle --no-daemon --console=plain --max-workers=4 --no-build-cache -Dorg.gradle.caching=false --no-scan
-Porg.gradle.java.installations.auto-detect=false -Porg.gradle.java.installations.auto-download=false
-Porg.gradle.java.installations.paths=$J8,$J11,$J17,$J21,$J25,$JL17 ARGS` with `GRADLE_USER_HOME=$O/gradle-home`, V read from DIR's
wrapper properties and the launcher by era (above; `GJ=PATH` overrides). Log `$O/logs/TAG.log`, JUnit summary `$O/logs/TAG.junit.txt`.
(`choom` is skipped when the process already runs at OOM score 500 or more, as a pipeline job does.) The 7.x and 6.x
`settings.gradle` apply the Gradle Enterprise / Develocity conventions plugins; `--no-scan` and the disabled build cache keep
them from publishing or reading anything remote.

**Repositories the builds name**, checked anonymously on 2026-11-25: Maven Central and the Gradle Plugin Portal (all eras);
`repo.spring.io/milestone` and `repo.spring.io/snapshot` (200; the 7.x and 6.x builds add them for a `-SNAPSHOT` version);
`repo.spring.io/libs-spring-framework-build` (6.0 and 5.3 builds; reachable, answers 404 for what was probed);
`repo.spring.io/release` (6.0, 6.1 builds' plugin management, **401**), `plugins-release`, `libs-release`, `libs-snapshot`,
`libs-milestone` (5.3 and 5.0 builds, **401**). The 7.x and 6.x builds resolve without the 401 repositories (Gradle finds every
module earlier in the list).

**Online resolution** (inline, each Gradle run in a 6 GB scope; `$O/scripts/resolve_online.sh WORKTREE...`): two passes per
worktree, `-I $O/scripts/resolve-all.init.gradle setupResolveAll -PsetupResolve=Classpath,kotlin,Kotlin,annotationProcessor,AnnotationProcessor`
then `-PsetupResolve=ALL`, over **every project** of the build (the init script adds tasks `setupResolveAll` and
`setupWriteClasspath` to every project and changes no upstream file). Per worktree 513–564 configurations in pass 1, all
resolved; 718–1,131 in pass 2. Summaries: `$O/logs/resolve-7x.summary.txt`, `$O/logs/resolve-6x.summary.txt`,
`$O/logs/resolve-6x-rerun.summary.txt`; logs `$O/logs/WORKTREE.resolve{1,2}.online.log`. Pass 2 failures, none used by a compile
or test task: the Kotlin plugin's IDE-only `*DependenciesMetadata` configurations (66–122 per worktree at 7.0.x and 6.x; none at
7.1), and at O18 (Gradle 7.6) the legacy `default` configuration of eight projects, whose `dependencies` report resolves every
module (`$O/logs/O18-fix.web-default.online.log`).

**Snapshot dependencies.** The 7.1.0-SNAPSHOT platforms import `reactor-bom:2026.0.0-SNAPSHOT` (reactor-core and reactor-test
3.9.0-SNAPSHOT, reactor-netty 1.4.0-SNAPSHOT) and most also `micrometer-bom:1.18.0-SNAPSHOT`. What was cached is the snapshot
current on 2026-11-25, not the one of each pin's date, and both pins of a case read the same bytes; build `--offline` to keep
them ([digests](#snapshot-artifacts)).

### Snapshot artifacts

The snapshot jars in `$O/gradle-home` (one file per module; full paths in `$O/logs/snapshot-artifacts.txt`). reactor-core, reactor-test, micrometer-observation, micrometer-commons and micrometer-observation-test have the same digests as the spring-and-java-data setup cached on 2026-11-22, so these snapshots had not moved since then.

| Module | sha256 |
|---|---|
| `io.micrometer:micrometer-commons:1.18.0-SNAPSHOT` | `1b3add3a081c9e9390fe3305dff43db944ea7a39b9a50a03acb1e3e65497eff9` |
| `io.micrometer:micrometer-core:1.18.0-SNAPSHOT` | `048dcfc51a98e344c22bc17720bceca999f65f7a5fd403a967b7aea296547fa6` |
| `io.micrometer:micrometer-jakarta9:1.18.0-SNAPSHOT` | `c5809b29a8458dd9128ff5e5f5beda7cdad73bbe72527f4b990a1c29a90fe6b1` |
| `io.micrometer:micrometer-observation:1.18.0-SNAPSHOT` | `e1c8305e6b8e30563012c3aa6cea565a9367ba773202386e8015efa5a46e6964` |
| `io.micrometer:micrometer-observation-test:1.18.0-SNAPSHOT` | `d4e85b7504c8621ba20e56a11bf4c0ff062b03a0b553bfce6d9e24c6d37da742` |
| `io.projectreactor.netty:reactor-netty-core:1.4.0-SNAPSHOT` | `eec27fecf961e887aa8ec1d1add4173556bf46d9ca87c429295ae93c2ebbba03` |
| `io.projectreactor.netty:reactor-netty-http:1.4.0-SNAPSHOT` | `e28e59e57bb53e643b71f8ec5aa253db868cbb5190bcd4ea67509c9d44533e55` |
| `io.projectreactor:reactor-core:3.9.0-SNAPSHOT` | `51436b9a3967185ee445d5db4053c5c43886465121383f6196d8f383a66bfc72` |
| `io.projectreactor:reactor-test:3.9.0-SNAPSHOT` | `129ede5ed343d6996fa427f48ffb29d56d0b7a6814d006c00e3c644a985b44a3` |

## O11 and O14: the historical builds cannot be configured

**O11 (#1366, 2017, Gradle 3.4).** The root `build.gradle`'s `buildscript` takes its plugins from `repo.spring.io/plugins-release`
only, which answers 401. Of its classpath, `dependency-management-plugin:1.0.0.RELEASE` and `kotlin-gradle-plugin:1.1.1` are on
Central, `asciidoctor-gradle-plugin:1.5.3` and `org.sonarqube` 2.2.1 on the Plugin Portal, but **`io.spring.gradle:propdeps-plugin:0.0.8`
and `io.spring.gradle:docbook-reference-plugin:0.3.1` were found nowhere**: 404 at Central, the Plugin Portal, `repo.spring.io/milestone`
and `snapshot`, `libs-spring-framework-build`, Grails, JBoss, Atlassian, Red Hat, JitPack, Alfresco, Jenkins, Sonatype OSS
releases and MuleSoft; 401 at `repo.spring.io/plugins-release(-local)`, `plugins-snapshot` and `libs-release-local`. Without them the
build script does not compile, so no init script can route around the 401. The project dependencies would also come from
`libs-release`/`libs-snapshot` (401). Not built, not tested.

**O14 (#25256, 2020, Gradle 6.5).** The root `build.gradle` applies `org.jetbrains.kotlin.jvm` **1.4-M2** and imports
`kotlin-bom:1.4-M2` and `kotlinx-coroutines-bom:1.3.7-1.4-M2`, from `dl.bintray.com/kotlin/kotlin-eap` (Bintray closed in 2021).
1.4-M2 was found nowhere: 404 at Central, the Plugin Portal, `repo.spring.io/milestone` and `snapshot`,
`packages.jetbrains.team/maven/p/kt/{dev,eap,bootstrap}`, `redirector.kotlinlang.org/maven/{dev,kotlin-eap}`, Google, JBoss,
Atlassian, Grails; `maven.pkg.jetbrains.space` does not resolve in DNS. The build also imports `reactor-bom:2020.0.0-SNAPSHOT`, which
`repo.spring.io/snapshot` still serves, but as its last build (2020-10-26, `2020.0.0-20201026.191845-20`), not the June 2020 one. The
settings plugin `io.spring.gradle-enterprise-conventions` 0.0.2 is not on the Plugin Portal either. Not built, not tested.

Neither gap was worked around: getting either build needs a decision this setup does not take (a trusted source for the missing
artifacts, or a change to the historical build). What the domain work can use instead is below.

**Released artifacts whose changed sources match the pins** (git blob ids of the files in the `-sources.jar`, compared with the pins'
blobs, `$O/logs/O11-O14-pinned-blobs.txt`; sources jars in `$O/dl/sources/`):

| Case | File | Pin blob | Release |
|---|---|---|---|
| O11 parent | `spring-jdbc/.../namedparam/NamedParameterUtils.java` | `cbde6f799dfe98e5637e599bd7e38a94f3bb0643` | **spring-jdbc 5.0.0.M5: identical** |
| O11 fix | the same | `6e47509b67b59265666a3bf53c25b8b4a127c348` | spring-jdbc 5.0.0.RC1 (`065a254bed4ac5328d187cb5cf8cf2a3b5f0a87e`): differs **only in the copyright line** (2002-2016 → 2002-2017); RC2 and 5.0.0.RELEASE differ further (`638a6ae5a410d5bd8a885bcdb692beedd788d816`) |
| O14 parent | `spring-tx/.../reactive/TransactionalOperatorImpl.java` | `26e343d285b6a389e194c0ff4d9bd3f5d3efa466` | **spring-tx 5.2.7.RELEASE and 5.2.8.RELEASE: identical** |
| O14 parent | `spring-tx/src/main/kotlin/.../TransactionalOperatorExtensions.kt` | `503ee4e2f3540e548767284035a1481c63360a68` | **5.2.7.RELEASE and 5.2.8.RELEASE: identical** |
| O14 parent | `spring-tx/.../interceptor/TransactionAspectSupport.java` | `4c9a27ff1525b80a8c8a68ef09653e2ab64e2484` | 5.2.7.RELEASE differs (copyright year, `<p>` in three Javadoc comments, two `retVal != null &&` guards on the Vavr check, one `@Nullable`) |
| O14 fix | `TransactionalOperatorImpl.java` | `7dc3de8842e62a5aeba14065ceb613005dc6f5c3` | **spring-tx 5.3.0-M1: identical** (5.3.0-M2 differs) |
| O14 fix | `TransactionalOperatorExtensions.kt` | `67b93e764c6c57cccde8109954ad0770c1014836` | **5.3.0-M1 and 5.3.0-M2: identical** |
| O14 fix | `TransactionAspectSupport.java` | `6752239a6e902677d71333b58efcf01eb3567675` | 5.3.0-M1 differs only in the `CallbackPreferringPlatformTransactionManager` branch (where `result` is declared and the throwable rethrown) and one Javadoc line |

The rest of each module (and of spring-core, spring-beans) moved between these releases and the pins; which route, if any, stands in
for a pin is the domain work's call. The source tree of each pin is in its worktree either way. At the O14 pins there is **no
`spring-r2dbc` module** (`settings.gradle` lists none); 5.3.0-M1 has one.

## Released artifacts

From Maven Central, or `repo.spring.io/milestone` for milestones, resolved with Maven into `$O/m2`
(`mvn -s $O/maven-settings.xml dependency:copy-dependencies` on a pom per set, `$O/releases/SET/pom.xml`); each set has its jars in
`$O/releases/SET/jars/` and a `:`-joined `classpath.txt`. Every jar's sha1 equals its repository's `.sha1`; `.asc` signatures were
fetched and checked in `$O/gnupg`, getting keys from keyserver.ubuntu.com / keys.openpgp.org (`$O/scripts/verify_releases.sh`,
results with sha256 in `$O/logs/release-verify.txt`).

| Set | Why | Jars |
|---|---|---|
| `spring-test-5.3.26` | the version issue #30220 reports (O03) | spring-test, spring-core, spring-jcl 5.3.26: good signatures, key `928FBF39003C0425` "Spring Builds" |
| `spring-jdbc-5.0.0.M5` | O11 parent's parser (above) | spring-jdbc, -tx, -beans, -core 5.0.0.M5, commons-logging 1.2: Spring jars signed by `23EF3D2F93185045`, key not obtainable (unchecked); commons-logging good (`A41F13C999945293`) |
| `spring-jdbc-5.0.0.RC1` | O11 fix's parser (above) | spring-jdbc, -tx, -beans, -core, -jcl 5.0.0.RC1: no `.asc` published |
| `spring-tx-5.2.7.RELEASE` | O14 parent's reactive files (above) | spring-tx, -beans, -core, -jcl 5.2.7.RELEASE with reactor-core and reactor-test 3.3.6.RELEASE and reactive-streams 1.0.3 (`reactor-bom:Dysprosium-SR8`, as the `v5.2.7.RELEASE` tag's build declares): key `9A2C7A98E457C53D` / `1364C5E2DF3E99C5` not obtainable (unchecked) |
| `spring-tx-5.3.0-M1` | O14 fix's reactive files (above) | spring-tx, -r2dbc, -beans, -core, -jcl 5.3.0-M1, reactor-core and reactor-test 3.4.0-M1, r2dbc-spi 0.8.2.RELEASE, r2dbc-h2 0.8.4.RELEASE, h2 1.4.200 (`reactor-bom:2020.0.0-M1`, `r2dbc-bom:Arabba-SR5`, h2 1.4.200, as the `v5.3.0-M1` tag's builds declare): milestones carry no `.asc`; r2dbc keys not obtainable; h2 good (`0A4B343F2A55FDAE`) |
| `postgresql-42.7.15` | a pgJDBC for O11's database read (claim .3); the brief names no version, this is the current release | postgresql 42.7.15 (good, `305F296EAC47556B` "pgjdbc releases"), checker-qual 3.55.1 (good, `B16698A4ADF4D638`) |

The optional Spring dependencies (Reactor and the R2DBC driver) do not appear in the Spring 5.x poms, so they were taken from the
release tag's build files, read with `gh api repos/spring-projects/spring-framework/contents/...?ref=TAG`.

**PostgreSQL smoke** (once, container removed): `docker run -d --rm --name o11-setup-pg-smoke -p 127.0.0.1:54331:5432
-e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=setup postgres@sha256:0d938e975177bef9f1f61f3f9dbcf2e0aa0a139568f66d3415ed8892eb97f6ac`,
ready (`pg_isready`) after about 2 s; `$J17/bin/java -cp $O/releases/postgresql-42.7.15/jars/postgresql-42.7.15.jar
$O/scripts/smoke/PgSmoke.java jdbc:postgresql://127.0.0.1:54331/setup postgres` printed `driver=PostgreSQL JDBC Driver 42.7.15
server=17.12 (Debian 17.12-1.pgdg13+1) autocommit=true`. No query of the brief was run.

## Jobs

One job per buildable case (18; O11 and O14 have none, see above), each of four steps run by `$O/scripts/case_job.sh CASE STEP`
(table of modules and test classes: `$O/scripts/cases.tsv`; submitted by `$O/scripts/submit_case.sh`):

1. `fix`: in `$W/CASE-fix`, offline: `:M:jar` for the case's jar modules and `:M:test --tests CLASS` for each landed test class,
   with `-Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline --continue`; then keeps
   `$O/artifacts/CASE-fix/`: `jars/`, `SHA256SUMS` (jars, and every class compiled from a production source file the landing
   changed, nested classes included) and, per classpath module M, `M.runtimeClasspath.txt` and `M.testRuntimeClasspath.txt`
   (`:`-joined; the project outputs they name are copied under `tree/`, the rest are paths into `$O/gradle-home`; written by
   `-I $O/scripts/resolve-all.init.gradle :M:setupWriteClasspath -PsetupCpConf=CONF -PsetupCpOut=FILE`).
2. `parent`: the same in `$W/CASE-parent`, with those landed classes that exist at the parent (all but O13's two new classes).
3. `transplant`: `git archive` of the parent into `$O/build/CASE-parent-landed`, every changed file under `src/test` or
   `src/testFixtures` taken from the fix, then the same test classes. Passes when they fail (`TRANSPLANT-FAILS-AS-EXPECTED`) or do
   not compile (`TRANSPLANT-DOES-NOT-COMPILE-AS-EXPECTED`).
4. `clean`: `git clean -fdxq` in both worktrees, transplant copy removed.

Before submitting, `case_job.sh CASE dryrun` (offline `--dry-run` of both pins' task graphs, the classpath tasks included)
configured for all 18 (`$O/logs/dryrun-{6x,7x-a,7x-b}.txt`). Logs per step: `$O/logs/CASE-ROLE.test.offline.{log,junit.txt,class.txt}`,
`$O/logs/CASE-parent-landed.test.offline.*`, `$O/logs/CASE-ROLE.cp-M-CONF.log`.

| Case | Job |
|---|---|
| O01 | `20261126-003556-setup-build-spring-framework-37434-o01-a` |
| O02 | `20261126-003556-setup-build-spring-framework-37576-o02-a` |
| O03 | `20261126-001149-setup-build-spring-framework-30238-o03-a` |
| O04 | `20261126-003557-setup-build-spring-framework-36913-o04-a` |
| O05 | `20261126-001149-setup-build-spring-framework-30045-o05-a` |
| O06 | `20261126-003557-setup-build-spring-framework-37325-o06-a` |
| O07 | `20261126-003557-setup-build-spring-framework-37378-o07-a` |
| O08 | `20261126-003557-setup-build-spring-framework-37218-o08-a` |
| O09 | `20261126-003557-setup-build-spring-framework-37193-o09-a` |
| O10 | `20261126-003557-setup-build-spring-framework-36714-o10-a` |
| O12 | `20261126-003557-setup-build-spring-framework-37308-o12-a` |
| O13 | `20261126-001149-setup-build-spring-framework-30530-o13-a` |
| O15 | `20261126-001149-setup-build-spring-framework-31133-o15-a` |
| O16 | `20261126-001149-setup-build-spring-framework-31699-o16-a` |
| O17 | `20261126-003557-setup-build-spring-framework-37047-o17-a` |
| O18 | `20261126-001149-setup-build-spring-framework-29116-o18-a` |
| O19 | `20261126-003558-setup-build-spring-framework-37403-o19-a` |
| O20 | `20261126-003558-setup-build-spring-framework-37600-o20-a` |

All 18 jobs passed every step (results below). Time and peak memory per job, as the runner reported them: O01 5m20s 3.8 GiB, O02 7m27s 4.1 GiB, O03 17m47s 3.2 GiB, O04 5m46s 3.4 GiB, O05 12m50s 2.0 GiB, O06 12m07s 5.7 GiB, O07 10m53s 4.4 GiB, O08 11m47s 6.1 GiB, O09 10m06s 4.6 GiB, O10 6m17s 3.2 GiB, O12 6m35s 3.2 GiB, O13 17m38s 2.4 GiB, O15 20m15s 2.6 GiB, O16 18m29s 3.3 GiB, O17 6m49s 4.1 GiB, O18 15m31s 2.1 GiB, O19 7m21s 3.8 GiB, O20 7m03s 4.0 GiB (O08 went just past the 6G estimate, under its 9G limit). The result files are `verification/results/2026/11/26/JOB/result.json`, collected by the runner onto another head (seen in commit `d8e67216443f80a88470c272c2aef1e6c6ce39d0`), not in this record's commits.

## Job results

**Spring 6.x cases: all six jobs passed every step** (read from the step logs in `$O/logs/` after the runner finished them on
2026-11-26). Fix and parent columns: the landed test classes at that pin (O13's two classes are new, so its parent step builds the jar only). Transplant: the
fix's changed test files on a copy of the parent.

| Case | Fix | Parent | Transplant |
|---|---|---|---|
| O03 | exit 0, 29 tests, 0 failures, 0 errors (211 s) | exit 0, 27 tests, 0 failures, 0 errors (190 s) | **does not compile**: `MockRestRequestMatchersTests.java:164` cannot find symbol; `MockRestRequestMatchersTests.java:172` cannot find symbol |
| O05 | exit 0, 33 tests, 0 failures, 0 errors (153 s) | exit 0, 30 tests, 0 failures, 0 errors (118 s) | **does not compile**: `TestScenarioCreator.java:82` incompatible types: MethodHandle cannot be converted to Method; `TestScenarioCreator.java:85` incompatible types: MethodHandle cannot be converted to Method |
| O13 | exit 0, 18 tests, 0 failures, 0 errors (207 s) | exit 0, 0 tests, 0 failures, 0 errors (169 s) | **does not compile**: `DataClassRowMapperTests.java:35` cannot find symbol; `DataClassRowMapperTests.java:35` cannot find symbol |
| O15 | exit 0, 17 tests, 0 failures, 0 errors (285 s) | exit 0, 18 tests, 0 failures, 0 errors (184 s) | **fails**: 17 tests, 1 failures, 0 errors; `R2dbcTransactionManagerUnitTests#testPropagationNestedWithExistingTransaction()` |
| O16 | exit 0, 20 tests, 0 failures, 0 errors (209 s) | exit 0, 20 tests, 0 failures, 0 errors (191 s) | **fails**: 20 tests, 11 failures, 0 errors; `ClassPathXmlApplicationContextTests#aliasWithPlaceholder()`, `ClassPathXmlApplicationContextTests#childWithProxy()`, `ClassPathXmlApplicationContextTests#configLocationPattern()`, `ClassPathXmlApplicationContextTests#factoryBeanAndApplicationListener()` and 7 more |
| O18 | exit 0, 19 tests, 0 failures, 0 errors (198 s) | exit 0, 18 tests, 0 failures, 0 errors (160 s) | **fails**: 19 tests, 1 failures, 0 errors; `SingleConnectionFactoryTests#testWithConnectionFactoryAndExceptionListenerAndReconnectOnExceptionWithJMSException()` |

O16's eleven transplant failures are `BeanCreationException`s (for example at `ClassPathXmlApplicationContextTests.java:187`):
every test that loads the changed `contextA.xml`, which adds `service3` with the single-resource collection properties, fails to
create its context on the parent. O15 fails an `AssertionError` at `R2dbcTransactionManagerUnitTests.java:479`, O18 an
`AssertionFailedError` at `SingleConnectionFactoryTests.java:409`. All three compile-failures name the API the landing adds
(`headerList`/`queryParamList`, `registerFunction(String, MethodHandle)`, the r2dbc row mappers). The `clean` step left no
untracked or ignored file in any of the twelve worktrees.

**Spring 7.x cases: all twelve jobs passed every step** (step logs in `$O/logs/`, read after the runner finished them on
2026-11-26). Same columns; every transplant fails or does not compile. Failing tests are named in full from
`$O/logs/CASE-parent-landed.test.offline.junit.txt`, parameterized ones with their method from the Gradle log.

| Case | Fix | Parent | Transplant |
|---|---|---|---|
| O01 | exit 0, 22 tests, 0 failures, 0 errors (75 s) | exit 0, 21 tests, 0 failures, 0 errors (67 s) | **fails**: 22 tests, 1 failure; `NumberUtilsTests#parseNumberAsPositiveHex()` |
| O02 | exit 0, 73 tests, 0 failures, 0 errors (116 s) | exit 0, 72 tests, 0 failures, 0 errors (96 s) | **fails**: 73 tests, 2 failures; `BitsCronFieldTests#parse()`, `CronExpressionTests#sundayToSunday()` |
| O04 | exit 0, 157 tests, 0 failures, 0 errors (84 s) | exit 0, 152 tests, 0 failures, 0 errors (69 s) | **fails**: 157 tests, 2 failures; `DefaultConversionServiceTests$OptionalConversionTests#canConvertOptionalWithBoundedWildcardReflectsUpperBound()`, `#canConvertOptionalToObjectReflectsContainedElementType()` |
| O06 | exit 0, 51 tests, 0 failures, 0 errors (171 s) | exit 0, 47 tests, 0 failures, 0 errors (138 s) | **fails**: 51 tests, 5 failures; `RestClientBuilderTests#copyConstructorCopiesDefaultCookiesImmutable()`, `#copyConstructorCopiesDefaultHeadersImmutable()`, `DefaultWebClientTests#mutateDoesNotShareDefaultHeaderAndCookieValues()`, `MockServerTests#buildDoesNotShareDefaultHeaderAndCookieValues()`, `#mutateDoesNotShareDefaultHeaderAndCookieValues()` |
| O07 | exit 0, 24 tests, 0 failures, 0 errors (165 s) | exit 0, 22 tests, 0 failures, 0 errors (132 s) | **fails**: 24 tests, 2 failures; `DefaultRenderingResponseTests#from()` in spring-webmvc and in spring-webflux |
| O08 | exit 0, 189 tests, 0 failures, 0 errors (155 s) | exit 0, 173 tests, 0 failures, 0 errors (146 s) | **spring-web does not compile**: `HttpRangeTests.java:118` cannot find symbol `resolveRanges(HttpHeaders,HttpHeaders)` (so `HttpRangeTests` and `ResourceHttpMessageWriterTests` did not run); **webmvc and webflux fail**: 156 tests, 4 failures; `ResourceHttpRequestHandlerTests$RangeRequestTests#ignoreRangeWhenIfRangeETagDoesNotMatch()`, `ResourceHandlerFunctionTests#ignoreRangeWhenIfRangeETagDoesNotMatch()`, `HttpEntityMethodProcessorMockTests#shouldIgnoreResourceByteRangeWhenIfRangeETagDoesNotMatch()`, `ResourceWebHandlerTests$RangeRequestTests#ignoreRangeWhenIfRangeETagDoesNotMatch()` |
| O09 | exit 0, 14 tests, 0 failures, 0 errors (124 s) | exit 0, 13 tests, 0 failures, 0 errors (124 s) | **fails**: 14 tests, 1 failure; `ServerSentEventHttpMessageReaderTests#ignoreInvalidRetry()` |
| O10 | exit 0, 379 tests, 0 failures, 0 errors (97 s) | exit 0, 367 tests, 0 failures, 0 errors (74 s) | **fails**: 379 tests, 4 failures; `DataBufferUtilsTests#writeWritableByteChannelWithJoinedBuffer(DataBufferFactory)` for its four Netty factories (`[1]`–`[4]`, Unpooled and Pooled, direct and heap), `AssertionFailedError` at `DataBufferUtilsTests.java:358` |
| O12 | exit 0, 53 tests, 0 failures, 0 errors (93 s) | exit 0, 48 tests, 0 failures, 0 errors (87 s) | **fails**: 53 tests, 5 failures; `NamedParameterJdbcTemplateTests#batchUpdateWithGeneratedKeys()`, `JdbcClientIndexedParameterTests#batchUpdateWithGeneratedKeys()`, `#batchUpdateWithGeneratedKeysAndKeyColumnNames()`, `JdbcClientNamedParameterTests#batchUpdateWithGeneratedKeys()`, `#batchUpdateWithGeneratedKeysAndKeyColumnNames()` |
| O17 | exit 0, 1 test, 0 failures, 0 errors (95 s) | exit 0, 1 test, 0 failures, 0 errors (87 s) | **fails**: 1 test, 1 failure; `ExpressionCachingIntegrationTests#expressionIsCacheBasedOnActualMethod()` |
| O19 | exit 0, 24 tests, 0 failures, 0 errors (110 s) | exit 0, 22 tests, 0 failures, 0 errors (108 s) | **fails**: 24 tests, 2 failures; `ReactiveRetryInterceptorTests#withCacheableAnnotation()`, `#withCacheEvictAnnotation()` |
| O20 | exit 0, 27 tests, 0 failures, 0 errors (114 s) | exit 0, 17 tests, 0 failures, 0 errors (94 s) | **fails**: 27 tests, 6 failures; `ReactiveCachingTests#cacheableFluxPropagatesContextOnCacheMiss(Class)` for all four configurations (`EarlyCacheHitDeterminationConfig`, `EarlyCacheHitDeterminationWithoutNullValuesConfig`, `LateCacheHitDeterminationConfig`, `LateCacheHitDeterminationWithValueWrapperConfig`), `#cachePutFluxPropagatesContext()`, `#cacheEvictFluxPropagatesContext()` |

Two things a reader of these rows would otherwise miss. In O10 only the synchronous joined-buffer test fails on the parent; the
landing's `writeAsynchronousFileChannelWithJoinedBuffer(DataBufferFactory)` passes there (the brief leaves that parent result to
the provider). In O20 the landed `cacheableMonoPropagatesContextOnCacheMiss(Class)` passes on the parent; the failures are the
Flux tests. The `clean` step left no untracked or ignored file in any of the
24 7.x worktrees, and no `$O/build/` copy remains.

## Digests of the built artifacts

Each `$O/artifacts/CASE-ROLE/SHA256SUMS` lists the module jars (`jars/`), the project jars on the kept classpaths (`tree/…`) and
the class digests of every production source file the landing changed (nested classes included). Jar digests include build
timestamps in the 6.x builds; the 7.x builds write reproducible jars (entries dated 1980-02-01), so a 7.x jar whose module the
landing does not touch has the same digest at both pins (O08's spring-webflux). The class digests are what compare across builds. Classpaths: `$O/artifacts/CASE-ROLE/M.runtimeClasspath.txt` and
`M.testRuntimeClasspath.txt` (`:`-joined).

| Case | Role | Module jar sha256 | Changed classes (sha256) |
|---|---|---|---|
| O03 | fix | `spring-test-6.0.8-SNAPSHOT.jar` `4f60554049081a4ec4384e1f7275d5f80064d90612b66ac4f56c8cc4104396ef` | `MockRestRequestMatchers.class` `afcfc0a2dc7a907f899dd1e01e1ff0277bb37172c4f15cad49bc17a80cc92ee4` |
| O03 | parent | `1ecc94b106d1235a54e77d46adc55146aaf35c380e4cb26a7498b8ce4880d37f` | `a3271f782ffce9d01ee8a3696f6f9227b4426ab9005ddc0d54c77c6c93820a07` |
| O05 | fix | `spring-expression-6.1.0-SNAPSHOT.jar` `1180be602732143635848905348d5e7b7005ff21f19a8b377125a92482078b57` | `FunctionReference.class` `498b71aaa065fe8c7edd0452c66200809b86578dd24062370a59f210b2c035f0`, `ReflectionHelper.class` `422c95e8f946da8e2c90947df07f3fe1d75e41bf460a1d3cbba7b76af1a088ca`, `StandardEvaluationContext.class` `a0caef978f9ce4ad592962b5c6613b5cf80a60a9c09eeb96289147753f42235a` (+2 nested, in the file) |
| O05 | parent | `bcb6092e71470a27918bc688904869c54df99581b0c26b36db1c346ecf1be415` | `825a80db74ecbff71867201a85a3e20ecd0e437067f25251e32f8d1cc09ef299`, `3cbd553409fd892336c7adafb417e6d21e89e0a8a0dddbff01a2514939b4f546`, `2b3434e3b5d90325171f6749e1f35800e2af238e53850bc7067fa4b4444a07e7` (same order) |
| O13 | fix | `spring-r2dbc-6.1.0-SNAPSHOT.jar` `8370831560ba085d01cdf6305863bab52a90a714df353f7b714d07b784e98ab6` | `BeanPropertyRowMapper.class` `d4c4a9a59f6fab7d6029a782d024212d59e1d3653edc9f2c956a3c9575556d99`, `DataClassRowMapper.class` `60d8f1a904327589d0fb89d4ac4d162abb9e0057201e6efb5e0767cd77ff960e` |
| O13 | parent | `267410963d204b43e8c7bad2db823abd85219e58e2b2c273a2aadb929bb32b78` | (classes absent) |
| O15 | fix | `spring-r2dbc-6.1.0-SNAPSHOT.jar` `431ed84317ee7492cdcf9b4203bd40ba00cb1df73cae5857acc06a943fc8f350` | `R2dbcTransactionManager.class` `a7d2781393588e636b0986d777e8d2004f11e8d9a244e59a29f4e4585f50b28d` (+2 nested) |
| O15 | parent | `009485c08575179c738e700eccfd9b64f9d3d63a54559c47b58beb5ab3b4d086` | `e018dc7b928b35cbd15d3041ae27b9d1fe1c31d01bca5fc2b09f1eef8e8dec1a` |
| O16 | fix | `spring-beans-6.1.2-SNAPSHOT.jar` `66738032d6bafb59cea89fb65250d659abe00dfae1fa2707e1cdd7c0b46d9346`, `spring-context-6.1.2-SNAPSHOT.jar` `65c27117cd2d5a1752e3ebd4f07188f0a15e2885347f7247d6a1ac45403583e1` | `TypeConverterDelegate.class` `276fbe147f33f1e8fca9f75009277a4205abd02a9d1f1fe41b2378183850f797` |
| O16 | parent | `c896916a37e92a599dcf17746027c68c883c8d55f459d89a7fe0cd94c89fca63`, `2fdc2658b06bcc1d2242186110e5555e9523eed0a82a05d15379d881002b5bea` | `c8cedbf575df814cf9bff2032cea7d80dfb3c0418657157f625de2af14c7b914` |
| O18 | fix | `spring-jms-6.0.6-SNAPSHOT.jar` `f6e94fef2e108adc75be33ae7559623421aeeaaa1bb2f471e51e0c2ba4910ab8` | `SingleConnectionFactory.class` `aa1d56c92469666a68cfe0a386954b1d7391299375b06037422533316bf1dbc0` (+2 nested) |
| O18 | parent | `dc522913ca18d225698a7afccdf2340a1ccf5f48b942927b15e260333b70508a` | `30206f976e7c2e391e257de000d5866f9bbf8542d60f55960fdaaba80dff01d2` |
| O01 | fix | `spring-core-7.1.0-SNAPSHOT.jar` `244fb25bb3c97c6c5053e20c95b793399d6c17a8c12d2b3180720f949333ee55` | `NumberUtils.class` `579e9b79b7b91c10e620821427b0d71795510e3ae3a162268f297d0be0299af7` |
| O01 | parent | `spring-core-7.1.0-SNAPSHOT.jar` `b5443b2c1d2ee7fb9edd1ff8a41652b9650fec35fdd62de7e8991243860fb57e` | `804868652c8983aa6b1309671ff656d522971515db649599c71aaa1232ea1e15` (same order) |
| O02 | fix | `spring-context-7.0.11-SNAPSHOT.jar` `8f413c79a5f90a0e5c7c3b4a831cf342a64112686feccc9b928b9e90e9eedd1a` | `BitsCronField.class` `cd8c93efbbbf6922b84808e4d38d28c5672893966f15a32f00ab8e7d1e9a660f` |
| O02 | parent | `spring-context-7.0.11-SNAPSHOT.jar` `f89d1b6c7a77bac8ff76e778246a6eae1bad81f9043bd91c6dee6ada3d551526` | `1db3066a3bf680fe8e6330721deece0b5df1e0aafd4fe541a2e5625743126870` (same order) |
| O04 | fix | `spring-core-7.1.0-SNAPSHOT.jar` `de7509824e61a15c3bc86b1880566afc18a8cfd96b033cb1eca6bc97c4da1300` | `OptionalToObjectConverter.class` `420639e8a8debdb6d761cded9c1a93dc6bdc2740dd44380787908cd610fee6a9` |
| O04 | parent | `spring-core-7.1.0-SNAPSHOT.jar` `b8397dbe3ea855a4f6fab9a73b768a0497ee8cdce5d8a7624afaca00c03f2418` | `3dfe259d743a903da82e3902c14057a0729c7af9e1a0ccc724fbf10f076f91ea` (same order) |
| O06 | fix | `spring-test-7.1.0-SNAPSHOT.jar` `15546e82d212d7710b2e9fa03aaf0194496a8ef046a52095b2ba3004caf4b470`, `spring-web-7.1.0-SNAPSHOT.jar` `ce6dcf80fefca587a85b8cdd61f9894cc912408fd765f8c2b925a975cd6cd137`, `spring-webflux-7.1.0-SNAPSHOT.jar` `499e4d5e283433e898d30cdf304db771bfff7852dea6a59154728d4356a201b9` | `spring-test DefaultWebTestClientBuilder.class` `67c00dfc5d6c2106f270c0ab71a6715c994d045f8dfc195a807902ddff753051`, `spring-web DefaultRestClientBuilder.class` `b2dad3b4d13ac614d1c7968ee2d56bb5ad1135e3467489d19fc08774a3cb2ddc`, `spring-webflux DefaultWebClientBuilder.class` `d343c1b3dff9af8d3304a36ce14e926df6f123e50711e0a26233138640d9206d` |
| O06 | parent | `spring-test-7.1.0-SNAPSHOT.jar` `c0c597a09fc6d8be6c0fc8d1ae82d036b248f34a7a7036ef7f3abfd194dd97a9`, `spring-web-7.1.0-SNAPSHOT.jar` `fe8dca4072a4bde84ff2026a656968feaed22a5ad680380b5c54d8f69bff4baa`, `spring-webflux-7.1.0-SNAPSHOT.jar` `a888c3569708b3e50887ef718b9697ae5111383b2b0a45fca2dab1bedddc37d2` | `af223238ace09ef729364fa71085386ff1a9f53cabcabbcff4825755270545f4`, `6a146da54b963bc0949263d507999e2b44b43b5023c4e9d1e92c25f18c97ba29`, `340685d373e8dd34c677614620c17451c1551404465528bcbc118c2d2055138e` (same order) |
| O07 | fix | `spring-webflux-7.0.10-SNAPSHOT.jar` `88239dd7548d74533fb4dad36d2d19e884d94d56330ac075e64b6b6b70dbf5dd`, `spring-webmvc-7.0.10-SNAPSHOT.jar` `d59708542c7a3d80b529bf390fae97696ed3d8a445487811ed8b4799b25c0126` | `spring-webflux DefaultRenderingResponseBuilder.class` `084ff712917c634ae299cf9d8daaa661b9d9bec33b505ae273c75868c4a1e544` (+1 nested), `spring-webflux RenderingResponse.class` `118905c8073875db1adbff6d12a8ea90df79cfdd4c2d7c295ff6eb8d7f26a61a` (+1 nested), `spring-webmvc DefaultRenderingResponseBuilder.class` `15df348607435245c4a4a694bac3fd2782e746efb816d72318d733055515ad67` (+1 nested), `spring-webmvc RenderingResponse.class` `67cd8769d6f35fa4a408fc2127e43ee72d2ce5eac67529bea2641c0f7736ff85` (+1 nested) |
| O07 | parent | `spring-webflux-7.0.10-SNAPSHOT.jar` `0b86e5adf7efe4c08b0a3a694669cbaefc4f6cc83e1cc38d33c16eee7cc38bc2`, `spring-webmvc-7.0.10-SNAPSHOT.jar` `50e46ae58f2cc394fe32c6087457f0f92a193ea5d315c093573765aec2cf688c` | `6a889dcc26e2b78d899e011b6615eb6f998cf1f6acccbd716ee982e77ea7f9bf`, `5d1d721bf0bd7e5ea0d4bc106dca4e8d740dcc01f417174984576a888c3e645f`, `9f43452700cb646047b2d85937d9e572cd56a2b8b381e8186200050aa2589357`, `1a1eb27ab3080fc9021ca57f24384f32bcbe8b9c09d575e9c638abe1688e36a9` (same order) |
| O08 | fix | `spring-web-7.1.0-SNAPSHOT.jar` `09d116a348b8e699ac69d952223c6ad4c68f43ce9739f51c3b918e11d665ce46`, `spring-webflux-7.1.0-SNAPSHOT.jar` `a888c3569708b3e50887ef718b9697ae5111383b2b0a45fca2dab1bedddc37d2`, `spring-webmvc-7.1.0-SNAPSHOT.jar` `df86969485f7c90f21d15b48f5e1a71406c61b91ebb3719b4fcbb744c701b02e` | `spring-web HttpHeaders.class` `b74d75df6759b71a5ad5096e52b4986406b4b79f304f8e19d3092c10ba1bc46d` (+5 nested), `spring-web HttpRange.class` `3b867c2b939ba137d0e1b82ae5ae7f17c4d7dd47903d69c45a86662db74229e0` (+2 nested), `spring-web ResourceHttpMessageWriter.class` `fc6e4a9f7e35d030e80e6db5f5b1ae715771f1be324bbbe9a688368be74240f2`, `spring-webmvc DefaultEntityResponseBuilder.class` `1ce5b828b227b6b85049190925ee6fa4c61297073cc944f44b19b1b230b89c38` (+6 nested), `spring-webmvc AbstractMessageConverterMethodProcessor.class` `b8ad20c1486418c8c1457d3195fcbfab82fee755cd24e2ad27458c416bd796c4` (+2 nested), `spring-webmvc ResourceHttpRequestHandler.class` `f650ea5dec48dae78469a52f1c10b326b34495a7ae936acd9f41287939d48225` |
| O08 | parent | `spring-web-7.1.0-SNAPSHOT.jar` `4d397f543ecf83e88be03951e60b4fc9696abe8835709658a686665dbbb16c0e`, `spring-webflux-7.1.0-SNAPSHOT.jar` `a888c3569708b3e50887ef718b9697ae5111383b2b0a45fca2dab1bedddc37d2`, `spring-webmvc-7.1.0-SNAPSHOT.jar` `fa8182db94bc85b7b969d92b0c452b7200c4d83199aebf97e65957888e7dbcd0` | `a8146e389db954b4d99b4828127421d60bf4de49bb071e40cda535df2a477e28`, `3796fb044f06ab84a3309ada1d4d721a524bf7676334428456745ea12137f8f5`, `9b36713f89a9b34db77a66e5ac3a3f549788b79838fa8bd8dbbf070192735c90`, `99b15f6c15c61e2dcadcfff7168102b39a8c841f23b2f31a210eb0dc87277519`, `2a6ec238e19087307967a2386ce7298f38eac987801c3e9d7579aaaa25b2de91`, `04b3bf65d0716619fdd984858f2a5c51208a27d58acaadd88bb37e781888ff72` (same order) |
| O09 | fix | `spring-web-7.1.0-SNAPSHOT.jar` `6f3145ab26e26a40402050dfef46d75489bffd872f1f6215d4044b4b19458e2a`, `spring-webflux-7.1.0-SNAPSHOT.jar` `2b93e6700e6ea9e50df6678733464f85df2499f6e355ddf4bb257cfc66ffc4a7` | `ServerSentEventHttpMessageReader.class` `4902dde3b5185ce5d5a548b25b28431614761daed22c237621ad68b47b1b90cd` (+1 nested) |
| O09 | parent | `spring-web-7.1.0-SNAPSHOT.jar` `6672125c0192816603a8265304094e1f49c11374103769c7e17f83acd2196471`, `spring-webflux-7.1.0-SNAPSHOT.jar` `2b93e6700e6ea9e50df6678733464f85df2499f6e355ddf4bb257cfc66ffc4a7` | `84cecb493920ce290fc038cd5d59cade70150e5536935ea1de58c8de84437141` (same order) |
| O10 | fix | `spring-core-7.0.8-SNAPSHOT.jar` `f565dbc70202a420da9e00b081b4897b73b0cadc7a033113fdf79aeca67c6a8d` | `DataBufferUtils.class` `a67b79ca7da6dc952b444560f61700cc3c2c0a8b4b0e6d9e34a877fcde399a08` (+15 nested) |
| O10 | parent | `spring-core-7.0.8-SNAPSHOT.jar` `6aa7010f26a043249446b67b210a406682070973619929404e29b5088fd2fb5d` | `a67b79ca7da6dc952b444560f61700cc3c2c0a8b4b0e6d9e34a877fcde399a08` (same order) |
| O12 | fix | `spring-jdbc-7.1.0-SNAPSHOT.jar` `ad2a45d3760e5fea45a79a9a3f64ac7ca20f3bab865b029519d37045366453d2` | `NamedParameterJdbcTemplate.class` `f75ab0ad2513426c9a7793acf5c85d0d2ba81bdbb51f89792df221cc3ead60d5` (+2 nested), `DefaultJdbcClient.class` `39f906a8238b1f00efc4ca72043d6a2c2bcbf5573369ef762cf60ad35acca90b` (+7 nested) |
| O12 | parent | `spring-jdbc-7.1.0-SNAPSHOT.jar` `cabf379ce542fc2b1ef46aaab4df95e3ed4eb750b1ceff898036b27b47fe6e64` | `7be9e63f24c781a1694193ceff5e8f45779052e147b22798ef218458a2d0f305`, `39f906a8238b1f00efc4ca72043d6a2c2bcbf5573369ef762cf60ad35acca90b` (same order) |
| O17 | fix | `spring-beans-7.1.0-SNAPSHOT.jar` `5b6874734e9d5dd07f585e7c705ed2b03bc71505df8e6bcba5fa0717e94df23a`, `spring-context-7.1.0-SNAPSHOT.jar` `1eeaeb19a637a19415870dccc7184dceb50f092ffe2512a508467848a773606f` | `AbstractBeanFactory.class` `bb03af74d0bbbbdf4e2dca36c5c27ed4fcbd2d105933d8e9b8d2ea2873b76e71` (+3 nested) |
| O17 | parent | `spring-beans-7.1.0-SNAPSHOT.jar` `74976c36cc6a615be753bfa40580d22d9b9118041e550212635dd52e580fb424`, `spring-context-7.1.0-SNAPSHOT.jar` `1eeaeb19a637a19415870dccc7184dceb50f092ffe2512a508467848a773606f` | `db05c4cbda960abd92c0376c0f2527f72c2601e90a0c0a0109a77e6bb63f9715` (same order) |
| O19 | fix | `spring-context-7.0.10-SNAPSHOT.jar` `b74d79a4e0acd7621c7cc56dc9fd1af5227190a937228fe10a425dfa32719e5d` | `CacheAspectSupport.class` `6c357c8fec1385f962bb01f107b52d99243201d1514ddaae0d2d8122e51a6790` (+8 nested) |
| O19 | parent | `spring-context-7.0.10-SNAPSHOT.jar` `a9fdab03f69493ef5eb5a69a76a986a01dbd8bfb32c0c0789559094f283e1744` | `6c357c8fec1385f962bb01f107b52d99243201d1514ddaae0d2d8122e51a6790` (same order) |
| O20 | fix | `spring-context-7.0.11-SNAPSHOT.jar` `734ff65ea07f28c2e92e9c9cd2363deba050a33d6a9b9ec6e3260047edd75f7b` | `CacheAspectSupport.class` `6c357c8fec1385f962bb01f107b52d99243201d1514ddaae0d2d8122e51a6790` (+8 nested) |
| O20 | parent | `spring-context-7.0.11-SNAPSHOT.jar` `72f588b87daa22a0bd8a875cc5ac5aa98cf694281ee74be4b9aae2e73b7d96e3` | `6c357c8fec1385f962bb01f107b52d99243201d1514ddaae0d2d8122e51a6790` (same order) |

Kept test runtime classpath sizes (fix): O03 spring-test 218 entries, O05 49, O13 65, O15 64, O16 spring-context 108, O18 54; O01, O04, O10 spring-core 77; O02, O17, O19, O20 spring-context 92; O06 spring-web 202, spring-webflux 207, spring-test 253; O07 spring-webflux 195, spring-webmvc 184; O08 spring-web 202, spring-webflux 207, spring-webmvc 196; O09 spring-web 202, spring-webflux 195; O12 spring-jdbc 56. The 7.x rows above come from `$O/scripts/digest_rows.py`; a class the landing touches in two modules is prefixed with its module.

## Commands for a rerun by hand

Every build below is over a minute, so outside a job it is a probe at most; the caches are filled, so all run `--offline`.

```bash
source ~/.cache/in-the-loop/spring-pr-links-o01-o20/scripts/env.sh
# one case's job steps (CASE in O01..O10, O12, O13, O15..O20; STEP fix | parent | transplant | clean | dryrun)
bash $O/scripts/case_job.sh CASE STEP
# any task in a worktree, with the Gradle and JDKs that worktree needs (log $O/logs/TAG.log)
$O/scripts/gradle_case.sh $W/O02-fix TAG "spring-context/build/test-results/test" \
  -Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g --offline \
  :spring-context:test --tests org.springframework.scheduling.support.CronExpressionTests
# a classpath of any project and configuration, offline
$O/scripts/gradle_case.sh $W/O02-fix TAG "" --offline -I $O/scripts/resolve-all.init.gradle \
  :spring-context:setupWriteClasspath -PsetupCpConf=testRuntimeClasspath -PsetupCpOut=$O/tmp/cp.txt
```

A worktree whose `clean` step ran has no `buildSrc/build`; the next offline run compiles `buildSrc` again (its dependencies are
cached). Every project's every configuration was resolved, so modules beyond the case's (spring-tx, spring-orm, …) also build
offline. The `later` worktrees (`O01-later`, `O17-later`, `O20-later`) were resolved too but never built.

## What failed or was not done

- **O11 and O14 are not built** (sections above): their build scripts need artifacts that are in no public repository
  (propdeps-plugin 0.0.8, docbook-reference-plugin 0.3.1; Kotlin 1.4-M2). No substitute was put in.
- Refused by servers (401, anonymous): `repo.spring.io/release`, `plugins-release(-local)`, `plugins-snapshot`, `libs-release(-local)`,
  `libs-snapshot`, `libs-milestone`. Nothing the 7.x and 6.x builds needed was only there.
- Unchecked signatures: Spring 5.0.0.M5 jars (key `23EF3D2F93185045`), Spring 5.2.7.RELEASE, Reactor 3.3.6.RELEASE and R2DBC 0.8.x
  jars (key `9A2C7A98E457C53D`), reactive-streams 1.0.3 (`1364C5E2DF3E99C5`): keys not obtainable from keyserver.ubuntu.com or
  keys.openpgp.org; milestones (5.0.0.RC1, 5.3.0-M1, reactor 3.4.0-M1) publish no `.asc`. Their sha1s match the repositories'.
  Gradle 3.4's wrapper jar has no published checksum (unused). Liberica publishes sha1 only.
- Not run: the O17 `later` revision's dedicated unit test and the other `later` revisions (outside the comparison by the brief);
  the whole module test suites (only the landed classes run).
- Two first-pass resolutions (O07 parent, O15 parent) and three O16 passes failed once, the first two because this session
  rewrote the runner script while they ran, O16 for want of the Liberica JDK; all reran cleanly.

Disk after setup, all jobs done and cleaned: `$O` 17 GB in all: worktrees 3.8 GB, `gradle-home` 10 GB, Gradle distributions
and the Liberica JDK 2.2 GB, downloads 209 MB, Maven repository and release sets 62 MB, kept artifacts 327 MB; the mirror
`~/.cache/in-the-loop/git-mirrors/spring-framework.git` 211 MB. The Gradle zips were deleted after their digests were recorded (the `.sha256` files stay).

## Setup Agent Notes

### What is ready, and where

- **Sources.** All 40 pins, plus the three `later` revisions the brief names, as worktrees `~/.cache/in-the-loop/spring-pr-links-o01-o20/worktrees/CASE-ROLE`
  (ROLE `parent` = before pin, `fix` = after pin, `later`), from the shared mirror `~/.cache/in-the-loop/git-mirrors/spring-framework.git`.
  Every PR's merge commit equals the after pin; every landed diff names exactly the PR's files; signed pins verify
  ([Upstream revisions](#upstream-revisions), full ids in its table).
- **Offline builds for 18 cases** (all but O11 and O14). Every configuration of every project is resolved into
  `$O/gradle-home`; `source $O/scripts/env.sh` then `$O/scripts/gradle_case.sh WORKTREE TAG "" --offline TASKS` picks the right
  Gradle (verified distributions in `$O/tools/`) and JDK ([Build facts](#build-facts-by-era), [Commands](#commands-for-a-rerun-by-hand)).
  `$O/scripts/case_job.sh CASE STEP` reruns a case's job steps.
- **Built jars, class digests and classpaths** per case and pin in `$O/artifacts/CASE-ROLE/` (`jars/`, `SHA256SUMS`,
  `M.runtimeClasspath.txt`, `M.testRuntimeClasspath.txt`, `:`-joined, project jars copied under `tree/`). Digests: the table in
  [Digests of the built artifacts](#digests-of-the-built-artifacts), all 18 cases.
- **Released artifacts** in `$O/releases/SET/` (`jars/`, `classpath.txt`): spring-test 5.3.26 (the reporter's version for O03);
  spring-jdbc 5.0.0.M5 and 5.0.0.RC1 (O11); spring-tx 5.2.7.RELEASE and 5.3.0-M1 with their Reactor, and spring-r2dbc 5.3.0-M1 with
  r2dbc-h2 and H2 (O14); pgJDBC 42.7.15 ([Released artifacts](#released-artifacts)).
- **PostgreSQL** for O11's driver read: `postgres@sha256:0d938e975177bef9f1f61f3f9dbcf2e0aa0a139568f66d3415ed8892eb97f6ac` (17.12) is
  in local Docker; the smoke command is in [Released artifacts](#released-artifacts).

### What was verified on a JVM

- 6.x cases, by their jobs (all steps passed): each landed test class passes at the fix and its parent version passes at the
  parent; the fix's test files on the parent **fail** for O15 (`testPropagationNestedWithExistingTransaction`), O16 (11 of 20
  `ClassPathXmlApplicationContextTests`, context creation fails) and O18
  (`testWithConnectionFactoryAndExceptionListenerAndReconnectOnExceptionWithJMSException`), and **do not compile** for O03, O05 and
  O13 (the API they use is new in the landing). Row by row in [Job results](#job-results).
- 7.x cases, by their jobs (all steps passed): the same holds for O01, O02, O04, O06, O07, O09, O10, O12, O17, O19 and O20,
  whose transplanted tests all compile and **fail** on the parent; for O08 the spring-web tests **do not compile** (they call the new
  `HttpRange.resolveRanges(HttpHeaders,HttpHeaders)`) and the webmvc and webflux If-Range tests **fail**. In O10 only the
  synchronous joined-buffer test fails on the parent, the asynchronous one passes; in O20 the Flux context tests fail, `cacheableMonoPropagatesContextOnCacheMiss` passes. Row by row, with every failing test named, in [Job results](#job-results).
- O11, O14: no build, no test run. Only the source comparison with releases (below).
- pgJDBC 42.7.15 connects to the PostgreSQL 17.12 image. No query from the brief was run anywhere.

### What to know before starting

- **O11 (#1366) and O14 (#25256) have no historical build** ([why](#o11-and-o14-the-historical-builds-cannot-be-configured)). The
  released files that equal the pins: O11 parent's `NamedParameterUtils.java` is byte-identical in spring-jdbc 5.0.0.M5; the fix's
  differs from 5.0.0.RC1's only in the copyright line. O14 parent's `TransactionalOperatorImpl.java` and
  `TransactionalOperatorExtensions.kt` are identical in spring-tx 5.2.7.RELEASE and 5.2.8.RELEASE, the fix's in 5.3.0-M1;
  `TransactionAspectSupport.java` differs from both releases (outside the reactive path; diffs described in that section). The rest
  of each release moved; whether to use a release, a source slice or neither is yours. The O14 pins have no spring-r2dbc module.
- **Snapshots.** The 7.1.0-SNAPSHOT builds take Reactor 3.9.0-SNAPSHOT, reactor-netty 1.4.0-SNAPSHOT and Micrometer 1.18.0-SNAPSHOT
  as cached on 2026-11-25 (digests in [Snapshot artifacts](#snapshot-artifacts)), the same bytes for both pins of a case, not the
  bytes of each pin's date. Build `--offline` to keep them.
- **O16 needs the Liberica JDK** (`$JL17`): the build demands toolchain vendor BELLSOFT; `gradle_case.sh` passes it.
- Default `java` on `PATH` is 25.0.5. The 7.x builds compile on toolchain 25 with `release` 17; the 6.x builds on JDK 17.
- The brief's database choices are open: O11 names no pgJDBC version (42.7.15 here is this setup's pick, the current release);
  O12's readback, O14's and O15's transaction-aware R2DBC writes need a driver the brief leaves open. On the kept test runtime
  classpaths: spring-jdbc has H2, HSQLDB and Derby (optional dependencies); spring-r2dbc has r2dbc-h2 (check
  `$O/artifacts/CASE-ROLE/M.testRuntimeClasspath.txt`).
- O08 and O10 land as two commits (intermediate commits `8ab533263994e92f9660c9917a07cd3d8f8e769b`, `d8bc54d2e7d09d115dfb78381fbbac1ac0c90ab0`
  in the mirror); the brief compares the outer pins.

### What is left for the domain work on purpose

All claims, scenarios, fixtures and examples; choosing a stand-in (or none) for O11 and O14; choosing databases and drivers beyond
what is fetched; any run of the brief's own scenarios or predictions (the trailing-space SSE case, the strict-mode R2DBC mapper, the
`initConnection` JMS path, the `take(1)` placement, the cross-route If-Range matrix and the rest); the `later` revisions; and
example ids and folders.
