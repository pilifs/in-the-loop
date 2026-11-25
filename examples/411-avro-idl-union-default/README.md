# Avro reads and prints defaults across union branch orders

The integer after a null branch changed from Java null and an IDL null initializer to Integer(1) and the literal 1. With the array default [1], both pins threw AvroRuntimeException from the field getter and the IDL writer when the int branch came first.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions.

Run `python3 examples/tools/build.py 411` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/apache/avro/pull/3709)
