# Malformed SSE retry hints preserve event delivery

The merge delivered both events after an invalid retry hint. It still accepted a trailing space as part of a 25 ms retry.

| History | Observation |
|---|---|
| Intent | At the public WebClient boundary the parent surfaced WebClientResponseException caused by NumberFormatException before delivering any payload. This refuted the registered outer exception type. The merge delivered foo and bar and completed. |
| Control | Both revisions attached 25 ms to foo and no retry to bar, preserving their order. |
| Challenge | The field rule predicts that a trailing space invalidates the hint. Both revisions attached 25 ms to foo for both space placements. |

The public observation records each ServerSentEvent envelope, the terminal signal, and both exception types when the stream fails.

With the prepared Spring cache, run `python3 examples/tools/build.py 466` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37193](https://github.com/spring-projects/spring-framework/pull/37193)
