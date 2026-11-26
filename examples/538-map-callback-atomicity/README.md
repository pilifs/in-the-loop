# A throwing value update leaves the map usable

Both Eclipse Collections maps discarded the missing key when the value factory threw. A later update succeeded, including when two unequal keys shared the same hash.

Colliding keys are distinct under equality. A fresh update after failure must still take the absent-key path.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `same=true,size=0,key=true,entries={};retry=NullPointerException / same=true,size=0,key=true,entries={};retry=NullPointerException` | `same=true,size=0,key=false,entries={};retry=6/{4=6} / same=true,size=0,key=false,entries={};retry=6/{4=6}` | matched |
| Control | `10/0/{4=10} / 10/0/{4=10}` | `10/0/{4=10} / 10/0/{4=10}` | matched |
| Challenge | `true/{1=7}/7/{1=7, 4=7}` | `true/{1=7}/7/{1=7, 4=7}` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 538`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/eclipse-collections/eclipse-collections/pull/1786)
