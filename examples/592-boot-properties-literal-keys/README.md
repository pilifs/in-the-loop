# Read escaped comment characters at the start of a property name

Reads the literal property names from Boot and the JDK over identical ASCII bytes.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `null,null,ok / hash,bang,ok` | `hash,bang,ok / hash,bang,ok` | matched |
| Control | `null,null,ok / null,null,ok` | `null,null,ok / null,null,ok` | matched |
| Challenge | `null,null,ok / hash,bang,ok` | `hash,bang,ok / hash,bang,ok` | matched |

Replay with `python3 examples/tools/build.py 592` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52207)
