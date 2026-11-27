# An application customizer can select the string converter

Reads HTTP bytes from a servlet response and an independent endpoint receiving the Boot-customized synchronous client’s request.

Both deployments use the same released Tomcat 11.0.24 transport. Spring MVC and RestClient consume the original Boot server and client customizers in their declared order.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `200:c3a9` | `200:e9` | matched |
| Control | `200:c3a9` | `200:c3a9` | matched |
| Challenge | `200:c3a9/200:c3a9` | `200:e9/200:e9` | matched |

Replay with `python3 examples/tools/build.py 604` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52251)
