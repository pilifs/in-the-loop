# A test bean override can target one level of a context hierarchy

A child-only override now preserves the parent greeting and field identity. Two different mocked children reused the identical parent with neither mock registered there.

Each hierarchy is declared on the concrete Jupiter test. Both mock clients run on the same JVM and Spring context cache.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · child | `selector unavailable` | `P/X local=true field=true` | matched |
| Control · all | `X/X` | `X/X` | matched |
| Challenge · split | `B/B fields=true parentAgain=B` | `A/B fields=true parentAgain=A` | matched |
| Challenge · cache | `mocks=true parentReused=false parentClean=false` | `mocks=true parentReused=true parentClean=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 501` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/34723)

Moving the hierarchy declaration to an abstract superclass caused both subclass field overrides to fail on the landing and Spring 7.1.0. [Separate inheritance follow-up](inherited-hierarchy/README.md)
