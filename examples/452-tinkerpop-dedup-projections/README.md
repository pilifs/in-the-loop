# TinkerPop rejects a second projection on one dedup step

| History | Observed result |
|---|---|
| Intent | Two projections on one dedup step returned all six Modern graph names on the parent. The merge threw IllegalStateException during the second by() call. |
| Control | One age projection returned josh, marko, peter and vadas, each once, on both revisions. |
| Challenge | Putting the name projection on its own dedup step restored a valid traversal with the same four people on both revisions. |

The application uses the embedded TinkerGraph built at the same commit as gremlin-core. It sorts the returned name multiset after iteration and separately records the phase of an exception.

Run `python3 examples/tools/build.py 452` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/apache/tinkerpop/pull/3105) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
