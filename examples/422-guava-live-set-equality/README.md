# Guava avoids traversal for impossible live-set equality

Both JRE and Android returned false with one backing iterator call on the parent and zero on the fix. Symmetry, same-size mismatches and live equality after backing-set mutation held on both pins.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Both the JRE and Android library variants run on the same JVM.

Run `python3 examples/tools/build.py 422` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/google/guava/pull/7784)
