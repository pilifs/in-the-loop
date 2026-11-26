# Request a JMS reply on a caller-owned queue

An embedded Artemis responder acknowledged both object- and name-addressed requests through the caller's reply queue. An independent exchange on the same queue then delivered C.

The existing overload returned its acknowledgement via a temporary queue on both revisions. The broker ran in-process with finite receives and one outstanding request.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · owned | `absent` | `replies:ack-A` | matched |
| Control · temporary | `temporary:ack-A` | `temporary:ack-A` | matched |
| Challenge · repeat | `absent` | `replies:ack-A/replies:ack-B/C` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 531` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36162)

Spring JMS 7.0.4 applies a correlation selector to the caller-owned queue. Uncorrelated replies remained there, and the same caller timed out. Copying the assigned message ID or an explicit request correlation ID into each reply restored ack-A, ack-B, and the subsequent marker C on Artemis. [Campaign release checks](../../verification/merged-pr-links/q01-q30/upstream.md) · [Release and later-revision evidence](../../llm-dlc/loops/spring-framework-pr-links-q01-q30-brief-results.md#published-versions-and-the-later-factory)
