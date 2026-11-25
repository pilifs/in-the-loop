# Generation record for merged Java pull requests M01–M10

The rows follow the submission order. Source observations are distinguished from expectations that still need execution. The last two columns give SHA-256 prefixes for the GitHub metadata and pinned-source responses read on 2026-11-25, cached under `~/.cache/in-the-loop/agent-tmp/ea63c5f6-1929-4c3f-9921-139ac43a8b86/m-brief/<PR number>/` as `pr.json` and `sources.json`.

| Pull request | State | Authoring input, outcome and open question | PR digest | Source digest |
|---|---|---|---|---|
| RoaringBitmap/RoaringBitmap#863 | written | Read #862, both implementations and six landed tests. The top-block endpoint has logical key 65,536. The PR reports parent failures and merge passes. Keeping two independently serialized snapshots across removal remains open. | `910023aa16f0ad95` | `254391c817b50f39` |
| FasterXML/jackson-databind#5913 | written | Read #5911, both submitted changes, the squashed name collection and five regression methods. The issue compares released versions. Its pinned-parent failure mode and canonical JSON write/read cycle remain unexecuted. | `9d9f3b52f929e392` | `3970509d6c3ee91b` |
| vavr-io/vavr#3272 | written | Compared parent Option.of(last) with the landed found flag, the Option.some(null) contract and three new tests. The reordered null/7 inputs and whether the fallback supplier runs remain unexecuted. | `3266776c05bd7e2f` | `71ed0d48bf0f5d4b` |
| apache/commons-compress#334 | written | Read COMPRESS-621 and the landed fixture test, reader and writer. Read the 217-byte pinned ZIP (SHA-256 198e954c1f2eaf9cf1cf8b7ce991d74ac3a0e2acfa7616dfbf7c8231ee6b20e0). Its local header is at 15, directory at 133, and 50-byte entry matches the issue URL. EOCD gives 195−62−118=15. The writer counts writePreamble in its offsets, so the reader’s difference is zero for that arrangement. Entry/prefix readback across both writer histories is unexecuted. | `f168b97c78f64547` | `a6381deabeb08bae` |
| apache/commons-rng#65 | written | Read RNG-115 and the pinned adapter, bit provider and replay test. Three boolean draws leave 29 cached bits. The parent reads an empty delegate stream on an unsaved recipient. Its next draw after failure and the merged 35-boolean continuation are unexecuted. | `ce1242e3278193a1` | `b8ba6986ae3c091b` |
| aeron-io/agrona#202 | written | Read five submitted commits and the landed changes in four map/test pairs. The primitive entry copies its key/value but hashes the iterator’s current pair. Independent entry hashes are 11, 22 and 29. HashSet lookup on the returned array entries is unexecuted. | `b9c7c75867171cce` | `52dd0c284a74553f` |
| locationtech/spatial4j#212 | written | Read issue #210, both submitted changes, landed registration, geometry serializer and standalone writer tests. The issue reports a Point-list success and MultiPoint-list failure. GeometryCollection children followed by an enclosing map sibling have not been exercised. | `b7f08261af1cffcd` | `7f2cfd64bcc382cc` |
| checkstyle/checkstyle#14128 | not yet | — | — | — |
| libgdx/libgdx#7278 | not yet | — | — | — |
| apache/tinkerpop#3105 | not yet | — | — | — |
