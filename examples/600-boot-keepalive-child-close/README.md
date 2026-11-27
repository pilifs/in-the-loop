# Closing a child context leaves the parent application alive

Observes process exit or a reply after the application main thread has returned, then closes the owning context.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `active:exited:0` | `active:reply:parent:0` | matched |
| Control | `inactive:exited:0` | `inactive:exited:0` | matched |
| Challenge | `active:exited:0` | `active:reply:sibling:0` | matched |

Replay with `python3 examples/tools/build.py 600` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52309)
