# Arrow reports the child interval and hash of a relocated list view

The nonzero-offset view changed from an empty reported child interval to [3,5). Relocating its two children now preserves the slot hash on both allocator backends.


| Question | Input |
|---|---|
| Intent | Inspect slot 1 and read the child values at all indices in its reported half-open interval. |
| Control | Inspect slot 0 at offset zero, length three. |
| Challenge | On the merge compare slot 1 with a slot in a separate vector whose child is [40,50] and whose valid view starts at zero with size two. Compare their objects and `hashCode(slot)` values using the default hasher. |

Run `python3 examples/tools/build.py 428` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are netty, unsafe. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/arrow-java/pull/1019) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
