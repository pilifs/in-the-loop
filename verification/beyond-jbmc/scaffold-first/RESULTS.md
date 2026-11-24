# Original Java release comparisons

All 16 supplied callers ran on both original releases. On 54 registered inputs, seven primary observations changed across four projects and 47 held. All 54 unchanged controls held. With independent JVMs, the application verifier qualified all 16 primary questions and all 16 controls over those finite inputs. The first attempt qualified 22 of the 32 questions. Binding previously absent manifest JARs closed the other ten. Six cold, warm and clean comparisons agreed, and all six deliberately wrong primary expectations were refuted. [Released callers and exact registrations](registrations) · [Recomposed decisions and measurements](audit.json)

The table identifies what reached the first frozen artifact-only workflow, what the supplied caller covered, and where strict native stopped on the full original question at the class-name repair. Every row links the startup and class-loader investigation. The finite observations for ISCWT, Cactoos and OpenCensus cover the example inputs listed here. The full native proofs for ISCWT and Cactoos cover their larger domains.

| Package and release pair | Any frozen generated operation reached both JVMs | Finite inputs | Changed primary observations | Full supplied native primary |
|---|---|---:|---:|---|
| [Dirgra 0.3 → 0.4](scaffolds/01.json.gz) | Yes | 2 | 0 | Stopped at `ArrayList.equals` |
| [RE2/J 1.6 → 1.7](scaffolds/02.json.gz) | Yes | 3 | 2 | Stopped at the parser stack's `size` |
| [Sisu Plexus 0.3.4 → 0.3.5](scaffolds/03.json.gz) | Yes | 2 | 0 | Stopped at `Class.getAnnotation` |
| [Batik 1.17 → 1.18](scaffolds/04.json.gz) | Yes | 2 | 2 | Both original conjuncts reached incomplete unwinding in `HashMap.resize` |
| [UIMA CPE 2.10.2 → 2.10.4](scaffolds/05.json.gz) | Yes | 2 | 0 | Stopped at the SAX `AttributesImpl` constructor |
| [Parboiled 1.1.7 → 1.4.1](scaffolds/06.json.gz) | Yes | 13 | 0 | Stopped at `Arrays.binarySearch` |
| [Google Auto Common 0.10 → 1.1.2](scaffolds/07.json.gz) | No | 2 | 0 | Stopped at `URI.create` while constructing compiler inputs |
| [ISCWT 5.3.20100629 → 5.5.20131203](scaffolds/08.json.gz) | Yes | 5 | 0 | Proved the glyph question for all 1,024 widths |
| [Cactoos 0.49 → 0.54.0](scaffolds/09.json.gz) | Yes | 5 | 0 | Proved the sticky-scalar question for every Java int |
| [HtmlCleaner 2.24 → 2.29](scaffolds/10.json.gz) | Yes | 2 | 2 | Incomplete unwinding in `HashMap.resize` at 16 |
| [Headius Options 1.4 → 1.7](scaffolds/11.json.gz) | No | 4 | 0 | Stopped at `System.getProperty` |
| [Jackson Jr 2.13.0 → 2.14.0](scaffolds/12.json.gz) | Yes | 2 | 1 | Stopped at an array copy over summarized cells |
| [OpenCensus 0.24.0 → 0.26.0](scaffolds/13.json.gz) | Yes | 4 | 0 | Stopped at `List.equals` on the all-int question |
| [Auto64To32F 1.4 → 2.1](scaffolds/14.json.gz) | No | 2 | 0 | Stopped at `Paths.get` |
| [Annotation Indexer 1.17 → 1.18](scaffolds/15.json.gz) | No | 2 | 0 | Stopped at `Paths.get` |
| [dom4j 2.1.3 → 2.1.4](scaffolds/16.json.gz) | Yes | 2 | 0 | Original release conjuncts stopped during factory startup |

## Automatic discovery after disclosure

The original cold result remains 0/16. On the unchanged artifact-only operator, all 64 original generated candidates plus four calibration candidates were accounted for on the class-name repair. The previous incorrect Sisu difference became a verified equality. All four original calibration witnesses remained reproducible. dom4j's first repeat stopped when impact selection differed. The recovery keeps the new ranking and measures displaced original callers separately when needed. [Candidate-level comparison](audit.json) · [dom4j selection and repeat](remeasured/16/comparison.json.gz)

The new resource generator received only neutral deployment JARs and the JDK. On the previously disclosed panel it recovered Annotation Indexer's nominated public entry, its merged set of names, duplicate handling, and the empty unrelated-annotation control. It also discovered Batik's service iterator, a different observation from the registered PNG question. The two generated callers ran on the real released implementations, with one resource root and both orders of two roots. All 60 populated original JVM trials matched their registered predictions. Four generated public claims were established and both wrong primaries were refuted. Fourteen packets stopped at candidate discovery because their primary libraries lacked either supported entry shape. [Annotation Indexer](resource-discovery/15/candidate-1/scaffold.json) · [Batik](resource-discovery/04/candidate-1/scaffold.json)

The three symbolic engines received the same two generated callers, with an unchanged control and an inverse on each of the four deployments. Strict native stopped at `Paths.get` during fixture creation. Integrated JBMC timed out. Stock JBMC reported incomplete unwinding at the campaign bound. These twelve symbolic comparisons did not qualify a decision. The application results above come from repeated original-method entry and finite JVM observations. [All four recorded symbolic profiles](resource-comparators)

## JVM and cache boundaries

Batik's old loader consulted its parser properties and multiple service descriptors. dom4j's old factory had been constructed under the wrong name by the relocated harness. Separate, original classpaths recovered the result for both projects. The manifest control observed byte 0 with the optional JAR absent, then byte 82 when it appeared. The warm plan stayed open until that provider had an explicit position. The resumed and clean plans then refuted preservation. Restoring the original deployment restored its exact positive cache hit. [Manifest qualification and witnesses](manifest-controls/summary.json)

The old strict checker also accepted a false equality for resource bytes 65 and 66. On the compensating reader, both original releases returned 65, but the old combined JVM confirmed an incorrect 66-versus-65 counterexample. The two errors came from using the current deployment's resource classpath during an old call. [Archived original false proof](native-resource/pre-repair.json) · [Incorrect counterexample and both original observations](native-resource/pre-repair-compensation.json)

## Prospective intake

The disjoint population contains 85 release pairs from 48 projects across five signed Ubuntu base releases. Its seed, exposure exclusions, checker and selection policy were fixed before binary screening. Eighteen candidates were screened. Thirteen had qualifying executable public methods on both original binaries, and all 26 JARs were reverified. No candidate yet has both source archives locally or a registered primary observation. The next randomly ranked package is absent from the local archive after several dozen targeted archive acquisitions. The private intake records each stopping point without opening the candidates to the evaluator. The new 16-pair selection is incomplete and has no score. [Public commitments and intake counts](prospective.json)
