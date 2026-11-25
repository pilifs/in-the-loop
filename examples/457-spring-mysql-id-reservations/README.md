# Spring JDBC reserves fresh IDs after a MySQL transaction failure

| History | Public observation |
|---|---|
| Intent · failed commit | The first reservation read 100 and rolled back. A separate connection read 98 and no inserted IDs. The parent then issued 100, 99, 100 and got MySQL duplicate-key error 1062 on the third insert. All three merged inserts succeeded for 99, 100, 101, with a final sequence of 102. |
| Control | With ordinary commits both revisions inserted 99, 100, 101. The durable maxima after each were 100, 100, 102. |
| Challenge · failed restoration | Both first requests raised DataAccessResourceFailureException after a successful commit. An independent read found 100 and no issued IDs. The parent inserted 100, 101, 102 and ended at 102. The merge left 99–100 unused, inserted 101, 102, 103 and ended at 104. |

A fresh MySQL 9.1.0 container runs the two InnoDB tables. Connector/J executes every query. A JDBC wrapper records the actual last_insert_id() read and injects one failure at the first commit or the first post-commit restoration. Each insert commits separately and every readback opens a new physical connection.

Run `python3 examples/tools/build.py 457` with the prepared `merged-pr-links-n01-n05` cache. Docker also needs the pinned MySQL image. The runner creates its own database and credentials. Each revision and history starts a fresh JVM with the same compiled caller. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observations](observations.json) · [Upstream PR](https://github.com/spring-projects/spring-framework/pull/37322) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-n01-n05-brief-setup.md)
