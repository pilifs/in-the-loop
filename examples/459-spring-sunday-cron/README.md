# A Sunday-to-Sunday cron range fires once a week

A singleton Sunday range advanced from Thursday to Friday on the parent and to Sunday on the merge.

| History | Observation |
|---|---|
| Intent | Starting on Thursday afternoon produced midnight on 26 February on the parent and 28 February on the merge. |
| Control | Both SUN and 0-0 selected Sunday, 28 February at midnight on both revisions. |
| Challenge | Starting at that Sunday midnight, SUN-SUN and 7-7 advanced to Monday on the parent. All three spellings advanced to Sunday, 7 March on the merge. |

The clocks are local dates and times. The Sunday returned by the singleton expression is the seed for the next set of calls.

With the prepared Spring cache, run `python3 examples/tools/build.py 459` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37576](https://github.com/spring-projects/spring-framework/pull/37576)
