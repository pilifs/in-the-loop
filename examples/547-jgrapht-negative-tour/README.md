# Return a closed tour when edge weights are negative

The negative-weight triangle produced a closed tour of weight −6. The four-vertex tour visited every vertex once and its reported weight equaled the sum along the returned path.

The positive edge allows initialization and leaves only negative candidates for expansion. Public graph readback checks the reported tour independently.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.NullPointerException` | `vertices=true,edges=true,weight=-6.0,sum=-6.0` | matched |
| Control | `vertices=true,edges=true,weight=9.0,sum=9.0` | `vertices=true,edges=true,weight=9.0,sum=9.0` | matched |
| Challenge | `throws java.lang.ArrayIndexOutOfBoundsException` | `vertices=true,edges=true,weightAgrees=true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 547`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/jgrapht/jgrapht/pull/1376)
