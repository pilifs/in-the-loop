# Expand only the declared repeatable-annotation container

The merged annotation stream ignored the lookalike container and kept the real repeated tags. Java reflection still retrieved the nested decoy from the unrelated annotation.

The official-container check preserves JDK declaration order and compares the Spring results as a multiset.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · lookalike | `[a, b]/[]` | `[]/[]` | matched |
| Control · official | `[a, b]/[a, b]` | `[a, b]/[a, b]` | matched |
| Challenge · mixed | `[decoy, live]/[live]/decoy` | `[live]/[live]/decoy` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 510` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37326)
