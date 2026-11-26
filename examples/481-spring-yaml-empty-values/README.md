# Choosing a value for empty YAML entries

The new YAML hook retained a caller-selected marker for an empty mapping and both null scalars. An empty sequence still became an empty string.

The adapter for each revision directly calls its protected overload. The common caller tests key presence and marker identity. The proposed uniform empty-container behavior was refuted.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · select | `blank,blank,null,blank,value` | `null,null,null,blank,value / marker,marker,marker,blank,value` | matched |
| Control · properties | `blank,blank,absent,blank,value` | `blank,blank,absent,blank,value` | matched |
| Challenge · containers | `map=null list=blank` | `map=marker list=blank` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 481` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36207)
