# Isolate message-bundle discovery across context class loaders

Successive contexts share Boot classes but see different resource roots. Both the installed bean and the resolved message are observed.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `false:missing/false:missing` | `false:missing/true:bar` | matched |
| Control | `true:bar/true:bar` | `true:bar/true:bar` | matched |
| Challenge | `true:bar/true:missing` | `true:bar/false:missing` | matched |

Replay with `python3 examples/tools/build.py 601` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52831)
