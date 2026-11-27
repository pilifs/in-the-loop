# Closing a context detaches meters registered after startup

Retains each late meter registry across context closure and reads global membership, closure and a surviving sibling’s counter.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `true/true:false` | `true/false:true` | matched |
| Control | `false:1.0:false` | `false:1.0:false` | matched |
| Challenge | `true:false/true:false:1.0/true:false` | `false:true/true:false:1.0/false:true` | matched |

Replay with `python3 examples/tools/build.py 602` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50886)
