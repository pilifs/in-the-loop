# The inspected byte count matches a writer’s slice

Checks the declared size against direct bytes, then verifies two regular TAR entries by reading their names, lengths and complete payloads.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `-1:test` | `4:test` | matched |
| Control | `4:test` | `4:test` | matched |
| Challenge | Outside this replay | `4102:true:marker:true:eof` | matched |

Replay with `python3 examples/tools/build.py 628` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52593)
