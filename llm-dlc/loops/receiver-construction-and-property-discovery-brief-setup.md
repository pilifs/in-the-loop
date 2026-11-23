# Setup for the receiver construction and property discovery brief

Mechanical setup for [`receiver-construction-and-property-discovery-brief.md`](receiver-construction-and-property-discovery-brief.md),
done on 2026-11-23 by a setup session (Claude Opus 5.5) before the domain work starts. The session pinned and
checked every revision the brief links or the cases' examples and receipts name. It resolved and signature-checked
the released libraries, kept the earlier receiver campaign's prepared area safe, pointed at JBMC 6.11.0 and the JDK
class the comparator profiles name, and confirmed the checker's release binary is current. It then reproduced, on a
JVM, every observation the brief states for an existing library or fixture.

It wrote no claims, examples, sidecars, adapters or recipes, allocated no example ids, ran neither the project
verifier nor JBMC on any claim, and changed nothing in `lib/` or the checker. Everything it fetched or built is
outside the checkout, under `~/.cache/in-the-loop/`. **No verification job was needed**: every JVM check took seconds,
and the two landed upstream regressions (#218 and #4538) already have committed runs of exactly those tests at the
pinned commits ([below](#landed-upstream-regressions)).

`$B` below is `~/.cache/in-the-loop/receiver-construction`. `$J` is Temurin 21.0.13+9,
`~/.sdkman/candidates/java/21.0.13.0+9-tem/bin` (`lib/modules` sha256 `a5fd7c31…5a39782c`). **The default `java` on
`PATH` is JDK 25**, so name JDK 21 by its full path.

## Layout

| Path | What it holds |
|---|---|
| `$B/releases/NAME/` | Released graphs from Maven Central: `lib/` (jars), `sources/` (sources jars), `classpath.txt` (ordered, absolute, into `$B/m2`), `tree.txt`. New here: `jgrapht-core-1.5.2`, `xz-1.11`, `xz-1.12`, `jackson-2.18.3`, `snakeyaml-2.4`, `snakeyaml-2.5`. Hard-linked from the fast-follow setup: `guava-33.4.8-jre`, `commons-lang3-3.17.0`, `jackson-2.19.0`. |
| `$B/resolve/NAME/pom.xml`, `$B/m2`, `$B/maven-settings.xml` | The throwaway POM per graph, the local repository (seeded by hard links from `~/.cache/in-the-loop/jbmc-fast-follow/m2`) and settings pointing at it. |
| `$B/receivers/area/`, `$B/receivers/maven-repository/` | **Hard-link snapshots** of the earlier receiver campaign's prepared area (`~/.cache/in-the-loop/tmp/domain-foundations-receivers`: `modules/`, `slices/`, `sources/`) and its Maven repository (`~/.cache/in-the-loop/agent-tmp/0cea9d0e-…/external-upgrade-shared-maven/repository`). Both originals sit in scratch folders. The snapshot keeps their bytes if those are cleaned; it takes no extra disk. |
| `$B/receivers/cp/CASE-SIDE.cp` | Ordered runtime classpaths for `commons-configuration-565`, `commons-configuration-601` and `commons-compress-767`, `old` and `new`, pointing into the snapshot. Each entry was checked against its `prepared.json` sha256. |
| `$B/originals/` | The four captured upstream JARs of examples 360 and 366 (hard links into `~/.cache/in-the-loop/targets/sha256/`): `javaparser-360-{parent,fix}.jar`, `csv-366-{parent,fix}.jar`. |
| `~/.cache/in-the-loop/git-mirrors/NAME.git` | One bare mirror per upstream, each pinned commit under `refs/pinned/WORKTREE`. New: `javaparser`, `jgrapht`, `xz-java`, `commons-csv`, `commons-configuration`, `commons-compress`. Already there: `guava`, `commons-lang`. |
| `$B/src/WORKTREE` | One detached worktree per pinned revision ([below](#pinned-revisions)). To add one: `$B/scripts/mirror.sh OWNER/REPO MIRROR WORKTREE SHA [LOCAL_SOURCE]`. |
| `$B/fixtures/` | A copy of the brief, `appendix/{Checkout,SafetySites}.java` extracted from it with `appendix/out/` compiled, and `appendix.sha256`. |
| `$B/probes/` | Throwaway JVM programs that reproduce the brief's stated observations (`probes.sha256`, `README.md`). Not claims or adapters. `released/DagCensus.java` is **evaluation-side only**. |
| `$B/jbmc/ubuntu-22.04/{bin/jbmc,lib/core-models.jar,lib/cprover-api.jar}` | The preflight JBMC package (hard links to the files the semantics-gap setup unpacked and checked). `$B/jbmc/ubuntu-24.04-{jbmc,core-models.jar}` link to the installed `/usr/bin/jbmc` and `/usr/lib/core-models.jar`. |
| `$B/jdk/temurin-21.0.13/classes/java/util/Arrays.class` | The JDK class the Guava comparator profile adds, alone in its directory tree. |
| `$B/keys`, `$B/gnupg` | Public keys, `keys/asc/` (every `.asc`), and this setup's own keyring (`GNUPGHOME=$B/gnupg`); its agent was stopped. |
| `$B/logs/` | Every resolution, `signatures.txt`, the `javap` dumps, the build plan of 360/366, the area checks, all JVM probe output and the cargo log. |
| `$B/scripts/` | `mirror.sh`, `check_area.py` (every classpath entry of every `prepared.json` under an area), `check_sha1.py` (slice jars against Maven's stored `.sha1`). |

## Pinned revisions

Commits fetched from a local copy are content-addressed, so the commit id fixes the tree whatever the transport. XZ's
two tags carry good signatures from Lasse Collin (`3690C240CE51B4670D30AD1C38EE757D69184620`, `git verify-tag`). The
JGraphT tag is unsigned. No commit is signed.

| Worktree (`$B/src/`) | Commit | Tree | Identity |
|---|---|---|---|
| `javaparser-360-parent` | `e0eb16b8870fc05c03ab794e502dd76f97422e26` | `8faacea1…` | example 360's parent, from github.com |
| `javaparser-360-fix` | `6529f264066e31bd9e78c71111ade3a20142d285` | `41cfed9b…` | its fix (a merge; first parent `e0eb16b8`) |
| `csv-366-parent` | `94711ebf25d79bd95df8a5e70885325660f94ddc` | `9f00320c…` | example 366's parent (from the java-domain-proof source copy) |
| `csv-366-fix` | `c15a06eee95e227fbe5c61849dd12b7bf126016a` | `6fc339f3…` | its fix, parent `94711ebf` |
| `configuration-565-old` | `b485cdac96378f862237a6ad2fe3c8f57ae0612c` | `480e10dd…` | #565 old side (Jackson 2.18.3) |
| `configuration-565-new` | `d2101a20e2b74ced47ae57dd3b6d1d90b03d409b` | `5f905866…` | #565 new side (Jackson 2.19.0), parent `b485cdac` |
| `configuration-601-old` | `4c3ff511d02fb23b0ce967930bb828e8e69ee25e` | `d438a0a6…` | #601 old side (SnakeYAML 2.4) |
| `configuration-601-new` | `0721015a499d1848bdf5a524c0f8a4f3a4fbbca2` | `783199ac…` | #601 new side (SnakeYAML 2.5), parent `4c3ff511` |
| `compress-767-old` | `f3dfc34f01616abaf75cb255d59769d660428b83` | `b56ad2fb…` | #767 old side (XZ 1.11) |
| `compress-767-new` | `b0757903222468a7a6b5e80a305ca749585129d5` | `53537e5e…` | #767 new side (XZ 1.12), parent `f3dfc34f` |
| `jgrapht-1.5.2` | `fe2d4cdfa42073eb1141e789844adc9c1fc8bf36` | `e31674f0…` | = tag `jgrapht-1.5.2` (the brief's link) |
| `xz-java-1.11` | `eec2ad9de0525bbadeaabc7ba7c02ae9a7fceeec` | `b566d961…` | = tag `v1.11` (signed) |
| `xz-java-1.12` | `107a519fac1e6789101ad9c234afe3dc407be7f5` | `d678bb5c…` | = tag `v1.12` (signed; the brief's link) |
| `guava-33.4.8` | `f06690fa3e874f65515e8fd338a74d636e2c792f` | `60b8ff61…` | = tag `v33.4.8` (fast-follow setup) |
| `commons-lang-3.17.0` | `29ccc7665f3bc5d84155a3092ab2209a053324e6` | `801d67b4…` | = tag `rel/commons-lang-3.17.0` |

The Configuration and Compress sides are the commits of the receipts the brief links
(`verification/domain-foundations/receiver-verified/04/callers/*.json`). In each pair only a dependency version
changes: the compiled `client.jar` is byte-identical on both sides (565 `34f3dae0…`, 601 `89ec09e9…`, 767 `305a7e87…`).

**Released sources equal the tags** for the files the brief names. `DirectedAcyclicGraph.java` (JGraphT; `addEdge`
at line 341 as linked), `ArrayCache.java` and `BasicArrayCache.java` (XZ 1.11 and 1.12), Guava `Ints.java` (the
`tryParse(String,int)` body at 834–840) and `Longs.java`, and Lang `MutableFloat.java` (`subtract(float)` at 374–376)
are each byte-identical between the release's sources jar and the tag worktree. **`ArrayCache.java` is identical in
XZ 1.11 and 1.12**: it reads `org.tukaani.xz.ArrayCache` once in `<clinit>` (line 78). An absent value means
`Dummy`, `Basic` selects `BasicArrayCache.getInstance()`, and anything else throws `new Error(...)`.

## Released artifacts

Resolved from Maven Central with `--strict-checksums` (SHA-1 against Central's). Every main and sources jar's `.asc`
is cryptographically valid in this setup's keyring, 20 of 20 (`$B/logs/signatures.txt`). The reused graphs (Guava,
Lang, Jackson 2.19.0) were signature-checked by the fast-follow setup.

| Graph (`$B/releases/…`) | Jars (sha256) | Signed by |
|---|---|---|
| `jgrapht-core-1.5.2` | jgrapht-core `dfa596e9f0d0838f1b5e81dd0cd60e3a76c2c290ac25a0a029ffde58cf5e4c14` (**= brief**), jheaps 0.14 `49a9898d…0684279`, apfloat 1.10.1 `a1480f56…b0782ba` | Joris Kinable `EC7686239F49ED0A22F808BFADEFFDCD3F07F158` (**key expired 2025-05-01**; gpg reports `EXPKEYSIG` with `VALIDSIG`: the signature is valid and was made while the key was live); Dimitrios Michail `5F459557…777B86B2` (jheaps); Mikko Tommila `E1188CE0…ED7ADE95` (apfloat) |
| `xz-1.11` | `0a4077f6aeae2865532a564807af8d30c26acc6f63b7928d93bd7ab1f2190449` (= 767 old receipt) | Lasse Collin `3690C240…69184620` |
| `xz-1.12` | `3e158a87bd73d8afb4b6e8239c013b7d049c48563f45860ce99cd2e448cf4a6b` (= 767 new receipt) | the same |
| `jackson-2.18.3` | databind `510bdda75a7a6186c5bf33b851239488a1450906ae5757121f2e1cc48a7e108f`, core `056bc4d3…b645e1d9`, annotations `8aa5740d…4f8b8931` (= 565 old receipt) | Tatu Saloranta `28118C07…C19F3181` |
| `jackson-2.19.0` | databind `ceda311f476c3b18e1d2b240c94e2dcb9c8d44e70f8afa9facab88bac4ddc03a`, core `da8e859b…c68560e4`, annotations `ead60e9c…c156cda7` (= 565 new receipt) | the same (fast-follow setup) |
| `snakeyaml-2.4` | `ef779af5d29a9dde8cc70ce0341f5c6f7735e23edff9685ceaa9d35359b7bb7f` (= 601 old receipt) | Andrey Somov `2FC53E6B1F681184F4CCD637F5C81DE10A0B8ECC` |
| `snakeyaml-2.5` | `e6682acf1ace77508ef13649cbf4f8d09d2cf5457bdb61d25ffb6ac0233d78dd` (= 601 new receipt) | the same |
| `guava-33.4.8-jre` | guava `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed` (**= brief**) and its five dependencies | Christopher Povirk (fast-follow setup) |
| `commons-lang3-3.17.0` | `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4` (**= brief**) | Gary Gregory (fast-follow setup) |

Keys were fetched from keyserver.ubuntu.com by fingerprint or long id (`$B/keys/key-*.asc`); Saloranta's came from the
fast-follow setup.

To redo a resolution: `cd $B/resolve/NAME && mvn -B -s $B/maven-settings.xml --strict-checksums
dependency:copy-dependencies -DoutputDirectory=$B/releases/NAME/lib -DincludeScope=runtime` (with
`-Dclassifier=sources` for sources). **Offline** works for all six new graphs:
`mvn -B -o -s $B/maven-settings.xml dependency:build-classpath -Dmdep.outputFile=… -DincludeScope=runtime` wrote
every `classpath.txt`.

## The receiver campaign's area (cases 4 and 6, and the frozen cohort)

`lib/benchmark/domain-foundations/receiver_campaign.py` (and the `engineering.py` and `check_scenarios.py` it calls)
reads `--area ~/.cache/in-the-loop/tmp/domain-foundations-receivers` and `--maven-cache
~/.cache/in-the-loop/agent-tmp/0cea9d0e-0fe8-427e-8e71-96614b084e11/external-upgrade-shared-maven/repository`,
as the group jobs of 2026-11-22 did (for example `20261122-040740-group-04-original-upgrade-receivers-and`). Both are
intact. `check_area.py` read all 64 prepared records (32 frozen targets, two sides each) and found 586 distinct
classpath files, **0 missing or changed** (`$B/logs/receiver-area-check.txt`). The 102 jar entries of the 565, 601 and
767 slices each match the `.sha1` Maven stored beside them at resolution (`$B/logs/receiver-jars-sha1.txt`).

The `prepared.json` files name absolute paths in the original locations, so the campaign scripts should keep being
pointed there. The snapshot under `$B/receivers/` exists so the bytes survive a cleanup of those scratch folders.
`$B/receivers/cp/*.cp` are the same classpaths through the snapshot. `verification/domain-foundations/results.json`
(`receivers`) gives the cohort: population 32, `historicallyReceiver` 23.

Classpaths of the brief's Configuration and Compress cases (order as in `prepared.json`):

| Case, side | Commit | Dependency that changes | Other jars |
|---|---|---|---|
| 565 old / new | `b485cdac` / `d2101a20` | jackson-databind, -core, -annotations 2.18.3 → 2.19.0 | client.jar, commons-lang3 3.17.0, commons-text 1.13.1, logging 1.3.5, beanutils 1.10.1, collections 3.2.2, codec 1.18.0, jexl 2.1.1, vfs2 2.10.0, httpcore(-nio) 4.4.16, io 2.19.0, jxpath 1.4.0, xml-resolver 1.2, spring-core/-beans 5.3.39, snakeyaml 2.4, log4j 2.24.3 (three jars) |
| 601 old / new | `4c3ff511` / `0721015a` | snakeyaml 2.4 → 2.5 | client.jar, commons-lang3 3.18.0, text 1.14.0, beanutils 1.11.0, codec 1.19.0, io 2.20.0, **jackson 2.20.0** (both sides), log4j 2.25.1, the rest as 565 |
| 767 old / new | `f3dfc34f` / `b0757903` | xz 1.11 → 1.12 | client.jar, zstd-jni 1.5.7-6, brotli dec 0.1.2, codec 1.21.0, asm 9.9.1, io 2.21.0, lang3 3.20.0 |

## Examples 360 and 366

`python3 examples/tools/build.py --plan 360 366` (saved as `$B/logs/build-plan-360-366.json`): 360 is B11 with 25
tasks (`replay`, then 24 `prove` tasks over postorder, terminal, preorder and nonempty, each parent and fix, in plain,
`-observed` and `-node-startup` forms). 366 is B11 with 5 tasks (`replay`, `fields-{parent,fix}` calibration,
`prefixes-{parent,fix}` preservation). Every task is executable. Their upstream-build artifacts are captured
(`records/build-historical/build-*.json` for 360, `records/original-build/build-*.json` for 366). The one original
JAR of each record is in the content-addressed target cache, so `build.py` restores rather than rebuilds:

| JAR | sha256 | Built with |
|---|---|---|
| javaparser-core-3.26.2-SNAPSHOT, parent `e0eb16b8` | `cbe961009b6fafe13085b895a486660a470485ac34316043e20df41188f446a8` | Temurin 17.0.21 (recipe `jdk: 17`); runs on 21 |
| the same, fix `6529f264` | `62cf2f2c4bb4be2ced24f7914b4d22ae9cc2a760a5ab11cd2cd867e68d69cd27` | the same |
| commons-csv-1.10.0-SNAPSHOT, parent `94711ebf` | `0c7bb36fb90647a396ca780759bf881ee214ccaf4df8ea039add8275b4566508` | Temurin 21.0.13 |
| the same, fix `c15a06ee` | `b71afe50e79e1df7e577206e92872c697e8c17a1101938739507251834132446` | the same |

Neither runtime classpath has a dependency beyond the JAR. These are SNAPSHOT builds of exact commits, pinned by
digest. The tasks themselves are B11 runs, so they are verification jobs under `CLAUDE.md`; this setup ran none.

### Landed upstream regressions

Both already ran at these commits, with results committed:
- **CSV #218**: `JiraCsv288Test#testParseWithDoublePipeDelimiter` and `…Quoted` fail on the parent (`expected:
  <a,b,c,d,,f> but was: <a,b|c,d,|f>`) and pass on the fix. Source:
  `examples/366-…/records/original-build/{parent,fix}-upstream.json`, written by job
  `20261122-062500-build-and-check-366-commons-csv-delimite`, whose step 1 passed.
- **JavaParser #4538**: `NodeTest$PostOrderIteratorTest#rootHasNoChild` errors with `EmptyStackException` on the
  parent (the test transplanted) and passes on the fix. Source: `examples/360-…/records/build-historical/{parent,fix}-upstream.json`.

Nothing has changed in these inputs since, so they were not queued again. The JVM probes below reproduce the same
behaviour directly from the captured JARs.

## Tools

| What | sha256 | Where |
|---|---|---|
| JBMC 6.11.0, 22.04 package: the brief's preflight binary | `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c` (**= brief**) | `$B/jbmc/ubuntu-22.04/bin/jbmc` |
| its `core-models.jar` | `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de` (**= brief**) | `$B/jbmc/ubuntu-22.04/lib/core-models.jar` |
| JBMC 6.11.0, installed 24.04 package (on `PATH`) | `200f4cbb…a722ec35`, models `a31ef93b…6ea49df` | `/usr/bin/jbmc`, `/usr/lib/core-models.jar` |
| `java/util/Arrays.class`, Temurin 21.0.13 | `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab` (**= brief**, extracted again with `jimage` today) | `$B/jdk/temurin-21.0.13/classes/` (the directory the Guava profile puts before the models jar) |
| `jvmcontract 0.1.0` release build | `b1e0edad5632990ef4797b8aaf23f82fa0beba809c9c8d8cfbd00805cf5ef389` (17,286,200 bytes) | `lib/target/release/jvmcontract` |

Both JBMC binaries report `6.11.0 (cbmc-6.11.0)`. The semantics-gap setup found that the two models jars decide
differently on one seed, so name the pairing in every standalone run. The checker:
`cargo build --release -j 6 --bin jvmcontract` under `systemd-run --user --scope -p MemoryMax=12G` found it fresh
for `lib/` at `@-` = `11665a892e6d`. That commit descends from the brief's planning baseline `2fff2b0d` (169 commits
later). The binary is a build product of this workspace and the next release build overwrites it.
`python3 -B lib/benchmark/java-semantics-gap/scorecard.py --check` passes at this head ("38 historical and 60
original statements, with raw evidence checked"). That is the 15-case campaign that the recommended step 4
remeasures, and its inputs are recorded in [`jbmc-java-semantics-gap-brief-setup.md`](jbmc-java-semantics-gap-brief-setup.md).

## The appendix fixtures

Extracted from the brief's two code blocks into `$B/fixtures/appendix/` and compiled with `$J/javac -g -d out
Checkout.java SafetySites.java` (class major 65). Sources: `Checkout.java` `8e473a34…0f5f1576`, `SafetySites.java`
`30f01730…5c6a293d`. Classes: `Checkout` `14b44637…2f131379d4`, `Checkout$Pair` `886e1d76…5c75ef8d`,
`Checkout$Stock` `b565b4ab…0bdaff6c82fd`, `SafetySites` `def12585…9da45a8e52` (`$B/fixtures/appendix.sha256`).

`run(II)I` bindings on this classfile (`$B/logs/javap-SafetySites.txt`) are those the brief observed: `idiv` at
**19**, exception table `16 20 21 java/lang/ArithmeticException` (handler at **21**), `iaload` at **44**,
`arraylength` at **54**. The mutant (first guard `mode > 3`, `$B/probes/safety-mutant/`, source `de38eff7…`, class
`6f9749d3…`) keeps the three sites at 19, 44 and 54.

## What was replayed on a JVM

Everything ran on Temurin 21.0.13, inline, each in about a second. Output is in `$B/logs/`.

| Case | Program | Brief says | Observed |
|---|---|---|---|
| 1 | `java -ea Checkout` | the five boundary counts pass in both alias states; the alias-blind claim fails at `open(1, true)` | "Shared backup changed from 1 to 0", exit 0 |
| 2 | `java SafetySites M V` | `(0,0)` −10, `(0,3)` 6, `(1,2)` escapes AIOOBE, `(3,0)` −99, `(2,0)` 21 | exactly these, plus `(1,0)` 3 and `(1,1)` 4 |
| 2 | mutant `SafetySites 3 0` | NPE at the `arraylength` | "escaped java.lang.NullPointerException" |
| 3 | `probes/originals/CsvPipes` on the two captured JARs | `a\|\|b\|\|`: parent `["a","b\|"]`, fix `["a","b",""]` | parent `["a","b\|"]` size 2; fix `["a","b",""]` size 3 |
| 4 | `probes/upgrades/RunCases` with the registered `UpgradeProbe` on each `$B/receivers/cp/*.cp` | `"[red, blue]"`, `"[Ada]"`, `"[7]"`, `null` on every side | 565 old and new, 601 old and new: all four, in order |
| 6 | the same, case 767 | empty, `hello\n`, `00 ff 00 80`, bytes 0–15 | all four, both sides (base64 as the receipt) |
| 6 | `probes/upgrades/XzProfile`, one fresh JVM per side and profile | absent or `Dummy`: dummy cache; `Basic`: basic cache; `Bogus`: `Error`, then `NoClassDefFoundError` | XZ 1.11 and 1.12 alike. Absent and `Dummy`: `ArrayCache` (the dummy instance), frames decoded. `Basic`: `BasicArrayCache`, frames decoded. `Bogus`: frame 1 `java.lang.Error: Unsupported value 'Bogus' …`, frames 2–4 and `getDefaultCache()` `NoClassDefFoundError: Could not initialize class org.tukaani.xz.ArrayCache` |
| 6 | `probes/originals/TreeProbe` on the two captured JARs | empty postorder: parent `EmptyStackException`, fix root; package `com`: `name, package, root`; preorder control | parent: empty `findAll(POSTORDER)` and `PostOrderIterator` throw `EmptyStackException`, empty preorder `root`. Fix: empty postorder `root`, iterator `root`. Both: `com` postorder `name package root`, preorder `root package name`, iterator exhausted after `root` |
| 6 | `TreeProbe clear` (clears `line.separator` before first use) | initialization failure, then failure on reuse | both sides: use 1 `ExceptionInInitializerError` caused by `NullPointerException`; use 2 `NoClassDefFoundError` caused by `ExceptionInInitializerError` |
| 5 | `probes/released/DagCensus` (evaluation side) | 25 graphs, 150 transitions: 48 insertions, 48 duplicates, 54 cycle exceptions; the identity control | `graphs=25 transitions=150 insert=48 duplicate=48 cycle=54 oracleMismatches=0`. Single edge `a→b`: existing edge with unregistered source `x` returns false; fresh edge with `x` throws `IllegalArgumentException`; null edge `a→c` throws `NullPointerException`; afterwards vertices `[a, b, c]`, one edge, `a→b` |
| 7 | `probes/released/GuavaHex` | all 131,072 strings agree with an ASCII oracle; the wrong minimum rule fails once | `strings=131072 agree=131072`, 22 positive values, 1 negative (`MIN_VALUE` at `u == '0'`), the wrong rule fails once; `tryParse("7ffffff~",16)` is null on the JVM |
| 8 | `probes/released/LangFloat` | `x=0x3f800001, y=0x3f800000` gives `0x34000000`; after adding `2.0f`, positive zero | `0x34000000` (exact against the double difference), translated `0x00000000`. 100,000 seeded random `[1,2)` pairs: 0 mismatches |

DagCensus builds each graph with `new DirectedAcyclicGraph<>(null,null,false)`, vertices `a, b, c`, and fresh
`DefaultEdge` insertions in lexicographic arc order, as the brief's comparator profile says. It compares every
pre-existing edge and both endpoint identities after each operation. The composition client of case 7 and the
137,257-string census need the client the brief asks the domain work to build, so this setup did not reproduce them.
Case 9 has no fixture to reproduce yet.

## Disk

`$B` is about 1 GB as `du` counts it without `receivers/`. Most of that is `$B/m2`, hard links into the fast-follow
repository, plus about 30 MB of new jars. `receivers/` is 2.4 GB as counted, all hard links (no new blocks). The six new
bare mirrors take about 120 MB (commons-compress 59 MB, commons-csv 36 MB, javaparser 20 MB). Nothing was left in
`/tmp`, and `$B/tmp` is empty.

## Setup Agent Notes

### What is ready, and where

- `$B = ~/.cache/in-the-loop/receiver-construction`. Use JDK 21 by full path,
  `~/.sdkman/candidates/java/21.0.13.0+9-tem/bin/` (the default `java` is 25).
- **Released libraries** (checksummed, 20/20 signatures valid, with sources jars and ordered classpaths):
  `$B/releases/{jgrapht-core-1.5.2,guava-33.4.8-jre,commons-lang3-3.17.0,xz-1.11,xz-1.12,jackson-2.18.3,jackson-2.19.0,snakeyaml-2.4,snakeyaml-2.5}/classpath.txt`.
  The JGraphT, Guava and Lang JARs match the brief's SHA-256 values. Offline re-resolution works
  (`mvn -o -s $B/maven-settings.xml` in `$B/resolve/NAME`).
- **Sources at every pinned revision** (`$B/src/`): JavaParser 360 parent and fix, CSV 366 parent and fix,
  Configuration 565 and 601 old and new, Compress 767 old and new, JGraphT 1.5.2, XZ 1.11 and 1.12, Guava 33.4.8,
  Lang 3.17.0. The released sources equal the tags for every file the brief links.
- **Cases 4 and 6, and the 23 historically receiver-blocked targets**: the earlier campaign's area and Maven cache
  are intact (586 classpath files, 0 changed). Keep pointing `receiver_campaign.py` at the original paths. Ordered
  classpaths for 565, 601 and 767, both sides, are in `$B/receivers/cp/`, with a hard-link snapshot under
  `$B/receivers/`.
- **Examples 360 and 366**: their four captured upstream JARs are in the target cache (`build.py` restores them) and
  linked in `$B/originals/`. The build plan is in `$B/logs/build-plan-360-366.json`.
- **Appendix fixtures**: compiled in `$B/fixtures/appendix/out`.
- **Comparator inputs**: JBMC 6.11.0 preflight package `$B/jbmc/ubuntu-22.04/` and the `Arrays.class` directory
  `$B/jdk/temurin-21.0.13/classes/`, both matching the brief's digests.
- **Checker**: `lib/target/release/jvmcontract` is current for `lib/` at `11665a89`.

### What was verified on a JVM

Every observation the brief states for an existing library or fixture reproduced exactly. The detail is in the
[table above](#what-was-replayed-on-a-jvm).
- Case 1: `Checkout`.
- Case 2: the `SafetySites` outputs and offsets 19/21/44/54, and the `mode > 3` mutant's NPE.
- Case 3: CSV `a||b||`, parent against fix.
- Case 4: the four registered observations on all four Configuration sides.
- Case 6: the 767 frames on both sides, and the XZ cache profiles on 1.11 and 1.12 (absent, `Dummy`, `Basic`, and
  `Bogus` giving `Error` then `NoClassDefFoundError`). JavaParser's traversals and the cleared-`line.separator`
  failures on both sides.
- Case 5: the JGraphT census (25/150, 48/48/54) and the identity control.
- Case 7: the Guava 131,072-string agreement and the single minimum failure.
- Case 8: the Commons Lang witness bits.
- The landed regressions of #218 and #4538 (fail on parent, pass on fix) are on record from 2026-11-22 runs at the
  same commits. They were not re-run.

### What to know before starting

- **JGraphT's signing key has expired** (Kinable, 2025-05-01). The signature is valid and was made while the key was
  live. The JGraphT tag is unsigned.
- The **XZ initializer is byte-identical in 1.11 and 1.12**, and so is each Configuration or Compress pair's compiled
  `client.jar`. Only the named dependency differs between sides. **601 runs Jackson 2.20.0 on both sides.**
- The 360 and 366 originals are **SNAPSHOT builds of exact commits** (`3.26.2-SNAPSHOT`, `1.10.0-SNAPSHOT`), pinned by
  digest in the target cache. A rebuild is a job, recipe in the plan. JavaParser's recipe builds on JDK 17.
- The receiver area and its Maven cache live under `~/.cache/in-the-loop/tmp/` and `agent-tmp/`, and the
  `prepared.json` paths point there. If they disappear, the bytes are in `$B/receivers/`, but the absolute paths
  would need re-preparing.
- `tryParse("7ffffff~",16)` is null on the JVM. The brief's stock-JBMC acceptance of it is a comparator artifact.
- `$B/probes/released/DagCensus.java` is an evaluation-side reproduction. Keep it out of the generator's inputs for
  case 5.

### What is left for the domain work on purpose

- Repeating the named jobs of 360 and 366, and the Configuration receipts, as opening results. Those are B11 and
  campaign runs, so they are jobs.
- Every JBMC comparator run and every native run. None was made.
- The isolation control of case 4, the property-read approach of case 6, case 7's `id=<hex>` client and its
  137,257-string census, case 8's adjacent-range transfer, and case 9's three-worker fixture and schedule enumerator.
- All claims, examples, sidecars, scoring and the frozen generator.
