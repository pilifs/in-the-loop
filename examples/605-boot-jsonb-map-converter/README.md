# Let JSON-B handle JSON maps when Kotlin Serialization is present

Checks Kotlin map eligibility and selects the first JSON writer from the actual client and server lists, then parses their bytes.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `true:true` | `false:true` | matched |
| Control | `true:false` | `true:false` | matched |
| Challenge | `throws org.springframework.http.converter.HttpMessageNotWritableException` | `jsonb:7/jsonb:7` | matched |

Replay with `python3 examples/tools/build.py 605` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52304)
