# Apply the configured Kafka shutdown policy to asynchronous listener results

Reads the shutdown policy independently from the factory template and an actual container created from it.

Both Boot revisions use the setup’s Spring Kafka 4.2.0-M2 substitution. The challenge runs its test kit’s genuine Kafka 4.3.1 KRaft broker on loopback and records a completed listener future and the container stop callback.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `false:false` | `true:true` | matched |
| Control | `false:false/false:false` | `false:false/false:false` | matched |
| Challenge | `stopping:true/future:normal/callback:after` | `stopping:true/future:normal/callback:after` | matched |

Replay with `python3 examples/tools/build.py 617` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51774)
