# A secondary entity manager rolls back flushed inserts in its own pool

Reads committed H2 state through separate connections after flushing and rolling back or committing a secondary persistence unit.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `1:0:present` | `0:0:absent` | matched |
| Control | `1:0:present` | `1:0:absent` | matched |
| Challenge | `1:0:present/0:0:absent` | `0:0:absent/0:0:absent` | matched |

Replay with `python3 examples/tools/build.py 610` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52824)
