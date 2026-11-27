# Resolving message codes from indexed bundle basenames

Reads codes from two indexed bundles, a scalar list and a single literal comma-bearing resource in an isolated loader.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `MISS/MISS` | `bar/bar-bar` | matched |
| Control | `bar/bar-bar` | `bar/bar-bar` | matched |
| Challenge | `MISS` | `MISS` | refuted |

Replay with `python3 examples/tools/build.py 595` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52904)
