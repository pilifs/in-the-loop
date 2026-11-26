# Named Hibernate bean requests preserve injection and fallback identity

The named Hibernate prototype now receives its originating Spring context. Named fallback creation retains X, and an absent name no longer resolves to a differently named Spring prototype.

The caller boots the original native Hibernate XML on HSQLDB and obtains BeanContainer from the unwrapped SessionFactory. The producer records both overloads.

Each pin supplies its changed production classes on spring-orm 5.1.4.RELEASE. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · injected | `multiple-1 context=false calls=0/0` | `multiple-1 context=true calls=0/0` | matched |
| Intent · fallback | `unnamed calls=1/0` | `X calls=0/1` | matched |
| Control · prototype | `single/single distinct=true contexts=true calls=0/0` | `single/single distinct=true contexts=true calls=0/0` | matched |
| Challenge · decoy | `known/known distinct=true calls=0/0` | `missing/known distinct=true calls=0/1` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 500` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/22260)
