# Keep constructor values when a join returns duplicate column labels

With duplicate id labels, both the record and the final-field class now retain the first id, 1. Changing the decoy to 200 left the counting id setter untouched and still populated note.

On the parent the record threw and the final-field class silently retained 100. Each positional oracle and typed projection executed through JdbcClient against H2.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · duplicate | `1/IllegalStateException/100:book` | `1/1:book/1:book` | matched |
| Control · unique | `1/1:book/1:book` | `1/1:book/1:book` | matched |
| Challenge · decoy | `100:1:packed / 200:1:packed` | `1:0:packed / 1:0:packed` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 521` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37602)
