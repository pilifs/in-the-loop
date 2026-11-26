# Executing SQL after a block comment whose closing line starts with dashes

The merged SQL populator committed both original rows and ignored the sentinel in a line comment. The parent committed the first row and then failed. Its old three-argument direct client lost binary linkage on the merge.

Each history reads the H2 table through a distinct JDBC connection. javap records the exact descriptor of the client compiled on the parent.

Each pin supplies its changed production classes on spring-jdbc 5.1.4.RELEASE. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · original | `ScriptStatementFailedException rows=[Juergen Hoeller]` | `ok rows=[Juergen Hoeller, Sam Brannen]` | matched |
| Control · bare | `ok rows=[Juergen Hoeller, Sam Brannen]` | `ok rows=[Juergen Hoeller, Sam Brannen]` | matched |
| Challenge · sentinel | `ScriptStatementFailedException rows=[Juergen Hoeller]` | `ok rows=[Juergen Hoeller, Sam Brannen]` | matched |
| Compatibility · descriptor | `select 1;` | `NoSuchMethodError` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 493` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/22392)
