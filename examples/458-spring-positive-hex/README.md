# An explicit plus sign on hexadecimal integers

Both hexadecimal prefixes now accept unary plus. The result still respects the requested numeric type and its bounds.

| History | Observation |
|---|---|
| Intent | Integer and BigInteger both rejected plus-prefixed hexadecimal 7f on the parent. Each returned 127 in its requested type on the merge. |
| Control | Both revisions returned Integer −127 for negative hexadecimal and BigInteger 127 for positive decimal. |
| Challenge | Both spellings of positive hexadecimal 80 returned Short 128 on the merge. Both Byte calls raised NumberFormatException. |

Each call records the runtime class and value or the number-format exception independently.

With the prepared Spring cache, run `python3 examples/tools/build.py 458` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37434](https://github.com/spring-projects/spring-framework/pull/37434)
