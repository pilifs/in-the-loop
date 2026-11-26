# Honor a JDBC row limit when the driver returns additional rows

At limit two, list, callback, and stream queries all delivered just 11 and 22 from an overlong JDBC cursor. At explicit zero the landing delivered no rows through any of the three APIs.

The connection delegates to H2 and records the limit call without enforcing it. The parent returned all three rows at zero, the JDBC unlimited setting. The default limit left the driver alone.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · two | `[11, 22, 33]/[11, 22, 33]/[11, 22, 33] set=[2, 2, 2]` | `[11, 22]/[11, 22]/[11, 22] set=[2, 2, 2]` | matched |
| Control · default | `[11, 22, 33]/[11, 22, 33]/[11, 22, 33] set=[]` | `[11, 22, 33]/[11, 22, 33]/[11, 22, 33] set=[]` | matched |
| Challenge · zero | `[11, 22, 33]/[11, 22, 33]/[11, 22, 33] set=[0, 0, 0]` | `[]/[]/[] set=[0, 0, 0]` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 520` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/34709)
