# Keep measures distinct from elevations in binary geometry

The measured WKB line used 57 bytes with only the M flag. Both byte orders decoded the original measures 3 and 7 and left elevation absent.

Endianness determines how numbers are encoded, independent of the meaning of the third ordinate.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws java.lang.IllegalArgumentException` | `57/M/[1.0:2.0:NaN:3.0, 5.0:6.0:NaN:7.0]/1` | matched |
| Control | `73/ZM/[1.0:2.0:3.0:4.0, 5.0:6.0:7.0:8.0]/1` | `73/ZM/[1.0:2.0:3.0:4.0, 5.0:6.0:7.0:8.0]/1` | matched |
| Challenge | `throws java.lang.IllegalArgumentException` | `1:57/M/[1.0:2.0:NaN:3.0, 5.0:6.0:NaN:7.0]/1 / 0:57/M/[1.0:2.0:NaN:3.0, 5.0:6.0:NaN:7.0]/1` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 556`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/locationtech/jts/pull/1092)
