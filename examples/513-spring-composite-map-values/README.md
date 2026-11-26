# Removing one of two equal values from a composite map

Removing one of two equal values now succeeds and leaves the second mapping intact. A second removal through the same public values view throws UnsupportedOperationException with that mapping still present.

The first removal on the parent had already mutated the first backing map when it threw. The merged live view also exposed a previously shadowed value after the winning mapping was removed.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · first | `UnsupportedOperationException:{}:{b=x}:[b]:1` | `true:{}:{b=x}:[b]:1` | matched |
| Control · missing | `false:{a=x}:{b=y} / true:{}:{b=y}` | `false:{a=x}:{b=y} / true:{}:{b=y}` | matched |
| Challenge · shadow | `true:hidden:[hidden]:1:{}:{a=hidden}` | `true:hidden:[hidden]:1:{}:{a=hidden}` | matched |
| Challenge · second | `UnsupportedOperationException:{}:{b=x}:[b]:1` | `UnsupportedOperationException:{}:{b=x}:[b]:1` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 513` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37332)
