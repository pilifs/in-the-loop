# Ten merged Java pull requests at their public APIs

All ten changes produced the intended parent-to-merge contrast. Across the thirty registered questions, **27 merged predictions held and three were refuted**. All ten controls met their predictions on both revisions. Nine controls returned byte-identical observations. The Commons Compress control read the same entry and payload on both sides and also exercised two accessors introduced by the merge. [Brief](organic-java-merged-pr-links-m01-m10-brief.md) · [Machine-readable audit](../../verification/merged-pr-links/m01-m10/audit.json)

| Example | Public observation |
|---|---|
| [M01 · RoaringBitmap](../../examples/443-roaring-unsigned-containment/README.md) | Heap, mutable and serialized readers rejected the missing block and accepted the complete unsigned top block on the merge. The retained snapshot still counted two after the new one counted one. |
| [M02 · Jackson Databind](../../examples/444-jackson-flattened-alias/README.md) | The parent populated the sibling but left the inner component null. The merge bound the alias and wrote exactly the canonical fields `b` and `c`. Reading that result produced the same record. |
| [M03 · Vavr](../../examples/445-vavr-matched-null/README.md) | A matched null suppressed the fallback on the merge. Moving 7 past null changed the selected value, and a rejected suffix preserved it. |
| [M04 · Commons Compress](../../examples/446-compress-zip-preamble/README.md) | The parent enumerated no entries in the supplied prefixed fixture. The merge recovered the entry, all 50 body bytes and the 15-byte prefix. A writer-produced preamble exposed a separate offset discrepancy. |
| [M05 · Commons RNG](../../examples/447-rng-cross-instance-state/README.md) | Following a failed restore, the parent receiver retained its own sequence. A merged receiver reproduced ten donor integers, and two recipients with different histories reproduced 35 booleans and the following integer. |
| [M06 · Agrona](../../examples/448-agrona-entry-arrays/README.md) | Both array overloads on all four maps retained three distinct pairs on the merge. Two of the three primitive entries still failed lookup with an equal JDK entry. |
| [M07 · Spatial4j](../../examples/449-spatial4j-geojson-siblings/README.md) | The parent threw while closing the enclosing list. The merge serialized the MultiPoint, both orders of the geometry collection and the trailing sibling. A fresh JSON reader checked the entire tree. |
| [M08 · Checkstyle](../../examples/450-checkstyle-record-fields/README.md) | The member record’s `quota` finding disappeared. A real CLI audit kept the ordinary class finding and reported exactly the nested `limit` parameter in both record spellings. |
| [M09 · libGDX](../../examples/451-libgdx-clipped-bounds/README.md) | The merge rejected the degenerate result with either a fresh or null output. In both revisions a reused polygon held the correct local vertices and returned its previous bounds. |
| [M10 · TinkerPop](../../examples/452-tinkerpop-dedup-projections/README.md) | Two projections on one step returned all six Modern names on the parent and threw during the second `by()` on the merge. Two separate steps returned the same four people as the single-age control. |

## Three refuted predictions

- **Commons Compress.** Both generated ZIP32 archives had their first local header at byte 15. Both returned the identical named payload. The reader reported offset 15 and the original prefix when the bytes were prepended after writing, but zero and a null prefix when `writePreamble` wrote the same bytes before the entry. [Both readbacks](../../examples/446-compress-zip-preamble/observations.json)
- **Agrona.** Without changing the backing map, each copied entry compared equal to its JDK counterpart in both directions. All three copies hashed to 11. The JDK reference hashes were 11, 22 and 29, and the set lookup returned true, false and false. [Entries, hashes and lookups](../../examples/448-agrona-entry-arrays/observations.json)
- **libGDX.** Pre-reading the output polygon’s bounds before reuse exposed stale transformed coordinates. With the same two input rectangles and a successful clip, the fresh bounds were (1,2,2,3) and the reused bounds were (−4,−4,2,2). The four local vertices agreed. This refuted the geometry consistency prediction on the parent as well as the merge. [Both geometries](../../examples/451-libgdx-clipped-bounds/observations.json)

## Deployment and replay

Each of the 60 public histories starts a fresh caller JVM. Each pair uses the same compiled caller, the registered JDK, ordered dependency hashes and original class providers. Checkstyle also runs eight child CLI processes and checks the provider of its CLI and check in each child. The two JDK 8 cases use that VM’s class-loading records. Jackson’s two exact databind revisions share reconstructed core and annotation snapshots. Setup identifies their source commits and the unavailable historical inputs. [Artifact preparation](organic-java-merged-pr-links-m01-m10-brief-setup.md) · [Independent replay job](../../verification/jobs/2026/11/25/20261125-220316-replay-all-30-m01-m10-public-predictions.json)

```sh
python3 verification/merged-pr-links/audit.py --campaign m01-m10
python3 examples/tools/build.py --plan 446
python3 examples/tools/build.py 446
```
