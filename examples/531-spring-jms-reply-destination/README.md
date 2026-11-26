# Request a JMS reply on a caller-owned queue

An embedded Artemis responder acknowledged both object- and name-addressed requests through the caller's reply queue. An independent exchange on the same queue then delivered C.

The existing overload returned its acknowledgement via a temporary queue on both revisions. The broker ran in-process with finite receives and one outstanding request.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · owned | `absent` | `replies:ack-A` | matched |
| Control · temporary | `temporary:ack-A` | `temporary:ack-A` | matched |
| Challenge · repeat | `absent` | `replies:ack-A/replies:ack-B/C` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 531` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36162)
