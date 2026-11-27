# Apply topology refresh to a Redis cluster supplied by a bean

Reads topology refresh options from the Boot-managed Lettuce factory for two bean forms and the property-driven cluster.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `plain/plain` | `cluster:30/cluster:30` | matched |
| Control | `cluster:30` | `cluster:30` | matched |

Replay with `python3 examples/tools/build.py 612` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52190)
