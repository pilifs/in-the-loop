# Setup for the JBMC fast-follow brief (callbacks, conversions, arrays)

Mechanical setup for [`jbmc-fast-follow-calls-conversions-and-arrays.md`](jbmc-fast-follow-calls-conversions-and-arrays.md),
done on 2026-11-23 by a setup session (Claude Opus 5.5) before the domain work starts. It resolved the released
libraries the brief names, with their sources and signatures, fetched the five source revisions the brief links,
pointed at both JBMC 6.11.0 packages, extracted and hashed the two JDK classes the brief names, built the checker's
release binary at this head, compiled the brief's appendix fixtures and ran their JVM controls. It wrote no claims,
examples, sidecars, adapters or recipes, allocated no example ids, ran neither the project verifier nor JBMC on any
claim, and changed nothing in `lib/` or the checker. Everything downloaded or built is outside the checkout, under
`~/.cache/in-the-loop/`, except the checker binary, which cargo writes to its usual place, `lib/target/release/`.

`$B` below is `~/.cache/in-the-loop/jbmc-fast-follow`. Every case in the brief is an **unmodified release** (no
parent/fix pairs, no landed upstream regression), so there was no upstream build or upstream test run, and **no
verification job** was needed. Setup is complete.

## Layout

| Path | What it holds |
|---|---|
| `$B/releases/NAME/` | Released artifacts from Maven Central: `lib/` (jars), `sources/` (their sources jars), `classpath.txt` (ordered, absolute paths into `$B/m2`), `tree.txt`. Graphs: `guava-33.4.8-jre`, `commons-lang3-3.17.0`, `commons-collections4-4.5.0`, `commons-math3-3.6.1`, `jackson-2.19.0` (databind, core, annotations). |
| `$B/resolve/NAME/pom.xml` | The throwaway POM that resolved each graph. |
| `$B/m2`, `$B/maven-settings.xml` | The Maven local repository (seeded by hard links from `~/.cache/in-the-loop/jbmc-java-semantics-gap/m2`, so shared files take no extra space) and settings that point at it (`mvn -s $B/maven-settings.xml`). |
| `~/.cache/in-the-loop/git-mirrors/{guava,commons-lang,commons-collections,jackson-databind,commons-math}.git` | One bare repository per upstream, shared. `jackson-databind` and `commons-math` are new; the pinned commits were fetched by full id at depth 2. |
| `$B/src/NAME` | One detached worktree per pinned revision ([below](#pinned-revisions)). To add a revision: `$B/scripts/mirror.sh OWNER/REPO MIRROR WORKTREE SHA`. |
| `$B/jbmc/ubuntu-22.04/{bin/jbmc,lib/core-models.jar,lib/cprover-api.jar}` | The 22.04 package's JBMC (hard links to the files the previous setup unpacked and checked). |
| `$B/jbmc/ubuntu-24.04/{jbmc,core-models.jar}` | Symlinks to the installed 24.04 package, `/usr/bin/jbmc` and `/usr/lib/core-models.jar`. |
| `$B/jdk/temurin-21.0.13/classes/`, `classes.sha256` | 53 `java.base` classes extracted from the Temurin 21.0.13 image with `jimage`: `Comparator`, `Comparators*`, `Arrays*`, `Objects`, `jdk/internal/util/ArraysSupport`, `Long`, `Integer`, `Short`, `Float`, `Double`, `Number`, `Math`, `StrictMath`, `FdLibm*`, `jdk/internal/math/{FloatToDecimal,DoubleToDecimal,FloatingDecimal*}`. |
| `$B/fixtures/` | `jbmc-fast-follow-calls-conversions-and-arrays.md` (copy of the brief), `fast-follow-fixtures/` (the 14 appendix sources, extracted with the brief's own script, and `out/{callbacks,numeric,rows}` compiled), `fixtures.sha256`, `classes.sha256`, and `{callbacks,numeric,rows}.cp` (the ordered library classpath of each family). |
| `$B/probes/exact/ExactBits.java` | One throwaway JVM program replaying the exact values the brief states ([below](#what-was-replayed-on-a-jvm)). Not a claim, not an adapter. |
| `$B/keys`, `$B/gnupg` | Public keys and this setup's own keyring (`GNUPGHOME=$B/gnupg`), apart from the user's. Its agent was stopped. `$B/keys/asc/` holds every `.asc` and Central's `.sha1`. |
| `$B/logs` | Every resolution, the signature table, the JVM control output, the `javap` dumps and the cargo build log. |

JDK: Temurin 21.0.13+9 (`~/.sdkman/candidates/java/21.0.13.0+9-tem`, `lib/modules` sha256
`a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c`, built from `adoptium/jdk21u`). The brief's
preflight says "OpenJDK 21.0.13"; the two class digests it gives match this image exactly ([below](#jdk-classes)).
Maven 3.10.0 (SDKMAN). No other JDK or build tool is needed: nothing in the brief is built from source.

## Released artifacts

All from Maven Central, resolved with `--strict-checksums` (SHA-1 against Central's) and checked again against each
`.sha1` by hand. Every main jar's and sources jar's `.asc` is a good signature in this setup's keyring (23 of 23;
`listenablefuture-9999.0` has no sources jar). Table: `$B/logs/signatures.txt`.

| Graph (`$B/releases/…`) | Jars (sha256) | Signed by |
|---|---|---|
| `guava-33.4.8-jre` | guava `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed`; failureaccess 1.0.3 `cbfc3906…59cb`, listenablefuture 9999.0 `b372a037…3f99`, jspecify 1.0.0 `1fad6e6b…fbab`, error_prone_annotations 2.36.0 `77440e27…61a5`, j2objc-annotations 3.0.0 `88241573…7c64` | Christopher Povirk `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (guava, failureaccess, listenablefuture, j2objc); Chris Povirk `41CD49B4EF5876F9E9F691DABAC30622339994C4` (jspecify); Liam Miller-Cushon `EE0CA873074092F806F59B65D364ABAA39A47320` (error_prone) |
| `commons-lang3-3.17.0` | commons-lang3 `6ee731df5c8e5a2976a1ca023b6bb320ea8d3539fbe64c8a1d5cb765127c33b4` (no runtime dependencies) | Gary David Gregory `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` |
| `commons-collections4-4.5.0` | commons-collections4 `00f93263c267be201b8ae521b44a7137271b16688435340bf629db1bac0a5845` (none) | the same |
| `commons-math3-3.6.1` | commons-math3 `1e56d7b058d28b65abd256b8458e3885b674c1d588fa43cd7d1cbb9c7ef2b308` (none) | Evan Ward `41A1A08C62FCA78B79D3081164A16FAAEC16A4BE` |
| `jackson-2.19.0` | jackson-databind `ceda311f476c3b18e1d2b240c94e2dcb9c8d44e70f8afa9facab88bac4ddc03a` (**= brief**), jackson-core `da8e859bac94874528116a25f20c68560e4287acbf27628711b8a4f96b028430`, jackson-annotations `ead60e9cac0e42b57092b9e2d087ff43536e9477d4486ba393037a8cc156cda7` | Tatu Saloranta `28118C070CB22A0175A2E8D43D12CA2AC19F3181` |

Keys: the Apache Commons `KEYS` (sha256 `f154a693…3299a`, which holds Gregory's and Ward's) and Povirk's
`F6D4A1D4…` key come from the previous setup's `keys/`; the other three were fetched from keyserver.ubuntu.com by
long key id (`$B/keys/key-*.asc`).

Library class versions (major): Guava `Longs` 52, Commons Lang `NumberUtils` 52, Jackson `LongNode` 52, Collections
`ObjectArrayIterator` 52, Commons Math `MathArrays` **49** (Java 5).

To redo a resolution: `cd $B/resolve/NAME && mvn -B -s $B/maven-settings.xml --strict-checksums
dependency:copy-dependencies -DoutputDirectory=$B/releases/NAME/lib -DincludeScope=runtime` (add `-Dclassifier=sources`
for the sources). **Offline** (`mvn -o`) works for all five graphs (checked).

## Pinned revisions

The brief links source files at five commits. Each was fetched by its full id and compared with its release tag
through the GitHub API (`repos/R/commits/TAG`): **every one is exactly the release tag**. None carries a commit
signature.

| Worktree (`$B/src/`) | Tag | Commit | Tree | Date, author |
|---|---|---|---|---|
| `guava-33.4.8` | `v33.4.8` | `f06690fa3e874f65515e8fd338a74d636e2c792f` | `60b8ff6155dfcfb23d160979664839dae7b7a2d5` | 2025-04-14, Chris Povirk |
| `commons-lang-3.17.0` | `rel/commons-lang-3.17.0` | `29ccc7665f3bc5d84155a3092ab2209a053324e6` | `801d67b4480c51ebb6a006b243de46a4d88b0c3b` | 2024-08-24, Gary Gregory |
| `commons-collections-4.5.0` | `rel/commons-collections-4.5.0` | `7f7fb0244abc940a2e9dd28b67508c0483a58c3e` | `587ea353928a4e3885ba85117021db0b4410aeda` | 2025-04-19, Gary D. Gregory |
| `jackson-databind-2.19.0` | `jackson-databind-2.19.0` | `f644a920f4ac768797edf7709070411837c83ef8` | `1ccea4958620b08773a906b2af8ef2e300c7e908` | 2025-04-24, Tatu Saloranta |
| `commons-math-3.6.1` | `MATH_3_6_1` | `16abfe5de688cc52fb0396e0609cb33044b15653` | `55310ccbae02bf01eba9c0c7fe150c5800a657ef` | 2016-03-17, Evan Ward |

**Released sources equal the tags.** Each file the brief names is byte-identical between the release's sources jar
and the tag worktree: Guava `primitives/Longs`, `collect/ComparisonChain`, `collect/Ordering`; Commons Lang
`math/NumberUtils`, `mutable/MutableLong`, `ArrayUtils`, `ObjectUtils`, `ArrayFill`; Collections
`iterators/ObjectArrayIterator`, `queue/CircularFifoQueue`; Jackson `node/LongNode`, `DoubleNode`, `NumericNode`,
`ValueNode`; Commons Math `util/MathArrays`, `exception/DimensionMismatchException`. The brief's line anchors land
where it says: `ArrayUtils.reverse(Object[])` at 6822, `ObjectUtils.compare(c1,c2,nullGreater)` at 311 (the two-argument
`compare` delegates to it just above), `ArrayFill.fill(T[],T)` at 143, `Ordering.min(a,b)` at 620–625;
`MathArrays.checkRectangular(long[][])` is at line 560.

## Tools

### JBMC 6.11.0

Both packages are as the previous setup checked them (record:
[`jbmc-java-semantics-gap-brief-setup.md`](jbmc-java-semantics-gap-brief-setup.md#jbmc-6110-two-packages)); the
digests were re-taken today and match the brief's prefixes:

| Brief role | `jbmc` sha256 | `core-models.jar` sha256 | Where |
|---|---|---|---|
| 22.04: the five numerical rows | `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c` | `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de` | `$B/jbmc/ubuntu-22.04/` |
| 24.04: callbacks and ragged-array controls (installed) | `200f4cbb273d94268cdf933ee1f7c5ea96c8abc95af83836c2ffc082a722ec35` | `a31ef93bfe898d373bb7eca6aef3b9ee2ebf05b0fe8efb305f86528396ea49df` | `/usr/bin/jbmc`, `/usr/lib/core-models.jar` (`$B/jbmc/ubuntu-24.04/`) |

Both report `6.11.0 (cbmc-6.11.0)`. `jbmc` on `PATH` is the 24.04 one. The previous setup found the two models jars
decide different answers on one of its seeds, so name the pairing in every standalone run.

### JDK classes

| Class (Temurin 21.0.13 image) | sha256 | Brief |
|---|---|---|
| `java/util/Comparator.class` | `31213c77d79b01f269b7e3ee1008a1cbe0ce11b4442d2401346de6ca80d8d095` | = (the `ComparisonChain` profile) |
| `java/util/Arrays.class` | `4a41d89cb79284298b95303a66b3738955d22694f9b34016d87241d9ae8193ab` | = (the reference-fill transfer) |

Both are in `$B/jdk/temurin-21.0.13/classes/java/util/`, with the other 51 in `classes.sha256`. To add a class:
`jimage extract --dir X --include 'regex:/java.base/PATH\.class' ~/.sdkman/candidates/java/21.0.13.0+9-tem/lib/modules`.

### The checker

`lib/target/release/jvmcontract`, built at this head (`@-` = `c41bda172b50`, a descendant of the brief's
`9d9a860c`; seven commits later, including the cycle-3 merge `30a84499`) with
`cargo build --release -j 6 --bin jvmcontract` under `systemd-run --user --scope -p MemoryMax=12G`.
It finished in 3 min 7 s (log `$B/logs/cargo-build-release.log`). Binary sha256
`e41539fd3d8b935a8165c0e70257e2bd8f898e3e50c2346b473880930b00be65` (17,219,224 bytes, `jvmcontract 0.1.0`), from a
`lib/` tree identical to `@-`'s. It is a build product of this workspace and is overwritten by the next release build.

`lib/benchmark/run.py` and `examples/tools/impact_check.py` default to `lib/target/release/jvmcontract`; the
campaign (`lib/benchmark/java-semantics-gap/campaign.py`) reads `$JVMCONTRACT`. `python3 -B
lib/benchmark/java-semantics-gap/scorecard.py --check` passes at this head ("38 historical and 60 original
statements, with raw evidence checked", 2 s).

## The fixtures

`$B/fixtures/fast-follow-fixtures/` holds the 14 sources, extracted by the brief's own script (sha256 in
`$B/fixtures/fixtures.sha256`), compiled per family on JDK 21.0.13 with the brief's command
(`javac -g -parameters -cp "$(cat $B/fixtures/FAMILY.cp)" -d out/FAMILY FAMILY/*.java`), class file major version
**65** (the campaign runner compiles its own fixtures with `-source 8 -target 8`; this setup did not). Class digests in
`$B/fixtures/classes.sha256`. Classpaths, in order:

| Family | `$B/fixtures/FAMILY.cp` |
|---|---|
| `callbacks` | Guava 33.4.8-jre graph, then Commons Lang 3.17.0 |
| `numeric` | jackson-databind, jackson-core, jackson-annotations 2.19.0, then Commons Lang 3.17.0 |
| `rows` | Commons Lang 3.17.0, Commons Collections 4.5.0, Commons Math 3.6.1 |

### Method-reference descriptors in the classfiles

From `javap -v -p` (`$B/logs/javap-{Lift,Chain}.txt`). Every site bootstraps through
`LambdaMetafactory.metafactory` with `REF_invokeStatic`:

| Site | SAM type (erased) | Target | Instantiated type |
|---|---|---|---|
| `Lift.lift()` → `Bi` | `(II)J` | `com/google/common/primitives/Longs.compare:(JJ)I` | `(II)J` |
| `Lift.box()` → `Box` | `(Ljava/lang/Integer;Ljava/lang/Integer;)J` | `Longs.compare:(JJ)I` | the same |
| `Lift.again()` → `Twice` | `(SS)J` | `org/apache/commons/lang3/math/NumberUtils.compare:(SS)I` | `(SS)J` |
| `Chain.guarded` → `Comparator<Integer>` | `(Ljava/lang/Object;Ljava/lang/Object;)I` | `Longs.compare:(JJ)I` | `(Ljava/lang/Integer;Ljava/lang/Integer;)I` |

## What was replayed on a JVM

All on Temurin 21.0.13 with `-ea`, inline, each in about a second. Output: `$B/logs/jvm-controls.log`,
`$B/logs/probe-exactbits.log`. From `$B/fixtures/fast-follow-fixtures/`:
`java -ea -cp "out/FAMILY:$(cat ../FAMILY.cp)" CLASS`.

| Program | Brief says | Observed |
|---|---|---|
| `LiftChecks` | 25 int pairs × (correct, boxed, transfer), null unboxing, three wrong claims fail | exit 0 |
| `Replay` | the stock counterexamples at `(0,1)` and the direct-call controls | "All exact control inputs replayed.", exit 0 |
| `ChainTests` | `good(-1,2)`, skipped null, active null throws NPE, `wrong(0,1)` fails | exit 0 |
| `NodeAssertions` | 100,000 random longs and doubles hold; both witnesses fail | "LongNode double-rounding witness", "Half-minimum subnormal witness", exit 0 |
| `RaggedJvm` | 209 two-slot graphs, 12 shared nonempty; `{new int[0], null}` falsifies both wrong alternatives | `total=209 bad inversion=195 bad snapshot=195 shared nonempty=12 both nonempty=156`, exit 0 |
| `MatrixJvm` | 21 non-null outer shapes: 8 normal, 7 NPE, 6 `DimensionMismatchException`; one-row `{null}` returns normally | `census=21 normal=8 NPE=7 dimensions=6`, exit 0 |

`$B/probes/exact/ExactBits.java` (`java -ea -cp "$(cat ../../fixtures/numeric.cp):…guava…:…collections…" ExactBits.java`,
classpath in the log) checked the brief's stated values; all held:

- `new LongNode(0x0040000040000001L).floatValue()` raw bits `0x5a800001`; through `DoubleNode(node.doubleValue())`
  `0x5a800000`; `MutableLong` agrees with the direct path on that input.
- `new DoubleNode(0x1p-150).floatValue()` raw bits `0x00000000` (positive zero); `nextUp(0x1p-150)` and `0x1p-149`
  give bits `0x00000001`.
- The graduation classification held on 1,056,768 inputs (halfway ±64 in 8,192 bins: the first 4,096, every 4,093rd,
  and the last ~2,048), with exactly two disagreements per bin, at `delta ∈ {1,2}` for even `hi` and `{−1,−2}` for odd.
  A finite grid, not the 2⁵⁴ domain.
- Reserve 4: `ObjectUtils.compare("\uD800","\uD802")` and `Ordering.natural().compare` give −2; `Ordering.min` keeps
  the first of two equal-valued distinct strings.
- Reserve 5: `ArrayFill.fill(new Integer[0], "x")` returns the same array; on `new Integer[]{7,8}` it throws
  `ArrayStoreException` with slot 0 still 7. `CircularFifoQueue(2)` holding two elements has `isFull() == false`.
- #375's literal: `Float.valueOf("0.100000001490116121")` gives bits `0x3dcccccd` on the JVM.

No JBMC run and no project verifier run was made: those are the opening comparison, which is the domain work.

## Disk

`$B` is about 580 MB as `du` counts it, almost all of it `$B/m2`, which is hard links into the previous setup's
repository (about 40 MB of new jars). The worktrees take about 100 MB, the two new bare mirrors 7 MB. Nothing was
left in `/tmp`; scratch went to `$B/tmp`.

## Setup Agent Notes

### What is ready, and where

- `$B = ~/.cache/in-the-loop/jbmc-fast-follow`. Released libraries, signed and checksummed, with sources jars and
  ordered classpaths: `$B/releases/{guava-33.4.8-jre,commons-lang3-3.17.0,commons-collections4-4.5.0,commons-math3-3.6.1,jackson-2.19.0}/classpath.txt`.
  Offline re-resolution works: `mvn -o -s $B/maven-settings.xml` in `$B/resolve/NAME`.
- Source at every revision the brief links, all exactly the release tags: `$B/src/{guava-33.4.8,commons-lang-3.17.0,commons-collections-4.5.0,jackson-databind-2.19.0,commons-math-3.6.1}`.
  The released sources jars equal these files.
- The brief's appendix fixtures, extracted by its own script and compiled on JDK 21.0.13:
  `$B/fixtures/fast-follow-fixtures/{callbacks,numeric,rows}/` with classes in `out/FAMILY/`; the matching library
  classpaths in `$B/fixtures/FAMILY.cp`. Use these for the brief's sample commands (`--classes out/numeric
  --classpath "$(cat $B/fixtures/numeric.cp)"`).
- JBMC 6.11.0: 22.04 package in `$B/jbmc/ubuntu-22.04/` (numerical rows), 24.04 installed (`jbmc` on `PATH`,
  `/usr/lib/core-models.jar`; callbacks and rows). Digests match the brief.
- The JDK classes the brief names, from the Temurin 21.0.13 image, with digests equal to the brief's:
  `$B/jdk/temurin-21.0.13/classes/java/util/{Comparator,Arrays}.class` (51 related classes alongside).
- The checker's release binary at this head: `lib/target/release/jvmcontract` (sha256 `e41539fd…00be65`, built from `c41bda17`'s `lib/`, before any change of yours).

### What was verified on a JVM

Every appendix program behaves as the brief says: `LiftChecks`, `Replay`, `ChainTests`, `NodeAssertions`,
`RaggedJvm` (209 graphs, 12 shared nonempty) and `MatrixJvm` (21 shapes: 8 normal, 7 NPE, 6 mismatch). The exact
witness bits (`0x5a800001` direct vs `0x5a800000` through double; `+0.0f` at `2^-150`), the disagreement
classification on a finite grid of 8,192 bins, and the reserve cases' JVM facts (−2 for `U+D800` vs `U+D802`,
`Ordering.min` identity, `ArrayFill` covariance, `CircularFifoQueue.isFull()` false at two of two) also held. The
javac bootstrap descriptors are recorded in the setup record's
[descriptor table](#method-reference-descriptors-in-the-classfiles).

### What to know before starting

- The repository is past the brief's `9d9a860c`: this head includes the cycle-3 merge (`30a84499`) and the Commons
  Lang decimal decisions. The kickoff check passes here (`scorecard.py --check`: 38 historical, 60 original). Pin
  your successor commit and the checker digest yourself, as the brief asks.
- The fixtures were compiled to class version 65 with the brief's `javac` command. The campaign runner compiles with
  `-source 8 -target 8`; if your intake needs that, recompile — the descriptors above do not change.
- JDK is Temurin 21.0.13, not Debian's build; the two class digests the brief gives match it exactly, so the
  `Comparator` and `Arrays` profiles are reproducible here. Other `java.base` classes were not compared with Debian's.
- The two JBMC models jars are compiled differently and can change answers; name the pairing in each standalone run.
- Nothing is a snapshot: every dependency is a signed release.

### What is left for the domain work on purpose

All JBMC and project-verifier runs (the four-column opening comparison), the replay regression, any example scaffolding
and claims, the choice of standalone classpath profiles (stock models vs. adding `Comparator.class` or `Arrays.class`),
the `-source 8` question, the encodings for the numeric and nested-array work, and every checker change.
