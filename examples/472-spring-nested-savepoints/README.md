# Outer R2DBC transactions remain active after nested savepoints

Both nested R2DBC scopes preserved the enclosing transaction on the merge. Its outer rollback removed even the successful inner write.

| History | Observation |
|---|---|
| Intent | The parent reported nested statuses true then false and left only D. The merge created two savepoints, reported true twice, committed the outer transaction once and left A, B and D. |
| Control | An ordinary outer commit exposed A. An ordinary outer rollback left no row. Neither revision created a savepoint. |
| Challenge | After outer rollback D survived on the parent. The merge left the table empty, including B from the successful inner scope. |

DatabaseClient uses the same connection factory as the transaction manager. The wrapper forwards to R2DBC H2, counts completed transaction and savepoint operations, and leaves the independent reader outside the transaction.

With the prepared Spring cache, run `python3 examples/tools/build.py 472` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #31133](https://github.com/spring-projects/spring-framework/pull/31133)
