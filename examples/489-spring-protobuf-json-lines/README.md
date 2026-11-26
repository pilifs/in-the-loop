# JSON Lines selection and physical line boundaries for protobuf

The compact encoder now selects JSONL and produces two parseable records. The default printer produced 12 physical lines for those two messages, none independently parseable.

The observer concatenates the actual bytes and splits at LF. Each complete record is checked against its original generated message. NDJSON with the compact printer stayed stable.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · jsonl | `not selected` | `lines=2 terminated=true decoded=[123, 456]` | matched |
| Control · ndjson | `lines=2 terminated=true decoded=[123, 456]` | `lines=2 terminated=true decoded=[123, 456]` | matched |
| Challenge · default | `not selected` | `lines=12 terminated=true decoded=[invalid, invalid, invalid, invalid, invalid, invalid, invalid, invalid, invalid, invalid, invalid, invalid]` | refuted |

With the prepared campaign cache, run `python3 examples/tools/build.py 489` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37559)
