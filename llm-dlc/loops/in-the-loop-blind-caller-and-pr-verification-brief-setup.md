# Setup for the blind-caller and PR-verification brief

Mechanical setup for [`in-the-loop-blind-caller-and-pr-verification-brief.md`](in-the-loop-blind-caller-and-pr-verification-brief.md),
done by a setup session (Claude Opus 5.5) on 2026-11-27, before the domain work starts.

Earlier campaigns had already prepared every case the brief names: deployments, source worktrees at the pins, JDKs,
the MySQL and Postgres images, and the historical observers. This session:

- checked every deployment file of the 120 numbered examples the brief names against its recorded digest, and found
  a worktree at each pin. That covers the whole P/Q/R draw inventory (478–587), N01–N05 (453–457), the adverse
  controls M04, M06 and M09 (446, 448, 451), and Spring 458 and 466. It also checked J08, J14, Log4j #1173 and
  Commons IO #520 at the paths their readers use. **All match**;
- re-ran on the original JVMs, read-only, the registered observations of 458, 466, 484, J08, J14 and Commons IO. Each
  equals its committed receipt;
- prepared plain-JVM **upstream test launches**, without Gradle or Maven, for part B's two cases. For Spring #37193
  (466) that is the landed `ServerSentEventHttpMessageReaderTests`. For Parquet #3638 (J08) it is the whole
  `parquet-column` and `parquet-hadoop` test trees at both pins, over the original 113-entry graphs. It fetched only
  the test dependencies and launchers those needed, from Maven Central, with checksums and signatures checked, and
  ran the landed regressions both ways;
