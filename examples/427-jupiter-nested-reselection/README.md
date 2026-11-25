# Jupiter reselects inherited nested tests by unique ID

Class selection now executed the two distinct bodies once. Separate public Launcher requests using the saved unique IDs reran exactly their respective declaring classes.


| Question | Input |
|---|---|
| Intent | Class-select Sub with both nested classes present. |
| Control | Select Base itself without changing the class files. |
| Challenge | On the merge save both leaf IDs from Sub’s TestPlan. For each ID create a fresh launcher request using `selectUniqueId(id)`, reset the markers, then execute only that request. |

Run `python3 examples/tools/build.py 427` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/junit-team/junit-framework/pull/6104) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
