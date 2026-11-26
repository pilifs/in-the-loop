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

The identical application class on Spring 7.1.0 again received no events via the old direct overloads. All three template and composite controls retained their original histories. [Campaign release checks](../../verification/merged-pr-links/q01-q30/upstream.md) · [Release and later-revision evidence](../../llm-dlc/loops/spring-framework-pr-links-q01-q30-brief-results.md#published-versions-and-the-later-factory)
