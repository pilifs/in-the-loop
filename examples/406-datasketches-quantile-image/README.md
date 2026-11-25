# DataSketches restores the quantiles of a queried sketch

The parent changed the median from b to c and exposed six entries after a four-item round trip. The fixed heap and wrapped readers returned four ordered values, weights 1 through 4, median b and rank-0.55 value c.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 406` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/apache/datasketches-java/pull/767)
