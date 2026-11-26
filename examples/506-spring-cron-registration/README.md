# Observe the zone of a programmatically registered cron task

The new London cron overload and the explicit trigger fired at 08:00Z in July and 09:00Z in January, including with a Tokyo context clock.

The caller reads the recorded trigger, invokes its runnable, uses a fixed date and zone, and checks that disabled registrations leave the task alone.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · london | `explicit=08:00Z overload=unavailable` | `explicit=08:00Z overload=08:00Z` | matched |
| Control · disabled | `count=1 next=09:00Z disabled=true` | `count=1 next=09:00Z disabled=true` | matched |
| Challenge · seasons | `explicit=08:00Z/09:00Z overload=unavailable` | `explicit=08:00Z/09:00Z overload=08:00Z/09:00Z` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 506` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36556)
