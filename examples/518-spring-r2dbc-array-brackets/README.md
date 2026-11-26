# Bind a named R2DBC parameter immediately inside SQL array brackets

PostgreSQL returned the bound array for tight brackets and preserved the order and multiplicity of [7,2,7]. The parent required a space after the parameter name.

Each history subscribed through Spring DatabaseClient against PostgreSQL 17 and compared the driver's Integer[] with an independently executed literal array.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · scalar | `binding failed:literal=[7]` | `[7]:literal=[7]` | matched |
| Control · space | `[7]:literal=[7]` | `[7]:literal=[7]` | matched |
| Challenge · list | `binding failed:literal=[7, 2, 7]` | `[7, 2, 7]:literal=[7, 2, 7]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 518` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/27716)
