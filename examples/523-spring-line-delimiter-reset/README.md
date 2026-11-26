# Retain data before a line feed after a lone carriage return

A lone carriage return now preserves both intervening bytes before the line feed. Splitting a UTF-8 character and adjacent carriage returns across buffers yielded the same two decoded strings.

Each subscription received fresh heap buffers and was collected to completion. Both revisions retained ordinary CRLF and LF behavior.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · lone | `[a<CR>X, b]` | `[a<CR>XY, b]` | matched |
| Control · standard | `[a, b] / [a, b]` | `[a, b] / [a, b]` | matched |
| Challenge · chunks | `[é<CR>, Z] / [é<CR>, Z]` | `[é<CR>, Z] / [é<CR>, Z]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 523` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37053)
