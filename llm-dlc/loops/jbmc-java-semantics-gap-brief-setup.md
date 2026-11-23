# Setup for the JBMC Java semantics gap brief

Mechanical setup for [`jbmc-java-semantics-gap-brief.md`](jbmc-java-semantics-gap-brief.md), done on 2026-11-23 by a
setup session (Claude Opus 5.5) before the domain work starts. It fetched the pinned sources, the released artifacts
and both JBMC 6.11.0 packages, checked their hashes and signatures, built the original artifacts the brief's pairs
need, and replayed the brief's JVM observations. It wrote no claims, examples, sidecars, adapters or recipes,
allocated no example ids, ran no project verifier and changed nothing in `lib/` or the checker. Everything it
downloaded or built is outside the checkout, under `~/.cache/in-the-loop/`.

`$B` below is `~/.cache/in-the-loop/jbmc-java-semantics-gap`. The status of each brief section is in the
[summary](#summary). Two builds and the stock-JBMC rerun are [verification jobs](#jobs).

## Layout

| Path | What it holds |
|---|---|
| `~/.cache/in-the-loop/git-mirrors/{commons-lang,commons-io,commons-text,commons-collections,gson,guava,spring-framework,cbmc,jdk21u}.git` | One bare repository per upstream, shared. Only the pinned commits were fetched (`git fetch --depth=2 origin SHA`, depth 3 for Gson's merge commits, depth 1 for Spring). `cbmc` and `jdk21u` are partial clones (`--filter=blob:none`, `remote.origin.promisor=true`): blobs are fetched on demand for the sparse paths checked out. |
| `$B/src/NAME` | One detached worktree per pinned revision (names [below](#pinned-revisions)). `cbmc-*` and `jdk21u-*` are sparse: only the regression folders and JDK files the brief names. To add a path: `git -C $B/src/cbmc-6.11.0 sparse-checkout add /jbmc/regression/OTHER/`. To add a revision: `$B/scripts/mirror.sh OWNER/REPO MIRROR WORKTREE SHA`. |
| `$B/releases/NAME` | Released artifacts from Maven Central: `lib/` (jars), `sources/` (their sources jars), `classpath.txt` (ordered, absolute paths into `$B/m2`, ready for `java -cp $(cat classpath.txt)`), `tree.txt`. Resolved by the throwaway POMs in `$B/resolve/NAME/` with `mvn --strict-checksums`. |
| `$B/releases/cbmc-6.11.0/ubuntu-22.04/{bin/jbmc,lib/core-models.jar,lib/cprover-api.jar}` | The JBMC binary and models from the Ubuntu 22.04 release package: the brief's preflight binary ([below](#jbmc-6110-two-packages)). |
| `$B/artifacts` | Jars built from pinned revisions, named after the worktree. |
| `$B/jdk/temurin-24.0.2` | The JDK 24 toolchain Guava's build asks for. |
| `$B/jdk/temurin-21.0.13/classes`, `classes.sha256` | The `java.base` classes the brief names, extracted from the Temurin 21.0.13 image with `jimage`, and their digests. |
| `$B/regressions/NAME` | Copies of the named upstream JBMC regression folders (from `cbmc-6.11.0`), with the `pom.xml` fixtures compiled into `target/classes` (`javac --release 8 -g`, JDK 21.0.13), ready for `jbmc` as each `test.desc` says. |
| `$B/probes` | The throwaway JVM programs that replayed the brief's observations (not claims, not adapters). `probes/seed/` holds `Semantics.java` and `ExtraOpeners.java` cut verbatim from the brief, and their compiled classes in `probes/seed/cls/`. |
| `$B/m2`, `$B/maven-settings.xml` | The Maven local repository (seeded by hard links from the Spring setup's, so files are shared) and settings that point at it with an absolute path (`mvn -s $B/maven-settings.xml`). |
| `$B/mvn-home`, `$B/toolchains.xml` | Maven's `user.home` and `MAVEN_USER_HOME` for the Guava build (wrapper distribution, toolchains), so nothing is written to `~/.m2`. |
| `$B/keys`, `$B/gnupg` | Public keys and a keyring of this setup's own (`GNUPGHOME=$B/gnupg`), apart from the user's. Its agent was stopped. |
| `$B/scripts` | `mirror.sh`, `guava_job.sh` and `jbmc_repro.py` (the two jobs' scripts). |
| `$B/logs` | The log of every build, test and resolution named below. |

JDKs (SDKMAN, already installed): `~/.sdkman/candidates/java/8.0.512.0+9-tem` (Gson), `21.0.13.0+9-tem` (everything
else), `17.0.21.0+9-tem`, `25.0.5.0+8-tem`. Maven 3.10.0 (`~/.sdkman/candidates/maven/current`); Guava uses its own
wrapper's Maven 3.9.9.

## Tools

### JBMC 6.11.0: two packages

The CBMC 6.11.0 GitHub release has one Debian package per Ubuntu version, and their JBMC binaries and
`core-models.jar` differ. The installed one (`/usr/bin/jbmc`, package `cbmc 6.11.0`) is the 24.04 package. The
brief's preflight digests are the **22.04** package's:

| Package (sha256 from the release's asset digest, checked) | `jbmc` sha256 | `core-models.jar` sha256 | Models built with |
|---|---|---|---|
| `ubuntu-22.04-cbmc-6.11.0-Linux.deb` `de9fa1cc4cf51c493e708a1c7608b192ad4956717b684d9c4501e22fd22d88a0` | `2cf572542163ad3926d0030f4594e4697fcd09a0c60b62dc58901ca3aa18065c` (= brief) | `2a05026b3ab948ebb4820ccc2fc01040b96e226dc1f58a3be36dfe0c15ed14de` (= brief) | JDK 11.0.32 |
| `ubuntu-24.04-cbmc-6.11.0-Linux.deb` `b3721aa541038384d7801ea3aeabbcddc3e8845ac8f1cbff637cf8dec7481ac8` (installed, files identical to `/usr/bin/jbmc` and `/usr/lib/core-models.jar`) | `200f4cbb273d94268cdf933ee1f7c5ea96c8abc95af83836c2ffc082a722ec35` (= `lib/benchmark/external-upgrades/v0.json`) | `a31ef93bfe898d373bb7eca6aef3b9ee2ebf05b0fe8efb305f86528396ea49df` | JDK 17.0.20 |

Both report `6.11.0 (cbmc-6.11.0)`. The 22.04 binary runs on this machine (no missing libraries). The two model jars
hold the same 91 classes, all compiled differently. **The models change an answer:** a capped probe of
`ExtraOpeners.firstDeclared` with the brief's flags gave exit 10 (the brief's FAILURE) with the 22.04 models, under
either binary, and exit 0 (assertion SUCCESS) with the installed 24.04 models. The [JBMC job](#jobs) reruns every
seed entry and regression in three pairings to show which results depend on which file. `lib/benchmark/run.py`'s
`--jbmc` defaults to `jbmc` on `PATH`, which is the installed 24.04 binary.

### JDKs

- **JDK 21.0.13.** The brief's preflight used Debian OpenJDK 21.0.13. This machine has Temurin 21.0.13+9
  (`SOURCE_REPO=adoptium/jdk21u`, `lib/modules` sha256 `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c`).
  Its `src.zip` copies of `ArrayDeque`, `AbstractCollection`, `Deque`, `Queue`, `Collection`, `Iterator`, `Objects`,
  `ImmutableCollections`, `List` and `ThreadLocal` are byte-identical to `openjdk/jdk21u` at `ba94eace` (the 21.0.13
  GA commit the brief links). Class bytes may still differ from Debian's build; the Debian package is not available
  here (the Ubuntu archive offers 21.0.12.1).
- **JDK 24** (Guava's toolchain): Temurin 24.0.2+12 from `adoptium/temurin24-binaries`,
  `OpenJDK24U-jdk_x64_linux_hotspot_24.0.2_12.tar.gz` sha256 `aea1cc55e51cf651c85f2f00ad021603fe269c4bb6493fa97a321ad770c9b096`
  (matches the published `.sha256.txt`), good signature by the Adoptium GPG key `3B04D753C9050D9A5D343F39843C48A565F8F04B`
  (from keyserver.ubuntu.com; keys.openpgp.org serves it without a user ID). Unpacked in `$B/jdk/temurin-24.0.2`; the
  tarball was deleted.
- **Maven 3.9.9** (Guava's wrapper): the wrapper checked the zip against the pinned
  `distributionSha256Sum=4ec3f26f…3a3c`; its sha512 also matches Central's `.sha512`.

### The JDK classes the brief names

`$B/jdk/temurin-21.0.13/classes.sha256` lists 40 classes: the eight of #9 (with the nested `ArrayDeque` classes),
`List`, `ImmutableCollections` and its nested classes, `AbstractList`, `ThreadLocal` and nested, `Enum`, `Integer`,
`Character`, `String`. The eight for #9 (sha256):

| Class | sha256 |
|---|---|
| `java/util/ArrayDeque` | `5a60b800c442734624acb4d657fa9ea6719bfceb2d27a53286d80ef467f9bad6` |
| `java/util/ArrayDeque$DeqIterator` | `d4149e4d7eed037b0637ccd650ce0e8d0f189f3ac026ba577687e0b28733cbd3` |
| `java/util/AbstractCollection` | `b93c4cb722381e978a48c97aad6e2e3ef2e4e75e527313d23c30faf769aa3235` |
| `java/util/Deque` | `fb776dc45a5a822ca78b7a4e0e8558c0649377e03d807336e48c28dfd43e2afb` |
| `java/util/Queue` | `6e8e39a174d0aab0dbe666da53ba2b07e7e18498428b407f10893f0e7c84e24d` |
| `java/util/Collection` | `d611f6da30630117675181c93c9870cd8fdf1258fa8549be17fe6f46a6badd16` |
| `java/util/Iterator` | `ebbaacb0efcf778bc45ebef522a49b82285f14cf20bbb8d43c8da44f87f8445a` |
| `java/util/Objects` | `8fccf445af40ac88bbe8fff5fda8d95f5206eb99d6ec4678d8a7ce69f860ba34` |

## Pinned revisions

Every commit was fetched by its full id, so git's object ids check its content. Each release commit was compared
with its tag through the GitHub API (`repos/R/commits/TAG`): all match. "Signed" means `git log --format=%G?` gave
`U` (good signature, no trust path) in this setup's keyring, with GitHub's web-flow key
(`https://github.com/web-flow.gpg`, sha256 `6e8af687…a3ef84`); the others carry no commit signature (the Apache
release tags themselves were not fetched).

| Brief | Worktree | Commit | Tree | Date, author | Signature |
|---|---|---|---|---|---|
| §2, §3 (B1 of the Spring setup) | `commons-lang-5904c573` | `5904c573ffacaa5d8836ffc2b346f400c8901ed1` | `a2ba93de7141b6a03d336c97c0e5ca588aa7fb46` | 2026-05-05, Gary Gregory | signed (web-flow) |
| #12 | `commons-lang-3e50a7f9` | `3e50a7f9cf103357d781483d41ec9c9386e69e9d` | `e647aeb55c36c8a91d745e7f2e94a1161ef66186` | 2026-06-20, alhuda (#1718) | signed (web-flow) |
| #8 dependency, #10 | `commons-lang-3.14.0` (tag `rel/commons-lang-3.14.0`) | `c8774fa74adbbbcd4e5f915ab6bc3aa10d877419` | `fc5d78865a6d16df7849913cfae1827e6985f250` | 2023-11-18, Gary Gregory | none |
| #7 | `commons-io-2.19.0` (tag `rel/commons-io-2.19.0`) | `2186f41bbae123ed355a77137e9be10c0b4c4630` | `2586337b7322bddb85801785dc2f329f886968a1` | 2025-04-08, Gary D. Gregory | none |
| #8 | `commons-text-1.12.0` (tag `rel/commons-text-1.12.0`) | `2c2d0818b0540c59f055f5174db51d0574af46da` | `2a9078e40e6864989532f660a448ec1e52901b13` | 2024-04-13, Gary Gregory | none |
| §5, #9 | `commons-collections-4.5.0` (tag `rel/commons-collections-4.5.0`) | `7f7fb0244abc940a2e9dd28b67508c0483a58c3e` | `587ea353928a4e3885ba85117021db0b4410aeda` | 2025-04-19, Gary D. Gregory | none |
| §4 Gson #719 parent | `gson-719-parent` | `10714ef0427536b679e9677f8417807e4cce017d` | `4296e6fd30e0d9b4421959240ce4e8c40c591fba` | 2015-10-21, inder123 (merge of #715) | none |
| §4 Gson #719 fix | `gson-719-fix` | `80c98ef0261826430a601cddfa5f3003627146c5` | `bc803952f0ef5eb6571381b6b5e1fb2beed2d6fe` | 2015-10-21, Jesse Wilson (merge of `7d1973e6` "Fix type hierarchy adapters to do a runtime check" into the parent) | none |
| §5 Guava #7955 parent | `guava-7955-parent` | `47b7e9e5ef3f2267f8ac327d68cc56b99e186aa8` | `78b250a366208d36ff2bbdfd438ff628a2ca33a6` | 2025-08-26, cpovirk | none |
| §5 Guava #7955 fix | `guava-7955-fix` | `148cea0778b7ea2e362c794c02b29a62bd93daa2` | `d6f57f0a3ecf8c0472ae00e8edf7b7d8fefbd630` | 2025-08-27, Éamonn McManus | none |
| #14 | `spring-framework-6.2.0` (tag `v6.2.0`) | `5024bb72279188f1d0dcfe19e8abdd4bdb9887c8` | `ce76e4e6d26074db44236164d3cf030ce00e08a1` | | none |
| upstream regressions, #6 | `cbmc-6.11.0` (tag `cbmc-6.11.0`, sparse) | `820ff0f555b43fb78e0cd9332e498461bd14244b` | `f0ad812df55d12ae6da4896a28b6476043308f7f` | 2026-08-21, Michael Tautschnig | signed (web-flow) |
| upstream regressions | `cbmc-d2972052` (sparse) | `d29720523b363987a3c5ccf6d4255a813fb8fe47` | `8f73feea92e99d3192a061422f94ffc2a426c5d2` | 2026-11-20, Michael Tautschnig | signed (web-flow) |
| #9 | `jdk21u-21.0.13` (sparse) | `ba94eace682733f66e623c089bcafcf4a1b8e39c` | `1b001608f68b6e8e9618636e37f3998a540e724d` | 2026-10-19, Christoph Langer (21.0.13 GA) | none |

The brief's baseline `d717edd2` is an ancestor of this checkout's head.

The seven regression folders the brief links (`jbmc-strings/StartsWith`, `jbmc-strings/toCodePoint`,
`jbmc-concurrency/synchronized-methods`, `jbmc/virtual5`, `jbmc/default-methods`,
`jbmc/no-main-object-array-elements-maybe-null{1,2}`) are **identical** at `cbmc-6.11.0` and at `d2972052`
(`diff -r`), so one copy (`$B/regressions/`) serves both links. `jbmc/lib/java-models-library` is not in the CBMC
tree at 6.11.0 (the build fetches it), so the packaged `core-models.jar` stands in for the `test.desc` classpath.

## Released artifacts

All from Maven Central with `--strict-checksums` (SHA-1 against Central's). Each main jar's and sources jar's `.asc`
(in `$B/keys/asc/`) is a good signature, checked in this setup's keyring:

| Graph (`$B/releases/…`) | For | Jars (sha256) | Signed by |
|---|---|---|---|
| `commons-lang3-3.14.0` | #10, #8's dependency | commons-lang3 `7b96bf3ee68949abb5bc465559ac270e0551596fa34523fddf890ec418dde13c` | Gary David Gregory, `2DB4F1EF0FA761ECC4EA935C86FDC7E2A11262CB` (Apache Commons KEYS, sha256 `f154a693…3299a`) |
| `commons-io-2.19.0` | #7 | commons-io `824268919b4b62f9f40f08c54381de5993b078f58667e332d17348ae019d72b9` | the same |
| `commons-text-1.12.0` | #8 | commons-text `de023257ff166044a56bd1aa9124e843cd05dac5806cc705a9311f3556d5a15f`, commons-lang3 3.14.0 (the version its POM declares) | the same |
| `commons-collections4-4.5.0` | §5 iterator, #9 transfer | commons-collections4 `00f93263c267be201b8ae521b44a7137271b16688435340bf629db1bac0a5845` (no runtime dependencies) | the same |
| `spring-core-6.2.0` | #14 | spring-core `3b82629da38717dd616a70ec1055f9a8e208d58132071a6314a32159f8bce162`, spring-jcl `2b59288f030ce77a89ec88aa426f32eb9a309056f3646dd5157f9f31f0204fd7` | Spring Builds (JAR Signing), `48B086A7D843CFA258E83286928FBF39003C0425` (keys.openpgp.org) |
| `guava-33.4.8-jre` | §5, the release whose `Strings.java` equals the **parent's** | guava `f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed`, failureaccess 1.0.3, jspecify 1.0.0, error_prone_annotations 2.36.0, j2objc-annotations 3.0.0, listenablefuture 9999.0 | Christopher Povirk, `BDB5FA4FE719D787FB3D3197F6D4A1D411E9D1AE` (keys.openpgp.org) |
| `guava-33.5.0-jre` | §5, the release whose `Strings.java` equals the **fix's** | guava `1e301f0c52ac248b0b14fdc3d12283c77252d4d6f48521d572e7d8c4c2cc4ac7`, failureaccess 1.0.3, jspecify 1.0.0, error_prone_annotations 2.41.0, j2objc-annotations 3.1 | the same |

Full digests: `cd $B/releases/NAME/lib && sha256sum *.jar`.

**Released sources match the pinned tags.** Each named file in the release's sources jar is byte-identical to the
tag worktree's: `StrBuilder.java` (3.14.0), `EndianUtils.java` (IO 2.19.0), `CodePointTranslator.java` and
`UnicodeUnpairedSurrogateRemover.java` (Text 1.12.0), `ObjectArrayListIterator.java`, `FilterIterator.java`,
`SingletonIterator.java` (Collections 4.5.0), `NamedThreadLocal.java` (Spring 6.2.0). Guava's `Strings.java` at the
parent `47b7e9e5` equals 33.4.8-jre's and at the fix `148cea07` equals 33.5.0-jre's. Other Guava classes differ
between each release and the commits (`Platform.java` at the parent equals neither release's).

## Built artifacts

| Jar (`$B/artifacts/`) | sha256 | Built | Class digest (first 16 hex digits of sha256) |
|---|---|---|---|
| `commons-lang-5904c573.jar` (3.21.0-SNAPSHOT) | `4f6b509b49e10b69de68d29cd4c7c0f378a6ee5f9e97f22778e24290de675d1c` | copied from the Spring setup's `commons-lang-1635-landed.jar` (the same commit; Maven, JDK 21.0.13) | `math/Fraction.class` `d63d06f22949499e` |
| `commons-lang-3e50a7f9.jar` (3.21.0-SNAPSHOT) | `5489541c16fe228f13443d8c7bb951722da80b25c56b73412707cab4011b032c` | here, Maven, JDK 21.0.13, commons-parent 102 | `Conversion.class` `7080056a627f12f1` |
| `gson-719-parent.jar` (2.5-SNAPSHOT) | `aa5c6883a29f7138e0452f8a9cd5c19efd9adba228f0d67024cd305cdfb3eb89` | here, Maven, JDK 8u512, source/target 1.5 | `internal/bind/TypeAdapters.class` `996c8d93736c6166` |
| `gson-719-fix.jar` (2.5-SNAPSHOT) | `f0c093dc10b6830cc7eef6d94bf8a40c2bfa46322d714b716807d9ed6a481477` | the same | `internal/bind/TypeAdapters.class` `ff3098521e48f63c` |
| `guava-7955-{parent,fix}.jar` | pending | [Guava job](#jobs) | |

Jar digests include build timestamps. The two Gson jars differ only in `TypeAdapters` and its nested classes (the fix
adds `TypeAdapters$31$1`). Gson has no runtime dependencies. The Commons Lang `3e50a7f9` worktree keeps its
`target/` (about 30 MB) so a caller can compile against `target/classes` at once.

## Build and test commands

### Commons Lang (`3e50a7f9`; `5904c573` is the same build)

```bash
B=~/.cache/in-the-loop/jbmc-java-semantics-gap
export JAVA_HOME=~/.sdkman/candidates/java/21.0.13.0+9-tem TMPDIR=$B/tmp
cd $B/src/commons-lang-3e50a7f9
mvn -o -B -s $B/maven-settings.xml -ntp -DskipTests -Dmaven.javadoc.skip=true -Dmaven.source.skip=true package   # ~22 s
mvn -o -B -s $B/maven-settings.xml -ntp test -Dtest=ConversionTest                                                 # 51/51 pass
```

The offline form works for `package` and `test` (checked). The `5904c573` worktree here is unbuilt; the Spring setup's
`~/.cache/in-the-loop/spring-java-data/src/commons-lang-1635-landed` is the same commit with `target/` in place.

### Gson #719 (JDK 8)

```bash
export JAVA_HOME=~/.sdkman/candidates/java/8.0.512.0+9-tem TMPDIR=$B/tmp
cd $B/src/gson-719-fix        # or gson-719-parent
mvn -o -B -s $B/maven-settings.xml -ntp -DfailIfNoTests=false \
  test-compile org.apache.maven.plugins:maven-surefire-plugin:2.18.1:test -Dtest=DefaultTypeAdaptersTest
mvn -o -B -s $B/maven-settings.xml -ntp -DskipTests -Dmaven.javadoc.skip=true -Dmaven.source.skip=true package
```

The Gson POM leaves Surefire's version open, and Maven 3.10.0's default Surefire (3.6.0) refuses the build's JUnit
3.8.2 ("not supported anymore"). The command above names Surefire 2.18.1 (2015) on the command line instead; the
build files are unchanged. `-DfailIfNoTests=false` is for the root aggregator, which has no tests. Offline works for
both commands on both sides (checked).

- Fix: `DefaultTypeAdaptersTest` 65/65 pass. Parent: its own 64/64 pass.
- **The regression, transplanted:** the fix's `DefaultTypeAdaptersTest.java` on the parent's code (a throwaway copy,
  deleted after): 65 run, 1 error, `testJsonElementTypeMismatch` with
  `java.lang.ClassCastException: Cannot cast com.google.gson.JsonPrimitive to com.google.gson.JsonObject`.
  Log: `logs/gson-719-parent.fix-test-on-parent.log`.

### Guava #7955 (as a job)

Guava builds with its Maven wrapper and a JDK 24 toolchain (`maven-toolchains-plugin`, and `toolchains-maven-plugin`
4.5.0, which would otherwise **download a JDK into `~/.m2/jdks` and write `~/.m2/toolchains.xml`**). Surefire's
toolchain is the running JDK's version. `$B/toolchains.xml` declares Temurin 24.0.2 and 21.0.13, and Maven's home is
moved into the cache folder:

```bash
export JAVA_HOME=$(readlink -f ~/.sdkman/candidates/java/21.0.13.0+9-tem) TMPDIR=$B/tmp \
       MAVEN_USER_HOME=$B/mvn-home/.m2 MAVEN_OPTS="-Duser.home=$B/mvn-home"
cd $B/src/guava-7955-fix      # or guava-7955-parent
./mvnw -B -ntp -s $B/maven-settings.xml -t $B/toolchains.xml -pl guava,guava-testlib,guava-tests -am \
  test -Dtest=com.google.common.base.StringsTest -Dsurefire.failIfNoSpecifiedTests=false
./mvnw -B -ntp -s $B/maven-settings.xml -t $B/toolchains.xml -o -pl guava -DskipTests package
```

A `validate` of the `guava` module (inline, 10 s) confirmed both toolchains resolve to those JDKs and nothing was
written to `~/.m2`. The test build compiles `guava-tests`, which takes minutes, so it runs as a job. The job
(`scripts/guava_job.sh`) runs the commands above on both sides, then the fix's `StringsTest.java` on the parent
(which adds `lenientFormat("%s + %s = %s", (Object[]) new Integer[] {5, 6, 11})`), the fix's test offline, and
removes the build trees.

### Released Commons, Spring and Guava artifacts

Nothing to build: use `java -cp $(cat $B/releases/NAME/classpath.txt)`. To redo a resolution:
`cd $B/resolve/NAME && mvn -B -s ../../maven-settings.xml --strict-checksums dependency:copy-dependencies -DoutputDirectory=../../releases/NAME/lib`
(add `-o` once cached).

## What was replayed on a JVM

All on Temurin 21.0.13, inline, each under a few seconds, with the throwaway programs in `$B/probes/` (sha256 in
[Scripts and probes](#scripts-and-probes)). Run any of them as `java -ea -cp CLASSPATH File.java` from its folder.

**The runnable seeds, verbatim from the brief** (`probes/seed/`). Compiled with `javac -source 8 -target 8 -g`
(JDK 21.0.13) into `probes/seed/cls/`, and the JBMC job reads those classes.

- `java -ea -cp cls:$B/artifacts/commons-lang-5904c573.jar Semantics` exits 0. Its 16.8-million-input `fraction`
  loop takes about 0.06 s with the JIT; under `-Xint` it took 3.8 s, so the loop does run.
- `java -ea -cp cls:$IO_JAR ExtraOpenersReplay` prints "All three witness replays passed".
- `Neg.java` counts the §2 numbers: the expected formula holds on all 16,777,216 inputs, floor-only fails on
  **4,194,304**, and `n=33_554_431` gives `16777216.0`. At `x=2^31` (raw bits `41e0000000000000`), `(int)x` is
  `2147483647` and `(int)(long)x` is `-2147483648`. `MutableDouble` gives `MAX_VALUE`, then `MIN_VALUE` after
  `setValue(-x)`.

| Brief | Probe, classpath | Observed | As the brief says |
|---|---|---|---|
| §4 Gson #719 | `gson/GsonGrid.java`, each built jar | Parent: four incompatible pairs (string as `JsonObject`, string as `JsonArray`, object as `JsonArray`, array as `JsonObject`) throw `ClassCastException`. Fix: the same four throw `JsonSyntaxException`. Five compatible pairs return `JsonPrimitive`, `JsonObject`, `JsonArray`, `JsonObject`, `JsonArray` on both. 18 observations. | yes |
| §4 `virtual5` | the fixture's class, a driver | `test(null)` and `test(new parent())` return; `test(new child())` throws `AssertionError` | yes |
| §5 kernel | `store/Covariant.java` | Through an `Object[]` view of a `String[]`: a `String` or `null` is stored; an `Integer` throws `ArrayStoreException`, and the old reference stays. Index 1 or −1 throws `ArrayIndexOutOfBoundsException`, and a null array throws `NullPointerException`. | yes |
| §5 iterator | `collections/IteratorGrid.java`, Collections 4.5.0 | 6 `IllegalStateException` (before `next()`), 5 writes, 1 `ArrayStoreException` (`Integer[]` with a `Double`); all 7 failures keep the original cell. `javap`: `set` stores with `aastore` at offset 27. | yes |
| §5 Guava #7955 | `guava/Lenient.java`. Two routes: (1) each side's unmodified `Strings.java`, compiled (`javac --release 8`) against the 33.4.8-jre classpath and put ahead of it (`probes/guava/slice-{parent,fix}/`); (2) the released 33.4.8-jre and 33.5.0-jre | Parent (both routes): `Integer[]{5,6,11}` throws `ArrayStoreException` with the original references kept; `Object[]{5,6,11}` gives `"5 + 6 = 11"` and its elements become `String`s. Fix (both routes): `"5 + 6 = 11"` for both arrays, references kept. | yes |
| #6 default methods | the `ExtraOpeners` seed; upstream `default-methods` fixture | The seed's replay passes. The fixture's `Test.testme` passes its seven assertions on the JVM and fails at line 18 (`assert false`), as its `test.desc` expects. | yes |
| #7 byte reversal | the `ExtraOpeners` seed, IO 2.19.0 | `endian(1)` holds; `halfSwap(1)` is rejected | yes (the 65,536-input grid was not run) |
| #8 surrogates | `text/Surrogate.java`, Text 1.12.0 + Lang 3.14.0, a custom two-unit `CharSequence` and a recording writer | Lone high or low surrogate at offset 0: 1. A valid pair: 0 at offset 0, 1 at offset 1. `DBFF DFFF`: 0 and 1. On all 1,048,576 valid pairs, offset 0 gives 0 and offset 1 gives 1, and forward and backward decoding equal the scalar formula. The writer received 0 units in every call. | yes (the 589,824-pair boundary grid was not run: the brief does not define it) |
| #9 deque | `deque/DequeHistories.java`, JDK 21.0.13 + Collections 4.5.0 | Removal before `next()` throws ISE. History 1: second removal throws ISE, `[b]`, `next()` returns `b` itself, then `NoSuchElementException`. History 2: `pollLast()` returns `b`, and the iterator's next read throws `ConcurrentModificationException`. `FilterIterator` over `SingletonIterator`: two `hasNext()` calls, removal while pending throws ISE, removal after `next()` succeeds, and on a non-removable singleton throws `UnsupportedOperationException`. Over the deque iterator: consume `a` and remove gives `[b]`; prefetching `b` makes removal throw ISE with `[a, b]`; consuming and removing `b` then gives `[a]`. | yes |
| #10 `StrBuilder` | `strbuilder/StrBuilderInit.java`, Lang 3.14.0 | `null`: no callback in the constructor. Empty, `A`, `D800`, `DC00`, `D83D DE00`: one callback, which sees `phase` 0. After `append("B")`: `phase` 7, the same receiver, and contents and lengths as expected. | yes |
| #11 hex | the `ExtraOpeners` seed | `hex(n)` holds for all 16 ≤ n ≤ 255; `lowFirst(190)` is rejected | yes |
| #12 nibble | `nibble/Nibble.java`, the `3e50a7f9` jar | 16 patterns × offsets {MIN, −1, 0, 1, 2, 3, 4, 5, MAX}: 144 of 144 agree with "hex digit of `m >>> off` for 0 ≤ off ≤ 3, else exactly `IndexOutOfBoundsException`". `1010` at 1 gives `'5'`. | yes |
| #13 enum | `enumlookup/EnumLookup.java` | `new String("OPEN")` and `new String("CLOSED")` give the same constants; `null` throws NPE; `"open"` and `"OTHER"` throw IAE; ordinals 0 and 1 | yes |
| #14 thread locals | `threadlocal/Locals.java`, Spring 6.2.0 | On both a `ThreadLocal` subclass and `NamedThreadLocal.withInitial`: a repeated `get()` returns the same reference (1 initializer call); after `set(null)`, `get()` is null with no new call; after `remove()`, a fresh object (2 calls); installing key 1's object in key 0 works; removing key 1 twice, then `get()`, initializes it afresh | yes |
| #15 monitors | `monitor/StaticSync.java` (one run, not a schedule enumeration); the upstream fixture's `A.me4` | 5 under the class lock, 6 after release and join; `me4` returns normally on the JVM | yes |

## Repository inputs at this head (`31643a20`)

For reference only: the domain agent freezes the opening score. `lib/models/classes/java/util/` holds the six list
model classes §1 names (sha256: `List` `12d8a136…`, `ImmutableCollections` `cd522de1…`, `$List12` `78720b4b…`,
`$ListN` `54145aee…`, `$ListItr` `18b0cbcc…`, `$AbstractImmutableList` `136c6d07…`), and `lib/models/java/lang/Enum.java`
and `lib/models/java/util/lists/ArrayDeque.java` exist. `lib/benchmark/conformance.json` has the `listOfArray`,
`listSearch` and `enumValueOf` cases. Examples end at **375**, as the brief says. Example 375 builds its Commons Lang
revisions through its own target route (`records/setup/build-{parent,landed}.json`). Examples 373, 374, 342, 343 and
314 are in place.

## Jobs

| Job | What | Status |
|---|---|---|
| `20261123-075049-setup-build-guava-at-the-7955-parent-and` | Guava #7955: both sides' `StringsTest`, both jars, the fix's test on the parent, offline rerun, cleanup (4 CPU, 5 GB, ~30 min est.) | pending |
| `20261123-075049-setup-rerun-the-brief-s-stock-jbmc-6-11` | Stock JBMC: the 14 seed entries and the 7 regression folders' 13 `test.desc` files, in three pairings (22.04 binary + 22.04 models = the preflight; installed binary + installed models; installed binary + 22.04 models). Per-entry exit, time, peak memory and property results go to `$B/jbmc-runs/PAIRING/` (`summary.txt` there). (1 CPU, 4 GB, ~60 min est.) | pending |

## Scripts and probes

sha256: `scripts/guava_job.sh` `ca02907a53a4fbc5571922e76dad4ba13b2e5d0a605b47f253a00623d9023bef`,
`scripts/jbmc_repro.py` `3f424d4b4275d3f740e8201f4747b5cd6bd7cad80ef4fe93d2f395522e6e508d`, `scripts/mirror.sh`
`04ae4cf4…f74760`; `probes/seed/Semantics.java` `29c9f00b9d25e744e1baba932dd01e6235bba532ae1216b9d154cd48dfeeee19` and
`ExtraOpeners.java` `ce08e8bc2909229a2d01197b01bdf2c8994816faa51d485b28a7e8c401be9416` (lines 186–243 and 265–320 of
the brief); the rest with `sha256sum $B/probes/*/*.java`.

## Disk

Mirrors 98 MB (Spring's 53 MB and Commons Lang's were already there). Worktrees 249 MB (Spring 90 MB, the Guava pair
84 MB). Releases 35 MB, artifacts 2 MB. JDK 24 and the extracted classes 298 MB. `m2` 391 MB, of which 334 MB are
hard links shared with the Spring setup. `mvn-home` 20 MB. About 1 GB in all, before the Guava job adds its
dependencies.

## Summary

| Brief | Sources | Artifacts | Original regression or reproduction on a JVM |
|---|---|---|---|
| §1 lists | in the repository | six model classes at this head | n/a (the domain agent runs the registered cases) |
| §2 numeric callers | Lang `5904c573` | built jar | yes: seed oracle; floor-only 4,194,304 failures; narrowing witness at `0x41e0…` |
| §3 prefix | Lang `5904c573`, `StartsWith` fixture | | yes: seed oracle over offsets −1..6 |
| §4 reference arrays, Gson #719 | null-cell fixtures, `virtual5`, Gson pair | Gson jars built (JDK 8) | yes: own tests pass on both sides; the fix's test fails on the parent (`ClassCastException`); 18 observations; `virtual5` |
| §5 covariant stores | Collections 4.5.0, Guava pair | Collections and Guava 33.4.8/33.5.0 released and signed; Guava build **pending (job)** | yes: kernel; 12-case grid; Guava parent/fix by slice and by release |
| #6–#15 | as listed | as listed | yes, each as the table above says |
| Comparator | CBMC 6.11.0 regressions | both JBMC packages; the brief's preflight binary and models found | rerun **pending (job)**; one probe showed the models jar decides `firstDeclared` |

**Refused:** nothing. **Not done, on purpose:** no examples, claims, sidecars, adapters or recipes; no verifier runs;
no opening score; no grids beyond the brief's named observations (#7's 65,536 inputs, #8's boundary grid, #15's
schedules); no investigation of why the models jar changes `firstDeclared`.

## Setup Agent Notes

### What is ready, and where

- Everything is under `~/.cache/in-the-loop/jbmc-java-semantics-gap` (`$B`); the [layout](#layout) table says what
  each folder holds. Worktrees for every pinned revision are in `$B/src/`. Released jars with ordered classpaths are
  in `$B/releases/NAME/classpath.txt`, and built jars are in `$B/artifacts/`.
- Commons Lang `5904c573` (§2, §3: `commons-lang-5904c573.jar`) and `3e50a7f9` (#12, `target/` kept). Released Lang
  3.14.0, IO 2.19.0, Text 1.12.0, Collections 4.5.0, Spring Core 6.2.0, and Guava 33.4.8-jre and 33.5.0-jre, all
  signature-checked.
- Gson #719 parent and fix jars (JDK 8). The Guava #7955 build is a pending job; until it lands, 33.4.8-jre and
  33.5.0-jre carry exactly the parent's and the fix's `Strings.java`, and `probes/guava/slice-{parent,fix}/` holds
  each side's own `Strings.class` built against 33.4.8.
- JBMC 6.11.0 in two forms. `/usr/bin/jbmc` with `/usr/lib/core-models.jar` is the 24.04 package, what the runner
  uses by default. `$B/releases/cbmc-6.11.0/ubuntu-22.04/{bin/jbmc,lib/core-models.jar}` is the brief's preflight
  pair, with matching digests.
- The upstream JBMC fixtures, compiled, in `$B/regressions/`. The brief's two seeds, compiled, in
  `$B/probes/seed/cls/`. The JDK 21.0.13 classes the brief names, with digests, in `$B/jdk/temurin-21.0.13/`.

### What was verified on a JVM

Every observation the brief reports that a JVM can make, on Temurin 21.0.13, matched; the [table](#what-was-replayed-on-a-jvm)
lists them. This covers both seeds' oracles, the §2 counts and witnesses, Gson's 18 observations and its regression
(the fix's test fails on the parent with `ClassCastException`), the §5 kernel, iterator grid and Guava parent/fix,
and #6–#15. Only Gson's upstream test was run as a parent/fix pair here; Guava's is the pending job.

### What to know before starting

- **Two JBMC packages, and the models matter.** The installed JBMC and models are not the brief's preflight pair. With
  the installed `core-models.jar`, `ExtraOpeners.firstDeclared` reports SUCCESS where the brief (and the 22.04 models,
  under either binary) reports FAILURE. Name the binary and models jar in every comparator row. The JBMC job's
  `$B/jbmc-runs/*/summary.txt` will say which other results move.
- **JDK:** Temurin 21.0.13, not Debian's build. The named `java.base` sources are identical to jdk21u at `ba94eace`;
  class bytes may differ from the brief's preflight, so the #9 hashes recorded here are Temurin's.
- **Gson** needs JDK 8 and Surefire 2.18.1 on the command line (the default Surefire refuses JUnit 3.8.2).
  **Guava** needs the JDK 24 toolchain and the `user.home` redirect given [above](#guava-7955-as-a-job), or its
  plugin downloads a JDK into `~/.m2`.
- **Commons Lang `3e50a7f9` and `5904c573` are 3.21.0-SNAPSHOT builds** whose jar digests include timestamps:
  compare class digests, not jar digests.
- The CBMC `test.desc` classpaths name `jbmc/lib/java-models-library/target/…`, which the 6.11.0 tree does not
  contain; the job substitutes the packaged `core-models.jar` and `cprover-api.jar` of each pairing.
- No snapshot dependencies were resolved from a remote; every input here is pinned by commit or by release checksum.

### What is left for the domain work on purpose

All claims and scopes, example ids and scaffolding, adapters and sidecars. Also: the opening score (recounting the
historical 13, freezing model hashes for the score), every native and integrated JBMC run, and the choice of §1's
and §3's transfer callers. The grids the brief only sketches (#7's patterned inputs, #8's boundary grid, #15's
schedules) and the #6 classfile-variant comparator regression are not built. Why the models jar flips
`firstDeclared` is not investigated.
