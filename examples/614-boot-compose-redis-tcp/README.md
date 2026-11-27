# Redis connection details select the TCP port when UDP is also published

Reads the Redis endpoint chosen from actual loopback TCP and UDP publications and sends a PING to the advertised TCP listener.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `udp:no-tcp-listener` | `tcp:PONG` | matched |
| Control | `tcp:PONG` | `tcp:PONG` | matched |
| Challenge | `udp:no-tcp-listener/udp:no-tcp-listener` | `tcp:PONG/tcp:PONG` | matched |

Replay with `python3 examples/tools/build.py 614` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52832)
