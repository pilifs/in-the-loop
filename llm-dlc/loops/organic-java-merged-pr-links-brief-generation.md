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
| FasterXML/woodstox#335 | written | Read issue #334, both buffered-writer revisions and the landed StAX2 regression. For offset 4, length 5 and selected X]]>Y, the first bracket is array index 5. After a one-character replacement the temporary copy puts it at index 1. The two-delimiter repaired-text readback remains a prediction. |
| apache/avro#3709 | written | Read AVRO-4211, the 1.12.0 spec, Schema, IdlUtils, JacksonUtils and its landed scalar tests at 4c29cfb. The IDL writer serializes field.defaultVal(); nonempty array conversion on the primitive branch reaches getElementType(), which throws there. The proposed int-first array fixture and IDL output were not executed. |
| ical4j/ical4j#931 | written | Read ComponentGroup’s two-parent landed range and its OpenSpec and parsed-calendar regression. The July 16 endpoint is included by that fixture, and the original and corrected lists both have three entries. The loop removes by start from a list containing earlier overrides. Order dependence when a moved occurrence lands on another original start is a source prediction. |
| brettwooldridge/HikariCP#2346 | written | Read issue #2323, both ProxyConnection revisions, PoolBase and PostgresTest with postgres:16 and pgJDBC 42.7.7. The parent skips setting the dirty bit when the applied schema is null. The landed test expects test/null/test across the two borrows. Same-backend SQL lookup of the marker remains unexecuted. |
| apache/commons-pool#85 | written | POOL-396 reports the stale idle object; both landed regression tests catch RuntimeException and assert active and idle counts are zero. The pinned destruction sites precede rethrow. Exact callback identity/order and the capacity-one replacement borrow are proposed public checks. |
| ReactiveX/RxJava#6019 | written | Read issue #6018's 2.1.13 callback sequence and the two landed disposal methods and tests. The publisher and subject APIs expose detachments independently of downstream silence. Per-registration cancellation counts before the stop signal, plus repeated disposal, are a proposed challenge. |
| reactor/reactor-core#3822 | written | Read issue #3821 and compared the landed three paths to the 11-commit submission. The final scope is exact buffers. The merged parameterized test checks finite demand, sets and discard counts. Whether the second set stays withheld until a second request remains open in the staged history. |
| qos-ch/logback#862 | written | Read #857 and the landed encoder, rolling/file/stream appenders and test at 42caff8. Startup and stream replacement both call encoderInit, but writeBytes checks isStarted; the landed test reads distinct files. Exact bytes after two consecutive explicit rotations remain a prediction. |
| jOOQ/jOOQ#19875 | written | Read the two-parent landed delta and issue #19856’s separate H2 test at 5a98d74. The test checks counts and name membership; the landed PR adds no test. Reordered inputs, partial batch and complete JDBC tuples are predictions for these pins. |
| jOOQ/jOOL#418 | written | Read issue #417, both module changes and SeqTest. At row index 2, upper offset Long.MAX_VALUE−1 overflows in WindowImpl.upper(), then narrows to int zero. That predicts a wrong last value of 1 for [1,2,3] despite a full frame; a public call has not confirmed it. |
| eclipse-jdt/eclipse.jdt.core#5380 | written | Read the three-commit PR, issues Core #5412 and UI #2598 and the landed test at 2008a72. Its actual edits use internal DefaultCodeFormatter with LF and CRLF; ToolFactory returns the built-in implementation when no extension ID is set. Public factory and second-pass idempotence remain to be observed. |
| junit-team/junit-framework#2646 | written | Compared the parent and merge generator, engine selection and the two engine discovery fixtures with issue #2645’s console output. Five submitted commits landed in one. The cached assertions cover the two annotation placements; the public TestPlan rename relation remains unexecuted. |
| google/guava#7784 | written | Read earlier PR #7716, the parent difference traversal, both landed Sets implementations and the equality/bound tests. For a four-element backing set and singleton exclusion the lower bound is three, so equals(emptySet()) can avoid the backing iterator. The exact counter and equality after same-size backing mutation remain public predictions. |

## Final check

The 20 input URLs are distinct. Their case headings and record rows match in order, with 61 claim rows. Each row names a public observation, its basis and an outcome that refutes it. All 20 PRs were accessible. The 112 code, test and documentation blob links use full revisions. The external jOOQ regression was checked against the separate commit in issue #19856. Reports, assertions in upstream tests, calculations and predictions for unexecuted fixtures are identified in the case sections.

For each range, the start is the target parent and the end is the landed commit. The second parents of DataSketches #767, Commons CSV #613, iCal4j #931 and jOOQ #19875 match the submitted heads. The other landed commits have one parent. For the multi-commit submissions we compared the landed source changes to the aggregate PR file list and inspected the available commit subjects. No case required extending the start over a multi-commit rebase. The Lucene and Solr changelog previews are truncated. The Jackson test rename exposes only the destination path in the aggregate path list. The changed implementations and all regressions added by the PRs were available. For jOOQ #19875 the regression fixture is in the reporter’s separate commit.

<details>
<summary>SHA-256 receipts for the upstream responses read on 2026-11-25</summary>

Each PR number refers to the repository in the table above. The first digest covers the GitHub PR response and the second covers the response containing the pinned blobs. Additional digests identify linked issue or commit responses downloaded separately.

