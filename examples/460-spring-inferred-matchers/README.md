# A single Hamcrest matcher sees the first HTTP request value

Recompiling the same unqualified Hamcrest call changed the method selected by javac for both headers and query parameters.

| History | Observation |
|---|---|
| Intent | Both inferred matchers failed on the parent and succeeded on the merge. The compiled descriptors show one Matcher parameter on the parent and a Matcher array on the merge. |
| Control | The explicit String type witness produced array calls on both revisions and both matchers passed. |
| Challenge | Changing the second request value left both scalar matches successful on the merge. Both ordered-list matchers rejected the change and accepted the original pair. |

Both compilations use the same caller source, compiler and Hamcrest version. The JVM receipt records the caller class hashes and the four direct factory call sites on each side. Reflection is used only for the two list factory names introduced at the merge.

With the prepared Spring cache, run `python3 examples/tools/build.py 460` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #30238](https://github.com/spring-projects/spring-framework/pull/30238)
