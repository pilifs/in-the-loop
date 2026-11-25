# Five Java changes at their public APIs

All 17 predictions for the merged revisions held. The five controls returned identical observations on both revisions, and all seven intended changes produced the predicted difference. The five callers ran 34 histories in fresh JVMs against the parent and merge artifacts. Each pair used identical caller bytecode. [Registered brief](organic-java-merged-pr-links-n01-n05-brief.md) · [Build provenance](organic-java-merged-pr-links-n01-n05-brief-setup.md) · [Machine-readable audit](../../verification/merged-pr-links/n01-n05/audit.json)

| Case | What the caller observed |
|---|---|
| [N01 · Commons CLI](../../examples/453-cli-option-defaults/README.md) | A failed parse left its discarded property on the parent definition. Retrying with a fresh parser returned that old value. On the merge the retry matched a fresh invocation, and a retained successful command line kept its original value. |
| [N02 · HdrHistogram](../../examples/454-hdrhistogram-resized-equality/README.md) | After growth and reset, both histograms reported one sample at the same value. Only the larger receiver threw on the parent. Both directions returned true on the merge. Both revisions rejected different interior counts despite equal totals and extrema. |
| [N03 · ThreeTen-Extra](../../examples/455-threeten-british-cutover/README.md) | The British backward period changed from (0, −6, −17) to (0, −6, −6). Adding it back now reaches epoch day −79368, the independent ISO result for the intended end. The month/year adjustment, direct day selection, invalid Julian day and BC overflow histories also matched their predictions. |
| [N04 · Esri Geometry](../../examples/456-esri-polyline-difference/README.md) | Touching the closed line threw in **both** directions on the parent. The merge kept all eleven edges once in either direction. Extending the subtractor by A–B removed precisely that edge **on both revisions**, leaving length 13326.118751140732. The reverse touch and the parent overlap were open in the brief. |
| [N05 · Spring JDBC](../../examples/457-spring-mysql-id-reservations/README.md) | Both injected failures raised the same Spring exception after the allocator read 100. A separate connection saw **98 after rollback** and **100 after a real commit followed by failed auto-commit restoration**. On the merge, the next three IDs were respectively 99, 100, 101 and 101, 102, 103. |

## Spring transaction readback

Each history started with an InnoDB sequence row of 98 and an empty primary-key table on MySQL 9.1.0. A wrapper forwarded the reservation statements to Connector/J, recorded the value the allocator read, and injected one transaction-boundary failure. After each returned ID, a separate transaction attempted the insert. Another physical connection read both tables. [Caller and failure injection](../../examples/457-spring-mysql-id-reservations/caller/PublicCaller.java) · [All six database histories](../../examples/457-spring-mysql-id-reservations/observations.json)

| First reservation | Parent retries and final durable maximum | Merged retries and final durable maximum |
|---|---|---|
| Rolled back at commit | 100, 99, 100. The third insert hit MySQL duplicate-key error 1062. Maximum 100. | 99, 100, 101. Three inserts committed. Maximum 102. |
| Ordinary commits | 99, 100, 101. Maxima after each insert were 100, 100, 102. | 99, 100, 101. Maxima after each insert were 100, 100, 102. |
| Committed, then failed restoring auto-commit | 100, 101, 102. Three inserts committed. Maximum 102. | 101, 102, 103. Three inserts committed. Maximum 104, with 99 and 100 unused. |

## Replay

With the prepared cache, run `python3 verification/merged-pr-links/audit.py --campaign n01-n05 --replay` to rebuild the callers and compare every observation. The audit without `--replay` checks the recorded results, question order, source pins, artifact digests and MySQL version offline. Each example also runs through `python3 examples/tools/build.py NNN`. The database example starts its own loopback-only container from the pinned local image and creates disposable credentials. [Runtime lock](../../examples/457-spring-mysql-id-reservations/runtime.json)

The independent jobs repeat the entire campaign and trace the original property handler, histogram equality method, British backward period and Esri path restoration. Each debugger trial uses the same compiled caller as the corresponding public comparison. [Campaign replay](../../verification/jobs/2026/11/25/20261125-232607-replay-the-17-n01-n05-predictions-with-m.json) · [CLI and histogram traces](../../verification/jobs/2026/11/25/20261125-233153-trace-option-default-reuse-and-histogram.json) · [Calendar and geometry traces](../../verification/jobs/2026/11/25/20261125-233153-trace-calendar-period-readback-and-esri.json)
