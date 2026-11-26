# Rejecting conflicting generated-key and declared insert columns before execution

Overlapping generated and supplied columns now fail during compilation. Correcting that same insert after failure returned a key identifying the only Sven row.

The observer checks the failure type, declared column spelling, compiled state, table count and the row reached through the returned key.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · compile | `ok compiled=true rows=0` | `InvalidDataAccessApiUsageException column=true compiled=false rows=0` | matched |
| Control · valid | `key-to-Sven=true rows=1` | `key-to-Sven=true rows=1` | matched |
| Challenge · recover | `DataIntegrityViolationException column=false rows=0 / InvalidDataAccessApiUsageException rows=0` | `InvalidDataAccessApiUsageException column=true rows=0 / key-to-Sven=true rows=1` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 494` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37014)
