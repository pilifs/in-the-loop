# Read resources from an absolute manifest dependency in a launched JAR

A fresh java -jar launch now reads the asset from an absolute manifest entry. Replacing that JAR at the same path changed the bytes from amber to cobalt, with a same-named amber decoy outside the classpath.

The child checked the loaded Spring resolver origin. Both revisions also read the one amber resource through a relative Class-Path entry.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · absolute | `[]` | `[amber]` | matched |
| Control · relative | `[amber]` | `[amber]` | matched |
| Challenge · replace | `[]/[]` | `[amber]/[cobalt]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 537` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/35732)
