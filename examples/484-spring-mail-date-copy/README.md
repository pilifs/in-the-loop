# A mail message owns its sent date across setters, getters and copies

Ordinary message copies now retain the original 1234 ms through mutations of the input, getter and target. Both copy paths skipped a subclass's getter-provided date.

The subclass leaves the inherited field unset. Its getter still returned 1234. The constructed copy returned null and the pre-populated target retained 77.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · mutations | `0/0 1/1 2/2` | `1234/1234 1234/1234 1234/1234` | matched |
| Control · unset | `null/null/77` | `null/null/77` | matched |
| Challenge · subclass | `1234/1234/1234` | `1234/null/77` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 484` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36626)
