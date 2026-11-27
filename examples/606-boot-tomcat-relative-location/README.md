# Embedded Tomcat returns a relative redirect by default

Compares raw and resolved redirect locations at a fixed local target, including strict servlet mode in a fresh JVM.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `302:absolute:same` | `302:/login:same` | matched |
| Control | `302:absolute:same` | `302:absolute:same` | matched |
| Challenge | `false/302:absolute:same` | `false/302:/login:same` | matched |

Replay with `python3 examples/tools/build.py 606` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51173)
