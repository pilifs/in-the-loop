# jOOλ finds window endpoints at finite frame bounds

Both jOOλ modules repaired the ordinary wide window and preserved the future-only control. Widening the upper bound to Long.MAX_VALUE minus one changed the fixed third row’s last value from 3 to 1.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. The two published module variants run separately on the same JDK.

Both 0.9.16 artifacts and both modules built from `main` at `9273e1f54356` returned (1,1) after the frame widened. The third row should retain the endpoints (1,3). [Upstream report and reproduction](../../verification/merged-pr-links/upstream/README.md#jooλ--widening-an-already-complete-window-changes-its-last-value)

Run `python3 examples/tools/build.py 419` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/jOOQ/jOOL/pull/418)
