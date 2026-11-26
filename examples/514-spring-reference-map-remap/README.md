# Remapping deletion changes the reference-map count immediately

All three null-producing remaps immediately report an empty singleton map. In a one-segment map with a second key, the count now agrees with the surviving iterator entry.

The caller keeps the entry objects reachable and reads size and emptiness before any lookup or purge. Replacing the value kept size one.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · delete | `1:null:1:false:null:[] / 1:null:1:false:null:[] / 1:null:1:false:null:[]` | `1:null:0:true:null:[] / 1:null:0:true:null:[] / 1:null:0:true:null:[]` | matched |
| Control · replace | `1:2:1:false:2:[a=2] / 1:2:1:false:2:[a=2] / 1:2:1:false:2:[a=2]` | `1:2:1:false:2:[a=2] / 1:2:1:false:2:[a=2] / 1:2:1:false:2:[a=2]` | matched |
| Challenge · survivor | `2:false:[b=keep]:0` | `1:false:[b=keep]:0` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 514` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37577)

The reported 6.2.13 release reproduced the stale singleton and size-two survivor counts. The same caller on 7.1.0 reproduced all three merged outcomes. [Campaign release checks](../../verification/merged-pr-links/q01-q30/upstream.md) · [Release and later-revision evidence](../../llm-dlc/loops/spring-framework-pr-links-q01-q30-brief-results.md#published-versions-and-the-later-factory)
