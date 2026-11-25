# Jackson routes an alias into an unwrapped record

| History | Observed result |
|---|---|
| Intent | The parent created the inner record with a null component. The merge bound Hello and preserved the outer sibling World!. |
| Control | The primary name c populated the child on both revisions. |
| Challenge | The merge emitted exactly the fields b and c, and the second record equalled the first. |

Both databind JARs came from the exact source pins. The expired Jackson core, annotations and parent/BOM snapshot inputs were rebuilt from the last upstream branch commits preceding the parent. Both deployments used the same replacements.

Run `python3 examples/tools/build.py 444` with the prepared `merged-pr-links-m01-m10` cache. The same compiled caller runs in a fresh JVM for each revision and history. [Predictions and refutations](comparison.json) · [Runtime lock](runtime.json) · [Caller](caller/PublicCaller.java) · [Recorded returns](observations.json) · [Upstream change](https://github.com/FasterXML/jackson-databind/pull/5913) · [Build provenance](../../llm-dlc/loops/organic-java-merged-pr-links-m01-m10-brief-setup.md)
