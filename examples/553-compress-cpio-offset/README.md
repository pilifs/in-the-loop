# Verify a CPIO entry checksum when the caller reads into a slice

The CPIO reader accepted checksum 132 after delivering unsigned bytes 1, 128 and 3 at a nonzero offset. Both one-byte read patterns preserved their prefix and reached the following entry.

Both pins use the same Commons IO snapshot rebuilt from e19519ad1a61ec6852601d28ffe94a8967e4e3e0.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `IOException (ArchiveException, checksum=true)/[1, 128, 3]` | `a:[1, 128, 3]/eof=-1/b:7/end=true/prefix=true` | matched |
| Control | `a:[1, 128, 3]/eof=-1/b:7/end=true/prefix=true` | `a:[1, 128, 3]/eof=-1/b:7/end=true/prefix=true` | matched |
| Challenge | `IOException (ArchiveException, checksum=true)/[1, 128, 3] / IOException (ArchiveException, checksum=true)/[1, 128, 3]` | `a:[1, 128, 3]/eof=-1/b:7/end=true/prefix=true / a:[1, 128, 3]/eof=-1/b:7/end=true/prefix=true` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 553`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/commons-compress/pull/725)