| PR | PR metadata | Pinned sources | Additional response |
|---|---|---|---|
| 14732 | `c4595ea820ae04e78b5e958f5f42ee453fa5b7b917eb26ff40319c7e91359ec5` | `a827cae4089d270b423d283a198625837aa9652671d21bd6d9a3ed01373182e0` |  |
| 1179 | `d65c86176e80602a00f1b8f9ab7f940d37f93444f571becce7c6d9d3b6219386` | `e6629118980427456d8627267fab8cccbf931be8ef5c8629f40fa60cc5cc7fb4` |  |
| 914 | `1e9abfa83af5b67164217e006e7c1ea7bc923e5746f35bc7020476e23e3a81ca` | `54f13b1b3760a550080944d5d23cde9c88cdedb71d3d00332053ca9981a4ea27` |  |
| 767 | `34efaf4ebe7e5e5a9816dd0d6236c7c7b868a24dcb347a2f769d2bded40a053c` | `1d2ced45821723e3137c1e2edcc097203cc44d8b82b5a763375462fdd8e0514c` |  |
| 3158 | `2640d85280f11e3c737b4f43eb010324aae0011c07af77973f58afe4b8e6db08` | `39e357d4e730956bd0332cb66795dde2077e3a5055405ded679b93c50c969d5b` | issue `59469e540d6b3b79c25192490b43da6b48bb791ef42dfc7724299972982d7d54` |
| 613 | `1f07d47ee122830275d92ba11d7b193a81b99474309362bb036c4ea721cd60c2` | `689990d65fe3568e7b432041a21e2bc710de8c84b4efb1baa9f7dcfd932fdbb3` | issue `8ce8142c498b59d805665cbf369d9d3f5960ddc18a86cc241e5c915f3bf7e6fd` |
| 625 | `150e2be6fe2e1f33006866a68ebabeb5885f8375bdf7e14133f4ab7ad45efca5` | `1f79e4770df44d3edf69dbbdb91c9af11a49875b38f4f00aa870e8d5f7f4985f` |  |
| 335 | `6f884dd3f5d7f5bb68acc5547017792a556ed61afd63ceffe002c2063a0fde31` | `1d2eec113f6048497e565dfb4b389f2379fea6fe32dc71b98bf6e1a550ff3a92` |  |
| 3709 | `221f795e40c1eb16a93549dfe5647bed9841374f4d0773c3ec4657c5b0463f2e` | `8d9c75dc43999029da8cc96eda3d70351153279cb2c411153e799b8812321701` | issue `55b1b319601d1dcff3cf5065ae43a39ea7915968c69ba030e3ba024f3de1fef9` |
| 931 | `b0ed7d563bf399ad20cbf830121bf0ae95e254529cc911387df4114392b6be5b` | `0c79e58afa1d6b180624bb60a63736af59444b470fca5899659c3a809bb0f31e` |  |
| 2346 | `e072612cc45e52df1364e8b51258e6c212d006e7d4d5f9ec948078f6608cf98f` | `637005b3f7fff282dc0547c563c4d1205e17f058defc2577a84ed5f9b3221e6f` |  |
| 85 | `6d31f492a040277366ec18e5e8ba1f27bd10be612404a492269981dc4a9c22f2` | `ee6ea71ea923b93701435132c456d9681a4f2534d9ee454f8cc70d7278bc9d26` | issue `38d1ad2f3a2dc457f88fd744fb326edfe248a2924c3f63cb9e3a77cf8a1306c1` |
| 6019 | `8830838128b3cc7c0769596a67aa23cd4e2ff0907c0e86e51ab7fd2cb3a337a9` | `55c63b8f20d19dd2ad417f44b793b606e796b4d6c2ef396db29d3a38bd332a56` |  |
| 3822 | `b193be48982e8d427da1dce3a73b444d208ff6451efb4282858beb14486051e9` | `266870d88dede255de6a08ba64ca9368ebcf2da54f80e5bff70416793b35b0f7` |  |
| 862 | `81d04cb81d7135c73388476cd784d713772c1d3baf0c54f734fbad03cf068217` | `fd9c0d75c6149d11d3c230562b1ccb357de9095008d35a37f14cc7ec4ed17016` |  |
| 19875 | `f3506af3a292620f5f5d18cefdb960d94caddca0d42eebe6e921d8e20fd075d0` | `d0eacd3b6b63a23510eefe3ef46fc6688806ca71e296fd802f742c58ad846991` | issue-test `b0046ff00087652fcddd46ced2c1118a834796aec952e221c34d580aa9423e20` |
| 418 | `8a2ca2726f05f40313cd4038f0732670419bf20a797a32495e08afe478e465db` | `54107505c68763d990f64fb2b2466d0f74bd3e84c3d223b71ac1140febb88b0e` |  |
| 5380 | `40229fde51c6505394a005d60c6a686bf8ec3d5f646cb1a9d0b8a5fc2c15f447` | `7e6933290974b080c62718d930023eb86c3b695546cfc331ba10a78e3b8ef2f7` | related-issue `bb84d784fc94946b1aabdf84a0f719df017c90ad16ac309fe1fee5a941118b09` |
| 2646 | `7b5f8d0a7cfcaf5a0039cf6d070122b12ec398a03d72379a192da121710e432d` | `5776904476fd90eb1eceeba2a864a235674eb3c70a4429a3d4217e9827a7a22a` |  |
| 7784 | `0e0d73d0facb44215fb13d1f581594592f3116c7612642537577a806614220b7` | `4a643abe37808bdd3c9588cbe3e00b939cb69798f5bc4dee1dbbe9393dad3366` |  |

</details>
