# Package versions from nested JARs without directory entries

Reads package metadata from the first real class load in a fresh executable, with and without a directory entry or a preceding failed optional lookup.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `null` | `1.2.3` | matched |
| Control | `1.2.3` | `1.2.3` | matched |
| Challenge | `null/null` | `1.2.3/null` | refuted |

Replay with `python3 examples/tools/build.py 631` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52244)
