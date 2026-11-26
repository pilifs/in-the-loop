# Lexical printing preserves array brackets after a renamed identifier

Renaming the mixed array parameter produced String[] b[] with rank two. Renaming one field in an int declaration left the sibling scalar.

Comma-separated declarators share a base type while brackets after one name affect only that variable.

The intermediate commit ba880df50766 changed only a varargs test. Its javaparser-core/src/main tree (14e3b4368c934db208b4447d68bc67bc8220fc77) is identical to the parent’s. The second commit changed that production tree.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws com.github.javaparser.ParseProblemException` | `class A { void m(String[] b[]) {} }/b/2` | matched |
| Control | `class A { void m(String[][] b) {} }/b/2` | `class A { void m(String[][] b) {} }/b/2` | matched |
| Challenge | `throws java.lang.UnsupportedOperationException` | `class A { int b[], keep; }/b:1/keep:0` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 561`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/javaparser/javaparser/pull/5207)
