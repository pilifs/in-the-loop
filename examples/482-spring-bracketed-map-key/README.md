# Map keys can contain balanced brackets in a bean property path

A balanced bracket inside a literal map key now selects the intended child. A quoted write left the similarly named decoy untouched.

A direct read from the backing Java map checks both children and counts its keys after the write.

Each pin supplies its changed production classes on spring-beans 5.1.6.RELEASE. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · read | `prefix` | `full` | matched |
| Control · plain | `control -> control2` | `control -> control2` | matched |
| Challenge · quoted | `throws org.springframework.beans.NullValueInNestedPathException` | `changed/prefix/changed keys=3` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 482` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/21855)
