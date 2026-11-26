# Reusing Jackson's encoding buffers preserves the JSON stream

After encoding one JSON object the recycler's acquisitions and returns now balance. Two successive NDJSON streams preserved an embedded quote and newline.

A separate mapper decoded the actual bytes. The caller checks the pool after each synchronous subscription has unwound.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · mono | `acquired=true balanced=false object=one` | `acquired=true balanced=true object=one` | matched |
| Control · array | `array=[one, two]` | `array=[one, two]` | matched |
| Challenge · repeat | `records=2 equal=true balanced=false / records=2 equal=true balanced=false` | `records=2 equal=true balanced=true / records=2 equal=true balanced=true` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 491` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37059)
