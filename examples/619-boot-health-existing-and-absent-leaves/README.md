# Missing intermediate health contributors resolve as absent

Reads a known healthy leaf and a missing terminal child on the same owned composite using the original health module.

The two original S32 health modules are first on their own classpaths. Both run over the same pinned Jersey/Tomcat transport from S34. This caller covers the two terminal-leaf controls.

On the merged health class, a bytecode check found an immediate return after a missing child. The two public intermediate-path claims remain open. [Merged class evidence](../../verification/merged-pr-links/s01-s50/repaired-guards.json)

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Control | `200:UP/404` | `200:UP/404` | matched |

Replay with `python3 examples/tools/build.py 619` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52321)
