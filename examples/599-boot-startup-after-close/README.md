# Startup callbacks after a context has closed

Records lifecycle notifications, runner calls and dependency creation after synchronous close.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `inactive:[runner]:1` | `inactive:[]:0` | matched |
| Control | `active:[started, runner, ready]:0` | `active:[started, runner, ready]:0` | matched |
| Challenge | `inactive:[started, runner]:1` | `inactive:[started]:0` | matched |

Replay with `python3 examples/tools/build.py 599` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52310)
