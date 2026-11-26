# Mixed named-parameter batches preserve an existing SQL parameter source

The mixed JDBC batch retained its supplied parameter source. Editing that source before binding committed (3,revised) alongside the map and bean rows.

Each successful batch used a real transaction and a separate H2 connection for ordered readback. Both conversion overloads preserved the ordinary two-row input.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · source | `false:false:IllegalArgumentException` | `true:true:source` | matched |
| Control · ordinary | `[map, bean]:[1=map, 2=bean] / [map, bean]:[1=map, 2=bean]` | `[map, bean]:[1=map, 2=bean] / [map, bean]:[1=map, 2=bean]` | matched |
| Challenge · mutate | `throws org.springframework.dao.InvalidDataAccessApiUsageException` | `[1=map, 2=bean, 3=revised]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 515` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37524)
