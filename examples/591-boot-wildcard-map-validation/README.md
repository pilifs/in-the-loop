# Binding a validated bean with wildcard map values

Reads a wildcard map through a validating binder and tests the enclosing bean’s concrete age constraint.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `unresolved-type` | `titi` | matched |
| Control | `validation:age` | `validation:age` | matched |
| Challenge | `unresolved-type/unresolved-type` | `validation:age/titi:10` | matched |

Replay with `python3 examples/tools/build.py 591` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50798)
