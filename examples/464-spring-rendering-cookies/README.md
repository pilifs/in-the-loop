# Copying a rendering response preserves cookies in both web stacks

Rebuilding a rendering response retained cookies, including two currencies with different paths, at both HTTP boundaries.

| History | Observation |
|---|---|
| Intent | The parent dropped the currency cookie in both stacks. The merged copy and written response retained EUR at /shop exactly once. |
| Control | The cookie-free response in both stacks kept checkout, status 201, the summary header and book model item, and gained /cart. |
| Challenge | Both merged responses emitted EUR at /shop, USD at /account and visit at /. The original still contained only the two currencies. |

Both a servlet ModelAndView and a resolving reactive View receive the model. The caller also decodes Set-Cookie response fields and compares value/path multiplicity.

With the prepared Spring cache, run `python3 examples/tools/build.py 464` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #37378](https://github.com/spring-projects/spring-framework/pull/37378)
