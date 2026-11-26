# Serialize indented JSON as complete server-sent event data

The independent event reader now reconstructs both indented JSON objects. Nested structure and a newline inside a field survived transport and parsed into the intended events.

The caller consumed each flush group and its buffers in order, dispatched data at blank lines, then parsed the complete payload. The compact control passed on both revisions.

Each pin supplies its changed production classes on spring-web-5.0.0.M3-q17. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · pretty | `events=2:invalid,invalid` | `events=2:A/one,B/two` | matched |
| Control · compact | `events=2:A/one,B/two` | `events=2:A/one,B/two` | matched |
| Challenge · nested | `events=2:invalid,invalid` | `events=2:A<LF>B/one,B/nested` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 524` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/1251)
