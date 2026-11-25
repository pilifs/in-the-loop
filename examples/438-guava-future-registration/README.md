# Guava aggregates done and reentrant futures in input order

Both JRE and Android artifacts eliminated the callback registration on a completed future. The pending and reentrant repeated-input cases completed in input order on both pins.

Both published artifact variants ran on the same desktop JDK 21.

| Question | Input |
|---|---|
| Intent | A is done before construction, B completes afterward. |
| Control | Start with two pending futures and complete B first, then A. |
| Challenge | Use the same pending forwarding future twice in the input. On its first addListener call, complete the underlying future with X immediately before delegating that registration. |

Run `python3 examples/tools/build.py 438` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are jre, android. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/google/guava/pull/7277) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
