# Generic bean lookup returns the advised interface proxy

Typed bean lookup retained the advised User proxy while continuing to reject an Order token for that same bean name.

| History | Observation |
|---|---|
| Intent | The parent rejected the User token. The merge returned the same JDK proxy as the named lookup, and persisting User 1 populated users/1. |
| Control | Raw interface lookup populated users/2 through the managed proxy on both revisions. |
| Challenge | The merge rejected the wrong name/token combination and accepted the Order token for orderDao. Persisting Order 9 populated orders/9 and left users/9 absent. |

The factory methods declare their generic return types. The cache is read independently of the returned entity.

With the prepared Spring cache, run `python3 examples/tools/build.py 474` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37047](https://github.com/spring-projects/spring-framework/pull/37047)
