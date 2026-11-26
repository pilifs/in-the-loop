# Replacing a session attribute notifies the displaced listener

Replacing a session attribute now unbinds the displaced listener before binding its replacement. Rebinding the same object was silent.

The public javax.servlet mock records the receiver, callback phase, session, attribute name and value. The challenge uses distinct listeners with equal application values.

Each pin supplies its changed production classes on spring-test 5.1.0.RC1. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · replace | `+A:A,+B:B stored=B` | `+A:A,-A:A,+B:B stored=B` | matched |
| Control · remove | `+A:A,-A:A stored=null` | `+A:A,-A:A stored=null` | matched |
| Challenge · equal | `+A:A,+A:A,+B:B stored=B` | `+A:A,-A:A,+B:B stored=B` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 486` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/1912)
