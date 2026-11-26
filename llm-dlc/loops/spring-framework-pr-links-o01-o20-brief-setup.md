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

## Jobs (verification pending)

The six Spring 6.x cases (O03, O05, O13, O15, O16, O18) are queued; the record of their results and of the other cases follows
in later commits of this setup.

- `20261126-001149-setup-build-spring-framework-30238-o03-a`
- `20261126-001149-setup-build-spring-framework-30045-o05-a`
- `20261126-001149-setup-build-spring-framework-30530-o13-a`
- `20261126-001149-setup-build-spring-framework-31133-o15-a`
- `20261126-001149-setup-build-spring-framework-31699-o16-a`
- `20261126-001149-setup-build-spring-framework-29116-o18-a`
