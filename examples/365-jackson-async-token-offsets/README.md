# Logical token locations across nonblocking array feeds

All 32 partitions of the six ASCII bytes of `[true]` run with zero through three bytes of leading padding on each fresh feed. The last feed signals end of input. The oracle records token IDs, 64-bit token and cursor offsets, total count and final EOF. [Upstream change](https://github.com/FasterXML/jackson-core/pull/1415)

The fixed parser emits START_ARRAY at (1,1), VALUE_TRUE at (2,5) and END_ARRAY at (5,6) on all 128 schedules. The parent adds the closing feed's padding to END_ARRAY’s token offset. Both parsers emit the same three tokens and terminate at final EOF. A suspended feed may return NOT_AVAILABLE. [Public observations](controls/table.json) · [Verification tasks](target.json)

The native checker proved both complete trace laws from an unused parser returned by the original factory. On parent selector 32 the reported closing offset is 6. The candidate replayed at the unchanged factory entry on the original JVM. Ordinary native startup remains open for the fixed properties and parent token preservation. [Paired proof](../../verification/results/20261122-142310-check-every-jackson-feed-from-the-unused/result.json) · [Original-entry replay](receipts/offsets-parent/executions/20261122T142730Z-88266c9c/replay.json)

Run `python3 examples/tools/build.py --plan 365` to inspect the frozen tasks.

To reproduce the parent counterexample from the repository root, run

```sh
python3 examples/tools/build.py 365 --task offsets-parent --replay-witness examples/365-jackson-async-token-offsets/records/ready-parser/parent/candidate.json
```
