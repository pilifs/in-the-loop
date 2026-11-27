# The PostgreSQL driver recovers a Compose database name exactly

Parses the JDBC URL supplied by a real Compose service. The driver returns the database name, timeout and application name independently.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `my db/30/my-app` | `my+db/30/my-app` | matched |
| Control | `database/30/my-app` | `database/30/my-app` | matched |
| Challenge | `my db/30/my-app;my+db/30/my-app` | `my+db/30/my-app;my%2Bdb/30/my-app` | matched |

Replay with `python3 examples/tools/build.py 615` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52625)
