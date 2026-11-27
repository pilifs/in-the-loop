# Apply the configured Kafka shutdown policy to asynchronous listener results

Reads the shutdown policy independently from the factory template and an actual container created from it.

This original Boot pair uses the setup’s Spring Kafka 4.2.0-M2 dependency. These configuration observations do not measure completion ordering at a broker.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `false:false` | `true:true` | matched |
| Control | `false:false/false:false` | `false:false/false:false` | matched |

Replay with `python3 examples/tools/build.py 617` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51774)
