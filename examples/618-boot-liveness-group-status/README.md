# A custom liveness URL retains liveness-only membership

Reads the canonical liveness group, its alias and overall HTTP health while a separately registered indicator changes state.

Both sides use the same recorded MVC transport and dependencies from S33. The S31 and S33-fix MVC main source trees agree. The health implementation and its owning dependencies come first from each original S31 deployment.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `503:DOWN/503:DOWN/503:DOWN` | `200:UP/200:UP/503:DOWN` | matched |
| Control | `503:DOWN/503:DOWN/503:DOWN` | `503:DOWN/503:DOWN/503:DOWN` | matched |
| Challenge | `503:DOWN/503:DOWN/503:DOWN;200:UP/200:UP/200:UP` | `200:UP/200:UP/503:DOWN;200:UP/200:UP/200:UP` | matched |

Replay with `python3 examples/tools/build.py 618` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50296)
