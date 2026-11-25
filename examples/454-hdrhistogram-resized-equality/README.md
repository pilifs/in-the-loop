# HdrHistogram compares samples after growth and reset

| History | Public observation |
|---|---|
| Intent | Each histogram reported exactly one count at (2⁶² − 1). The larger receiver threw ArrayIndexOutOfBoundsException on the parent and returned true on the merge. The smaller receiver returned true on both. |
| Control | Reordered observations compared equal both ways. After recording a second 20 in B, totals were 3 and 4 and both comparisons returned false. |
| Challenge | Both totals were four and both ranges were 10–40. The counts at 20 and 30 were 2 and 0 in A and 0 and 2 in B. Both revisions returned false in both directions. |

Both histograms use the auto-resizing three-digit constructor. Each equality call is observed independently, so an exception on the larger receiver cannot hide the reverse result.

Run `python3 examples/tools/build.py 454` with the prepared `merged-pr-links-n01-n05` cache. Each revision and history starts a fresh JVM with the same compiled caller. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observations](observations.json) · [Upstream PR](https://github.com/HdrHistogram/HdrHistogram/pull/145) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-setup.md)
