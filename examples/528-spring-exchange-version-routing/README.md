# Dispatch versioned HTTP exchange controllers

Versioned HTTP exchange controllers now dispatch to v1.1 on MVC and WebFlux. Both stacks rejected version 99 with HTTP 400 and zero controller invocations.

MockMvc and WebTestClient used the same published Spring Test 7.0.10 client companion with both original server revisions. Standard request mappings provided the control.

For a fresh setup cache, place the published JAR at `releases/spring-test-7.0.10/jars/spring-test-7.0.10.jar` under the campaign cache. Its SHA-256 is `73c18292b63e814c415c1c470fcc47be1e21442b80ee31a0bcd949e53d0c49bd`. The replay checks it before dispatch. [Maven Central artifact](https://repo.maven.apache.org/maven2/org/springframework/spring-test/7.0.10/spring-test-7.0.10.jar) · [Published checksum](https://repo.maven.apache.org/maven2/org/springframework/spring-test/7.0.10/spring-test-7.0.10.jar.sha256)

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · exchange | `ambiguous` | `200:v1.1:1` | matched |
| Control · request | `200:v1.1:1 / 400:0` | `200:v1.1:1 / 400:0` | matched |
| Challenge · stacks | `ambiguous / ambiguous \| ambiguous / ambiguous` | `200:v1.1:1 / 400:0 \| 200:v1.1:1 / 400:0` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 528` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/36602)
