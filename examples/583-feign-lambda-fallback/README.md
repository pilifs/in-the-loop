# Invoke a lambda fallback supplied by a Feign fallback factory

The real HTTP 400 response invoked an application-package lambda. Two failing GETs received fresh fallback-1 and fallback-2 values, while a successful GET bypassed the factory.

The factory contract creates a fallback per exception. A single constant fallback result cannot detect reuse across calls.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `gets=1,factories=1,error=java.lang.IllegalAccessException` | `gets=1,factories=1,result=fallback` | matched |
| Control | `gets=1,factories=0,result=server` | `gets=1,factories=0,result=server` | matched |
| Challenge | `gets=1,factories=1,error=java.lang.IllegalAccessException` | `gets=2,factories=2,results=[fallback-1, fallback-2]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 583`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/resilience4j/resilience4j/pull/1999)

With identical compiled caller bytes, 2.1.0 matched the parent and 2.2.0 matched the landing on all three histories. [Release measurements](../../verification/merged-pr-links/r01-r50/release-observations.json)
