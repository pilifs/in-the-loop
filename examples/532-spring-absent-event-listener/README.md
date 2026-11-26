# Publish an event when an optional listener bean is absent

A null listener factory now leaves its consumer empty and lets publication return. A later ordered listener received E1 and E2 exactly once each.

The parent threw before the later listener saw either event. A genuine optional listener still received E1 once on both revisions.

Each pin supplies its changed production classes on spring-context-5.2.1.RELEASE-q25. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · missing | `empty:IllegalStateException` | `empty:ok` | matched |
| Control · present | `present:[E1]` | `present:[E1]` | matched |
| Challenge · ordered | `IllegalStateException:[]` | `ok:[E1, E2]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 532` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/23784)
