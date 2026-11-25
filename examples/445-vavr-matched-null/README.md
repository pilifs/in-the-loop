# Vavr distinguishes a matched null from an empty search

| History | Observed result |
|---|---|
| Intent | Selecting the last null changed from an empty option with one fallback call to a defined null with zero calls. |
| Control | With no match the supplier ran once. Selecting odd numbers returned 3 and suppressed it on both revisions. |
| Challenge | Reordering null and 7 selected whichever came last. An additional rejected 4 left the choice and the zero callback count intact. |

Each search consumes a new iterator. The observation records presence, value and actual callback count.

Run `python3 examples/tools/build.py 445` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/vavr-io/vavr/pull/3272) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
