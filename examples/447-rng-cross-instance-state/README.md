# Commons RNG restores an integer sequence and its cached booleans

| History | Observed result |
|---|---|
| Intent | A never-saved recipient rejected the parent checkpoint and kept its original continuation. The merged recipient produced the donor’s next ten integers. |
| Control | Saving and restoring the same generator reproduced all ten integers on both revisions. |
| Challenge | After restoring the cached third-bit position, the fresh and 19-draw recipients matched all 35 booleans and the following integer (−1705591924). |

The donor and recipient checkpoints belong to the same revision. The independent reference extracts low-order bits from java.util.Random.nextInt(). The historical JDK 8 supplies both the application and the class-loading records.

Run `python3 examples/tools/build.py 447` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/apache/commons-rng/pull/65) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
