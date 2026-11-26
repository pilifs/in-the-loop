# Read a scalar map value through a primitive-array annotation member

A scalar 7 now reads as primitive int[] through both the public annotation reader and a synthesized annotation.

The reference annotation comes from javac and reflection. Both array members were compared independently.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · codes | `IllegalStateException` | `int[] [7]` | matched |
| Control · ordinary | `String[] [east] int[] [7, 9]` | `String[] [east] int[] [7, 9]` | matched |
| Challenge · synthesize | `IllegalStateException` | `codes=true names=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 479` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37349)
