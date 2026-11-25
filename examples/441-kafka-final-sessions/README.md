# Kafka Streams admits the session close boundary and publishes one final count

At the grace boundary the parent dropped A at time 8 and emitted a provisional final A at time 3. The merged Streams topology accepted the boundary record and published only A@[0,5] with count two.

Each comparison uses Kafka Streams, clients, Connect modules and the test driver from its exact pin. Rebuilding all seven test-driver sources independently on the two locked classpaths produced identical driver JARs.

| Question | Input |
|---|---|
| Intent | Send key T at 10 ms to establish stream time, then the first record for key A at 8 ms. |
| Control | From separate clean starts after T@10, try the first A at 7 ms and at 9 ms. |
| Challenge | Send A@0 then T@3, inspect suppressed output for A, send A@5, then a different key U@25 to flush. Track every suppressed A record. |

Run `python3 examples/tools/build.py 441` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/apache/kafka/pull/6654) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

Run `python3 examples/441-kafka-final-sessions/setup/prepare.py` to restore the omitted test driver on a fresh setup. Its loaded provider is checked alongside the session aggregate. [Driver build](setup/prepare.py) · [Driver digests](setup/artifacts.sha256)
