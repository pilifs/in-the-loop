# Retain empty multipart fields exactly once, including the final field

The servlet multipart converter now returns both an empty first field and an empty last field. Three fields under one name retained order and cardinality.

Both original CRLF resources come from the pinned test tree. A separate wire fixture repeats the same name with empty, nonempty and empty bodies.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · edges | `text2=[a] / text1=[a]` | `text1=[<empty>];text2=[a] / text1=[a];text2=[<empty>]` | matched |
| Control · one | `text1=[a]` | `text1=[a]` | matched |
| Challenge · repeated | `item=[a]` | `item=[<empty>, a, <empty>]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 490` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37202)
