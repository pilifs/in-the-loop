# Logback writes an encoder header after every rotation

The active file after one rotation changed from BF to HBF. Two rotations on the fix produced HAF, HF and HBF from oldest to newest. Without rotation both pins wrote HABF.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 417` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/qos-ch/logback/pull/862)
