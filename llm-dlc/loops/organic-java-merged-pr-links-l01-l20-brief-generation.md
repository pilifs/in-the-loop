# Generation record for merged Java pull requests L01–L20

Read on 2026-11-25. The table follows submission order. The checks below compare upstream PR and issue metadata with source at the linked revisions. They are source inspections. No project was built or executed.

| Pull request | State | Source check and open question |
|---|---|---|
| google/gson#3059 | written | Read the three-commit submission, issue #992 and the landed parser, equality/hash implementation and tests. The two changed files match the squash. The test asserts the parsed/integer pair and signed zero; the three-producer map replacement/removal is unexecuted. |
| apache/commons-collections#701 | written | Compared the two submitted commits with the squash and read the multiset contract, both iterator removals and the landed shared test. The PR supplies the parent’s three-null example. The reinsert-and-remove history across views is a source-based prediction. |
| remkop/picocli#1529 | written | Compared all four submitted commit subjects with the target history. The contiguous three landed commits start after 4090e3d; the final one adds only the test. Both CommandLine previews truncate beyond the changed methods. Clearing a redundant primary-name alias should preserve dispatch by contract, but map removal predicts failure; execution remains open. |
| java-diff-utils/java-diff-utils#233 | written | Read the two-parent merge, DiffUtils, the generator’s explicit and implicit paths and the two new tests. Both landed paths match the submission. The PR reports 149 passing tests. Both-column equality formatting with explicit versus implicit leading and trailing equal parts is unexecuted. |
| junit-team/junit-framework#6104 | not yet | |
| apache/arrow-java#1019 | not yet | |
| jgrapht/jgrapht#792 | not yet | |
| apache/commons-statistics#140 | not yet | |
| eclipse-rdf4j/rdf4j#1989 | not yet | |
| apache/calcite#5378 | not yet | |
| apache/commons-imaging#335 | not yet | |
| quartz-scheduler/quartz#1496 | not yet | |
| apache/maven-shade-plugin#150 | not yet | |
| apache/iceberg#12855 | not yet | |
| gradle/gradle#21084 | not yet | |
| google/guava#7277 | not yet | |
| ical4j/ical4j#947 | not yet | |
| ReactiveX/RxJava#6895 | not yet | |
| apache/kafka#6654 | not yet | |
| JSQLParser/JSqlParser#2770 | not yet | |
