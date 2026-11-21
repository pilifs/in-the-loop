# Six upstream Java fixes on their original bytecode

The six parent regressions reproduced on Temurin 21.0.13. All eight named upstream test methods failed on the parent and passed on the landed revision. Every fixed public-call observation matched an independent oracle across **3,658 input rows per revision**. Strict native verification advanced from **17/46 to 39/46 original-scope obligations**, from one to five complete PRs. It established 26 and found all 13 original counterexamples. Each counterexample reproduced on the original JVM. Finite JVM verification advanced from **36/46 to 46/46** and covered all six. [Recountable scorecard](../../verification/organic-java-pr-campaign.json)

The baseline was `5e41cd71ab872a626179c02914aaae9f812c2c8c`. The latest confirmation uses verifier `35ba19a31d97586a7d9cbcbb757929d4d39c1356` and executable SHA-256 `6b60043b7c651f33ec748bf0ae94068c3fa11f290fbb917196eb8de87582cdb9`. The ordinary native and finite runs, the input-by-input native checks, and the observed-startup checks use that same verifier. A strict establishment requires a non-vacuous result over the stated inputs and startup. A candidate from a narrower scope earns an original-scope refutation only if the original JVM independently admits the input and violates the original assertion. The two transfer PRs have separate counts. [Baseline fingerprint](../../lib/benchmark/organic-java/baseline.json) · [Public factory proofs and original witnesses](../../verification/results/20261121-155347-prove-the-original-avro-factory-and-repl/result.json)

## Original scope and outcomes

