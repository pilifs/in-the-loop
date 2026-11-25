# JSqlParser visits only the active ALTER body and retains its tail

The fixed renderer ignored the inactive default and visited only the active operand in both TYPE fixtures. Both emitted a trailing CASCADE and both PostgreSQL reparses rejected it. The independent database check identifies the invalid grammar assumption.

The selectable TYPE body, visitor trace and single tail satisfy the deparser expectation. PostgreSQL 16.16 returns SQLSTATE 42601 with that tail and writes 103 without it. The original falsified prediction is retained.

| Question | Input |
|---|---|
| Intent | Deparse the RESTART action containing the stale default for other. |
| Control | Parse `ALTER TABLE t ALTER COLUMN amount SET DEFAULT (1 + 2)` with Dialect.POSTGRESQL and no stale metadata. Apply the same visitor. |
| Challenge | Use the landed TYPE fixture with active `id TYPE INT USING id + 2` and one CASCADE tail. In separate identical ASTs set the inactive default for other to 1 or 9. Custom-deparse each, reparse the resulting SQL under PostgreSQL and stock-render it. |

Run `python3 examples/tools/build.py 442` with the prepared `merged-pr-links-l01-l20` cache. The deployment variants are pins. The replay compiles the caller and checks each recorded return or exception in a fresh JVM.

[Upstream change](https://github.com/JSQLParser/JSqlParser/pull/2770) · [Predictions and oracles](comparison.json) · [Runtime and digests](runtime.json) · [Caller](caller/PublicCaller.java) · [Observations](observations.json) · [Artifact preparation](../../llm-dlc/loops/organic-java-merged-pr-links-l01-l20-brief-setup.md)

Run `python3 examples/442-jsqlparser-active-alter/controls/grammar.py` to check the tail with JSqlParser and a real PostgreSQL 16.16 server. [Grammar receipt](controls/postgres.json)
