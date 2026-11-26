# Reject unmatched parentheses before selecting an active profile

Malformed profile expressions now fail during construction. A context with the malformed annotation also failed, while its valid twin supplied the requested bean.

The parent matched both malformed expressions and activated the malformed bean. The valid conjunction changed truth when prod became active on both revisions.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · parse | `true/true` | `IllegalArgumentException/IllegalArgumentException` | matched |
| Control · valid | `true/false` | `true/false` | matched |
| Challenge · annotation | `loaded/loaded` | `malformed/loaded` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 509` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36550)
