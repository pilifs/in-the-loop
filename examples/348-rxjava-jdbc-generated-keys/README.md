# rxjava-jdbc and H2 generated keys

Upgrade rxjava-jdbc 0.7.15 · H2 1.4.192 → 1.4.200  
Caller-visible behavior `returnGeneratedKeys().getAs(Integer.class)` emits the IDs that a subscriber can associate with inserted rows.  
Result One two-row statement changed from `[2]` to `[1, 2]`. Two single-row inserts returned `[1, 2]` on both versions. All four databases contained `(1, "something")` and `(2, "again")`. [JDK 8 observations](records/jvm-receipt.json)  
Scope The synchronous rxjava-jdbc client inserted the same two text values into a fresh in-memory H2 table with a `BIGINT AUTO_INCREMENT` primary key on every run.  
Review action Update any final-key-only consumer and its assertion before taking the upgrade. If the application needs one ID per row on both H2 versions, the two single-row calls produced that sequence in this fixture.

## What CI saw

CompSuite names `DatabaseSyncTest#testReturnGeneratedKeysForMultipleInsertedValuesInOneStatement`. That subclass inherits the recorded expectation from `DatabaseTestBase`. Surefire 2.12.4 ran exactly one matching testcase in each new report directory. The old test passed. The new test reached its assertion and failed with `java.lang.AssertionError` and `expected:<[2]> but was:<[1, 2]>`. The original two-insert companion also ran independently and passed on both sides. [Old trigger](records/old/trigger-surefire.xml) · [New trigger](records/new/trigger-surefire.xml) · [Old companion](records/old/companion-surefire.xml) · [New companion](records/new/companion-surefire.xml) · [Original assertions](https://github.com/compsuite-team/rxjava-jdbc/blob/5e04239e1f831878884972fbf72ab1f529b0647d/src/test/java/com/github/davidmoten/rx/jdbc/DatabaseTestBase.java#L1577)

The exact source POMs inherit the `nexus-staging-maven-plugin:1.6.5` build extension. Offline `mvn -B test` on Maven 3.6.3 stopped loading that uncached extension on both sides and produced zero tests. The XML above came from invoking that Maven release’s actual Surefire JUnit 4 provider and XML reporter directly on the compiled original tests. All production and test sources compiled, including the JMH annotation processor for the test sources. The upstream Travis file lists one JDK 8 and two JDK 7 lanes. The JDK 8 replay is the measured lane. [Maven results and toolchains](records/jvm-receipt.json) · [Surefire launcher](independent/NamedSurefire.java) · [Upstream CI configuration](https://github.com/compsuite-team/rxjava-jdbc/blob/5e04239e1f831878884972fbf72ab1f529b0647d/.travis.yml)

The full JDK 8 test set reported 454 tests in 22 classes on each H2 version, with two skipped on each side. The old run took 2.178 s with zero failures and errors. The new run took 3.450 s with three assertion failures and zero errors. All three came from the same inherited method under `DatabaseSyncTest`, `DatabaseAsyncTest` and `DatabaseViaDataSourceTest`. Preparing, compiling and replaying the cold job took 46.3 s in its execution step. [Full test-set counts and failure inventory](records/whole-suite.json) · [Pipeline measurements](../../verification/results/20261120-232343-run-the-full-rxjava-jdbc-historical-sure/result.json)

The existing assertion already detects the changed sequence, and the companion already covers two insert calls. The additional curator observation is that the final IDs and text in the table are identical in all four cases. It came from a separate SQL read over the real database after the subscriber finished. This narrows the maintenance decision to callers consuming returned IDs. [Independent observer](independent/Observe.java) · [Client JDBC call](https://github.com/compsuite-team/rxjava-jdbc/blob/5e04239e1f831878884972fbf72ab1f529b0647d/src/main/java/com/github/davidmoten/rx/jdbc/QueryUpdateOnSubscribe.java#L243)

## Pinned verifier result

Strict native equivalence remained **open**. On the paired original published client and the two H2 closures, the verifier first stopped at `java.sql.DriverManager.getConnection(String)` in the adapter. The adapter’s separate JVM controls matched the real subscriber on both inputs and both closures under Temurin 21.0.13. The independently compiled CompSuite subject and original tests ran under Temurin 8u512-b09. The historical test and input were disclosed to the curator before the run. Automatic claim discovery and additional verifier findings receive no credit. [Two-sided JVM replay](receipts/replay/20261120T231806Z-aa24d830/result.json) · [Native receipt](receipts/generated-keys/20261120T232346Z-e35e180a/result.json) · [Workflow handoff](workflow-handoff.md) · [Pinned pipeline execution](../../verification/results/20261120-231316-check-returned-h2-keys-through-the-uncha/result.json)

## Provenance and cost

This is a benchmark-curated pair on real rxjava-jdbc client code. The old tag and upstream release tag `0.7.15` both resolve to `5e04239e1f831878884972fbf72ab1f529b0647d`. Its direct child `735c4108c0ebfd9ad4f350d496e9c74bc0893bb7` changes only the H2 version. H2 has **test scope** in this client POM. This disclosed example is excluded from the production-dependency cohort and from transfer. The `src/main` and `src/test` Git trees match across revisions. All 105 independently compiled production classes have identical bytes. A sorted uncompressed JAR containing those class entries has SHA-256 `de2191fd8498856cabfcdd185579688c942b9e1f8f95a7637840c687d25171bd` on each side. All 105 class entries also match the published rxjava-jdbc 0.7.15 JAR used by the native workflow, entry for entry. [CompSuite registry at its pin](https://github.com/compsuite-team/compsuite/blob/6e6d738c8b0ca6ecbba6220b1fd549b2ae14a05d/incompatibilities.json) · [Exact dependency change](https://github.com/compsuite-team/rxjava-jdbc/compare/5e04239e1f831878884972fbf72ab1f529b0647d...735c4108c0ebfd9ad4f350d496e9c74bc0893bb7) · [Target and published JAR locks](target.json)

The receipt identifies the H2 JAR actually loaded by each JVM and the ordered 22 test JARs. The subject JDK’s launcher, compiler and runtime library are hashed. Maven 3.6.3’s own model builder resolved the pinned parent POM, interpolated properties, and applied the default jar lifecycle bindings. The portable effective POMs replace only the absolute checkout directory with `${project.basedir}`. The public Surefire XML retains the matching testcase and failure stack and omits machine-specific VM properties. Raw XML and model digests are recorded. [Dependency digests](independent/inputs.json) · [Old effective POM](records/old/effective-pom.xml) · [New effective POM](records/new/effective-pom.xml)

Inputs were cold at acquisition and warm for each paired run. The first diagnostic Surefire XML was available 5 min 50 s after the acquisition directory was created. The two returned lists and the four row observations were available at the 15-minute checkpoint. The native check used repository commit `19fbb233b928fb822ab3d9e018dccbb2756748cd`, binary SHA-256 `5e56d4e1b9b01d3cb310817866b3ed717f03b9a8971851bdc957356578483c18`, and library tree `6ff6d17a384664aaf02d89881193eef038b86637`. Its pipeline job took 175 s including setup, with 5.414 s wall, 7.362 CPU-s and 158,355,456 bytes peak for the case step. Human minutes, model tokens and currency cost were unmetered for the open calibration. [Curator and product timings](records/calibration.json) · [Exported pipeline report](records/pipeline-report.json)

## Reproduction

Run the following commands from this example directory with an installed Temurin JDK 8 available in `JAVA8_HOME`. The output and work directories for an execution must be new. `acquire.py` uses anonymous public sources, compares every artifact to the lock, and reuses verified files. The native check and the whole-suite baseline run through the verification queue. [Full-test job](../../verification/jobs/20261120-232343-run-the-full-rxjava-jdbc-historical-sure.json)

```sh
case_dir="$TMPDIR/rxjava-i87"
python3 independent/acquire.py "$case_dir/inputs"
unzip -q "$case_dir/inputs/apache-maven-3.6.3-bin.zip" -d "$case_dir"
chmod +x "$case_dir/apache-maven-3.6.3/bin/mvn"
python3 independent/reproduce.py --inputs "$case_dir/inputs" \
  --repository "$case_dir/inputs/subject.git" --java-home "$JAVA8_HOME" \
  --maven-home "$case_dir/apache-maven-3.6.3" --work "$case_dir/build" \
  --output "$case_dir/receipt"
```
