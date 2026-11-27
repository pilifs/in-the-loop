# Config-tree values survive a parent segment in the import path

Compares enumeration and stream bytes for two spellings of the same owned directory using regular files.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `[]:absent` | `[a]:65` | matched |
| Control | `[a]:65` | `[a]:65` | matched |
| Challenge | `[a]:65/[]:absent` | `[a]:65/[a]:65` | matched |

Replay with `python3 examples/tools/build.py 594` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52666)
