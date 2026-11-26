# Transaction outcome when a reactive subscriber cancels

The pinned reactive operator rolled back cancellation at the merge. Moving take(1) inside its transaction preserved the row.

| History | Observation |
|---|---|
| Intent | The subscriber received the inserted token before explicitly cancelling. The parent committed it. The merge rolled back and a fresh connection found no row. |
| Control | Normal completion committed the row on both revisions. The designated source exception propagated and its row was absent on both. |
| Challenge | Both placements delivered one token. The parent committed both. The merge rolled back the outer take and committed the inner take. |

The exact TransactionalOperatorImpl.java from each pin is compiled against the same Spring 5.3.0-M1 transaction and R2DBC companions. A delegating manager waits for real H2 transaction cleanup before a fresh unpooled read. These results cover the Java operator.

With the prepared Spring cache, run `python3 examples/tools/build.py 471` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #25256](https://github.com/spring-projects/spring-framework/pull/25256)
