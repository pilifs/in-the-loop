# Read exactly the remaining bytes of stored and deflated JAR entries

Reads well-formed stored and deflated entries through the public nested-JAR API and compares suffixes and EOF with the JDK.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `EOFException` | `true:true` | matched |
| Control | `true:true/true:true` | `true:true/true:true` | matched |
| Challenge | `EOFException/true:true` | `true:true/true:true` | matched |

Replay with `python3 examples/tools/build.py 629` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52285)
