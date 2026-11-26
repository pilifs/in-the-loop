# A UTF-32 supplementary character survives a parser refill

All seven prefix lengths recovered both supplementary characters in both UTF-32 byte orders. Shifting the input by one space also agreed with the independent UTF-8 parse.

The unavailable snapshot parent POM was rebuilt from Jackson BOM 7796a7ddb240ce41c1b6c6a3a435b29948a6a727.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `tested=14,exact=10,wrong=[UTF-32BE@3995+0:[1f600, d800], UTF-32LE@3995+0:[1f600, d800], UTF-32BE@3997+0:[d83d, f600, 10000], UTF-32LE@3997+0:[d83d, f600, 10000]]` | `tested=14,exact=14,wrong=[]` | matched |
| Control | `tested=14,exact=14,wrong=[]` | `tested=14,exact=14,wrong=[]` | matched |
| Challenge | `tested=28,exact=22,wrong=[UTF-32BE@3995+0:[1f600, d800], UTF-32LE@3995+0:[1f600, d800], UTF-32BE@3996+1:[d83d, f600, 10000], UTF-32LE@3996+1:[d83d, f600, 10000], UTF-32BE@3997+0:[d83d, f600, 10000], UTF-32LE@3997+0:[d83d, f600, 10000]]` | `tested=28,exact=28,wrong=[]` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 555`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/FasterXML/jackson-core/pull/1716)
