# Recover the next JSON event after an interrupted encode

Reads successive successful encodes from one public writer on a new thread and checks event boundaries.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Control | `{"ok":"a"}/{"ok":"b"}` | `{"ok":"a"}/{"ok":"b"}` | matched |

Replay with `python3 examples/tools/build.py 625` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51156)
