# Reach a named health group through a multi-segment path

Parses the health status and component names at exact aliases and a nested component URL on an original MVC server.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `throws org.springframework.beans.factory.BeanCreationException` | `200:UP:diskSpace` | matched |
| Control | `200:UP:diskSpace` | `200:UP:diskSpace` | matched |
| Challenge | `throws org.springframework.beans.factory.BeanCreationException` | `200:UP:near/200:UP:far/404;200:UP:near/200:UP:far/404` | refuted |

Replay with `python3 examples/tools/build.py 620` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51470)
