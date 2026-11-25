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
| apache/maven-shade-plugin#150 | written | Read MSHADE-425, both transformer versions, DefaultShader and the landed transformer test. The regression supplies identical provider lines under two names and expects both copies in one output descriptor. Discovery of two distinct loadable providers under both input orders remains unexecuted. |
| apache/iceberg#12855 | written | Read issue #11239, both GenericRecord copy constructors and the landed table and identity tests. The regression expects IDs 200–202 removed. ByteBuffers.copy reads remaining() through an independent view. The four-row Parquet scan and nested slice mutation have not been run. |
| gradle/gradle#21084 | written | Read #7923, the Groovy task-action implementation and the merged integration test. The test appends an unrelated registration and checks console output for both doFirst and doLast. The A→B file and clean-build comparison are open public checks. |
| google/guava#7277 | written | Compared both AggregateFuture implementations with Futures.allAsList’s input-order contract and existing FuturesTest cases. A done input bypasses addListener on the merge. The counted mixed case and the duplicate future completing inside listener registration remain unexecuted. |
| ical4j/ical4j#947 | written | Read the January fixture and the temporal-comparison change. The upstream PR reports the UTC exception’s parent failure and merge pass. For the proposed March fixture, Paris 09:00 corresponds to 08:00Z on March 30 and 07:00Z on March 31 and April 1. The transition and end-time control remain unexecuted. |
| ReactiveX/RxJava#6895 | written | Read the 2.x report and the 3.x cancellation regression. Its test counts 1,000 source emissions with one constant key. For prefetch four the threshold is three, leaving one consumed survivor item insufficient without releasing the three queued values. Both proposed two-key histories remain unexecuted. |
| apache/kafka#6654 | written | Read KAFKA-8289, the pinned acceptance comparison and both processor and topology regressions. With grace 2 and stream time 10 the changed equality boundary is 8. Suppression now adds grace and gap. The positive-grace dual-output history remains unexecuted. |
| JSQLParser/JSqlParser#2770 | written | Read the two-commit PR, usage guide and pinned tests. The stale default in the identity fixture is 1 and must receive no visitor callback. The TYPE fixture rewrites only 2 and asserts one CASCADE. Varying the inactive literal and reparsing that TYPE output remain open. |

## Final check

All 20 distinct PRs were accessible. The case headings and record rows follow the input order. Each of the 60 claims gives a public observation, an independent basis and a result that would refute the prediction. The review traced historical observations to their PR, issue, regression or release note. No authoring-time project build, fixture execution or proof was needed.

Checked all 20 comparisons against target ancestry and submitted changes. Picocli #1529 is the exception to using the landed commit’s first parent as the start. Three consecutive target commits contain the implementation, rename and test. The four submitted commits include a branch synchronization merge. For the other 19 PRs the landed commit and its first parent cover the submission. Full pinned comparison diffs settled the truncated file previews for picocli and Calcite. All 97 source, test, build and fixture links use full commit IDs and match the saved files or binary blob metadata. The two Commons Imaging TIFFs were identified by Git blob ID and size. Their pixels were not decoded.

<details>
<summary>SHA-256 receipts for the source responses read on 2026-11-25</summary>

The brief links the PR, comparison and source paths for each case. The columns below identify the saved GitHub PR metadata, the response containing the pinned files, and any separate Jira issue response. The local cache is under `~/.cache/in-the-loop/agent-tmp/ea63c5f6-1929-4c3f-9921-139ac43a8b86/l-brief/<PR number>/`.

