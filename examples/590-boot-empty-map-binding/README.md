# An explicitly empty map binds as a present value

Distinguishes an empty bound map from an absent value and checks the same property through YAML application startup.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `conversion-failed` | `bound:{}` | matched |
| Control | `bound:{a=one, b=two}` | `bound:{a=one, b=two}` | matched |
| Challenge | `conversion-failed/conversion-failed` | `{}/{}` | matched |

Replay with `python3 examples/tools/build.py 590` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50773)
