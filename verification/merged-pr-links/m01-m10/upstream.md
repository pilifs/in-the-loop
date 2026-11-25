# Follow-up on the three historical counterexamples

The historical caller bytecode ran on six released library versions. All eighteen histories completed. The intent and control predictions held on every release. The challenge outcomes below distinguish the two issues that still reproduce from the later libGDX fix. The release versions were checked against Maven Central’s metadata on 2026-11-25. Each runtime JAR matched the checksum served by the repository, and the replay locks its SHA-256. [Artifact and JDK lock](release-inputs.json) · [Full release observations](release-observations.json) · [Release source JARs and development file digests](source-comparison.json)

## Commons Compress returns zero for a writer-produced preamble

On **1.23.0 and 1.28.0**, write a single ZIP32 entry containing the 50 UTF-8 bytes of the COMPRESS-621 issue URL. Give the archive the ASCII prefix `Before Zip file`, once by prepending it to the finished ZIP and once with `ZipArchiveOutputStream.writePreamble` before writing the entry. The first local header physically starts at 15 in both files. `ZipFile` lists the same entry and reads its complete body in both.

For the prepended file, `getFirstLocalFileHeaderOffset()` returns 15 and `getContentBeforeFirstLocalFileHeader()` yields the supplied bytes. For the writer-produced file the same calls return zero and null. The getter documents the length of the content before the first local header. The writer has already included its preamble in the ZIP offsets, so the reader’s offset adjustment and the physical header position differ. At development commit `a9a89fa47c17`, the ZIP32 calculation still uses the central-directory offset adjustment and the prefix getter still returns null for zero. This development check compared source. The released JARs supplied the JVM evidence. The original COMPRESS-621 ticket covers reading a post-write prefix. The user can file the writer/reader discrepancy as a follow-up. [Reproducer](../../../examples/446-compress-zip-preamble/caller/PublicCaller.java) · [Getter contract](https://github.com/apache/commons-compress/blob/0bacf83eb0b3367cd5572ab27e42a444efbcd5f8/src/main/java/org/apache/commons/compress/archivers/zip/ZipFile.java#L724-L743) · [Original ticket](https://issues.apache.org/jira/browse/COMPRESS-621)

## Agrona copied entries compare equal and hash differently

On **1.4.0 and 2.7.2**, populate an allocation-avoiding `Int2IntHashMap` with 1→10, 2→20 and 3→30. Convert its entry set with `toArray(new Map.Entry[0])` and insert the returned entries into a JDK `HashSet`. The backing map stays unchanged. Each entry equals a fresh JDK `SimpleImmutableEntry` of the same key and value, in both directions.

The three copied entries all returned hash 11. The corresponding JDK entries returned 11, 22 and 29. Probing the set with those JDK entries found only 1→10. The landed copy reads keys and values from its snapshot but hashes through the iterator cursor. The complete 2.7.2 Int2IntHashMap source file also matches development commit `e6c7256ec21d` byte for byte. A GitHub tracker search for `hashCode` and `Entry` on the check date returned a different change to IntArrayList. The user can file the three-entry reproduction against 2.7.2. [Reproducer](../../../examples/448-agrona-entry-arrays/caller/PublicCaller.java) · [Landed implementation](https://github.com/aeron-io/agrona/blob/13a9083e32f886c652041a536d13980a1ff982e0/agrona/src/main/java/org/agrona/collections/Int2IntHashMap.java) · [Map.Entry hash contract](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/Map.Entry.html#hashCode())

## libGDX repaired the reused bounds

On **1.13.0**, clipping into a previously read polygon reproduced the stale bounds of the original comparison. On **1.14.2**, the fresh and reused outputs returned the same four vertices and bounds (1,2,2,3). Upstream merged #7522 on 2024-11-22. It resets transformations on the output polygon and marks the transformed vertices dirty. This case already has an upstream resolution. [Reproducer](../../../examples/451-libgdx-clipped-bounds/caller/PublicCaller.java) · [Upstream repair](https://github.com/libgdx/libgdx/pull/7522)

## Repeat the release checks

The release runner compiles each caller against its earlier published release using the historical compiler. It requires every compiled class to match the historical receipt before launching the released libraries. The locked public JARs and the listed JDKs suffice on a fresh machine. Both Agrona releases run on JDK 17 with the same caller compiled on JDK 8. The Commons Compress and libGDX release trials use their historical JDK 11 and 17 respectively. The first command retrieves any missing release artifacts. The second reuses the pinned files offline. [Independent release job](../../jobs/2026/11/25/20261125-221211-repeat-three-historical-witnesses-on-six.json)

```sh
python3 verification/merged-pr-links/m01-m10/releases.py --fetch
python3 verification/merged-pr-links/m01-m10/releases.py
```