| Original PR | Independent inputs | Baseline native | Final native | Baseline finite | Final finite |
|---|---|---:|---:|---:|---:|
| [Guava #8509](../../examples/353-guava-saturated-sum) | 49 pairs of counts from the seven registered values | 10/10 | 10/10 | 10/10 | 10/10 |
| [Commons Lang #1719](../../examples/354-commons-lang-surrogate-cuts) | 1,515 windows on all 31 strings of 0–4 tokens, 36 cuts on a fixed mixed string, and abbreviation widths 4 and 5 | 2/10 | 10/10 | 10/10 | 10/10 |
| [Avro #3878](../../examples/355-avro-writable-buffer-limit) | 21 combinations of capacity 0–5 and logical length 0–capacity | 0/10 | 3/10 | 0/10 | 10/10 |
| [Gson #3034](../../examples/356-gson-overflowing-number) | 10 overflow literals plus 10, 00 and 01 | 5/6 | 6/6 | 6/6 | 6/6 |
| [Gson #3137](../../examples/357-gson-repeated-bom) | 0, 1 or 2 marks crossed with read caps 1, 2 and 100 | 0/4 | 4/4 | 4/4 | 4/4 |
| [Commons Codec #135](../../examples/358-commons-codec-partitioned-base16) | 256 words over 0, 1, A and F times eight partitions, plus three ten-character schedules | 0/6 | 6/6 | 6/6 | 6/6 |

## What changed on the public path

- **Guava #8509.** Two counts of 2³⁰ yielded size 2³¹−1, lookup −2³¹ and an exception from the first entry on the parent. All three observers yield 2³¹−1 on the fix. An absent key stays at zero and mutating a backing count updates both observers of the same live view from six to seven. The existing live-view and iterator support already covered the backing objects, saturated addition, empty iteration and exhaustion.
- **Commons Lang #1719.** An initial two-unit cut of a😀b left [0061,D83D] on the parent and [0061] on the fix. The opposite cut discarded a lone low surrogate on the fix. At abbreviation width four, the parent kept D83D before the three dots and the fix returned only the dots. An intact pair and width five are preserved. Exact UTF-16 operations now follow complete code points and snapshot a selected char array range. The fixed mixed string is symbolic. The fixed full-domain result uses 1,515 separately checked native call sites. A single unsplit fixed-side proof reaches its 60-second deadline.
- **Avro #3878.** With capacity five and logical length three, the parent had position/limit/capacity/remaining (0,5,5,5) and read 4 at index 3. The fix had (0,3,5,3) and threw IndexOutOfBoundsException. Both returned the prefix 1, 2, 3 with position zero. The nested converter is scored separately from the real JobConf(false) factory. Class intake now checks the actual source and bytes selected by the subject JVM for declared dependency overlaps. Both historical closures contain 124 entries and seven differing package metadata classes. The native checker also found a parent witness through the public nested converter. At capacity one and logical length zero, the parent left byte 1 readable. The fixed converter rejected index zero and kept capacity one. The native candidate reproduced on the original parent JVM at the ambient entry. The native checker also decided all eight factory obligations after the four-root startup. The original parent reproduced both factory violations on a fresh JVM.
- **Gson #3034.** For every decimal suffix after 2⁶⁴, the parent threw MalformedJsonException at peek(). The fix returned NUMBER and the same reader returned all 21 original characters. Both revisions accept 10 and reject 00 and 01. The selected char-array range now constructs an immutable String snapshot. The existing arithmetic and reader models handled the signed 64-bit wrap and the separate overflow flag.
- **Gson #3137.** With two leading marks and cap one or two, the parent returned foo and the fix returned FEFF followed by foo. Cap 100 and a plain StringReader preserve the second mark on both revisions. Every read length is in the JVM control logs. The same String snapshot repair used for Gson #3034 covers the second historical JsonReader unchanged. The real reader supplies its short-read schedule and its own buffer compaction.
- **Commons Codec #135.** Decoding 4142434445 with writes at offsets 0, 3 and 7 yielded ABCD on the parent and ABCDE on the fix. A single write and a 2+4+4 schedule yielded ABCDE on both. The public stream receives the same source array for every write. The same style of a stateful public caller and independent end observation transfers from the Gson reader. This case additionally needed the selected JDK output-stream and byte-array growth bytecode.

The 17 deliberately wrong primary results and five transfer controls were all rejected. They include a wrapped count, a dropped UTF-16 unit, exposure of a byte beyond the logical limit, loss of the original decimal spelling or second mark, and loss of the carried half-byte. The raw parent and fix output, return/exception projections, ordered JAR and class hashes, selected upstream XML and each claim’s evidence are linked from the scorecard. [Independent domain and control generator](../../lib/benchmark/organic-java/domains.py)

## Conditional transfer cases

The original Eclipse Collections BooleanArrayListTest.addAllAtIndexOne and JavaParser NodeTest$PostOrderIteratorTest.rootHasNoChild each failed on the parent and passed on the fix. Both projects built with JDK 17 and their public-call grids ran on JDK 21.

| Case | Bounded inputs | Baseline strict native | Current strict native | Current finite JVM |
|---|---|---:|---:|---:|
| [Eclipse Collections #1434](../../examples/359-eclipse-boolean-list-insertion) | 2,865 combinations of original and inserted Boolean lists and insertion indices | 0/8 | 8/8 | 8/8 |
| [JavaParser #4538](../../examples/360-javaparser-postorder-root) | An empty CompilationUnit and one with package com | 0/8 | 2/8 | 8/8 |

**Eclipse Collections #1434.** Inserting [false,true] at index zero into [true,false,true] threw IndexOutOfBoundsException on the parent. The fix returned true and produced [false,true,true,false,true]. Indices two and three succeed, and four throws, on both revisions. The baseline stopped in BitSet(int). Running the selected JDK BitSet bytecode proved the return over all 2,865 inputs and the preserved cases. The single symbolic content claim reached 60 seconds on both CaDiCaL and Bitwuzla. Checking every admitted selector against the original fixed bytecode established the exact size and contents in 121.4 seconds end to end, with 79.7 MiB peak native process RSS. Both parent properties have counterexamples replayed on the original JVM. [Current Eclipse confirmation and selector checks](../../verification/results/20261121-155348-repeat-organic-java-example-359-on-the-f/result.json)

**JavaParser #4538.** The parent threw `EmptyStackException` on an empty root in both `findAll(Node.class, POSTORDER)` and direct iterator traversal. The fix returns the same root once and leaves the iterator exhausted. Both revisions return the original name, package and root in order for package `com`. Two counterexamples found by the native checker reproduced on the original parent at input zero, without an observed initializer. These two refutations count at original scope. [Postorder replay](../../examples/360-javaparser-postorder-root/records/original-witnesses/postorder-parent) · [Iterator replay](../../examples/360-javaparser-postorder-root/records/original-witnesses/terminal-parent)

**All eight obligations were decided with `Node` startup observed.** On the original Temurin 21.0.13 JVM, `Node` read LF as the line separator and initialized 14 other application types. Each was compared with its state after independent initialization. From that state the verifier established six properties and refuted two. It ran the real JDK stack and vector, child-list wrappers, list callbacks and reflective casts. On the common verifier, the eight workflow checks took 30.3 seconds. Two fresh original-parent replays took another 4.8 seconds. The six establishments retain their startup condition. [Traversal results and ordinary-startup comparison](../../verification/results/20261121-155348-repeat-organic-java-example-360-on-the-f/result.json)

## Startup conditions and remaining native work

**JavaParser.** Ambient startup reaches `System.getProperty("line.separator")`. Observing only `LineSeparator` now preserves the actual enum constants and their aliases. With that narrower startup observation the native checker reaches `HashSet(Collection)` in the default printer configuration. [Ambient and enum-only comparison](../../verification/results/20261121-120554-measure-the-two-remaining-javaparser-sta/result.json)

**Avro direct converter.** On both original revisions, a two-processor JVM with an empty environment and Unix root working directory initialized `org.apache.avro.Schema` followed by `org.apache.hadoop.io.BytesWritable`. The 197 application classes shared one table of 696 captured objects. Both revisions produced state digest `cf029b2245da586d4f1863ebbb7b117ec59433fccf3a4eee9eebdc70513413eb`. The verifier carried the reserved-set reference through the real Avro constructor, executed the JDK’s empty queue initialization and then ran the original Hadoop getters, Avro conversion and JDK buffer code. It established the fixed direct contract for all 21 capacity and logical-length pairs. The parent violated it at selector 1. A fresh JVM reproduced that input on the original parent with ambient startup. The independent replay establishes the parent refutation at original scope. [Native proof and original replay](../../verification/results/20261121-155347-prove-the-original-avro-factory-and-repl/result.json) · [Ambient witness](../../examples/355-avro-writable-buffer-limit/records/original-witnesses/direct-limit-parent/20261121T161139Z-0faa510d.json)

**Avro public factory.** All eight registered factory obligations were decided under one observed startup. The original JDK initialized `Schema`, `BytesWritable`, `JobConf` and Hadoop `Credentials`, in order, on two processors, with an empty environment and Unix root working directory. Both original 124-entry classpaths produced the same 220-class, 1,079-object state, `540f78ac686458dc4648b26cafe10fde211ffc3231f0965ce5fd67494e7cad64`. The verifier ran the original `new JobConf(false)`, factory construction, `create(BytesWritable.class)`, conversion, and public buffer observations. Bounds, readable prefix and the first rejected index each cover all 21 capacity/length pairs per revision. The separately frozen full-length control uses (5, 5). All six expected establishments and both expected refutations were reached. [Factory proofs and fresh JVM replays](../../verification/results/20261121-155347-prove-the-original-avro-factory-and-repl/result.json)

The JVM observed only null values in Hadoop's weak registry. A weak key can disappear while that fact holds. The checker followed the atomic deprecation context through the actual Commons Collections wrappers to two HashMaps with 178 and 176 String keys. It then executed the selected JDK's fresh properties, empty overlay copy and entry iteration, and preserved the logical limit of the returned buffer. The private table operations and constructor fence are qualified on Temurin 21.0.13 and 25.0.5. The table read requires a known in-bounds index. The successive earlier stops are retained. [Weak registry](../../verification/results/20261121-145625-follow-the-original-avro-factory-through/result.json) · [Configuration startup](../../verification/results/20261121-151148-verify-the-real-avro-factory-with-its-ob/result.json) · [Property lookup](../../verification/results/20261121-153140-check-avro-factory-lookups-using-the-cap/result.json)

**Avro at original scope.** Both factory violations reproduced at selector 1. A parent buffer with one physical byte and zero logical bytes exposes byte 1 at index zero. The fixed buffer has limit zero, capacity one and position zero, and its absolute read throws. Together with the nested converter, three parent obligations now have an independently reproduced original-scope refutation. All seven universal native results retain a startup condition. With ordinary startup, strict native checking stops at Hadoop `Configuration.<clinit>` on the factory path and Avro `Schema.<clinit>` on the direct path. [Bounds witness](../../examples/355-avro-writable-buffer-limit/records/original-witnesses/bounds-parent/20261121T161103Z-ef6f61a9.json) · [Rejected-index witness](../../examples/355-avro-writable-buffer-limit/records/original-witnesses/rejected-parent/20261121T161111Z-621950ab.json) · [Ordinary native and finite confirmation](../../verification/results/20261121-155347-repeat-organic-java-example-355-on-the-f/result.json)

## Measured cost

| PR | Build setup, s | Named tests, s | Native workflow, s | Finite JVM workflow, s | Additional native checks and replays, s | SAT search, s | Peak native step, MiB | Peak finite step, MiB | Adapter lines |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Guava #8509 | 112.3 | 76.3 | 9.9 | 14.6 | 0.0 | 0.039 | 150.6 | 137.6 | 80 |
| Commons Lang #1719 | 106.1 | 55.4 | 78.4 | 22.0 | 77.2 | 0.542 | 983.5 | 222.1 | 55 |
| Avro #3878 | 196.6 | 53.2 | 77.9 | 52.3 | 127.4 | 0.018 | 1380.1 | 510.4 | 66 |
| Gson #3034 | 88.7 | 57.2 | 9.0 | 11.2 | 0.0 | 0.001 | 176.2 | 129.0 | 44 |
| Gson #3137 | 90.0 | 60.5 | 5.4 | 6.6 | 0.0 | 0.009 | 132.2 | 119.8 | 55 |
| Commons Codec #135 | 88.7 | 36.5 | 8.7 | 14.9 | 0.0 | 0.462 | 574.8 | 196.0 | 60 |
| Eclipse Collections #1434 | 258.8 | 128.5 | 126.4 | 103.1 | 130.1 | 49.067 | 842.9 | 306.3 | 73 |
| JavaParser #4538 | 87.7 | 65.3 | 10.2 | 13.4 | 35.1 | 0.000 | 185.6 | 145.4 | 47 |

Build setup and the named test times come from the pinned original Maven builds on both revisions. The two workflow columns measure the current standard checks, including preparation and JVM controls. The additional column measures the managed selector or startup checks and their original witness replays. Peak memory is the largest measured managed step on the corresponding route. SAT search sums the instrumented native search for the accepted results, including the separately scoped proofs. Durations exclude queue wait and release compilation. [Per-claim times and evidence](../../verification/organic-java-pr-campaign.json)

The eight original Avro factory checks took 85.2 seconds under the recorded startup. Replaying the two candidates at their original factory entries took another 14.8 seconds. The measured peak was 1,380.1 MiB. The nested converter checks and their independent parent replay took a further 27.4 seconds. [Managed timing and memory](../../verification/results/20261121-155347-prove-the-original-avro-factory-and-repl/result.json)

## Reproduction

Regenerate the independent domains without changing them and recount the saved receipts with the following commands.

```sh
python3 lib/benchmark/organic-java/domains.py --check
python3 lib/benchmark/organic-java/report.py --check
python3 examples/tools/build.py --plan 354
python3 examples/tools/targets/workflow_handoff.py handoff 355 --markdown
```

The selector replay workflow accepts an interpreter-produced native selector candidate only after a fresh JVM executes the exact admitted input on the original artifact. The Eclipse parent return and contents at input 940 exercise this route. The scorecard links these additional JVM replays under `nativeSelectorJVMReplays`.

The original Maven recipes, historical toolchain pins and normal workflow entry points are recorded with the corpus. [Reproduction notes](../../lib/benchmark/organic-java/README.md)
