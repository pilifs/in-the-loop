# Updating an EnumMap merges the values already owned by the caller

Updating the EnumMap modified the externally held A value. Reading the serialized bean back showed that changing C’s initial state affected only C.

Both builds use the timestamped Jackson Core 3.4.0 and annotations 2.24 snapshots listed in runtime.json.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws tools.jackson.databind.exc.InvalidDefinitionException` | `true/true/3/init-A/init-C` | matched |
| Control | `1/x` | `1/x` | matched |
| Challenge | `throws tools.jackson.databind.exc.InvalidDefinitionException` | `3/init-A/3/first/4 / 3/init-A/3/second/8` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 566`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/FasterXML/jackson-databind/pull/6473)
