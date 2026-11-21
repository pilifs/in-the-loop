# Six upstream Java fixes on their original bytecode

The six parent regressions reproduced on Temurin 21.0.13. All eight named upstream test methods failed on the parent and passed on the landed revision. Every fixed public-call observation matched an independent oracle across **3,658 input rows per revision**. Strict native verification advanced from **17/46 to 36/46 obligations** and from **one to five complete PRs**. Finite JVM verification advanced from **36/46 to 46/46** and covered all six. No accepted formal outcome disagreed with the original JVM. [Recountable scorecard](../../verification/organic-java-pr-campaign.json)

The baseline was `5e41cd71ab872a626179c02914aaae9f812c2c8c`. The six final jobs used `12229ff68f95c60cd1b7e5f36f6d1a587937e89f` and checker SHA-256 `8a4891a9c50c7f2bd62410d871c3f3f7e7289c047b13c6a99a301cb241bd4563`. A strict decision requires the frozen contract, a non-vacuous proof or a counterexample reproduced on the original JVM. Each count includes both revisions and the preservation obligations. Two transfer cases are reported separately. [Baseline fingerprint](../../lib/benchmark/organic-java/baseline.json)

## Original scope and outcomes

| Original PR | Independent inputs | Baseline native | Final native | Baseline finite | Final finite |
|---|---|---:|---:|---:|---:|
| [Guava #8509](../../examples/353-guava-saturated-sum) | 49 pairs of counts from the seven registered values | 10/10 | 10/10 | 10/10 | 10/10 |
| [Commons Lang #1719](../../examples/354-commons-lang-surrogate-cuts) | 1,515 windows on all 31 strings of 0–4 tokens, 36 cuts on a fixed mixed string, and abbreviation widths 4 and 5 | 2/10 | 10/10 | 10/10 | 10/10 |
| [Avro #3878](../../examples/355-avro-writable-buffer-limit) | 21 combinations of capacity 0–5 and logical length 0–capacity | 0/10 | 0/10 | 0/10 | 10/10 |
| [Gson #3034](../../examples/356-gson-overflowing-number) | 10 overflow literals plus 10, 00 and 01 | 5/6 | 6/6 | 6/6 | 6/6 |
| [Gson #3137](../../examples/357-gson-repeated-bom) | 0, 1 or 2 marks crossed with read caps 1, 2 and 100 | 0/4 | 4/4 | 4/4 | 4/4 |
| [Commons Codec #135](../../examples/358-commons-codec-partitioned-base16) | 256 words over 0, 1, A and F times eight partitions, plus three ten-character schedules | 0/6 | 6/6 | 6/6 | 6/6 |

## What changed on the public path

- **Guava #8509.** Two counts of 2³⁰ yielded size 2³¹−1, lookup −2³¹ and an exception from the first entry on the parent. All three observers yield 2³¹−1 on the fix. An absent key stays at zero and mutating a backing count updates both observers of the same live view from six to seven. The existing live-view and iterator support already covered the backing objects, saturated addition, empty iteration and exhaustion.
- **Commons Lang #1719.** An initial two-unit cut of a😀b left [0061,D83D] on the parent and [0061] on the fix. The opposite cut discarded a lone low surrogate on the fix. At abbreviation width four, the parent kept D83D before the three dots and the fix returned only the dots. An intact pair and width five are preserved. Exact UTF-16 operations now follow complete code points and snapshot a selected char array range. The fixed mixed string is symbolic. The fixed full-domain result uses 1,515 separately checked native call sites. A single unsplit fixed-side proof reaches its 60-second deadline.
- **Avro #3878.** With capacity five and logical length three, the parent had position/limit/capacity/remaining (0,5,5,5) and read 4 at index 3. The fix had (0,3,5,3) and threw IndexOutOfBoundsException. Both returned the prefix 1, 2, 3 with position zero. The nested converter is scored separately from the real JobConf(false) factory. Class intake now checks the actual source and bytes selected by the subject JVM for declared dependency overlaps. Both historical closures contain 124 entries and seven differing package metadata classes. Native startup reaches Hadoop Configuration from the factory and Avro Schema from the direct route. Observing startup exposes System.getenv and Runtime.availableProcessors respectively.
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

**Eclipse Collections #1434.** Inserting [false,true] at index zero into [true,false,true] threw IndexOutOfBoundsException on the parent. The fix returned true and produced [false,true,true,false,true]. Indices two and three succeed, and four throws, on both revisions. The baseline stopped in BitSet(int). Running the selected JDK BitSet bytecode proved the return over all 2,865 inputs and the preserved cases. The single symbolic content claim reached 60 seconds on both CaDiCaL and Bitwuzla. Checking the original fixed bytecode on every admitted selector established the exact size and complete list contents in 129.6 seconds, with about 90.6 MiB peak native RSS. Both parent properties have counterexamples replayed on the original JVM.

**JavaParser #4538.** The parent threw `EmptyStackException` on an empty root in both `findAll(Node.class, POSTORDER)` and direct iterator traversal. The fix returns the same root once and leaves the iterator exhausted. Both revisions return the original name, package and root in order for package `com`. Two counterexamples found by the native checker reproduced on the original parent at input zero, without an observed initializer. These two refutations count at original scope. [Postorder replay](../../examples/360-javaparser-postorder-root/records/original-witnesses/postorder-parent) · [Iterator replay](../../examples/360-javaparser-postorder-root/records/original-witnesses/terminal-parent)

**All eight obligations were decided with `Node` startup observed.** On the original Temurin 21.0.13 JVM, `Node` read LF as the line separator and initialized 14 other application types. Each was compared with its state after independent initialization. From that state the verifier established six properties and refuted two. It ran the real JDK stack and vector, child-list wrappers, list callbacks and reflective casts. The eight workflow checks took 26.1 seconds on verifier `7dc35cf64662`. Two fresh JVM replays of the original parent claims took another 4.6 seconds. The six establishments retain their startup condition. [Traversal results](../../verification/results/20261121-120554-recheck-all-node-startup-claims-and-orig/result.json)

## Remaining native work

**JavaParser.** Ambient startup reaches `System.getProperty("line.separator")`. Observing only `LineSeparator` now preserves the actual enum constants and their aliases. With that narrower startup observation the native checker reaches `HashSet(Collection)` in the default printer configuration. [Ambient and enum-only comparison](../../verification/results/20261121-120554-measure-the-two-remaining-javaparser-sta/result.json)

**Avro.** Both fixed-side claims were rerun on the original 124-entry classpath over the 21 registered capacity and logical-length pairs. With two processors and an empty environment, factory startup reaches `File.getAbsoluteFile` in Hadoop `Configuration`. With two processors, the direct converter reaches a cross-class write. Initializing Avro `Schema` installs a `JsonProperties$1` instance in `Accessor.jsonPropertiesAccessor`. Initializing `Accessor` alone leaves it null. Native proofs still need the filesystem context for the factory and a faithful account of the shared static state for the direct route. The finite-JVM record covers all ten obligations. [Avro startup checks](../../verification/results/20261121-120341-avro-factory-and-nested-converter-with-m/result.json)

## Measured cost

| PR | Build setup, s | Named tests, s | Native workflow, s | Added selector workflow, s | Native solver, s | Peak native MiB | Peak finite JVM MiB | Handwritten adapter lines |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Guava #8509 | 112.3 | 76.3 | 10.1 | 0.0 | 0.047 | 80.9 | 101.6 | 80 |
| Commons Lang #1719 | 106.1 | 55.4 | 79.1 | 74.7 | 0.456 | 125.6 | 170.0 | 55 |
| Avro #3878 | 196.6 | 53.2 | 82.9 | 0.0 | 0.000 | 180.9 | 185.2 | 66 |
| Gson #3034 | 88.7 | 57.2 | 9.2 | 0.0 | 0.001 | 78.7 | 59.7 | 44 |
| Gson #3137 | 90.0 | 60.5 | 5.8 | 0.0 | 0.006 | 78.6 | 60.2 | 55 |
| Commons Codec #135 | 88.7 | 36.5 | 8.8 | 0.0 | 0.430 | 494.9 | 164.1 | 60 |
| Eclipse Collections #1434 | 258.8 | 128.5 | 125.6 | 129.6 | 47.733 | 404.2 | 222.6 | 73 |
| JavaParser #4538 | 87.7 | 65.3 | 10.1 | 0.0 | 0.000 | 79.3 | 61.0 | 47 |

Setup is the sum of the recorded original Maven build, prerequisite and classpath steps on both sides. Named tests include their recorded Maven execution. The native workflow column includes preparation, normal verification and replay. Additional native-selector jobs have a separate wall-time column. Solver time sums instrumented native SAT search for the ordinary and selector results used in the score. Unsuccessful whole-domain attempts have their own timing in each task’s receipt. Peak RSS is the largest measured process RSS for that case. Human setup time and time spent waiting in the shared queue were unmetered.

## Reproduction

Regenerate the independent domains without changing them and recount the saved receipts with the following commands.

```sh
python3 lib/benchmark/organic-java/domains.py --check
python3 lib/benchmark/organic-java/report.py --check
python3 examples/tools/build.py --plan 354
python3 examples/tools/targets/workflow_handoff.py handoff 355 --markdown
```

The selector replay workflow at `b39bf642d33d01c933a638da1042293213cac2ff` accepts an interpreter-produced native selector candidate only after a fresh JVM executes the exact admitted input on the original artifact. The Eclipse parent return and contents at input 940 exercise this route. The scorecard links these additional JVM replays under `nativeSelectorJVMReplays`.

The original Maven recipes, historical toolchain pins and normal workflow entry points are recorded with the corpus. [Reproduction notes](../../lib/benchmark/organic-java/README.md)
