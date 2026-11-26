# Carry immutable builder replacements through buffered property assignment

Buffered properties survived replacement of the immutable builder. Creator-first, creator-last and array encodings returned the same record, including after changing only b.

Both builds use the timestamped Jackson Core 3.4.0 and annotations 2.24 snapshots listed in runtime.json.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `0,0,7,8` | `5,6,7,8` | matched |
| Control | `7/value` | `7/value` | matched |
| Challenge | `5,6,7,8 / 0,0,7,0 / 0,0,7,8 / 5,16,7,8 / 0,0,7,0 / 0,0,7,8` | `5,6,7,8 / 5,6,7,8 / 5,6,7,8 / 5,16,7,8 / 5,16,7,8 / 5,16,7,8` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 565`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/FasterXML/jackson-databind/pull/6407)
