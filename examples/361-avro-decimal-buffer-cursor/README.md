# Repeated Avro decimal conversion over a caller-owned buffer window

Avro #729 changes how a decimal conversion reads bytes from a caller’s buffer. Each of the 12 inputs starts inside the backing array. One check observes the caller’s position and limit after the first conversion. A second checks the signed unscaled integer and scale from two calls on the same buffer. [Upstream change](https://github.com/apache/avro/commit/ce9032a4123e262341a3e746e6eb2b8476eae1ae)

The independent oracle decodes each window in Python. The driver reports the original Java results, including the exception from a second read on the parent. [Frozen input and result table](controls/table.json) · [Verification tasks](target.json)

The original JVM reproduced both parent failures without early initialization. Under the registered two-class startup the native checker also establishes both fixed properties. [Native proofs and original witnesses](../../verification/results/20261122-001142-prove-avro-729-decimals-and-replay-its-o/result.json) · [Finite and ordinary-startup results](../../verification/results/20261122-001142-confirm-the-ordinary-avro-729-native-and/result.json)
