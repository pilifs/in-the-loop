# Quartz reloads a replaced schedule and its extension rows

On Derby and PostgreSQL the parent persisted CRON with one simple row and zero cron rows, then failed to reload the trigger. The fixed scheduler and fresh JDBC reads agreed after both replacements. The second group kept its own schedule.

The Derby driver uses a new in-memory database in every process. PostgreSQL 16.16 uses one private schema per history on a disposable loopback server.

| Question | Input |
|---|---|
| Intent | Replace the original simple schedule by cron. |
| Control | On a fresh copy of the original fixture replace SIMPLE by SIMPLE under the same key, using repeat count 3 and interval 60,000 ms. |
| Challenge | Add an independent SIMPLE trigger named t in group other for a second job. Perform SIMPLE→CRON→SIMPLE on g/t. After each committed replacement inspect the affected and control keys through a fresh JDBC connection as well as getTrigger. |

Run `python3 examples/tools/build.py 434` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are derby, postgres16. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/quartz-scheduler/quartz/pull/1496) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)
