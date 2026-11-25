# Generation record for the merged Java PR brief

Read on 2026-11-25. The table follows submission order. The checks below compare upstream PR and issue metadata with source at the linked revisions. They are source inspections. No project was built or executed.

The pinned comparisons and primary sources are linked in [the brief](organic-java-merged-pr-links-brief.md). Local responses and reconstructed diffs are under `~/.cache/in-the-loop/agent-tmp/ea63c5f6-1929-4c3f-9921-139ac43a8b86/brief-sources/<PR number>/`. Each directory contains the original PR metadata, the pinned blob response and the extracted source files. Reuse those copies for any further source checks.

| Pull request | State | Source check and open question |
|---|---|---|
| apache/lucene#14732 | written | Read the two cast sites and the INT point-query regression at the pinned revisions. The aggregate PR and landed changes agree on both Java files. The changelog blob preview is truncated. The PR reports the regression fails on the parent. Exact public count/search outcomes for the explicit four-document index remain predictions. |
| locationtech/jts#1179 | written | Compared the four landed paths against the submitted changes and read issue #1178, the core POM, the projection overload, and testProjectSegment. Its x=8 test expects repeated (8,0), while x=9 expects null. The new app function distinguishes these through nonempty and empty line strings in source. Its public readback remains unexecuted. |
| RoaringBitmap/RoaringBitmap#914 | written | Read both overloads at 49e120d and b4b0ba1 and the two landed subtype-array tests. Parent uses clone() in both, despite PR prose describing an older copyOf; the four fixture ranges and three distinct outliers imply 16 union members. Permuted inputs and operand preservation remain predictions. |
| apache/datasketches-java#767 | written | Issue #756 supplies the four-item before readout. Comparing the pinned generic sketch and SerDe tests located the removed live flag write and both reader checks. The independent permutation and cumulative-weight oracle remain unexecuted. The eight-item test does not establish compaction. |
| apache/solr#3158 | written | Read SOLR-17649 and the pinned TestJsonFacets, schema, enum mapping, field type and terms guide. Counting the six input documents gives Low=4, Medium=3, Not Available=3, High=2. The release report describes empty buckets. Repeating a label within a document remains an open check on the merge. |
| apache/commons-csv#613 | written | CSV-329 supplies the one-row StringReader failure. At 871f745, the regression uses package-level nextRecord(), iterator uses Uncheck.get, and the POM pins Commons IO 2.22.0. Independent UTF-8 prefix lengths are 8 (LF), 9 (CRLF) and 4 (ASCII delimiter/LF). Public suffix readback remains open. |
| FasterXML/jackson-dataformats-text#625 | written | Read issue #9, the change from named to unnamed parser state, and both pinned quote tests. The schema-less regression asserts two EOF APIs; the wrapped branch only checks its first row. The added second-record/lookahead history is unexecuted. |
| FasterXML/woodstox#335 | not yet | |
| apache/avro#3709 | not yet | |
| ical4j/ical4j#931 | not yet | |
| brettwooldridge/HikariCP#2346 | not yet | |
| apache/commons-pool#85 | not yet | |
| ReactiveX/RxJava#6019 | not yet | |
| reactor/reactor-core#3822 | not yet | |
| qos-ch/logback#862 | not yet | |
| jOOQ/jOOQ#19875 | not yet | |
| jOOQ/jOOL#418 | not yet | |
| eclipse-jdt/eclipse.jdt.core#5380 | not yet | |
| junit-team/junit-framework#2646 | not yet | |
| google/guava#7784 | not yet | |