| PR | PR metadata | Pinned sources | Jira issue |
|---|---|---|---|
| google/gson#3059 | 54ede4535b237c311e5c46aa0abbfa38d70c3bd89af215ce89ea4b42b2e78c03 | 908403f5d1fcd8c27d4206393a1e2b201a23155f78d1dd79c2ea4cfcfa08d87c |  |
| apache/commons-collections#701 | 5b16846589e83446287a27ad368bf12948e263bbe6fb56c43112f4dd5c3381b0 | 4e4ba111a59bbfb192fa9ad6e093eb7a373061cd160ebed9e09fb08b9477a3c8 |  |
| remkop/picocli#1529 | 4c882066347ebc6e7a9694e59cc45e194a3b5a1398f94bb9b2cc59ad33198441 | 1a40c1fc171c56b513d4da4f6f0a7235bfb2eecb915e74c5fa432ce29e6ca61e |  |
| java-diff-utils/java-diff-utils#233 | 8526a080fe57a36234ef00be95174368403f4faf4c6b53cbfe44c5f2e586c499 | c057964aaf274316246881d67090c64da270e1137d5a6c20bf7b3be156cf896d |  |
| junit-team/junit-framework#6104 | 82b02fbca347f6150687c62b2af27e023d9dafbb0d9fe0e467a938b38410f10c | 964663d968708a0cbea801e4bc1348f19a0091c00feb9fb67070a45b960923c4 |  |
| apache/arrow-java#1019 | 04663c568a2c2bae73625c3040265e68760f6c62bcccb8f47f80339eafd6abe4 | 96045464e22e34343a91807247eecd4d83582e2e6caacb76489e88da54856fb6 |  |
| jgrapht/jgrapht#792 | 4a6be7b9b33be449c70e7e60a09b8fbb25ca448dfaf6fb15cc43745cbaff65dc | c2c7a4aa1081f11b6b7a6329753abcc50d7d40629196bfbe4bc43ce7b272f0db |  |
| apache/commons-statistics#140 | 8043a3424457b7745b0acc23262ebdc720c8bd4c7b78605de172924209a70dc4 | 7d8de1b6e3550b559b5cda1863bd6f44192c997feaf226f68cd37bcf6c8084e9 |  |
| eclipse-rdf4j/rdf4j#1989 | 12bdf2b1b9ceab40158ed806f5e8735007af4de599a40f20fc5feeeef2602185 | acdad634d76d018e10cdf74272edf7a77359c1bbb22a25da1b3bd0f1e9f02192 |  |
| apache/calcite#5378 | dbcf4c758948cfb41dc1236146572f8bffe2dce97bacacc05f5372877e5ccedc | 5bd446a29580927bd72ea5baa6b7cf6dd70d31df3ffca9f9a14ffbb76b8f9968 | a68081842d0ee09fefad27683c571141eabd75fffdacdaeb58a1b1fa57b56ab2 |
| apache/commons-imaging#335 | 96cd250bbff4f06ad612c2c364d4b9685f5337bd79596e8a1eb7731dbaa29a38 | c5116c78de5de6540019cf31505f6c5d67a34c547bf45b969cec61f5f6ce74e9 | e6c8ca4b6a1861d0041c7976af1077b1ca057f4811a14d266dc6793bd4f74ce5 |
| quartz-scheduler/quartz#1496 | 1ffc14f43e63ad7094156bb189f8a939adbf021bb0d468ea446d976ae34249d5 | da77d033b4f9a3b7f9f3abd13dcccb198344e4cc0d8d72b902b62fba4faf9e77 |  |
| apache/maven-shade-plugin#150 | 5786ca3f397f36357d74045fb2ca4cdd79a30853f92a99315bcb5a5663a2c4f6 | 2917eb91c6fcf7b356c847952e61678d2056b5e8799cc1e96d236f6ccf21b1ff | f832ceadcd43ee0e5cf8445bb40baa970d6085f4e42978c0c8fc971b70885fa0 |
| apache/iceberg#12855 | 92597f136f3c5038900c3c6092a34a6d9f450c8c551f989599bcaacfa393bf6f | 611f440d549c7470cd98e31e41e409629412923e022fc5a53c4be427ea0da1cd |  |
| gradle/gradle#21084 | c872caa6cd45328406c0c873e14aa13ff3dca3ba6a6dcf06b268378adaf724cb | e2f199713d34e6d40c69245697d24fa55aadce8f5ceba3b1635a3a60ffaf24ba |  |
| google/guava#7277 | ab1b971b0bc23f0d74a6acc94aa3b71e6c4da18c3a979e176a1403d0740e67ba | b39a4dc31fcd6805a6faefd6b0f116ae21f96657ec8cafb4de3bb359516ab05d |  |
| ical4j/ical4j#947 | 4b54f7a51d7596161a6136fd213fc1e04a97aaa5e502dfffc50393c60c261d0f | 6c8a1c673ea2bca774c3cbbdf8f7c02ed1cf9a894458724ff79e9f47c769e432 |  |
| ReactiveX/RxJava#6895 | c8d87cf704126fbf9ab41e2df8cdd43fd80953a940481ec59e25ae28f1f6aedf | 78af0c64ccda756aa8f6652c4b613556656896d6301092262991af58caa89d0b |  |
| apache/kafka#6654 | e0331a6d4000e0edcaa0aae0b4d93ba334180104c664a1c34a6d42efab4d38f2 | fd6c76e8d09631587240834737e39f23d5c297f743628e73d21e2dfbffbdda6e | 9ce60de7dc09728c118625741c8ed15ef83f5728210ecf75840b656a3768ed5a |
| JSQLParser/JSqlParser#2770 | 501a10fb25a97618529ca7c81d64615014e1ece3d29f5bff2b51515f66fe1ee0 | b3df5bbeda8edc7cee3c41caa1cd9dd9ed7e2480facd48575620bb11d0d3aaf0 |  |

The full picocli comparison response has digest `dcb28170aeec0db2f798e70cde1e5c741c41956565da034372a07602173b3500`. The full Calcite comparison response has digest `9c66e2c19696c268c90d07c9d9516e18deba6ddfec751acb15a210c8053b85b9`.

</details>
