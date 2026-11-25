# Generation record for the merged Java PR brief

Read on 2026-11-25. The table follows submission order. The checks below compare upstream PR and issue metadata with source at the linked revisions. They are source inspections. No project was built or executed.

| Pull request | State | Source check and open question |
|---|---|---|
| apache/lucene#14732 | written | Read the two cast sites and the INT point-query regression at the pinned revisions. The aggregate PR and landed changes agree on both Java files. The changelog blob preview is truncated. The PR reports the regression fails on the parent. Exact public count/search outcomes for the explicit four-document index remain predictions. |
| locationtech/jts#1179 | written | Compared the four landed paths against the submitted changes and read issue #1178, the core POM, the projection overload, and testProjectSegment. Its x=8 test expects repeated (8,0), while x=9 expects null. The new app function distinguishes these through nonempty and empty line strings in source. Its public readback remains unexecuted. |
| RoaringBitmap/RoaringBitmap#914 | written | Read both overloads at 49e120d and b4b0ba1 and the two landed subtype-array tests. Parent uses clone() in both, despite PR prose describing an older copyOf; the four fixture ranges and three distinct outliers imply 16 union members. Permuted inputs and operand preservation remain predictions. |
| apache/datasketches-java#767 | not yet | |
| apache/solr#3158 | not yet | |
| apache/commons-csv#613 | not yet | |
| FasterXML/jackson-dataformats-text#625 | not yet | |
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
