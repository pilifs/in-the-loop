# Generation record for merged Java pull requests M01–M10

The rows follow the submission order. Source observations are distinguished from expectations that still need execution. The last two columns give SHA-256 prefixes for the GitHub metadata and pinned-source responses read on 2026-11-25, cached under `$TMPDIR/m-brief/<PR number>/` as `pr.json` and `sources.json`.

| Pull request | State | Authoring input, outcome and open question | PR digest | Source digest |
|---|---|---|---|---|
| RoaringBitmap/RoaringBitmap#863 | written | Read #862, both implementations and six landed tests. The top-block endpoint has logical key 65,536. The PR reports parent failures and merge passes. Keeping two independently serialized snapshots across removal remains open. | `910023aa16f0ad95` | `254391c817b50f39` |
| FasterXML/jackson-databind#5913 | written | Read #5911, both submitted changes, the squashed name collection and five regression methods. The issue compares released versions. Its pinned-parent failure mode and canonical JSON write/read cycle remain unexecuted. | `9d9f3b52f929e392` | `3970509d6c3ee91b` |
| vavr-io/vavr#3272 | written | Compared parent Option.of(last) with the landed found flag, the Option.some(null) contract and three new tests. The reordered null/7 inputs and whether the fallback supplier runs remain unexecuted. | `3266776c05bd7e2f` | `71ed0d48bf0f5d4b` |
| apache/commons-compress#334 | not yet | — | — | — |
| apache/commons-rng#65 | not yet | — | — | — |
| aeron-io/agrona#202 | not yet | — | — | — |
| locationtech/spatial4j#212 | not yet | — | — | — |
| checkstyle/checkstyle#14128 | not yet | — | — | — |
| libgdx/libgdx#7278 | not yet | — | — | — |
| apache/tinkerpop#3105 | not yet | — | — | — |
