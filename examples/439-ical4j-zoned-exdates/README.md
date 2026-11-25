# ical4j resolves UTC exceptions across the Paris daylight-saving change

The parent retained January 2 despite a UTC exception at its Paris start. The fix removed just that occurrence, kept an exception at its end harmless and switched to the summer offset on March 31.


| Question | Input |
|---|---|
| Intent | Expand the January event with the UTC exception on the second day. |
| Control | Replace the exception with January 2 at 09:00 UTC, the end of that day’s event. |
| Challenge | Move the first occurrence to March 30, 2024 at 09:00 Paris, retain the daily count and duration, and query March 30 through April 2 at UTC midnight. Compare March 31 exceptions at 07:00Z and at 08:00Z. |

Run `python3 examples/tools/build.py 439` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/ical4j/ical4j/pull/947) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
