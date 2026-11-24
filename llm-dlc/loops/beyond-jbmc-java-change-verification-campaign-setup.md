# Setup for the beyond-JBMC Java change-verification campaign

Mechanical setup for [`beyond-jbmc-java-change-verification-campaign.md`](beyond-jbmc-java-change-verification-campaign.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. The session:
- recorded the starting commit, the checker binary, both JDKs and both JBMC 6.11.0 packages;
- checked the archived 187-case benchmark file and matched its IDs to the case catalog at this head;
- resolved 42 release graphs from Maven Central, with sources, and checked every jar against Central's checksums and
  signatures;
- pinned the three upstream revisions the brief links (Commons Codec, protobuf, SV-Benchmarks);
- extracted and disassembled the classes the casebook names;
- replayed the twelve SV-Benchmarks tasks with typed choice streams;
- reproduced on a JVM the observations the casebook states for released artifacts.

It wrote no claims, examples, sidecars, adapters, recipes or checker code, allocated no example ids, and ran neither
the project verifier nor JBMC on any claim. It did not draw, see or seal the 16-upgrade blind panel. Everything it
fetched or built is outside the checkout. **No verification job was needed**: every JVM check took seconds, and the
brief names no upstream build or upstream test run.

`$B` below is `~/.cache/in-the-loop/beyond-jbmc`. `$J21` is Temurin 21.0.13+9, `~/.sdkman/candidates/java/21.0.13.0+9-tem/bin`,
and `$J25` is Temurin 25.0.5+8, `~/.sdkman/candidates/java/25.0.5.0+8-tem/bin`. **The default `java` on `PATH` is
JDK 25.0.5**, so name JDK 21 by its full path.

## Starting commit and tools

- The brief's baseline is `867fa025a5b4ee4fecf312a3bd304c3c831c8e3d` (`lib/` tree `8313a4b39110ad43966113da92048f7c3c93c5f4`).
- This setup ran at `9920f659e67c1aea4aa114c59c93813dbd61b69d` ("Merge the queued run trusted-kernel-and-receiver-recovery-2
  into the line"), with `867fa025` an ancestor. Its `lib/` tree is `d098b73a0d1057ff165395c6551fc8f67f6a9c44`. The last
  change to the checker sources is `850595ae1e2f91815eee3b5822cd640f96eed630`, so `lib/` differs from the baseline.

| Tool | Where | sha256 / identity |
|---|---|---|
| `jvmcontract` release, built at `9920f659` | `lib/target/release/jvmcontract` | `f02a6de8c6298109711f9cc4f81fb00c84168cfb276abfd57c1e1ab4dc6f9ca6`. `cargo build --release --bin jvmcontract` recompiled it, 2 min 58 s (`$B/logs/cargo-build-release.log`). The previous record's binary `a61246d28d07c5f63df21694b7ec1484b26a06b79faad7b532579e10c95afa28` was built before the last `lib/` changes. |
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` | `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c` (= the earlier setups) |
| Temurin 25.0.5+8 (the historical profile; `java -version` = the archived `environment.java`) | `~/.sdkman/candidates/java/25.0.5.0+8-tem` | `lib/modules` `f5463cffa81c51b3c13f57e2c23eacceab2b12e842069acf2facd5485f63bc85` |
| JBMC 6.11.0, Ubuntu 24.04 package (installed, on `PATH`) | `/usr/bin/jbmc`, `/usr/lib/core-models.jar` | `200f4cbb273d94268cdf933ee1f7c5ea96c8abc95af83836c2ffc082a722ec35`; models `a31ef93bfe898d373bb7eca6aef3b9ee2ebf05b0fe8efb305f86528396ea49df` |
| JBMC 6.11.0, Ubuntu 22.04 package | `~/.cache/in-the-loop/jbmc-java-semantics-gap/releases/cbmc-6.11.0/ubuntu-22.04/{bin/jbmc,lib/core-models.jar}` | `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c`; models `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de` |
| Maven / Gradle | on `PATH` | 3.10.0 / 9.8.2 |

Both JBMC packages report `6.11.0 (cbmc-6.11.0)`; their two `core-models.jar` differ. The earlier setups' digests for
both are unchanged ([fast-follow setup](jbmc-fast-follow-calls-conversions-and-arrays-setup.md#jbmc-6110)). The archived
benchmark names only the version string, not the package.

## The historical 187

- `lib/benchmark/results.json` at this head and at `867fa025` has sha256
  `14c25280da82eaba7116753d704c33527aedf0e2008ff0eb664a805068d1de75` (= brief). It was last changed by `6e584f2e268a96b675edbc3b1f141248c29ff590`.
  Its `environment` names commit `c9995ae17d82df1eceb185e55ccd55182b29a7f1` and job `20261107-183709-vf-014-a-fresh-lib-benchmark-results-jso`.
  The settings are timeout 120, unwind 16, maxArrayLength 8, referenceSearch 200000, groups 1–4, all three engines,
  modes and stagings.
- **Unmodified copy**: `$B/historical/results-867fa025.json`, read-only, the same sha256.
- `cases` holds **187 unique IDs**: group 1 160, group 2 13, group 3 12, group 4 2 (`example/141`, `example/142`).
- `run.load_cases({1,2,3,4})` at this head returns **188 cases**. All 187 historical IDs are present, with the same
  `group`, `workload`, `kind` and `expected`. The extra one is `conformance/mapCapacity/2`, new since `c9995ae1`, so
  pass the 187 IDs through `run(options, case_ids=...)`.
- What changed in the inputs since `c9995ae1`:

| Input | `c9995ae1` → this head |
|---|---|
| `lib/benchmark/corpus.json` | unchanged, `ec24aeb8ca6c7eaa6fe154dfbb9f30f808c9837efeff135b4e371991f1dc902c` |
| `lib/benchmark/Reference.java` | unchanged, `e0b7b6afd68f27d2c43b29ef92cbff71d11c390bba212d2a824db657a20ce291` |
| `lib/tests/conformance/Runner.java` | unchanged, `64362c765effed0b94f916b3ac871b179b5e2756a5a972ed21f492729f89d131` |
| `lib/benchmark/conformance.json` | `aec8f6fb34f707a07c39ea236ab3e204c158f362e2447c16e4a8c39aeb495c2e` → `16582cd92016a2833692734a04c0ba3e8297a351db60a4eba4846b10b7df96ae`. One case added (`mapCapacity/2`). In 22 historical cases only the `nativeStrict` annotation changed (for example `listSizes/1` unverifiable → verified); no other field changed. |
| `lib/tests/conformance/conformance/Conformance.java` | `53000a632df563a2148b3994d1b942dad096b1eb1781c253b793637c791e51c7` → `ddea8abdafc871f693a2432e18de2f7d3126ff15b0f673efb0c9393e7cf869f3`: 22 lines added (interface `Source`, `sourceSize`, `sourceNameLength`, `sourceTriangle`), none removed. Line numbers after the insertion moved. |
| `lib/benchmark/run.py` | `RECORDED` unchanged (`141`, `142`); 114 lines changed elsewhere (selection, provenance). `examples/141-*` and `examples/142-*` unchanged. |

No benchmark run was made. The fresh opening and closing matrices are the domain work.

## Released artifacts

**Graphs.** One throwaway POM per graph (`$B/resolve/NAME/pom.xml`, from `$B/scripts/graphs.tsv` by
`$B/scripts/resolve.sh`), resolved with `mvn --strict-checksums` into `$B/m2` (settings `$B/maven-settings.xml`). Each
`$B/releases/NAME/` holds `lib/` (runtime jars), `sources/` (sources jars), `tree.txt` and `classpath.txt` (ordered,
colon-separated). The files in `lib/` and `sources/` are hard links into `$B/m2`.

**Checks.** Every one of the 167 distinct jars (main and sources) was compared with a fresh copy of Central's `.sha1`.
All 167 match, and the 38 `.sha512` Central publishes also match (`$B/logs/central-checksums.tsv`). Each `.asc` was
verified in this setup's own keyring (`GNUPGHOME=$B/gnupg`, keys from keyserver.ubuntu.com): 165 `GOODSIG` and 2
`EXPKEYSIG` (`$B/logs/signatures.tsv`). The two are JTS 1.18.2 jar and sources: James Hughes `0E9BD9062B021BBA50F41EEB9549F6CB1E679A56`,
signature made 2021-08-27, key expired 2022-03-20, so it was signed while the key was live. The gpg agent was stopped.
All jar digests: `$B/logs/release-jars.sha256`.

**Brief digests.** All seven in the brief's table match: lucene-core 8.11.0 and 9.0.0, vecmath 1.5.2, spring-core 6.1.14
and 6.2.0, protobuf-java 3.25.5 and 4.33.0. Lang 3.17.0 and Guava 33.4.8-jre equal the earlier setups' digests.

| Release (`$B/releases/…`) | Main jar | sha256 | Signer (fingerprint) |
|---|---|---|---|
| `lucene-core-8.11.0` | `lucene-core-8.11.0.jar` | `5069436519426486f74a84a77763895ec9ace807929dc931ab36760893cb8267` | Adrien Grand (CODE SIGNING KEY) `E6E21FFCDCEA14C95910EA65051A0FAF76BC6507` |
| `lucene-core-9.0.0` | `lucene-core-9.0.0.jar` | `f03aa0afc676ac80d111189c235974e6f4c628182e511aeb7e58b01db577c91a` | Adrien Grand (CODE SIGNING KEY) `E6E21FFCDCEA14C95910EA65051A0FAF76BC6507` |
| `protobuf-java-3.25.5` | `protobuf-java-3.25.5.jar` | `8540247fad9e06baefa8fb45eb313802d019f485f14300e0f9d6b556ed88e753` | Protobuf Release `1A55F091AD28C07F831FA44D7905DE25C78AD456` |
| `protobuf-java-4.28.3` | `protobuf-java-4.28.3.jar` | `ba02977c0fef8b40af9f85fe69af362d8e13f2685b49a9752750b18da726157e` | Protobuf Release `1A55F091AD28C07F831FA44D7905DE25C78AD456` |
| `protobuf-java-4.33.0` | `protobuf-java-4.33.0.jar` | `6c50b4323a101dfd7b8aea209337ac49ecf5d8e33e0b210b196fc654291ed2cc` | Protobuf Release `1A55F091AD28C07F831FA44D7905DE25C78AD456` |
| `vecmath-1.5.2` | `vecmath-1.5.2.jar` | `3558e81ca74c60dc01baca7ef05f48594bbaed43af45d4f1b9196e479734e675` | Martin Wolfgang Kirst `4C1D22A7676CDD9E2FEC929F79F983E12B7518D1` |
| `jackson-core-2.19.0` | `jackson-core-2.19.0.jar` | `da8e859bac94874528116a25f20c68560e4287acbf27628711b8a4f96b028430` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.1` | `jackson-core-2.17.1.jar` | `ddb26c8a1f1a84535e8213c48b35b253370434e3287b3cf15777856fc4e58ce6` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.1` | `jackson-databind-2.17.1.jar` | `b6ca2f7d5b1ab245cec5495ec339773d2d90554c48592590673fb18f4400a948` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.1` | `jackson-annotations-2.17.1.jar` | `fccad82e13172c0e4384db71577219c9b8631c0820f4b18daaa57016fb661c76` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.2` | `jackson-core-2.17.2.jar` | `721a189241dab0525d9e858e5cb604d3ecc0ede081e2de77d6f34fa5779a5b46` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.2` | `jackson-databind-2.17.2.jar` | `c04993f33c0f845342653784f14f38373d005280e6359db5f808701cfae73c0c` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `jackson-2.17.2` | `jackson-annotations-2.17.2.jar` | `873a606e23507969f9bbbea939d5e19274a88775ea5a169ba7e2d795aa5156e1` | Tatu Saloranta (cowtowncoder) `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |
| `commons-lang3-3.17.0` | `commons-lang3-3.17.0.jar` | `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4` | Gary David Gregory (Code signing key) `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` |
| `guava-33.4.8-jre` | `guava-33.4.8-jre.jar` | `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed` | Christopher Povirk `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` |
| `commons-numbers-1.1` | `commons-numbers-field-1.1.jar` | `dc7d8e17afdd4a0fe44107ddb6202d5eb5749fc60fec65712e30ec58b3e7d2f2` | Alex Herbert (CODE SIGNING KEY) `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` |
| `commons-numbers-1.1` | `commons-numbers-core-1.1.jar` | `966896d9bb1e77cdd13830738acbcda22daeba57b4b093f7f4167828add95b58` | Alex Herbert (CODE SIGNING KEY) `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` |
| `commons-numbers-1.2` | `commons-numbers-field-1.2.jar` | `8c12ee361b999c74ddce80a45a72a7e258a82697e9a99cf7f171bc63dda080fa` | Alex Herbert (CODE SIGNING KEY) `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` |
| `commons-numbers-1.2` | `commons-numbers-core-1.2.jar` | `8664f1183ed71d3ec7ad290a348060f101e828366c228aad64eb6d2fd80950ff` | Alex Herbert (CODE SIGNING KEY) `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` |
| `jts-core-1.18.2` | `jts-core-1.18.2.jar` | `8cd3d3f31c990482b0a0ae2786fc3864ffa8a76303ccd1b6cbdaaba7dddd899b` | James Hughes `0E9BD9062B021BBA50F41EEB9549F6CB1E679A56` **EXPKEYSIG** |
| `jts-core-1.20.0` | `jts-core-1.20.0.jar` | `6a783d8f9dba3d3cf7265435f134402f63c05838aa6cbcc4297ad3a5b2842baf` | Jody Garnett `6EB0DED2F354B5D1DD24006168127E5CB45F41F3` |
| `commons-math3-3.6.1` | `commons-math3-3.6.1.jar` | `1e56d7b058d28b65abd256b8458e3885b674c1d588fa43cd7d1cbb9c7ef2b308` | Evan Ward `41A1A08C62FCA78B79D3081164A16FAAEC16A4BE` |
| `pcollections-3.1.4` | `pcollections-3.1.4.jar` | `34f579ba075c8da2c8a0fedd0f04e21eac2fb6c660d90d0fabb573e8b4dc6918` | Harold Cooper `E0D98C5FD55A8AF232290E58DEE12B9896F97E34` |
| `pcollections-4.0.2` | `pcollections-4.0.2.jar` | `2bbeef5797a241300c4f7513cd546239629ed7deda4fc0c31df90bb95f5f13ef` | Harold Cooper `E0D98C5FD55A8AF232290E58DEE12B9896F97E34` |
| `jsoup-1.18.1` | `jsoup-1.18.1.jar` | `3bb5b0ec02998abe45a51f37d7ce67c3068b4ccd4ab63c965929ec5074d64e91` | Jonathan Hedley `F3184BCD55F4D016E30D4C9BF42E87F9665015C9` |
| `jsoup-1.18.2` | `jsoup-1.18.2.jar` | `5e02a47f28af283e12477784e1b06ffbcb76be70212a19ddf4be6b9451b5bcb2` | Jonathan Hedley `F3184BCD55F4D016E30D4C9BF42E87F9665015C9` |
| `jsoup-1.18.3` | `jsoup-1.18.3.jar` | `5be1ccd3228ae5fd6eed1bd6d827bac2bc65b91c20e9957d16ea65f739f15302` | Jonathan Hedley `F3184BCD55F4D016E30D4C9BF42E87F9665015C9` |
| `spring-6.1.14` | `spring-core-6.1.14.jar` | `e15a1179fc9642ffed13ca55e2863e2da524ccd1083b7c6f1b5cfd5733f3b2c5` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.1.14` | `spring-context-6.1.14.jar` | `da76b53f6a20f09b38052a300435f3245780d30deb46ec5dd75314cda06fd365` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.2.0` | `spring-core-6.2.0.jar` | `3b82629da38717dd616a70ec1055f9a8e208d58132071a6314a32159f8bce162` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.2.0` | `spring-context-6.2.0.jar` | `a0d2de9df7902edc5f6ae55e2936327bdeac177dbc5392906b8d36f3691fe121` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.1.3` | `spring-core-6.1.3.jar` | `f4448994a1eb4892b805020e7952aa96a8e3f101b7093a632635d2b0bab887eb` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.1.3` | `spring-context-6.1.3.jar` | `48801f87034b107f66a199d946cf1f2d5c32b39d5345ca4f4bb26ac60159839e` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.2.3` | `spring-core-6.2.3.jar` | `49531684df2304f0e611f775faba79273c77504eb7d856592d830e2389e9eb14` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `spring-6.2.3` | `spring-context-6.2.3.jar` | `53feea6d8c61a25089d8c474c4f92ebd24f0ef7eb52ecdaf46f11e9a253fdb4e` | Spring Builds (JAR Signing) `48B086A7D843CFA258E83286928FBF39003C0425` |
| `commons-codec-1.13` | `commons-codec-1.13.jar` | `61f7a3079e92b9fdd605238d0295af5fd11ac411a0a0af48deace1f6c5ffa072` | Gary David Gregory (Code signing key) `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` |
| `commons-codec-1.14` | `commons-codec-1.14.jar` | `a128e4f93fabe5381ded64cf2873019e06030b718eb43ceeae0b0e5d17ad33e9` | Gary David Gregory (Code signing key) `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` |
| `commons-codec-1.15` | `commons-codec-1.15.jar` | `b3e9f6d63a790109bf0d056611fbed1cf69055826defeb9894a71369d246ed63` | Alex Herbert (CODE SIGNING KEY) `BC87A3FD0A54480F0BADBEBD21939FF0CA2A6567` |
| `joda-time-2.12.0` | `joda-time-2.12.0.jar` | `e7541834295efb4efb537a9af20aa7bd41aff250b32a91856dbe4b36b22c6256` | Stephen Colebourne (CODE SIGNING KEY) `B41089A2DA79B0FA5810252872385FF0AF338D52` |
| `joda-time-2.12.1` | `joda-time-2.12.1.jar` | `dbc55310dcaf336dd656fb764e0478b561335048d50257ff5c709ce409c9fdc8` | Stephen Colebourne (CODE SIGNING KEY) `B41089A2DA79B0FA5810252872385FF0AF338D52` |
| `semver4j-5.6.0` | `semver4j-5.6.0.jar` | `e66744e33e556f12816c50abec041488b348f922d29819cf4f6ab09ed252a755` | semver4j `45B1912987CB9DFA6A0D9693067091F1549B293F` |
| `semver4j-5.7.0` | `semver4j-5.7.0.jar` | `acf66a18cd69e7debbc2ea9576320c2e5fdd3cf5420daca924bbab14ee7b3103` | semver4j `45B1912987CB9DFA6A0D9693067091F1549B293F` |
| `semver4j-6.0.0` | `semver4j-6.0.0.jar` | `43d5e02f60e2b1f8ff0c92139f612a547691a1debe6bea32b0a70ba5a3bcbdd7` | semver4j `45B1912987CB9DFA6A0D9693067091F1549B293F` |
| `semver4j-6.1.0` | `semver4j-6.1.0.jar` | `c8a5c0d6253a4be09b60ba031d8541eb8452486689f0ab00008a5a00e8ea4233` | semver4j `45B1912987CB9DFA6A0D9693067091F1549B293F` |
| `RoaringBitmap-1.6.15` | `RoaringBitmap-1.6.15.jar` | `5ea0add939911c977289fc2dd542bd73faf39c521da79ef41e18b6cf2223e4fd` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.16` | `RoaringBitmap-1.6.16.jar` | `90690b7fd4e7c3dc63c8aa25e07b1e98a048756edc68d7a4ee635e5d9368cb62` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.17` | `RoaringBitmap-1.6.17.jar` | `4a827e19a0b1b56e3e522d4f31eb3609c29922d1c73155709c6e305b4e1363c4` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.18` | `RoaringBitmap-1.6.18.jar` | `b180d760d918ff6b70e2b01d93144bb64b7abe978004c10d14c769177a80bd46` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.25` | `RoaringBitmap-1.6.25.jar` | `e463f85d9a7f5f1d67ece01e5964c78854aae25438b7c3f16af0e420ad26108f` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.26` | `RoaringBitmap-1.6.26.jar` | `b0b664c2413cde67cc0eb85c3ebc28b0b70e3663ee437257a659954f53faf38e` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.27` | `RoaringBitmap-1.6.27.jar` | `f84d5e5b910b4bafe6df26d7ad34c0a57a28234e12c0d694ca4b162d2af7a8fb` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |
| `RoaringBitmap-1.6.28` | `RoaringBitmap-1.6.28.jar` | `44f326d533ffc1ad4d3a37f999d875d1bdd508dc066851d248217bcb97222bf8` | Daniel Lemire `015479E1055341431B4545AB72475FD306B9CAB7` |

Dependencies outside the table:
- Guava's graph: failureaccess 1.0.3, listenablefuture 9999.0, jspecify 1.0.0, error_prone_annotations 2.36.0, j2objc-annotations 3.0.0.
- commons-numbers-field brings commons-numbers-fraction at the same version.
- semver4j 5.6.0–6.0.0 bring jspecify 1.0.0, and 6.1.0 brings 1.0.1.
- Each Spring graph has spring-jcl, aop, beans and expression at its version, plus micrometer-observation and -commons:
  1.12.2 for 6.1.3, 1.12.11 for 6.1.14, 1.14.0 for 6.2.0 and 1.14.4 for 6.2.3.

Digests and signers for all of these are in `$B/logs/release-jars.sha256` and `$B/logs/signatures.tsv`.

**Commands.** To redo one graph: `$B/scripts/resolve.sh NAME COORDS...` (the line of `graphs.tsv`). It runs
`mvn -B -s $B/maven-settings.xml --strict-checksums dependency:copy-dependencies -DoutputDirectory=… -DincludeScope=runtime`
(again with `-Dclassifier=sources -DfailOnMissingClassifierArtifact=false`), then `dependency:tree`. **Offline works**:
every `classpath.txt` was written by `mvn -B -o -s $B/maven-settings.xml dependency:build-classpath
-Dmdep.outputFile=$B/releases/NAME/classpath.txt -DincludeScope=runtime`. The dependency plugin is in `$B/m2`.

**Not on the list.** The brief names no released version for the S03 formatter (#374), C07's unaffected zone,
or the E and H11–H14 fixtures, so nothing was fetched for them. PR #842, PR #888 and the jsoup and Spring issues are
release pairs here; their upstream commits were not pinned.

## Pinned sources

Partial bare mirrors (`--filter=blob:none`, depth 1, only the pinned commits) under `~/.cache/in-the-loop/git-mirrors/`,
refs `refs/pinned/NAME`, with a detached worktree in `$B/src/NAME`. To add one: `$B/scripts/mirror.sh URL MIRROR NAME SHA [SPARSE-DIR…]`.

| Worktree (`$B/src/`) | Commit | Tree | Identity |
|---|---|---|---|
| `commons-codec-c89d2af7` | `c89d2af770f05457fbefa5fb4713c888bf177fb2` | `af87e29671f44bd4683d41655adb0fe7c3d35bf9` | = tags `rel/commons-codec-1.15` and `commons-codec-1.15-RC1` (annotated); "Prepare for 1.15 release", 2020-08-28. The brief's MurmurHash3 link. |
| `protobuf-0a2f7757` (sparse: `java/`) | `0a2f7757e38b07c2e40c5c885a7100e8c16eb40f` | `c15e08b815750706ec6bfbf6938a4107d56d28b7` | **Not a release tag**: it is `refs/pull/15043/head`, "Branch-free varint size calculation", Protobuf Team Bot, 2023-12-14. The brief's "Protobuf release source" link. The released 3.25.5, 4.28.3 and 4.33.0 sources are the sources jars. |
| `sv-benchmarks-7efe28dd` (sparse: `java/`) | `7efe28dd29576b46927b7a34e8f742bd90966a75` | `821f141c93c2c8c324eaa962819037be94ea8041` | = tag `svcomp26` (annotated tag object `d3c6ac0522e86d2b37c7add407db4aedf88559bf`) and `testcomp26`. GitLab. |
| (mirror ref only) `sv-benchmarks-svcomp26-rc1` | `e8b309124df9bee33baf12bd47c629245971fce7` | — | = tag `svcomp26-rc.1`, **the revision the published SV-COMP 26 JBMC run used** (its provenance: `svcomp26-rc.1-0-ge8b309124df`) |

**The twelve B tasks are the same at both SV-Benchmarks revisions.** Their directories, `.yml` files, `java/common`
and `properties/valid-assert.prp` have identical git object ids at `e8b30912` and `7efe28dd`
(`java/common` tree `4780f7522804f8b4d3cbedd5c86395d9a950be41`, `valid-assert.prp` blob `a9d5a52b46054c05e2e25cd21faf90b75a729f18`).
File digests: `$B/logs/sv-tasks.sha256`.

**Official results.** `$B/svcomp/results.xml.bz2` (sha256 `f3e17836d3863f21c912a6bdd0ce187580b89382187488940e0715abdeed0f35`)
and `table.html` (`305657483d4cca85b830ca926ddc691a2f8a38608e366accbb1f9ff686eddba1`) are the brief's `[svres]` URL
and its XML. The run was JBMC `6.8.0 (cbmc-6.8.0-10-g4767cf5d65)`, 900 s, 15 GB, 4 cores, `--graphml-witness witness.graphml`.

| ID | Task (`java/…`) | Expected | Published status | CPU s |
|---|---|---|---|---|
| B01 | `jbmc-regression/StringBuilderCapLen01` | true | true | 1.41 |
| B02 | `jbmc-regression/StringBuilderCapLen02` | false | false | 5.85 |
| B03 | `jbmc-regression/StringBuilderInsertDelete01` | true | true | 1.17 |
| B04 | `jbmc-regression/StringBuilderInsertDelete02` | false | unknown | 4.32 |
| B05 | `jayhorn-recursive/SatFibonacci02` | true | true | 1.03 |
| B06 | `jayhorn-recursive/UnsatFibonacci02` | false | false | 6.17 |
| B07 | `jayhorn-recursive/SatEvenOdd01` | true | ERROR (42) | 877.28 |
| B08 | `jayhorn-recursive/UnsatEvenOdd01` | false | false | 1.04 |
| B09 | `algorithms/BinaryTreeSearch-FunSat01` | true | ERROR (42) | 876.81 |
| B10 | `algorithms/BinaryTreeSearch-FunUnsat01` | false | false | 2.64 |
| B11 | `algorithms/InsertionSort-FunSat01` | true | OUT OF MEMORY | 236.06 |
| B12 | `algorithms/InsertionSort-FunUnsat01` | false | false | 1.09 |

Every status equals the brief's table. Each `.yml` also declares `no-runtime-exception.prp`, expected true.

## Class entries

`$B/scripts/extract.sh RELEASE JAR CLASS…` unzips each named class with its inner classes into `$B/classes/RELEASE/`,
and writes `javap -c -p -v` of each top-level class to `$B/logs/javap/RELEASE/CLASS.txt`. There are 300 entries
(`$B/logs/classes.sha256`):
- Lucene `store/ByteArrayDataOutput`, `ByteArrayDataInput`, `DataOutput`, `DataInput` and `util/BitUtil`;
- vecmath `Tuple2f`, `Vector2f`;
- Jackson `io/NumberInput`, 2.17.1, 2.17.2 and 2.19.0;
- Lang `NumberUtils`, `StringUtils`, `CharSequenceUtils`, `ArrayUtils`, `MutableInt`, `MutableObject`;
- Guava `Ascii`; Numbers `FP64`; JTS `Orientation`, `CGAlgorithmsDD`; Math `Vector2D`;
- protobuf `CodedOutputStream`, `CodedInputStream`; PCollections `TreePVector`;
- RoaringBitmap `IntIteratorFlyweight`, `ReverseIntIteratorFlyweight`, `RoaringBitmap` and the three containers, for
  all eight versions;
- jsoup `FormElement`, `Attribute`, `Attributes`; Spring `GenericTypeResolver`, `ResolvableType`, `BridgeMethodResolver`;
- Codec `MurmurHash3`;
- Joda `DateTimeZone`, `tz/ZoneInfoProvider` and the compiled zone resource `tz/data/America/Mexico_City`;
- semver4j `Semver`.

**Class-file major versions** (first top-level class of each jar):
- 49: commons-math3 3.6.1, joda-time 2.12.x;
- 50: vecmath 1.5.2, pcollections 3.1.4;
- 51: commons-codec 1.13–1.15;
- 52: Lucene 8.11.0, protobuf, Jackson, Lang, Guava, Numbers, JTS, pcollections 4.0.2, RoaringBitmap, jsoup, semver4j 5.x;
- **55: lucene-core 9.0.0**;
- **61: Spring 6.x and semver4j 6.x**.

| Entry (`$B/classes/…`) | sha256 |
|---|---|
| `lucene-core-8.11.0/org/apache/lucene/store/ByteArrayDataOutput.class` | `345aee36fd0e36a98191dff65ed3ca2552390821605e51e153be6d918801e7e8` |
| `lucene-core-8.11.0/org/apache/lucene/store/ByteArrayDataInput.class` | `182cfde9fa11d3063762e3bd2a1095e442d1e26ef02a27b459ed8747a3193664` |
| `lucene-core-8.11.0/org/apache/lucene/util/BitUtil.class` | `08c7301d3062b95ed3c7436bb449fb5c9c2793e7fa9fa471a4d302aeab497457` |
| `lucene-core-9.0.0/org/apache/lucene/store/ByteArrayDataOutput.class` | `5bb17be51a09c9fc604120e8f210dddf803150ebdf28a7de7a6fcae37f034b9f` |
| `lucene-core-9.0.0/org/apache/lucene/store/ByteArrayDataInput.class` | `ecc4294b2c044e52adb577607855dad3ef3c0f2bff75f8e38f270be85de94943` |
| `lucene-core-9.0.0/org/apache/lucene/util/BitUtil.class` | `80b86176fe8bed93aa307b698d86bc21fa95ca27f51bf02de29a4e29ceac64f8` |
| `vecmath-1.5.2/javax/vecmath/Tuple2f.class` | `55cc73464f410d9d962129fd843bf461d44ff14d06181809d8b3a0b233c165d5` |
| `jackson-2.17.1/com/fasterxml/jackson/core/io/NumberInput.class` | `6246ef3766dd1e6691a809a4b8de92b6ccc1a55462f645c2deda3f026f31fe1c` |
| `jackson-2.17.2/com/fasterxml/jackson/core/io/NumberInput.class` | `22ac035670ca04eb345a5fe157581503ec9e779b11c0a2da209faa822516eeea` |
| `jackson-core-2.19.0/com/fasterxml/jackson/core/io/NumberInput.class` | `78b9b939d828df341d82cc26042b61af6ba5a97b67fae1c26cef898e9362f6e8` |
| `commons-numbers-1.1/org/apache/commons/numbers/field/FP64.class` | `91fd1b05dd02e16cf565c6ba8f907d8d6814d9148aabae4b34cf7b54437a553e` |
| `commons-numbers-1.2/org/apache/commons/numbers/field/FP64.class` | `0204bf9fa50fd19b6f9e0f407d74425714ab5bd0aa828fd40ec1a0ed5fa4fc47` |
| `commons-codec-1.13/org/apache/commons/codec/digest/MurmurHash3.class` | `a02592bcb2a95b6a7cceecd38674ea8480e07989ea5f52a2837f127bfa63c1c9` |
| `commons-codec-1.14/org/apache/commons/codec/digest/MurmurHash3.class` | `69a0315c33c1e7d02f82f56fb878b3b5473e927e77d03ee3010c3858a67e1813` |
| `commons-codec-1.15/org/apache/commons/codec/digest/MurmurHash3.class` | `0178269ac4dbbb80fffd0e92caa5dd1d07d3dab8b3f9459414c6b1d326730a70` |
| `joda-time-2.12.0/org/joda/time/tz/data/America/Mexico_City` | `42fecf5d4cba34dc6ca8c29936a31670ced6ec1bcc716921f7b55c06baee18c7` |
| `joda-time-2.12.1/org/joda/time/tz/data/America/Mexico_City` | `7cb726bebcb0411b5196528417bd61db0eb36f32c6428757605c01b8dc2172be` |

## What was replayed on a JVM

All on Temurin 21.0.13 unless stated, inline, each in seconds. The probes are throwaway programs in `$B/probes/`, with
digests in each folder's `probes.sha256`, and their output is in `$B/logs/jvm-*.txt`. They are not claims, adapters
or drivers. Where the brief gives no grid, the values used are the probe's choice and are named in its source and
report.

### B · SV-Benchmarks witnesses

`$B/probes/sv/replay.sh JDKBIN` compiles each pinned task unchanged against the corpus's `java/common`. It then runs
the task with `-ea` and `$B/probes/sv/choice/…/Verifier.java` first on the classpath. That class has the corpus API, with
the nondeterminism replaced by a typed choice stream (`-Dsv.choices=i8`, `s` for an empty String). Output:
`$B/logs/jvm-sv-21.0.13.0+9-tem.txt` and `jvm-sv-25.0.5.0+8-tem.txt`. The two JDKs gave the same results.

| ID | Choices | JVM |
|---|---|---|
| B01, B03, B05 | none (fixed input) | exit 0, all assertions pass |
| B02 | `s` (empty) | `AssertionError` at `Main.java:14` |
| B04 | `s,s` | `AssertionError` at `Main.java:50` |
| B06 | `i8` | `AssertionError` at `Main.java:29` |
| B07 | `i0`, `i7` | exit 0 |
| B08 | `i0` (and `i1`) | `AssertionError` at `Main.java:43` both |
| B09 | `i3,i0,i5,i-1` | exit 0 |
| B10 | `i2,i0` | `AssertionError` at `Main.java:115`; `i2,i1` passes |
| B11 | `i5` | exit 0 |
| B12 | `i2,i0,i0` | `AssertionError` at `Main.java:65`; `i2,i0,i1` passes |

All six false-task witnesses of the brief reproduce, and B01 and B05 pass.

### S · Spring and reflection

Probes: `$B/probes/jvm/s/`, report `$B/probes/jvm/s/REPORT.md`. S04–S09 ran on Spring 6.1.3, 6.1.14, 6.2.0 and 6.2.3,
each in its own JVM, compiled once against 6.1.3 with `-parameters`.

| ID | Observed | Brief |
|---|---|---|
| S01 | The brief's `InterfaceShape.java` verbatim, `javac -source 8 -target 8 -g` (major 52): `intact()` true twice, `expected()` returns, `inverted()` throws `AssertionError`. Also: argument order (Enum<?>, String), the Enum argument is the wildcard `?` with upper bound [Object], and `getActualTypeArguments` and `getUpperBounds` hand out fresh arrays. | reproduces |
| S02 | `resolveType(...).getGeneric(0).getGeneric(0).resolve()` in String→Integer→String contexts: 6.1.3 and 6.1.14 null/null/null; 6.2.0 and 6.2.3 String/Integer/String. `ResolvableType.forMethodReturnType(get, ctx)` gives String/Integer/String on all four. The fixture is upstream `GenericTypeResolverTests.resolveNestedTypeVariable` (PR #30079, merge `e788aeb25baba51880b6c9cccbeb51fe5a6d401b`), plus an Integer subinterface. | reproduces |
| S04 | The bridge resolves to `name(String)` cold, warm, and after resolving the decoy. It equals `getDeclaredMethod("name", String.class)`, declaring class Impl. All versions. | reproduces |
| S05 | Merged lookup fills both aliases, direct lookup is null, and unequal values throw `AnnotationConfigurationException`. All versions. | reproduces |
| S06 | Empty → `ConverterNotFoundException`, +1 → 42, +2 (second `addConverter`) → 43, remove → not convertible. The second service is untouched throughout. All versions. | reproduces |
| S07 | String listener F,T,F,T; List<String> listener F,T,T,F, on all four versions. | reproduces |
| S08 | 6.1.x specific/page/page/page, 6.2.x specific/absent/page/page, in all 4 registration orders tried. The three intended injections keep identity. Fixture: `Spr16179Tests.java` at fix commit `7e67da8a267b1d41c3bd33fbd94dcf0b26e816c4` (#20727, 6.2.0-M1). | reproduces |
| S09 | `Converter<java.lang.Enum<?>, java.lang.String>` before mutation, after mutation and after `clearCache()`. | reproduces |

S03 was not run: it needs the historical source slices.

### W, N · wire formats and numerics

_In progress._

### H, C · histories and reuse

_In progress._

## Disk

`$B` is 188 MB with `m2` (the release folders are hard links into `m2`). Mirrors: commons-codec 0.8 MB, protobuf
1.4 MB, sv-benchmarks 37 MB. `$B/tmp` is the `TMPDIR` for this work. Nothing was left in `/tmp`.

## Setup Agent Notes

_Written when setup is complete._
