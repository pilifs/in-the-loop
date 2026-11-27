# Graceful shutdown drains requests after a web server restarts

Runs the same blocking servlet over real Tomcat and Jetty loopback ports. Records completed requests at the shutdown callback and each response body.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `REQUESTS_ACTIVE@0:[200:finished]/REQUESTS_ACTIVE@0:[200:finished]` | `IDLE@1:[200:finished]/IDLE@1:[200:finished]` | matched |
| Control | `IDLE@1:[200:finished]/IDLE@1:[200:finished]` | `IDLE@1:[200:finished]/IDLE@1:[200:finished]` | matched |
| Challenge | `REQUESTS_ACTIVE@0:[200:finished, 200:finished]/REQUESTS_ACTIVE@0:[200:finished, 200:finished]` | `IDLE@2:[200:finished, 200:finished]/IDLE@2:[200:finished, 200:finished]` | matched |

Replay with `python3 examples/tools/build.py 607` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52162)
