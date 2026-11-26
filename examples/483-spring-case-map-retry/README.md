# A failed computation leaves no case-insensitive key behind

A failed computation now leaves size, iteration and case-insensitive membership in agreement. A successful retry keeps its own KEY spelling.

An existing null-valued mapping retained its original spelling on both revisions. The throwing function is checked by exception identity.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · failed | `null:0,true,null,[] / marker:0,true,null,[]` | `null:0,false,null,[] / marker:0,false,null,[]` | matched |
| Control · existing | `null:1,true,null,[Key]` | `null:1,true,null,[Key]` | matched |
| Challenge · retry | `Key:[Key]:v:0,false,null,[]` | `KEY:[KEY]:v:0,false,null,[]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 483` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37351)
