# Repeated reads and copies of a small multipart file

Two reads and a filesystem copy now returned all six in-memory upload bytes. Interleaved readers preserved independent positions at both storage thresholds.

The destination started longer than the upload. Its bytes and the first reader's remaining suffix were observed after transfer.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent · memory | `abcdef//` | `abcdef/abcdef/abcdef` | matched |
| Control · disk | `abcdef/abcdef/abcdef` | `abcdef/abcdef/abcdef` | matched |
| Challenge · interleave | `a/bcdef// \| a/abcdef/abcdef/bcdef` | `a/abcdef/abcdef/bcdef \| a/abcdef/abcdef/bcdef` | matched |

With the prepared campaign cache, run `python3 examples/tools/build.py 487` to repeat this comparison. [Registered questions and falsifiers](comparison.json) · [Public caller](caller/PublicCaller.java) · [Locked inputs](runtime.json) · [Measured outcomes](observations.json) · [Upstream pull request](https://github.com/spring-projects/spring-framework/pull/37531)
