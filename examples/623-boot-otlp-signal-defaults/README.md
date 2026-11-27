# Common OTLP settings reach the signal-specific exporters

Decodes three independently emitted protobuf signals after HTTP delivery and compares request paths, compression and all suite header values.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | Outside this replay | `/v1/logs:[common]:gzip:Hello//v1/traces:[common]:gzip:fixture-span//v1/metrics:[common]:gzip:springfixture=7` | matched |
| Control | `/explicit:[]:plain:Hello` | `/explicit:[]:plain:Hello` | matched |
| Challenge | Outside this replay | `/v1/logs:[logs]:plain:Hello//v1/traces:[common]:gzip:fixture-span//v1/metrics:[common]:gzip:springfixture=7` | matched |

Replay with `python3 examples/tools/build.py 623` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50461)
