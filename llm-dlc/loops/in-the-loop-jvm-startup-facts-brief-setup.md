# Setup for the JVM startup facts brief

Mechanical setup for [`in-the-loop-jvm-startup-facts-brief.md`](in-the-loop-jvm-startup-facts-brief.md).
A setup session (Claude Opus 5.5) did it on 2026-11-26, before the domain work starts.

Every case the brief names was already prepared by an earlier campaign: deployments, source worktrees at the pins,
JDKs, the historical observers and their receipts. The session:

- checked every artifact those cases name against its recorded digest, at the path the case's reader resolves, and
  every source worktree against its pinned commit and tree;
- fetched the one missing input, Batik's upstream source at `1_17`, into a new shallow bare mirror, and compared it
  blob by blob with the Debian source tarball and the deployed jars;
- re-ran on the original JVMs, read-only, the registered public observations of Commons IO, ThreeTenBP, POI and Spring
  480, and the 16 historical charset trials of Commons IO. Each fresh result equals the committed receipt;
- checked on fresh JVMs the startup outcomes the brief states for the default charset (`"é".getBytes().length`),
  Commons Configuration's own and inherited invalid lookup name, and JavaParser's cleared `line.separator`;
- recorded the source blob ids and class digests of the startup classes the brief names;
- confirmed that `lib/target/release/jvmcontract` is current.

It wrote no claims, examples, sidecars, adapters, callers, recipes, receipts or library code. It allocated no example
ids, and ran neither the verifier nor any prover on a claim. It ran no capture with `ObservedInitializer`: what that
recorder sees is the brief's own measurement. It changed no file in the repository other than this one.
**No verification job was needed.** The brief names no upstream build or upstream test run, every re-run took
seconds, and the earlier setups record the builds and landed-test runs of these pins (links per case below).

`$S` below is `~/.cache/in-the-loop/jvm-startup-facts` (this work, 61 MB, nearly all the Batik worktree). The other
caches are the earlier campaigns':

| Name | Path | Setup record |
|---|---|---|
| `$FF` | `~/.cache/in-the-loop/organic-composition-ff` | [fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md) (Commons IO, ThreeTenBP, POI) |
| `$PANEL` | `~/.cache/in-the-loop/beyond-jbmc/panel` | [beyond-jbmc campaign setup](beyond-jbmc-java-change-verification-campaign-setup.md) (Batik, slot 04) |
| `$RC` | `~/.cache/in-the-loop/receiver-construction` | [receiver construction setup](receiver-construction-and-property-discovery-brief-setup.md) (Commons Configuration) |
| `$P` | `~/.cache/in-the-loop/spring-pr-links-p01-p30` | [P01–P30 setup](spring-framework-pr-links-p01-p30-brief-setup.md) (example 480) |
| Maven cache | `examples/tools/targets/runtime_maven.Cache()` (by sha256) | examples 355 and 360 (captured upstream builds, organic-java-pr-campaign) |

## Starting commit

