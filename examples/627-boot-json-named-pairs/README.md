# Named JSON pair members retain their object boundary

Parses named and unnamed pair groups, including empty input and same-named values in distinct object scopes.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `invalid-json` | `{"version":1,"pairs":{"a":"A","b":"B"}}` | matched |
| Control | `{"version":1,"a":"A","b":"B"}` | `{"version":1,"a":"A","b":"B"}` | matched |
| Challenge | `throws java.lang.IllegalStateException` | `{"version":1,"pairs":{"version":2}} / {"version":1,"pairs":{}}` | matched |

Replay with `python3 examples/tools/build.py 627` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52522)
