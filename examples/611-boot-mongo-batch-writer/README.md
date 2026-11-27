# Selecting the transaction manager for a Mongo Batch repository

Writes Batch metadata on a local Mongo replica set. Records the selected manager’s acquisition and commit before reading back the execution ID and job name.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `false:false:true` | `true:true:true` | matched |
| Control | `true` | `true` | matched |
| Challenge | `false:false:true:true` | `true:true:false:true` | matched |

Replay with `python3 examples/tools/build.py 611` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51725)
