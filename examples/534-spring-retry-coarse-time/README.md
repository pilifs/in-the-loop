# Invoke retry-annotated methods with coarse time units

Both coarse retry units now allow an immediately successful call. A real retry also recovered at attempt two with the very large seconds bound and its millisecond equivalent.

The parent seconds conversion raised ArithmeticException before target entry. A representable explicit maximum worked through the advised bean on both revisions.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · units | `ArithmeticException:0/ArithmeticException:0` | `sent:1/sent:1` | matched |
| Control · finite | `sent:1` | `sent:1` | matched |
| Challenge · retry | `ArithmeticException:0/recovered:2` | `recovered:2/recovered:2` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 534` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37525)
