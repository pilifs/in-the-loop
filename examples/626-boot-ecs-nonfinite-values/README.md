# Non-finite floating-point values leave structured log events parseable

Parses complete ECS console events with an independent strict JSON reader, checking scalar and primitive-array types.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `invalid-json,invalid-json,invalid-json,invalid-json,invalid-json,invalid-json` | `string:NaN,string:Infinity,string:-Infinity,string:NaN,string:Infinity,string:-Infinity` | matched |
| Control | `number:1.25,number:-2.5` | `number:1.25,number:-2.5` | matched |
| Challenge | `invalid-json` | `string:NaN/[number:1.0,string:NaN]` | matched |

Replay with `python3 examples/tools/build.py 626` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/52477)
