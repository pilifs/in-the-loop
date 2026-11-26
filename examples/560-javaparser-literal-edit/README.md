# Typed literal edits reach the lexical printer

The lexical printer emitted the changed literal. A fresh parse recovered the embedded newline and quote and retained the adjacent comment.

A Java string literal cannot contain an unescaped physical line break. A consumer must recover the logical characters regardless of how the printer escapes them.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `b/a/false` | `b/b/true` | matched |
| Control | `true/a` | `true/a` | matched |
| Challenge | `true/false/true` | `true/true/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 560`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/javaparser/javaparser/pull/5176)
