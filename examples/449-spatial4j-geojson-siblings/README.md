# Spatial4j closes a MultiPoint before writing sibling values

| History | Observed result |
|---|---|
| Intent | Serializing a one-element MultiPoint list threw JsonGenerationException on the parent. The merge returned the expected array containing [[100,100]]. |
| Control | A list containing the constituent Point read back as [100,100] on both revisions. |
| Challenge | Both geometry orders survived the merge with their numeric coordinates, and the enclosing map retained the trailing sibling value 17. |

Each successful write is parsed by a fresh mapper without the geometry module. The observation preserves all fields and array positions while normalizing equivalent numeric spellings.

Run `python3 examples/tools/build.py 449` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/locationtech/spatial4j/pull/212) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
