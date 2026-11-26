# Keep HTTP handler decorators when cloning a WebFlux handler builder

A clone retained its configured HTTP decorator. Independently extending the two builders produced ordered markers A,B and A,C, including A,C on another clone of the original.

Each fresh request completed at a terminal WebHandler that recorded the full path and every header value.

Each pin supplies its changed production classes on spring-web-5.3.0-RC1-q20. The replay verifies the loaded class origins and all class digests of each compiled slice.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · clone | `/probe:[A] / /probe:[]` | `/probe:[A] / /probe:[A]` | matched |
| Control · empty | `/probe:[] / /probe:[]` | `/probe:[] / /probe:[]` | matched |
| Challenge · extend | `/probe:[B] / /probe:[A, C] / /probe:[]` | `/probe:[A, B] / /probe:[A, C] / /probe:[A, C]` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 527` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/25656)
