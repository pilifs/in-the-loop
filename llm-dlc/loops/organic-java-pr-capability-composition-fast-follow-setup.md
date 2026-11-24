# Setup for the organic Java PR capability-composition fast follow

Mechanical setup for [`organic-java-pr-capability-composition-fast-follow.md`](organic-java-pr-capability-composition-fast-follow.md),
done on 2026-11-24 by a setup session (Claude Opus 5.5) before the domain work starts. The session:
- fetched the 20 pinned upstream revisions of cases A–I (and the middle commit of Log4j #1173);
- built the production jars;
- ran each PR's landed test on both sides;
- resolved and checked the released versions the brief names;
- reproduced the brief's JVM preflight observations on the built jars.

It wrote no claims, examples, sidecars, adapters, observers, workflows, manifests, lemma declarations or checker code, and
allocated no example ids. It ran neither the project verifier nor JBMC on anything. The small Java programs under
`$O/probes/` only reproduce the brief's stated preflight observations: they are setup checks, not the case's caller artifacts.
Everything fetched or built is outside the checkout.

`$O` below is `~/.cache/in-the-loop/organic-composition-ff`, and `$M` is `~/.cache/in-the-loop/git-mirrors`. JDKs are Temurin,
under `~/.sdkman/candidates/java/`:
- `$J8` = `8.0.512.0+9-tem`
- `$J11` = `11.0.33.0+10-tem`
- `$J17` = `17.0.21.0+9-tem`
- `$J21` = `21.0.13.0+9-tem`

**The default `java` on `PATH` is JDK 25.0.5**, so name a JDK by its full path.

## Starting commit

- Checkout at setup: `da56af5745f8727ff505d9b98281408861371a57` ("Record the brief queue's handover"). It comes after
  the Beyond JBMC landing `4547213152` ("Merge the single-agent run beyond-jbmc-java-change-verification-cam into the line").
- The brief's planning baseline `96d1883e78d65f01507240f122108d8f1c668437` is an ancestor. The `lib/` trees differ:
  - at setup: `d7159867d97c4cd918cd73119d51094de9149d6d`;
  - at the baseline: `d08a6ab533d23456820af7004b8c9a6911b2a17d`.

  `git diff --stat 96d1883e HEAD -- lib/src examples/tools/targets lib/benchmark/domain-foundations` shows 34 files,
  1721 insertions and 265 deletions. Reading what changed is left to the domain work (the brief's "Starting point").
- The membership check against the predecessor's sealed panel, the exposure labels and the overlap with example 310
  are domain work. The setup did not look at any sealed material.

## Toolchain

| Tool | Where | Identity |
|---|---|---|
| Temurin 1.8.0_512-b09 | `$J8` | `jre/lib/rt.jar` sha256 `e699f968b854b98994148dac954cfb1fa78a0a7065d64e374a6d57fb463d5d5e` |
| Temurin 11.0.33+10 | `$J11` | `lib/modules` `c08aa45bcf1a51a18faeab078421519a2198a5ae272150e276add2ee28030fae` |
| Temurin 17.0.21+9 | `$J17` | `lib/modules` `fcdfc72acc1ec5e8542fc2170c587ef23edbbdeddcbf435f169d270e02469d7c` |
| Temurin 21.0.13+9 (the brief's preflight JDK) | `$J21` | `lib/modules` `a5fd7c311fbd96adcbd43757dbb94461e14df353b6ae9f5c029c45805a39782c` (the same as the earlier setups) |
| Maven 3.10.0 | on `PATH` (`~/.sdkman/candidates/maven/3.10.0`) | runs on JDK 8 too |
| Maven 3.8.4, Log4j's wrapper version | `$O/tools/apache-maven-3.8.4` | zip sha256 `ccd67d1ee4fd79339c9b6f95d1e5e1e0e0209a8c1b095d9291e009afa0a492a5`. Central `.sha1` matches (Central has no `.sha512` for it, 404). The `.asc` is a good signature by Michael Osipov `6A814B1F869C2BBEAB7CB7271A2A1C94BDE89688`; that key has since expired. |
| Gradle 9.8.1, POI's wrapper version | `$O/gradle-home/wrapper/dists/gradle-9.8.1-bin/a2l6ltp3k1vth6lwipzm5p2jp/gradle-9.8.1` | The distribution zip's sha256 `dce76f55f8e251a3a1f130eb120f30b3d271de2b76c9b0729d316b5a1b6dc01f` equals `services.gradle.org`'s `.sha256`. The tree the wrapper unpacked is identical (`diff -r`) to a separately downloaded and checked zip. POI's `gradle-wrapper.jar`, the same at both revisions, has `3b8a25775a69158b5ad2b1d17a80a88dc7b40a352a73eb27d06c612a7ce68e98` = the published `gradle-9.8.1-wrapper.jar.sha256`. |

Caches this work owns:
- `$O/m2` is the Maven local repository, named by `$O/maven-settings.xml`.
- `$O/gradle-home` is `GRADLE_USER_HOME`.
- `$O/toolchains.xml` is the Log4j toolchains layout with JDK 8 and 11 filled in.
- `$O/gnupg` is the keyring; its agent was stopped.

Every Maven command below takes `-s $O/maven-settings.xml`. The checkout's own `~/.m2` was not used.

## Upstream revisions

One bare, shallow mirror per upstream under `$M` holds only the pinned commits (`refs/pins/ROLE-SHA`). There is one
worktree per revision, `$O/worktrees/CASE-MIRROR-ROLE`. All the commits were fetched by SHA from the project's GitHub
repository; `$O/logs/pins-resolved.tsv` has each one's tree and parents. Each fix's recorded parent is the brief's
parent, except Log4j, whose change is two commits.

| Case | Worktree role | Commit | Tree | Note |
|---|---|---|---|---|
| A ThreeTenBP #77 | `A-threetenbp-parent` | `cc6cbd71d14e44633d3afdcd89afa096a8f1d145` | `2165f78f7c511c9464695f687088a387c05fc5a0` | 2018-01-11 "Update Travis build" |
| | `A-threetenbp-fix` | `f0865ac1e3f5d06822560f09bc9c59f5138fa16f` | `9264d219787d5c16872d67fd7be846ecef32b59a` | merge; parents `cc6cbd71…` (first) and `3136efa0cb7afba592d2f5d96e5a1c753073176f` (PR head) |
| B POI #1420 | `B-poi-parent` | `6b277ffc80c0f3876126781bcee12cb74d489ad2` | `8aa714fc3e1f72950c1d9e4e62c9db7605386460` | 2026-10-16 |
| | `B-poi-fix` | `bd15f5bc11c1433725d031642bdfaf64f4c2ce72` | `73b20382b7bb34b2bddcd4383b73ba10a2ee081e` | squash, parent `6b277ffc…` |
| C libphonenumber #2272 | `C-libphonenumber-parent` | `84dbe5ac9b559b6f4a1764ea9b914538131a39b9` | `296c9f52f42894f1578ca26ef5cc732ef022aba4` | 2018-10-18 |
| | `C-libphonenumber-fix` | `865da605da12b01053c4f053310bac7c5fbb7935` | `33b4b7b3c8211ee79e2ebd7e53a2b39256d320c2` | squash, parent `84dbe5ac…` |
| D ICU #3249 | `D-icu-parent` | `d868f13bd82ba4428574ce71937e09c9615dee47` | `d12309a7b7c2d8dc932ab67bbb59f266c1a7032b` | 2024-10-30 |
| | `D-icu-fix` | `8d86ca142e43d55017be8073d3671d6c5a114e1a` | `d779c4e67ddd19ab2ed1bb4ffe4f55dd5fe8e8ac` | "ICU-22941 Revert ICU-22112 …", parent `d868f13b…` |
| E Commons IO #520 | `E-commons-io-parent` | `dccc7011046542e9375b6a4f90b24ca02b01a890` | `8739971752b6f238f6ac2b78decdc501dee0e61c` | 2023-12-02 |
| | `E-commons-io-fix` | `3e7f57784c2fa8190fb3c75c977920ba6022de66` | `0e3c864e504db0ba773198c0254794cad2ac8fc4` | parent `dccc7011…` |
| F Collections #628 | `F-commons-collections-628-parent` | `ec38f6fa7f867000eed81791c3078b327a451d89` | `6d71c58be01e4c34c8713bee9c1ac7db290b1f58` | 2025-08-15 |
| | `F-commons-collections-628-fix` | `845c0e5400c5a804c972bdd9d60e6852f0c268f9` | `4926ed02a3a719cfcba33901b6aa417b0b5ff868` | parent `ec38f6fa…` |
| F Collections #755 | `F-commons-collections-755-parent` | `7f61af5216d13cba0d2fca45b59e8ed45734bc63` | `7020a3c4047b3548ff3371fcf5e59615ff4b138e` | 2026-11-11 |
| | `F-commons-collections-755-fix` | `ba6ea29fb48ee8dfb61e66ee209189a9c787486f` | `3b0d5f5bc97a2cc6272d139be1e0e4d7f866bc71` | parent `7f61af52…` |
| G Log4j #1173 | `G-logging-log4j2-parent` | `e325de9abf771a4501bae7cd7910fcbce31f5663` | `c2ace3b75ab10944e6f21c1de36a8c8a6f1e7492` | 2023-01-02 |
| | (mirror only) | `5bde96782efab839c2d6242b9d46401fee3fa211` | `593c567c74ccf67682eebb577640540d3cf2fc05` | first commit of the PR, parent `e325de9a…` |
| | `G-logging-log4j2-fix` | `7107cd655380d81dea72df930a832e598173971e` | `7b506a6963f271fd3897f41b30aa2a02869af9a5` | second commit, parent `5bde9678…`; the PR was merged as these two commits on `release-2.x` |
| H Commons Lang #1839 | `H-commons-lang-parent` | `390fe4027e331a77bc126d647fee3287c13827a6` | `6d0d9199343de64082123747da914aa0c94856c3` | 2026-10-24 |
| | `H-commons-lang-fix` | `f4bdd4e1d2c99cdab12e5177989fc11e1add33d5` | `0adabd64d8c542e134224e062df0926efb91ee8e` | parent `390fe402…` |
| I Gson #3098 | `I-gson-parent` | `61f2c646066e959f65cb99a826a2a759be42dbdd` | `20bae51799db928cc9940cbada907ebe1bf01356` | 2026-08-26 |
| | `I-gson-fix` | `b3f4ca20087f9066de4c340522ff84e0558e1ad1` | `929ed4f8f290afe0e99aebaf09ce226cfa3879e5` | parent `61f2c646…` |

GitHub shows no signature check here: the commits were taken by SHA, which is their own content hash. The diffstat of
each change is in `$O/logs/pr-diffstats.txt`. Each PR's metadata (title, body, head, merge commit) is in
`$O/upstream/prs/REPO-N.json`, from `gh api`. All ten are merged, and the merge commit of each equals the brief's fix
revision.

What the changes touch, in short (production files only):
- **A**: `DateTimeBuilder.java`.
- **B**: `CellNumberFormatter.java` and `DataFormatter.java`. Also a new test resource, `test-data/spreadsheet/bug70146.xlsx`.
- **C**: `AsYouTypeFormatter.java`. The production metadata is unchanged; only the test metadata `PhoneNumberMetadataProtoForTesting_US` changed.
- **D**: no Java production file. The ICU4J resources `brkitr/word.brk`, `word_POSIX.brk` and `res_index.res` changed, and
  `brkitr/fi.res`, `sv.res` and `word_fi_sv.brk` were removed. The rest is icu4c data and test data.
- **E**: `CharSequenceInputStream.java` (and a contributor line in `pom.xml`).
- **F #628**: `IteratorChain.java` and `UnmodifiableIterator.java`.
- **F #755**: `IteratorChain.java`.
- **G**: `PatternProcessor.java` and `DatePatternConverter.java`.
- **H**: `FastDateParser.java`. Two new private static methods, `isValidDayOfWeek(int)` and `toCalendarDayOfWeek(int)`, exist only on the fix.
- **I**: `JsonReader.java` and `internal/bind/JsonTreeReader.java`.

## Built jars and landed tests

Each build used its checkout's own build files, unchanged. For a transplant, the fix's test file (or test data) was
copied onto the parent, run, and restored with `git checkout`. Every worktree's build tree was removed afterwards
(`git clean -fdx`), so the worktrees are clean. Jars are in `$O/artifacts/`; their digests are in
`$O/logs/artifacts.sha256`. A jar's digest includes its build timestamp, so a rebuild gives another digest: bind the copy
in `$O/artifacts/`. The digests of the classes and resources inside are stable.

| Jar (`$O/artifacts/`) | sha256 | Version | Built with | Runtime dependencies (`$O/logs/WT.runtime-classpath.txt`) |
|---|---|---|---|---|
| `A-threetenbp-parent.jar` | `f2db710ef43a72dc7987b55f23b9397376f6fc6f090e335df721553dfc2d6ebc` | 1.3.6 | Maven 3.10.0, JDK 8 (class files major 50, target 1.6) | none |
| `A-threetenbp-fix.jar` | `568a09e20cecaec3c5df3e8bcaf3bd35809dc3e329992b7799956d35b535df89` | 1.3.6 | the same | none |
| `C-libphonenumber-parent.jar` | `e6a7af40675a1e87b7fa3675ce63afd80274c4c33c2a170be415e5ec3e952ee8` | 8.9.17-SNAPSHOT | Maven 3.10.0, JDK 8 (target 1.5) | none; the jar carries 254 `data/PhoneNumberMetadataProto_*` resources |
| `C-libphonenumber-fix.jar` | `feb25f9f743f84aaaf93843cdfd93065ccc82ed276693615c058efc59346b1d7` | 8.9.17-SNAPSHOT | the same | none |
| `E-commons-io-parent.jar` | `24718c09f6e0f7990a968e144be96042a20b97510b4dc611e1c97c3c3189e341` | 2.15.2-SNAPSHOT | Maven 3.10.0, JDK 17 (release 8) | none |
| `E-commons-io-fix.jar` | `48fc79897f329de108aa4452288c86be27f76c7146e33c38bfc345b5d7885dcc` | 2.15.2-SNAPSHOT | the same | none |
| `F-commons-collections-628-parent.jar` | `dff189f043780426b4fd144a1177867acd0eabc73c485d104807afac881bb934` | 4.6.0-SNAPSHOT | Maven 3.10.0, JDK 17 | commons-codec 1.19.0 |
| `F-commons-collections-628-fix.jar` | `c8d05a162b289beff2f3515d7d7cef4cd82bba44d74a1d5bc87f5b0e5e6552aa` | 4.6.0-SNAPSHOT | the same | commons-codec 1.19.0 |
| `F-commons-collections-755-parent.jar` | `c89596ea5a8d6e9816304c25e0cf7b348b2f471bf0dda4a46969ed37c6e85d42` | 4.6.1-SNAPSHOT | the same | commons-codec 1.23.0 |
| `F-commons-collections-755-fix.jar` | `9166502d0ad6013174dcf5018d9d1153b0cc2ce2d8920a99b26272597313c662` | 4.6.1-SNAPSHOT | the same | commons-codec 1.23.0 |
| `H-commons-lang-parent.jar` | `bebde4555f1cc520baab15d86d29df52d1fdc79623c2d9c027438e374e72d01a` | 3.21.1-SNAPSHOT | Maven 3.10.0, JDK 17 | none |
| `H-commons-lang-fix.jar` | `26166ddf56ce976033f286bfc1c30db63531c5dea80132de8040177f45bf4316` | 3.21.1-SNAPSHOT | the same | none |
| `I-gson-parent.jar` | `6f39446178fc99d6fa3e15c73a4c9b326f3f3915c1be810887b99ab11b32c9ae` | 2.14.1-SNAPSHOT | Maven 3.10.0, JDK 17 (release 8) | error_prone_annotations 2.50.0 |
| `I-gson-fix.jar` | `6dad830e7188de3bfcaf7da17664a1bf70cf845c92f7083d243fb599f2d15cf1` | 2.14.1-SNAPSHOT | the same | error_prone_annotations 2.50.0 |

B, D and G are built by verification jobs (below).

**Landed tests on a JVM** (logs in `$O/logs/WT.mvn-online.log`, `WT.mvn-offline.log` and `WT.transplanted-test.log`):

| Case | Test | Fix | Parent's own | Landed file on the parent |
|---|---|---|---|---|
| A | `TestZonedDateTime` | 515/515 pass | 503/503 pass | **fails**. Surefire reports "515 run, 6 failures" and its TestNG total "505, 2": `test_parseWithZoneAndOffsetToInstant` ×4 and `test_parseFormatRoundtripWithZoneAndOffset` ×2. For example, expected `2016-11-06T06:00:00Z` but found `2016-11-06T05:00:00Z`. |
| C | `AsYouTypeFormatterTest` | 33/33 pass | 33/33 pass | **passes, 33/33**. The PR changed no Java test, only the test metadata `PhoneNumberMetadataProtoForTesting_US`, and the parent passes with the fix's copy too. On the JVM, the landed Java test does not tell the two sides apart; the preflight probe below does. |
| E | `CharSequenceInputStreamTest` | 418/418 pass | 413 run, 2 skipped, 0 failures | **fails, 7 of 418**: `testMarkReset_RequiredCharsets` ×6 and `testResetBeforeEndSetCharSequence` |
| F #628 | `IteratorChainTest` | 25/25 pass | 21/21 pass | **passes, 25/25**. #628 is a performance fix (deep nesting), so its landed test does not separate the sides. |
| F #755 | `IteratorChain*Test` (4 classes) | 310/310 pass | `IteratorChainTest` 25/25 pass | **fails, 215 of 310**: Rechaining 118, Compatibility 56, Cycle 40, `IteratorChainTest` 1 |
| H | `FastDateParserTest` | 43842/43842 pass | 43798/43798 pass | **fails, 20 of 43842**: `testWeekYearParsingOutOfRangeDayOfWeek` ×18 and `testWeekYearParsingStrictDayOfWeek` ×2 |
| I | `MapTest`, `JsonReaderPathTest`, `JsonParserTest` (`-Dtest` also matches `com.google.gson.JsonParserTest`) | 106 run, 1 skipped, 0 failures | 103 run, 1 skipped, 0 failures | **fails, 7**: `promoteNameToValueUpdatesPath[STRING_READER]` and `[OBJECT_READER]`, `testExtraCommasInMaps`, `testMapDeserializationUnterminatedValueIncludesNameInPath`, and three `testMapDeserializationWithDuplicateKeys*` |

**Commands** (each takes under 40 s; the first run of each was online and filled `$O/m2`, and the parent runs and
transplants ran with `-o`, so the offline form works):

```bash
O=~/.cache/in-the-loop/organic-composition-ff; export TMPDIR=$O/tmp; W=$O/worktrees
SK="-Drat.skip -Djapicmp.skip -Danimal.sniffer.skip -Dcheckstyle.skip -Dspotbugs.skip -Dpmd.skip -Dcpd.skip -Djacoco.skip \
    -Dmaven.javadoc.skip -Dcyclonedx.skip -Dspdx.skip -Drevapi.skip -Dmaven.source.skip"
# A (JDK 8): jar in target/threetenbp-1.3.6.jar
cd $W/A-threetenbp-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem mvn -B -o -s $O/maven-settings.xml -Dtest=TestZonedDateTime package
# C (JDK 8): jar in java/libphonenumber/target/libphonenumber-8.9.17-SNAPSHOT.jar
cd $W/C-libphonenumber-fix/java && JAVA_HOME=$HOME/.sdkman/candidates/java/8.0.512.0+9-tem mvn -B -o -s $O/maven-settings.xml -pl libphonenumber -Dtest=AsYouTypeFormatterTest package
# E, F, H (JDK 17): jar in target/
cd $W/E-commons-io-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK -Dtest=CharSequenceInputStreamTest -Dsurefire.failIfNoSpecifiedTests=false package
cd $W/F-commons-collections-755-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK '-Dtest=IteratorChain*Test' -Dsurefire.failIfNoSpecifiedTests=false package
cd $W/H-commons-lang-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK -Dtest=FastDateParserTest -Dsurefire.failIfNoSpecifiedTests=false package
# I (JDK 17): jar in gson/target/gson-2.14.1-SNAPSHOT.jar
cd $W/I-gson-fix && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK -pl gson '-Dtest=MapTest,JsonReaderPathTest,JsonParserTest' -Dsurefire.failIfNoSpecifiedTests=false package
```

The `$SK` flags only skip report and lint plugins (rat, japicmp, javadoc and so on). They change nothing that is compiled.
The runtime classpaths above came from
`mvn -s $O/maven-settings.xml org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath -DincludeScope=runtime`.
That plugin version is resolved in `$O/m2`; ThreeTenBP's own pinned `maven-dependency-plugin` 2.10 is not, so name 3.8.1 for an offline call.

## Released versions the brief names

Resolved from Maven Central with `mvn --strict-checksums` into `$O/m2`, one throwaway POM per graph
(`$O/scripts/resolve.sh`, `$O/scripts/graphs.tsv`). Each `$O/releases/NAME/` holds:
- `lib/` (the runtime jars, hard links into `$O/m2`);
- `sources/`;
- `tree.txt`;
- `classpath.txt` (ordered).

Every main jar's `.sha1` matches. Every `.asc` was checked in `$O/gnupg` with keys from keyserver.ubuntu.com: **14/14
`GOODSIG`** (`$O/scripts/sig_check.sh`, `$O/logs/release-signatures.tsv`).

| Release (`$O/releases/…`) | Jar | sha256 | Signer (fingerprint) |
|---|---|---|---|
| `poi-6.0.0` | `poi-6.0.0.jar` | `4977f1ae04e1c77e42c81dd94cca008e0d81ff8d0daa8b85e2a0740c3c1da3cc` | PJ Fanning `6BA4DA8B1C88A49428A29C3D0C69C1EF41181E13` |
| | `commons-codec-1.23.0.jar` | `47504a3ce71d73a1b0af07675546b8d8c5af87f82ef12b6381f9eb3c17dd5a5b` | Gary Gregory `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` |
| | `commons-collections4-4.6.0.jar` | `4e0d0896bac5356cead277bac0283f09813e14417e3e84e0c86b573b54d218a3` | Gary Gregory `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` |
| | `commons-math3-3.6.1.jar` | `1e56d7b058d28b65abd256b8458e3885b674c1d588fa43cd7d1cbb9c7ef2b308` | Evan Ward `41A1A08C62FCA78B79D3081164A16FAAEC16A4BE` |
| | `commons-io-2.22.0.jar` | `2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758` | Gary Gregory `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` |
| | `SparseBitSet-1.3.jar` | `f76b85adb0c00721ae267b7cfde4da7f71d3121cc2160c9fc00c0c89f8c53c8a` | Brett Wooldridge `F3A90E6B10E809F851AB4FC54CC08E7F47C3EC76` |
| | `log4j-api-2.26.1.jar` | `f1810a4704ccce019d02bba029dc02a4f2ac0c997f647b465e7d409c1927f822` | ASF Logging Services RM `077E8893A6DCC33DD4A4D5B256E73BA9A0B592D0` |
| `icu4j-76.1` | `icu4j-76.1.jar` | `732cdf18121b1642899da1f5e37e52cc7f48e3ec07fa737105d4603976781b33` | ICU Release Robot `E52F07877A5805F9AF4AB0ACD46C5610D06E7001` |
| `commons-collections4-4.6.0` | `commons-collections4-4.6.0.jar` | `4e0d0896bac5356cead277bac0283f09813e14417e3e84e0c86b573b54d218a3` | Gary Gregory `F4DD59C90148BDC52BEB90A4530AA5F25C25011F` |
| `log4j-2.19.0` | `log4j-core-2.19.0.jar` | `b4a1796fab7bfc36df015c1b4052459147997e8d215a7199d71d05f9e747e4f4` | Ralph Goers `53C935821AA6A755BD337DB53595395EB3D8E1BA` |
| | `log4j-api-2.19.0.jar` | `5ccb24ad9f92e768d0bc456d3061a737951262df803e004d2cad096b75a88d60` | Ralph Goers `53C935821AA6A755BD337DB53595395EB3D8E1BA` |
| `log4j-2.20.0` | `log4j-core-2.20.0.jar` | `6137df848cdaed9f4d5076f75513c6c85da80b953f4e7acca38098b770763f55` | Ralph Goers `53C935821AA6A755BD337DB53595395EB3D8E1BA` |
| | `log4j-api-2.20.0.jar` | `2f43eea679ea66f14ca0f13fec2a8600ac124f5a5231dcb4df8393eddcb97550` | Ralph Goers `53C935821AA6A755BD337DB53595395EB3D8E1BA` |
| `gson-2.14.0` | `gson-2.14.0.jar` | `2cbd119bf1961c28788310963dc80ba65f58cdeec1dd139c8bdb1240faa2c36f` | Éamonn McManus `C7BE5BCC9FEC15518CFDA882B0F3710FA64900E7` |
| | `error_prone_annotations-2.48.0.jar` | `b49c5c958316ed67a09c699dda9aa749caf434d51d863dea599ef36a49b9c855` | Liam Miller-Cushon `EE0CA873074092F806F59B65D364ABAA39A47320` |

POI's own build resolves exactly this runtime graph for `:poi` at both revisions
(`$O/logs/B-poi-*.poi.runtimeClasspath.txt`). The six dependency jars in `$O/gradle-home` have the same sha256 as those
in `releases/poi-6.0.0/lib/`.

## The brief's preflights, reproduced on a JVM

The probes are in `$O/probes/X/`, compiled per jar into `out-JAR/`. Their output is in `$O/logs/X-probe*.txt`. Every
run on a built jar was repeated on JDK 21.0.13 with identical output (`$O/logs/probes-jdk21.txt`).

**A, ThreeTenBP** (`OverlapProbe`, JDK 8 and 21). The formatter was built with
`new DateTimeFormatterBuilder().append(ISO_ZONED_DATE_TIME).toFormatter(Locale.ROOT).withResolverStyle(STRICT)`. One
`ParsePosition` read the two New York texts concatenated, then a third time at the end:

| | 1st | 2nd | 3rd (end of input) |
|---|---|---|---|
| parent NY | `2016-11-06T05:00:00Z`, index 40 | `2016-11-06T05:00:00Z`, index 80 | `DateTimeParseException`, index 80, error index 80 |
| fix NY | `2016-11-06T05:00:00Z`, index 40 | `2016-11-06T06:00:00Z`, index 80 | the same |
| parent Berlin | `2016-10-30T00:00:00Z`, index 37 | `2016-10-30T00:00:00Z`, index 74 | exception, index 74, error index 74 |
| fix Berlin | `2016-10-30T00:00:00Z`, index 37 | `2016-10-30T01:00:00Z`, index 74 | the same |

`ISO_ZONED_DATE_TIME` used directly gives the same results. This is the brief's statement exactly.

Bound identities, all from the jars:
- `org/threeten/bp/TZDB.dat` is `24d8db6ab7b32af2bd8df1ab1cc42b3c3058251cd4055bbee1fe51c55e2cbc77` in both jars, the same as
  `src/main/resources` at both revisions.
- `META-INF/services/org.threeten.bp.zone.ZoneRulesProvider` is `d6a572c1a9f9d61765f4e020f2fa15836dd5a0072f677eb48b47a01cba6bc275`
  in both. It names `org.threeten.bp.zone.TzdbZoneRulesProvider`.
- `Jdk8Methods.class` is `849cc80bef83b3281ff352a50e2a31553d3c014319745995a012c6f5ec5c9fee` in both. It holds
  `public static int floorMod(long, int)` with descriptor `(JI)I`.
- `DateTimeFormatter.class` is `a810b97bba10e91c8d9caea5b6d61091aa2a9874a686ef19a22d44aef5d5a2db` in both.
- `DateTimeBuilder.class`: parent `8d79cec145e05b8d9f95efbb815472019f68d9cbabf520eef584b5228fdff08c`,
  fix `ecd2ccb7bab26378811bd76dc0baef26a227610c074dbfa587a11b9ddd620487`.

**C, libphonenumber** (`AsYouTypeProbe`, JDK 8 and 21, the production metadata in the jar).

Swedish `08123456`, typed one digit at a time:
- parent: `0 | 08 | 081 | 08 12 | 08 123 | 08 123 4 | 08 123 45 | 08 12 34 56`
- fix: `0 | 08 | 081 | 08-12 | 08-123 | 08-123 4 | 08-123 45 | 08-12 34 56`

`inputDigitAndRememberPosition` on the 4th digit gives a remembered position of 5 on both sides. `clear()` followed by a
replay on the same receiver repeats the history exactly. US `6502530000` gives the same history on both sides, ending
`(650) 253-0000`, remembered 7.

Every supported region × `PhoneNumberType` example number, typed in its national-format digits, gives **1,326 histories**.
**25 differ** between the sides, which is the brief's count:
- BR PREMIUM_RATE;
- CO TOLL_FREE and PREMIUM_RATE;
- EC FIXED_LINE, FIXED_LINE_OR_MOBILE and VOIP;
- KZ FIXED_LINE, MOBILE, FIXED_LINE_OR_MOBILE and VOIP;
- RU FIXED_LINE, MOBILE and FIXED_LINE_OR_MOBILE;
- all nine of SE's types;
- ZM FIXED_LINE, FIXED_LINE_OR_MOBILE and TOLL_FREE.

The input and every prefix are in `$O/logs/C-libphonenumber-{parent,fix}.probe-all.txt`.

The metadata resources are the same in both jars:
- `data/PhoneNumberMetadataProto_SE`: `46db5145d11130b01df0cdf653646c1cccfc78461c787a258a6da6589d25a667`
- `data/PhoneNumberMetadataProto_EC`: `74d3fc74bd1ffe87d0fd33bcd9f102d7e60312753758d3485ac5b821c2689fe5`
- `data/PhoneNumberMetadataProto_US`: `edece0eebcbfdd587ed984c939e8b012ce8337179e9008b89539c8534503f523`
- `MetadataManager.class`: `ae4c4a69875be6392fa6018b045d5e3384765bf01273cee753fae3b34800db9e`

`AsYouTypeFormatter.class` is parent `155bc3bdf9646c00ddb8304fbfe92a94019615dec9a51f7afc6538b63bd532a4` and fix
`cd36ff903e81bb36d6b88f1a574bd76f1fa8b834aea1c19cf705279b1ade8e3e`.

**E, Commons IO** (`MarkResetProbe`, JDK 17 and 21). The stream is `new CharSequenceInputStream("Aé中Z", UTF_8, 8)`. It
reads one byte (65), calls `mark(100)`, then three times reads `read(dst, 1, 3)` into a 5-byte array guarded by 0x7f and
calls `reset()`:
- parent: `c3a9e4 / c3a9e4 / b8ad5a`
- fix: `c3a9e4 / c3a9e4 / c3a9e4`

Every read returns 3, and the guard bytes are untouched. This is the brief's statement.

**F, Commons Collections** (`ChainProbe`, JDK 17 and 21). The child chain is over `[a,b,c]` and is advanced once (`a`).
The parent is `IteratorChain(child, [d,e])`.

| Jar | `parent.next()` | `remove()` | the rest | backing list |
|---|---|---|---|---|
| 628-parent, 755-fix | `b` | ok | `[c, d, e]` | `[a, c]` |
| 628-fix, 755-parent, and the **4.6.0 release** | `d` | `UnsupportedOperationException` | `[e]` | `[a, b, c]` |

A flat chain gives `[a, b, c]` at all four endpoints. This is the brief's statement. The 4.6.0 release behaves like the
regressed endpoints.

**G, Log4j** (`RolloverProbe` on the **release** jars 2.19.0 and 2.20.0, JDK 17 and 21, each run in a fresh JVM). The
probe calls `new PatternProcessor(pattern)`, then `getNextTime(2014-03-04T10:00Z, 1, false)`, then `updateTime()`:

| Default zone | Pattern | 2.19.0 next | 2.20.0 next |
|---|---|---|---|
| GMT+10 | `logs/app-%d{yyyy-MM-dd}{GMT-6}.log.gz` | `2014-03-04T14:00:00Z` | `2014-03-05T06:00:00Z` |
| GMT-10 | the same | `2014-03-05T10:00:00Z` | `2014-03-05T06:00:00Z` |
| GMT+10 | `logs/app-%d{yyyy-MM-dd}.log.gz` (zone omitted) | `2014-03-04T14:00:00Z` | `2014-03-04T14:00:00Z` |
| GMT-10 | the same | `2014-03-05T10:00:00Z` | `2014-03-05T10:00:00Z` |

`getPrevFileTime()` after `updateTime()` equals the recorded `getNextFileTime()` in every row (in `$O/logs/G-probe-releases.txt`).
This is the brief's statement. The same probe on the jars built at the PR revisions waits for the Log4j job.

**H, Commons Lang** (`WeekProbe`, JDK 17 and 21). The probe calls
`FastDateFormat.getInstance("YYYY-'W'ww-u", UTC, locale).parse("2025-W01-D", pos, calendar)`, with the calendar's
leniency set. There are 16 combinations (US and Germany × strict and lenient × D = 0, 7, 8, 15):
- **lenient 8**: the parent throws `IllegalArgumentException`; the fix returns `1736121600000` in both locales.
- **strict 0**: accepted on the parent (US `1735430400000`, DE `1736035200000`), rejected on the fix (`IllegalArgumentException`).
- **strict 15**: rejected on both.
- **7**: the same on both (US `1735430400000`, DE `1736035200000`).
- **lenient 0 and 15**: the parent accepts 0 and throws on 15; the fix accepts both (US 0 → `1734825600000`, 15 → `1736726400000`).

After an exception the cursor index is 10 (11 for "15") with error index −1 on both sides; the calendar is not checked
after failure. Full table: `$O/logs/H-probe.txt`. It agrees with the brief.

**I, Gson** (`PathProbe`, JDK 17 and 21). A `String` adapter registered through `GsonBuilder` records `getPath()`
before reading each value and `getPreviousPath()` after it. The input is `{"1":"x","2":"y"}` into
`Map<Integer,String>`, through `fromJson(String)` and through `fromJson(JsonElement)`:
- parent and the **2.14.0 release**: `$., $., $., $.` on both readers.
- fix: `$.1, $.1, $.2, $.2` on both readers.

The maps are equal (`{1=x, 2=y}`). This is the brief's statement.

**D, ICU4J** (`WordProbe` on the **76.1 release**, JDK 21). `BreakIterator.getWordInstance(ULocale)` with
`setText("xx:yy")`, forward then backward, then `setText` with `𐐀:𐐨` on the same receiver; boundaries are listed as
offset:status:

| Locale | forward `xx:yy` | reverse | supplementary |
|---|---|---|---|
| en_US | `0:0, 2:200, 3:0, 5:200` | the reverse of forward | the same boundaries |
| fi, sv | `0:0, 5:200` | the reverse of forward | the same boundaries |
| en_US_POSIX | `0:0, 2:200, 3:0, 5:200` | the reverse of forward | the same boundaries |

So 76.1 has the `[0,2,3,5]` en_US rules.

The same probe on the **built** core jars (JDK 21, `$O/logs/D-probe.txt`):

| Locale | parent `xx:yy` forward | fix `xx:yy` forward |
|---|---|---|
| en_US | `0:0, 2:200, 3:0, 5:200` | **`0:0, 5:200`** |
| fi, sv | `0:0, 5:200` | `0:0, 5:200` |
| en_US_POSIX | `0:0, 2:200, 3:0, 5:200` | `0:0, 2:200, 3:0, 5:200` |

The reverse walk mirrors the forward one, and the supplementary text `𐐀:𐐨` gives the same boundaries as `xx:yy` in
every row. This is the brief's statement. The 76.1 release behaves like the parent.

Rule resources in the jars (sha256; `—` = absent). The prefix is `com/ibm/icu/impl/data/icudata/brkitr/`:

| Resource | parent core jar | fix core jar | icu4j 76.1 release |
|---|---|---|---|
| `word.brk` | `6791a9e07e1676903c1f7984a90bf995b3d639d2300610bc903cdf848e682edf` | `e7e505439ca75fd34cb1fc584142a5c4ee7d1e60dbd73925ced84565bcb66d9c` | = parent |
| `word_POSIX.brk` | `f6dbac854a96f028f0a29e352a0d118aa0a86559aa81f69fe0dc1eb054213d94` | `a43297bfabc9a1a4fa39c296f92c3d7784254696af862b4e08f833f787954dfe` | = parent |
| `word_fi_sv.brk` | `e7e505439ca75fd34cb1fc584142a5c4ee7d1e60dbd73925ced84565bcb66d9c` | — | = parent |
| `fi.res` | `d2c33190f4461737a9e92ea1f239d8c198f40ef291a5705b1eff75a03e420865` | — | = parent |
| `sv.res` | `d2c33190f4461737a9e92ea1f239d8c198f40ef291a5705b1eff75a03e420865` | — | = parent |
| `res_index.res` | `5e9e613dd7d55768676c49b8b7fc04b2acea95e4a41f44a104cec9938f2c14f0` | `55b1b0b6ed0f7dab68429548fef0e29af2ed1195c159d65efc400de5b890595a` | = parent |

**The fix's `word.brk` is byte-identical to the parent's `word_fi_sv.brk`.** The revert made the root rules equal to
what Finnish and Swedish had. On the fix, fi and sv have no `.res` of their own and fall back to root. The jar
resources equal the committed files in `icu4j/main/core/src/main/resources/` (checked for `word.brk` at both
revisions). `com/ibm/icu/text/UTF16.class` is `0cba408d08acb711264a661fb94bbe24a8fbb33a400d3a465c77c1722de1a0bb` in both
core jars, with `public static boolean isTrailSurrogate(int)`, descriptor `(I)Z`.

## Jobs

The jobs were written by `$O/scripts/submit_jobs.py` and committed with this record:

| Job | Subject | Status |
|---|---|---|
| `20261124-134447-setup-build-apache-poi-s-poi-module-at-b` | B: `:poi:jar` at both revisions; `TestDataFormatter`, own and transplanted | **failed** at step 1 after 13.9 s. `:poi:jar` built (BUILD SUCCESSFUL), but the step looked for the jar in `poi/build/libs/`, and POI writes it to `build/dist/maven/poi/`. This was the setup script's mistake; the result was collected on another line (`7fcd18cc09e4`). |
| `20261124-135600-setup-build-apache-poi-s-poi-module-at-b` | B: the same, jar path fixed | **passed**, 4/4 steps in 1m00s, peak 1.5 GiB (collected in `2405aab9d751`) |
| `20261124-134447-setup-build-icu4j-core-at-both-3249-revi` | D: ICU4J `main/core` at both revisions; RBBI tests, own and transplanted | **passed**, 5/5 steps in 1m57s, peak 1.6 GiB (collected in `08e02797e4`) |
| `20261124-134447-setup-build-log4j-core-at-both-1173-revi` | G: `log4j-core-test -am` at both revisions; `PatternProcessorTest`, own and transplanted | **failed** at step 1 after 36.5 s. `log4j-api` unpacks `log4j-api-java9:zip:2.19.1-SNAPSHOT`, and `-am` from `log4j-core-test` does not bring that module into the reactor, so Maven looked for the zip on `repository.apache.org/snapshots` and did not find it. Again the setup's mistake. Inline, `-pl log4j-api-java9,log4j-api -DskipTests package` then built in 6 s. |
| `20261124-140027-setup-build-log4j-core-at-both-1173-revi` | G: the same with `-pl log4j-api-java9,log4j-core-java9,log4j-core-test -am`, `package` in every step | **failed** at step 1 after 22.6 s: with Maven on JDK 11, `log4j-api-test` does not compile (`StackLocatorUtilTest` imports `sun.reflect.Reflection`). Upstream CI runs Maven on JDK 8 with toolchain 11 (`.github/workflows/build.yml`). Inline, `-pl log4j-api-java9,log4j-api,log4j-api-test -DskipTests package` on JDK 8 then built. |
| `20261124-141323-setup-build-log4j-core-at-both-1173-revi` | G: the same, Maven running on JDK 8 | pending |

**B, POI** (job `20261124-135600-setup-build-apache-poi-s-poi-module-at-b`). Gradle 9.8.1 ran `--offline` on JDK 17;
`TestDataFormatter` gives:

| Step | Result |
|---|---|
| fix | 59 run, 2 skipped, 0 failures |
| parent's own | 57 run, 2 skipped, 0 failures |
| landed file on the parent | **2 fail**: `testCurrencyStringWithoutLanguageInfo()` and `testFormatWithSpecialCharactersInLiteral()` |

Jars (`build/dist/maven/poi/poi-6.0.0-SNAPSHOT.jar`):
- `$O/artifacts/B-poi-parent.jar`: `6e43938a40a3bafd59ba6bcc89f03a89a9f4c54520f08c3d8481d5dc1e7502a5`
- `$O/artifacts/B-poi-fix.jar`: `3bb5a6d4840677d91125456f35afab47e2b2a904ac8dc3c730d704957852d5fa`

The runtime classpath is the `releases/poi-6.0.0` graph without `poi-6.0.0.jar`. Logs: `$O/logs/B-poi-*.poi.*`. The
offline command:

```bash
cd $O/worktrees/B-poi-fix && GRADLE_USER_HOME=$O/gradle-home JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem ./gradlew --no-daemon --offline \
  -Porg.gradle.java.installations.auto-download=false -Porg.gradle.java.installations.paths=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem \
  :poi:jar :poi:test --tests 'org.apache.poi.ss.usermodel.TestDataFormatter'
```

Class digests:

| Class | parent | fix |
|---|---|---|
| `DataFormatter` | `e4982b2ac7ccc06340120f75213b02bd1fcfc2f2d140a425c4fae1c72e18e25c` | `54883f8d266126d89bbc94028fa50f86c2b648af67991a14abf59bd92181a951` |
| `CellNumberFormatter` | `00797a9d7aeff192ab40b9b9c5804340df6a41f19cf14fc21f6d0b45dc9a3fbb` | `63776b2d54df49c081b30ea940bc5bc796e7df6e5cfe1952b09f3f0941085829` |
| `DateUtil` | `c337b84d54b4f3f6b30936790e0f90d4dfc22af4660a8b9f5014c291b1ea4f13` | the same |
| `LocaleUtil` | `ae941c3c1da68e92c5ac6bbc5e6cf34dc523aee8f7e33768b11331cfda903b81` | the same |

`DateUtil.isInternalDateFormat(int)` has descriptor `(I)Z`.

**B preflight** (`LocaleProbe`, JDK 21, the built jars over the 6.0.0 dependencies; `$O/logs/B-probe.txt`). The probe uses
`formatRawCellContents(0.001, -1, "#,##0.000000000\"тг.\"")` on one `new DataFormatter()`, through
`LocaleUtil.setUserLocale` US → kk-KZ → US:
- parent: `0.001 / 0,001 / 0.001`
- fix: `0.001000000тг. / 0,001000000тг. / 0.001000000тг.`

A fresh peer at each stage gives the same output. The control `0.0` gives `0.0 / 0,0 / 0.0` on both sides. A fresh
process that sets kk-KZ before constructing the formatter gives `0,001` on the parent and `0,001000000тг.` on the fix.
This is the brief's statement. Log4j API prints "could not find a logging provider" on stderr, because no log4j-core is
on the classpath; it is harmless.

**D, ICU4J** (job `20261124-134447-setup-build-icu4j-core-at-both-3249-revi`). It ran Maven 3.10.0 on JDK 17 with
`-pl main/core -am` (framework and core); `-Dtest=RBBITestExtended,RBBIMonkeyTest,RBBITestMonkey,RBBITest,RBBIAPITest,BreakIteratorTest`
gives 61 tests.

| Step | Result |
|---|---|
| fix, online build and the landed tests | 61/61 pass |
| parent's own | 61/61 pass |
| landed test files on the parent (`RBBITestMonkey.java`, `break_rules/word.txt`, `word_POSIX.txt`, `rbbitst.txt`) | **4 fail**: `RBBIMonkeyTest#TestMonkey`, `RBBITestExtended#TestExtended`, `RBBITestMonkey#TestWordMonkey`, `RBBITestMonkey#TestRTWordMonkey` |
| fix, offline | 61/61 pass |

Core jars:
- `$O/artifacts/D-icu-parent-core.jar`: `47235ad8dfd1d3f44736174dac8509d1267d3b87ec01ab1ede1dc69bfadd73b2`
- `$O/artifacts/D-icu-fix-core.jar`: `45f175800c28882b34223896697afb5050669f22a64d4989ba06d2f287037f7a`

Both are version 76.1-SNAPSHOT. The core module has no runtime dependencies. Logs: `$O/logs/D-icu-*.rbbi.*`. The
offline command:

```bash
cd $O/worktrees/D-icu-fix/icu4j && JAVA_HOME=$HOME/.sdkman/candidates/java/17.0.21.0+9-tem mvn -B -o -s $O/maven-settings.xml $SK \
  -Dbnd.baseline.skip -Dsurefire.failIfNoSpecifiedTests=false -pl main/core -am \
  '-Dtest=RBBITestExtended,RBBIMonkeyTest,RBBITestMonkey,RBBITest,RBBIAPITest,BreakIteratorTest' package   # jar: main/core/target/core-76.1-SNAPSHOT.jar
```

POI's `:poi` configurations were all resolved online before its job ran: an init script in the cache folder,
`$O/scripts/resolve-all.init.gradle`, provides the task `:poi:setupResolveAll`, and nothing in the checkout was changed.
`:poi:dependencies --offline` then worked at both revisions. The ICU and Log4j jobs resolve online in their first step
and run the rest offline.

**Disk** after setup: `$O` holds 2.4 GB, mostly the 20 worktrees (POI and ICU are the large ones). `$O/m2` is 566 MB
and `$O/gradle-home` 393 MB. The mirrors add about 240 MB, of which POI is 128 MB and ICU 64 MB.

**Checker.** `lib/target/release/jvmcontract` at setup is up to date with the checkout (`cargo build --release --bin
jvmcontract` had nothing to do). Its sha256 is `a03d514a66aa6931f0c7770db673f24eb6b4f93ef592a48844d8637ef9eadf46`, at
`lib/` tree `d7159867d97c4cd918cd73119d51094de9149d6d`. Freezing and recording the checker is the domain work's step 2.

## Setup Agent Notes

### What is ready, and where

- **Cache folder** `~/.cache/in-the-loop/organic-composition-ff` (`$O`). Everything is outside the checkout.
  - Worktrees: `$O/worktrees/CASE-REPO-ROLE`, one per pinned revision, all clean (no build trees).
  - Mirrors: one shallow bare mirror per upstream under `~/.cache/in-the-loop/git-mirrors/`.
  - Revisions with trees and parents: the [Upstream revisions](#upstream-revisions) table.
  - PR metadata (title, body, head, merge commit): `$O/upstream/prs/REPO-N.json`.
- **Built production jars**, both sides of every case: `$O/artifacts/`, digests in `$O/logs/artifacts.sha256` and the
  [Built jars](#built-jars-and-landed-tests) table.
  - A ThreeTenBP 1.3.6: `A-threetenbp-{parent,fix}.jar`.
  - C libphonenumber: `C-libphonenumber-{parent,fix}.jar`, with the production metadata inside.
  - D ICU4J core: `D-icu-{parent,fix}-core.jar`.
  - E Commons IO: `E-commons-io-{parent,fix}.jar`.
  - F Commons Collections, four endpoints: `F-commons-collections-{628,755}-{parent,fix}.jar`.
  - H Commons Lang: `H-commons-lang-{parent,fix}.jar`.
  - I Gson: `I-gson-{parent,fix}.jar`.
  - B POI 6.0.0-SNAPSHOT: `B-poi-{parent,fix}.jar`.
  - G Log4j: `G-logging-log4j2-{parent,fix}-log4j-{api,core}.jar` come from job
    `20261124-141323-setup-build-log4j-core-at-both-1173-revi` (see [Jobs](#jobs) for its state). Until then, the
    2.19.0 and 2.20.0 release jars stand in.
- **Runtime classpaths**: `$O/logs/WT.runtime-classpath.txt`.
  - Most built jars need nothing else.
  - Collections needs commons-codec (1.19.0 for #628, 1.23.0 for #755).
  - Gson needs error_prone_annotations 2.50.0.
  - POI `:poi` needs the `releases/poi-6.0.0` graph minus `poi-6.0.0.jar` (the same jars, checked by sha256).
- **Released versions the brief names**, all checked against Central with good PGP signatures:
  - `$O/releases/{poi-6.0.0,icu4j-76.1,commons-collections4-4.6.0,log4j-2.19.0,log4j-2.20.0,gson-2.14.0}/`, each with
    `lib/`, `sources/` and an ordered `classpath.txt`.
- **Toolchain**:
  - JDKs 8, 11, 17 and 21 under `~/.sdkman/candidates/java/`;
  - Maven 3.10.0 on `PATH`;
  - Maven 3.8.4 for Log4j in `$O/tools/`, with `$O/toolchains.xml`;
  - Gradle 9.8.1 for POI in `$O/gradle-home`.
  - Maven builds use `-s $O/maven-settings.xml`. Every Maven build here works with `-o`, and POI's with `--offline`.
- **Build and test commands** per checkout, with the offline form: [Commands](#built-jars-and-landed-tests), the ICU command in
  [Jobs](#jobs), and the job steps in `verification/jobs/2026/11/24/*setup-build*.json`, written by `$O/scripts/submit_jobs.py`.
- **Setup probes** that reproduce each preflight: `$O/probes/{A..I}/*.java`, with their output in `$O/logs/*-probe*.txt`.
  They are throwaway checks, not case artifacts.

### What was verified on a JVM

- **Landed upstream tests** (fix / parent / landed test transplanted onto the parent):
  - A, `TestZonedDateTime`: pass / pass / **6 failures**, the overlap tests.
  - B, `TestDataFormatter`: pass / pass / **2 failures** (`testCurrencyStringWithoutLanguageInfo`, `testFormatWithSpecialCharactersInLiteral`).
  - D, RBBI (61 tests): pass / pass / **4 failures**, the word monkeys and `TestExtended`.
  - E, `CharSequenceInputStreamTest`: pass / pass / **7 failures**.
  - F #755, 4 `IteratorChain*Test` classes: pass / pass / **215 failures**.
  - H, `FastDateParserTest`: pass / pass / **20 failures**.
  - I, `MapTest`/`JsonReaderPathTest`/`JsonParserTest`: pass / pass / **7 failures**.
  - **C and F #628 pass on both sides even with the landed test**: C changed only test metadata, and #628 is a
    performance fix. For them, the probes below are the discriminators.
  - G (`PatternProcessorTest`) is in the pending job.
- **The brief's preflight observations, reproduced as stated** on the built jars, identical on JDK 21.0.13:
  - **A**: NY cursor 40 → 80, with the parent `05:00Z` twice and the fix `05:00Z`/`06:00Z`. Berlin 37 → 74, with
    `00:00Z` twice versus `00:00Z`/`01:00Z`. The read at end of input throws with error index = index. The builder
    formatter and `ISO_ZONED_DATE_TIME` agree.
  - **B**: US → kk-KZ → US gives `0.001 / 0,001 / 0.001` on the parent and `0.001000000тг. / 0,001000000тг. /
    0.001000000тг.` on the fix. A fresh peer gives the same. The `0.0` control is preserved. A process that starts in
    kk-KZ already differs.
  - **C**: Swedish `08123456` ends `08 12 34 56` on the parent and `08-12 34 56` on the fix. Clear and replay repeat
    the history. US is preserved. **25 of 1,326** region × type example histories change, listed in the record.
  - **D**: en_US `xx:yy` goes from `[0,2,3,5]` to `[0,5]`; fi and sv stay at `[0,5]`; en_US_POSIX stays at `[0,2,3,5]`.
    The reverse walk and the supplementary `𐐀:𐐨` agree.
  - **E**: the parent gives `c3a9e4 / c3a9e4 / b8ad5a`, the fix `c3a9e4` ×3; guards untouched.
  - **F**: the parent returns `b` and removes it at 628-parent and 755-fix; it returns `d` and throws on `remove` at
    628-fix and 755-parent. A flat chain is the same at all four.
  - **G** (release jars 2.19.0 and 2.20.0): the explicit GMT−6 zone gives 06:00Z on March 5, 2014 under both defaults
    on 2.20.0 and two different deadlines on 2.19.0. With the zone omitted, the old deadlines stay on both.
  - **H**: lenient day 8 throws on the parent and gives `1736121600000` on the fix. Strict 0 goes from accepted to
    rejected. Strict 15 is rejected on both. 7 is the same.
  - **I**: the parent reports `$.` ×4 on both readers; the fix reports `$.1, $.1, $.2, $.2`. The maps are equal.
- Every release jar's sha1 and signature, both build tools' distributions and wrapper jar, and the commit and tree of each
  pinned revision.

### What to know before starting

- **The default `java` is JDK 25.0.5.** Name the JDK by its path. The jars were built as follows:
  - ThreeTenBP and libphonenumber with JDK 8. Their class files are majors 50 and 49, targets 1.6 and 1.5.
  - The rest with JDK 17, at release or target 8.
  - Log4j with JDK 11 and toolchains 8 and 11.
- **Built jar digests include build timestamps.** Bind the copies in `$O/artifacts/` (digests in the record), or the
  class and resource digests listed there, which are stable. A rebuild gives another jar digest.
- **The released versions do not all sit on one side:**
  - Collections 4.6.0 and Gson 2.14.0 behave like the regressed or parent side.
  - ICU4J 76.1 behaves like the #3249 parent, and its brkitr resources are byte-identical to the parent build's.
  - Log4j 2.19.0 behaves like the parent and 2.20.0 like the fix.
- **ICU**: the fix's root `word.brk` is byte-identical to the parent's `word_fi_sv.brk`
  (`e7e505439ca75fd34cb1fc584142a5c4ee7d1e60dbd73925ced84565bcb66d9c`). The fix removes `fi.res`, `sv.res` and
  `word_fi_sv.brk`. This bears on the brief's "where the rule bytes match across two locales" question; the full table is in the record.
- **Log4j #1173 is two commits**: `e325de9abf771a4501bae7cd7910fcbce31f5663` → `5bde96782efab839c2d6242b9d46401fee3fa211` →
  `7107cd655380d81dea72df930a832e598173971e`. Only the two ends have worktrees; the middle one is in the mirror.
- **H**: the private helpers that exist only on the fix are `FastDateParser.isValidDayOfWeek(int)` and
  `toCalendarDayOfWeek(int)`.
- **A**: `Jdk8Methods.floorMod(long,int)`, descriptor `(JI)I`, and `TZDB.dat`
  (`24d8db6ab7b32af2bd8df1ab1cc42b3c3058251cd4055bbee1fe51c55e2cbc77`) are byte-identical on both sides. Only
  `DateTimeBuilder.class` differs.
- **C**: the production metadata resources are identical on both sides; only `AsYouTypeFormatter.class` differs.
- **POI**:
  - Its build writes the jar to `build/dist/maven/poi/`, not `poi/build/libs/`.
  - Gradle needs `-Porg.gradle.java.installations.auto-download=false -Porg.gradle.java.installations.paths=$J17`.
  - Its `:poi` configurations are cached, so `--offline` works. Other POI modules (`poi-ooxml`, where the PR's
    `TestXSSFBugs` change lives) were **not** resolved or built.
- **Log4j**: run Maven 3.8.4 **on JDK 8** with `-t $O/toolchains.xml` (toolchain 11), as upstream CI does, with
  `-pl log4j-api-java9,log4j-core-java9,log4j-core-test -am` and `package`. Each setup try that did otherwise failed
  (see [Jobs](#jobs)).
- **No snapshot dependencies** from outside are used. The only SNAPSHOT versions are the projects' own modules.
- The probes set their own state (zones, locales), and Log4j's probe runs one JVM per default zone.
- **POI**: `DateUtil` and `LocaleUtil` are byte-identical on both sides; `DataFormatter` and `CellNumberFormatter` differ.

### What is left for the domain work on purpose

- The membership and exposure check against Beyond JBMC's sealed panel, the overlap with example 310, and reading what
  changed in `lib/` since `96d1883e`.
- Every case artifact: `prepared.json` for each side, the `caller-workflows/v1` workflows, scopes, `UpgradeProbe`,
  observers, fixtures, manifests and lemma declarations.
- Registering the changed-history and preservation questions, and all claims, runs, startup recovery, summary
  consumption and cache comparisons. No case directory or example id was created.
- The choice of Ecuadorian inputs for C and of the extension cases after C. B's accounting-format path. Any POI module
  beyond `:poi`.
- The aspirational URL-only selection.
