# JUL records still reach the logging backend after a test context resumes

Checks context identity and counts JUL and direct SLF4J markers at the same Logback appender after each reuse.

The TestContext adapter uses the unchanged spring-boot-test main tree 40d684720ce0fde87e00849f58ec523058db2deb shared by both S37 pins and S34 parent. Both S37 runs use those same adapter bytes. The logging module itself comes from the respective S37 build.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `reused:true;1/1,1/1,0/1` | `reused:true;1/1,1/1,1/1` | matched |
| Control | `reused:true;1/1,1/1,1/1` | `reused:true;1/1,1/1,1/1` | matched |
| Challenge | `reused:true;1/1,1/1,0/1,0/1` | `reused:true;1/1,1/1,1/1,1/1` | matched |

Replay with `python3 examples/tools/build.py 624` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51959)
