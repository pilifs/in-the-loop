# HikariCP restores the schema on the same PostgreSQL backend

Both borrows used the same PostgreSQL backend. After a nonexistent schema selection, the parent left its schema null and the marker lookup failed with SQLSTATE 42P01. The fix restored test and read exactly 37.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Each replay starts an isolated PostgreSQL 16 database. One application role owns its schema and marker.

Run `python3 examples/tools/build.py 413` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/brettwooldridge/HikariCP/pull/2346)
