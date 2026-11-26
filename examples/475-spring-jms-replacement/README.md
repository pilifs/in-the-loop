# JMS recovery after a replacement connection fails preparation

After reset the merged JMS factory recovered on C. Direct reinitialization followed by the same failure left the retry on closed A.

| History | Observation |
|---|---|
| Intent | Both sides surfaced B's listener error. After reset the parent served a session on B. The merge closed B, prepared C and served a C session. |
| Control | Two successful logical connections shared one prepared physical A and both yielded A sessions on each revision. |
| Challenge | Direct initConnection closed A before B failed. The merged factory also closed B, then attempted the next session on closed A. No C connection was created. |

A deterministic Jakarta JMS provider records every creation, listener installation and physical close. It refuses sessions after a physical close. All application calls use the public Spring factory.

With the prepared Spring cache, run `python3 examples/tools/build.py 475` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #29116](https://github.com/spring-projects/spring-framework/pull/29116)
