# GNU sparse TAR extraction starts at the first data record

An aligned sparse TAR map now produced three zeros followed by ABCD. Replacing the data with WXYZ preserved the next member’s name, payload and end of archive.

The file data and the next member have independent TAR boundaries. Successful delivery of the first file alone does not prove subsequent alignment.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `[0, 0, 0, 0, 0, 0, 0]` | `[0, 0, 0, 65, 66, 67, 68]` | matched |
| Control | `[0, 0, 0, 65, 66, 67, 68]` | `[0, 0, 0, 65, 66, 67, 68]` | matched |
| Challenge | `throws org.apache.commons.compress.archivers.ArchiveException` | `[0, 0, 0, 87, 88, 89, 90]/tail/Z/true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 554`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-compress/pull/775)
