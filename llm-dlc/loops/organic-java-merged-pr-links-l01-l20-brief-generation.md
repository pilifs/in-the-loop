# Generation record for merged Java pull requests L01–L20

Read on 2026-11-25. The table follows submission order. The checks below compare upstream PR and issue metadata with source at the linked revisions. They are source inspections. No project was built or executed.

| Pull request | State | Source check and open question |
|---|---|---|
| google/gson#3059 | written | Read the three-commit submission, issue #992 and the landed parser, equality/hash implementation and tests. The two changed files match the squash. The test asserts the parsed/integer pair and signed zero; the three-producer map replacement/removal is unexecuted. |
| apache/commons-collections#701 | written | Compared the two submitted commits with the squash and read the multiset contract, both iterator removals and the landed shared test. The PR supplies the parent’s three-null example. The reinsert-and-remove history across views is a source-based prediction. |
| remkop/picocli#1529 | written | Compared all four submitted commit subjects with the target history. The contiguous three landed commits start after 4090e3d; the final one adds only the test. Both CommandLine previews truncate beyond the changed methods. Clearing a redundant primary-name alias should preserve dispatch by contract, but map removal predicts failure; execution remains open. |
| java-diff-utils/java-diff-utils#233 | written | Read the two-parent merge, DiffUtils, the generator’s explicit and implicit paths and the two new tests. Both landed paths match the submission. The PR reports 149 passing tests. Both-column equality formatting with explicit versus implicit leading and trailing equal parts is unexecuted. |
| junit-team/junit-framework#6104 | written | Read the four-commit submission, squashed resolver changes, release note, Launcher API and execution assertions. The regression separately rediscovers IDs and executes the whole class. Executing each saved leaf with identical method names and inspecting body markers is open. |
| apache/arrow-java#1019 | written | Read #470, both submitted changes, the merged vector and its SmallIntVector fixtures. In the ordered fixture the parent’s slot-1 size is two while its end by arithmetic is five. The test’s element readback uses slot zero. Equal default hashes after relocating the [40,50] slice remain unexecuted. |
| jgrapht/jgrapht#792 | written | Read issue #790, both public algorithms, the shared implementation and regression at 2663008. Enumerating the two feasible complete matchings gives totals 18 and 20. Changing the unused 5→7 edge to weight 1 creates a first-path tie, while 5→8 is still compulsory. Both public results remain unexecuted. |
| apache/commons-statistics#140 | written | Read both Cauchy sources and the SciPy-based regression at 2535c20. The parent evaluates tan(0) at the median despite the PR’s drift claim. With p=2⁻¹⁰⁵⁰ and scale 2⁻¹⁰⁰ the real magnitude is about 2⁹⁵⁰/π, while the merged unscaled reciprocal can overflow. These public calls were not executed. |
| eclipse-rdf4j/rdf4j#1989 | written | Read #1978, parent/merge GroupIterator, the two pinned SPARQL XML result fixtures and public tuple-query tests. The fixtures contain zero and one result element respectively. Embedding the explicit group in a join with two VALUES rows is an unexecuted cardinality challenge. |
| apache/calcite#5378 | written | Read CALCITE-7909, the pinned rule and planner.iq at 5f48eec. The report supplies the old EXCEPT observation and the landed fixture expects 1/0 rows for EXCEPT/INTERSECT. Counting duplicates by full tuple yields 2/1 then 0/3 in the challenge, which remains unexecuted. |
| apache/commons-imaging#335 | written | Read IMAGING-369, both JpegDecoder revisions and TiffJpegTest. The landed fixture metadata identifies the 3,833-byte compressed file and 48,652-byte reference. For the existing square crop at (11,11) the greatest tested coordinate is 125, short of the 126 edge. The rectangular 3×2 corner comparison remains unexecuted. |
| quartz-scheduler/quartz#1496 | written | Read issue #920, public Scheduler, both delegate revisions and the Derby job-store regression at adeae66. The issue used Quartz 2.3.2/PostgreSQL; the landed test calls the store directly in both directions. Public scheduler snapshots, extension row counts and isolation by trigger group remain predictions. |
| apache/maven-shade-plugin#150 | not yet | |
| apache/iceberg#12855 | not yet | |
| gradle/gradle#21084 | not yet | |
| google/guava#7277 | not yet | |
| ical4j/ical4j#947 | not yet | |
| ReactiveX/RxJava#6895 | not yet | |
| apache/kafka#6654 | not yet | |
| JSQLParser/JSqlParser#2770 | not yet | |
