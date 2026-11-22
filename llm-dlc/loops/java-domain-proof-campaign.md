# Java domain proof campaign · From buffer views to evolving schemas

**Execution brief for `pilifs/in-the-loop` · Based on [`develop@ae92d881`][develop].**

Prove five merged changes across Apache Parquet, Jackson Core, Apache Avro and Apache Commons CSV. Start with Parquet, where a public caller can already reproduce the failure. Open the first Avro case early. Use it to learn how much of the real reader can be verified before taking on the capstone, a schema-evolution change that constructs a default value while decoding a record.

| Suggested order | Upstream change | What the checker has to explain |
|---|---|---|
| 1 | [Parquet #3333][p-pr] · Nested binary value | Which bytes belong to one child of a serialized container, even when the enclosing buffer starts at a nonzero position. |
| 2 | [Avro #1381][a-pr] · Enum names across namespaces | How a writer schema and a reader schema resolve to the value a caller actually receives. |
| 3 | [Jackson Core #1415][j-pr] · Nonblocking token locations | How multiple physical array windows become one logical byte stream through suspension and resumption. |
| 4 | [Commons CSV #218][c-pr] · Multicharacter delimiters | How lookahead, quoted fields and end-of-input interact when recognizing a delimiter consumes characters. |
| 5 | [Avro #3730][d-pr] · Reader-only union field | How fast-reader construction selects the array member of a union and materializes its empty default in a decoded record. |

**The research question.** Can an agent prove a public change in another library more cheaply using a fact established by the Avro run? Can a second Avro feature reuse evidence from the first while adding genuinely new semantics? Preserve room to try any technique. The durable requirements are an explicit claim, evidence at its stated entry and scope, and an honest measurement of what a later feature reused.

## Starting point

The six earlier PRs remain at **39/46 ordinary native decisions** and **46/46 finite JVM decisions**. Avro #3878 accounts for all seven open ordinary claims. Example 361 already covers Avro #729. Its two parent violations replayed at the original public entry. Its two fixed claims were established under recorded startup, yielding **2/4 original native, 4/4 under recorded startup and 4/4 finite**. The final checker retried all seven open original Avro and six open JavaParser claims. All thirteen still refused under ordinary startup. The accessor-registration proof, writable-shrink proof and JDK buffer proofs are useful starting evidence with different scopes. [Pilot report][pilot] · [Machine-readable results][pilot-json] · [Example 361][decimal]

The bounded heap-buffer result covers backing arrays through length six. It establishes the relationship among identity, capacity, position, limit and remaining length. A separate proof covers an independently moving duplicate cursor. On #729, checked reuse saved one solver invocation, but end-to-end time rose from **8.22 to 8.51 seconds**. Its qualifier currently recognizes specific Avro call sites. Parquet introduces read-only views and serialized containers larger than six bytes. The new caller must justify those differences. [Producer][producer] · [Call-site qualifier][qualifier] · [Measurements][cost]

### Preflight evidence

I compiled original production source from the pinned parent and fix revisions and ran independent public-API probes on Debian OpenJDK 21.0.13 for the following three cases. They are useful starting witnesses. The campaign still needs the original build artifacts, upstream tests and native receipts on its chosen subject JVM.

| Case | Parent observation | Fixed observation |
|---|---|---|
| Parquet | 32/64 selected elements passed. Every first element failed, and every last element passed. With an empty first element, a one-byte sibling and 25 bytes of leading padding, the returned view had position 35, limit 41 and six bytes remaining. | 64/64 passed. The same empty view had position 35 and limit 35. Its next relative read threw `BufferUnderflowException`. |
| Jackson | With `[true]` fed as the padded window `[1,7)`, the closing bracket’s token offset was **6**, and the cursor after it was **6**. The trace matched the unpadded reference for 32/128 schedules. | Closing-token offset **5**, cursor **6**. All 128 traces matched. The start-array and boolean observations also matched across the revisions in the one-feed witness. |
| Commons CSV | Parsing `a||b||` with delimiter `||` produced `["a","b|"]`. Parsing `a|b` produced one literal field. | The first input produced `["a","b",""]`. The lone delimiter prefix in the second remained literal. |

The Parquet probe compiled the original production classes needed for its public path. The Jackson probe compiled the production sources, generated package-version metadata from the upstream template and used matching FastDoubleParser sources. The CSV probe compiled the two original production trees. The two proposed Avro cases were checked against the merged patches, first parents and upstream test code. Their predicted failures await the paired JVM builds. [Parquet diff][p-diff] · [Jackson regression][j-test] · [CSV regression][c-test] · [Avro enum test][a-test] · [Avro default test][d-test]

## The five examples

For each PR, freeze **one changed-behavior claim and one preservation claim, each on parent and fix**. This gives 20 primary obligations across the five PRs. Freeze each public entry, input family, bounds, startup, observations and independent expected values before checker development. A named upstream test may exercise a broader public path than the bounded claim. Retain it and label both paths.

### 1. Parquet · A nested value has its own byte extent

Use the `parquet-variant` module. Build a two-element binary array with `VariantBuilder`, then call `getElementAtIndex(i).getBinary()`. Use both payload lengths independently from 0 to 3, both indices, and backing offsets 0 and 25, for 64 cases per revision. At payload index j use byte 10+j for the first element and 20+j for the second. Rewrap the original value and metadata at the specified offset, preserving their logical lengths. The upstream object-with-nested-array test exercises an additional public path. [Original test][p-test] · [Padding fixture][p-fixture]

- **Changed behavior.** Compare remaining length, every byte and relative-read exhaustion with the selected payload. For an empty child, the first read must already throw. Keep the original nonzero-position witness.
- **Preservation.** Read the last child, advance its view, and look it up again. The fresh lookup returns its original position and exact payload. An oracle that accepts the following child’s header, or requires position zero, should be rejected by the appropriate control.
- **Foundation opportunity.** The implementation duplicates a buffer, sets its position, then sets a logical limit. The public `Variant` constructor creates read-only views. Inspect the actual JDK method targets and maximum backing length. A read-only view can share storage while declining public access to its backing array. Express the new guarantee in terms the caller can observe, such as indexed contents, cursor independence and exhaustion. Bind its hypotheses at the call site and price the extra work. A public `Variant` built from independently checked serialized bytes is a useful companion if the builder blocks the primary.

### 2. Avro · Resolve the schema, then read the value

Use Avro’s core Java module. The change makes enum and fixed resolution compare unqualified names. The historical regression creates a record with an enum field, writes it with `DataFileWriter` and reads it with `DataFileStream`. Run that test on both artifacts. For the bounded proof, use a real `GenericDatumReader` with an original writer schema, reader schema and binary decoder. A one-field record containing enum symbol A or B needs only the encoded index when the writer symbols are ordered [A,B]. A literal byte 0 or 2 provides an independent binary input. [Upstream regression][a-test] · [Landing change][a-pr]

- **Changed behavior.** Fix the outer record and field names. Use writer enum `writer.E` and reader enum `reader.E` with both symbols. Check normal completion and the decoded field’s symbol text. The parent is expected to reject the namespace change, and the fix to return A or B. Include a reader with reversed symbol order to catch accidental reuse of the writer’s ordinal.
- **Preservation.** The same enum name and namespace decodes both symbols. A reader with a different short name and no alias must still reject. Observe a typed failure at the actual decoder entry and obtain its concrete exception class from the pinned JVM.
- **Foundation opportunity.** A small companion can inspect `Resolver.resolve` directly on the enum pair. A record-level resolution may defer a nested error to the field read. The primary claim observes the resulting record or exception. Keep any reusable schema-construction or resolved-field fact available to case 5, including the dependencies that must be checked on its later Avro revision.

### 3. Jackson Core · A token has a logical offset across feeds

Use `new JsonFactory().createNonBlockingByteArrayParser()`, `ByteArrayFeeder.feedInput(bytes,start,endExclusive)` and the real `nextToken()` loop. Split the six ASCII bytes of `[true]` at each subset of its five internal boundaries. For each of the 32 partitions, use one common padding value from 0 through 3 in every chunk’s fresh backing array, with sentinel bytes outside the window. Drain available tokens after each feed, signal end on the final feed and observe termination. The upstream test on the parent marks two failures as expected. Run the unmasked fixed test source against both production builds. [Upstream test][j-test] · [Original issue][j-issue]

- **Changed behavior.** For all 128 schedules the emitted triples (token, token offset, current cursor) must be `(START_ARRAY,1,1)`, `(VALUE_TRUE,2,5)`, `(END_ARRAY,5,6)`. Use these independent expected constants as well as the unpadded differential run. Only emitted tokens contribute triples.
- **Preservation.** Across the same schedules, the parser emits exactly those three token kinds in order and terminates after end-of-input. Temporary `NOT_AVAILABLE` replies are legal before completion. Distinguish them from final EOF.
- **Foundation opportunity.** Prove how a parser-buffer index maps to a cumulative logical position across one refill, then try composing it across feeds. This public Jackson parser has a different call graph from the Jackson initialization that blocked Avro. Any proposed transfer between the two must name a shared producer and check its bytecode and preconditions.

### 4. Commons CSV · Delimiter recognition that consumes input

Use `CSVParser.parse(Reader, CSVFormat)`, iterate the returned records and observe field count, field contents and final exhaustion. Start with the real `StringReader` and pin the delimiter and quoting settings. Build the oracle from expected field vectors and a small independent fixture encoder. Receiving a single formatted output string would conceal some distinctions among empty and missing fields. [Patch][c-pr] · [Named upstream cases][c-test]

- **Changed behavior.** For each delimiter `||`, `|||` and `|~|`, encode four single-record shapes: ordinary successive fields, an interior empty field, a quoted field containing the complete delimiter, and a trailing empty field. Include the exact upstream adjacent-delimiter and quoted witnesses as named fixtures. Compare every returned field including the final empty string.
- **Preservation.** A proper delimiter prefix embedded in a field and followed by a nonmatching character remains literal. Include the single-character delimiter and ordinary quoted-field controls on both sides. A wrong oracle that strips every pipe or drops the final empty field must fail.
- **Foundation opportunity.** Track the effect of lookahead separately from the act of consuming a confirmed delimiter. If the Jackson work supplied a useful input-segmentation technique, try the CSV caller with a real capped `Reader` as a separate experiment. Establish the contracted short-read behavior and preserve the primary `StringReader` denominator.

### 5. Avro · Materialize a default through a union in the fast reader

Run the original parameterized test in **both binary and JSON**. The writer has an empty record. The reader adds a field of type `[array<Record>,null]` with default `[]`. Use the same public setup as upstream: a fresh `GenericData` with fast reading enabled, a `GenericDatumReader`, its expected and writer schemas, and `read(null, decoder)`. The parent passes the union schema into array construction. The fix selects the array member. [Upstream test and reader setup][d-test] · [Landed diff][d-diff]

- **Changed behavior.** Freeze the binary public reader as primary. Include the upstream empty record and a record with a preserved integer marker drawn from −1, 0 and 1. Check successful decoding, an empty array in the new field and each marker where present. The parent is expected to throw during default construction. A hard-coded empty list that loses the marker cannot pass this oracle.
- **Preservation.** With a direct array field and the same empty default, the reader must decode the same records. Capture JSON and standard-reader results as separately labeled controls. A default-free required field supplies a negative control for a model that synthesizes missing fields indiscriminately.
- **Foundation opportunity.** Check whether the earlier schema/reader fact survived the change in historical classpath. Keep actual union selection, fast-reader setup and default allocation visible. If a producer cannot be discharged, report the strongest public result obtainable with its exact assumption, the narrower native proof if any, and the first unproved producer. A helper returning the right schema is useful intermediate progress.

## Historical pins and test selectors

The left revision is the **first parent of the landed commit**. The branch tip or the PR’s last advertised base can differ. Resolve and record full SHAs when building.

| PR | First parent | Landed commit | Historical selector |
|---|---|---|---|
| Parquet #3333 | `dfc025e17e21a326addaf0e43c493e085cbac8f4` | `8e740f07c26783d6dec2c4ac2cffa9823fe18036` | `TestVariantObjectBuilder#testMixedBinaryBuilder` |
| Avro #1381 | `0cbfb17d49186348a85cc2afc19c6b940da4aad1` | `c35add7b29b5fab9229d79927a74f327bd56fa70` | `TestResolvingGrammarGenerator#testDifferingEnumNamespaces` |
| Jackson #1415 | `99f749d958a55013724571d825625e1032af9d4b` | `596fd82955080ba7207b4adc54100781b5024a61` | `AsyncLocation1412Test#feedWholeDocumentFromNonZeroOffset`, `feedByteByByteFromNonZeroOffset` and the offset-zero control |
| Commons CSV #218 | `94711ebf25d79bd95df8a5e70885325660f94ddc` | `c15a06eee95e227fbe5c61849dd12b7bf126016a` | `JiraCsv288Test#testParseWithDoublePipeDelimiter`, `testParseWithDoublePipeDelimiterQuoted` |
| Avro #3730 | `974961d97a84d3601113d0f3cdc41db6580d1b6b` | `892d6997dcb65627560b04bd76c5a3dd97666cdf` | `TestReadingWritingDataInEvolvedSchemas#readerWithEmptyListAsDefaultValueForUnionFieldIsApplied` |

## How to work through it

Use the managed verification pipeline and the repository’s [standing rules and timebox][loop]. One research agent can follow an example across the adapter, checker, JDK model and evidence tools. Build/replay jobs for independent libraries can run concurrently while that agent investigates a blocker.

1. **Prepare and freeze.** Allocate free IDs at execution head (361 was the latest at inspection). Reuse the original-build and class-binding workflow. Build both original production artifacts and transplant only the necessary upstream test code and fixtures to the parent. Record loaded defining classes, JAR providers and hashes, compilers, subject JDK, ordered runtime classpaths, build dependencies and test outcomes. Historical Maven snapshots, particularly Jackson’s parent POM, need resolved identity. Retain a build failure or a different oracle outcome with its explanation. [Existing original-build workflow][workflow]
2. **Run a before/after on the same claims.** Commit the prepared examples before submitting the jobs. Start with the pinned campaign verifier, ordinary startup and strict gap handling. Use the current fingerprint inventory for a new baseline. Bind the baseline to the execution commit and binary digest. After implementation, repeat on one identified final verifier. For each obligation record claimed scope, reached bytecode, status, first blocker, wall time, peak memory and receipt. A genuine parent counterexample needs admission and replay at the original public entry on the original JVM. Finite JVM enumeration and named upstream regressions have their own columns. Keep a fixed-side establishment conditioned on captured startup in the companion column unless ordinary startup has been discharged.
3. **Spend on the shared obstacle when it helps a consumer.** Try the existing bounded bytes-schema/Jackson startup probe from the last report if the two new Avro cases reach the same producer. A scoped success, a concrete refusal, or a real counterexample can guide the next move. Follow the standing timebox and keep working through independent examples. New scope, a changed observer, a local assumption, or a test with early initialization gets a separately named companion.
4. **Price transfer.** Compare checked reuse disabled and enabled on the same downstream public obligation with identical inputs, startup, verifier and budget. Separate producer construction, recertification, call-site validation and checker time. Report whether a later PR reused a proof, reused implementation only, or still required a new argument. Include a changed bound, provider or observable that should invalidate the evidence. When both routes decide the same scope, report end-to-end cost. When only one decides it, report the capability gain.

Use `python3 examples/tools/build.py --plan ID` to inspect prepared claims and `python3 examples/tools/build.py ID --task TASK` as the normal managed job entry. Reproduce a narrowed parent witness with `--original-witness ORIGINAL_TASK --from-task COMPANION_TASK`. The run should emit example records, a machine-readable per-obligation scorecard and a short results brief with links to the final jobs. [Example and reproduction commands][pilot] · [Evidence qualification][qual]

## Done when

Every proposed PR has a paired build/test outcome, a frozen public claim pair or explicit intake blocker, and a final disposition. Report original native decisions out of **20 planned**, with establishments and replayed refutations shown separately. Publish finite JVM, startup-conditioned and narrower helper results in adjacent columns. Keep the earlier 39/46 and example 361’s 2/4 populations intact. A higher input-row count gives coverage information within one obligation.

**Target a step up in depth:** reproduce all five historical failures, establish the fixed changed behavior at ordinary native scope in at least three PRs including one public Avro decode, and demonstrate one checked cross-feature use of a foundation. These are research targets. Record shortfalls and their first remaining blockers. The most valuable closing comparison is what the agent had to build for the first Avro reader, what the second actually reused, and what the union default still required.

## Loop until

Work on independent examples while jobs run. When the remaining work depends on the pipeline, end Progress with `waiting on jobs` and their IDs. Finish with the scorecard and named deferrals once all five cases have a disposition.

## Progress

Examples 363–367 freeze all twenty ordinary public claims on the execution head. The independent grids cover 64 Parquet inputs, four enum schema/input pairs, 128 Jackson schedules, fourteen CSV fixtures and four evolved Avro records. Each preservation property runs on both original revisions. [Opening verifier fingerprint](../../lib/benchmark/java-domain-proof/opening.json) · [Original build pins](../../lib/benchmark/java-domain-proof/cases.json)

The original-build and opening-verifier jobs are [363](../../verification/jobs/20261122-062459-build-and-check-363-parquet-nested-binar.json), [364](../../verification/jobs/20261122-062459-build-and-check-364-avro-enum-namespace.json), [365](../../verification/jobs/20261122-062459-build-and-check-365-jackson-async-token.json), [366](../../verification/jobs/20261122-062500-build-and-check-366-commons-csv-delimite.json), [367](../../verification/jobs/20261122-062500-build-and-check-367-avro-union-array-def.json). Each preserves original failures, the ordered classpath, the finite JVM result and ordinary native receipts.

The first five jobs returned 178 hash-checked outputs. Commons CSV already has three ordinary establishments and a parent refutation. Avro #1381 reproduced its original namespace error in all sixteen upstream test invocations and passed all sixteen on the fix. Its ordinary native reader reaches SLF4J’s blocking queue. The repeat jobs correct finite-command argument order, Parquet’s historical formatter option, Jackson’s moved test and coverage-only build check, and Avro’s three build toolchains. [363 retry](../../verification/jobs/20261122-063655-qualify-363-original-artifacts-and-compl.json) · [364 retry](../../verification/jobs/20261122-063655-qualify-364-original-artifacts-and-compl.json) · [365 retry](../../verification/jobs/20261122-063655-qualify-365-original-artifacts-and-compl.json) · [366 retry](../../verification/jobs/20261122-063655-qualify-366-original-artifacts-and-compl.json) · [367 retry](../../verification/jobs/20261122-063655-qualify-367-original-artifacts-and-compl.json).

The historical regressions have now run on both revisions of all five PRs. On Avro #3730 the two parent errors in the named test are `AvroRuntimeException` during array construction, and both fixed invocations pass. The module packaging step lost Maven Central while an unrelated invoker test resolved its clean plugin. That infrastructure failure did not exercise a public claim. The next job skips that invoker and still runs the two historical test invocations. Parquet and Jackson both pass fresh public JVM replays after binding the shaded metadata and concrete async parser, respectively. [Parquet opening](../../verification/jobs/20261122-121129-measure-the-original-parquet-opening-cla.json) · [Jackson opening](../../verification/jobs/20261122-121129-measure-the-original-jackson-opening-cla.json) · [Avro default opening](../../verification/jobs/20261122-121129-measure-the-original-avro-fast-reader-op.json)

The managed opening jobs returned all sixteen Parquet, Avro enum, Jackson and CSV obligations. The finite JVM decided all sixteen. At ordinary native scope CSV established three and replayed one parent counterexample. The other twelve stopped at heap-buffer transfer, SLF4J queue construction or Jackson's startup property read. The capstone module also packaged on both revisions. Its control driver interpreted the workflow's revision argument as a request for diagnostic text. Reserving `--controls` for that report restores the frozen machine-readable observations. The original JVM replay passes with the previously built JARs. [Capstone opening rerun](../../verification/jobs/20261122-122655-bind-the-four-avro-default-opening-rows.json)

The opening verifier decided **4/20 ordinary claims** and the finite JVM decided **20/20**. Both Avro public readers first refused SLF4J's blocking queue. The final verifier executes fresh queue construction, handles overlapping heap-buffer copies on the pinned JDK images and considers both outcomes of an immediate string comparison against a JVM property. Its public jobs also try constant native calls over the original guard when a symbolic query remains open. The separate Avro and Parquet jobs measure call-site and producer evidence. [Per-obligation scorecard](../../verification/java-domain-proof/scorecard.json)

- Status: waiting on jobs 20261122-123421-final-java-domain-363-parquet-nested-bin 20261122-123421-final-java-domain-364-avro-enum-namespac 20261122-123421-final-java-domain-365-jackson-async-toke 20261122-123421-final-java-domain-366-commons-csv-delimi 20261122-123422-final-java-domain-367-avro-union-array-d 20261122-123422-trace-and-check-the-original-avro-reader 20261122-123429-check-367-fast-reader-producers-and-call 20261122-123429-price-the-avro-buffer-fact-at-the-parque

[develop]: https://github.com/pilifs/in-the-loop/tree/ae92d881c61581011ed494c0ce62fcdfd291343e
[pilot]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/llm-dlc/loops/domain-foundations-strategy-results.md
[pilot-json]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/verification/domain-foundations/results.json
[decimal]: https://github.com/pilifs/in-the-loop/tree/ae92d881c61581011ed494c0ce62fcdfd291343e/examples/361-avro-decimal-buffer-cursor
[producer]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/lib/benchmark/domain-foundations/BufferRange.java
[qualifier]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/lib/benchmark/domain-foundations/buffer_fact.py
[cost]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/verification/domain-foundations/buffer-adoption/measurement.json
[workflow]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/lib/benchmark/organic-java/README.md
[loop]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/llm-dlc/loops/brief-template.md#standing-rules
[qual]: https://github.com/pilifs/in-the-loop/blob/ae92d881c61581011ed494c0ce62fcdfd291343e/examples/tools/targets/qualification.py
[p-pr]: https://github.com/apache/parquet-java/pull/3333
[p-test]: https://github.com/apache/parquet-java/blob/8e740f07c26783d6dec2c4ac2cffa9823fe18036/parquet-variant/src/test/java/org/apache/parquet/variant/TestVariantObjectBuilder.java
[p-fixture]: https://github.com/apache/parquet-java/blob/8e740f07c26783d6dec2c4ac2cffa9823fe18036/parquet-variant/src/test/java/org/apache/parquet/variant/VariantTestUtil.java
[p-diff]: https://github.com/apache/parquet-java/commit/8e740f07c26783d6dec2c4ac2cffa9823fe18036
[a-pr]: https://github.com/apache/avro/pull/1381
[a-test]: https://github.com/apache/avro/blob/c35add7b29b5fab9229d79927a74f327bd56fa70/lang/java/avro/src/test/java/org/apache/avro/io/parsing/TestResolvingGrammarGenerator.java
[j-pr]: https://github.com/FasterXML/jackson-core/pull/1415
[j-test]: https://github.com/FasterXML/jackson-core/blob/596fd82955080ba7207b4adc54100781b5024a61/src/test/java/com/fasterxml/jackson/core/json/async/AsyncLocation1412Test.java
[j-issue]: https://github.com/FasterXML/jackson-core/issues/1412
[c-pr]: https://github.com/apache/commons-csv/pull/218
[c-test]: https://github.com/apache/commons-csv/blob/c15a06eee95e227fbe5c61849dd12b7bf126016a/src/test/java/org/apache/commons/csv/issues/JiraCsv288Test.java
[d-pr]: https://github.com/apache/avro/pull/3730
[d-test]: https://github.com/apache/avro/blob/892d6997dcb65627560b04bd76c5a3dd97666cdf/lang/java/avro/src/test/java/org/apache/avro/TestReadingWritingDataInEvolvedSchemas.java
[d-diff]: https://github.com/apache/avro/commit/892d6997dcb65627560b04bd76c5a3dd97666cdf
