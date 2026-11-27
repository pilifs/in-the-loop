# Resolve constructor defaults before type conversion

Reads a typed duration from the application’s configuration-properties bean under explicit, fallback and invalid settings.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `conversion-failed` | `PT72H` | matched |
| Control | `PT120H` | `PT120H` | matched |
| Challenge | `PT120H/conversion-failed` | `PT120H/conversion-failed` | matched |

Replay with `python3 examples/tools/build.py 589` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51661)
