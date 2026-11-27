# Restore an explicitly empty JVM property after a scoped override

Reads the callback value and the process property after a scoped override, including nested exceptional exit.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `temporary/default` | `temporary/empty` | matched |
| Control | `temporary/default;temporary/original` | `temporary/default;temporary/original` | matched |
| Challenge | `inner/true/temporary/default` | `inner/true/temporary/empty` | matched |

Replay with `python3 examples/tools/build.py 588` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52125)
