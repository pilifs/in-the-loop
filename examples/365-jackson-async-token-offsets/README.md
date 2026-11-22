# Logical token locations across nonblocking array feeds

All 32 partitions of the six ASCII bytes of `[true]` run with zero through three bytes of leading padding on each fresh feed. The last feed signals end of input. The oracle records token IDs, 64-bit token and cursor offsets, total count and final EOF. [Upstream change](https://github.com/FasterXML/jackson-core/pull/1415)

All 128 padded feed schedules emit START_ARRAY at (1,1), VALUE_TRUE at (2,5), and END_ARRAY at (5,6), matching the unpadded reference. The original parser emits exactly START_ARRAY, VALUE_TRUE and END_ARRAY, in order, then terminates at final EOF. A suspended feed may return NOT_AVAILABLE. [Public observations](controls/table.json) · [Verification tasks](target.json)

Run `python3 examples/tools/build.py --plan 365` to inspect the frozen tasks.
