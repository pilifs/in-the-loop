# Keep a supplementary character intact at the truncation boundary

A cut inside an emoji now drops the whole split pair. The strict UTF-8 encoder accepted the retained earlier emoji and the exact truncation suffix.

Hexadecimal units expose the lone high surrogate the parent returned. A complete pair at limit 3 and an input that fits at 4 each retained their original units.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · cut | `0061 d83d \|suffix=true` | `0061 \|suffix=true` | matched |
| Control · whole | `0061 d83d de00 \|suffix=true / 0061 d83d de00 0062 \|suffix=false` | `0061 d83d de00 \|suffix=true / 0061 d83d de00 0062 \|suffix=false` | matched |
| Challenge · encode | `MalformedInputException` | `a😀 (truncated)...` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 478` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37435)
