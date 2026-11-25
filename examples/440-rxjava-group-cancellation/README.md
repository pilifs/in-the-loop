# RxJava restores discarded group demand and respects the survivor’s limit

Cancelling the stalled group now delivers 4 through 8 and completes the survivor and outer stream. With one unit of demand the survivor waited for its next four requests.


| Question | Input |
|---|---|
| Intent | Cancel the stalled first group after the four-element prefetch. |
| Control | Give both groups unbounded demand from their first subscription. Perform no cancellation. |
| Challenge | Keep the original zero demand on group 0, but grant group 1 only one item initially. Cancel group 0 outside callbacks, read group 1, then request four more from it. |

Run `python3 examples/tools/build.py 440` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/ReactiveX/RxJava/pull/6895) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
