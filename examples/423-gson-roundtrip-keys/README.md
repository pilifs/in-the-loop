# Gson finds parsed numeric keys in a map

Equal boxed and parsed numbers missed a HashMap lookup on the parent and retrieved the saved value on the merge. Signed-zero replacement and removal used a single entry.


| Question | Input |
|---|---|
| Intent | Insert integer 42 and look up parsed JSON number 42. |
| Control | Insert numeric 42 and seek `new JsonPrimitive("42")`, then seek another integer 42. |
| Challenge | On the merge insert `new JsonPrimitive(-0.0)`, replace its value using parsed JSON `0`, and remove via `new JsonPrimitive(0L)`. |

Run `python3 examples/tools/build.py 423` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/google/gson/pull/3059) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
