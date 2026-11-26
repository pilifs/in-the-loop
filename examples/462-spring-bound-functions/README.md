# SpEL calls a function bound to a Java receiver

A parsed SpEL function now invokes its bound Java receiver and sees a replacement binding on the next evaluation.

| History | Observation |
|---|---|
| Intent | The parent raised SpelEvaluationException for the bound String.concat handle. The merge returned the String red-fox. |
| Control | The reflective static Integer.toString function returned the String 7 on both revisions. |
| Challenge | Reusing the parsed expression after replacing its handle returned blue-fox on the merge. The parent lacks the handle registration overload. |

The receiver is captured with a public JDK method handle. The initial binding uses setVariable, which exists on both revisions.

With the prepared Spring cache, run `python3 examples/tools/build.py 462` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #30045](https://github.com/spring-projects/spring-framework/pull/30045)
