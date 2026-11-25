# RoaringBitmap unions subtype arrays

Heap and buffer aggregation both threw ArrayStoreException on subtype arrays before the fix. Both fixed paths returned the 16-member union and preserved every input reference and element after permutation.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 405` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/RoaringBitmap/RoaringBitmap/pull/914)
