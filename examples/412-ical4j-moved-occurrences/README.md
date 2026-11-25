# ical4j associates moved occurrences with their recurrence IDs

The fix retained both the timed and all-day July 14 occurrences and removed the original timed July 15. With two moved events, the fix returned only B for input order A,B and both replacements for B,A.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

The order-dependent loss persists on `develop` at `2c5ff9f211a8`. Published 4.4.0 predates #931 and returned the original masters in both orders. The later half-open query contract changed the midnight control, while both moved meetings fall inside the noon challenge window. [Upstream report and reproduction](../../verification/merged-pr-links/upstream/README.md#ical4j--reordering-two-distinct-recurrence-overrides-drops-a-meeting)

Run `python3 examples/tools/build.py 412` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/ical4j/ical4j/pull/931)
