# Find the next valid local cron hour after a midnight gap

The merged cron returned Cairo's next two even hours on April 25 and New York's next legal midnight and 02:00 on March 9. Both parent schedules skipped a day.

Both the civil time and instant are recorded on each successive call. The installed zone rules must contain both named gaps.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · cairo | `2025-04-26T00:00+03:00=2025-04-25T21:00:00Z / 2025-04-26T02:00+03:00=2025-04-25T23:00:00Z` | `2025-04-25T02:00+03:00=2025-04-24T23:00:00Z / 2025-04-25T04:00+03:00=2025-04-25T01:00:00Z` | matched |
| Control · ordinary | `2025-04-24T00:00+02:00=2025-04-23T22:00:00Z / 2025-04-24T02:00+02:00=2025-04-24T00:00:00Z` | `2025-04-24T00:00+02:00=2025-04-23T22:00:00Z / 2025-04-24T02:00+02:00=2025-04-24T00:00:00Z` | matched |
| Challenge · newyork | `2026-03-10T00:00-04:00=2026-03-10T04:00:00Z / 2026-03-10T02:00-04:00=2026-03-10T06:00:00Z` | `2026-03-09T00:00-04:00=2026-03-09T04:00:00Z / 2026-03-09T02:00-04:00=2026-03-09T06:00:00Z` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 507` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36865)
