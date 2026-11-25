# Generation record for organic Java R01–R50

| Pull request | State | Authoring check and open question |
|---|---|---|
| eclipse-collections/eclipse-collections#1786 | written | Read both insertion paths and the throwing factory/function assertions. Landed code delays key writes. Collision followed by public retry remains unexecuted. |
| apache/commons-collections#688 | written | Compared the add and reindex paths with the regression on strings 01 and 1. A surviving duplicate can cause reindex to reject the backing list. Reindex followed by a valid add remains unexecuted. |
| vavr-io/vavr#3276 | written | Read the public Map contract, Maps remapping branch and null-valued lookup assertions. Before/after use different option constructors for the same stored null. Callback arguments and persistence across a second remap remain open. |
| vigna/fastutil#325 | written | Compared the primitive driver and both int regressions. The copy length changes from destination length to size(). Nonzero spare cells and post-copy mutation remain unexecuted. |
| google/guava#8811 | written | Compared the pinned extreme-distance rotation test and public range method with the boxed-list contract. Integer.MIN_VALUE modulo lengths 3 and 5 gives right rotations of 1 and 2. The sentinel-protected subrange remains unexecuted. |
| apache/commons-lang#1865 | not yet |  |
| locationtech/jts#1168 | not yet |  |
| jgrapht/jgrapht#1379 | not yet |  |
| google/guava#8801 | not yet |  |
| jgrapht/jgrapht#1376 | not yet |  |
| apache/commons-io#931 | not yet |  |
| apache/commons-io#860 | not yet |  |
| google/jimfs#435 | not yet |  |
| vigna/fastutil#384 | not yet |  |
| apache/commons-codec#437 | not yet |  |
| apache/commons-compress#725 | not yet |  |
| apache/commons-compress#775 | not yet |  |
| FasterXML/jackson-core#1716 | not yet |  |
| locationtech/jts#1092 | not yet |  |
| apache/commons-csv#412 | not yet |  |
| square/javapoet#994 | not yet |  |
| square/javapoet#986 | not yet |  |
| javaparser/javaparser#5176 | not yet |  |
| javaparser/javaparser#5207 | not yet |  |
| square/moshi#1442 | not yet |  |
| google/gson#2998 | not yet |  |
| FasterXML/jackson-core#1816 | not yet |  |
| FasterXML/jackson-databind#6407 | not yet |  |
| FasterXML/jackson-databind#6473 | not yet |  |
| FasterXML/jackson-dataformat-xml#895 | not yet |  |
| h2database/h2database#4034 | not yet |  |
| h2database/h2database#2614 | not yet |  |
| apache/calcite#5345 | not yet |  |
| apache/calcite#4942 | not yet |  |
| apache/arrow-java#1518 | not yet |  |
| apache/arrow-java#1342 | not yet |  |
| apache/avro#2282 | not yet |  |
| apache/avro#2520 | not yet |  |
| apache/parquet-java#3830 | not yet |  |
| ThreeTen/threeten-extra#433 | not yet |  |
| ReactiveX/RxJava#5101 | not yet |  |
| reactor/reactor-core#937 | not yet |  |
| reactor/reactor-core#3783 | not yet |  |
| ReactiveX/RxJava#6664 | not yet |  |
| resilience4j/resilience4j#2067 | not yet |  |
| resilience4j/resilience4j#1999 | not yet |  |
| remkop/picocli#2036 | not yet |  |
| assertj/assertj#3710 | not yet |  |
| junit-team/junit-framework#5839 | not yet |  |
| junit-team/junit-framework#4466 | not yet |  |

The cases distinguish upstream reports and pinned test assertions from predicted caller observations. No upstream build, runtime probe or verification job was run during authoring.
