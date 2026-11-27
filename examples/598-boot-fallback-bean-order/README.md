# Auto-configuration ordering still determines which fallback bean wins

Reads the count and identity of conditional beans, including a transitive ordering dependency and reversed input.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `1:preferred` | `1:preferred` | matched |
| Control | `1:fallback` | `1:fallback` | matched |
| Challenge | `1:preferred:bridge/1:preferred:bridge` | `1:preferred:bridge/1:preferred:bridge` | matched |

Replay with `python3 examples/tools/build.py 598` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51867)
