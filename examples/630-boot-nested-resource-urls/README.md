# A URL for a nested resource with escaped ASCII opens the original entry

Opens each URL returned by the launched Boot class loader and compares its byte with the original library ZIP.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `FileNotFoundException/42` | `42/42` | matched |
| Control | `17/17` | `17/17` | matched |
| Challenge | `FileNotFoundException/42,FileNotFoundException/99` | `42/42,99/99` | matched |

Replay with `python3 examples/tools/build.py 630` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52280)
