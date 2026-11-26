# Cron callers can distinguish an impossible date from a distant leap day

Both merged cron APIs returned no match for June 31 and found the leap day in 2104 after February 29, 2096. The old trigger threw for each search.

A fixed TriggerContext and UTC keep the calendar independent of the clock. Both triggers selected June 30, 2021 for the ordinary control.

Each pin supplies its changed production classes on spring-context-5.3.0-M1. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · impossible | `IllegalArgumentException/absent` | `null/null` | matched |
| Control · june | `2021-06-30T00:00:00Z` | `2021-06-30T00:00:00Z` | matched |
| Challenge · leap | `IllegalArgumentException/absent` | `2104-02-29T00:00:00Z/2104-02-29T00:00` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 517` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/25464)
