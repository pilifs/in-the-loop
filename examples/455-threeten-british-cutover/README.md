# ThreeTen-Extra resolves cutover fields and reads a British period back

| History | Public observation |
|---|---|
| Intent · month and year | Adding a month to 12 August 1752 and a year to 12 September 1751 yielded 23 September on the parent and 2 September on the merge. |
| Control · elapsed day and direct selection | Both revisions advanced from 2 to 14 September in one elapsed day, reversed it, and selected 23 September when asked for day-of-month 12. |
| Challenge · backward period | The parent returned (0, −6, −17). Adding it back reached 21 August, epoch day −79379. The merge returned (0, −6, −6) and reached 1 September, epoch day −79368, equal to the independent ISO oracle. |
| Intent · Julian day field | Selecting day 30 in February 2011 moved from 28 February to 2 March. Both revisions rejected day 32. |
| Intent · BC conversion | Both chronologies wrapped the minimum int to −2147483647 on the parent and threw DateTimeException on the merge. Both returned −2147483646 for the maximum int. |

The period is a ChronoPeriod added back to 18 March 1753. The caller reads all date and period fields and independently converts ISO 12 September 1752 to an epoch day. Both chronology singletons receive JulianEra.BC.

Run `python3 examples/tools/build.py 455` with the prepared `merged-pr-links-n01-n05` cache. Each revision and history starts a fresh JVM with the same compiled caller. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observations](observations.json) · [Upstream PR](https://github.com/ThreeTen/threeten-extra/pull/463) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-setup.md)
