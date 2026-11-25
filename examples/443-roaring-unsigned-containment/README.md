# RoaringBitmap checks a missing block and the unsigned upper endpoint

| History | Observed result |
|---|---|
| Intent | All three readers switched from accepting the missing B to rejecting it, with and without the later block. All three began accepting the complete top block. |
| Control | Heap, mutable and deserialized readers retained [0,B) after adding 3B. |
| Challenge | The first immutable snapshot kept both members. Adding zero kept the live range complete, removing −2 broke it, and the final snapshot counted one member. |

Each low-range triple gives heap, mutable buffer and independently serialized immutable results, in that order. B is 65,536 and the exclusive top endpoint is 2³².

Run `python3 examples/tools/build.py 443` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/RoaringBitmap/RoaringBitmap/pull/863) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
