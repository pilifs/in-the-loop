# libGDX clips polygons into a fresh or reused output

| History | Observed result |
|---|---|
| Intent | For the stored float triangle, the parent threw with a fresh output and returned true with null. Both merged calls returned false and the output stayed empty. |
| Control | The contained rectangle produced four vertices and bounds (1,2,2,3) on each revision. |
| Challenge | On both revisions, successful reuse wrote the four correct local vertices but the bounds reader still returned the previous square (−4,−4,2,2). |

The caller snapshots all four bound values before reuse and compares local coordinate pairs independently of cyclic vertex order. The fresh-output control uses the same two input polygons.

Run `python3 examples/tools/build.py 451` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/libgdx/libgdx/pull/7278) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
