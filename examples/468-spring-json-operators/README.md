# PostgreSQL JSON operators beside a named JDBC parameter

The pinned named-parameter parser preserved both PostgreSQL JSON operators and bound only the application parameter.

| History | Observation |
|---|---|
| Intent | The parent rejected the raw all-keys operator before statement preparation. The merge passed the original operator to the callback, replaced the named parameter and bound the title once at slot 1. |
| Control | Both parsers rejected an actual mixture of named and positional placeholders before statement creation or callback. |
| Challenge | Both raw operators reached the merged callback. Through pgJDBC's escaped operator spelling, PostgreSQL returned true for any and false for all on both sides. |

The exact NamedParameterUtils.java from each pin is compiled against the same Spring JDBC 5.0.0.M5 companions. The driver path uses pgJDBC 42.7.15 and the digest-pinned PostgreSQL 17.12 container. The recording DataSource and real database queries answer different parts of the question.

With the prepared Spring cache, run `python3 examples/tools/build.py 468` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #1366](https://github.com/spring-projects/spring-framework/pull/1366)
