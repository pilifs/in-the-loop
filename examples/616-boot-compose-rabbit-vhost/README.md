# Connect to the RabbitMQ virtual host configured by Compose

Uses the classic broker and stream connection details from an owned Compose service. Reads an absent stream through the stream protocol.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `/:refused` | `app:open` | matched |
| Control | `/:open` | `/:open` | matched |
| Challenge | `/:refused//:refused` | `app:open/app:false` | matched |

Replay with `python3 examples/tools/build.py 616` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51940)
