# Derive a JDBC pool from the root exposed by its wrapper

Compares JDBC root identity and reads URL and user from the pool derived through each intermediate delegate.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `delegate` | `root` | matched |
| Control | `same` | `same` | matched |
| Challenge | `throws org.springframework.boot.jdbc.UnsupportedDataSourcePropertyException` | `jdbc:h2:mem:root/probe;jdbc:h2:mem:root/probe` | matched |

Replay with `python3 examples/tools/build.py 608` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51410)
