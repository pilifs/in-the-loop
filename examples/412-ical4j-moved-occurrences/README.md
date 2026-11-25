# ical4j associates moved occurrences with their recurrence IDs

The fix retained both the timed and all-day July 14 occurrences and removed the original timed July 15. With two moved events, the fix returned only B for input order A,B and both replacements for B,A.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 412` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/ical4j/ical4j/pull/931)
