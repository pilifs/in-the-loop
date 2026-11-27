# Extract a runnable JAR and both library scopes from an executable WAR

Extracts an actual packaged executable, reads the relocated web resources and dependency bytes, then launches its application JAR from a separate directory.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `invalid-library-location` | `both:ordered:html+jsp:REG/PROV` | matched |
| Control | `both:ordered:REG/PROV` | `both:ordered:REG/PROV` | matched |
| Challenge | `invalid-library-location/invalid-library-location` | `both:ordered:html+jsp:REG/PROV/collision:both-paths` | matched |

Replay with `python3 examples/tools/build.py 636` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51372)
