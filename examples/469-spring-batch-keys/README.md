# Binding the first JDBC batch row once when returning generated keys

The merge eliminated redundant first-row bindings, and two actual generated keys identified the two inserted H2 rows.

| History | Observation |
|---|---|
| Intent | The parent bound foo and UK twice before adding the first named batch row. The merge bound each value once. Both added the original two rows and returned counts of one each. |
| Control | Without a KeyHolder, both revisions bound each value once and inserted the two ordered rows. |
| Challenge | The indexed parent bound foo twice. The merge bound foo then bar once each. On both, a separate connection looked up the two returned keys and recovered foo then bar from exactly two committed rows. |

The recording wrapper forwards calls to H2 2.4.240. Bind order, addBatch snapshots, update counts, generated keys and independent reads come from the same run.

With the prepared Spring cache, run `python3 examples/tools/build.py 469` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37308](https://github.com/spring-projects/spring-framework/pull/37308)
