# Read retry counts and exception history inside retry callbacks

RetryTemplate supplied retry counts and original exception identities to listeners. Direct calls to the old methods of a CompositeRetryListener stopped reaching its legacy delegate on the landing.

Template-driven legacy callbacks still worked, and both delegate orders retained the expected records. The direct-call parent delivered both events.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · state | `absent` | `[fail:E1:1:E0,E1, ok:R:2:E0,E1]:R` | matched |
| Control · old | `[fail:E1, ok:R]:R:[]` | `[fail:E1, ok:R]:R:[]` | matched |
| Challenge · fanout | `absent` | `true/true` | matched |
| Compatibility challenge · direct | `[fail:E1, ok:R]` | `[]` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 536` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37465)
