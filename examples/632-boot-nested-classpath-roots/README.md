# An executable JAR exposes each nested classpath root

Reads marker payloads from Spring’s wildcard resolver and the two independently enumerated library roots inside a real executable archive.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `missing-root` | `true:app` | matched |
| Control | `xml` | `xml` | matched |
| Challenge | `` | `first:A,second:B` | matched |

Replay with `python3 examples/tools/build.py 632` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52402)
