# CGLIB advice sees a checked exception before the caller receives its wrapper

CGLIB advice now sees the original undeclared checked exception. The caller still receives its wrapper, and type-specific advice can recover normally.

The caller and interceptor compare the exact exception objects. A JDK proxy and declared and unchecked failures supply controls.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · undeclared | `advice=wrapper caller=wrapper cause=true` | `advice=original caller=wrapper cause=true` | matched |
| Control · allowed | `class=true jdk=true jdkUndeclared=true` | `class=true jdk=true jdkUndeclared=true` | matched |
| Challenge · recover | `class=wrapper:0 jdk=normal:1` | `class=normal:1 jdk=normal:1` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 502` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/32469)
