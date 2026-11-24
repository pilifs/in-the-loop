# Setup for the change verification strategy brief

Mechanical setup for [`in-the-loop-change-verification-strategy.md`](in-the-loop-change-verification-strategy.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. The brief pins two concrete
cases for its first step, example 345 and Retrofit/Wire (CompSuite `compsuite-i-1`). It feeds in three queued
briefs that have setups of their own, and it leaves the held-back Spring Boot 2.7.x → 3.0.x application for the
domain work to pick. This session mirrored and checked every upstream revision those two cases name. It
signature-checked their released jars and rebuilt Retrofit's wire module on both sides. It reproduced on a JVM every
Wire and 345 observation the brief states, and recounted the organic scorecard the brief cites. It also prefetched
and checked the last Spring Boot 2.7 and 3.0 starter graphs on JDK 17.

It wrote no claims, examples, sidecars, adapters or recipes, allocated no example ids, ran the project verifier on
no claim, and changed nothing in `lib/` or the checker. Everything it fetched or built is outside the checkout,
under `~/.cache/in-the-loop/`. **No verification job was needed**: the longest run was example 345's validation
(4 min 18 s, the tests `validate_example.py` runs with it), and every build, upstream test and probe took seconds.

`$B` below is `~/.cache/in-the-loop/change-verification`. `$J8` is Temurin 8u512
(`~/.sdkman/candidates/java/8.0.512.0+9-tem`, `release` sha256 `b965ee87…4d89e`, the `jdkReleaseSha256` of the
campaign's Retrofit preparation). `$J17` is Temurin 17.0.21+9 (`~/.sdkman/candidates/java/17.0.21.0+9-tem`,
`lib/modules` sha256 `fcdfc72a…469d7c`). JDK 21.0.13 is `~/.sdkman/candidates/java/21.0.13.0+9-tem`. **The default
`java` on `PATH` is JDK 25**, so name a JDK by its full path. Maven is 3.10.0 (sdkman).

## Layout

| Path | What it holds |
|---|---|
| `$B/src/WORKTREE` | One detached worktree per pinned revision ([below](#pinned-revisions)). To add one: `$B/scripts/mirror.sh OWNER/REPO MIRROR WORKTREE SHA [LOCAL_SOURCE]`. Build trees (`target/`) were deleted after their digests were recorded. |
| `~/.cache/in-the-loop/git-mirrors/{retrofit,commons-io,commons-csv}.git` | Bare mirrors, each pinned commit under `refs/pinned/WORKTREE`. `retrofit.git` is new. The `commons-io.git` mirror existed but was empty. |
| `$B/retrofit/{old,new}/` | Retrofit's built `retrofit-2.6.0.jar` and `converter-wire-2.6.0.jar`, the wire module's `test-classes/` (the upstream `Phone` message and `WireConverterFactoryTest`), `runtime.cp` and `test.cp` (ordered, absolute, into `$B/m2`), and `files.sha256`. |
| `$B/m2`, `$B/maven-settings.xml` | The local Maven repository, seeded by **hard links** from `~/.cache/in-the-loop/receiver-construction/receivers/maven-repository` (itself a hard-link snapshot of the external-upgrade campaign's shared repository), with settings pointing at it. New in it: okio 2.4.1, kotlin-stdlib 1.3.50, and the Spring Boot 2.7.18 and 3.0.13 graphs and build plugins. |
| `$B/resolve/boot-{2.7.18,3.0.13}/` | Throwaway resolution POMs (starter parent; starters web, validation, actuator, test; the Boot Maven plugin; Java 17), with `runtime.cp`, `test.cp` and `tree.txt`. Not applications. |
| `$B/probes/wire/WireProbe.java` | The throwaway JVM program that reproduces the brief's Wire observations ([below](#retrofitwire-on-a-jvm)). Not a claim or adapter. `probes.sha256`. |
| `$B/evidence/345-replay/` | The replay receipt that `validate_example.py 345 --replay` wrote, moved out of the checkout ([below](#example-345)). |
| `$B/evidence/organic-recount.json` | The organic scorecard recounted from today's receipts, written outside the checkout. |
| `$B/keys`, `$B/gnupg` | Public keys, `keys/asc/` (every `.asc` fetched from Maven Central), and this setup's own keyring (`GNUPGHOME=$B/gnupg`). Its agent was stopped. |
| `$B/logs/` | Every build, test, resolution and check: `central-check.txt`, `signatures.txt`, `signers.txt`, `boot-verify.txt`, `345-central.txt`, `wire-probe.txt`, `retrofit-*-test.txt`, `validate-345-replay.txt`, `check-*.txt`, `organic-recount.diff`, `cargo-release.txt`. |
| `$B/scripts/` | `mirror.sh`, `central_check.sh` (fetch a G:A:V, compare its SHA-1 with Central's, keep the `.asc`), `verify_paths.sh` (the same plus signature for files already in `$B/m2`), `jar_classes.py` (one digest over a jar's `.class` entries). |

## Pinned revisions

Commits fetched from github.com at depth 2. A commit id fixes its tree whatever the transport. None of these
commits or tags is signed.

| Worktree (`$B/src/`) | Commit | Tree | Identity |
|---|---|---|---|
| `retrofit-old` | `b8d593cf029652eb682434c0217ad92b5cbb005e` | `afc6cca4…` | `compsuite-i-1` old side (Wire 2.2.0), from `github.com/compsuite-team/retrofit` |
| `retrofit-new` | `577716be23b960fe24b31b1edcdf6b01e88a692e` | `63070831…` | new side (Wire 3.0.2), parent `b8d593cf`. The whole diff is one line of the root `pom.xml`: `wire-runtime`'s version `${wire.version}` → `3.0.2` |
| `io-345-parent` | `16bcc65a493123dfc1eeba7b3943a69acf03e47c` | `2d4ddf54…` | 345's `io-parent` (Commons IO, `BOMInputStream`) |
| `io-345-fix` | `4f1e3e564d0be5e2a01702039b1ddf3b5cea16ce` | `8397e89b…` | 345's `io-fix`, parent `16bcc65a` |
| `csv-345-parent` | `4f9a4037a2c1890154e1f077d66306ec54afbf60` | `655aaef9…` | 345's `csv-parent` (Commons CSV, `CSVParser`) |
| `csv-345-fix` | `7a4f93f3d13218a74dce0c8d8b85af4b341ac3ac` | `288a37cc…` | 345's `csv-fix`, a merge whose first parent is `4f9a4037` |

Both Retrofit sides have the corpus's `WireResponseBodyConverter.java` (sha256 `f41b5760…f6c962`) and module POM
`retrofit-converters/wire/pom.xml` (`c88d4a81…4f9559`, which is also the sha256 of Central's
`converter-wire-2.6.0.pom`).

The brief's planning head `2fff2b0d` is an ancestor of this workspace's head (`0d3e17f2`, "Record two new OpenAI
cyber-filter stops in VF-046").

## Retrofit/Wire

### Build and test commands

All on `$J8`, from `$B/src/retrofit-SIDE`, under a memory cap. The online and offline forms both work. Every
dependency and plugin is in `$B/m2`.

```sh
export JAVA_HOME=~/.sdkman/candidates/java/8.0.512.0+9-tem PATH=$JAVA_HOME/bin:$PATH
# the upstream named test (WireConverterFactoryTest#serializeAndDeserialize is one of its 5 tests)
mvn -o -s $B/maven-settings.xml --batch-mode --no-transfer-progress -pl retrofit-converters/wire -am \
  -Dtest=WireConverterFactoryTest -Dsurefire.failIfNoSpecifiedTests=false test
# the production artifacts and the runtime classpath, as the campaign's preparation did
mvn -o -s $B/maven-settings.xml --batch-mode --no-transfer-progress -pl retrofit-converters/wire -am \
  -Dmaven.test.skip=true package \
  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -DincludeScope=runtime -Dmdep.outputFile=target/runtime.cp
# the same test without Maven, from the cached classpath
$J8/bin/java -cp $(cat $B/retrofit/SIDE/test.cp) org.junit.runner.JUnitCore retrofit2.converter.wire.WireConverterFactoryTest
```

Maven 3.10's default Surefire is 3.6.0, which needs `-Dsurefire.failIfNoSpecifiedTests=false` (not
`-DfailIfNoTests=false`) when `-am` builds the core module. Each build takes about 10 s.

| Run | old (Wire 2.2.0) | new (Wire 3.0.2) |
|---|---|---|
| `WireConverterFactoryTest`, Maven | 5 run, 0 failures, **BUILD SUCCESS** | 5 run, **1 error**: `serializeAndDeserialize:64 » NoSuchMethodError okio.Utf8.size$default(Ljava/lang/String;IIILjava/lang/Object;)J` |
| the same, JUnitCore on `$B/retrofit/SIDE/test.cp` | `OK (5 tests)` | `Tests run: 5, Failures: 1`, the same `NoSuchMethodError` |

This matches the corpus's original CI (`passed` before, `error` after).

### Artifacts and classpaths

| File | sha256 | Note |
|---|---|---|
| `retrofit-2.6.0.jar` (built, both sides) | `d1ca389c…ad0132` | Timestamped, so a rebuild changes the jar digest. Its 110 class entries equal those of Central's `retrofit-2.6.0.jar` (`cbf7c823…98358c`) and of the campaign's prepared `089c70bc…` (old) and `684e4c43…` (new): one `jar_classes.py` digest, `f515e3bf…3e99`, for all of them. |
| `converter-wire-2.6.0.jar` (built, both sides) | `93b1383e…db006f2` | Its 4 classes equal the campaign's normalized `07b9bf04…38341` (the first entry of every Retrofit receipt classpath). |
| `test-classes/` | identical on both sides | `Phone.class` `538e140b…7351c`. `Phone` is the upstream test's generated message. |

The two runtime classpaths, in order (into `$B/m2`, then the built jars):

| old | new |
|---|---|
| `converter-wire-2.6.0.jar`, `retrofit-2.6.0.jar`, okhttp 3.12.0 `71787f2c…`, okio 1.15.0 `693fa319…`, wire-runtime 2.2.0 `893aabd7…` | `converter-wire-2.6.0.jar`, `retrofit-2.6.0.jar`, okhttp 3.12.0, **okio 1.15.0**, wire-runtime 3.0.2 `a31e28f8…`, kotlin-stdlib 1.3.10 `9b965055…`, annotations 13.0 `ace2a10d…`, kotlin-stdlib-common 1.3.50 `8ce678e8…` |

These are the same jars, in the same order, as the operational receipt's classpaths
(`verification/external-upgrades/corpus-runs/operational/01/compsuite-i-1.json`), except for the two built Retrofit
jars. The operational receipt's core-jar digests (`6917e9e4…`, `5681519c…`) are not cached anywhere on this machine.
The prepared area that is cached
(`~/.cache/in-the-loop/receiver-construction/receivers/area/modules/compsuite-i-1/SIDE/prepared.json`) has its own
build of that jar, with the same classes. Its `classpath` entries still name paths under
`~/.cache/in-the-loop/tmp/domain-foundations-receivers/` and `agent-tmp/0cea9d0e-…/`. Both exist today, but they are
scratch folders, and the hard-link snapshot beside them has the same bytes.

Wire 3.0.2's POM declares okio **2.4.1** and kotlin-stdlib 1.3.50. Retrofit's `dependencyManagement` keeps okio at
1.15.0, and the `NoSuchMethodError` comes from that. Both of Wire's declared versions are in `$B/m2`, checked like the
rest.

### Released artifacts, checked against Maven Central

`$B/logs/central-check.txt`: 16 coordinates, jar and POM each, **32 of 32 SHA-1s equal Central's `.sha1`**.
`$B/logs/signatures.txt`: **32 of 32 signatures valid**. 22 are good signatures by unexpired keys. 10 are valid
signatures by keys that have since expired (`EXPKEYSIG` with `VALIDSIG`): Wire 3.0.2 and okio 2.4.1 (Egor
Andreevici, `682F765E…685C46769DBB5E5D`), Retrofit and converter-wire 2.6.0 (Jake Wharton, `47BF5922…E0CB7823CFD00FBF`),
JetBrains annotations 13.0 (`2E3A1AFF…BCF4173966770193`). The others: okhttp and mockwebserver 3.12.0 (Jesse
Wilson), Wire 2.2.0 and okio 1.15.0 (Jake Wharton, `90EE1978…`), Kotlin Release keys, JUnit, Hamcrest, AssertJ, jsr305.
`$B/logs/signers.txt` maps each fingerprint to its key's name.

### Retrofit/Wire on a JVM

`$B/probes/wire/WireProbe.java` builds the converters through `WireConverterFactory.create()` and a `Retrofit`
instance, on each side's `runtime.cp` plus the upstream `test-classes`, under `$J8`. It does not use the project's
debugger or observer. It reads each recorded response body and writes `new Phone(number)` for the two phone strings
of the registered (`v3-final-finite/01`) and outbound (`operational/01`) records:

| Input | Response converter, old / new | Request converter, old | Request converter, new |
|---|---|---|---|
| `(519) 867-5309` | `(519) 867-5309` / `(519) 867-5309` | `Cg4oNTE5KSA4NjctNTMwOQ==` (= expected) | `NoSuchMethodError: okio.Utf8.size$default(Ljava/lang/String;IIILjava/lang/Object;)J` |
| `123` | `123` / `123` | `CgMxMjM=` (= expected) | the same `NoSuchMethodError` |

As the brief says: the response converter preserves the phone on both inputs, and serializing the same phone
throws `NoSuchMethodError` after the upgrade. **For information only**, the new side was also run with Wire's
declared okio 2.4.1 and kotlin-stdlib 1.3.50 in place of okio 1.15.0 and kotlin-stdlib 1.3.10. Both directions then
give the expected values on both inputs (`$B/logs/wire-probe.txt`). That is a different deployment from the
original new side. Whether and how to treat it is for the domain work.

## Example 345

| Input (`controls/libraries.json`) | sha256, cached at `~/.cache/in-the-loop/targets/sha256/` | Check |
|---|---|---|
| `io-parent` (built at `16bcc65a`) | `5f1fad34…850506a` | bytes hash to their name |
| `io-fix` (built at `4f1e3e56`) | `a9c4200f…8523a4` | the same |
| `csv-parent` (built at `4f9a4037`) | `13cddf90…dcbe` | the same |
| `csv-fix` (built at `7a4f93f3`) | `98986788…9701` | the same |
| `io-api`, `commons-io:commons-io:2.22.0` | `2b9a7b1f…04758` | SHA-1 = Central, good signature (Gary Gregory, `530AA5F25C25011F`) |
| `codec`, `commons-codec:commons-codec:1.22.0` | `d164fe79…72ce4` | SHA-1 = Central, good signature (the same key) |

The four upstream commits are mirrored and checked out ([above](#pinned-revisions)), and their parent relations are
as the catalog states.

`python3 examples/tools/validate_example.py 345 --replay` passed (4 min 18 s, 2 GB cap):

- form `prepared`;
- `plans: 19 tasks plan`. The brief counts 16 proof tasks and three replays;
- the replay re-ran on JDK 21.0.13. `parent-parent` violates the oracle at 68 of the 96 inputs, and `fix-fix` holds
  it on all 96, as the `install-both` pair expects;
- then the tests the validator runs with it: `test_packets` (1 s), `test_acceptance` (189 s), `test_targets_contract`
  (38 s), `test_gap_inventory` (15 s).

The validator re-ran only the `replay` task, not `replay-io` or `replay-csv`. **It writes a new receipt into the
example and updates `examples/index.json`.** This session moved that receipt to `$B/evidence/345-replay/` and
restored the checkout, so the example is unchanged. Without `--replay` it re-runs nothing on a JVM.

## Checks of the brief's cited measurements

| Command | Result |
|---|---|
| `python3 lib/benchmark/organic-java/report.py --check` | **Fails** ("stored scorecard differs from its receipts"), as the brief says. Recounted to `$B/evidence/organic-recount.json`: current strict native 39 qualified of 46 (26 established, 13 refuted, 7 open), finite 46 of 46 (33/13/0), 5 and 6 complete cases. The whole difference from `verification/organic-java-pr-campaign.json` (`$B/logs/organic-recount.diff`, 32 lines) is one added task run: the established native receipt `examples/360-javaparser-postorder-root/records/copy-set-nonempty-180-native/nonempty-parent-observed/20261122T030639Z-e73e09a8/result.json`, the brief's "[Additional JavaParser receipt]". |
| `python3 lib/benchmark/external-upgrades/pin.py --check lib/benchmark/external-upgrades/v3.json` | Fails at this head: "product inputs differ from the revision" (some 150 files in `lib/`, `examples/tools/` and `llm-dlc/tools/` changed since V3 was pinned). Expected for a later head. It checks the V3 pin, not today's tree. |
| `python3 lib/benchmark/external-upgrades/current_report.py --check` | Fails at this head: "the measured Java workflow has changed". The same cause. |
| `cargo build --manifest-path lib/Cargo.toml --release -j 6 --bin jvmcontract` (12 GB cap) | Already fresh: `lib/target/release/jvmcontract` sha256 `a61246d2…afa28` for `lib/` at `0d3e17f2`. It is a build product of this workspace, and the next release build overwrites it. |

## The queued work the brief feeds in

Each has its own setup record and cache, and this session did not repeat them. The caches are intact (sizes
today):

| Brief | Setup record | Cache | State on this line |
|---|---|---|---|
| The 15 Java semantics cases | [`jbmc-java-semantics-gap-brief-setup.md`](jbmc-java-semantics-gap-brief-setup.md) | `~/.cache/in-the-loop/jbmc-java-semantics-gap` (1.1 GB) | Results: [`jbmc-java-semantics-gap-results.md`](jbmc-java-semantics-gap-results.md), and the fast follow [`jbmc-fast-follow-calls-conversions-and-arrays-results.md`](jbmc-fast-follow-calls-conversions-and-arrays-results.md) |
| Receiver construction and property discovery | [`receiver-construction-and-property-discovery-brief-setup.md`](receiver-construction-and-property-discovery-brief-setup.md) | `~/.cache/in-the-loop/receiver-construction` (3.4 GB) | Results: [`receiver-construction-and-property-discovery-results.md`](receiver-construction-and-property-discovery-results.md), merged as `fdb0513f` |
| Independent kernel (Guava 336 → 346) | [`in-the-loop-trusted-kernel-experiment-brief-setup.md`](in-the-loop-trusted-kernel-experiment-brief-setup.md) | `~/.cache/in-the-loop/trusted-kernel` (77 MB) | Set up, **no results document on this line** |
| Spring workstream (binding, metadata, formatter) | [`spring-and-java-data-setup.md`](spring-and-java-data-setup.md) | `~/.cache/in-the-loop/spring-java-data` (3.2 GB) | Results: [`spring-and-java-data-workstream-results.md`](spring-and-java-data-workstream-results.md) |

## Spring Boot 2.7.x → 3.0.x prefetch (step 4)

The brief names a family, not an application or versions. This session picked neither. It prefetched the last
releases of both lines as of today, **2.7.18** and **3.0.13** (Central's `maven-metadata.xml`), so that whatever
application is picked builds mostly from cache:

```sh
export JAVA_HOME=~/.sdkman/candidates/java/17.0.21.0+9-tem PATH=$JAVA_HOME/bin:$PATH
cd $B/resolve/boot-VERSION && mvn -s $B/maven-settings.xml --batch-mode --no-transfer-progress \
  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:go-offline \
  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -DincludeScope=runtime -Dmdep.outputFile=runtime.cp \
  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:tree -DoutputFile=tree.txt
mvn -o -s $B/maven-settings.xml -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -DincludeScope=test -Dmdep.outputFile=test.cp
```

| Graph | runtime jars | test jars | `runtime.cp` sha256 | `test.cp` sha256 |
|---|---|---|---|---|
| Boot 2.7.18 (`javax`, Spring Framework 5.3) | 42 | 70 | `2fd6f6bc…a9fab9a4` | `c5fca2ee…ffe792` |
| Boot 3.0.13 (`jakarta`, Spring Framework 6.0) | 44 | 72 | `9907f6bb…a6c38a` | `69e96628…fbc90` |

`$B/logs/boot-verify.txt`: the 128 distinct jars of both test graphs plus the two `spring-boot-maven-plugin` jars.
**130 of 130 SHA-1s equal Central's.** 119 have good signatures. 7 have valid signatures by since-expired keys
(classmate 1.5.1, jakarta.validation-api 2.0.2 and 3.0.2, hamcrest 2.2, LatencyUtils 2.0.3, snakeyaml 1.30 and 1.33).
Two cannot be checked: hibernate-validator 6.2.5.Final and 8.0.1.Final are signed by `DFE102108BF9381F`, and neither
keyserver.ubuntu.com nor keys.openpgp.org serves that key with a user id. Two have no `.asc` on Central at all:
jboss-logging 3.4.3.Final and 3.5.3.Final. These four rest on SHA-1 alone.

## What could not be done, or was not attempted

- Nothing was refused, and no repository had gone away. `compsuite-team/retrofit` still answers on GitHub.
- The operational receipt's two built Retrofit core jars (`6917e9e4…`, `5681519c…`) are not on this machine. A
  rebuild gives different jar digests with the same class bytes ([above](#artifacts-and-classpaths)).
- The project's `check_scenarios.py` / `build.py --review-upgrade` route was not run on `compsuite-i-1`. It is the
  verifier's own JVM observation of the frozen claims, and running it is domain work.
- No signature for the four artifacts listed in the Boot section.

## Setup Agent Notes

### What is ready, and where

`$B` = `~/.cache/in-the-loop/change-verification`. Detail in the sections above.
- **Retrofit/Wire (`compsuite-i-1`)**: both pins checked out at `$B/src/retrofit-{old,new}` (mirror
  `~/.cache/in-the-loop/git-mirrors/retrofit.git`). The built jars, the upstream test classes, and ordered
  `runtime.cp` / `test.cp` for both sides are in `$B/retrofit/{old,new}/`, with `files.sha256`. Every dependency is
  in `$B/m2` (settings `$B/maven-settings.xml`), SHA-1- and signature-checked against Central, and that includes
  Wire 3.0.2's own declared okio 2.4.1 and kotlin-stdlib 1.3.50. The builds run on JDK 8 (`$J8`), offline (`mvn -o`).
- The campaign's own prepared Retrofit area (`prepared.json` per side) is
  `~/.cache/in-the-loop/receiver-construction/receivers/area/modules/compsuite-i-1/`. The scenario scopes are
  `lib/benchmark/external-upgrades/scenarios/compsuite-i-1/{scope.json,operational/scope.json}`. The historical
  receipts are `verification/external-upgrades/corpus-runs/v3-final-finite/01/compsuite-i-1.json` (response) and
  `…/operational/01/compsuite-i-1.json` (request).
- **Example 345**: all six library jars in `~/.cache/in-the-loop/targets/sha256/`, digest-checked. The four upstream
  commits are checked out at `$B/src/{io,csv}-345-{parent,fix}`.
- **Spring Boot 2.7.18 and 3.0.13** starter graphs (web, validation, actuator, test) and build plugins are in `$B/m2`,
  with classpaths in `$B/resolve/boot-*/`. JDK 17 is `~/.sdkman/candidates/java/17.0.21.0+9-tem`.
- The checker release binary `lib/target/release/jvmcontract` is current at `0d3e17f2`.
- The queued briefs' setups and caches are intact (table above). Semantics gap, receiver construction and Spring have
  results on this line. **The trusted kernel (Guava 336 → 346) is set up but has not run.**

### What was verified on a JVM

- Retrofit, JDK 8: `WireConverterFactoryTest` passes 5/5 on Wire 2.2.0. On 3.0.2 `serializeAndDeserialize` errors
  with `NoSuchMethodError okio.Utf8.size$default(Ljava/lang/String;IIILjava/lang/Object;)J`, through Maven and from
  the cached classpath alike.
- A throwaway probe through `WireConverterFactory`, on the two recorded phones: the response converter returns
  `(519) 867-5309` and `123` on both sides. The request converter writes `Cg4oNTE5KSA4NjctNTMwOQ==` and `CgMxMjM=`
  on the old side and throws the same `NoSuchMethodError` on the new side. That is the brief's preserved read and
  missed write. Informational: with Wire's declared okio 2.4.1 in place of 1.15.0, the new side writes the expected
  bytes too.
- Example 345, JDK 21: `validate_example.py 345 --replay` passes. `parent-parent` violates the oracle on 68 of 96
  inputs and `fix-fix` holds it on all 96.
- The organic recount reproduces the brief exactly: strict native 39/46, finite 46/46. The stored scorecard differs
  from it only by the later JavaParser receipt `20261122T030639Z-e73e09a8`.

### What to know before starting

- **The default `java` is JDK 25.** Retrofit's subject JDK is 8 (`$J8`), 345 runs on 21, and the Boot prefetch
  used 17.
- The new Retrofit side's runtime has **okio 1.15.0**, because Retrofit's `dependencyManagement` keeps it there,
  while Wire 3.0.2 declares okio 2.4.1. The pair's whole source diff is one line of the root POM. Old and new built
  Retrofit jars are byte-identical, and so are the test classes.
- Retrofit's built jars carry timestamps, so a rebuild changes their sha256 but not their classes. Compare class
  content (`$B/scripts/jar_classes.py`) or use the campaign's normalized assets. The operational receipt's core-jar
  digests are not reproducible from anything cached.
- `validate_example.py NNN --replay` **writes a new receipt into the example** and rewrites `examples/index.json`,
  and it re-runs only the task named `replay`. It also runs about 4 minutes of tests.
- `pin.py --check v3.json` and `current_report.py --check` fail at this head because the product changed since V3
  was pinned, not because a receipt is wrong. The organic `report.py --check` fails for the reason the brief gives.
- In `$B/m2`, about 2 GB are hard links shared with the receiver-construction snapshot. Don't edit files there in
  place.
- Four Boot-graph jars rest on SHA-1 alone: hibernate-validator 6.2.5/8.0.1 (signing key unavailable) and
  jboss-logging 3.4.3/3.5.3 (unsigned on Central). There are no snapshot dependencies anywhere in this setup.

### What is left for the domain work on purpose

- Everything the brief's steps ask for: the baseline runs of the current workflow on 345 and Retrofit, the inventory
  and planner inputs, the new request-side obligation, the second-commit matrix, and the scoring.
- Running `check_scenarios.py` or `build.py --review-upgrade` on `compsuite-i-1`, and any claims, adapters or
  sidecars for it.
- Choosing the held-back Spring Boot 2.7 → 3.0 application, its workflows, budgets and expectations, and fetching its
  own sources. Only the generic starter graphs are prefetched.
- Whether the okio-2.4.1 graph counts as a valid new-side deployment, or as a migrated client.
- Running the trusted-kernel experiment.
