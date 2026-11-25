# picocli dispatches through a registered child’s edited aliases

Ordinary aliases now dispatch and retire correctly. Registering the primary name itself as an alias and then clearing the alias removes the primary dispatch entry on the merge.


| Question | Input |
|---|---|
| Intent | After registration set `aliases("first")`, execute first, replace it with `aliases("second")`, then execute first and second. |
| Control | With no aliases, execute sub and then an unknown token. Repeat after attaching an ordinary distinct alias. |
| Challenge | On the merge add the primary name itself as an alias with `aliases("sub")`, then clear aliases using an empty string array. Compare to a fresh root that never had aliases. |

Run `python3 examples/tools/build.py 425` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/remkop/picocli/pull/1529) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

The same primary-name failure reproduced on picocli 4.7.7 and main at 10509c0af89a. VF-065 holds the runnable report. [Release and development evidence](../../verification/merged-pr-links/l01-l20/upstream/README.md)
