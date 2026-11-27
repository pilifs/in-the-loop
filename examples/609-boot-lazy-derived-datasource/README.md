# Derive a migration data source through a lazy connection proxy

Checks derived-pool settings and reads a seeded row through real H2 connections behind one or two transparent wrappers.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `throws org.springframework.boot.jdbc.UnsupportedDataSourcePropertyException` | `true:migration:fixture:true` | matched |
| Control | `true:migration:fixture:true` | `true:migration:fixture:true` | matched |
| Challenge | `throws org.springframework.boot.jdbc.UnsupportedDataSourcePropertyException` | `73/73` | matched |

Replay with `python3 examples/tools/build.py 609` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50271)
