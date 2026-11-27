# Choose which property-migration diagnostics stop startup

Pairs application startup with the migrator’s identified key for removed, renamed and mixed arguments.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `active:banner` | `migration-failed:banner` | matched |
| Control | `active:logging/active:logging/active:logging` | `active:logging/active:logging/migration-failed:logging` | matched |
| Challenge | `active:banner+logging/active:banner+logging` | `migration-failed:banner+logging/migration-failed:banner+logging` | matched |

Replay with `python3 examples/tools/build.py 596` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51855)
