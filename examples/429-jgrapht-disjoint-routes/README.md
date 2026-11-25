# JGraphT reconstructs three edge-disjoint routes in the original graph

Both algorithms recovered the expected three vertex sequences and weights. Both returned a 3→7 edge object absent from the input graph. The single-route control used only the original edges.


| Question | Input |
|---|---|
| Intent | Original graph, k=3. |
| Control | Same original graph, k=1. |
| Challenge | On the merge lower only 5→7 from 3 to 1 and request k=3 again. |

Run `python3 examples/tools/build.py 429` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/jgrapht/jgrapht/pull/792) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
