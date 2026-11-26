# Derived HTTP clients keep independent default header and cookie lists

All three HTTP clients isolated an edited default header and cookie list from a second derivative of the base client.

| History | Observation |
|---|---|
| Intent | On the parent the edited client and a fresh derivative both sent one and two. On the merge only the edited client sent two, for RestClient, WebClient and WebTestClient. |
| Control | Adding a previously absent header and cookie left both names absent on the base derivative on both revisions. |
| Challenge | After changing the retained builder, WebTestClient B sent both values. A retained just one on the merge and sent both on the parent. |

The synchronous request factory reads the serialized Cookie header. The two reactive clients deliver requests to an in-process HttpHandler. The initial header is added through defaultHeaders so the fixture supplies a mutable list for the append.

With the prepared Spring cache, run `python3 examples/tools/build.py 463` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37325](https://github.com/spring-projects/spring-framework/pull/37325)