- queued two verification jobs: the five campaign replays at this head, and Parquet's full upstream suites. **Both
  passed** ([Verification jobs](#verification-jobs)): every P, Q, R, N and M audit replays byte-identical, and the
  Parquet suites differ between the graphs in exactly the two landed `TestDictionary` tests.

It wrote no claims, examples, sidecars, adapters, callers, recipes or library code, and allocated no example ids. It
ran no verifier or prover on a claim and did not run the product's change plan, `construct`, discovery or any
generator: those runs are the brief's measurements. It changed no repository file other than this record and the
two job files.

`$B` below is `~/.cache/in-the-loop/blind-caller-pr-verification`, this work's cache (88 MB). The other caches belong to earlier campaigns:

| Name | Path | Setup record |
|---|---|---|
| `$P` | `~/.cache/in-the-loop/spring-pr-links-p01-p30` | [P01–P30 setup](spring-framework-pr-links-p01-p30-brief-setup.md) |
| `$Q` | `~/.cache/in-the-loop/spring-pr-links-q01-q30` | [Q01–Q30 setup](spring-framework-pr-links-q01-q30-brief-setup.md) |
| `$R` | `~/.cache/in-the-loop/merged-pr-links-r01-r50` | [R01–R50 setup](organic-java-merged-pr-links-r01-r50-brief-setup.md) |
| `$N` | `~/.cache/in-the-loop/merged-pr-links-n01-n05` | [N01–N05 setup](organic-java-merged-pr-links-n01-n05-brief-setup.md) |
| `$M` | `~/.cache/in-the-loop/merged-pr-links-m01-m10` | [M01–M10 setup](organic-java-merged-pr-links-m01-m10-brief-setup.md) |
| `$O` | `~/.cache/in-the-loop/spring-pr-links-o01-o20` (458 = O01, 466 = O09) | [O01–O20 setup](spring-framework-pr-links-o01-o20-brief-setup.md) |
| `$P20` | `~/.cache/in-the-loop/organic-pr-20` (J08, J14) | [product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md) |
| `$FF` | `~/.cache/in-the-loop/organic-composition-ff` (Log4j, Commons IO) | [fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md) |

The brief-23 and brief-24 setups ([generated observers](in-the-loop-generated-observers-and-callers-brief-setup.md),
[JVM startup facts](in-the-loop-jvm-startup-facts-brief-setup.md)) and the
[classpath and entry discovery setup](in-the-loop-classpath-and-entry-discovery-brief-setup.md) cover the same cases
in more depth: changed production files with blob ids, the Log4j and J08 class digests, and the release panel.

## Starting commit

The brief's baseline is `develop` at `5f0b2389344879610f907ac9ee5b048dd59c9df8`. This setup ran at
`524b1fbd9277032681921afbeac09d218d156147` ("Merge the single-agent run jvm-startup-facts into the line", `develop@origin`),
and the baseline is its ancestor (`git merge-base --is-ancestor`). **Brief 24 (JVM startup facts) has landed at this head**,
with [results](in-the-loop-jvm-startup-facts-brief-results.md). Part D says to reuse it.

## Layout of `$B`

| Path | What it holds |
|---|---|
| `$B/scripts/` | `check_examples.py`, `check_inputs.py`, `physical_copy.py` and `io_observe.py` (copied from the brief-23 setup), `o09_upstream_test.sh`, `j08_upstream_tests.sh`, `j08_suite.sh`, `resolve.sh`, `verify_sigs.sh`. Digests in `$B/logs/scripts.sha256`, rewritten after the launch fix below: `j08_suite.sh` `43bf4aea056dada9b09b97ccafda01d9a7dfe86f543d14940a78f205d23aa4e8`, `j08_upstream_tests.sh` `892b0b18f5cf106fe1f08f74c3f6e273c5ffe8864ddc95bbac37efb4f947101b`. |
| `$B/logs/examples.json`, `inputs.json` | The digest and pin check of every example and input (below). |
| `$B/logs/audit-{p01-p30,q01-q30,r01-r50,n01-n05,m01-m10}.json` | Static (non-replay) audits, byte-identical to the committed `audit.json`. |
| `$B/logs/replay-{458,466,484}.txt`, `physical-J{08,14}.txt`, `io-observe.txt` | The JVM re-runs. |
| `$B/logs/o09-upstream-test-jdk{25,17}.txt`, `j08-overlay-TestDictionary.txt`, `j08-landed-and-writer-tests.txt`, `j08-TestParquetWriter-probe*.txt`, `j08-all-tests-compile-*.txt` | The upstream test launches. |
| `$B/logs/O09-{fix,parent}-spring-web-testRuntimeClasspath.sha256` | sha256 of all 202 entries of each O09 test runtime classpath. |
| `$B/logs/sigs-*.txt`, `releases.sha256` | Signature results and digests of every fetched jar. |
| `$B/m2`, `$B/maven-settings.xml`, `$B/resolve/`, `$B/releases/NAME/{lib,classpath.txt,tree.txt}` | Maven cache and the three resolved sets (below). |
| `$B/upstream-tests/O09/test-ROLE-on-ROLE/` | Compiled `ServerSentEventHttpMessageReaderTests` per pin (`SHA256SUMS`). |
| `$B/upstream-tests/J08/{fix,parent}/{classes,resources,sources.txt,compiled.txt,SHA256SUMS}` | Compiled `parquet-column` and `parquet-hadoop` test trees per pin. |
| `$B/upstream-tests/J08/reports/{fix-on-fix,parent-on-parent,fix-on-parent}/` | Job 2's suite runs: per module the candidate, excluded and run class lists, the launcher log, JUnit XML, and `summary.txt` (below). |
| `$B/logs/j08-cp-launch-fix-on-{fix,parent}.txt` | The probe of the corrected `-cp` launch (below). |
| `$B/probes/` | Scratch copies from the re-runs. **Evaluator material**: they hold historical observers and actual outcomes. |
| `$B/gnupg` | Private keyring; its daemons were stopped (`gpgconf --homedir $B/gnupg --kill all`). |
| `$B/tmp` | `TMPDIR` for this work. |

Nothing was added to `~/.cache/in-the-loop/git-mirrors/`: every pinned revision already had a worktree.

## Tools

| Tool | Where | Identity |
|---|---|---|
| Temurin 8u512-b09 | `~/.sdkman/candidates/java/8.0.512.0+9-tem` | `release` `b965ee876a40eb8b76e7146403b3efc54e309ebd573064a18c7b87665ce4d89e` |
| Temurin 11.0.33+10 | `~/.sdkman/candidates/java/11.0.33.0+10-tem` | `release` `065d95ec83774b32bf27d20a827c3b934b08ca2e77e80609711c9a77e83d6681` |
| Temurin 17.0.21+9 | `~/.sdkman/candidates/java/17.0.21.0+9-tem` | `release` `9568390645661374febde48f3c7a019f21cb116d6e4c627de29c119aa7bd0efc` |
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` | `release` `f83f6dcc966043c93cd498ac8e7ee7c310852074970d62c702e4ad2710002898` |
| Temurin 25.0.5+8 | `~/.sdkman/candidates/java/25.0.5.0+8-tem` (**the default `java` on `PATH`**) | `release` `8545053a54a73969a65db2c8157f40f89bcdcf7526ae90a7ce9b3061c01bc34a` |
| JBMC 6.11.0 (cbmc-6.11.0) | `/usr/bin/jbmc` | sha256 `200f4cbb273d94268cdf933ee1f7c5ea96c8abc95af83836c2ffc082a722ec35` |
| `jvmcontract` release | `lib/target/release/jvmcontract` | sha256 `aa6a6e26a770316bd80bd3c2c9d1f67ed55e1f7b3fa77a90fe3854ad7e7e69c6`; `cargo build --release -j 4 --bin jvmcontract` at this head found it up to date |
| Maven 3.10.0 | `~/.sdkman/candidates/maven/current` | used only to resolve the sets below |
| Docker images | local | `mysql:9.1.0` `sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` (457, N05), `postgres:17` `sha256:0d938e975177bef9f1f61f3f9dbcf2e0aa0a139568f66d3415ed8892eb97f6ac` (518). These are the digests the `runtime.json` files name. |

Every example's recorded `jdkReleaseSha256` equals the `release` digest of the JDK it names.

## Examples: deployments and pins

`python3 -I $B/scripts/check_examples.py . $B/logs/examples.json 446 448 451 453 454 455 456 457 458 466 484 $(seq 478 587)`
(21 s) hashed 1,485 files. For each example it checks:

- that every classpath entry and every `upstreamTestInputs` file exists, and matches `runtime.json`'s `sha256` map;
- that every classpath entry has a digest in that map;
- that the JDK's `release` digest matches;
- that one worktree under the cache's `worktrees/` is at each pin of `comparison.json`, with no tracked change.

Result: **all 120 examples match** (484 is in both lists).

| Set | Examples | Cache | JDK (count) | Deployments |
|---|---|---|---|---|
| P (draw) | 478–507 | `$P` | 17 (28), 8 (2) | `pins` |
| Q (draw) | 508–537 | `$Q` | 17 (25), 8 (5) | `pins`; 518 needs the `postgres:17` image |
| R (draw) | 538–587 | `$R` | 17 (40), 21 (8), 8 (1), 25 (1) | `pins`, except 542 and 546 (`jre` and `android`), 576 and 579 (`overlay`) |
| N01–N05 | 453–457 | `$N` | per case | 457 needs the `mysql:9.1.0` image |
| M04, M06, M09 | 446, 448, 451 | `$M` | per case | `pins` |
| 458, 466 | 458 (O01), 466 (O09) | `$O` | 17 | `pins` |

Per-example rows (cache, JDK, files, worktree paths, `runtime.json` and `comparison.json` sha256) are in `$B/logs/examples.json`.

**One worktree differs from its commit in line endings only.** `$R/worktrees/R47-picocli-parent` (584, parent
`7c7c8b954277b6e18c57ff5ea1791b59569c0511`) shows 18 `docs/*.html` files as modified. `git diff --ignore-cr-at-eol`
is empty: the files were committed with mixed line endings under an `eol=lf` attribute that this commit adds, and git
reports the normalization. No source or build file differs. The checker lists it under `crAtEolOnly` and accepts it,
and the worktree was left as it is.

The static audits (`python3 verification/merged-pr-links/audit.py --campaign C --output …`, under a second each) are
byte-identical to each campaign's committed `audit.json`:

| Campaign | Cases | Questions | Fresh JVMs (recorded) |
|---|---|---|---|
| p01-p30 | 30 | 94 | 188 |
| q01-q30 | 30 | 92 | 184 |
| r01-r50 | 50 | 150 | 312 |
| n01-n05 | 5 | 17 | 34 |
| m01-m10 | 10 | 30 | 60 |

They check records against records and do not read the deployments. The JVM replay is job 1 below, and it **passed**:
every campaign's `--replay` audit equals its `audit.json` byte for byte.

## Other inputs: J08, J14, Log4j #1173, Commons IO #520

`python3 -I $B/scripts/check_inputs.py . $B/logs/inputs.json`: **all inputs match**.

| Input | Reader | Classpath matching (old / new) | Parent commit / tree | Fix commit / tree | JDK |
|---|---|---|---|---|---|
| J08 Parquet #3638 | `verification/product-behaviour/cases/J08/bindings.json` under `$P20` | 113/113, 113/113 | `5c360ff5d879d3567f23cea3290894712fb336d9` / `fdca60b7968396b96ac09362e2a90ccfc0064036` | `5e14d7cd43403a95d331be8791e8792dbf38683d` / `4005c46207142ab7b0c19de2711fc2114e0414e4` | 21.0.13 |
| J14 Lucene #15727 | `verification/product-behaviour/cases/J14/bindings.json` under `$P20` | 2/2, 2/2 | `182ee9c4cc3bc52ace12e699248b750377a3aa2f` / `4752063348a2900ec879136c7e39c00659d53610` | `167503f6d84d8e43db4ec6ae3baf17337290393f` / `960a3171eee14e937579bad793c8747ff74dc6af` | 25.0.5 |
| Log4j #1173 | `lib/benchmark/organic-composition/log4j/{old,new}/prepared.json` | 2/2, 2/2 | `e325de9abf771a4501bae7cd7910fcbce31f5663` / `c2ace3b75ab10944e6f21c1de36a8c8a6f1e7492` | `7107cd655380d81dea72df930a832e598173971e` / `7b506a6963f271fd3897f41b30aa2a02869af9a5` | 21.0.13 |
| Commons IO #520 | `lib/benchmark/organic-composition/io/{old,new}/prepared.json` | 1/1, 1/1 | `dccc7011046542e9375b6a4f90b24ca02b01a890` / `8739971752b6f238f6ac2b78decdc501dee0e61c` | `3e7f57784c2fa8190fb3c75c977920ba6022de66` / `0e3c864e504db0ba773198c0254794cad2ac8fc4` | 21.0.13 |

Log4j jars (api, then core): parent `$FF/artifacts/G-logging-log4j2-parent-log4j-api.jar`
`c9d2f400916a5346816deff5309f725069804a810e7d0492294d931a391d7582` and `…-parent-log4j-core.jar`
`da05ae3790513bb74285ce65a37e9b06829b82d9af2939df826a815176802b6f`; fix `$FF/artifacts/G-logging-log4j2-fix-log4j-api.jar`
`c9d2f400916a5346816deff5309f725069804a810e7d0492294d931a391d7582` and `…-fix-log4j-core.jar`
`c98f9f1dad7d5e81f893838971083cabe252e454c3568c11db0f47e4f3df9b60`. Commons IO: `$FF/artifacts/E-commons-io-parent.jar`
`24718c09f6e0f7990a968e144be96042a20b97510b4dc611e1c97c3c3189e341` and `$FF/artifacts/E-commons-io-fix.jar`
`48fc79897f329de108aa4452288c86be27f76c7146e33c38bfc345b5d7885dcc`.

Example 333 (custom loaders, part D): `python3 examples/tools/validate_example.py 333` passed. It took 183 s because it
also runs the targets tests, so treat it as a job next time. The stock-JBMC finding VF-071 (part D) binds no
downloaded artifact: its multi-release fixtures are generated (`verification/classpath-entry-discovery/mr-proofs.json`)
and its backend is the JBMC above.

## What was run on a JVM

All runs were read-only for the repository (`jj diff` showed only this record and the job files). Each ran under
`systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300`, with `TMPDIR=$B/tmp`.

| Case | Command (repository root) | Result |
|---|---|---|
| 458, 466, 484 | `PYTHONPATH=examples/tools python3 -m targets.public_comparison NNN` (raises if the fresh observations differ from `observations.json`) | all exit 0, 1–4 s each |
| J08, J14 | `python3 -I $B/scripts/physical_copy.py . CASE $B/probes/physical` | both "fresh physical.json equals the committed one" (10 and 10 histories) |
| Commons IO | `python3 -I $B/scripts/io_observe.py . $B/probes/io ~/.sdkman/candidates/java/21.0.13.0+9-tem` | "all registered IO histories match" (8) |

Part A's first operation, Spring 458's three-argument `NumberUtils.parseNumber(String, Class, NumberFormat)`, is not
touched by #37434. The landing's two hunks are at lines 276 and 290 of
`spring-core/src/main/java/org/springframework/util/NumberUtils.java`. The `DecimalFormat` branch that calls
`isParseBigDecimal()` and `setParseBigDecimal(true/false)` (lines 250 and 264 at the fix) is the same at both pins.
This is a fact about the source, not a prediction.

### Spring #37193 (466, O09): the landed upstream test in a plain JVM

`$O/artifacts/O09-{fix,parent}/spring-web.testRuntimeClasspath.txt` (202 entries each, kept by the O setup) holds
every jar the upstream `:spring-web:test` launch used. It includes spring-web's own production and test-fixture jars,
copied under `$O/artifacts/O09-ROLE/tree/`. That holds on both pins. The classpath files' sha256 are
`1f4523ccf0607d533702dd4efe989ed6448e1b2bfe62871bdeacbf62172e0283` (fix) and `de0666106c1341d9bdb7fa6be85f2a46f9fa8ab6888fffee4584cbae7b763366` (parent).
All 202 entries exist. Their sha256 are in `$B/logs/O09-ROLE-spring-web-testRuntimeClasspath.sha256`, and each
side's `SHA256SUMS` jar lines check (`sha256sum -c`). Only one entry differs between the sides:
`tree/spring-web/build/libs/spring-web-7.1.0-SNAPSHOT.jar`. The kept classpath has no compiled test classes, because
the O setup's `clean` step removed them.

`$B/scripts/o09_upstream_test.sh TESTROLE CLASSROLE JDK [OUT]` does three things:

- takes `ServerSentEventHttpMessageReaderTests.java` from `$O/worktrees/O09-TESTROLE` with `git show HEAD:`;
- compiles it with `--release 17 -parameters` against CLASSROLE's classpath;
- runs it with the JUnit Platform console launcher 6.1.2, the platform version on that classpath.

| Test from | Classes | JDK 25.0.5 (Gradle's test toolchain) | JDK 17.0.21 (example 466's) |
|---|---|---|---|
| fix | fix | 14/14 pass | 14/14 pass |
| parent | parent | 13/13 pass | 13/13 pass |
| fix (transplanted) | parent | **1 fails**: `ignoreInvalidRetry`, `onError(java.lang.NumberFormatException: For input string: "none")` where `expectNext(… data=foo)` was expected | the same |
| parent | fix | 13/13 pass | 13/13 pass |

These match the O setup's Gradle runs (job `20261126-003557-setup-build-spring-framework-37193-o09-a`). Each launch
takes about 2 s. Test-source sha256: fix `fb76f46c230a591996511b4209f233e23ef394db6f2bdd6efa9c84f9b954e413`, parent
`f6fa07d5987c32047050ad3e9536f0337569f2edeb45a20506ac28cde1ac3ee2`. The compiled class (`$B/upstream-tests/O09/test-ROLE-on-ROLE/`)
has sha256 `8d48e5a5ae9c6994bceee8aac16e12551521190c0a7b6e5938f7a9afee3bcaea` (fix test) and
`12ef3c3957530021f28b361615c923fe389ab50447220f08509ef65f1dfa6f31` (parent test), the same on either classpath.

Run any other spring-web test class the same way: swap the path in the script. The kept
`spring-webflux.testRuntimeClasspath.txt` serves webflux classes. Classes that need Kotlin or other test sources need
those sources on the javac line too.

### Parquet #3638 (J08): the upstream test trees over the original 113-entry graphs

The pins' own Maven build cannot run here: `parquet-format-structures` needs a `thrift` 0.23.0 binary
([product-behaviour setup](organic-java-pr-product-behaviour-20-additional-cases-setup.md#j08--apache-parquet-3638-pinned-source-overlay-over-1182)).
J08's deployment is the pinned-source overlay over Parquet 1.18.2 plus Hadoop 3.3.0, the 113 entries of
`bindings.json`. Parquet 1.18.2 alone already behaves like the fix. This setup compiled the pins' upstream test
sources against that graph.

- **Test dependencies** were resolved at the versions the pinned POMs name: `$B/releases/j08-hadoop-testdeps`
  (33 jars: JUnit 5.14.4 jupiter and vintage, console launcher 1.14.4, junit 4.13.2, guava 33.6.0-jre, mockito 5.23.0,
  assertj 3.27.7, okhttp-jvm 5.4.0, commons-io 2.22.0, commons-lang3 3.20.0, zero-allocation-hashing 0.27ea1,
  slf4j-simple 1.7.33, jts-core 1.20.0, hamcrest-core 1.3, and their dependencies) and `$B/releases/j08-column-testdeps`
  (junit-benchmarks 0.7.2). They come from `$B/scripts/resolve.sh NAME test COORDS…`: Maven `--strict-checksums`
  against Central, with signatures checked below. `parquet-hadoop`'s runtime-only `brotli-codec` 0.1.1 is not on
  Central and was not fetched. No test that was compiled needs it.
- **Compile**: `$B/scripts/j08_upstream_tests.sh compile ROLE` builds the 180 test sources of `parquet-column` (83)
  and `parquet-hadoop` (97), with `parquet-common` and `parquet-encoding`'s test sources on `-sourcepath`. It builds
  against ROLE's graph plus the test dependencies, on JDK 21.0.13, `-proc:none`. Both pins compile with no error, to
  425 classes each in 4 s. Outputs are in `$B/upstream-tests/J08/ROLE/` (`compiled.txt`, and `SHA256SUMS` of every
  class and test resource). That file's sha256 is `f0035495acf23d2d2463eb774ad59dbd2e7ec21368291b8c5404d966479fec38`
  (fix) and `11e859a2ef3c2214c596b5bf711a6b49aaeaa8bb55051e180c290b2ceae361a1` (parent).
- **Run**: `$B/scripts/j08_upstream_tests.sh run ROLE GRAPH [launcher selectors]` runs ROLE's test classes on
  GRAPH's graph, where GRAPH is `parent` or `fix`. `classpath ROLE GRAPH` prints the classpath, with the test
  classes and `parquet-hadoop/src/test/resources` first, then the 113 graph entries and the test dependencies.

| Tests from | Graph | `TestDictionary` (landed) + `TestParquetWriter` |
|---|---|---|
| fix | fix | 55/55 pass (24 + 31) |
| parent | parent | 53/53 pass (22 + 31) |
| fix | parent | **2 fail**: `testDictionaryWriterReusableAfterFirstPageFallBack`, `testDictionaryWriterReusableAfterFallBack` (`Index 10 out of bounds for length 1`) |
| parent | fix | 53/53 pass |

The older `$P20/scripts/j08_overlay_test.sh` (JUnit 4, parquet-column classpath only) gives the same `TestDictionary`
results ([log](#layout-of-b)). `TestParquetWriter` exercises the public `ParquetWriter` file path on both graphs and
passes on both. Whether it reaches the changed writer bodies is for the domain's trace run to show.

#### The whole suites (job 2, passed)

Job `20261127-032259-setup-run-parquet-3638-s-upstream-parque` ran `$B/scripts/j08_suite.sh ROLE GRAPH` (the version
with sha256 `f2e8fa09c378a8757551143984251728d69c87e55360e851683e8d241ef9ac11`) at
`5c57e715acb8e32f1ed7fc1dc2f7ba684882837c`, from 2026-11-27T03:30:23Z to 03:41:52Z. Peak memory was 3.0 GiB, and each
run took 223–233 s. Its result is in commit `2c45066adba0` (`verification/results/2026/11/27/20261127-032259-setup-run-parquet-3638-s-upstream-parque/`),
which this line has not merged. Each run covers 138 classes: 66 in `parquet-column` and 72 in `parquet-hadoop`. Of
`parquet-hadoop`'s 78 name-matching files, seven are excluded: `InterOpTester` itself and the six classes that use it.

| Tests from | Graph | `parquet-column` (found / passed / failed) | `parquet-hadoop` (found / passed / failed / aborted) | `summary.txt` sha256 |
|---|---|---|---|---|
| fix | fix | 664 / 649 / 15 | 725 / 690 / 9 / 24 | `e364ee98ddf2babb34cb325a4abef9d1c24105943207ec6629d330ffb9f6db64` |
| parent | parent | 662 / 647 / 15 | 725 / 690 / 9 / 24 | `f129655e6c5799836085cfc30a18082009ba8f5ce26105e673ee620004fe8ddf` |
| fix | parent | 664 / 647 / **17** | 725 / 690 / 9 / 24 | `37d431f19796081b2ff1be4ae142a418d316a8dd1c0e01a9961cadbb288d55e0` |

**Results that differ between the runs.** The lists of failing tests are identical in fix-on-fix and
parent-on-parent. Fix-on-parent adds exactly the two landed `TestDictionary` tests, the same two as above. The other
24 failures and 24 aborts fall on both pins, so they come from the deployment, not from #3638.

| Tests | Count | Cause |
|---|---|---|
| `TestStatisticsNanCount` (7), `TestStatistics#testSpecBuilderFor{Double,Float}`, `TestColumnIndexBuilderNaN` (3), `TestColumnIndexBuilder#testBuild{Double,Float}ZeroNaN`, `TestMessageType#testMergeSchemaWithColumnOrder`, `TestParquetMetadataConverter#{testBinaryStatsV1,testBinaryStatsV2,testNestedColumnOrdersUseLeafOrder}`, `TestFloat16ReadWriteRoundTrip` (2), `TestFloat16Statistics` (2) | 20 | Version skew in the overlay: the pins' tests exercise NaN-count, float16 and column-order behaviour that released Parquet 1.18.2 does not have. Two examples: `IEEE754Float16Statistics cannot be cast to … Float16Statistics`, and `Num nulls should match expected:<3004> but was:<0>`. |
| `TestDirectCodecFactory#compressionCodecs` | 1 | `ClassNotFoundException: org.apache.hadoop.io.compress.BrotliCodec`: `brotli-codec` 0.1.1 is absent. |
| `TestLargeColumnChunk#validateAllData`, `#validateFiltering` | 2 | `Java heap space` at the JVM's default heap. The POM sets no `-Xmx`, and these tests run only with `enableResourceIntensiveTests=true`. |
| `TestParquetWriterError#testInSeparateProcess` | 1 | **A launcher artifact, now fixed.** The test starts a child JVM with `-cp ${java.class.path}`. Under `java -jar console-standalone`, that is the launcher jar alone, so the child failed with `ClassNotFoundException: …TestParquetWriterError$Main`. |
| `TestVectorIoBridge` (20), `TestFileRangeBridge` (4) | 24 aborted | JUnit assumptions: Hadoop 3.3.0 has no vectored IO (`ClassNotFoundException: org.apache.hadoop.fs.FileRange`, "Bridge not available"). |

**The launch fix.** `j08_suite.sh` and `j08_upstream_tests.sh run` now start
`org.junit.platform.console.ConsoleLauncher` from `-cp "$CP"` instead of `-jar … --class-path "$CP"`. The
console-standalone 1.14.4 jar was already on `$CP`, so only `java.class.path` changes, and child test JVMs inherit the
whole test classpath. A probe ran `j08_upstream_tests.sh run fix GRAPH --select-class` on `TestParquetWriterError`,
`TestDictionary` and `TestParquetWriter`, from `parquet-hadoop`, under the probe cap:

| Graph | Result |
|---|---|
| fix | 57/57 pass in 5 s, including `testInSeparateProcess` |
| parent | 55 pass; the 2 landed `TestDictionary` tests fail as before |

Logs: `$B/logs/j08-cp-launch-fix-on-{fix,parent}.txt`. The job's reports were written by the older launch, so they
still show `testInSeparateProcess` failing. The whole suites were not run again: the probe shows the one changed test,
and no other test source in `parquet-column`, `parquet-hadoop`, `parquet-common` or `parquet-encoding` reads `java.class.path` or starts a process (grep for `java.class.path`, `ProcessBuilder`, `Runtime.getRuntime().exec`).

## Fetched artifacts and signatures

Resolved into `$B/m2` (`$B/maven-settings.xml`). Maven `--strict-checksums` checked every file against Central's
sha1. Signatures were checked with `$B/scripts/verify_sigs.sh NAME`: `.asc` from repo1, keys from keyserver.ubuntu.com,
private keyring `$B/gnupg`. Full lines are in `$B/logs/sigs-*.txt`, and sha256 of every jar in `$B/logs/releases.sha256`.

| Set | Jars | Signatures |
|---|---|---|
| `junit6-console` | `junit-platform-console-standalone-6.1.2.jar` `1a80b327b0f3bd536d28aecc857eee6948184eb35889357f5a937507f2c0dbb3` | GOODSIG Marc Philipp `FF6E2C001948C5F2F38B0CC385911F425EC61B51` |
| `j08-hadoop-testdeps` | 33 jars, including `junit-platform-console-standalone-1.14.4.jar` `7c6968cbcaf4301c729f202b23b7d736c5d88be625fc7d27ad5d746146a8bc28`, `guava-33.6.0-jre.jar` `dc573e1fca4fd5454f4a5fd3d7da2df03002876a4175bafc14a95980dd7713b3`, `okhttp-jvm-5.4.0.jar` `b15e605ca0a4b12c62ea7f657dad413c236c947e875854767349cdbe20df473c` | 31 GOODSIG. `annotations-13.0.jar` (JetBrains) EXPKEYSIG: a good signature by an expired key, `2E3A1AFFE42B5F53AF19F780BCF4173966770193`. `zero-allocation-hashing-0.27ea1.jar` (`67fbdbbec169e4621befcd9d82fe07a99c47c9090b2c10a807a63a96c0658790`) is **unchecked**: its key `C38B83CF2DD6A1CCD87EA7ED3425435D424DEE7F` is not on keyserver.ubuntu.com or pgp.mit.edu, and keys.openpgp.org serves it without a user ID, which gpg will not import. Its sha1 `9491fc9ae28fbfaa51d6cf35b4e18cb4c3b0cd1a` equals Central's. |
| `j08-column-testdeps` | `junit-benchmarks-0.7.2.jar` `962c7d4bbb6f278fd877842c86bb99221fd233e30decc8705c2e9a98e5805aba` | GOODSIG Dawid Weiss `A32C3BF4A5B04200A31E05370A9F96A917990CF6` |

The keyring's daemons were stopped with `gpgconf --homedir $B/gnupg --kill all`. No `gpg-agent` or `dirmngr` for it is running.

## Verification jobs

| Job | What | Status |
|---|---|---|
| `20261127-032247-setup-replay-the-p-q-r-n-and-m-public-ob` | `audit.py --campaign C --replay` for p01-p30, q01-q30, r01-r50, n01-n05 and m01-m10 at this head, each compared byte for byte with the committed `audit.json`: every historical caller recompiled, every physical trial rerun on the original deployments (Docker for 457 and 518). 2 CPU, 1 GiB, ~15 min. | **passed**: 10/10 steps at `5c57e715acb8e32f1ed7fc1dc2f7ba684882837c`, 2026-11-27T03:30:23Z–03:35:05Z, 4 min 32 s, peak 296 MiB. All five `repeated-audit.json` equal `audit.json`. Result in commit `dc6fd6c8f17f` (`verification/results/2026/11/27/20261127-032247-setup-replay-the-p-q-r-n-and-m-public-ob/`), not yet merged into this line. |
| `20261127-032259-setup-run-parquet-3638-s-upstream-parque` | `$B/scripts/j08_suite.sh ROLE GRAPH` for fix/fix, parent/parent and fix/parent. Each runs the whole `parquet-column` and `parquet-hadoop` suites, one JVM per module as surefire forks them. It uses the POM's argLine (`-XX:MaxJavaStackTraceDepth=8` and the 13 `--add-opens`/`--add-exports` of `extraJavaTestArgs`) and its properties (`enableResourceIntensiveTests=true`, simpleLogger ERROR), and surefire's default includes minus `**/benchmark/*`. The six `InterOpTester` classes are left out because they download parquet-testing files: `TestEncryptionOptions`, `TestInterOpReadFloatingPointNanCount`, `TestInterOpReadFloat16`, `TestInteropBloomFilter`, `TestInterOpReadByteStreamSplit`, `codec.TestInteropReadLz4RawCodec`. That leaves 138 classes per run (66 + 72; the seventh excluded file is `InterOpTester` itself). Reports go to `$B/upstream-tests/J08/reports/ROLE-on-GRAPH/`. 2 CPU, 4 GiB, ~45 min. | **passed**: 3/3 steps in 11 min 19 s, peak 3.0 GiB. Result in commit `2c45066adba0`, not yet merged into this line. Outcomes are in [the whole suites](#the-whole-suites-job-2-passed). |

## What was not done, and why

- No new upstream source, mirror or worktree: every pin the brief names already had a clean worktree.
- No Gradle or Maven build of any pin. The deployments are the ones earlier setups built and tested at the pins (see
  their records). The O09 and J08 test launches above bypass the build tools on purpose: they run in seconds and can
  carry a tracer.
- No Log4j #1173 JVM re-run. The classpath-discovery setup recorded its four `getNextTime` rows and the landed test
  (job `20261124-141323-setup-build-log4j-core-at-both-1173-revi`). Its strict `UpgradeProbe#schedule()Z` and the
  eight timezone histories are part D's work. Note that job `20261126-200411-replay-log4j-public-entry-bindings-and-s`
  (domain work, not setup) **failed**: its scaffold-and-resume step exited 1 and `log4j-replays.json` was not produced.
- No Commons IO native query, stock-JBMC run, or example 333 loader run: those are part D's measurements.
- No full spring-web or spring-webflux upstream suite: the domain agent chooses which upstream classes the trace launch uses.

## Setup Agent Notes

### What is ready, and where

- **The whole draw inventory, P 478–507, Q 508–537 and R 538–587, is checked**: every deployment file matches its
  `runtime.json` digest, the JDKs match, and there is a worktree at each pin
  ([Examples: deployments and pins](#examples-deployments-and-pins); rows in
  `~/.cache/in-the-loop/blind-caller-pr-verification/logs/examples.json`). The caches are
  `~/.cache/in-the-loop/{spring-pr-links-p01-p30,spring-pr-links-q01-q30,merged-pr-links-r01-r50}`, with worktrees
  `worktrees/P01-{parent,fix}` … `Q30-…`, `R01-<project>-{parent,fix}` … `R50-…`.
- **N01–N05** (examples 453–457, `~/.cache/in-the-loop/merged-pr-links-n01-n05`) and the adverse controls **M04, M06,
  M09** (examples 446, 448, 451, `~/.cache/in-the-loop/merged-pr-links-m01-m10`) are checked the same way. The MySQL
  sidecar image `mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6` and Connector/J 9.1.0
  are in place ([N01–N05 setup notes](organic-java-merged-pr-links-n01-n05-brief-setup.md#setup-agent-notes)).
- **Development cases**: 458, 466 and 484 read `runtime.json` against `~/.cache/in-the-loop/spring-pr-links-o01-o20`
  (458, 466) and `~/.cache/in-the-loop/spring-pr-links-p01-p30` (484). J14 (Lucene #15727) reads
  `verification/product-behaviour/cases/J14/bindings.json` under `~/.cache/in-the-loop/organic-pr-20`.
- **Part B upstream test launches, in a plain JVM (no Gradle or Maven)**:
  - Spring 466: `~/.cache/in-the-loop/blind-caller-pr-verification/scripts/o09_upstream_test.sh TESTROLE CLASSROLE JDK [OUT]`
    compiles and runs `ServerSentEventHttpMessageReaderTests` on the kept 202-entry spring-web test classpath
    `~/.cache/in-the-loop/spring-pr-links-o01-o20/artifacts/O09-{fix,parent}/spring-web.testRuntimeClasspath.txt`,
    with the JUnit console 6.1.2 at `~/.cache/in-the-loop/blind-caller-pr-verification/releases/junit6-console/lib/junit-platform-console-standalone-6.1.2.jar`.
  - Parquet J08: `~/.cache/in-the-loop/blind-caller-pr-verification/scripts/j08_upstream_tests.sh {compile ROLE | classpath ROLE GRAPH | run ROLE GRAPH [selectors]}`.
    The compiled `parquet-column` and `parquet-hadoop` test trees of both pins are in
    `~/.cache/in-the-loop/blind-caller-pr-verification/upstream-tests/J08/{fix,parent}/`, and run over the original
    113-entry graphs of `verification/product-behaviour/cases/J08/bindings.json`. Commands and digests are in
    [the J08 section](#parquet-3638-j08-the-upstream-test-trees-over-the-original-113-entry-graphs).
- Log4j #1173 and Commons IO #520 read `lib/benchmark/organic-composition/{log4j,io}/{old,new}/prepared.json`.
  Jar digests are in [Other inputs](#other-inputs-j08-j14-log4j-1173-commons-io-520).
- JDKs 8, 11, 17, 21.0.13 and 25.0.5 are in `~/.sdkman/candidates/java/`; the default `java` is 25.0.5. JBMC 6.11.0
  is at `/usr/bin/jbmc`. `lib/target/release/jvmcontract` is current at `524b1fbd9277032681921afbeac09d218d156147`
  (sha256 `aa6a6e26a770316bd80bd3c2c9d1f67ed55e1f7b3fa77a90fe3854ad7e7e69c6`). Identities are in [Tools](#tools).

### What was verified on a JVM

- The registered observations of 458, 466, 484, J08, J14 and Commons IO, re-run in fresh JVMs on the original
  deployments, equal the committed receipts ([What was run](#what-was-run-on-a-jvm)).
- Spring 466's landed test, on JDKs 25 and 17: the fix's test passes on the fix (14/14) and fails on the parent only in
  `ignoreInvalidRetry`, with `NumberFormatException: For input string: "none"`. The parent's test passes on both (13/13).
- Parquet J08: the landed `TestDictionary` passes on the fix graph (24) and fails on the parent graph in
  `testDictionaryWriterReusableAfterFirstPageFallBack` and `testDictionaryWriterReusableAfterFallBack`. Upstream
  `TestParquetWriter` (31 tests, the public file path) passes on both graphs.
- Example 333 validates.
- **Job `20261127-032247-setup-replay-the-p-q-r-n-and-m-public-ob` passed.** Every historical P, Q, R, N and M
  observation was replayed in fresh JVMs on the original deployments at `5c57e715acb8e32f1ed7fc1dc2f7ba684882837c`,
  including the MySQL 9.1.0 and Postgres 17 sidecars. Each audit equals its committed `audit.json` byte for byte. The
  110-case draw inventory, N01–N05 and the M controls are re-run, not only digest-checked.
- **Job `20261127-032259-setup-run-parquet-3638-s-upstream-parque` passed.** Parquet's whole `parquet-column` and
  `parquet-hadoop` suites (138 classes) ran on the original 113-entry graphs, fix on fix, parent on parent, and fix on
  parent. The fix-on-fix and parent-on-parent failure lists are identical. Fix-on-parent adds exactly the two landed
  `TestDictionary` tests. The 24 failures and 24 aborts common to both pins are causes of the deployment, listed in
  [the whole suites](#the-whole-suites-job-2-passed).
- One of those shared failures was this setup's own: `TestParquetWriterError#testInSeparateProcess`, whose child JVM
  got only the launcher jar as its classpath. The launch now uses `-cp`, and a probe shows the test passing on the fix
  graph (57/57 with `TestDictionary` and `TestParquetWriter`). On the parent graph, only the two landed tests fail.
- Both results are in commits that this line has not merged: `dc6fd6c8f17f` and `2c45066adba0` (the latter also
  holds the first). `pipeline.py status` lists both jobs as "in commit 2c45066adba0 … merge it".

### What to know before starting

- **Producer-view hygiene.** These all hold historical callers, receipts or actual outcomes:
  - the examples' `caller/`, `observations.json` and `comparison.json`;
  - `verification/merged-pr-links/*/audit.json` and `repeated-audit.json`;
  - `verification/product-behaviour/cases/J*/{case,physical}.json` and `UpgradeProbe.java`;
  - this setup's `~/.cache/in-the-loop/blind-caller-pr-verification/probes/` and `logs/replay-*`, `physical-*`, `io-observe.txt`.

  The worktrees hold the upstream tests and test diffs, which the brief keeps out of the first blind view. The compiled
  test trees under `upstream-tests/` are upstream tests too: they belong to the test-assisted diagnostic and part B,
  not to the headline attempt.
- **J08's test launch is over overlays, not a pin build.** The pins' build needs a `thrift` 0.23.0 binary. The graph is
  the pin's two changed `parquet-column` classes (8 overlay classes) over released Parquet 1.18.2, Hadoop 3.3.0 and an
  unshaded fastutil 8.5.19. The upstream `parquet-hadoop` tests run against 1.18.2's `parquet-hadoop`, not the pin's.
  Label trace evidence from it that way. `brotli-codec` 0.1.1 (runtime-only, not on Central) is absent. The six
  network `InterOpTester` classes are left out of the job.
- **Which upstream tests run usefully on J08's graphs.** 24 tests fail on both pins for reasons of the deployment, not
  #3638: 20 from version skew against 1.18.2 (NaN counts, float16, column orders), one from the missing Brotli codec,
  two from heap at the default `-Xmx`, and `TestParquetWriterError#testInSeparateProcess` from the old launch, now
  fixed. A further 24 abort because Hadoop 3.3.0 has no vectored IO. A selection policy should treat these as
  coverage gaps of the overlay, and they are listed by name in each run's `summary.txt`.
- Launch J08 tests with `j08_upstream_tests.sh run` or `j08_suite.sh`. Both now start the console launcher from
  `-cp`, so a child test JVM inherits the whole classpath. A tracer that must follow a child JVM needs the same
  `java.class.path`.
- **Spring 466's classpath has snapshot dependencies**: `reactor-core` and `reactor-test` `3.9.0-SNAPSHOT`, and
  micrometer `1.18.0-SNAPSHOT` on the P cases. They are fixed bytes, digest-checked, from the O, P and Q setups'
  Gradle homes. Do not re-resolve them. Gradle's test JVM for O09 was JDK 25 with `--release 17`; example 466's
  runtime is JDK 17. The landed test behaves the same on both.
- `$R/worktrees/R47-picocli-parent` (example 584) reports 18 `docs/*.html` files as modified. They differ only in line
  endings, and no source differs ([details](#examples-deployments-and-pins)).
- R05 (542) and R09 (546) have two deployments each (`jre`, `android`). R39 (576) and R42 (579) are overlays: R42's
  pinned build cannot be configured from public sources
  ([R setup](organic-java-merged-pr-links-r01-r50-brief-setup.md)). Examples 518 and 457 start Docker services.
- `zero-allocation-hashing-0.27ea1.jar`'s signature could not be checked; only its sha1 matched Central.
- Brief 24 (JVM startup facts) has landed at this head, so part D can reuse it. Job
  `20261126-200411-replay-log4j-public-entry-bindings-and-s` failed and is not setup's to fix.
- Run `public_comparison` as `PYTHONPATH=examples/tools python3 -m targets.public_comparison NNN`: the plain script
  path fails on its import. `validate_example.py 333` takes about 3 minutes. pytest is not installed; use `unittest`
  or `lib/tools/test_costs.py`.

### What is left for the domain work on purpose

- Everything the brief builds or measures:
  - the retained-argument operation on 458 and its planted callers;
  - the three development exercises;
  - the sealed inventory, the exclusions, the freeze, the seed and the draw;
  - the blind, test-assisted and reviewed attempts, and scoring;
  - trace-guided ranking and the scheduler-hop exercise;
  - the N01–N05 fresh-workspace run;
  - every part D qualification.
- Choosing which upstream test classes the trace launch uses (the policy to freeze), attaching the tracer
  (`examples/tools/targets/java/UpgradeTrace.java`), and the plain-JVM comparison runs.
- What goes into each producer view, and what stays with the evaluator.
- Any example ids, registrations, scaffolds or claims.