The brief was reviewed against `develop` at `32d3a22cfbae921d272649eaaae608d60ae89ecf`. This setup ran at
`5f0b2389344879610f907ac9ee5b048dd59c9df8` ("Merge the single-agent run generated-observers-and-callers into the
line"), which has `32d3a22c…` as an ancestor (122 commits later). The brief's "Generated callers brief" link points at a
private chat library. The repository's copy is
[`in-the-loop-generated-observers-and-callers-brief.md`](in-the-loop-generated-observers-and-callers-brief.md), and its
results are merged at this head ([results](in-the-loop-generated-observers-and-callers-brief-results.md)).

Of the in-repository files the brief links, these changed between `32d3a22c…` and this head (`git diff --stat`), so
their line anchors in the brief may have moved: `examples/tools/targets/change_evidence.py` (+54/−),
`examples/tools/targets/java/UpgradeTrace.java` (+248), `examples/tools/targets/recipes.py` (+44),
`lib/src/property.rs` (+4: a JBMC multi-release gap, not the cache guard), `llm-dlc/runtime.md` (+50) and
`verification/findings.md` (+54). At this head the `--observed-initializer` with `--cache` refusal is at
`lib/src/property.rs:302-304`, and VF-054 starts at `verification/findings.md:485`. `ObservedInitializer.java`,
`lib/src/observed.rs`, `lib/src/bmc/{observed,reflection,jar_resources}.rs`, `lib/src/property/startup_witness.rs`,
`lib/benchmark/domain-foundations/startup.py`, the setting and observed countermodel fixtures and tests, the IO driver
and receipts, the target-claim schema, examples 332 and 480 and the receiver-discovery `recovery.md` are unchanged.

## Layout of `$S`

| Path | What it holds |
|---|---|
| `$S/scripts/` | `check_inputs.py`, `observe.py`, `charset_profiles.py`, `properties_check.py`, `startup_classes.py` (below). Digests in `$S/logs/scripts.sha256`. |
| `$S/logs/inputs.json` | The digest and pin check of every case (sha256 `0423063ed178fc0bd56c2f06c741448484c52a855a29008dfc9dc22820aaf087`). |
| `$S/logs/observe-{io,threeten,poi}.txt`, `charset-profiles.txt`, `getbytes-{21,25}.txt`, `properties-check.txt`, `replay-480.txt` | The JVM re-runs (below). |
| `$S/logs/startup-classes.tsv` | Source blob ids and class digests of the startup classes (below). |
| `$S/logs/cargo-build.txt` | The `jvmcontract` up-to-date check. |
| `$S/worktrees/batik-1_17` | Batik source at `3c83de345f21cae4f4a64dfe6244483f87885808`, a worktree of `~/.cache/in-the-loop/git-mirrors/xmlgraphics-batik.git`. |
| `$S/probes/` | Scratch copies and outputs of the re-runs: `observe-*`, `charset/verification/organic-composition/io/charset-profiles.json` (the fresh copy of the receipt), `getbytes/`, `properties/`, `batik/` (the two extracted 1.17 entries from each jar and the `.orig`, and the file lists of the tree comparison). **Evaluator material**: they hold the historical observers and their actual outcomes. |
| `$S/tmp` | `TMPDIR` for this work. |

No keyring was needed (the one download is a git commit fetched by its SHA), so no `gpg` daemon was started.

## Tools

| Tool | Where | Identity |
|---|---|---|
| Temurin 21.0.13+9 | `~/.sdkman/candidates/java/21.0.13.0+9-tem` (every case's recorded JDK, except 480; "the pinned image" of the IO driver) | `release` `f83f6dcc966043c93cd498ac8e7ee7c310852074970d62c702e4ad2710002898`; `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c` |
| Temurin 17.0.21+9 | `~/.sdkman/candidates/java/17.0.21.0+9-tem` (example 480) | `release` `9568390645661374febde48f3c7a019f21cb116d6e4c627de29c119aa7bd0efc`; `lib/modules` `fcdfc72acc1ec5e8542fc2170c587ef23edbbdeddcbf435f169d270e02469d7c` |
| Temurin 25.0.5+8 | `~/.sdkman/candidates/java/25.0.5.0+8-tem` (**the default `java` on `PATH`**; the other JDK the WeakHashMap/Properties models are bound to, VF-054) | `release` `8545053a54a73969a65db2c8157f40f89bcdcf7526ae90a7ce9b3061c01bc34a`; `lib/modules` `f5463cffa81c51b3c13f57e2c23eacceab2b12e842069acf2facd5485f63bc85` |
| Temurin 8u512-b09 | `~/.sdkman/candidates/java/8.0.512.0+9-tem` (ThreeTenBP's upstream build) | `release` `b965ee876a40eb8b76e7146403b3efc54e309ebd573064a18c7b87665ce4d89e` |
| `jvmcontract` release | `lib/target/release/jvmcontract` | sha256 `d0bcabc8fe2cc1af89d2e999c55bbc5995231a47fe8b8b3cfb91090ba8895258`, built at 21:27 after `3c448d85f941d2dbc16bda43d3ee8554fa052e91` (21:18), the last commit touching `lib/src`. `cargo build --release -j 4 --bin jvmcontract` at this head finished in 0.09 s with nothing to rebuild. |

Every case's recorded `jdkReleaseSha256` equals the `release` digest of the JDK it names. The host has the `C` and
`C.utf8` locales (`locale -a`), the two the IO driver uses.

## Cases: inputs, pins and digests

`$S/scripts/check_inputs.py` (run as `python3 -I $S/scripts/check_inputs.py . $S/logs/inputs.json` from the
repository root, with `TMPDIR=$S/tmp`) checked every case. Result: **all inputs match**.

### Commons IO #520 (first slice, exercise 1)

Reader: `lib/benchmark/organic-composition/io/{old,new}/prepared.json` (absolute paths). Driver of the 16 trials:
`lib/benchmark/organic-composition/io/charset/profiles.py` (with `CharsetPositions.java` and `io/UpgradeProbe.java`).

| Side | Commit | Tree | Jar | sha256 |
|---|---|---|---|---|
| old | `dccc7011046542e9375b6a4f90b24ca02b01a890` | `8739971752b6f238f6ac2b78decdc501dee0e61c` | `$FF/artifacts/E-commons-io-parent.jar` | `24718c09f6e0f7990a968e144be96042a20b97510b4dc611e1c97c3c3189e341` |
| new | `3e7f57784c2fa8190fb3c75c977920ba6022de66` | `0e3c864e504db0ba773198c0254794cad2ac8fc4` | `$FF/artifacts/E-commons-io-fix.jar` | `48fc79897f329de108aa4452288c86be27f76c7146e33c38bfc345b5d7885dcc` |

Worktrees `$FF/worktrees/E-commons-io-{parent,fix}` are at these pins and trees, clean. The jars are the complete
production jars built at the pins (Maven 3.10.0, JDK 17, `--release 8`; no runtime dependencies). The landed
`CharSequenceInputStreamTest` passes on the fix (418/418) and fails 7 of 418 on the parent
([fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md#built-jars-and-landed-tests), which
also gives the offline Maven command). The small countermodel `sc.Encoded` is
`lib/tests/fixtures/setting-countermodels/sc/Encoded.java`, in the repository; it needs nothing fetched.

### ThreeTenBP #77 (exercise 2)

Reader: `lib/benchmark/organic-composition/threeten/{old,new}/prepared.json`; resources
`META-INF/services/org.threeten.bp.zone.ZoneRulesProvider` and `org/threeten/bp/TZDB.dat` are bound there.

| Side | Commit | Tree | Jar | sha256 |
|---|---|---|---|---|
| old | `cc6cbd71d14e44633d3afdcd89afa096a8f1d145` | `2165f78f7c511c9464695f687088a387c05fc5a0` | `$FF/artifacts/A-threetenbp-parent.jar` | `f2db710ef43a72dc7987b55f23b9397376f6fc6f090e335df721553dfc2d6ebc` |
| new | `f0865ac1e3f5d06822560f09bc9c59f5138fa16f` (the brief's source link) | `9264d219787d5c16872d67fd7be846ecef32b59a` | `$FF/artifacts/A-threetenbp-fix.jar` | `568a09e20cecaec3c5df3e8bcaf3bd35809dc3e329992b7799956d35b535df89` |

Worktrees `$FF/worktrees/A-threetenbp-{parent,fix}`, clean. Version 1.3.6, built by Maven 3.10.0 on JDK 8 (target 1.6),
no runtime dependencies. In `Chronology.java` at the fix, `LOCALE_METHOD` is declared at line 164, assigned at line
172, and invoked with `"ca"` at line 246. The landed `TestZonedDateTime` passes on the fix (515/515) and fails 6 on the
parent ([fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md#built-jars-and-landed-tests)).

### Apache POI #1420 with Log4j API (exercise 3)

Reader: `lib/benchmark/organic-composition/poi/{old,new}/prepared.json`, seven entries per side in this order: the POI
jar, then from `$FF/m2` commons-codec 1.23.0, commons-collections4 4.6.0, commons-math3 3.6.1, commons-io 2.22.0,
SparseBitSet 1.3, log4j-api 2.26.1. No log4j-core is on the classpath.

| Side | Commit | Tree | Jar | sha256 |
|---|---|---|---|---|
| old | `6b277ffc80c0f3876126781bcee12cb74d489ad2` | `8aa714fc3e1f72950c1d9e4e62c9db7605386460` | `$FF/artifacts/B-poi-parent.jar` | `6e43938a40a3bafd59ba6bcc89f03a89a9f4c54520f08c3d8481d5dc1e7502a5` |
| new | `bd15f5bc11c1433725d031642bdfaf64f4c2ce72` | `73b20382b7bb34b2bddcd4383b73ba10a2ee081e` | `$FF/artifacts/B-poi-fix.jar` | `3bb5a6d4840677d91125456f35afab47e2b2a904ac8dc3c730d704957852d5fa` |

The dependency digests are in `$S/logs/inputs.json` (`organic.poi/*.classpath`), all matching. `log4j-api-2.26.1.jar`
is sha256 `f1810a4704ccce019d02bba029dc02a4f2ac0c997f647b465e7d409c1927f822` (its signature was checked by the
fast-follow setup: ASF Logging Services RM `077E8893A6DCC33DD4A4D5B256E73BA9A0B592D0`). Its sources jar is beside it,
`$FF/m2/org/apache/logging/log4j/log4j-api/2.26.1/log4j-api-2.26.1-sources.jar`, sha256
`d136436fb50076930f99aa5f45a83c661f71b84c4bb99d08ba3850ff794281bd`. This session checked both against their Central
`.sha1` files (`b9864ed8d0c01f65f3b0bf70f1447e5cc1b49c24`, `c98d07e79127db91e9bc2004281490ac7c5b8f02`). It holds
`org/apache/logging/log4j/util/{PropertiesUtil,SystemPropertiesPropertySource,EnvironmentPropertySource}.java`.
The landed `TestDataFormatter` passes on the fix (59 run, 2 skipped) and fails 2 on the parent (job
`20261124-135600-setup-build-apache-poi-s-poi-module-at-b`,
[fast-follow setup](organic-java-pr-capability-composition-fast-follow-setup.md#jobs), with its offline Gradle command).
The constructor-first experiment the brief cites is `lib/benchmark/organic-composition/poi/{StartupHistory.java,startup_frontier.py}`
with its record `verification/organic-composition/poi/observed-frontier.json`.

### Batik 1.17, the parser properties (exercise 4)

The pinned deployment is beyond-jbmc slot 04, Ubuntu `libbatik-java` 1.17 → 1.18, already extracted at
`$PANEL/evaluation/04/packet/{old,new}/NNN.jar` (53 jars old, 39 new), listed with their digests in
`$PANEL/evaluation/04/packet/inputs.json` (sha256 `43691f03acee60b16488c6936055e0d0377823ec5b07c379bd93e94946f2a3c2`,
equal to the scaffold receipt's `packetSha256`). Every jar matches; the first of each side equals the roster
(`lib/benchmark/beyond-jbmc/blind/draw/roster.json`): old `bacf416330ae68c01d4d6a4cab8dd6006643c83136b2f7cd8e5bfd526642ca12`,
new `f6eb2dd1b5962c6690fc924304386fb808fada1bd0422071fd6c44d33e785fa7`. The reader that builds manifests from the
packet is `resource_transfer.manifests` in `lib/benchmark/beyond-jbmc/blind/resource_transfer.py`.

**Two jars on each side carry `XMLResourceDescriptor`**: on 1.17, `old/000.jar` (manifest
`Implementation-Title: org.apache.xmlgraphics:batik-all`, `Implementation-Version: 1.17`) and `old/014.jar` (the
`org.apache.batik.util` bundle, whose manifest still says `Bundle-Version: 1.12.0` although its entries are dated
2023-08-24 like the rest of 1.17); on 1.18, `new/000.jar` and `new/006.jar`. On all four, the class and the
properties file are the same bytes (table in [Startup classes](#startup-classes-source-blobs-and-class-digests)), so
which copy a loader selects is decided by order, not content. The packaged
`org/apache/batik/util/resources/XMLResourceDescriptor.properties` has one non-comment line:
`org.w3c.css.sac.driver = org.apache.batik.css.parser.Parser`.

**Upstream source, fetched by this session.** The brief links `batik-1_17`, which is a branch on
`https://github.com/apache/xmlgraphics-batik`. It points at the same commit as the release tag `1_17`:
`3c83de345f21cae4f4a64dfe6244483f87885808` (tree `c7d90c233cee42d0349f93c2d039b90dbcdf01b0`, "Update version",
2023-08-14). `git ls-remote` shows no `^{}` entry for `1_17`, so it is a lightweight tag and has no signature to check;
the commit was fetched by its SHA, which is its own content hash, and `git fsck` is clean. Mirror:
`~/.cache/in-the-loop/git-mirrors/xmlgraphics-batik.git`, **shallow** (`--depth 1`, only `refs/tags/1_17`, 32 MB);
worktree `$S/worktrees/batik-1_17`. Blob comparison:

| File | git at `1_17` | Debian `batik-1.17` `.orig` (`$PANEL/54e63c3bf560573b621f1e0a4f3ffe77ecef5b98e2f202e42f249be6fbb952ed.orig`) | Deployed jars |
|---|---|---|---|
| `batik-util/src/main/java/org/apache/batik/util/XMLResourceDescriptor.java` | `ad7c5a7279f37b5c686757d2f9930c509c9db71f` | same | (class, below) |
| `batik-util/src/main/resources/org/apache/batik/util/resources/XMLResourceDescriptor.properties` | `68368ce0a57219fa8d61d228b437497da6d16270` | same | same blob in all four jars |

Over the whole tree, the `.orig` has 2,823 files and the git tree 3,475; the 2,820 they share are identical. The `.orig`
adds `LICENSE`, `NOTICE` and `samples/3D.png`, and leaves out 655 files (repository metadata, checkstyle files and the
bundled demo jars under `documentation-sources/`). The 1.18 `.orig` is
`$PANEL/07c3971adc2b2e8c5ecb3e242a19a428e6108770740f8c4ce8fecea5cd800d36.orig`; 1.18's git source was not fetched, as
the brief names only 1.17.

### Commons Configuration #565 and #601 (exercise 8)

Reader: `callers.prepared_inputs` in `lib/benchmark/receiver-discovery/callers.py`, which relocates
`$RC/receivers/area/slices/<key>/{old,new}/prepared.json` and rechecks every digest. 23 classpath entries per side,
all matching (`$S/logs/inputs.json`, `configuration`).

| Key | Side | Commit (the manifest's) | Differing dependency (`recovery.md`) |
|---|---|---|---|
| `commons-configuration-565` | old | `b485cdac96378f862237a6ad2fe3c8f57ae0612c` | Jackson Databind 2.18.3 |
| `commons-configuration-565` | new | `d2101a20e2b74ced47ae57dd3b6d1d90b03d409b` | Jackson Databind 2.19.0 |
| `commons-configuration-601` | old | `4c3ff511d02fb23b0ce967930bb828e8e69ee25e` | SnakeYAML 2.4 |
| `commons-configuration-601` | new | `0721015a499d1848bdf5a524c0f8a4f3a4fbbca2` | SnakeYAML 2.5 |

Sources: `$RC/src/configuration-{565,601}-{old,new}/` (source exports, not git checkouts). The recorded measurements
are `verification/receiver-discovery/recovery/commons-configuration-{565,601}/measurement.json` and `live-table.json`
(job `20261124-035245-recover-json-and-yaml-public-callers-fro`).

### JavaParser #4538 (example 360) and Avro #3878 (example 355) (exercises 9, 11)

Both use the `upstream-build` route with captured builds, restored by `upstream_artifact.restore` from the Maven cache.

| Example | Side | Commit | Build record (sha256) | Entries cached | Original jar (sha256) |
|---|---|---|---|---|---|
| 360 | parent | `e0eb16b8870fc05c03ab794e502dd76f97422e26` | `records/build-historical/build-parent.json` (`1265afd09271daf1ad220c8ba1fe1fa6b941cd260b4e9c3a7719eae3072170ea`) | 1/1 | `javaparser-core-3.26.2-SNAPSHOT.jar` (`cbe961009b6fafe13085b895a486660a470485ac34316043e20df41188f446a8`) |
| 360 | fix | `6529f264066e31bd9e78c71111ade3a20142d285` | `records/build-historical/build-fix.json` (`2a29cb8bb88d185048cb98b39375eb7d11130758dd24a7644e4460e19cbe48b5`) | 1/1 | `javaparser-core-3.26.2-SNAPSHOT.jar` (`62cf2f2c4bb4be2ced24f7914b4d22ae9cc2a760a5ab11cd2cd867e68d69cd27`) |
| 355 | parent | `cc134b3ff6016d86a5f97798afc77ef1a47b7d73` | `records/build-avro-root/build-parent.json` (`77ea572171a14e3623e4ff44ea7a882ace7a8afd6c5d0ca185304a6a7da32164`) | 124/124 | `avro-mapred-1.13.0-SNAPSHOT.jar` (`3fff1ce9c4a2b59575b4190d05a8cf937176ecc0e365ab215b70d84daaec12c2`) |
| 355 | fix | `f3bb10eaea1f03eb17893bc779eb26213da8177c` | `records/build-avro-root/build-fix.json` (`a66e86d7f7725c510796540b359ecc394c57b96a16a5499b43da3131313a9ebf`) | 124/124 | `avro-mapred-1.13.0-SNAPSHOT.jar` (`dce9b9276b50fc76cb7ed430c2fa70e2ec0f08fa902a87962d07b7f38857d96d`) |

The git mirrors `~/.cache/in-the-loop/git-mirrors/{javaparser,avro}.git` hold these commits. Avro's recorded four-root
startup (the 220-class, 1,079-object state of VF-054) is what example 355's `claims/*-lookup-startup.json` and their
receipts consume. JavaParser's recorded separator profiles are
`verification/receiver-discovery/recovery/javaparser/clean-profiles/measurement.json` (job
`20261124-041236-replay-javaparser-separator-claims-on-th`); its `boundClassSha256` for `LineSeparator` equals the class
digest in the table below. Example 332 is a fixture example (`examples/332-paper-initialization/{cached,helper,live}`),
in the repository.

### Spring example 480 (exercise 10)

Reader: `examples/480-spring-nested-return-type/runtime.json`, cache `$P`, JDK 17. Six classpath files, all matching:
`artifacts/P03-{parent,fix}/jars/spring-core-7.1.0-SNAPSHOT.jar` and commons-logging 1.3.5, micrometer-observation
1.16.4, micrometer-commons 1.16.4, jspecify 1.0.0 from `$P/gradle-home` (digests in `runtime.json`). Worktrees
`$P/worktrees/P03-parent` (`a0dba60fa657088015be64e9987f68c179c76e08`, tree `a2f57238fc5eca1ab28645eb2a5b8be98f233125`)
and `$P/worktrees/P03-fix` (`c1e90d51ca6a8379a0366f30cd77e5c1be019447`, tree `ab9abc8bef7464f64382aa043cb316b7985cb95c`),
clean.

### In-repository fixtures (exercises 5–7)

Nothing to fetch: the six setting countermodels are `lib/tests/fixtures/setting-countermodels/sc/*.java` (with
`README.md`), `oc.JointStartup` is `lib/tests/fixtures/observed-countermodels/app/oc/JointStartup.java`, tested in
`lib/tests/observed_countermodels.rs`. Exercise 5's properties fixture is the domain agent's to write; it needs only
the JDK.

## Startup classes: source blobs and class digests

`python3 -I $S/scripts/startup_classes.py $S/logs/startup-classes.tsv .` (from the repository root). For Batik and
Configuration the "source blob" column is the git blob id of the bytes named (the jar entry, or the exported source
file), since those are not git checkouts.

| Case | Side | Source file, blob | Class, sha256 |
|---|---|---|---|
| Commons IO | parent and fix | `src/main/java/org/apache/commons/io/Charsets.java`, `11433cfed6599726bccda0f93a6bd84daa6ca5d5` | `org/apache/commons/io/Charsets.class`, `1d252090d6d4a98f141f9d5bc5df2c4f8bb382212409f8e74c24337f6f27db8d` |
| ThreeTenBP | parent and fix | `src/main/java/org/threeten/bp/chrono/Chronology.java`, `c6a62efabbde64d939dd6fac94a43032379f7ed9` | `org/threeten/bp/chrono/Chronology.class`, `142767ee8a32284b07b4752b03206ef1101e89cfc5c2e6387982ce6b5d9efff1` |
| ThreeTenBP | parent and fix | `src/main/java/org/threeten/bp/format/DateTimeFormatter.java`, `e6bcdc2a9046c488feacf79a8429f377b8d431e1` | `org/threeten/bp/format/DateTimeFormatter.class`, `a810b97bba10e91c8d9caea5b6d61091aa2a9874a686ef19a22d44aef5d5a2db` |
| POI | parent | `poi/src/main/java/org/apache/poi/ss/usermodel/DataFormatter.java`, `c40609fe9dceb8ff1a28c199211b9e3393e61aea` | `org/apache/poi/ss/usermodel/DataFormatter.class`, `e4982b2ac7ccc06340120f75213b02bd1fcfc2f2d140a425c4fae1c72e18e25c` |
| POI | fix | the same file, `1badd7f58bc02dedf702a63e3fa119fc1819566a` | the same class, `54883f8d266126d89bbc94028fa50f86c2b648af67991a14abf59bd92181a951` |
| Batik | 1.17 (`old/000.jar`, `old/014.jar`) and 1.18 (`new/000.jar`, `new/006.jar`) | `XMLResourceDescriptor.properties` entry, blob `68368ce0a57219fa8d61d228b437497da6d16270`, sha256 `f8898b358ab657e58d71ca5182f6a02f32847762c1ef68cc245327b166fb6708` | `org/apache/batik/util/XMLResourceDescriptor.class`, `aa059142749f5f9a2e3d1853165e7fc146a7ed71f68959371bb78ec0701b94e6` |
| Configuration #565 | old and new | `$RC/src/configuration-565-{old,new}/…/interpol/ConfigurationInterpolator.java`, blob `1cfec976ae956a643db12b2adebc1b700f3b380f` | (not extracted) |
| Configuration #601 | old and new | `$RC/src/configuration-601-{old,new}/…/interpol/ConfigurationInterpolator.java`, blob `cc3abe3dbf4b53917bacc1c8cf7aa9cb7827cf18` | (not extracted) |
| JavaParser #4538 | parent and fix | `javaparser-core/src/main/java/com/github/javaparser/utils/LineSeparator.java`, `a226d632d4ef8f3a169dd088f3a9575e93f2422e` | `com/github/javaparser/utils/LineSeparator.class`, `0413a3f8b4707638860dc0dea988cdf0dae425da5eeae8cc803cae7724919e56` |

The startup class is the same on both sides of every pair except POI, where `DataFormatter` itself is the changed
class. `recovery.md` gives the `InterpolatorSpecification` class digest common to all four Configuration graphs.

## What was run on a JVM

Every run below is read-only with respect to the repository (`jj diff` was empty afterwards), each under
`systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 choom -n 500 -- timeout 300`, with
`TMPDIR=$S/tmp`, on JDK 21.0.13 unless named. Each took seconds.

| Case | Command (from the repository root) | Result |
|---|---|---|
| Commons IO, ThreeTenBP, POI | `python3 -I $S/scripts/observe.py . $S/probes/observe-CASE ~/.sdkman/candidates/java/21.0.13.0+9-tem CASE` for `io`, `threeten`, `poi`. It compiles the case's `UpgradeProbe.java` with the shared `UpgradeObservation` launcher against each prepared classpath, and runs each case of each `workflows.json` scope in a fresh JVM, as `register.physical()` does | All equal their registered values (old: the scope's `expected`; new: the allowed change's `expectedNew`, else `expected`): IO 8/8, ThreeTenBP 12/12, POI 12/12 (the twelve of `poi/physical.json`) |
| Commons IO, 16 charset trials | `python3 -I $S/scripts/charset_profiles.py . $S/probes/charset`: runs `io/charset/profiles.py`'s `main()` with its `ROOT` pointed at the probe folder, then compares bytes | **The fresh `charset-profiles.json` is byte-identical to `verification/organic-composition/io/charset-profiles.json`**: 8 profiles (old/new × `C.UTF-8`/`C` × explicit/default constructor), each two fresh JVMs with `-Dfile.encoding=COMPAT`, 32 read/reset cycles each |
| Default charset | `$S/probes/getbytes/src/DefaultBytes.java` (`"é".getBytes().length` first, then `Charset.defaultCharset()` and three properties), in `env -i` with `LC_ALL`/`LANG` set, on JDK 21.0.13 and 25.0.5 | See below |
| Configuration #565/#601, JavaParser #4538 | `python3 -I $S/scripts/properties_check.py . $S/probes/properties` (`TableModes.java`): sets the key in the stock table (`own`), in the parent of a child table installed with `System.setProperties` (`inherited`), or clears it, then touches the class twice | See below |
| Spring 480 | `PYTHONPATH=examples/tools python3 -m targets.public_comparison 480` (no `--record`: it raises if the fresh observations differ from `observations.json`) | Exit 0: fresh observations equal the committed receipt |

**Agreement with the brief:**

| # | Case | What the brief says | Fresh observation |
|---|---|---|---|
| 1 | Commons IO | 16 trials crossed explicit and defaulted constructors with UTF-8 and US-ASCII defaults; explicit UTF-8 preserves the bytes in both profiles; the defaulted ASCII encoder replaces both unrepresentable characters with `3f` | Under `C`, default `US-ASCII`: the explicit constructor's encoder is UTF-8 with initial mark `4,1,4,1,4,7,c3a9e4b8ad5a`, as under `C.UTF-8`; the defaulted one's is US-ASCII with `4,1,4,1,4,4,3f3f5a`. The registered rewinds: parent third read `51b8ad5a253647`, fix `51c3a9e4253647` |
| 1 | default charset | `"é".getBytes().length` is 2 under UTF-8 and 1 under the recorded ASCII profile | `C.UTF-8` with or without `COMPAT`: 2 bytes, `UTF-8`. `C` with `-Dfile.encoding=COMPAT`: **1 byte, default `US-ASCII`, but `file.encoding` reads `ANSI_X3.4-1968`** (as do `native.encoding` and `sun.jnu.encoding`). `C` without the flag: 2 bytes, `UTF-8` (JEP 400). The same on JDK 21.0.13 and 25.0.5 |
| 2 | ThreeTenBP | DST-overlap histories as registered | New York: parent `2016-11-06T05:00:00Z/40/-1\|2016-11-06T05:00:00Z/80/-1\|end@80/80/80`, fix second instant `2016-11-06T06:00:00Z`; Berlin: parent second `2016-10-30T00:00:00Z`, fix `2016-10-30T01:00:00Z` |
| 3 | POI | twelve original locale observations | 12/12 equal `poi/physical.json` (e.g. parent custom en-US `en-US[.]:0.001~…`, fix `0.001000000тг.~…`) |
| 8 | Configuration | an invalid own entry gives first-use `ExceptionInInitializerError` and then `NoClassDefFoundError`; the inherited setting preserves ordinary outputs | On all four deployments, through `ConfigurationInterpolator.getDefaultPrefixLookups()`: absent, 14 lookups twice; own `_`, `ExceptionInInitializerError` (cause `IllegalArgumentException`) then `NoClassDefFoundError` (cause `ExceptionInInitializerError`); inherited `_` (child has no own key, `getProperty` returns `_`), 14 lookups twice. The four original predicates were not re-run |
| 9 | JavaParser | a missing `line.separator` gave initialization failure with a null-pointer cause, then erroneous-class use | Parent and fix: default, `LineSeparator` initializes; cleared, `ExceptionInInitializerError` (cause `NullPointerException`) then `NoClassDefFoundError` |
| 10 | Spring 480 | raw `Collection` vs `Collection<Optional<String>>`, distinct Long/String siblings | parent `Collection equal=false`, `String`, `Collection / Collection`; fix `Collection<Optional<String>> equal=true`, `String`, `Collection<Optional<Long>> / Collection<Optional<String>>` |

## What was not done, and why

- No signature check or keyring: the one download is a git commit fetched by SHA from a lightweight tag. Every other
  input was already in a cache and checked against its recorded digest; the earlier setups verified the signatures and
  publisher checksums of the released jars, and this session rechecked log4j-api's two jars against their `.sha1` files.
- No upstream build or test run, inline or as a job: the brief names none, and the deployments are the ones the earlier
  setups built and tested at the pins (landed-test results cited per case above). No offline build command was needed,
  so none was resolved or rechecked.
- No capture with `ObservedInitializer`, no native or JBMC run, no `build.py --change-plan`: the brief's stops are to be
  reproduced by the domain work through normal preparation, and those runs are its measurements. Avro's four-root
  capture, the ThreeTen and POI observed-native refusals and the Batik `getCSSParserClassName()` observation were
  therefore not re-run.
- `lib/tests/observed_countermodels.rs` (exercise 7) was not run: it is the domain work's test, and its cost is in
  `lib/tests/costs.json`.
- Batik 1.18's git source was not fetched: the brief names only 1.17, and the 1.18 `.orig` is in `$PANEL`.

## Setup Agent Notes

### What is ready, and where

- Every case's inputs are prepared and checked; the only new download is Batik's upstream source at `1_17`. Pins,
  digests and readers are in [Cases: inputs, pins and digests](#cases-inputs-pins-and-digests). In short:
  - Commons IO, ThreeTenBP, POI: `lib/benchmark/organic-composition/{io,threeten,poi}/{old,new}/prepared.json`, which
    point at `~/.cache/in-the-loop/organic-composition-ff/artifacts/{E-commons-io,A-threetenbp,B-poi}-{parent,fix}.jar`
    (POI adds six jars from `~/.cache/in-the-loop/organic-composition-ff/m2`, including log4j-api 2.26.1 and its
    sources jar). Source worktrees: `~/.cache/in-the-loop/organic-composition-ff/worktrees/{E-commons-io,A-threetenbp,B-poi}-{parent,fix}`.
  - Batik 1.17 → 1.18: `~/.cache/in-the-loop/beyond-jbmc/panel/evaluation/04/packet/{old,new}/NNN.jar` with
    `inputs.json`; upstream source at `~/.cache/in-the-loop/jvm-startup-facts/worktrees/batik-1_17` (commit
    `3c83de345f21cae4f4a64dfe6244483f87885808`), mirror `~/.cache/in-the-loop/git-mirrors/xmlgraphics-batik.git` (shallow).
  - Commons Configuration #565/#601: `callers.prepared_inputs(dir, [key])` in `lib/benchmark/receiver-discovery/callers.py`
    over `~/.cache/in-the-loop/receiver-construction/receivers/area/slices/commons-configuration-{565,601}`; sources in
    `~/.cache/in-the-loop/receiver-construction/src/configuration-{565,601}-{old,new}`.
  - Examples 355 (Avro, two 124-entry classpaths) and 360 (JavaParser): their captured builds restore wholly from the
    Maven cache ([table](#javaparser-4538-example-360-and-avro-3878-example-355-exercises-9-11)); 480 reads
    `runtime.json` against `~/.cache/in-the-loop/spring-pr-links-p01-p30`; 332 and the countermodel fixtures are in
    the repository.
- Source blob ids and class digests of the startup classes (`Charsets`, `Chronology`, `DateTimeFormatter`,
  `DataFormatter`, `XMLResourceDescriptor` and its properties, `ConfigurationInterpolator`, `LineSeparator`):
  [Startup classes](#startup-classes-source-blobs-and-class-digests).
- JDKs 8, 17, 21.0.13 and 25.0.5 with their `release` and `lib/modules` digests: [Tools](#tools). Every case except 480
  names JDK 21.0.13 (`~/.sdkman/candidates/java/21.0.13.0+9-tem`); 480 names 17. The default `java` on `PATH` is
  JDK 25: give the others by full path.
- `lib/target/release/jvmcontract`, sha256 `d0bcabc8fe2cc1af89d2e999c55bbc5995231a47fe8b8b3cfb91090ba8895258`, is
  current at `5f0b2389344879610f907ac9ee5b048dd59c9df8`. Rebuild it after changing `lib/src`.
- The scripts that reproduce each check in seconds are in `~/.cache/in-the-loop/jvm-startup-facts/scripts/`, with
  commands in [What was run on a JVM](#what-was-run-on-a-jvm).

### What was verified on a JVM

- The registered public observations, on the original deployments in fresh JVMs, equal the committed receipts: Commons
  IO 8/8, ThreeTenBP 12/12 (the New York and Berlin overlaps), POI 12/12 (`poi/physical.json`), Spring 480.
- **The 16 historical Commons IO charset trials reproduce byte for byte** (`verification/organic-composition/io/charset-profiles.json`):
  under `C` the defaulted constructor encodes `Aé中Z` with `3f3f`, the explicit one keeps `c3a9e4b8ad5a`.
- `"é".getBytes().length` on untouched JVMs: 2 under `C.UTF-8`; 1 under `C` with `-Dfile.encoding=COMPAT`; 2 under `C`
  without the flag. The same on JDK 21.0.13 and 25.0.5.
- Commons Configuration, all four deployments: own `_` gives `ExceptionInInitializerError` then `NoClassDefFoundError`;
  `_` inherited through a defaults table gives the 14 ordinary lookups twice. JavaParser, both sides: cleared
  `line.separator` gives `ExceptionInInitializerError` caused by `NullPointerException`, then `NoClassDefFoundError`.
- Batik's `XMLResourceDescriptor.java` and `.properties` at `1_17` have the same git blob ids as the Debian `.orig` and
  as the properties entry in both deployed jars that carry it.

### What to know before starting

- **Under `C` with `COMPAT`, `file.encoding` is not the canonical name**: it reads `ANSI_X3.4-1968` while
  `Charset.defaultCharset().name()` is `US-ASCII`. Without `-Dfile.encoding=COMPAT`, JDK 18+ selects UTF-8 under `C`,
  so the ASCII profile exists only with the flag.
- **Batik has two copies of `XMLResourceDescriptor` on each side**: 1.17 `old/000.jar` (batik-all) and `old/014.jar`
  (the util bundle, whose manifest says `Bundle-Version: 1.12.0`); 1.18 `new/000.jar` and `new/006.jar`. All four
  copies of the class and of the properties file are identical, and 1.17 and 1.18 are identical, so the selected copy
  follows classpath order, and changing the resource "at the same path" (exercise 4) has two candidate jars.
- The brief's `batik-1_17` link is a branch; the release tag `1_17` points at the same commit. The mirror is shallow
  (`--depth 1`): there is no history behind `3c83de345f21cae4f4a64dfe6244483f87885808`.
- In-repository anchors moved since the brief's review commit: the `--observed-initializer`/`--cache` refusal is at
  `lib/src/property.rs:302-304`, VF-054 at `verification/findings.md:485`; `change_evidence.py`, `recipes.py`,
  `UpgradeTrace.java` and `llm-dlc/runtime.md` grew. The observer, importer, reflection and JAR-resource sources are
  unchanged ([Starting commit](#starting-commit)).
- POI's classpath has log4j-api but no log4j-core: Log4j prints "could not find a logging provider" on stderr, which
  is harmless. The deployments are built `SNAPSHOT` jars at the pins (fixed bytes, digest-checked), not snapshot
  resolutions that can move.
- Configuration's sources in `~/.cache/in-the-loop/receiver-construction/src/` are exports, not git checkouts.
- **Keep the evaluator material apart** where the brief asks for automatic recovery: the historical observers and
  drivers (`lib/benchmark/organic-composition/*/UpgradeProbe.java`, `io/charset/`, `poi/StartupHistory.java`), their
  receipts, and `~/.cache/in-the-loop/jvm-startup-facts/probes/` and `logs/` hold callers and actual outcomes. The
  `DefaultBytes` and `TableModes` probes are this setup's checks, not product probes, and count as case-specific if used.
- No verification job was queued or is pending for this setup.

### What is left for the domain work on purpose

- Everything the brief asks to build or measure: the typed startup facts and receipts, the capture rules, admission
  checks and importer operations, the workflow integration, the cache keys, and the scorecard.
- Running normal preparation, `ObservedInitializer` captures, the native checker and JBMC on any case, including
  reproducing the original strict refusals (IO `Charsets.<clinit>`, ThreeTen `LOCALE_METHOD`, POI `DataFormatter.<clinit>`)
  and Avro's four-root profile.
- Observing Batik's `getCSSParserClassName()`, writing the labelled replaced-resource control and exercise 5's
  properties fixture, the exercise 6 whole-table consumer, the exercise 10 cached-`Method` control, and the
  perturbation, stale-receipt and interrupted-capture controls.
- Running `lib/tests/observed_countermodels.rs` and any new tests under the repository's tiers.
- Any new example ids or registrations.
