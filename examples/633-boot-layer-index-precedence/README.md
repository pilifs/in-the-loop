# Preserve layer assignment when extracting a Boot-generated index

Compares physical layer contents from a genuinely generated index and a separate hand-authored overlapping index under each original extractor.

Both inputs use the same S49 packager to produce the ordinary compacted index. The root launcher class files are then taken from the respective S46 build, and the nested tools JAR is byte-identical to its S46 original. The mixed-index experiment edits only that index.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `app:marker/dep:library` | `app:marker/dep:library` | matched |
| Control | `app:marker/dep:library;app:marker/dep:library/app:sibling` | `app:marker/dep:library;app:marker/dep:library/app:sibling` | matched |
| Challenge | `first` | `second` | matched |

Replay with `python3 examples/tools/build.py 633` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/51653)
