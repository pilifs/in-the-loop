# Inherited command-line map options retain their fallback values

Inherited -Dkey now inserted a present key with a null value. Root and subcommand parsing agreed on both null and an independently configured empty string.

Inheritance changes where the option can be spelled, while fallback belongs to the declared option. The two distinct map values expose an incorrect copy even when parse succeeds.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `throws picocli.CommandLine$ParameterException` | `1/true/<null>` | matched |
| Control | `1/true/actual` | `1/true/actual` | matched |
| Challenge | `throws picocli.CommandLine$ParameterException` | `1/true/empty / 1/true/empty / 1/true/<null> / 1/true/<null>` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 584`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/remkop/picocli/pull/2036)
